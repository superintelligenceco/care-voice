"""Local SQLite storage for check-ins and alerts.

Everything stays in one file on disk. Nothing in this module talks to the
network.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from care_voice.models import Alert, Answer, CheckinResult, CheckinStatus, Severity, Turn

SCHEMA = """
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person TEXT NOT NULL,
    started_at TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 1,
    answers TEXT NOT NULL,
    transcript TEXT NOT NULL,
    unclear TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS checkins_person_time ON checkins (person, started_at);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkin_id INTEGER REFERENCES checkins (id) ON DELETE CASCADE,
    person TEXT NOT NULL,
    created_at TEXT NOT NULL,
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    reasons TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS alerts_person_time ON alerts (person, created_at);
"""


def _answer_to_json(a: Answer) -> dict[str, Any]:
    return {
        "question_id": a.question_id,
        "raw": a.raw,
        "value": a.value,
        "understood": a.understood,
        "flags": sorted(a.flags),
        "source": a.source,
        "detail": a.detail,
    }


def _answer_from_json(d: dict[str, Any]) -> Answer:
    return Answer(
        question_id=d["question_id"],
        raw=d["raw"],
        value=d["value"],
        understood=d["understood"],
        flags=frozenset(d["flags"]),
        source=d["source"],
        detail=d.get("detail", {}),
    )


class Store:
    """A thin wrapper around a SQLite database file (or ``:memory:``)."""

    def __init__(self, path: str | Path = "care-voice.db") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._conn:
            yield self._conn

    def save_checkin(self, result: CheckinResult) -> int:
        """Insert ``result`` and set its ``id``."""
        with self._tx() as conn:
            cur = conn.execute(
                "INSERT INTO checkins (person, started_at, status, attempts, answers, transcript,"
                " unclear) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    result.person,
                    result.started_at.isoformat(),
                    result.status.value,
                    result.attempts,
                    json.dumps({k: _answer_to_json(v) for k, v in result.answers.items()}),
                    json.dumps([[t.speaker, t.text, t.question_id] for t in result.transcript]),
                    json.dumps(result.unclear),
                ),
            )
        result.id = int(cur.lastrowid or 0)
        return result.id

    def save_alerts(self, alerts: list[Alert]) -> None:
        with self._tx() as conn:
            conn.executemany(
                "INSERT INTO alerts (checkin_id, person, created_at, severity, code, message,"
                " reasons) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        a.checkin_id,
                        a.person,
                        (a.created_at or datetime.now().astimezone()).isoformat(),
                        a.severity.label,
                        a.code,
                        a.message,
                        json.dumps(list(a.reasons)),
                    )
                    for a in alerts
                ],
            )

    @staticmethod
    def _row_to_checkin(row: sqlite3.Row) -> CheckinResult:
        return CheckinResult(
            id=row["id"],
            person=row["person"],
            started_at=datetime.fromisoformat(row["started_at"]),
            status=CheckinStatus(row["status"]),
            attempts=row["attempts"],
            answers={k: _answer_from_json(v) for k, v in json.loads(row["answers"]).items()},
            transcript=[Turn(s, t, q) for s, t, q in json.loads(row["transcript"])],
            unclear=json.loads(row["unclear"]),
        )

    def history(
        self, person: str, before: datetime | None = None, limit: int = 30
    ) -> list[CheckinResult]:
        """Return up to ``limit`` check-ins for ``person``, newest first."""
        sql = "SELECT * FROM checkins WHERE person = ?"
        params: list[Any] = [person]
        if before is not None:
            sql += " AND started_at < ?"
            params.append(before.isoformat())
        sql += " ORDER BY started_at DESC, id DESC LIMIT ?"
        params.append(limit)
        return [self._row_to_checkin(r) for r in self._conn.execute(sql, params)]

    def recent_checkins(self, limit: int = 50) -> list[CheckinResult]:
        rows = self._conn.execute(
            "SELECT * FROM checkins ORDER BY started_at DESC, id DESC LIMIT ?", (limit,)
        )
        return [self._row_to_checkin(r) for r in rows]

    def recent_alerts(self, limit: int = 100) -> list[Alert]:
        rows = self._conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        )
        return [
            Alert(
                code=r["code"],
                severity=Severity.parse(r["severity"]),
                message=r["message"],
                reasons=tuple(json.loads(r["reasons"])),
                checkin_id=r["checkin_id"],
                person=r["person"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]
