"""Load and validate YAML check-in scripts."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

QUESTION_TYPES = frozenset({"yes_no", "scale", "day_of_week", "text"})


class ScriptError(ValueError):
    """Raised when a check-in script is malformed."""


@dataclass(frozen=True)
class Question:
    """One question in a check-in script."""

    id: str
    type: str
    ask: str
    reprompt: str | None = None
    min: int = 1
    max: int = 5
    polarity: str = "positive"
    followups: tuple[Followup, ...] = ()

    @property
    def is_problem_question(self) -> bool:
        """True when a "yes" answer reports a problem (for example, "Are you in pain?")."""
        return self.polarity == "problem"


@dataclass(frozen=True)
class Followup:
    """A question asked only when the parent answer equals ``when``."""

    when: Any
    question: Question


@dataclass(frozen=True)
class CheckinScript:
    """A parsed check-in script."""

    name: str
    greeting: str
    closing: str
    questions: tuple[Question, ...]
    emergency_notice: str = (
        "If you need urgent help, please hang up and call your local emergency number now."
    )
    reprompt_prefix: str = "Sorry, I didn't quite catch that."
    source: str = field(default="<memory>", compare=False)

    def iter_all(self) -> Iterator[Question]:
        """Yield every question, including follow-ups, depth first."""

        def walk(questions: tuple[Question, ...]) -> Iterator[Question]:
            for q in questions:
                yield q
                yield from walk(tuple(f.question for f in q.followups))

        yield from walk(self.questions)

    def question(self, question_id: str) -> Question:
        for q in self.iter_all():
            if q.id == question_id:
                return q
        raise KeyError(question_id)


def _parse_question(raw: Any, where: str) -> Question:
    if not isinstance(raw, dict):
        raise ScriptError(f"{where}: each question must be a mapping")
    for key in ("id", "type", "ask"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ScriptError(f"{where}: missing required string field {key!r}")
    qtype = raw["type"]
    if qtype not in QUESTION_TYPES:
        allowed = ", ".join(sorted(QUESTION_TYPES))
        raise ScriptError(f"{where}: unknown type {qtype!r}; expected one of: {allowed}")
    lo, hi = raw.get("min", 1), raw.get("max", 5)
    if qtype == "scale" and not (isinstance(lo, int) and isinstance(hi, int) and lo < hi):
        raise ScriptError(f"{where}: scale questions need integer min < max")
    polarity = raw.get("polarity", "positive")
    if polarity not in ("positive", "problem"):
        raise ScriptError(f"{where}: polarity must be 'positive' or 'problem'")
    followups = []
    for i, f in enumerate(raw.get("followups") or []):
        if not isinstance(f, dict) or "when" not in f:
            raise ScriptError(f"{where}.followups[{i}]: needs a 'when' value")
        body = {k: v for k, v in f.items() if k != "when"}
        followups.append(Followup(f["when"], _parse_question(body, f"{where}.followups[{i}]")))
    return Question(
        id=raw["id"],
        type=qtype,
        ask=raw["ask"].strip(),
        reprompt=(raw.get("reprompt") or None),
        min=lo,
        max=hi,
        polarity=polarity,
        followups=tuple(followups),
    )


def parse_script(data: Any, source: str = "<memory>") -> CheckinScript:
    """Build a :class:`CheckinScript` from already-loaded YAML data."""
    if not isinstance(data, dict):
        raise ScriptError(f"{source}: script must be a mapping")
    questions_raw = data.get("questions")
    if not isinstance(questions_raw, list) or not questions_raw:
        raise ScriptError(f"{source}: 'questions' must be a non-empty list")
    questions = tuple(
        _parse_question(q, f"{source}: questions[{i}]") for i, q in enumerate(questions_raw)
    )
    kwargs: dict[str, str] = {}
    for key in ("emergency_notice", "reprompt_prefix"):
        if data.get(key):
            kwargs[key] = str(data[key]).strip()
    script = CheckinScript(
        name=str(data.get("name", "check-in")),
        greeting=str(data.get("greeting", "Hello {name}, this is your daily check-in.")).strip(),
        closing=str(data.get("closing", "Thank you, {name}. Talk to you tomorrow.")).strip(),
        questions=questions,
        source=source,
        **kwargs,
    )
    seen: set[str] = set()
    for q in script.iter_all():
        if q.id in seen:
            raise ScriptError(f"{source}: duplicate question id {q.id!r}")
        seen.add(q.id)
    return script


def load_script(path: str | Path | None = None) -> CheckinScript:
    """Load a script from ``path``, or the bundled default when ``path`` is ``None``."""
    if path is None or str(path) == "default":
        text = resources.files("care_voice").joinpath("data/default_script.yaml").read_text("utf-8")
        return parse_script(yaml.safe_load(text), "default")
    p = Path(path)
    try:
        text = p.read_text("utf-8")
    except OSError as exc:
        raise ScriptError(f"cannot read script {p}: {exc}") from exc
    return parse_script(yaml.safe_load(text), str(p))
