from datetime import timedelta

from care_voice.models import Answer, CheckinResult, CheckinStatus, Severity
from care_voice.risk import QuestionIds, RiskConfig, RiskEngine, mood_baseline

from .conftest import GOOD_DAY, NOW


def codes(alerts):
    return [a.code for a in alerts]


def mood_day(mood, days_ago):
    return CheckinResult(
        person="Ada",
        started_at=NOW - timedelta(days=days_ago),
        status=CheckinStatus.COMPLETED,
        answers={"mood": Answer("mood", str(mood), mood)},
    )


def test_good_day_has_no_alerts(run_session):
    assert RiskEngine().evaluate(run_session(GOOD_DAY)) == []


def test_missed_meds_is_high(run_session):
    replies = list(GOOD_DAY)
    replies[1] = "No, I forgot"
    alerts = RiskEngine().evaluate(run_session(replies))
    assert codes(alerts) == ["MISSED_MEDS"]
    assert alerts[0].severity is Severity.HIGH
    assert alerts[0].reasons == ('said: "No, I forgot"',)


def test_unconfirmed_meds_is_medium(run_session):
    replies = ["yes", "what?", "pardon?", *GOOD_DAY[2:]]
    alerts = RiskEngine().evaluate(run_session(replies))
    assert "MEDS_UNCONFIRMED" in codes(alerts)


def test_fall_and_severe_pain(run_session):
    replies = ["yes", "yes", "yes", "yes my hip", "eight", "my hip", "Yes, I fell yesterday"]
    replies += ["wednesday", "3"]
    alerts = RiskEngine().evaluate(run_session(replies))
    by_code = {a.code: a for a in alerts}
    assert by_code["FALL_REPORTED"].severity is Severity.HIGH
    assert by_code["PAIN_REPORTED"].severity is Severity.HIGH
    assert "pain level 8/10" in by_code["PAIN_REPORTED"].reasons
    assert alerts[0].severity >= alerts[-1].severity


def test_fall_mentioned_elsewhere_counts(run_session):
    replies = ["Not well, I slipped getting up in the night", *GOOD_DAY[1:]]
    alerts = RiskEngine().evaluate(run_session(replies))
    assert "FALL_REPORTED" in codes(alerts)
    assert "POOR_SLEEP" in codes(alerts)


def test_mild_pain_is_medium(run_session):
    replies = ["yes", "yes", "yes", "a little", "3", "my back", "no", "wednesday", "4"]
    alerts = RiskEngine().evaluate(run_session(replies))
    assert [(a.code, a.severity) for a in alerts] == [("PAIN_REPORTED", Severity.MEDIUM)]


def test_confusion_signals_escalate(run_session):
    one = list(GOOD_DAY)
    one[5] = "Saturday"
    alerts = RiskEngine().evaluate(run_session(one))
    assert [(a.code, a.severity) for a in alerts] == [("POSSIBLE_CONFUSION", Severity.MEDIUM)]

    many = [
        "I need to feed the cat",
        "I need to feed the cat",
        "yes",
        "no",
        "no",
        "no",
        "Where am I?",
        "what day is it",
        "4",
    ]
    alerts = RiskEngine().evaluate(run_session(many))
    confusion = next(a for a in alerts if a.code == "POSSIBLE_CONFUSION")
    assert confusion.severity is Severity.HIGH
    joined = " ".join(confusion.reasons)
    assert "repeated the same reply" in joined
    assert "sounded disoriented" in joined
    assert "could not name the day" in joined


def test_emergency_is_critical(run_session):
    alerts = RiskEngine().evaluate(run_session(["I can't breathe properly"]))
    assert alerts[0].code == "EMERGENCY_WORDS"
    assert alerts[0].severity is Severity.CRITICAL


def test_not_eaten_and_low_mood_are_low(run_session):
    replies = list(GOOD_DAY)
    replies[2] = "No, not hungry"
    replies[6] = "2"
    alerts = RiskEngine().evaluate(run_session(replies))
    assert {(a.code, a.severity) for a in alerts} == {
        ("NOT_EATEN", Severity.LOW),
        ("LOW_MOOD", Severity.LOW),
    }


def test_mood_drop_against_baseline(run_session):
    history = [mood_day(5, d) for d in range(1, 6)]
    replies = list(GOOD_DAY)
    replies[6] = "3"
    alerts = RiskEngine().evaluate(run_session(replies), history)
    assert codes(alerts) == ["MOOD_DROP"]
    assert "recent average 5.0/5" in alerts[0].reasons[0]
    assert RiskEngine().evaluate(run_session(replies), history[:2]) == []


def test_mood_baseline_needs_enough_history():
    cfg = RiskConfig(baseline_min_checkins=3, baseline_window=3)
    assert mood_baseline([mood_day(4, 1), mood_day(4, 2)], cfg) is None
    days = [mood_day(2, 1), mood_day(4, 2), mood_day(3, 3), mood_day(5, 4)]
    assert mood_baseline(days, cfg) == 3.0


def test_no_answer_escalates_on_streak():
    today = CheckinResult("Ada", NOW, CheckinStatus.NO_ANSWER, attempts=3)
    alerts = RiskEngine().evaluate(today)
    assert [(a.code, a.severity) for a in alerts] == [("NO_ANSWER", Severity.HIGH)]
    yesterday = CheckinResult("Ada", NOW - timedelta(days=1), CheckinStatus.NO_ANSWER)
    alerts = RiskEngine().evaluate(today, [yesterday])
    assert alerts[0].severity is Severity.CRITICAL
    assert "2 check-ins in a row" in alerts[0].reasons[1]


def test_incomplete_checkin(run_session):
    alerts = RiskEngine().evaluate(run_session(["yes", "yes"]))
    assert codes(alerts) == ["CHECKIN_INCOMPLETE"]


def test_custom_question_ids(run_session):
    cfg = RiskConfig(ids=QuestionIds(took_meds="slept_well"))
    alerts = RiskEngine(cfg).evaluate(run_session(["no", *GOOD_DAY[1:]]))
    assert "MISSED_MEDS" in codes(alerts)


def test_alerts_carry_checkin_metadata(run_session):
    result = run_session(["yes", "no", *GOOD_DAY[2:]])
    result.id = 42
    (alert,) = RiskEngine().evaluate(result)
    assert (alert.checkin_id, alert.person, alert.created_at) == (42, "Ada", NOW)
