"""Send alerts by email over SMTP."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from care_voice.models import Alert, CheckinResult, Severity
from care_voice.notifiers.base import format_text


class EmailNotifier:
    """Sends one plain-text email per check-in with all qualifying alerts.

    ``security`` is ``"starttls"`` (default, usually port 587), ``"ssl"``
    (usually port 465), or ``"none"`` for a local relay.
    """

    name = "email"

    def __init__(
        self,
        host: str,
        sender: str,
        recipients: list[str],
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        security: str = "starttls",
        min_severity: Severity = Severity.MEDIUM,
        timeout: float = 20.0,
    ) -> None:
        if security not in ("starttls", "ssl", "none"):
            raise ValueError("security must be 'starttls', 'ssl', or 'none'")
        if not recipients:
            raise ValueError("email notifier needs at least one recipient")
        self.host = host
        self.port = port
        self.sender = sender
        self.recipients = recipients
        self.username = username
        self.password = password
        self.security = security
        self.min_severity = min_severity
        self.timeout = timeout

    def build_message(self, alerts: list[Alert], result: CheckinResult) -> EmailMessage:
        top = max(alerts, key=lambda a: a.severity)
        msg = EmailMessage()
        msg["Subject"] = (
            f"[care-voice] {top.severity.label.upper()}: {result.person}, {top.code}"
            + (f" and {len(alerts) - 1} more" if len(alerts) > 1 else "")
        )
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg.set_content(format_text(alerts, result))
        return msg

    def send(self, alerts: list[Alert], result: CheckinResult) -> None:
        msg = self.build_message(alerts, result)
        context = ssl.create_default_context()
        smtp: smtplib.SMTP
        if self.security == "ssl":
            smtp = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
        else:
            smtp = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        with smtp:
            if self.security == "starttls":
                smtp.starttls(context=context)
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(msg)
