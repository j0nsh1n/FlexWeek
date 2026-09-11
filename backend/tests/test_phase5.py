from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.storage import initialize

PASSWORD = "password-12345"
WRITE = {"X-FlexWeek-Request": "1"}
WEEK = "2026-09-07"


def phase7_defaults() -> dict:
    return {
        "reminder_dnd_override": False,
        "timer_work_min": 30,
        "timer_break_min": 15,
        "timer_long_break_min": 30,
        "timer_long_break_every": 4,
        "auto_split_pomodoro": False,
        "default_spotify_url": None,
        "alarms": [],
    }


def make_client(tmp_path: Path) -> TestClient:
    db = tmp_path / "phase5.db"
    app = create_app(database=db, origin="http://testserver")
    return TestClient(app)


def register(client: TestClient, username: str = "alice") -> TestClient:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": PASSWORD},
        headers=WRITE,
    )
    assert response.status_code == 201
    return client


def test_reminder_preferences_persist(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        register(client)
        assert client.get("/api/preferences").json() == {
            "theme": "system",
            "reminders_enabled": False,
            "reminder_lead_min": 5,
            "reminder_sound": True,
            **phase7_defaults(),
        }
        payload = {
            "theme": "slate",
            "reminders_enabled": True,
            "reminder_lead_min": 15,
            "reminder_sound": False,
            **phase7_defaults(),
        }
        assert client.put("/api/preferences", json=payload, headers=WRITE).status_code == 200
        assert client.get("/api/preferences").json() == payload
        assert client.put(
            "/api/preferences",
            json={**payload, "reminder_lead_min": 121},
            headers=WRITE,
        ).status_code == 422


def test_reminder_preference_migration_on_legacy_db(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "legacy.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
            CREATE TABLE sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires INTEGER NOT NULL
            );
            CREATE TABLE weeks (
                user_id INTEGER NOT NULL, week_start TEXT NOT NULL, blocks TEXT NOT NULL, revision INTEGER NOT NULL,
                PRIMARY KEY (user_id, week_start)
            );
            CREATE TABLE preferences (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                theme TEXT NOT NULL DEFAULT 'nocturne'
            );
            CREATE TABLE auth_attempts (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);
            """
        )
    initialize(db)
    app = create_app(database=db, origin="http://testserver")
    with TestClient(app) as client:
        register(client, "migrated")
        prefs = client.get("/api/preferences").json()
        assert prefs["reminders_enabled"] is False
        assert prefs["reminder_lead_min"] == 5
        assert prefs["reminder_sound"] is True


def test_completed_flag_round_trips_on_week(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        register(client)
        block = {
            "id": "hw",
            "title": "Essay",
            "kind": "flexible",
            "duration_min": 60,
            "days": [0],
            "priority": 3,
            "energy": "medium",
            "completed": True,
            "completed_day": 0,
            "start": "09:00",
            "category": "assignments",
        }
        put = client.put(
            "/api/week",
            json={"week_start": WEEK, "blocks": [block], "revision": 0},
            headers=WRITE,
        )
        assert put.status_code == 200
        loaded = client.get(f"/api/week?week_start={WEEK}").json()["blocks"][0]
        assert loaded["completed"] is True
        assert loaded["completed_day"] == 0
        assert loaded["category"] == "assignments"
