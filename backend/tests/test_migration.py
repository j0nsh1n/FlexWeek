"""Migration checks: older databases upgrade on start without losing a row."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

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


# The preferences table v0.8.0 shipped: its CHECK only allowed the two explicit themes.
PREFERENCES_BEFORE_SYSTEM = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL
    );
    CREATE TABLE preferences (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        theme TEXT NOT NULL DEFAULT 'nocturne' CHECK(theme IN ('nocturne', 'slate')),
        reminders_enabled INTEGER NOT NULL DEFAULT 0 CHECK(reminders_enabled IN (0, 1)),
        reminder_lead_min INTEGER NOT NULL DEFAULT 5 CHECK(reminder_lead_min >= 0 AND reminder_lead_min <= 120),
        reminder_sound INTEGER NOT NULL DEFAULT 1 CHECK(reminder_sound IN (0, 1)),
        reminder_dnd_override INTEGER NOT NULL DEFAULT 0 CHECK(reminder_dnd_override IN (0, 1)),
        timer_work_min INTEGER NOT NULL DEFAULT 30,
        timer_break_min INTEGER NOT NULL DEFAULT 15,
        timer_long_break_min INTEGER NOT NULL DEFAULT 30,
        timer_long_break_every INTEGER NOT NULL DEFAULT 4,
        auto_split_pomodoro INTEGER NOT NULL DEFAULT 0 CHECK(auto_split_pomodoro IN (0, 1)),
        default_spotify_url TEXT,
        alarms_json TEXT NOT NULL DEFAULT '[]'
    );
"""


def test_system_theme_migration_keeps_chosen_themes_and_defaults_new_rows_to_system(tmp_path: Path) -> None:
    path = tmp_path / "v0.8.0.db"
    with sqlite3.connect(path) as db:
        db.executescript(PREFERENCES_BEFORE_SYSTEM)
        for user_id, name in ((1, "light-student"), (2, "dark-student"), (3, "new-student")):
            db.execute("INSERT INTO users VALUES (?, ?, 'scrypt$placeholder-hash')", (user_id, name))
        db.execute("INSERT INTO preferences(user_id, theme, reminder_lead_min, alarms_json) VALUES (1, 'slate', 15, ?)",
                   ('[{"id":"a"}]',))
        db.execute("INSERT INTO preferences(user_id, theme) VALUES (2, 'nocturne')")

    initialize(path)
    initialize(path)

    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO preferences(user_id) VALUES (3)")
        themes = dict(db.execute("SELECT user_id, theme FROM preferences").fetchall())
        kept = db.execute("SELECT reminder_lead_min, alarms_json FROM preferences WHERE user_id = 1").fetchone()
        db.execute("UPDATE preferences SET theme = 'system' WHERE user_id = 1")
        leftovers = db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'preferences_%'"
        ).fetchall()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE preferences SET theme = 'dark' WHERE user_id = 2")

    assert themes == {1: "slate", 2: "nocturne", 3: "system"}
    assert kept == (15, '[{"id":"a"}]')
    assert leftovers == []


def test_an_unconstrained_legacy_theme_value_becomes_system(tmp_path: Path) -> None:
    path = tmp_path / "unconstrained.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
            CREATE TABLE preferences (user_id INTEGER PRIMARY KEY, theme TEXT NOT NULL DEFAULT 'nocturne');
        """)
        db.execute("INSERT INTO users VALUES (1, 'old-student', 'scrypt$placeholder-hash')")
        db.execute("INSERT INTO preferences VALUES (1, 'purple')")

    initialize(path)

    with sqlite3.connect(path) as db:
        assert db.execute("SELECT theme FROM preferences WHERE user_id = 1").fetchone() == ("system",)
