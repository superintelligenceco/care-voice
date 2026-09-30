"""The conversation engine: drives one check-in from a script.

:class:`CheckinSession` is a turn-based state machine. It never blocks on
I/O, so the same session works for the terminal simulator (synchronous
``input()``), and for telephony webhooks, where each reply arrives as a
separate HTTP request.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from care_voice.extractors.base import ExtractionContext, Extractor
from care_voice.models import FLAG_EMERGENCY, Answer, CheckinResult, CheckinStatus, Turn
from care_voice.script import CheckinScript, Question


class CheckinSession:
    """One check-in conversation.

    Call :meth:`start` for the opening line, then pass each reply to
    :meth:`respond` until :attr:`done` is true. :meth:`result` returns the
    structured outcome.
    """

    def __init__(
        self,
        script: CheckinScript,
        extractor: Extractor,
        person_name: str,
        now: datetime,
        max_reprompts: int = 1,
        max_silences: int = 3,
    ) -> None:
        self.script = script
        self.extractor = extractor
        self.person_name = person_name
        self.now = now
        self.max_reprompts = max_reprompts
        self.max_silences = max_silences
        self.context = ExtractionContext(today=now.date(), person_name=person_name)
        self._pending: list[Question] = list(script.questions)
        self._current: Question | None = None
        self._reprompts = 0
        self._silences = 0
        self._carried_flags: frozenset[str] = frozenset()
        self._started = False
        self.done = False
        self.status = CheckinStatus.COMPLETED
        self.answers: dict[str, Answer] = {}
        self.unclear: list[str] = []
        self.transcript: list[Turn] = []

    def _fmt(self, text: str) -> str:
        return text.replace("{name}", self.person_name)

    def _agent(self, text: str) -> str:
        text = self._fmt(text)
        qid = self._current.id if self._current else None
        self.transcript.append(Turn("agent", text, qid))
        return text

    def _advance(self, prefix: str = "") -> str:
        self._reprompts = 0
        self._carried_flags = frozenset()
        if not self._pending:
            self._current = None
            self.done = True
            return self._agent(f"{prefix}{self.script.closing}")
        self._current = self._pending.pop(0)
        return self._agent(f"{prefix}{self._current.ask}")

    def start(self) -> str:
        """Return the greeting and the first question."""
        if self._started:
            raise RuntimeError("session already started")
        self._started = True
        return self._advance(prefix=f"{self._fmt(self.script.greeting)} ")

    def hang_up(self) -> None:
        """Record that the person ended the call before the script finished."""
        if not self.done:
            self.status = CheckinStatus.ABANDONED
            self.done = True

    def respond(self, utterance: str | None) -> str | None:
        """Process one reply and return the agent's next line.

        ``None`` or an empty string means silence. Returns ``None`` once the
        session is over.
        """
        if not self._started:
            raise RuntimeError("call start() first")
        if self.done or self._current is None:
            return None
        question = self._current
        utterance = (utterance or "").strip()
        self.transcript.append(Turn("person", utterance or "(silence)", question.id))

        if not utterance:
            self._silences += 1
            if self._silences >= self.max_silences:
                self.status = CheckinStatus.ABANDONED
                self.done = True
                return None
        else:
            self._silences = 0

        answer = self.extractor.extract(question, utterance, self.context)
        # Keep safety flags from earlier, re-asked attempts at this question.
        if self._carried_flags - answer.flags:
            answer = replace(answer, flags=answer.flags | self._carried_flags)
        self._carried_flags = answer.flags

        if FLAG_EMERGENCY in answer.flags:
            self.answers[question.id] = answer
            self.done = True
            self._current = None
            return self._agent(self.script.emergency_notice)

        if not answer.understood and self._reprompts < self.max_reprompts:
            self._reprompts += 1
            reprompt = question.reprompt or question.ask
            return self._agent(f"{self.script.reprompt_prefix} {reprompt}")

        self.answers[question.id] = answer
        if answer.understood:
            followups = [f.question for f in question.followups if f.when == answer.value]
            self._pending[:0] = followups
        else:
            self.unclear.append(question.id)
        return self._advance()

    def result(self) -> CheckinResult:
        """Return the structured outcome. Safe to call before the session ends."""
        return CheckinResult(
            person=self.person_name,
            started_at=self.now,
            status=self.status,
            answers=dict(self.answers),
            transcript=list(self.transcript),
            unclear=list(self.unclear),
        )


class Channel(Protocol):
    """A synchronous, turn-by-turn connection to the person."""

    def connect(self) -> bool:
        """Try to reach the person. Return ``False`` if nobody answers."""
        ...

    def say(self, text: str) -> None:
        """Speak or print one agent line."""
        ...

    def listen(self) -> str | None:
        """Return the next reply, ``""`` for silence, or ``None`` if the person hung up."""
        ...

    def close(self) -> None:
        """Release the connection."""
        ...


@dataclass
class RetryPolicy:
    """How many times to try reaching the person, and how long to wait between tries."""

    attempts: int = 3
    delay_seconds: float = 0.0


def run_checkin(
    make_session: Callable[[], CheckinSession],
    channel: Channel,
    retry: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> CheckinResult:
    """Run a full check-in over ``channel``, retrying when nobody answers."""
    retry = retry or RetryPolicy()
    for attempt in range(1, max(1, retry.attempts) + 1):
        if channel.connect():
            session = make_session()
            try:
                line: str | None = session.start()
                while line is not None:
                    channel.say(line)
                    if session.done:
                        break
                    reply = channel.listen()
                    if reply is None:
                        session.hang_up()
                        break
                    line = session.respond(reply)
            finally:
                channel.close()
            result = session.result()
            result.attempts = attempt
            return result
        if attempt < retry.attempts and retry.delay_seconds > 0:
            sleep(retry.delay_seconds)
    session = make_session()
    result = session.result()
    result.status = CheckinStatus.NO_ANSWER
    result.attempts = max(1, retry.attempts)
    return result
