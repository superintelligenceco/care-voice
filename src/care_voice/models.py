"""Core data types shared across the engine, extractors, rules, and storage."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class Severity(enum.IntEnum):
    """Alert severity, ordered so that comparisons work (``HIGH > LOW``)."""

    INFO = 10
    LOW = 20
    MEDIUM = 30
    HIGH = 40
    CRITICAL = 50

    @classmethod
    def parse(cls, value: str | Severity) -> Severity:
        if isinstance(value, Severity):
            return value
        try:
            return cls[value.strip().upper()]
        except KeyError as exc:
            names = ", ".join(s.name.lower() for s in cls)
            raise ValueError(f"unknown severity {value!r}; expected one of: {names}") from exc

    @property
    def label(self) -> str:
        return self.name.lower()


class CheckinStatus(enum.StrEnum):
    """Final state of a check-in."""

    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    ABANDONED = "abandoned"


# Flags an extractor can attach to any utterance, independent of the question.
FLAG_EMERGENCY = "emergency"
FLAG_FALL = "fall"
FLAG_PAIN = "pain"
FLAG_DISORIENTED = "disoriented"


@dataclass(frozen=True)
class Answer:
    """A structured answer extracted from one utterance.

    ``value`` holds the normalized answer: ``bool`` for yes/no questions,
    ``int`` for scale questions, a weekday name for day-of-week questions,
    and the raw text for free-text questions. ``understood`` is ``False``
    when the extractor could not map the utterance to a value.
    """

    question_id: str
    raw: str
    value: Any = None
    understood: bool = True
    flags: frozenset[str] = frozenset()
    source: str = "rules"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Turn:
    """One line of a transcript."""

    speaker: str  # "agent" or "person"
    text: str
    question_id: str | None = None


@dataclass
class CheckinResult:
    """Everything the risk engine and the store need about one check-in."""

    person: str
    started_at: datetime
    status: CheckinStatus
    answers: dict[str, Answer] = field(default_factory=dict)
    transcript: list[Turn] = field(default_factory=list)
    attempts: int = 1
    unclear: list[str] = field(default_factory=list)
    id: int | None = None

    def value(self, question_id: str) -> Any:
        answer = self.answers.get(question_id)
        return answer.value if answer is not None and answer.understood else None

    @property
    def all_flags(self) -> set[str]:
        flags: set[str] = set()
        for answer in self.answers.values():
            flags |= answer.flags
        return flags


@dataclass(frozen=True)
class Alert:
    """A caregiver-facing alert produced by the risk engine."""

    code: str
    severity: Severity
    message: str
    reasons: tuple[str, ...] = ()
    checkin_id: int | None = None
    person: str = ""
    created_at: datetime | None = None
