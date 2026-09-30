"""The telephony and voice adapter interface.

EXPERIMENTAL. The interface can change before 1.0.

A voice adapter connects a :class:`care_voice.engine.CheckinSession` to a
real phone call or voice session. Providers differ in how they deliver
speech, so the contract is kept small:

1. :meth:`VoiceAdapter.start_call` asks the provider to ring the person and
   returns the provider's call id.
2. The provider reports what the person said, turn by turn, as
   :class:`CallEvent` objects passed to :meth:`VoiceAdapter.handle_event`.
   The adapter feeds each utterance to the session with
   ``session.respond(text)`` and returns the provider-specific reply (for
   Twilio, a TwiML document) that speaks the agent's next line.
3. When the session is done, or the call ends early, or nobody answers after
   the configured attempts, the adapter hands the
   :class:`care_voice.models.CheckinResult` to
   :meth:`care_voice.service.CareVoice.process`, which stores it, evaluates
   the rules, and notifies caregivers.

Speech recognition and text-to-speech stay with the provider. The core only
ever sees text, so the extractor and the rules behave the same in the
simulator and on a real call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class CallEvent:
    """A provider-neutral event for one call.

    ``kind`` is one of ``"answered"``, ``"speech"``, ``"silence"``,
    ``"ended"``, or ``"unanswered"``.
    """

    call_id: str
    kind: str
    text: str = ""
    raw: dict[str, str] = field(default_factory=dict)


class VoiceAdapter(Protocol):
    """What a telephony or voice provider integration implements."""

    name: str

    def start_call(self, to_number: str) -> str:
        """Place an outbound call and return the provider's call id."""
        ...

    def handle_event(self, event: CallEvent) -> str:
        """Advance the call's session and return the provider-specific response body."""
        ...
