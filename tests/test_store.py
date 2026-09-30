from datetime import timedelta

from care_voice.models import CheckinStatus, Severity
from care_voice.risk import RiskEngine
from care_voice.store import Store

from .conftest import GOOD_DAY, NOW


def test_round_trip_checkin_and_alerts(run_session, tmp_path):
    store = Store(tmp_path / "sub" / "cv.db")
    result = run_session(["yes", "no", *GOOD_DAY[2:]])
    checkin_id = store.save_checkin(result)
    assert result.id == checkin_id
    store.save_alerts(RiskEngine().evaluate(result))

    (loaded,) = store.recent_checkins()
    assert loaded.id == checkin_id
    assert loaded.status is CheckinStatus.COMPLETED
    assert loaded.value("took_meds") is False
    assert loaded.value("mood") == 4
    assert loaded.transcript == result.transcript
    assert loaded.started_at == NOW

    (alert,) = store.recent_alerts()
    assert (alert.code, alert.severity, alert.checkin_id) == ("MISSED_MEDS", Severity.HIGH, 1)
    store.close()


def test_history_is_newest_first_and_filtered(run_session):
    store = Store(":memory:")
    for days_ago in (3, 1, 2):
        store.save_checkin(run_session(GOOD_DAY, now=NOW - timedelta(days=days_ago)))
    other = run_session(GOOD_DAY)
    other.person = "Bob"
    store.save_checkin(other)
    history = store.history("Ada")
    assert [h.started_at for h in history] == [NOW - timedelta(days=d) for d in (1, 2, 3)]
    assert len(store.history("Ada", before=NOW - timedelta(days=1))) == 2
    assert len(store.history("Ada", limit=1)) == 1
