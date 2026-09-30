"""Glue: save a finished check-in, evaluate rules against history, notify."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from care_voice.config import Config
from care_voice.engine import CheckinSession
from care_voice.extractors import Extractor
from care_voice.models import Alert, CheckinResult
from care_voice.notifiers import Notifier, filter_alerts
from care_voice.risk import RiskEngine
from care_voice.script import CheckinScript, load_script
from care_voice.store import Store

log = logging.getLogger(__name__)


@dataclass
class CareVoice:
    """The assembled application: script, extractor, rules, store, and notifiers."""

    config: Config
    store: Store
    script: CheckinScript
    extractor: Extractor
    risk: RiskEngine
    notifiers: list[Notifier] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: Config, store: Store | None = None) -> CareVoice:
        return cls(
            config=config,
            store=store or Store(config.resolve(config.database)),
            script=load_script(config.resolve(config.script)),
            extractor=config.build_extractor(),
            risk=RiskEngine(config.rules),
            notifiers=config.build_notifiers(),
        )

    def now(self) -> datetime:
        return datetime.now(self.config.tz)

    def new_session(self, now: datetime | None = None) -> CheckinSession:
        return CheckinSession(
            script=self.script,
            extractor=self.extractor,
            person_name=self.config.person_name,
            now=now or self.now(),
            max_reprompts=self.config.checkin.max_reprompts,
            max_silences=self.config.checkin.max_silences,
        )

    def process(self, result: CheckinResult) -> list[Alert]:
        """Store ``result``, evaluate the rules, store and deliver the alerts."""
        history = self.store.history(result.person, before=result.started_at)
        self.store.save_checkin(result)
        alerts = self.risk.evaluate(result, history)
        self.store.save_alerts(alerts)
        for notifier in self.notifiers:
            selected = filter_alerts(alerts, notifier.min_severity)
            if not selected:
                continue
            try:
                notifier.send(selected, result)
            except Exception:
                log.exception("notifier %s failed", notifier.name)
        return alerts
