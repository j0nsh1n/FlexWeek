from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.models import valid_spotify_url
from backend.storage import initialize

WRITE = {"X-FlexWeek-Request": "1"}
PASSWORD = "password-12345"
WEEK = "2026-09-07"


def register(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"username": "phase7", "password": PASSWORD},
        headers=WRITE,
    )
    assert response.status_code == 201


def test_phase7_preferences_and_alarms_round_trip(tmp_path: Path) -> None:
    with TestClient(create_app(database=tmp_path / "phase7.db", origin="http://testserver")) as client:
        register(client)
        defaults = client.get("/api/preferences").json()
        assert defaults | {} == {
            "theme": "nocturne",
            "reminders_enabled": False,
            "reminder_lead_min": 5,
            "reminder_sound": True,
            "reminder_dnd_override": False,
            "timer_work_min": 30,
            "timer_break_min": 15,
            "timer_long_break_min": 30,
            "timer_long_break_every": 4,
            "auto_split_pomodoro": False,
            "default_spotify_url": None,
            "alarms": [],
        }
        payload = {
            **defaults,
            "timer_work_min": 45,
            "timer_break_min": 15,
            "auto_split_pomodoro": True,
            "reminder_dnd_override": True,
            "default_spotify_url": "https://open.spotify.com/playlist/abc123",
            "alarms": [{
                "id": "wake",
                "name": "Wake up",
                "time": "07:30",
                "days": [0, 2, 4],
                "enabled": True,
                "sound": "spotify",
                "spotify_url": "https://open.spotify.com/track/track123",
            }],
        }
        saved = client.put("/api/preferences", json=payload, headers=WRITE)
        assert saved.status_code == 200
        assert saved.json() == payload
        assert client.get("/api/preferences").json() == payload


def test_phase7_rejects_unsafe_spotify_and_bad_alarm(tmp_path: Path) -> None:
    with TestClient(create_app(database=tmp_path / "phase7.db", origin="http://testserver")) as client:
        register(client)
        defaults = client.get("/api/preferences").json()
        assert client.put(
            "/api/preferences",
            json={**defaults, "default_spotify_url": "javascript:alert(1)"},
            headers=WRITE,
        ).status_code == 422
        assert client.put(
            "/api/preferences",
            json={**defaults, "alarms": [{
                "id": "bad", "name": "Bad", "time": "25:00", "days": [0],
                "enabled": True, "sound": "chime",
            }]},
            headers=WRITE,
        ).status_code == 422


def test_focus_and_pomodoro_fields_survive_week_save(tmp_path: Path) -> None:
    block = {
        "id": "essay-focus-1",
        "title": "Essay focus 1/2",
        "kind": "locked",
        "duration_min": 30,
        "days": [0],
        "priority": 3,
        "energy": "medium",
        "start": "16:00",
        "spotify_url": "https://open.spotify.com/album/album123",
        "focus_sessions": 2,
        "focus_minutes": 60,
        "pomodoro_parent_id": "essay",
        "pomodoro_role": "work",
        "pomodoro_index": 1,
    }
    with TestClient(create_app(database=tmp_path / "phase7.db", origin="http://testserver")) as client:
        register(client)
        saved = client.put(
            "/api/week",
            json={"week_start": WEEK, "blocks": [block], "revision": 0},
            headers=WRITE,
        )
        assert saved.status_code == 200
        loaded = client.get(f"/api/week?week_start={WEEK}").json()["blocks"][0]
        assert {key: loaded[key] for key in block} == block
        unsafe = {**block, "spotify_url": "https://evil.example/track/album123"}
        assert client.put(
            "/api/week",
            json={"week_start": WEEK, "blocks": [unsafe], "revision": 1},
            headers=WRITE,
        ).status_code == 422


def test_phase7_preference_migration_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as db:
        db.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
            CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires INTEGER NOT NULL);
            CREATE TABLE weeks (user_id INTEGER NOT NULL, week_start TEXT NOT NULL, blocks TEXT NOT NULL,
                revision INTEGER NOT NULL, PRIMARY KEY (user_id, week_start));
            CREATE TABLE preferences (user_id INTEGER PRIMARY KEY, theme TEXT NOT NULL DEFAULT 'nocturne',
                reminders_enabled INTEGER NOT NULL DEFAULT 0, reminder_lead_min INTEGER NOT NULL DEFAULT 5,
                reminder_sound INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE auth_attempts (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);
            """
        )
    initialize(database)
    initialize(database)
    with sqlite3.connect(database) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(preferences)")}
    assert {"timer_work_min", "alarms_json", "default_spotify_url"} <= columns


def test_spotify_validation_matches_the_browser_exactly() -> None:
    # The two validators must agree. urlsplit lowercases the scheme and host and
    # tolerates a doubled slash, so a value the server accepted but the browser
    # rejected was coerced to null and the next save wiped a link the user had
    # stored. These are the exact forms safeSpotifyUrl in app.js accepts.
    for good in (
        "https://open.spotify.com/track/abc123",
        "https://open.spotify.com/playlist/xyz789/",
        "https://open.spotify.com/episode/aZ09?si=token",
    ):
        assert valid_spotify_url(good) == good

    for bad in (
        "HTTPS://OPEN.SPOTIFY.COM/track/abc123",
        "https://OPEN.spotify.com/track/abc123",
        "https://open.spotify.com//track/abc123",
        "https://open.spotify.com/track/abc 123",
        "https://user:pw@open.spotify.com/track/abc123",
        "https://open.spotify.com:443/track/abc123",
        "https://open.spotify.com/podcast/abc123",
        "http://open.spotify.com/track/abc123",
        "https://evil.example/track/abc123",
    ):
        with pytest.raises(ValueError):
            valid_spotify_url(bad)
