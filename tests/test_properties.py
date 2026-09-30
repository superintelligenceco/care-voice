"""Property-based tests for the pure parsing and alerting logic."""

from __future__ import annotations

import string
from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from care_voice.engine import CheckinSession
from care_voice.extractors import ExtractionContext, RuleBasedExtractor
from care_voice.extractors.rules import (
    WEEKDAYS,
    detect_flags,
    normalize,
    parse_scale,
    parse_weekday,
    parse_yes_no,
)
from care_voice.models import (
    FLAG_DISORIENTED,
    FLAG_EMERGENCY,
    FLAG_FALL,
    FLAG_PAIN,
    Severity,
)
from care_voice.risk import RiskEngine
from care_voice.script import load_script

from .conftest import NOW

KNOWN_FLAGS = {FLAG_EMERGENCY, FLAG_FALL, FLAG_PAIN, FLAG_DISORIENTED}
# Filler text that cannot contain a digit, number word, or weekday by accident.
FILLER = st.text(alphabet="bcdfghjklmpqrstvwxz ", max_size=30)
ANY_TEXT = st.text(max_size=80)
SCRIPT = load_script()


@given(ANY_TEXT)
def test_normalize_is_idempotent_and_restricted(text: str) -> None:
    once = normalize(text)
    assert normalize(once) == once
    assert set(once) <= set(string.ascii_lowercase + string.digits + "' -")
    assert once == once.strip()
    assert "  " not in once


@given(ANY_TEXT, st.integers(0, 5), st.integers(0, 10))
def test_parse_scale_never_returns_out_of_range(text: str, lo: int, span: int) -> None:
    hi = lo + span
    value, how = parse_scale(text, lo, hi)
    if value is None:
        assert how in {"out_of_range", "no_number"}
    else:
        assert lo <= value <= hi
        assert how in {"number", "word"}


@given(st.integers(1, 10), FILLER, FILLER)
def test_parse_scale_reads_a_number_anywhere(n: int, before: str, after: str) -> None:
    assert parse_scale(f"{before} {n} {after}", 0, 10) == (n, "number")


@given(st.sampled_from(WEEKDAYS), FILLER, FILLER)
def test_parse_weekday_finds_the_single_day(day: str, before: str, after: str) -> None:
    assert parse_weekday(f"{before} {day.capitalize()} {after}") == day


@given(st.lists(st.sampled_from(WEEKDAYS), min_size=2, max_size=4, unique=True))
def test_parse_weekday_refuses_to_guess_between_days(days: list[str]) -> None:
    assert parse_weekday(" or ".join(days)) is None


@given(st.sampled_from(["yes", "Yeah", "yep", "Sure"]), FILLER, st.booleans())
def test_leading_yes_is_always_yes(lead: str, rest: str, problem: bool) -> None:
    assert parse_yes_no(f"{lead}, {rest}", problem_question=problem) is True


@given(st.sampled_from(["no", "Nope", "nah", "Not yet"]), FILLER, st.booleans())
def test_leading_no_is_always_no(lead: str, rest: str, problem: bool) -> None:
    assert parse_yes_no(f"{lead}, {rest}", problem_question=problem) is False


@given(ANY_TEXT)
def test_detect_flags_only_returns_known_flags(text: str) -> None:
    assert detect_flags(text) <= KNOWN_FLAGS


@given(
    FILLER,
    st.sampled_from(["help me", "I can't breathe", "chest pain", "I'm on the floor"]),
    FILLER,
)
def test_emergency_phrase_is_flagged_in_any_context(before: str, phrase: str, after: str) -> None:
    assert FLAG_EMERGENCY in detect_flags(f"{before} {phrase} {after}")


@given(st.sampled_from(SCRIPT.questions), ANY_TEXT)
def test_extractor_marks_understood_iff_value_present(question, text: str) -> None:
    ctx = ExtractionContext(today=date(2026, 9, 30), person_name="Ada")
    answer = RuleBasedExtractor().extract(question, text, ctx)
    assert answer.understood is (answer.value is not None)
    assert answer.question_id == question.id
    assert answer.flags == detect_flags(text)


@settings(max_examples=60)
@given(st.lists(st.one_of(st.none(), ANY_TEXT), max_size=25))
def test_any_conversation_ends_and_alerts_are_explained(replies: list[str | None]) -> None:
    session = CheckinSession(SCRIPT, RuleBasedExtractor(), "Ada", NOW)
    session.start()
    for reply in replies:
        if session.done:
            break
        session.respond(reply)
    if not session.done:
        session.hang_up()
    result = session.result()
    alerts = RiskEngine().evaluate(result)
    severities = [a.severity for a in alerts]
    assert severities == sorted(severities, reverse=True)
    for alert in alerts:
        assert alert.message
        assert alert.person == "Ada"


@settings(max_examples=40)
@given(st.integers(0, 6), FILLER)
def test_emergency_words_always_raise_a_critical_alert(position: int, filler: str) -> None:
    replies = ["yes", "yes", "yes", "no", "no", "wednesday", "4"]
    replies.insert(position, f"{filler} help me {filler}")
    session = CheckinSession(SCRIPT, RuleBasedExtractor(), "Ada", NOW)
    session.start()
    for reply in replies:
        if session.done:
            break
        session.respond(reply)
    if not session.done:
        session.hang_up()
    alerts = RiskEngine().evaluate(session.result())
    assert alerts
    assert alerts[0].code == "EMERGENCY_WORDS"
    assert alerts[0].severity is Severity.CRITICAL
