"""Availability preferences through the API: work and study hours, protected time and the day cutoff stay on the 15-minute grid and keep their saved shape."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import Preferences, create_app
from backend.models import StudyWindow

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


def assignment(**overrides) -> dict:
    body = {
        "id": "hw-essay",
        "title": "Essay",
        "course": "History",
        "category": None,
        "priority": 2,
        "energy": "low",
        "spotify_url": None,
        "due": "2026-09-15T23:59",
        "estimate_min": 120,
        "focus_minutes": 0,
        "focus_sessions": 0,
        "completed": False,
        "completed_at": None,
        "revision": 0,
    }
    body.update(overrides)
    return body


def defaults(client: TestClient) -> dict:
    return client.get("/api/preferences").json()


def test_preferences_reject_off_grid_windows_and_solve_honors_cutoff(alice: TestClient) -> None:
    prefs = defaults(alice)
    bad = alice.put(
        "/api/preferences",
        json={
            **prefs,
            "protected": [{"kind": "downtime", "days": [0], "start": "06:07", "duration_min": 60}],
        },
        headers=WRITE,
    )
    assert bad.status_code == 422
    saved = alice.put(
        "/api/preferences",
        json={**prefs, "day_cutoff": "06:15"},
        headers=WRITE,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["day_cutoff"] == "06:15"
    assert alice.get("/api/preferences").json()["day_cutoff"] == "06:15"
    homework = {
        "id": "hw",
        "title": "Homework",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "high",
    }
    solved = alice.post("/api/solve", json={"blocks": [homework]}, headers=WRITE)
    assert solved.status_code == 200, solved.text
    placed = next(block for block in solved.json()["placed"] if block["id"] == "hw")
    hour, minute = map(int, placed["start"].split(":"))
    assert hour * 60 + minute + int(placed["duration_min"]) <= 6 * 60 + 15


def test_estimates_and_the_planners_windows_stay_on_the_quarter_hour(alice: TestClient) -> None:
    """Blocks take any minute; what the planner works in does not. Each of these is one minute or
    five off a quarter hour, and each is refused."""
    assert (
        alice.put("/api/assignments/hw-essay", json=assignment(estimate_min=50), headers=WRITE).status_code
        == 422
    )
    prefs = defaults(alice)
    off: list[dict] = [
        {"work_windows": [{"days": [0], "start": "17:05", "end": "19:00"}]},
        {"work_windows": [{"days": [0], "start": "17:00", "end": "19:10"}]},
        {"study_windows": [{"days": [0], "start": "17:05", "duration_min": 60}]},
        {"study_windows": [{"days": [0], "start": "17:00", "duration_min": 50}]},
        {"protected": [{"kind": "meal", "days": [0], "start": "18:05", "duration_min": 30}]},
        {"day_cutoff": "21:05"},
        {"auto_split_pomodoro": True, "timer_work_min": 25},
    ]
    for change in off:
        assert alice.put("/api/preferences", json={**prefs, **change}, headers=WRITE).status_code == 422, (
            change
        )
    assert alice.put("/api/assignments/hw-essay", json=assignment(), headers=WRITE).status_code == 200
    spread = alice.post(
        "/api/assignments/hw-essay/spread",
        json={"session_min": 50, "from_date": "2026-09-14"},
        headers=WRITE,
    )
    assert spread.status_code == 422


def test_preferred_study_hours_saved_by_an_older_build_open_as_study_hours(
    alice: TestClient, database: Path
) -> None:
    """A preferences row from an older build, with planning hours and preferred study hours apart,
    opens as one Study hours list, the planner reads that list, and the next save writes it alone."""
    old = {
        "work_windows": [{"days": [0, 1, 2, 3, 4], "start": "16:00", "end": "21:00"}],
        "study_windows": [{"days": [5, 6], "start": "10:00", "duration_min": 120}],
    }
    with sqlite3.connect(database) as db:
        db.execute("UPDATE preferences SET availability_json = ?", (json.dumps(old),))
    prefs = alice.get("/api/preferences").json()
    assert "study_windows" not in prefs
    hours = [
        {"days": [0, 1, 2, 3, 4], "start": "16:00", "end": "21:00"},
        {"days": [5, 6], "start": "10:00", "end": "12:00"},
    ]
    assert prefs["work_windows"] == hours
    # Saturday has no other hours, so homework there goes in the carried window or nowhere.
    homework = {
        "id": "hw",
        "title": "Homework",
        "kind": "flexible",
        "duration_min": 60,
        "days": [5],
        "priority": 3,
        "energy": "low",
    }
    solved = alice.post("/api/solve", json={"blocks": [homework]}, headers=WRITE)
    assert solved.status_code == 200, solved.text
    assert next(block for block in solved.json()["placed"] if block["id"] == "hw")["start"] == "10:00"
    assert alice.put("/api/preferences", json=prefs, headers=WRITE).status_code == 200
    with sqlite3.connect(database) as db:
        (stored,) = db.execute("SELECT availability_json FROM preferences").fetchone()
    assert json.loads(stored)["work_windows"] == hours
    assert "study_windows" not in json.loads(stored)


def test_an_older_client_sending_preferred_study_hours_saves_them_as_study_hours(
    alice: TestClient,
) -> None:
    prefs = defaults(alice)
    preferred = [{"days": [2], "start": "19:00", "duration_min": 90, "subject": "Math"}]
    saved = alice.put("/api/preferences", json={**prefs, "study_windows": preferred}, headers=WRITE)
    assert saved.status_code == 200, saved.text
    assert "study_windows" not in saved.json()
    assert saved.json()["work_windows"] == [
        {"days": [2], "start": "19:00", "end": "20:30", "subject": "Math"}
    ]
    assert alice.get("/api/preferences").json()["work_windows"] == saved.json()["work_windows"]


def test_protected_time_keeps_an_optional_name(alice: TestClient, database: Path) -> None:
    prefs = defaults(alice)
    piano = {"kind": "downtime", "days": [1, 3], "start": "17:00", "duration_min": 90}
    saved = alice.put(
        "/api/preferences",
        json={**prefs, "protected": [{**piano, "title": "  Piano "}, {**piano, "days": [5], "title": " "}]},
        headers=WRITE,
    )
    assert saved.status_code == 200, saved.text
    named, blank = saved.json()["protected"]
    assert named["title"] == "Piano", "trimmed"
    assert "title" not in blank, "a blank name is no name"
    assert alice.get("/api/preferences").json()["protected"] == saved.json()["protected"]
    too_long = {**piano, "title": "x" * 41}
    assert (
        alice.put("/api/preferences", json={**prefs, "protected": [too_long]}, headers=WRITE).status_code
        == 422
    )
    # A row saved before names existed still opens, without one.
    with sqlite3.connect(database) as db:
        db.execute("UPDATE preferences SET availability_json = ?", (json.dumps({"protected": [piano]}),))
    assert alice.get("/api/preferences").json()["protected"] == [piano]


def test_preferences_reject_overlapping_protected_windows_and_accept_adjacent_ones(
    alice: TestClient,
) -> None:
    prefs = defaults(alice)
    overlapping = alice.put(
        "/api/preferences",
        json={
            **prefs,
            "protected": [
                {"kind": "downtime", "days": [0], "start": "18:00", "duration_min": 60},
                {"kind": "meal", "days": [0], "start": "18:30", "duration_min": 60},
            ],
        },
        headers=WRITE,
    )
    assert overlapping.status_code == 422
    adjacent = alice.put(
        "/api/preferences",
        json={
            **prefs,
            "protected": [
                {"kind": "downtime", "days": [0], "start": "18:00", "duration_min": 60},
                {"kind": "meal", "days": [0], "start": "19:00", "duration_min": 60},
            ],
        },
        headers=WRITE,
    )
    assert adjacent.status_code == 200, adjacent.text
    same_time_other_day = alice.put(
        "/api/preferences",
        json={
            **prefs,
            "protected": [
                {"kind": "downtime", "days": [0], "start": "18:00", "duration_min": 120},
                {"kind": "meal", "days": [1], "start": "19:00", "duration_min": 60},
            ],
        },
        headers=WRITE,
    )
    assert same_time_other_day.status_code == 200, same_time_other_day.text


def test_protected_window_model_rejects_overlap_and_accepts_adjacency() -> None:
    base = {"theme": "system"}
    with pytest.raises(ValidationError):
        Preferences.model_validate(
            {
                **base,
                "protected": [
                    {"kind": "downtime", "days": [0], "start": "18:00", "duration_min": 60},
                    {"kind": "meal", "days": [0], "start": "18:30", "duration_min": 60},
                ],
            }
        )
    adjacent = Preferences.model_validate(
        {
            **base,
            "protected": [
                {"kind": "downtime", "days": [0], "start": "18:00", "duration_min": 60},
                {"kind": "meal", "days": [0], "start": "19:00", "duration_min": 60},
            ],
        }
    )
    assert len(adjacent.protected) == 2


@pytest.mark.parametrize("subject", ["   ", "x" * 41])
def test_a_subject_must_be_a_real_name(subject: str) -> None:
    with pytest.raises(ValueError):
        StudyWindow(days=[0], start="15:30", duration_min=60, subject=subject)
