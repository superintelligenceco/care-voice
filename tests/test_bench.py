"""Benchmarks for the hot path: reply extraction, a full check-in, and the rules.

Normal test runs execute each benchmark once without timing. `make bench` times
them and compares the medians with benchmarks/baseline.json.
"""

from __future__ import annotations

from typing import Any

from care_voice.engine import CheckinSession
from care_voice.extractors import ExtractionContext, RuleBasedExtractor
from care_voice.extractors.rules import detect_flags
from care_voice.models import CheckinResult
from care_voice.risk import RiskEngine
from care_voice.script import load_script

from .conftest import NOW, WEDNESDAY

SCRIPT = load_script()
CONCERNING_DAY = [
    "Not really, I kept waking up",
    "No, I forgot them",
    "Not yet",
    "Yes, my hip hurts",
    "About an eight",
    "My right hip",
    "I slipped in the bathroom last night",
    "Is it Sunday?",
    "Pretty low today",
]


def _checkin(replies: list[str]) -> CheckinResult:
    session = CheckinSession(SCRIPT, RuleBasedExtractor(), "Margaret", NOW)
    session.start()
    for reply in replies:
        session.respond(reply)
    return session.result()


def test_bench_detect_flags(benchmark: Any) -> None:
    text = "I slipped in the bathroom last night and my hip hurts, but I can get up"
    assert benchmark(detect_flags, text) == frozenset({"fall", "pain"})


def test_bench_extract_answer(benchmark: Any) -> None:
    extractor = RuleBasedExtractor()
    ctx = ExtractionContext(today=WEDNESDAY, person_name="Margaret")
    question = next(q for q in SCRIPT.questions if q.id == "mood")
    answer = benchmark(extractor.extract, question, "Pretty low today", ctx)
    assert answer.value == 2


def test_bench_full_checkin(benchmark: Any) -> None:
    result = benchmark(_checkin, CONCERNING_DAY)
    assert result.value("had_fall") is True


def test_bench_risk_engine(benchmark: Any) -> None:
    result = _checkin(CONCERNING_DAY)
    history = [_checkin(CONCERNING_DAY) for _ in range(14)]
    alerts = benchmark(RiskEngine().evaluate, result, history)
    assert alerts[0].code == "FALL_REPORTED"
