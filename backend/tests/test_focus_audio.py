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


def test_a_later_sound_is_stored_until_it_can_play(alice: TestClient) -> None:
    saved = alice.put("/api/preferences", json={**defaults(), "focus_audio": "rain"}, headers=WRITE)
    assert saved.status_code == 200, saved.text
    assert saved.json()["focus_audio"] == "rain"
    assert alice.get("/api/preferences").json()["focus_audio"] == "rain"
