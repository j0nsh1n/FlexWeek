"""Reminders are on unless the student turns them off.

Accounts made before 0.15 had them off only because setup never asked, so they are turned on once.
Each account records that it has been, so a student who turns them off afterwards stays off.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.storage import initialize

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
# The preferences table 0.14 made. Nothing in it records a one-time change.
PREFERENCES_0_14 = """
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
    CREATE TABLE preferences (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        theme TEXT NOT NULL DEFAULT 'system' CHECK(theme IN ('system', 'slate', 'nocturne')),
        reminders_enabled INTEGER NOT NULL DEFAULT 0 CHECK(reminders_enabled IN (0, 1)),
        reminder_lead_min INTEGER NOT NULL DEFAULT 5
            CHECK(reminder_lead_min >= 0 AND reminder_lead_min <= 120),
        reminder_sound INTEGER NOT NULL DEFAULT 1 CHECK(reminder_sound IN (0, 1)),
        reminder_dnd_override INTEGER NOT NULL DEFAULT 0 CHECK(reminder_dnd_override IN (0, 1)),
        timer_work_min INTEGER NOT NULL DEFAULT 30,
        timer_break_min INTEGER NOT NULL DEFAULT 15,
        timer_long_break_min INTEGER NOT NULL DEFAULT 30,
        timer_long_break_every INTEGER NOT NULL DEFAULT 4,
        auto_split_pomodoro INTEGER NOT NULL DEFAULT 0 CHECK(auto_split_pomodoro IN (0, 1)),
        default_spotify_url TEXT,
        alarms_json TEXT NOT NULL DEFAULT '[]',
        availability_json TEXT NOT NULL DEFAULT '{}',
        comfort_json TEXT NOT NULL DEFAULT '{}'
    );
"""


def reminders(database: Path) -> dict[int, int]:
    with sqlite3.connect(database) as db:
        return dict(db.execute("SELECT user_id, reminders_enabled FROM preferences").fetchall())


def client_for(database: Path) -> TestClient:
    return TestClient(create_app(database=database, origin="http://testserver"))


def register(client: TestClient, username: str) -> None:
    response = client.post("/api/auth/register", json={"username": username, "password": PASSWORD}, headers=WRITE)
    assert response.status_code == 201


def turn_off(client: TestClient) -> None:
    prefs = client.get("/api/preferences").json()
    assert client.put("/api/preferences", json={**prefs, "reminders_enabled": False}, headers=WRITE).status_code == 200


def test_a_new_account_has_reminders_on(tmp_path: Path) -> None:
    with client_for(tmp_path / "new.db") as client:
        register(client, "fresh")
        assert client.get("/api/preferences").json()["reminders_enabled"] is True


def test_a_preferences_body_without_the_switch_leaves_reminders_on(tmp_path: Path) -> None:
    with client_for(tmp_path / "partial.db") as client:
        register(client, "partial")
        saved = client.put("/api/preferences", json={"theme": "slate"}, headers=WRITE)
        assert saved.status_code == 200 and saved.json()["reminders_enabled"] is True


def test_accounts_from_0_14_are_turned_on_once_and_a_later_choice_stands(tmp_path: Path) -> None:
    database = tmp_path / "old.db"
    with sqlite3.connect(database) as db:
        db.executescript(PREFERENCES_0_14)
        for user_id, name in ((1, "skipped_setup"), (2, "said_no")):
            db.execute("INSERT INTO users VALUES (?, ?, 'scrypt$placeholder')", (user_id, name))
            db.execute("INSERT INTO preferences(user_id, reminder_lead_min) VALUES (?, 10)", (user_id,))

    initialize(database)
    assert reminders(database) == {1: 1, 2: 1}
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT reminder_lead_min FROM preferences WHERE user_id = 1").fetchone() == (10,)
        db.execute("UPDATE preferences SET reminders_enabled = 0 WHERE user_id = 2")
    initialize(database)
    initialize(database)
    assert reminders(database) == {1: 1, 2: 0}


def test_an_account_made_after_the_update_is_never_turned_on_again(tmp_path: Path) -> None:
    """Made in a database that 0.14 created, where the column's own default is still off."""
    database = tmp_path / "upgraded.db"
    with sqlite3.connect(database) as db:
        db.executescript(PREFERENCES_0_14)
    initialize(database)
    with client_for(database) as client:
        register(client, "newcomer")
        assert client.get("/api/preferences").json()["reminders_enabled"] is True
        turn_off(client)
    initialize(database)
    with client_for(database) as client:
        client.post("/api/auth/login", json={"username": "newcomer", "password": PASSWORD}, headers=WRITE)
        assert client.get("/api/preferences").json()["reminders_enabled"] is False
