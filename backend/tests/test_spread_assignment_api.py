"""Spreading an assignment over several days: the preview writes nothing and belongs to one account's open assignment."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
WEEK = "2026-09-14"


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


def register(client: TestClient, username: str) -> None:
    assert (
        client.post(
            "/api/auth/register", json={"username": username, "password": PASSWORD}, headers=WRITE
        ).status_code
        == 201
    )


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


def test_spread_preview_does_not_write_and_stays_on_one_assignment(alice: TestClient) -> None:
    saved = alice.put("/api/assignments/hw-essay", json=assignment(), headers=WRITE)
    assert saved.status_code == 200, saved.text
    preview = alice.post(
        "/api/assignments/hw-essay/spread",
        json={"session_min": 60, "from_date": "2026-09-14"},
        headers=WRITE,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json() == {
        "assignment_id": "hw-essay",
        "session_min": 60,
        "remaining_min": 0,
        "sessions": [
            {"week_start": "2026-09-14", "date": "2026-09-14", "days": [0], "duration_min": 60},
            {"week_start": "2026-09-14", "date": "2026-09-15", "days": [1], "duration_min": 60},
        ],
    }
    listed = alice.get(f"/api/assignments?week_start={WEEK}").json()["assignments"]
    assert listed[0]["id"] == "hw-essay"
    assert "pomodoro_parent_id" not in listed[0]
    week = alice.get(f"/api/week?week_start={WEEK}").json()
    assert week == {"week_start": WEEK, "blocks": [], "revision": 0}


def test_spread_on_another_account_is_404(app: FastAPI, alice: TestClient) -> None:
    assert alice.put("/api/assignments/hw-essay", json=assignment(), headers=WRITE).status_code == 200
    with TestClient(app) as bob:
        register(bob, "bob")
        stolen = bob.post(
            "/api/assignments/hw-essay/spread",
            json={"session_min": 60, "from_date": "2026-09-14"},
            headers=WRITE,
        )
        assert stolen.status_code == 404


def test_spread_rejects_a_completed_assignment(alice: TestClient) -> None:
    body = assignment(completed=True, completed_at="2026-09-14T16:00")
    assert alice.put("/api/assignments/hw-essay", json=body, headers=WRITE).status_code == 200
    response = alice.post(
        "/api/assignments/hw-essay/spread",
        json={"session_min": 60, "from_date": "2026-09-14"},
        headers=WRITE,
    )
    assert response.status_code == 422


def test_spread_leaves_the_day_of_a_placed_session_for_last(alice: TestClient) -> None:
    # 120 minutes due Tuesday 2026-09-15 with a 30 minute session already timed on Monday: 90 are
    # uncovered, as shares of 60 and 30. Monday and Tuesday are the only days, so the 60 takes Tuesday
    # (no session there) and the 30 takes Monday, the held day, once Tuesday has its share.
    assert alice.put("/api/assignments/hw-essay", json=assignment(), headers=WRITE).status_code == 200
    placed = {
        "id": "hw-essay-held",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 30,
        "days": [0],
        "start": "16:00",
        "priority": 2,
        "energy": "low",
        "assignment_id": "hw-essay",
    }
    saved = alice.put(
        "/api/week", json={"week_start": WEEK, "blocks": [placed], "revision": 0}, headers=WRITE
    )
    assert saved.status_code == 200, saved.text
    preview = alice.post(
        "/api/assignments/hw-essay/spread",
        json={"session_min": 60, "from_date": "2026-09-14"},
        headers=WRITE,
    )
    assert preview.status_code == 200, preview.text
    shares = [(item["date"], item["duration_min"]) for item in preview.json()["sessions"]]
    assert shares == [("2026-09-15", 60), ("2026-09-14", 30)]


def test_spread_gives_a_free_day_the_share_before_a_day_with_a_placed_session(
    alice: TestClient,
) -> None:
    # Due Wednesday: three days. The held session is on Monday, so the two shares take Tuesday and
    # Wednesday, not Monday and Tuesday.
    body = assignment(due="2026-09-16T23:59", estimate_min=150)
    assert alice.put("/api/assignments/hw-essay", json=body, headers=WRITE).status_code == 200
    placed = {
        "id": "hw-essay-held",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 30,
        "days": [0],
        "start": "16:00",
        "priority": 2,
        "energy": "low",
        "assignment_id": "hw-essay",
    }
    saved = alice.put(
        "/api/week", json={"week_start": WEEK, "blocks": [placed], "revision": 0}, headers=WRITE
    )
    assert saved.status_code == 200, saved.text
    preview = alice.post(
        "/api/assignments/hw-essay/spread",
        json={"session_min": 60, "from_date": "2026-09-14"},
        headers=WRITE,
    )
    shares = [(item["date"], item["duration_min"]) for item in preview.json()["sessions"]]
    assert shares == [("2026-09-15", 60), ("2026-09-16", 60)]
