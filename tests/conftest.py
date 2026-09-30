from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from hypothesis import HealthCheck, settings

from care_voice.engine import CheckinSession
from care_voice.extractors import ExtractionContext, RuleBasedExtractor
from care_voice.models import CheckinResult
from care_voice.script import CheckinScript, load_script

# HYPOTHESIS_PROFILE=nightly runs many more examples; the nightly workflow sets it.
settings.register_profile("nightly", max_examples=2000, deadline=None)
settings.register_profile("default", deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

# 30 September 2026 is a Wednesday.
WEDNESDAY = date(2026, 9, 30)
NOW = datetime(2026, 9, 30, 9, 0, tzinfo=ZoneInfo("UTC"))

GOOD_DAY = [
    "Yes, I slept well",
    "Yes, I took them",
    "I had porridge",
    "No, I feel fine",
    "No",
    "It's Wednesday",
    "4",
]


@pytest.fixture
def script() -> CheckinScript:
    return load_script()


@pytest.fixture
def extractor() -> RuleBasedExtractor:
    return RuleBasedExtractor()


@pytest.fixture
def ctx() -> ExtractionContext:
    return ExtractionContext(today=WEDNESDAY, person_name="Ada")


@pytest.fixture
def run_session(
    script: CheckinScript, extractor: RuleBasedExtractor
) -> Callable[..., CheckinResult]:
    def run(replies: list[str], now: datetime = NOW, **kwargs: int) -> CheckinResult:
        session = CheckinSession(script, extractor, "Ada", now, **kwargs)
        session.start()
        for reply in replies:
            if session.done:
                break
            session.respond(reply)
        if not session.done:
            session.hang_up()
        return session.result()

    return run
