import json
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from care_voice.config import parse_config
from care_voice.dashboard import serve
from care_voice.models import CheckinStatus
from care_voice.service import CareVoice
from care_voice.store import Store
from care_voice.telephony.base import CallEvent
from care_voice.telephony.twilio import TwilioAdapter, compute_signature, validate_signature

from .conftest import GOOD_DAY


def test_signature_matches_twilio_reference_vector():
    # Reference values from Twilio's request validation documentation and SDK tests.
    params = {
        "CallSid": "CA1234567890ABCDE",
        "Caller": "+12349013030",
        "Digits": "1234",
        "From": "+12349013030",
        "To": "+18005551212",
    }
    url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    assert compute_signature(url, params, "12345") == "0/KCTR6DLpKmkAf8muzZqo1nDgQ="
    assert validate_signature(url, params, "0/KCTR6DLpKmkAf8muzZqo1nDgQ=", "12345")
    assert not validate_signature(url, params, "bogus", "12345")


class Recorder:
    def __init__(self):
        self.requests = []
        self.scheduled = []

    def opener(self, req):
        self.requests.append(req)
        return json.dumps({"sid": f"CA{len(self.requests)}"}).encode()

    def scheduler(self, delay, fn):
        self.scheduled.append((delay, fn))


@pytest.fixture
def app():
    cfg = parse_config({"person": {"name": "Ada"}, "notifiers": []})
    return CareVoice.from_config(cfg, store=Store(":memory:"))


@pytest.fixture
def rec():
    return Recorder()


@pytest.fixture
def adapter(app, rec):
    return TwilioAdapter(
        app, "AC123", "token", "+15555550199", "https://cv.example.com/", rec.opener, rec.scheduler
    )


def test_constructor_validation(app):
    with pytest.raises(ValueError):
        TwilioAdapter(app, "", "t", "+1", "https://x")
    with pytest.raises(ValueError):
        TwilioAdapter(app, "AC", "t", "+1", "http://x")


def test_start_call_uses_rest_api(adapter, rec):
    assert adapter.start_checkin("+15555550100") == "CA1"
    (req,) = rec.requests
    assert req.full_url == "https://api.twilio.com/2010-04-01/Accounts/AC123/Calls.json"
    assert req.get_header("Authorization").startswith("Basic ")
    form = dict(urllib.parse.parse_qsl(req.data.decode()))
    assert form["To"] == "+15555550100"
    assert form["Url"] == "https://cv.example.com/twilio/voice"
    assert form["StatusCallback"] == "https://cv.example.com/twilio/status"


def test_full_call_flow_records_checkin(adapter, app):
    first = adapter.handle_event(adapter.event_from_voice_webhook({"CallSid": "CA1"}))
    assert '<Gather input="speech"' in first
    assert "Good morning, Ada." in first
    twiml = ""
    for reply in GOOD_DAY:
        event = adapter.event_from_voice_webhook({"CallSid": "CA1", "SpeechResult": reply})
        assert event.kind == "speech"
        twiml = adapter.handle_event(event)
    assert "<Hangup/>" in twiml and "Thank you, Ada." in twiml
    assert adapter.sessions == {}
    (saved,) = app.store.recent_checkins()
    assert saved.status is CheckinStatus.COMPLETED
    assert saved.value("mood") == 4
    # The final status callback after a finished call is a no-op.
    assert (
        adapter.handle_event(
            adapter.event_from_status_callback({"CallSid": "CA1", "CallStatus": "completed"})
        )
        == ""
    )
    assert len(app.store.recent_checkins()) == 1


def test_silence_and_escaping(adapter):
    adapter.handle_event(CallEvent("CA9", "answered"))
    event = adapter.event_from_voice_webhook({"CallSid": "CA9"})
    assert event.kind == "silence"
    twiml = adapter.handle_event(event)
    assert "Sorry, I didn't quite catch that." in twiml
    assert "didn&apos;t" not in twiml  # apostrophes are fine in XML text
    assert adapter.handle_event(CallEvent("unknown", "speech", "hi")).endswith(
        "<Hangup/></Response>"
    )


def test_hang_up_mid_call_is_abandoned(adapter, app):
    adapter.handle_event(CallEvent("CA2", "answered"))
    adapter.handle_event(CallEvent("CA2", "speech", "yes"))
    adapter.handle_event(
        adapter.event_from_status_callback({"CallSid": "CA2", "CallStatus": "completed"})
    )
    (saved,) = app.store.recent_checkins()
    assert saved.status is CheckinStatus.ABANDONED
    codes = [a.code for a in app.store.recent_alerts()]
    assert codes == ["CHECKIN_INCOMPLETE"]


def test_unanswered_retries_then_alerts(adapter, app, rec):
    adapter.start_checkin("+15555550100")
    unanswered = {"CallSid": "CA1", "CallStatus": "no-answer"}
    for expected_retries in (1, 2):
        adapter.handle_event(adapter.event_from_status_callback(unanswered))
        assert len(rec.scheduled) == expected_retries
        delay, fn = rec.scheduled[-1]
        assert delay == 600
        fn()
    assert len(rec.requests) == 3
    adapter.handle_event(adapter.event_from_status_callback({**unanswered, "CallStatus": "busy"}))
    assert len(rec.scheduled) == 2
    (saved,) = app.store.recent_checkins()
    assert (saved.status, saved.attempts) == (CheckinStatus.NO_ANSWER, 3)
    assert app.store.recent_alerts()[0].code == "NO_ANSWER"


def test_retry_failure_records_no_answer(app, rec):
    def failing_opener(req):
        raise OSError("network down")

    adapter = TwilioAdapter(
        app, "AC1", "t", "+1555", "https://x.example.com", failing_opener, rec.scheduler
    )
    adapter._to_number = "+1555"
    adapter._round.attempts = 2
    adapter._retry("+1555")
    assert len(rec.scheduled) == 1


def test_unknown_event_kind(adapter):
    with pytest.raises(ValueError):
        adapter.handle_event(CallEvent("CA1", "exploded"))


def test_webhook_routes_require_valid_signature(adapter, app):
    server = serve(app.store, "127.0.0.1", 0, twilio=adapter)
    threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        params = {"CallSid": "CA5"}
        body = urllib.parse.urlencode(params).encode()
        bad = urllib.request.Request(
            base + "/twilio/voice", data=body, headers={"X-Twilio-Signature": "nope"}
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(bad, timeout=5)
        assert exc.value.code == 403

        sig = compute_signature("https://cv.example.com/twilio/voice", params, "token")
        good = urllib.request.Request(
            base + "/twilio/voice", data=body, headers={"X-Twilio-Signature": sig}
        )
        with urllib.request.urlopen(good, timeout=5) as resp:
            assert resp.headers["Content-Type"] == "text/xml"
            assert "Good morning, Ada." in resp.read().decode()

        status = {"CallSid": "CA5", "CallStatus": "completed"}
        sig = compute_signature("https://cv.example.com/twilio/status", status, "token")
        req = urllib.request.Request(
            base + "/twilio/status",
            data=urllib.parse.urlencode(status).encode(),
            headers={"X-Twilio-Signature": sig},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.read() == b"<Response/>"
        assert app.store.recent_checkins()[0].status is CheckinStatus.ABANDONED
    finally:
        server.shutdown()
        server.server_close()
