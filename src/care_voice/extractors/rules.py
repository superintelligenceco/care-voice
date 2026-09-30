"""A deterministic, offline extractor based on keyword and pattern rules.

It is intentionally conservative: when a reply is ambiguous it reports
``understood=False`` instead of guessing, and the engine re-asks. It also
runs as a safety net underneath the LLM extractor, so its safety flags
(emergency, fall, pain, disorientation) are always evaluated.
"""

from __future__ import annotations

import re
from typing import Any

from care_voice.extractors.base import ExtractionContext
from care_voice.models import (
    FLAG_DISORIENTED,
    FLAG_EMERGENCY,
    FLAG_FALL,
    FLAG_PAIN,
    Answer,
)
from care_voice.script import Question

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

NUMBER_WORDS = {
    "zero": 0,
    "none": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

# Words that describe how someone feels, mapped onto a 1-5 scale. Only used
# for 1-5 scale questions when the person answers with a word, not a number.
FEELING_WORDS = {
    "terrible": 1,
    "awful": 1,
    "miserable": 1,
    "horrible": 1,
    "bad": 2,
    "low": 2,
    "sad": 2,
    "down": 2,
    "poorly": 2,
    "lonely": 2,
    "okay": 3,
    "ok": 3,
    "alright": 3,
    "so-so": 3,
    "fine": 4,
    "good": 4,
    "well": 4,
    "great": 5,
    "wonderful": 5,
    "excellent": 5,
    "fantastic": 5,
}

YES_LEAD = ("yes", "yeah", "yep", "yup", "yea", "sure", "absolutely", "definitely", "certainly")
YES_LEAD_PHRASES = re.compile(r"^(of course|uh huh|mhm|i did|i have|i am|that's right)\b")
NO_LEAD = ("no", "nope", "nah", "not", "never")
NEGATIVE_MARKERS = re.compile(
    r"\b(not|never|nothing|forgot|forgotten|hardly|barely|badly|poorly|terribly|awful|"
    r"terrible|\w+n't|cannot)\b"
)
POSITIVE_MARKERS = re.compile(
    r"\b(did|have|has|had|took|taken|ate|eaten|slept|done|well|good|great|fine|"
    r"lovely|wonderful|bit|little|some|hurts?|hurting|aches?|aching|sore|pain|fell)\b"
)
# Replies that mean "all good" and therefore "no" to a problem question.
WELLNESS_MARKERS = re.compile(r"\b(fine|okay|ok|good|great|well|alright|all right)\b")

EMERGENCY_PATTERNS = re.compile(
    r"\b(help me|call (an )?ambulance|can'?t breathe|cannot breathe|chest pains?|"
    r"can'?t get up|cannot get up|on the floor|heart attack|stroke|bleeding a lot|"
    r"passed out|blacked out|emergency)\b"
)
FALL_WORDS = re.compile(r"\b(fell|fallen|fall|falling|tripped|stumbled|slipped|collapsed)\b")
PAIN_WORDS = re.compile(r"\b(pains?|painful|hurts?|hurting|aches?|aching|sore|agony)\b")
DISORIENTED_PATTERNS = re.compile(
    r"\b(where am i|who are you|what day is it|what year is it|i'?m (so )?confused|"
    r"i don'?t know (what|which) day|i can'?t remember (what|which) day|"
    r"i don'?t know where i am)\b"
)
NEGATION_WORDS = re.compile(r"^(no|not|never|without|\w+n't|cannot)$")


def normalize(text: str) -> str:
    """Lowercase, unify apostrophes, and collapse whitespace and punctuation."""
    text = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    text = re.sub(r"[^a-z0-9' -]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _negated_before(words: list[str], index: int, window: int = 3) -> bool:
    return any(NEGATION_WORDS.match(w) for w in words[max(0, index - window) : index])


def _clauses(text: str) -> list[str]:
    parts = re.split(r"[,.;:!?]|\bbut\b|\band\b", text.lower().replace("\u2019", "'"))
    return [normalize(p) for p in parts if p.strip()]


def _find_unnegated(pattern: re.Pattern[str], text: str) -> bool:
    """True if ``pattern`` matches a word that no nearby word in its clause negates."""
    for clause in _clauses(text):
        words = clause.split()
        for i, word in enumerate(words):
            if pattern.fullmatch(word) and not _negated_before(words, i):
                return True
    return False


def detect_flags(utterance: str) -> frozenset[str]:
    """Return safety flags present in ``utterance``, independent of the question."""
    text = normalize(utterance)
    flags: set[str] = set()
    if EMERGENCY_PATTERNS.search(text):
        flags.add(FLAG_EMERGENCY)
    if _find_unnegated(FALL_WORDS, utterance):
        flags.add(FLAG_FALL)
    if _find_unnegated(PAIN_WORDS, utterance):
        flags.add(FLAG_PAIN)
    if DISORIENTED_PATTERNS.search(text):
        flags.add(FLAG_DISORIENTED)
    return frozenset(flags)


def parse_yes_no(text: str, problem_question: bool = False) -> bool | None:
    """Return ``True``/``False`` for a yes/no reply, or ``None`` if unclear."""
    raw, text = text, normalize(text)
    if not text:
        return None
    first = text.split()[0]
    if first in YES_LEAD or YES_LEAD_PHRASES.match(text):
        return True
    if first in NO_LEAD or text.startswith(("not yet", "not really")):
        return False
    if problem_question and (_find_unnegated(PAIN_WORDS, raw) or _find_unnegated(FALL_WORDS, raw)):
        return True
    if NEGATIVE_MARKERS.search(text):
        return False
    if problem_question and WELLNESS_MARKERS.search(text):
        return False
    if POSITIVE_MARKERS.search(text):
        return True
    return None


def parse_scale(text: str, lo: int, hi: int) -> tuple[int | None, str]:
    """Return ``(value, how)`` for a scale reply. ``value`` is ``None`` if unclear."""
    text = normalize(text)
    for token in text.split():
        number: int | None = None
        if token.isdigit():
            number = int(token)
        elif token in NUMBER_WORDS:
            number = NUMBER_WORDS[token]
        if number is not None:
            return (number, "number") if lo <= number <= hi else (None, "out_of_range")
    if (lo, hi) == (1, 5):
        if "not bad" in text or "not too bad" in text:
            return 3, "word"
        negated = text.startswith("not ") or " not " in f" {text} "
        for token in text.split():
            if token in FEELING_WORDS:
                value = FEELING_WORDS[token]
                if negated:
                    value = min(value, 2)
                return value, "word"
    return None, "no_number"


def parse_weekday(text: str) -> str | None:
    """Return the single weekday named in ``text``, or ``None``."""
    found = {day for day in WEEKDAYS if re.search(rf"\b{day}\b", normalize(text))}
    return found.pop() if len(found) == 1 else None


class RuleBasedExtractor:
    """Offline extractor. No network, no API key, fully deterministic."""

    name = "rules"

    def extract(self, question: Question, utterance: str, context: ExtractionContext) -> Answer:
        flags = detect_flags(utterance)
        value: Any = None
        detail: dict[str, Any] = {}
        if question.type == "yes_no":
            value = parse_yes_no(utterance, question.is_problem_question)
        elif question.type == "scale":
            value, detail["how"] = parse_scale(utterance, question.min, question.max)
        elif question.type == "day_of_week":
            value = parse_weekday(utterance)
            if value is not None:
                detail["correct"] = value == WEEKDAYS[context.today.weekday()]
        else:
            value = utterance.strip() or None
        return Answer(
            question_id=question.id,
            raw=utterance,
            value=value,
            understood=value is not None,
            flags=flags,
            source=self.name,
            detail=detail,
        )
