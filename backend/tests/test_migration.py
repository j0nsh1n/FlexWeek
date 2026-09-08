"""Migration checks: the pre-dated one-row-per-account weeks table upgrades without losing a row."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from backend.storage import initialize

# The schema before dated weeks: weeks keyed by user_id alone, no week_start column.
OLD_SCHEMA = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL
    );
    CREATE TABLE weeks (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        blocks TEXT NOT NULL DEFAULT '[]',
        revision INTEGER NOT NULL DEFAULT 0
    );
"""

LEGACY_BLOCKS = [
    {
        "id": "hw-tuesday",
        "title": "History essay",
        "kind": "flexible",
        "duration_min": 45,
        "days": [1],
        "priority": 2,
        "energy": "low",
        "earliest": None,
        "latest": "Tuesday 20:00",
        "start": None,
        "course": "History",
    }
]
LEGACY_JSON = json.dumps(LEGACY_BLOCKS)


def test_initialize_twice_migrates_a_legacy_week_without_losing_it(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.executescript(OLD_SCHEMA)
        db.execute("INSERT INTO users VALUES (1, 'legacy-student', 'scrypt$placeholder-hash')")
        db.execute("INSERT INTO weeks(user_id, blocks, revision) VALUES (1, ?, 4)", (LEGACY_JSON,))

    initialize(path)
    initialize(path)

    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT user_id, week_start, blocks, revision FROM weeks").fetchall()
        legacy = db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'weeks_legacy'"
        ).fetchall()

    assert len(rows) == 1
    user_id, week_start, blocks, revision = rows[0]
    assert (user_id, blocks, revision) == (1, LEGACY_JSON, 4)
    assert date.fromisoformat(week_start).weekday() == 0
    assert legacy == []
