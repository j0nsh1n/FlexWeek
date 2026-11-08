"""Preferences a student sets: theme, reminders, the focus timer, alarms and the Spotify link, and the old databases they upgrade."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.models import valid_spotify_url
from backend.storage import initialize
from backend.tests.account_support import PASSWORD, WRITE, preferences

TIMER_DEFAULTS: dict[str, object] = {
    "reminder_dnd_override": False,
    "timer_work_min": 30,
    "timer_break_min": 15,
    "timer_long_break_min": 30,
    "timer_long_break_every": 4,
    "auto_split_pomodoro": False,
    "default_spotify_url": None,
    "alarms": [],
}


def make_client(tmp_path: Path, name: str = "prefs.db") -> TestClient:
    return TestClient(create_app(database=tmp_path / name, origin="http://testserver"))


def register(client: TestClient, username: str = "alice") -> TestClient:
    response = client.post(
        "/api/auth/register", json={"username": username, "password": PASSWORD}, headers=WRITE
    )
    assert response.status_code == 201
    return client


def test_a_new_account_has_the_default_preferences(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        register(client)
        assert client.get("/api/preferences").json() == {
            "theme": "system",
            "reminders_enabled": True,
            "reminder_lead_min": 5,
            "reminder_sound": True,
            **TIMER_DEFAULTS,
        }


def test_reminder_choices_are_kept_and_a_lead_time_over_two_hours_is_refused(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        register(client)
        payload = {
            "theme": "slate",
            "reminders_enabled": False,
            "reminder_lead_min": 15,
            "reminder_sound": False,
            **TIMER_DEFAULTS,
        }
        assert client.put("/api/preferences", json=payload, headers=WRITE).status_code == 200
        assert client.get("/api/preferences").json() == payload
        assert (
            client.put(
                "/api/preferences", json={**payload, "reminder_lead_min": 121}, headers=WRITE
            ).status_code
            == 422
        )


def test_the_theme_starts_as_system_and_only_system_slate_or_nocturne_are_kept(tmp_path: Path) -> None:
    with make_client(tmp_path) as alice:
        register(alice)
        assert alice.get("/api/preferences").json()["theme"] == "system"
        for theme in ("slate", "nocturne", "system"):
            assert alice.put("/api/preferences", json=preferences(theme), headers=WRITE).status_code == 200
            assert alice.get("/api/preferences").json()["theme"] == theme
        for label in ("light", "dark", ""):
            assert alice.put("/api/preferences", json=preferences(label), headers=WRITE).status_code == 422


def test_timer_alarm_and_spotify_choices_round_trip(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        register(client)
        defaults = client.get("/api/preferences").json()
        assert defaults == preferences()
        payload = {
            **defaults,
            "timer_work_min": 45,
            "timer_break_min": 15,
            "auto_split_pomodoro": True,
            "reminder_dnd_override": True,
            "default_spotify_url": "https://open.spotify.com/playlist/abc123",
            "alarms": [
                {
                    "id": "wake",
                    "name": "Wake up",
                    "time": "07:30",
                    "days": [0, 2, 4],
                    "enabled": True,
                    "sound": "spotify",
                    "spotify_url": "https://open.spotify.com/track/track123",
                }
            ],
        }
        saved = client.put("/api/preferences", json=payload, headers=WRITE)
        assert saved.status_code == 200
        assert saved.json() == payload
        assert client.get("/api/preferences").json() == payload


def test_a_non_spotify_link_or_an_alarm_at_25_00_is_refused(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        register(client)
        defaults = client.get("/api/preferences").json()
        assert (
            client.put(
                "/api/preferences",
                json={**defaults, "default_spotify_url": "javascript:alert(1)"},
                headers=WRITE,
            ).status_code
            == 422
        )
        bad_alarm = {
            "id": "bad",
            "name": "Bad",
            "time": "25:00",
            "days": [0],
            "enabled": True,
            "sound": "chime",
        }
        assert (
            client.put(
                "/api/preferences", json={**defaults, "alarms": [bad_alarm]}, headers=WRITE
            ).status_code
            == 422
        )


def test_a_spotify_link_is_accepted_exactly_when_the_browser_accepts_it() -> None:
    # The server and the browser must agree. urlsplit lowercases the scheme and host and
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


def test_a_database_from_before_reminders_gains_them_turned_on(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as conn:
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
    initialize(database)
    with TestClient(create_app(database=database, origin="http://testserver")) as client:
        register(client, "migrated")
        prefs = client.get("/api/preferences").json()
        assert prefs["reminders_enabled"] is True
        assert prefs["reminder_lead_min"] == 5
        assert prefs["reminder_sound"] is True


def test_upgrading_a_database_twice_adds_the_timer_and_alarm_columns_once(tmp_path: Path) -> None:
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
