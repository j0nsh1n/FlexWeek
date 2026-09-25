"""Stage 5 authenticated API: comfort prefs, split preview, presets and limits."""

from __future__ import annotations

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
    return tmp_path / "test.db"


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


def test_new_account_preferences_omit_comfort_defaults(alice: TestClient) -> None:
    assert alice.get("/api/preferences").json() == defaults()


def test_comfort_fields_round_trip_and_reject_out_of_range(alice: TestClient) -> None:
    payload = {
        **defaults(),
        "alert_volume": 40,
        "end_chime": True,
        "tray_notifications": False,
        "start_at_login": True,
        "preferred_view": "day",
        "sidebar_collapsed": True,
        "sidebar_width_px": 280,
    }
    saved = alice.put("/api/preferences", json=payload, headers=WRITE)
    assert saved.status_code == 200, saved.text
    assert saved.json() == payload
    assert alice.get("/api/preferences").json() == payload
    restored = alice.put("/api/preferences", json=defaults(), headers=WRITE)
    assert restored.status_code == 200, restored.text
    assert restored.json() == defaults()
    assert (
        alice.put("/api/preferences", json={**defaults(), "alert_volume": 101}, headers=WRITE).status_code
        == 422
    )
    assert (
        alice.put("/api/preferences", json={**defaults(), "sidebar_width_px": 50}, headers=WRITE).status_code
        == 422
    )


def test_auto_split_rejects_a_25_minute_work_length(alice: TestClient) -> None:
    rejected = alice.put(
        "/api/preferences",
        json={**defaults(), "timer_work_min": 25, "auto_split_pomodoro": True},
        headers=WRITE,
    )
    assert rejected.status_code == 422
    saved = alice.put(
        "/api/preferences",
        json={**defaults(), "timer_work_min": 45, "auto_split_pomodoro": True},
        headers=WRITE,
    )
    assert saved.status_code == 200, saved.text
    loaded = alice.get("/api/preferences").json()
    assert loaded["timer_work_min"] == 45
    assert loaded["auto_split_pomodoro"] is True


def test_timer_split_preview_snaps_and_plans_a_90_minute_task(alice: TestClient) -> None:
    response = alice.post(
        "/api/timer-split-preview",
        json={
            "duration_min": 90,
            "timer_work_min": 25,
            "timer_break_min": 5,
            "timer_long_break_min": 15,
            "timer_long_break_every": 4,
        },
        headers=WRITE,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "timer_work_min": 30,
        "timer_break_min": 15,
        "timer_long_break_min": 15,
        "timer_long_break_every": 4,
        "rounded": True,
        "message": (
            "Work length 25 minutes becomes 30 on the 15-minute grid. "
            "Break length 5 minutes becomes 15 on the 15-minute grid."
        ),
        "segments": [
            {"role": "work", "duration_min": 30, "index": 1},
            {"role": "break", "duration_min": 15, "index": 1},
            {"role": "work", "duration_min": 30, "index": 2},
            {"role": "break", "duration_min": 15, "index": 2},
            {"role": "work", "duration_min": 30, "index": 3},
        ],
        "total_min": 120,
    }
    unchanged = alice.get("/api/preferences").json()
    assert unchanged["timer_work_min"] == 30
    assert "alert_volume" not in unchanged


def test_timer_presets_and_reminder_limits_match_the_contract(alice: TestClient) -> None:
    presets = alice.get("/api/timer-presets")
    assert presets.status_code == 200, presets.text
    assert presets.json() == {
        "presets": [
            {
                "id": "short",
                "label": "Short",
                "timer_work_min": 15,
                "timer_break_min": 15,
                "timer_long_break_min": 30,
                "timer_long_break_every": 4,
            },
            {
                "id": "standard",
                "label": "Standard",
                "timer_work_min": 30,
                "timer_break_min": 15,
                "timer_long_break_min": 30,
                "timer_long_break_every": 4,
            },
            {
                "id": "long",
                "label": "Long",
                "timer_work_min": 45,
                "timer_break_min": 15,
                "timer_long_break_min": 30,
                "timer_long_break_every": 4,
            },
        ]
    }
    limits = alice.get("/api/reminder-limits")
    assert limits.status_code == 200, limits.text
    assert limits.json() == {
        "web_open": "Reminders fire in this browser only while FlexWeek is open in a tab.",
        "desktop_background": "The desktop app can still alert from the tray after the window is closed.",
        "spotify": "A Spotify link is best-effort. FlexWeek plays a built-in sound if the track does not play.",
        "duplicate": "The same block start fires at most one reminder until it is handled or the day changes.",
    }


def test_comfort_routes_require_a_session(client: TestClient) -> None:
    assert client.get("/api/timer-presets").status_code == 401
    assert client.get("/api/reminder-limits").status_code == 401
    assert (
        client.post(
            "/api/timer-split-preview",
            json={
                "timer_work_min": 30,
                "timer_break_min": 15,
                "timer_long_break_min": 30,
                "timer_long_break_every": 4,
            },
            headers=WRITE,
        ).status_code
        == 401
    )
