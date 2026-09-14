"""GET /api/day from docs/stage2-contract.md. Expected minutes are from the 06:00-23:00 grid, not a recorded run."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
DAY = "2026-09-15"
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


def assignment(assignment_id: str = "hw-essay", **overrides) -> dict:
    body = {
        "id": assignment_id,
        "title": "Essay",
        "course": None,
        "category": "Homework",
        "priority": 3,
        "energy": "medium",
        "spotify_url": None,
        "due": "2026-09-16T23:59",
        "estimate_min": 120,
        "focus_minutes": 0,
        "focus_sessions": 0,
        "completed": False,
        "completed_at": None,
        "revision": 0,
    }
    body.update(overrides)
    return body


def school() -> dict:
    return {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "duration_min": 390,
        "days": [0, 1, 2, 3, 4],
        "priority": 1,
        "energy": "medium",
        "start": "08:00",
        "category": "School",
    }


def session(block_id: str, assignment_id: str = "hw-essay", **overrides) -> dict:
    block = {
        "id": block_id,
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [1],
        "priority": 3,
        "energy": "medium",
        "assignment_id": assignment_id,
        "category": "Homework",
    }
    block.update(overrides)
    return block


def save_week(client: TestClient, blocks: list[dict], revision: int = 0):
    return client.put(
        "/api/week", json={"week_start": WEEK, "blocks": blocks, "revision": revision}, headers=WRITE
    )


def put_assignment(client: TestClient, body: dict):
    return client.put(f"/api/assignments/{body['id']}", json=body, headers=WRITE)


def get_day(client: TestClient, day: str = DAY):
    return client.get(f"/api/day?date={day}")


def test_empty_day_is_add_with_seventeen_free_hours(alice: TestClient) -> None:
    response = get_day(alice)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "date": DAY,
        "week_start": WEEK,
        "due_soon": [],
        "sessions": [],
        "locked": [],
        "next_action": {"kind": "add"},
        "workload": {
            "scheduled_min": 0,
            "focus_min": 0,
            "available_min": 1020,
            "by_category": [],
        },
    }


def test_school_and_a_finished_session_leave_570_minutes_free(alice: TestClient) -> None:
    assert put_assignment(
        alice, assignment(completed=True, completed_at="2026-09-15T17:00")
    ).status_code == 200
    done = session("w1", start="16:00", completed=True, completed_day=1)
    saved = save_week(alice, [school(), done])
    assert saved.status_code == 200, saved.text
    body = get_day(alice).json()
    assert body["next_action"] == {"kind": "add"}
    assert body["workload"]["scheduled_min"] == 450
    assert body["workload"]["focus_min"] == 60
    assert body["workload"]["available_min"] == 570
    assert body["workload"]["by_category"] == [
        {"category": "School", "scheduled_min": 390, "focus_min": 0},
        {"category": "Homework", "scheduled_min": 60, "focus_min": 60},
    ]
    assert [block["id"] for block in body["locked"]] == ["school"]
    assert [block["id"] for block in body["sessions"]] == ["w1"]
    assert body["sessions"][0]["start"] == "16:00"
    assert body["sessions"][0]["completed"] is True


def test_due_tomorrow_is_plan_and_due_in_three_days_is_not(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    assert put_assignment(alice, assignment("later", title="Later", due="2026-09-18T12:00")).status_code == 200
    body = get_day(alice).json()
    assert [item["id"] for item in body["due_soon"]] == ["hw-essay"]
    assert body["due_soon"][0]["due"] == "2026-09-16T23:59"
    assert body["due_soon"][0]["planned_min"] == 0
    assert body["due_soon"][0]["unplanned_min"] == 120
    assert body["next_action"] == {"kind": "plan", "assignment_id": "hw-essay"}


def test_a_placed_unfinished_session_is_start(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    placed = session("w1", start="16:00")
    assert save_week(alice, [placed]).status_code == 200
    body = get_day(alice).json()
    assert body["next_action"] == {"kind": "start", "block_id": "w1"}
    assert body["sessions"][0]["start"] == "16:00"
    assert body["workload"]["scheduled_min"] == 60
    assert body["workload"]["focus_min"] == 0
    assert body["workload"]["available_min"] == 960


def test_overdue_open_homework_is_due_soon(alice: TestClient) -> None:
    assert put_assignment(alice, assignment(due="2026-09-14T12:00")).status_code == 200
    body = get_day(alice).json()
    assert [item["id"] for item in body["due_soon"]] == ["hw-essay"]
    assert body["next_action"] == {"kind": "plan", "assignment_id": "hw-essay"}


def test_day_rejects_a_malformed_date(alice: TestClient) -> None:
    assert alice.get("/api/day").status_code == 422
    assert alice.get("/api/day?date=2026-09-15T00:00").status_code == 422
    assert alice.get("/api/day?date=1999-12-31").status_code == 422


def test_day_requires_a_session(client: TestClient) -> None:
    assert client.get(f"/api/day?date={DAY}").status_code == 401


def test_day_does_not_show_another_accounts_week(app: FastAPI, alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    assert save_week(alice, [school()]).status_code == 200
    with TestClient(app) as bob:
        assert (
            bob.post(
                "/api/auth/register", json={"username": "bob", "password": PASSWORD}, headers=WRITE
            ).status_code
            == 201
        )
        body = get_day(bob).json()
        assert body["locked"] == []
        assert body["sessions"] == []
        assert body["due_soon"] == []
        assert body["workload"]["scheduled_min"] == 0
        assert body["next_action"] == {"kind": "add"}
