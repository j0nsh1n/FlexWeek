"""Running late through the solve API: a preview writes nothing, bad requests are refused, and the moved block is explained."""

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
LATE_MESSAGE = "Moved after you ran late so the rest of the day still fits."


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


def defaults(client: TestClient) -> dict:
    return client.get("/api/preferences").json()


def test_running_late_preview_does_not_write_the_week(alice: TestClient) -> None:
    prefs = defaults(alice)
    windows = [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "06:00", "end": "23:00"}]
    assert (
        # The homework fills the one free hour before a fixed event, so this account chose no gap.
        alice.put(
            "/api/preferences", json={**prefs, "work_windows": windows, "buffer_min": 0}, headers=WRITE
        ).status_code
        == 200
    )
    wind = {
        "id": "wind",
        "title": "Wind-down",
        "kind": "locked",
        "duration_min": 960,
        "days": [0],
        "priority": 1,
        "energy": "medium",
        "start": "07:00",
    }
    homework = {
        "id": "hw",
        "title": "Homework",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "high",
    }
    before = alice.post("/api/solve", json={"blocks": [wind, homework]}, headers=WRITE)
    assert before.status_code == 200, before.text
    assert {block["id"] for block in before.json()["placed"]} >= {"wind", "hw"}
    late = alice.post(
        "/api/solve",
        json={
            "blocks": [wind, homework],
            "running_late": {
                "day": 0,
                "minutes": 60,
                "from_start": "06:00",
                "previous_placed": before.json()["placed"],
            },
        },
        headers=WRITE,
    )
    assert late.status_code == 200, late.text
    body = late.json()
    assert [block["id"] for block in body["unplaced"]] == ["hw"]
    assert next(block for block in body["placed"] if block["id"] == "wind")["start"] == "07:00"
    stored = alice.get(f"/api/week?week_start={WEEK}")
    assert stored.status_code == 200
    assert stored.json() == {"week_start": WEEK, "blocks": [], "revision": 0}


def test_running_late_rejects_recover_together_and_illegal_minutes(alice: TestClient) -> None:
    homework = {
        "id": "hw",
        "title": "Homework",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "medium",
    }
    school = {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "duration_min": 60,
        "days": [0],
        "start": "08:00",
    }
    both = alice.post(
        "/api/solve",
        json={
            "blocks": [school, homework],
            "recover": {"missed_block_id": "school", "missed_day": 0, "previous_placed": []},
            "running_late": {"day": 0, "minutes": 30, "from_start": "14:30", "previous_placed": []},
        },
        headers=WRITE,
    )
    assert both.status_code == 422
    bad_minutes = alice.post(
        "/api/solve",
        json={
            "blocks": [homework],
            "running_late": {"day": 0, "minutes": 45, "from_start": "14:30", "previous_placed": []},
        },
        headers=WRITE,
    )
    assert bad_minutes.status_code == 422


def test_running_late_explanation_uses_the_late_sentence(alice: TestClient) -> None:
    prefs = defaults(alice)
    windows = [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "06:00", "end": "23:00"}]
    assert (
        alice.put("/api/preferences", json={**prefs, "work_windows": windows}, headers=WRITE).status_code
        == 200
    )
    school = {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "duration_min": 390,
        "days": [0],
        "priority": 1,
        "energy": "medium",
        "start": "08:00",
    }
    homework = {
        "id": "hw",
        "title": "Homework",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0, 1],
        "priority": 3,
        "energy": "high",
    }
    before = alice.post("/api/solve", json={"blocks": [school, homework]}, headers=WRITE)
    assert before.status_code == 200, before.text
    late = alice.post(
        "/api/solve",
        json={
            "blocks": [school, homework],
            "running_late": {
                "day": 0,
                "minutes": 30,
                "from_start": "06:00",
                "previous_placed": before.json()["placed"],
            },
        },
        headers=WRITE,
    )
    assert late.status_code == 200, late.text
    move = next(item for item in late.json()["moves"] if item["reason"] == "RESHUFFLE_AFTER_MISS")
    assert move["block_id"] == "hw"
    assert move["from_start"] == "06:00"
    assert move["to_start"] == "06:30"
    message = next(
        item["message"]
        for item in late.json()["explanations"]
        if item["block_id"] == "hw" and item["reason"] == "RESHUFFLE_AFTER_MISS"
    )
    assert message == LATE_MESSAGE
