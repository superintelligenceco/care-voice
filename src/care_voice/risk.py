"""The risk-rules engine: turns a check-in (and recent history) into alerts.

Each rule is a small function. Rules read answers by question id, so custom
scripts that keep the ids listed in :class:`QuestionIds` get the same
alerts. See the "Alert rules reference" section of the README for the full
table.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from care_voice.extractors.rules import normalize
from care_voice.models import (
    FLAG_DISORIENTED,
    FLAG_EMERGENCY,
    FLAG_FALL,
    FLAG_PAIN,
    Alert,
    CheckinResult,
    CheckinStatus,
    Severity,
)


@dataclass(frozen=True)
class QuestionIds:
    """Question ids the rules look for in a script."""

    slept_well: str = "slept_well"
    took_meds: str = "took_meds"
    has_eaten: str = "has_eaten"
    in_pain: str = "in_pain"
    pain_level: str = "pain_level"
    had_fall: str = "had_fall"
    day_of_week: str = "day_of_week"
    mood: str = "mood"


@dataclass(frozen=True)
class RiskConfig:
    """Thresholds for the built-in rules."""

    pain_high_threshold: int = 7
    mood_drop_threshold: float = 1.5
    low_mood_threshold: int = 2
    baseline_min_checkins: int = 3
    baseline_window: int = 14
    unclear_answers_threshold: int = 2
    repetition_min_words: int = 4
    ids: QuestionIds = field(default_factory=QuestionIds)


Rule = Callable[[CheckinResult, Sequence[CheckinResult], RiskConfig], "Alert | None"]


def _alert(code: str, severity: Severity, message: str, *reasons: str) -> Alert:
    return Alert(code=code, severity=severity, message=message, reasons=tuple(reasons))


def rule_emergency(r: CheckinResult, _h: Sequence[CheckinResult], _c: RiskConfig) -> Alert | None:
    hits = [a for a in r.answers.values() if FLAG_EMERGENCY in a.flags]
    if not hits:
        return None
    return _alert(
        "EMERGENCY_WORDS",
        Severity.CRITICAL,
        f"{r.person} used words that may signal an emergency. Contact them now.",
        *(f'said: "{a.raw}"' for a in hits),
    )


def rule_no_answer(r: CheckinResult, h: Sequence[CheckinResult], _c: RiskConfig) -> Alert | None:
    if r.status is not CheckinStatus.NO_ANSWER:
        return None
    streak = 1
    for past in h:
        if past.status is not CheckinStatus.NO_ANSWER:
            break
        streak += 1
    reasons = [f"no answer after {r.attempts} attempt(s)"]
    severity = Severity.HIGH
    if streak > 1:
        severity = Severity.CRITICAL
        reasons.append(f"{streak} check-ins in a row without an answer")
    return _alert("NO_ANSWER", severity, f"{r.person} did not answer the check-in.", *reasons)


def rule_incomplete(r: CheckinResult, _h: Sequence[CheckinResult], _c: RiskConfig) -> Alert | None:
    if r.status is not CheckinStatus.ABANDONED:
        return None
    return _alert(
        "CHECKIN_INCOMPLETE",
        Severity.MEDIUM,
        f"{r.person}'s check-in ended before all questions were answered.",
        f"answered {len(r.answers)} question(s)",
    )


def rule_fall(r: CheckinResult, _h: Sequence[CheckinResult], c: RiskConfig) -> Alert | None:
    reasons = []
    if r.value(c.ids.had_fall) is True:
        reasons.append(f'answered yes to the fall question: "{r.answers[c.ids.had_fall].raw}"')
    for a in r.answers.values():
        if FLAG_FALL in a.flags and a.question_id != c.ids.had_fall:
            reasons.append(f'mentioned a fall: "{a.raw}"')
    if not reasons:
        return None
    return _alert("FALL_REPORTED", Severity.HIGH, f"{r.person} reported a fall.", *reasons)


def rule_meds(r: CheckinResult, _h: Sequence[CheckinResult], c: RiskConfig) -> Alert | None:
    answer = r.answers.get(c.ids.took_meds)
    if answer is None:
        return None
    if answer.understood and answer.value is False:
        return _alert(
            "MISSED_MEDS",
            Severity.HIGH,
            f"{r.person} has not taken their morning medication.",
            f'said: "{answer.raw}"',
        )
    if not answer.understood:
        return _alert(
            "MEDS_UNCONFIRMED",
            Severity.MEDIUM,
            f"{r.person} could not confirm their morning medication.",
            f'unclear reply: "{answer.raw}"',
        )
    return None


def rule_pain(r: CheckinResult, _h: Sequence[CheckinResult], c: RiskConfig) -> Alert | None:
    reasons = []
    if r.value(c.ids.in_pain) is True:
        reasons.append(f'reported pain: "{r.answers[c.ids.in_pain].raw}"')
    for a in r.answers.values():
        if FLAG_PAIN in a.flags and a.question_id not in (c.ids.in_pain, c.ids.pain_level):
            reasons.append(f'mentioned pain: "{a.raw}"')
    if not reasons:
        return None
    level = r.value(c.ids.pain_level)
    where = r.value("pain_where")
    if isinstance(level, int):
        reasons.append(f"pain level {level}/10")
    if isinstance(where, str):
        reasons.append(f"location: {where}")
    high = isinstance(level, int) and level >= c.pain_high_threshold
    return _alert(
        "PAIN_REPORTED",
        Severity.HIGH if high else Severity.MEDIUM,
        f"{r.person} reported {'severe ' if high else ''}pain.",
        *reasons,
    )


def rule_not_eaten(r: CheckinResult, _h: Sequence[CheckinResult], c: RiskConfig) -> Alert | None:
    if r.value(c.ids.has_eaten) is not False:
        return None
    return _alert("NOT_EATEN", Severity.LOW, f"{r.person} has not eaten yet today.")


def rule_poor_sleep(r: CheckinResult, _h: Sequence[CheckinResult], c: RiskConfig) -> Alert | None:
    if r.value(c.ids.slept_well) is not False:
        return None
    return _alert("POOR_SLEEP", Severity.LOW, f"{r.person} did not sleep well.")


def _repeated_replies(r: CheckinResult, min_words: int) -> list[str]:
    counts: dict[str, int] = {}
    for turn in r.transcript:
        if turn.speaker != "person":
            continue
        text = normalize(turn.text)
        if len(text.split()) >= min_words:
            counts[text] = counts.get(text, 0) + 1
    return [text for text, n in counts.items() if n > 1]


def rule_confusion(r: CheckinResult, _h: Sequence[CheckinResult], c: RiskConfig) -> Alert | None:
    if r.status is CheckinStatus.NO_ANSWER:
        return None
    signals: list[str] = []
    day = r.answers.get(c.ids.day_of_week)
    if day is not None:
        if day.understood and day.detail.get("correct") is False:
            today = r.started_at.strftime("%A")
            signals.append(f'gave the wrong day: "{day.raw}" (today is {today})')
        elif not day.understood:
            signals.append(f'could not name the day: "{day.raw}"')
    for a in r.answers.values():
        if FLAG_DISORIENTED in a.flags:
            signals.append(f'sounded disoriented: "{a.raw}"')
    for text in _repeated_replies(r, c.repetition_min_words):
        signals.append(f'repeated the same reply: "{text}"')
    if len(r.unclear) >= c.unclear_answers_threshold:
        signals.append(f"{len(r.unclear)} answers could not be understood: {', '.join(r.unclear)}")
    if not signals:
        return None
    severity = Severity.HIGH if len(signals) >= 2 else Severity.MEDIUM
    return _alert(
        "POSSIBLE_CONFUSION",
        severity,
        f"{r.person} showed {len(signals)} sign(s) of possible confusion.",
        *signals,
    )


def mood_baseline(history: Sequence[CheckinResult], c: RiskConfig) -> float | None:
    """Mean mood over recent completed check-ins, or ``None`` if there are too few."""
    moods = [
        v
        for past in history[: c.baseline_window]
        if isinstance(v := past.value(c.ids.mood), int) and not isinstance(v, bool)
    ]
    if len(moods) < c.baseline_min_checkins:
        return None
    return statistics.fmean(moods)


def rule_mood(r: CheckinResult, h: Sequence[CheckinResult], c: RiskConfig) -> Alert | None:
    mood = r.value(c.ids.mood)
    if not isinstance(mood, int) or isinstance(mood, bool):
        return None
    baseline = mood_baseline(h, c)
    if baseline is not None and baseline - mood >= c.mood_drop_threshold:
        return _alert(
            "MOOD_DROP",
            Severity.MEDIUM,
            f"{r.person}'s mood is well below their usual.",
            f"mood today {mood}/5, recent average {baseline:.1f}/5",
        )
    if mood <= c.low_mood_threshold:
        return _alert("LOW_MOOD", Severity.LOW, f"{r.person} reported low mood.", f"mood {mood}/5")
    return None


DEFAULT_RULES: tuple[Rule, ...] = (
    rule_emergency,
    rule_no_answer,
    rule_incomplete,
    rule_fall,
    rule_meds,
    rule_pain,
    rule_confusion,
    rule_mood,
    rule_not_eaten,
    rule_poor_sleep,
)


class RiskEngine:
    """Evaluates rules against a check-in and returns alerts, most severe first."""

    def __init__(self, config: RiskConfig | None = None, rules: Sequence[Rule] = DEFAULT_RULES):
        self.config = config or RiskConfig()
        self.rules = tuple(rules)

    def evaluate(self, result: CheckinResult, history: Sequence[CheckinResult] = ()) -> list[Alert]:
        """Return alerts for ``result``.

        ``history`` holds earlier check-ins for the same person, newest first.
        """
        alerts = [a for rule in self.rules if (a := rule(result, history, self.config))]
        alerts = [
            Alert(
                code=a.code,
                severity=a.severity,
                message=a.message,
                reasons=a.reasons,
                checkin_id=result.id,
                person=result.person,
                created_at=result.started_at,
            )
            for a in alerts
        ]
        return sorted(alerts, key=lambda a: a.severity, reverse=True)
