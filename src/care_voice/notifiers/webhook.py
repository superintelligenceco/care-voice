"""POST alerts as JSON to a URL, optionally signed with HMAC-SHA256."""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.request

from care_voice.models import Alert, CheckinResult, Severity
from care_voice.notifiers.base import alert_payload

SIGNATURE_HEADER = "X-Care-Voice-Signature"


def sign(body: bytes, secret: str) -> str:
    """Return the signature header value for ``body``."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class WebhookNotifier:
    """Sends one POST per check-in with all qualifying alerts.

    When ``secret`` is set, the request carries an
    ``X-Care-Voice-Signature: sha256=<hex>`` header computed over the raw
    body, so the receiver can verify where the request came from.
    """

    name = "webhook"

    def __init__(
        self,
        url: str,
        min_severity: Severity = Severity.MEDIUM,
        secret: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not url.startswith(("https://", "http://")):
            raise ValueError("webhook url must start with http:// or https://")
        self.url = url
        self.min_severity = min_severity
        self.secret = secret
        self.timeout = timeout

    def send(self, alerts: list[Alert], result: CheckinResult) -> None:
        body = json.dumps(alert_payload(alerts, result)).encode()
        headers = {"Content-Type": "application/json", "User-Agent": "care-voice"}
        if self.secret:
            headers[SIGNATURE_HEADER] = sign(body, self.secret)
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")  # noqa: S310
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
            resp.read()
