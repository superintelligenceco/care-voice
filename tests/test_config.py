from pathlib import Path

import pytest

from care_voice.config import ConfigError, load_config, parse_config
from care_voice.extractors import LLMExtractor, RuleBasedExtractor
from care_voice.models import Severity
from care_voice.notifiers import ConsoleNotifier, EmailNotifier, WebhookNotifier

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_defaults():
    cfg = parse_config(None)
    assert cfg.person_name == "friend"
    assert cfg.timezone == "UTC"
    assert isinstance(cfg.build_extractor(), RuleBasedExtractor)
    (console,) = cfg.build_notifiers()
    assert isinstance(console, ConsoleNotifier)
    assert load_config(None).script == "default"


def test_example_config_is_valid():
    cfg = load_config(EXAMPLES / "care-voice.yaml")
    assert cfg.person_name == "Margaret"
    assert cfg.resolve(cfg.database).startswith(str(EXAMPLES.resolve()))


def test_full_config(monkeypatch, tmp_path):
    monkeypatch.setenv("HOOK_SECRET", "abc")
    monkeypatch.setenv("SMTP_PASS", "pw")
    monkeypatch.setenv("LLM_KEY", "k")
    cfg = parse_config(
        {
            "person": {"name": "Ada", "timezone": "Europe/London", "phone": "+15555550100"},
            "database": "/tmp/x.db",
            "checkin": {"max_reprompts": 2, "call_attempts": 5},
            "extractor": {
                "kind": "llm",
                "base_url": "http://localhost:11434/v1",
                "model": "llama3.1",
                "api_key_env": "LLM_KEY",
            },
            "rules": {"pain_high_threshold": 5, "question_ids": {"mood": "feeling"}},
            "notifiers": [
                {"kind": "console", "min_severity": "info"},
                {"kind": "webhook", "url": "https://example.com/h", "secret_env": "HOOK_SECRET"},
                {
                    "kind": "email",
                    "host": "smtp.example.com",
                    "sender": "a@example.com",
                    "recipients": ["b@example.com"],
                    "username": "a@example.com",
                    "password_env": "SMTP_PASS",
                    "min_severity": "high",
                },
            ],
            "dashboard": {"host": "0.0.0.0", "port": 9000},
            "telephony": {"from_number": "+15555550199", "public_url": "https://x.example.com"},
        },
        base_dir=tmp_path,
    )
    assert cfg.tz.key == "Europe/London"
    assert cfg.checkin.max_reprompts == 2
    assert cfg.rules.pain_high_threshold == 5
    assert cfg.rules.ids.mood == "feeling"
    absolute = str(tmp_path / "abs" / "x.db")
    assert cfg.resolve(absolute) == absolute
    assert cfg.resolve("rel.db") == str(tmp_path / "rel.db")
    extractor = cfg.build_extractor()
    assert isinstance(extractor, LLMExtractor)
    assert extractor.api_key == "k"
    console, hook, mail = cfg.build_notifiers()
    assert console.min_severity is Severity.INFO
    assert isinstance(hook, WebhookNotifier) and hook.secret == "abc"
    assert hook.min_severity is Severity.MEDIUM
    assert isinstance(mail, EmailNotifier) and mail.password == "pw"
    assert mail.min_severity is Severity.HIGH
    assert cfg.dashboard_port == 9000
    assert cfg.telephony.from_number == "+15555550199"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ([], "mapping"),
        ({"person": {"timezone": "Mars/Olympus"}}, "timezone"),
        ({"extractor": {"kind": "magic"}}, "extractor kind"),
        ({"extractor": {"kind": "llm"}}, "base_url and model"),
        ({"notifiers": [{"kind": "pager"}]}, "notifier kind"),
        ({"notifiers": [{"kind": "webhook"}]}, "url"),
        ({"notifiers": [{"kind": "email", "host": "h"}]}, "sender"),
        ({"notifiers": [{"kind": "console", "min_severity": "urgent"}]}, "severity"),
        ({"notifiers": {"kind": "console"}}, "list"),
        ({"rules": {"bogus": 1}}, "unknown keys"),
        ({"checkin": "fast"}, "mapping"),
    ],
)
def test_invalid_config(data, message):
    with pytest.raises(ConfigError, match=message):
        parse_config(data)


def test_missing_config_file(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path / "missing.yaml")
