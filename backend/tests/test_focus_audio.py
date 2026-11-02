"""Focus audio is a comfort preference on this computer. Off is omitted. The other values round-trip."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    return tmp_path / "focus-audio.db"


@pytest.fixture()
def app(database: Path) -> FastAPI:
    return create_app(database=database, origin="http://testserver")


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def alice(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
    )
    assert response.status_code == 201, response.text
    return client


def defaults() -> dict:
    return {
        "theme": "system",
        "reminders_enabled": True,
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


def test_off_is_omitted_and_a_choice_comes_back(alice: TestClient, database: Path) -> None:
    fresh = alice.get("/api/preferences")
    assert fresh.status_code == 200
    assert "focus_audio" not in fresh.json()

    refused = alice.put("/api/preferences", json={**defaults(), "focus_audio": "vinyl"}, headers=WRITE)
    assert refused.status_code == 422

    saved = alice.put("/api/preferences", json={**defaults(), "focus_audio": "spotify"}, headers=WRITE)
    assert saved.status_code == 200, saved.text
    assert saved.json()["focus_audio"] == "spotify"
    assert alice.get("/api/preferences").json()["focus_audio"] == "spotify"

    comfort = sqlite3.connect(database).execute("SELECT comfort_json FROM preferences").fetchone()
    assert comfort is not None
    assert '"focus_audio":"spotify"' in comfort[0]

    quiet = alice.put("/api/preferences", json={**defaults(), "focus_audio": "off"}, headers=WRITE)
    assert quiet.status_code == 200, quiet.text
    assert "focus_audio" not in quiet.json()
    assert "focus_audio" not in alice.get("/api/preferences").json()


@pytest.mark.parametrize("sound", ["rain", "lo-fi", "white-noise"])
def test_each_ambient_sound_round_trips(alice: TestClient, sound: str) -> None:
    saved = alice.put("/api/preferences", json={**defaults(), "focus_audio": sound}, headers=WRITE)
    assert saved.status_code == 200, saved.text
    assert saved.json()["focus_audio"] == sound
    assert alice.get("/api/preferences").json()["focus_audio"] == sound


def test_the_two_focus_rules_default_to_mute_on_and_complete_off_and_round_trip(
    alice: TestClient, database: Path
) -> None:
    fresh = alice.get("/api/preferences").json()
    assert "focus_auto_mute" not in fresh and "focus_auto_complete" not in fresh  # defaults are omitted

    saved = alice.put(
        "/api/preferences",
        json={**defaults(), "focus_auto_mute": False, "focus_auto_complete": True},
        headers=WRITE,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["focus_auto_mute"] is False
    assert saved.json()["focus_auto_complete"] is True
    again = alice.get("/api/preferences").json()
    assert again["focus_auto_mute"] is False and again["focus_auto_complete"] is True
    comfort = sqlite3.connect(database).execute("SELECT comfort_json FROM preferences").fetchone()
    assert comfort is not None
    assert '"focus_auto_mute":false' in comfort[0] and '"focus_auto_complete":true' in comfort[0]

    back = alice.put("/api/preferences", json={**defaults()}, headers=WRITE)
    assert back.status_code == 200, back.text
    assert "focus_auto_mute" not in back.json() and "focus_auto_complete" not in back.json()
    refused = alice.put("/api/preferences", json={**defaults(), "focus_auto_mute": "maybe"}, headers=WRITE)
    assert refused.status_code == 422
