"""End-to-end tests: run the real CLI on the example transcripts and check the alerts."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from care_voice.cli import main

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
CONFIG = str(EXAMPLES / "care-voice.yaml")


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    code = main(list(argv), out=out)
    return code, out.getvalue()


def simulate(db: Path, replies: str, date: str = "2026-09-30", *extra: str) -> str:
    code, output = run(
        "simulate",
        "--config",
        CONFIG,
        "--db",
        str(db),
        "--replies",
        str(EXAMPLES / "replies" / replies),
        "--date",
        date,
        "--no-notify",
        *extra,
    )
    assert code == 0
    return output


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "care-voice.db"


def test_good_day_raises_no_alerts(db: Path) -> None:
    output = simulate(db, "good-day.txt")
    assert "not a medical device" in output
    assert "--- check-in completed (1 attempt(s)) ---" in output
    assert "alerts: none" in output


def test_concerning_day_raises_expected_alerts(db: Path) -> None:
    output = simulate(db, "concerning-day.txt")
    for expected in (
        "[HIGH] FALL_REPORTED",
        "[HIGH] MISSED_MEDS",
        "[HIGH] PAIN_REPORTED",
        "[MEDIUM] POSSIBLE_CONFUSION",
        "(today is Wednesday)",
        "[LOW] LOW_MOOD",
    ):
        assert expected in output

    code, alerts = run("alerts", "--config", CONFIG, "--db", str(db))
    assert code == 0
    assert "FALL_REPORTED" in alerts
    assert "MISSED_MEDS" in alerts


def test_confused_day_flags_confusion(db: Path) -> None:
    output = simulate(db, "confused-day.txt")
    assert "POSSIBLE_CONFUSION" in output


def test_no_answer_is_recorded_and_alerted(db: Path) -> None:
    code, output = run(
        "simulate", "--config", CONFIG, "--db", str(db), "--no-answer", "--no-notify"
    )
    assert code == 0
    assert "(call attempt 3: no answer)" in output
    assert "check-in no_answer (3 attempt(s))" in output
    assert "NO_ANSWER" in output

    code, history = run("history", "--config", CONFIG, "--db", str(db))
    assert code == 0
    assert "no_answer" in history


def test_mood_drop_against_baseline(db: Path, tmp_path: Path) -> None:
    for day in ("2026-09-26", "2026-09-27", "2026-09-28"):
        simulate(db, "good-day.txt", day)
    low = tmp_path / "low.txt"
    good = (EXAMPLES / "replies" / "good-day.txt").read_text("utf-8").splitlines()
    good = [line for line in good if line and not line.startswith("#")]
    good[-1] = "About a two"
    low.write_text("\n".join(good) + "\n", "utf-8")
    code, output = run(
        "simulate",
        "--config",
        CONFIG,
        "--db",
        str(db),
        "--replies",
        str(low),
        "--date",
        "2026-09-30",
        "--no-notify",
    )
    assert code == 0
    assert "MOOD_DROP" in output


def test_validate_example_scripts() -> None:
    code, output = run("validate", "--config", CONFIG)
    assert code == 0
    assert output.startswith("ok: config valid")
    code, output = run(
        "validate", "--config", CONFIG, "--script", str(EXAMPLES / "gentle-evening-script.yaml")
    )
    assert code == 0


def test_bad_config_exits_with_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("extractor:\n  kind: nonsense\n", "utf-8")
    code, _ = run("validate", "--config", str(bad))
    assert code == 2
    assert "error:" in capsys.readouterr().err
