"""Load the YAML configuration file.

Secrets are never stored in the config file itself. Fields that end in
``_env`` name the environment variable that holds the secret.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from care_voice.extractors import Extractor, LLMExtractor, RuleBasedExtractor
from care_voice.models import Severity
from care_voice.notifiers import ConsoleNotifier, EmailNotifier, Notifier, WebhookNotifier
from care_voice.risk import QuestionIds, RiskConfig


class ConfigError(ValueError):
    """Raised when the configuration file is invalid."""


@dataclass
class CheckinSettings:
    max_reprompts: int = 1
    max_silences: int = 3
    call_attempts: int = 3
    retry_delay_minutes: float = 10.0


@dataclass
class TelephonySettings:
    provider: str = "twilio"
    from_number: str = ""
    public_url: str = ""
    account_sid_env: str = "TWILIO_ACCOUNT_SID"
    auth_token_env: str = "TWILIO_AUTH_TOKEN"  # noqa: S105 - env var name, not a secret


@dataclass
class Config:
    person_name: str = "friend"
    person_phone: str = ""
    timezone: str = "UTC"
    script: str = "default"
    database: str = "care-voice.db"
    checkin: CheckinSettings = field(default_factory=CheckinSettings)
    extractor: dict[str, Any] = field(default_factory=lambda: {"kind": "rules"})
    rules: RiskConfig = field(default_factory=RiskConfig)
    notifiers: list[dict[str, Any]] = field(default_factory=lambda: [{"kind": "console"}])
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8080
    telephony: TelephonySettings = field(default_factory=TelephonySettings)
    base_dir: Path = field(default_factory=Path.cwd)

    @property
    def tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ConfigError(f"unknown timezone {self.timezone!r}") from exc

    def resolve(self, path: str) -> str:
        """Resolve ``path`` relative to the config file's directory."""
        if path in (":memory:", "default") or Path(path).is_absolute():
            return path
        return str(self.base_dir / path)

    def build_extractor(self) -> Extractor:
        kind = self.extractor.get("kind", "rules")
        if kind == "rules":
            return RuleBasedExtractor()
        if kind == "llm":
            key_env = self.extractor.get("api_key_env", "CARE_VOICE_LLM_API_KEY")
            base_url = self.extractor.get("base_url")
            model = self.extractor.get("model")
            if not base_url or not model:
                raise ConfigError("extractor kind 'llm' needs base_url and model")
            return LLMExtractor(
                base_url=str(base_url),
                model=str(model),
                api_key=os.environ.get(key_env),
                timeout=float(self.extractor.get("timeout", 15)),
            )
        raise ConfigError(f"unknown extractor kind {kind!r}; expected 'rules' or 'llm'")

    def build_notifiers(self) -> list[Notifier]:
        return [_build_notifier(n) for n in self.notifiers]


def _env(spec: dict[str, Any], key: str) -> str | None:
    name = spec.get(f"{key}_env")
    return os.environ.get(str(name)) if name else None


def _build_notifier(spec: dict[str, Any]) -> Notifier:
    kind = spec.get("kind")
    try:
        sev = Severity.parse(spec.get("min_severity", "low" if kind == "console" else "medium"))
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    if kind == "console":
        return ConsoleNotifier(min_severity=sev)
    if kind == "webhook":
        if not spec.get("url"):
            raise ConfigError("webhook notifier needs a url")
        return WebhookNotifier(url=spec["url"], min_severity=sev, secret=_env(spec, "secret"))
    if kind == "email":
        for key in ("host", "sender", "recipients"):
            if not spec.get(key):
                raise ConfigError(f"email notifier needs {key!r}")
        return EmailNotifier(
            host=spec["host"],
            port=int(spec.get("port", 587)),
            sender=spec["sender"],
            recipients=list(spec["recipients"]),
            username=spec.get("username") or _env(spec, "username"),
            password=_env(spec, "password"),
            security=spec.get("security", "starttls"),
            min_severity=sev,
        )
    raise ConfigError(f"unknown notifier kind {kind!r}; expected console, webhook, or email")


def _dataclass_from(cls: Any, data: Any, where: str) -> Any:
    if data is None:
        return cls()
    if not isinstance(data, dict):
        raise ConfigError(f"{where} must be a mapping")
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"{where}: unknown keys {sorted(unknown)}")
    return cls(**data)


def parse_config(data: Any, base_dir: Path | None = None) -> Config:
    """Build a :class:`Config` from already-loaded YAML data."""
    data = {} if data is None else data
    if not isinstance(data, dict):
        raise ConfigError("config must be a mapping")
    person = data.get("person") or {}
    rules_raw = dict(data.get("rules") or {})
    ids = _dataclass_from(QuestionIds, rules_raw.pop("question_ids", None), "rules.question_ids")
    rules = _dataclass_from(RiskConfig, rules_raw, "rules")
    dashboard = data.get("dashboard") or {}
    notifiers = data.get("notifiers", [{"kind": "console"}]) or []
    if not isinstance(notifiers, list):
        raise ConfigError("notifiers must be a list")
    cfg = Config(
        person_name=str(person.get("name", "friend")),
        person_phone=str(person.get("phone", "")),
        timezone=str(person.get("timezone", "UTC")),
        script=str(data.get("script", "default")),
        database=str(data.get("database", "care-voice.db")),
        checkin=_dataclass_from(CheckinSettings, data.get("checkin"), "checkin"),
        extractor=dict(data.get("extractor") or {"kind": "rules"}),
        rules=RiskConfig(**{**rules.__dict__, "ids": ids}),
        notifiers=notifiers,
        dashboard_host=str(dashboard.get("host", "127.0.0.1")),
        dashboard_port=int(dashboard.get("port", 8080)),
        telephony=_dataclass_from(TelephonySettings, data.get("telephony"), "telephony"),
        base_dir=base_dir or Path.cwd(),
    )
    cfg.tz  # noqa: B018 - validate the timezone early
    cfg.build_extractor()
    cfg.build_notifiers()
    return cfg


def load_config(path: str | Path | None) -> Config:
    """Load ``path``, or return the defaults when ``path`` is ``None``."""
    if path is None:
        return parse_config({})
    p = Path(path)
    try:
        data = yaml.safe_load(p.read_text("utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read config {p}: {exc}") from exc
    return parse_config(data, base_dir=p.resolve().parent)
