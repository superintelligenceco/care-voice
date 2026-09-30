import hashlib
import hmac
import io
import json
import smtplib
from typing import ClassVar

import pytest

from care_voice.models import Severity
from care_voice.notifiers import (
    ConsoleNotifier,
    EmailNotifier,
    WebhookNotifier,
    alert_payload,
    filter_alerts,
)
from care_voice.notifiers.webhook import SIGNATURE_HEADER, sign
from care_voice.risk import RiskEngine

from .conftest import GOOD_DAY
from .helpers import local_server


@pytest.fixture
def bad_day(run_session):
    replies = ["no", "no I forgot", "no", "my back hurts", "9", "back", "no", "friday", "2"]
    result = run_session(replies)
    result.id = 7
    return result, RiskEngine().evaluate(result)


def test_filter_alerts(bad_day):
    _, alerts = bad_day
    high = filter_alerts(alerts, Severity.HIGH)
    assert {a.code for a in high} == {"MISSED_MEDS", "PAIN_REPORTED"}
    assert len(filter_alerts(alerts, Severity.INFO)) == len(alerts)


def test_console_notifier(bad_day):
    result, alerts = bad_day
    out = io.StringIO()
    ConsoleNotifier(stream=out).send(alerts, result)
    text = out.getvalue()
    assert "[HIGH] MISSED_MEDS" in text
    assert "not a medical device" in text


def test_webhook_posts_signed_json(bad_day):
    result, alerts = bad_day
    with local_server(lambda *_: (200, {"ok": True})) as (url, requests):
        WebhookNotifier(f"{url}/hook", secret="s3cret").send(alerts, result)
    (req,) = requests
    assert req["path"] == "/hook"
    body = json.loads(req["body"])
    assert body == alert_payload(alerts, result)
    assert body["checkin_id"] == 7
    expected = "sha256=" + hmac.new(b"s3cret", req["body"], hashlib.sha256).hexdigest()
    assert req["headers"][SIGNATURE_HEADER] == expected == sign(req["body"], "s3cret")


def test_webhook_without_secret_and_errors(bad_day):
    result, alerts = bad_day
    with local_server(lambda *_: (200, {})) as (url, requests):
        WebhookNotifier(url).send(alerts, result)
    assert SIGNATURE_HEADER not in requests[0]["headers"]
    with local_server(lambda *_: (500, {})) as (url, _), pytest.raises(OSError):
        WebhookNotifier(url).send(alerts, result)
    with pytest.raises(ValueError):
        WebhookNotifier("ftp://example.com")


class FakeSMTP:
    instances: ClassVar[list["FakeSMTP"]] = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port
        self.calls = []
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, msg):
        self.sent.append(msg)


@pytest.mark.parametrize(
    ("security", "attr", "calls"),
    [
        ("starttls", "SMTP", ["starttls", ("login", "u", "p")]),
        ("ssl", "SMTP_SSL", [("login", "u", "p")]),
        ("none", "SMTP", [("login", "u", "p")]),
    ],
)
def test_email_notifier(monkeypatch, bad_day, security, attr, calls):
    result, alerts = bad_day
    FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, attr, FakeSMTP)
    notifier = EmailNotifier(
        "smtp.example.com", "cv@example.com", ["family@example.com"], 2525, "u", "p", security
    )
    notifier.send(alerts, result)
    (smtp,) = FakeSMTP.instances
    assert (smtp.host, smtp.port) == ("smtp.example.com", 2525)
    assert smtp.calls == calls
    (msg,) = smtp.sent
    assert msg["To"] == "family@example.com"
    assert msg["Subject"].startswith("[care-voice] HIGH: Ada, ")
    assert "more" in msg["Subject"]
    assert "MISSED_MEDS" in msg.get_content()


def test_email_validation():
    with pytest.raises(ValueError):
        EmailNotifier("h", "s", [], security="starttls")
    with pytest.raises(ValueError):
        EmailNotifier("h", "s", ["r"], security="plain")


def test_single_alert_subject(run_session):
    result = run_session(["yes", "no", *GOOD_DAY[2:]])
    alerts = RiskEngine().evaluate(result)
    msg = EmailNotifier("h", "s@example.com", ["r@example.com"]).build_message(alerts, result)
    assert msg["Subject"] == "[care-voice] HIGH: Ada, MISSED_MEDS"
