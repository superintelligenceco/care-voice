"""A small caregiver dashboard and webhook server, built on the standard library.

Routes:

- ``GET /`` shows recent alerts and check-ins as an HTML page.
- ``GET /api/checkins`` and ``GET /api/alerts`` return JSON.
- ``GET /healthz`` returns ``ok``.
- ``POST /twilio/voice`` and ``POST /twilio/status`` are mounted only when a
  Twilio adapter is configured (EXPERIMENTAL).

The server binds to ``127.0.0.1`` by default. Set the
``CARE_VOICE_DASHBOARD_PASSWORD`` environment variable to require HTTP basic
authentication (any username) for the dashboard and API routes.
"""

from __future__ import annotations

import base64
import hmac
import html
import json
import logging
import os
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

from care_voice.models import Alert, CheckinResult
from care_voice.store import Store

if TYPE_CHECKING:
    from care_voice.telephony.twilio import TwilioAdapter

log = logging.getLogger(__name__)

PASSWORD_ENV = "CARE_VOICE_DASHBOARD_PASSWORD"  # noqa: S105 - env var name

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>care-voice dashboard</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
body {{ max-width: 960px; margin: 2rem auto; padding: 0 1rem; line-height: 1.4; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
th, td {{ text-align: left; padding: .4rem .5rem; border-bottom: 1px solid #8884;
  vertical-align: top; }}
.sev {{ font-weight: 600; padding: .1rem .4rem; border-radius: .3rem; font-size: .85em; }}
.critical {{ background: #b00020; color: #fff; }} .high {{ background: #d9480f; color: #fff; }}
.medium {{ background: #f0ad4e; color: #000; }} .low, .info {{ background: #8883; }}
ul {{ margin: .2rem 0; padding-left: 1.2rem; }} small {{ color: #888; }}
details summary {{ cursor: pointer; }}
</style></head><body>
<h1>care-voice</h1>
<p><small>Not a medical device. Not for emergencies. In an emergency, call your local
emergency number.</small></p>
<h2>Recent alerts</h2>
{alerts}
<h2>Recent check-ins</h2>
{checkins}
</body></html>
"""


def _e(value: Any) -> str:
    return html.escape(str(value))


def render_alerts(alerts: list[Alert]) -> str:
    if not alerts:
        return "<p>No alerts yet.</p>"
    rows = []
    for a in alerts:
        reasons = "".join(f"<li>{_e(r)}</li>" for r in a.reasons)
        when = f"{a.created_at:%Y-%m-%d %H:%M}" if a.created_at else ""
        rows.append(
            f"<tr><td>{_e(when)}</td><td>{_e(a.person)}</td>"
            f'<td><span class="sev {_e(a.severity.label)}">{_e(a.severity.label)}</span></td>'
            f"<td><strong>{_e(a.code)}</strong><br>{_e(a.message)}<ul>{reasons}</ul></td></tr>"
        )
    return (
        "<table><thead><tr><th>When</th><th>Person</th><th>Severity</th><th>Alert</th></tr>"
        f"</thead><tbody>{''.join(rows)}</tbody></table>"
    )


def render_checkins(checkins: list[CheckinResult]) -> str:
    if not checkins:
        return "<p>No check-ins yet. Run <code>care-voice simulate</code> to try one.</p>"
    rows = []
    for c in checkins:
        answers = "".join(
            f"<li>{_e(qid)}: {_e(a.value if a.understood else '(unclear)')}</li>"
            for qid, a in c.answers.items()
        )
        transcript = "<br>".join(f"<b>{_e(t.speaker)}</b>: {_e(t.text)}" for t in c.transcript)
        rows.append(
            f"<tr><td>{_e(f'{c.started_at:%Y-%m-%d %H:%M}')}</td><td>{_e(c.person)}</td>"
            f"<td>{_e(c.status.value)}</td><td><ul>{answers}</ul>"
            f"<details><summary>Transcript</summary>{transcript}</details></td></tr>"
        )
    return (
        "<table><thead><tr><th>When</th><th>Person</th><th>Status</th><th>Answers</th></tr>"
        f"</thead><tbody>{''.join(rows)}</tbody></table>"
    )


def checkin_json(c: CheckinResult) -> dict[str, Any]:
    return {
        "id": c.id,
        "person": c.person,
        "started_at": c.started_at.isoformat(),
        "status": c.status.value,
        "attempts": c.attempts,
        "answers": {
            k: {"value": a.value, "understood": a.understood, "flags": sorted(a.flags)}
            for k, a in c.answers.items()
        },
    }


def alert_json(a: Alert) -> dict[str, Any]:
    return {
        "checkin_id": a.checkin_id,
        "person": a.person,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "severity": a.severity.label,
        "code": a.code,
        "message": a.message,
        "reasons": list(a.reasons),
    }


def make_handler(
    store: Store, twilio: TwilioAdapter | None = None, password: str | None = None
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler class bound to ``store`` (and optionally Twilio)."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "care-voice"

        def log_message(self, format: str, *args: Any) -> None:
            log.info("%s %s", self.address_string(), format % args)

        def _send(self, status: int, body: str | bytes, content_type: str) -> None:
            data = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            if not password:
                return True
            header = self.headers.get("Authorization", "")
            if not header.startswith("Basic "):
                return False
            try:
                decoded = base64.b64decode(header[6:]).decode()
            except (ValueError, UnicodeDecodeError):
                return False
            _, _, supplied = decoded.partition(":")
            return hmac.compare_digest(supplied, password)

        def do_GET(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/healthz":
                self._send(HTTPStatus.OK, "ok", "text/plain")
                return
            if not self._authorized():
                self.send_response(HTTPStatus.UNAUTHORIZED)
                self.send_header("WWW-Authenticate", 'Basic realm="care-voice"')
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path == "/":
                page = PAGE.format(
                    alerts=render_alerts(store.recent_alerts(50)),
                    checkins=render_checkins(store.recent_checkins(30)),
                )
                self._send(HTTPStatus.OK, page, "text/html; charset=utf-8")
            elif path == "/api/checkins":
                body = json.dumps([checkin_json(c) for c in store.recent_checkins(100)])
                self._send(HTTPStatus.OK, body, "application/json")
            elif path == "/api/alerts":
                body = json.dumps([alert_json(a) for a in store.recent_alerts(200)])
                self._send(HTTPStatus.OK, body, "application/json")
            else:
                self._send(HTTPStatus.NOT_FOUND, "not found", "text/plain")

        def do_POST(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if twilio is None or path not in ("/twilio/voice", "/twilio/status"):
                self._send(HTTPStatus.NOT_FOUND, "not found", "text/plain")
                return
            length = min(int(self.headers.get("Content-Length") or 0), 64 * 1024)
            raw = self.rfile.read(length).decode()
            params = dict(urllib.parse.parse_qsl(raw, keep_blank_values=True))
            from care_voice.telephony.twilio import validate_signature

            url = f"{twilio.public_url}{self.path}"
            signature = self.headers.get("X-Twilio-Signature", "")
            if not validate_signature(url, params, signature, twilio.auth_token):
                self._send(HTTPStatus.FORBIDDEN, "invalid signature", "text/plain")
                return
            if path == "/twilio/voice":
                event = twilio.event_from_voice_webhook(params)
            else:
                event = twilio.event_from_status_callback(params)
            body = twilio.handle_event(event)
            self._send(HTTPStatus.OK, body or "<Response/>", "text/xml")

    return Handler


def serve(
    store: Store,
    host: str = "127.0.0.1",
    port: int = 8080,
    twilio: TwilioAdapter | None = None,
) -> ThreadingHTTPServer:
    """Create (but do not start) the HTTP server."""
    handler = make_handler(store, twilio, os.environ.get(PASSWORD_ENV) or None)
    return ThreadingHTTPServer((host, port), handler)
