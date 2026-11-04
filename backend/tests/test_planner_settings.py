"""Planner settings through the API. Times are the same counts as the Rust tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
PLANNER_KEYS = (
    "weekend_homework_free",
    "buffer_min",
    "urgent_first",
    "split_long_tasks",
    "show_weekends",
)


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


def save(client: TestClient, **changes: object) -> dict:
    body = client.get("/api/preferences").json()
    saved = client.put("/api/preferences", json={**body, **changes}, headers=WRITE)
    assert saved.status_code == 200, saved.text
    return saved.json()


def block(block_id: str, minutes: int, days: list[int], **extra: object) -> dict:
    return {
        "id": block_id,
        "title": block_id,
        "kind": "flexible",
        "duration_min": minutes,
        "days": days,
        "priority": 3,
        "energy": "medium",
        **extra,
    }


def placed(client: TestClient, blocks: list[dict]) -> dict[str, tuple[int, str, int]]:
    solved = client.post("/api/solve", json={"blocks": blocks}, headers=WRITE)
    assert solved.status_code == 200, solved.text
    found = {}
    for item in solved.json()["placed"]:
        if item["kind"] != "flexible":
            continue
        found[item["id"]] = (item["days"][0], item["start"], item["duration_min"])
    return found


def test_a_fresh_account_omits_planner_settings(alice: TestClient) -> None:
    body = alice.get("/api/preferences").json()
    for key in PLANNER_KEYS:
        assert key not in body
    saved = alice.put("/api/preferences", json=body, headers=WRITE)
    assert saved.status_code == 200, saved.text
    assert saved.json() == body


def test_timer_pacing_stays_separate_from_splitting_a_long_task(alice: TestClient) -> None:
    saved = save(alice, split_long_tasks=True, timer_work_min=25, timer_break_min=5)
    assert saved["split_long_tasks"] is True
    assert saved["timer_work_min"] == 25
    assert saved["auto_split_pomodoro"] is False
    rejected = alice.put(
        "/api/preferences",
        json={**alice.get("/api/preferences").json(), "auto_split_pomodoro": True},
        headers=WRITE,
    )
    assert rejected.status_code == 422


def test_buffer_and_an_unknown_gap_are_checked(alice: TestClient) -> None:
    saved = save(alice, buffer_min=15)
    assert "buffer_min" not in saved
    assert "buffer_min" not in alice.get("/api/preferences").json()
    rejected = alice.put(
        "/api/preferences",
        json={**alice.get("/api/preferences").json(), "buffer_min": 10},
        headers=WRITE,
    )
    assert rejected.status_code == 422


def test_each_planner_setting_moves_the_week(alice: TestClient) -> None:
    friday = [{"days": [4], "start": "16:00", "end": "20:00"}]
    both = friday + [{"days": [5], "start": "10:00", "end": "12:00"}]
    tight = [{"days": [4], "start": "16:00", "end": "18:00"}]
    evening = [{"days": [4], "start": "21:00", "end": "23:00"}]
    morning = [{"days": [5], "start": "10:00", "end": "12:00"}]

    save(alice, work_windows=friday)
    homework = [
        block("class", 60, [4], kind="locked", start="15:00", energy="medium"),
        block("hw", 60, [4]),
    ]
    assert placed(alice, homework)["hw"] == (4, "16:15", 60)
    save(alice, buffer_min=0)
    assert placed(alice, homework)["hw"] == (4, "16:00", 60)
    save(alice, buffer_min=30)
    assert placed(alice, homework)["hw"] == (4, "16:30", 60)
    save(alice, buffer_min=0)

    save(alice, work_windows=both)
    pair = [
        block("science", 60, [4], latest="Friday 18:00"),
        block("math", 60, [4, 5], energy="high"),
    ]
    assert placed(alice, pair) == {
        "science": (4, "16:00", 60),
        "math": (5, "10:00", 60),
    }
    save(alice, weekend_homework_free=True)
    assert placed(alice, pair)["math"] == (4, "17:00", 60)
    save(alice, weekend_homework_free=False)

    save(alice, work_windows=tight)
    urgent = [
        block("a-math", 60, [4], latest="Sunday 20:00"),
        block("b-science", 60, [4], latest="Friday 20:00"),
    ]
    assert placed(alice, urgent)["b-science"] == (4, "16:00", 60)
    save(alice, urgent_first=False)
    assert placed(alice, urgent)["a-math"] == (4, "16:00", 60)
    save(alice, urgent_first=True)

    save(alice, work_windows=both)
    essay = [block("essay", 120, [4, 5])]
    assert placed(alice, essay)["essay"] == (4, "16:00", 120)
    save(alice, split_long_tasks=True)
    parts = placed(alice, essay)
    assert parts["essay"] == (4, "16:00", 60)
    assert parts["essay~2"] == (5, "10:00", 60)
    save(alice, split_long_tasks=False)

    save(alice, work_windows=evening, day_cutoff="22:00")
    assert placed(alice, [block("hw", 60, [4], energy="low")])["hw"] == (4, "21:00", 60)
    save(alice, day_cutoff="21:00")
    missed = alice.post(
        "/api/solve",
        json={"blocks": [block("hw", 60, [4], energy="low")]},
        headers=WRITE,
    )
    assert missed.status_code == 200, missed.text
    assert [item["id"] for item in missed.json()["unplaced"]] == ["hw"]
    save(alice, day_cutoff=None)

    save(alice, work_windows=morning, show_weekends=False)
    assert placed(alice, [block("math", 60, [5], energy="high")])["math"] == (5, "10:00", 60)
    assert alice.get("/api/preferences").json()["show_weekends"] is False


def test_a_new_account_plans_with_a_15_minute_buffer(alice: TestClient) -> None:
    body = alice.get("/api/preferences").json()
    # The dump omits the 15-minute default the way other planner defaults are omitted.
    assert body.get("buffer_min", 15) == 15
    save(alice, work_windows=[{"days": [4], "start": "16:00", "end": "20:00"}])
    homework = [
        block("class", 60, [4], kind="locked", start="15:00", energy="medium"),
        block("hw", 60, [4]),
    ]
    assert placed(alice, homework)["hw"] == (4, "16:15", 60)


def test_choosing_no_buffer_is_saved_and_kept(alice: TestClient) -> None:
    saved = save(alice, buffer_min=0)
    assert saved["buffer_min"] == 0
    assert alice.get("/api/preferences").json()["buffer_min"] == 0


def test_planning_a_spread_that_must_share_a_day_succeeds_and_returns_the_notice(
    alice: TestClient,
) -> None:
    week_start = "2026-09-07"
    body = {
        "id": "essay",
        "title": "History essay",
        "course": None,
        "category": None,
        "priority": 3,
        "energy": "medium",
        "spotify_url": None,
        "due": "2026-09-11T21:00",
        "estimate_min": 90,
        "focus_minutes": 0,
        "focus_sessions": 0,
        "completed": False,
        "completed_at": None,
        "revision": 0,
    }
    saved = alice.put("/api/assignments/essay", json=body, headers=WRITE)
    assert saved.status_code == 200, saved.text
    save(alice, work_windows=[{"days": [2], "start": "16:00", "end": "21:00"}])
    pieces = [
        block(
            "essay-a",
            60,
            [2],
            title="History essay",
            assignment_id="essay",
        ),
        block(
            "essay-b",
            30,
            [2],
            title="History essay",
            assignment_id="essay",
        ),
    ]
    solved = alice.post(
        "/api/solve",
        json={"blocks": pieces, "week_start": week_start},
        headers=WRITE,
    )
    assert solved.status_code == 200, solved.text
    notice = "Couldn't spread History essay over separate days, so two parts share Wednesday."
    notices = solved.json().get("notices") or []
    assert any(item.get("kind") == "spread_same_day" and item.get("message") == notice for item in notices), (
        notices
    )
