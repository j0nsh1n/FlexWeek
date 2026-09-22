from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import create_app
from backend.availability import DEFAULT_WORK_WINDOWS, OPEN_WORK_WINDOWS
from backend.models import TimeBlock, WeekRequest, WorkWindow
from backend.slots import DAY_END_MIN, DAY_START_MIN, SLOTS_PER_DAY, hhmm_to_slot, minutes_to_hhmm
from backend.solver import solve

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
WEEK = "2026-09-14"


@pytest.fixture()
def app(tmp_path: Path) -> FastAPI:
    return create_app(database=tmp_path / "test.db", origin="http://testserver")


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def alice(client: TestClient) -> TestClient:
    assert (
        client.post(
            "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
        ).status_code
        == 201
    )
    return client


def _flex(**overrides) -> TimeBlock:
    body = {
        "id": "hw",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "medium",
    }
    body.update(overrides)
    return TimeBlock.model_validate(body)


def test_the_day_is_midnight_to_midnight() -> None:
    assert (DAY_START_MIN, DAY_END_MIN, SLOTS_PER_DAY) == (0, 1440, 96)
    assert hhmm_to_slot("00:00") == 0
    assert minutes_to_hhmm(1440) == "24:00"


def test_a_week_saves_a_midnight_start_and_a_block_that_ends_at_24(alice: TestClient) -> None:
    night = {
        "id": "night",
        "title": "Night reading",
        "kind": "locked",
        "duration_min": 60,
        "days": [0],
        "start": "00:00",
        "priority": 1,
        "energy": "low",
    }
    late = {
        "id": "late",
        "title": "Late lab",
        "kind": "locked",
        "duration_min": 60,
        "days": [0],
        "start": "23:00",
        "priority": 1,
        "energy": "low",
    }
    WeekRequest.model_validate({"blocks": [night, late]})
    saved = alice.put(
        "/api/week",
        json={"week_start": WEEK, "blocks": [night, late], "revision": 0},
        headers=WRITE,
    )
    assert saved.status_code == 200, saved.text
    loaded = alice.get(f"/api/week?week_start={WEEK}").json()["blocks"]
    by_id = {block["id"]: block for block in loaded}
    assert (by_id["night"]["start"], by_id["night"]["duration_min"]) == ("00:00", 60)
    assert (by_id["late"]["start"], by_id["late"]["duration_min"]) == ("23:00", 60)


def test_the_planner_places_nothing_outside_work_windows() -> None:
    windows = [WorkWindow(days=[0], start="15:00", end="17:00")]
    trace = solve([_flex(id="hw", duration_min=60, days=[0, 1])], work_windows=windows)
    placed = next(block for block in trace.placed if block.id == "hw")
    assert placed.days == [0]
    assert placed.start == "15:00"
    assert trace.work_windows_defaulted is False
    assert trace.work_windows[0].start == "15:00"


def test_the_planner_leaves_work_unplaced_rather_than_using_the_night() -> None:
    windows = [WorkWindow(days=[0], start="15:00", end="16:00")]
    trace = solve([_flex(id="hw", duration_min=90, days=[0])], work_windows=windows)
    assert [block.id for block in trace.unplaced] == ["hw"]
    assert all(block.id != "hw" or block.start is None for block in trace.unplaced)


def test_no_windows_uses_seven_to_ten_and_says_so() -> None:
    trace = solve([_flex(id="hw", energy="high")])
    placed = next(block for block in trace.placed if block.id == "hw")
    assert placed.start == "07:00"
    assert trace.work_windows_defaulted is True
    assert [window.model_dump() for window in trace.work_windows] == [
        window.model_dump() for window in DEFAULT_WORK_WINDOWS
    ]


def test_a_hand_placed_night_block_is_left_alone() -> None:
    night = _flex(id="hw", start="03:00", days=[0], pinned=True, energy="low")
    other = _flex(id="other", duration_min=30, days=[0], energy="high")
    trace = solve([night, other])
    kept = next(block for block in trace.placed if block.id == "hw")
    assert (kept.start, kept.days, kept.pinned) == ("03:00", [0], True)
    planned = next(block for block in trace.placed if block.id == "other")
    assert planned.start == "07:00"


def test_full_day_windows_can_place_at_midnight() -> None:
    trace = solve([_flex(id="hw", energy="low")], work_windows=OPEN_WORK_WINDOWS)
    placed = next(block for block in trace.placed if block.id == "hw")
    assert placed.start == "17:00"


def test_a_subject_window_does_not_admit_other_homework() -> None:
    windows = [WorkWindow(days=[0], start="15:00", end="17:00", subject="Math")]
    reading = _flex(id="read", course="Reading", days=[0])
    trace = solve([reading], work_windows=windows)
    assert [block.id for block in trace.unplaced] == ["read"]


def test_work_window_end_may_be_midnight() -> None:
    window = WorkWindow(days=[0], start="23:00", end="24:00")
    assert window.end == "24:00"
    with pytest.raises(ValidationError):
        WorkWindow(days=[0], start="23:00", end="23:00")


def test_solve_on_an_old_week_without_stored_windows_still_plans(alice: TestClient) -> None:
    homework = {
        "id": "hw",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "high",
    }
    response = alice.post("/api/solve", json={"blocks": [homework]}, headers=WRITE)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["placed"][0]["start"] == "07:00"
    assert body["work_windows_defaulted"] is True
    assert body["work_windows"][0] == {
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start": "07:00",
        "end": "22:00",
    }


def test_stored_work_windows_round_trip_and_bind_the_planner(alice: TestClient) -> None:
    prefs = alice.get("/api/preferences").json()
    windows = [{"days": [0], "start": "16:00", "end": "18:00"}]
    saved = alice.put("/api/preferences", json={**prefs, "work_windows": windows}, headers=WRITE)
    assert saved.status_code == 200, saved.text
    assert saved.json()["work_windows"] == windows
    homework = {
        "id": "hw",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0, 1],
        "priority": 3,
        "energy": "medium",
    }
    body = alice.post("/api/solve", json={"blocks": [homework]}, headers=WRITE).json()
    assert body["placed"][0]["start"] == "16:00"
    assert body["placed"][0]["days"] == [0]
    assert body["work_windows_defaulted"] is False
