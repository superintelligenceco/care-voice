"""Twilio Programmable Voice adapter.

EXPERIMENTAL. This adapter places real phone calls when configured with
real credentials. Test it with your own phone number first, and read the
safety notes in the README before you point it at anyone else.

How a call flows:

1. :meth:`TwilioAdapter.start_checkin` calls the Twilio REST API to ring the
   person. Twilio fetches ``<public_url>/twilio/voice`` when they answer.
2. Each ``/twilio/voice`` request carries Twilio's speech-to-text result in
   ``SpeechResult``. The adapter feeds it to the session and replies with
   TwiML: ``<Gather input="speech">`` wrapping a ``<Say>`` of the next line.
3. ``/twilio/status`` receives call status callbacks. ``no-answer``,
   ``busy``, ``failed``, and ``canceled`` trigger a retry until the
   configured number of attempts is used up, and then a ``NO_ANSWER``
   check-in is recorded.

Every webhook is checked against the ``X-Twilio-Signature`` header before
it is processed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import threading
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from xml.sax.saxutils import escape, quoteattr

from care_voice.engine import CheckinSession
from care_voice.models import CheckinStatus
from care_voice.service import CareVoice
from care_voice.telephony.base import CallEvent

log = logging.getLogger(__name__)

API_BASE = "https://api.twilio.com/2010-04-01"
UNANSWERED_STATUSES = frozenset({"no-answer", "busy", "failed", "canceled"})

Opener = Callable[[urllib.request.Request], bytes]
Scheduler = Callable[[float, Callable[[], None]], None]


def compute_signature(url: str, params: Mapping[str, str], auth_token: str) -> str:
    """Compute Twilio's ``X-Twilio-Signature`` for a form-encoded POST."""
    payload = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def validate_signature(
    url: str, params: Mapping[str, str], signature: str, auth_token: str
) -> bool:
    """Return ``True`` when ``signature`` matches the request."""
    expected = compute_signature(url, params, auth_token)
    return hmac.compare_digest(expected, signature or "")


def _default_opener(req: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed https base
        body: bytes = resp.read()
        return body


def _thread_scheduler(delay: float, fn: Callable[[], None]) -> None:
    timer = threading.Timer(delay, fn)
    timer.daemon = True
    timer.start()


@dataclass
class _Round:
    attempts: int = 0


class TwilioAdapter:
    """A :class:`~care_voice.telephony.base.VoiceAdapter` for Twilio. EXPERIMENTAL."""

    name = "twilio"

    def __init__(
        self,
        app: CareVoice,
        account_sid: str,
        auth_token: str,
        from_number: str,
        public_url: str,
        opener: Opener = _default_opener,
        scheduler: Scheduler = _thread_scheduler,
    ) -> None:
        if not (account_sid and auth_token and from_number and public_url):
            raise ValueError("Twilio needs account_sid, auth_token, from_number, and public_url")
        if not public_url.startswith("https://"):
            raise ValueError("public_url must be an https:// URL that Twilio can reach")
        self.app = app
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.public_url = public_url.rstrip("/")
        self.opener = opener
        self.scheduler = scheduler
        self.sessions: dict[str, CheckinSession] = {}
        self._round = _Round()
        self._to_number = ""
        self._lock = threading.Lock()

    @property
    def voice_url(self) -> str:
        return f"{self.public_url}/twilio/voice"

    @property
    def status_url(self) -> str:
        return f"{self.public_url}/twilio/status"

    # Outbound calls -----------------------------------------------------

    def start_call(self, to_number: str) -> str:
        form = urllib.parse.urlencode(
            {
                "To": to_number,
                "From": self.from_number,
                "Url": self.voice_url,
                "Method": "POST",
                "StatusCallback": self.status_url,
                "StatusCallbackMethod": "POST",
                "StatusCallbackEvent": "completed",
                "Timeout": "30",
            }
        ).encode()
        token = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        req = urllib.request.Request(  # noqa: S310 - fixed https base
            f"{API_BASE}/Accounts/{self.account_sid}/Calls.json",
            data=form,
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        payload = json.loads(self.opener(req))
        call_sid = str(payload["sid"])
        log.info("placed call %s", call_sid)
        return call_sid

    def start_checkin(self, to_number: str) -> str:
        """Start a new check-in round (first attempt) and return the call id."""
        with self._lock:
            self._round = _Round(attempts=1)
            self._to_number = to_number
        return self.start_call(to_number)

    # Webhooks -------------------------------------------------------------

    def event_from_voice_webhook(self, params: Mapping[str, str]) -> CallEvent:
        call_id = params.get("CallSid", "")
        speech = params.get("SpeechResult", "")
        if call_id not in self.sessions:
            kind = "answered"
        else:
            kind = "speech" if speech.strip() else "silence"
        return CallEvent(call_id=call_id, kind=kind, text=speech, raw=dict(params))

    @staticmethod
    def event_from_status_callback(params: Mapping[str, str]) -> CallEvent:
        status = params.get("CallStatus", "")
        kind = "unanswered" if status in UNANSWERED_STATUSES else "ended"
        return CallEvent(call_id=params.get("CallSid", ""), kind=kind, raw=dict(params))

    def handle_event(self, event: CallEvent) -> str:
        if event.kind == "answered":
            session = self.app.new_session()
            self.sessions[event.call_id] = session
            return self._twiml(session, session.start())
        if event.kind in ("speech", "silence"):
            active = self.sessions.get(event.call_id)
            if active is None:
                return self._hangup_twiml()
            line = active.respond(event.text if event.kind == "speech" else "")
            return self._twiml(active, line)
        if event.kind == "ended":
            self._finish(event.call_id, hung_up=True)
            return ""
        if event.kind == "unanswered":
            self._unanswered()
            return ""
        raise ValueError(f"unknown event kind {event.kind!r}")

    # Internals -------------------------------------------------------------

    def _finish(self, call_id: str, hung_up: bool = False) -> None:
        session = self.sessions.pop(call_id, None)
        if session is None:
            return
        if hung_up:
            session.hang_up()
        result = session.result()
        result.attempts = max(1, self._round.attempts)
        self.app.process(result)

    def _unanswered(self) -> None:
        with self._lock:
            attempts = self._round.attempts
            limit = self.app.config.checkin.call_attempts
            if attempts < limit and self._to_number:
                self._round.attempts += 1
                delay = self.app.config.checkin.retry_delay_minutes * 60
                to_number = self._to_number
                self.scheduler(delay, lambda: self._retry(to_number))
                return
        session = self.app.new_session()
        result = session.result()
        result.status = CheckinStatus.NO_ANSWER
        result.attempts = max(1, attempts)
        self.app.process(result)

    def _retry(self, to_number: str) -> None:
        try:
            self.start_call(to_number)
        except Exception:
            log.exception("retry call failed")
            self._unanswered()

    def _twiml(self, session: CheckinSession, line: str | None) -> str:
        say = f"<Say>{escape(line)}</Say>" if line else ""
        if session.done:
            call_id = next((k for k, v in self.sessions.items() if v is session), None)
            if call_id is not None:
                self._finish(call_id)
            return f'<?xml version="1.0" encoding="UTF-8"?><Response>{say}<Hangup/></Response>'
        action = quoteattr(self.voice_url)
        return (
            '<?xml version="1.0" encoding="UTF-8"?><Response>'
            f'<Gather input="speech" action={action} method="POST" speechTimeout="auto"'
            f' timeout="6">{say}</Gather>'
            f'<Redirect method="POST">{escape(self.voice_url)}</Redirect></Response>'
        )

    @staticmethod
    def _hangup_twiml() -> str:
        return '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>'
