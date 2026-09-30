"""The extractor interface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from care_voice.models import Answer
from care_voice.script import Question


@dataclass(frozen=True)
class ExtractionContext:
    """Information an extractor may need beyond the utterance itself."""

    today: date
    person_name: str = ""


class Extractor(Protocol):
    """Maps one utterance, in reply to one question, to a structured answer.

    Implementations must never raise on odd input. When they cannot map the
    utterance to a value they return an :class:`Answer` with
    ``understood=False`` so that the engine can re-ask.
    """

    name: str

    def extract(self, question: Question, utterance: str, context: ExtractionContext) -> Answer:
        """Return the structured answer for ``utterance``."""
        ...
