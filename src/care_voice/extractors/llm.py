"""An LLM-backed extractor for any OpenAI-compatible chat completions API.

The LLM only interprets the reply to the current question. The rule-based
extractor always runs as well: its safety flags are merged into the result,
and its answer is used whenever the LLM call fails or returns something
invalid. A misbehaving model can therefore add signal but never hide an
emergency keyword.

Only the current question, the reply, and today's weekday are sent to the
provider. Names, history, and caregiver details are never included.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import replace
from typing import Any

from care_voice.extractors.base import ExtractionContext
from care_voice.extractors.rules import WEEKDAYS, RuleBasedExtractor, parse_weekday
from care_voice.models import FLAG_DISORIENTED, FLAG_EMERGENCY, FLAG_FALL, FLAG_PAIN, Answer
from care_voice.script import Question

log = logging.getLogger(__name__)

ALLOWED_FLAGS = frozenset({FLAG_EMERGENCY, FLAG_FALL, FLAG_PAIN, FLAG_DISORIENTED})

SYSTEM_PROMPT = """\
You extract a structured answer from one spoken reply in a daily wellbeing \
check-in call with an older adult. Reply with a single JSON object and nothing else:
{"understood": true|false, "value": <see below>, "flags": [<zero or more of \
"emergency", "fall", "pain", "disoriented">]}
value rules by question type:
- yes_no: true or false. For problem questions, true means the problem is present.
- scale: an integer within the given range.
- day_of_week: the lowercase English weekday the person said, e.g. "tuesday".
- text: a short plain summary of what the person said.
Set understood to false and value to null if the reply does not answer the question.
Flags describe the reply itself, whatever the question: "emergency" for an urgent \
need for help, "fall" for a reported fall, "pain" for reported pain, "disoriented" \
for confusion about time, place, or the call. Do not guess."""


class LLMError(RuntimeError):
    """Raised internally when the provider call fails or returns invalid output."""


class LLMExtractor:
    """Extractor that asks an OpenAI-compatible model, with a rule-based safety net."""

    name = "llm"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 15.0,
        fallback: RuleBasedExtractor | None = None,
    ) -> None:
        if not base_url.startswith(("https://", "http://")):
            raise ValueError("base_url must start with http:// or https://")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.fallback = fallback or RuleBasedExtractor()

    def _messages(self, question: Question, utterance: str, context: ExtractionContext) -> Any:
        spec: dict[str, Any] = {
            "question": question.ask,
            "type": question.type,
            "problem_question": question.is_problem_question,
            "today": WEEKDAYS[context.today.weekday()],
            "reply": utterance,
        }
        if question.type == "scale":
            spec["range"] = [question.min, question.max]
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(spec)},
        ]

    def _call(self, messages: Any) -> dict[str, Any]:
        body = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }
        ).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(  # noqa: S310 - scheme validated in __init__
            f"{self.base_url}/chat/completions", data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                payload = json.loads(resp.read())
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError) as exc:
            raise LLMError(f"provider call failed: {exc}") from exc
        except (json.JSONDecodeError, TypeError) as exc:
            raise LLMError(f"provider returned invalid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMError("provider returned a non-object")
        return parsed

    @staticmethod
    def _coerce(question: Question, parsed: dict[str, Any]) -> tuple[Any, bool]:
        value = parsed.get("value")
        if not parsed.get("understood") or value is None:
            return None, False
        if question.type == "yes_no":
            if isinstance(value, bool):
                return value, True
            raise LLMError(f"expected boolean, got {value!r}")
        if question.type == "scale":
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise LLMError(f"expected integer, got {value!r}")
            if not question.min <= value <= question.max:
                raise LLMError(f"value {value!r} outside {question.min}-{question.max}")
            return int(value), True
        if question.type == "day_of_week":
            day = parse_weekday(str(value))
            if day is None:
                raise LLMError(f"expected a weekday, got {value!r}")
            return day, True
        return str(value), True

    def extract(self, question: Question, utterance: str, context: ExtractionContext) -> Answer:
        baseline = self.fallback.extract(question, utterance, context)
        try:
            parsed = self._call(self._messages(question, utterance, context))
            value, understood = self._coerce(question, parsed)
        except LLMError as exc:
            log.warning("LLM extractor fell back to rules for %s: %s", question.id, exc)
            return replace(baseline, detail={**baseline.detail, "llm_error": str(exc)})
        raw_flags = parsed.get("flags") or []
        llm_flags = {f for f in raw_flags if isinstance(f, str) and f in ALLOWED_FLAGS}
        detail = dict(baseline.detail)
        if question.type == "day_of_week" and understood:
            detail["correct"] = value == WEEKDAYS[context.today.weekday()]
        return Answer(
            question_id=question.id,
            raw=utterance,
            value=value,
            understood=understood,
            flags=baseline.flags | frozenset(llm_flags),
            source=self.name,
            detail=detail,
        )
