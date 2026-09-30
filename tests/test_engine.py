import pytest

from care_voice.engine import CheckinSession, RetryPolicy, run_checkin
from care_voice.models import CheckinStatus

from .conftest import GOOD_DAY, NOW


def test_good_day_answers_everything(run_session):
    result = run_session(GOOD_DAY)
    assert result.status is CheckinStatus.COMPLETED
    assert result.value("slept_well") is True
    assert result.value("took_meds") is True
    assert result.value("in_pain") is False
    assert "pain_level" not in result.answers
    assert result.value("day_of_week") == "wednesday"
    assert result.value("mood") == 4
    assert result.unclear == []


def test_greeting_uses_name_and_closing_ends_session(script, extractor):
    session = CheckinSession(script, extractor, "Ada", NOW)
    first = session.start()
    assert first.startswith("Good morning, Ada.")
    assert first.endswith("Did you sleep well last night?")
    with pytest.raises(RuntimeError):
        session.start()
    line = None
    for reply in GOOD_DAY:
        line = session.respond(reply)
    assert session.done
    assert line is not None and line.startswith("Thank you, Ada.")
    assert session.respond("anything else") is None


def test_respond_before_start_raises(script, extractor):
    with pytest.raises(RuntimeError):
        CheckinSession(script, extractor, "Ada", NOW).respond("hi")


def test_pain_followups_asked_only_on_yes(run_session):
    result = run_session(
        ["yes", "yes", "yes", "my back hurts", "8", "lower back", "no", "wed", "3"]
    )
    assert result.value("pain_level") == 8
    assert result.value("pain_where") == "lower back"


def test_unclear_answer_is_reprompted_once_then_recorded(script, extractor):
    session = CheckinSession(script, extractor, "Ada", NOW, max_reprompts=1)
    session.start()
    reprompt = session.respond("purple")
    assert reprompt is not None and reprompt.startswith("Sorry, I didn't quite catch that.")
    assert "good night's sleep" in reprompt
    nxt = session.respond("banana")
    assert nxt == "Have you taken your morning medication?"
    assert session.result().unclear == ["slept_well"]


def test_reprompt_then_understood(run_session):
    result = run_session(["hmm", "yes", *GOOD_DAY[1:]])
    assert result.value("slept_well") is True
    assert result.unclear == []


def test_emergency_ends_the_session_with_notice(script, extractor):
    session = CheckinSession(script, extractor, "Ada", NOW)
    session.start()
    line = session.respond("Help me, I've fallen and I can't get up")
    assert session.done
    assert line is not None and "emergency number" in line
    result = session.result()
    assert "emergency" in result.answers["slept_well"].flags


def test_repeated_silence_abandons(run_session):
    result = run_session(["", "", ""], max_silences=3)
    assert result.status is CheckinStatus.ABANDONED


def test_hang_up_mid_call(run_session):
    result = run_session(["yes"])
    assert result.status is CheckinStatus.ABANDONED
    assert list(result.answers) == ["slept_well"]


class FakeChannel:
    def __init__(self, answer_on=1, replies=()):
        self.answer_on = answer_on
        self.replies = list(replies)
        self.said = []
        self.connects = 0

    def connect(self):
        self.connects += 1
        return self.answer_on is not None and self.connects >= self.answer_on

    def say(self, text):
        self.said.append(text)

    def listen(self):
        return self.replies.pop(0) if self.replies else None

    def close(self):
        pass


def _factory(script, extractor):
    return lambda: CheckinSession(script, extractor, "Ada", NOW)


def test_run_checkin_retries_until_answered(script, extractor):
    channel = FakeChannel(answer_on=2, replies=GOOD_DAY)
    sleeps: list[float] = []
    result = run_checkin(
        _factory(script, extractor), channel, RetryPolicy(3, 60), sleep=sleeps.append
    )
    assert result.status is CheckinStatus.COMPLETED
    assert result.attempts == 2
    assert sleeps == [60]
    assert channel.said[-1].startswith("Thank you")


def test_run_checkin_no_answer(script, extractor):
    channel = FakeChannel(answer_on=None)
    sleeps: list[float] = []
    result = run_checkin(
        _factory(script, extractor), channel, RetryPolicy(3, 5), sleep=sleeps.append
    )
    assert result.status is CheckinStatus.NO_ANSWER
    assert result.attempts == 3
    assert sleeps == [5, 5]


def test_run_checkin_hang_up(script, extractor):
    channel = FakeChannel(replies=["yes", "yes"])
    result = run_checkin(_factory(script, extractor), channel)
    assert result.status is CheckinStatus.ABANDONED
