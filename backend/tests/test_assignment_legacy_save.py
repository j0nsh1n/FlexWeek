"""Old weekday latest on PUT /api/week. Expected dues are from the calendar, not a recorded run."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
WEEK = "2026-09-07"
AID = "a-4c3275a3fa104726ed3f39fbfb7dcdbf"


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(database=tmp_path / "test.db", origin="http://testserver")
    with TestClient(app) as test_client:
        assert (
            test_client.post(
                "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
            ).status_code
            == 201
        )
        yield test_client


def flex_with_latest(**overrides) -> dict:
    block = {
        "id": "essay",
        "title": "Draft title",
        "kind": "flexible",
        "duration_min": 90,
        "days": [0, 1, 2, 3, 4],
        "priority": 2,
        "energy": "low",
        "course": "History",
        "latest": "Thursday 21:00",
    }
    block.update(overrides)
    return block


def save(client: TestClient, blocks: list[dict], revision: int):
    return client.put(
        "/api/week", json={"week_start": WEEK, "blocks": blocks, "revision": revision}, headers=WRITE
    )


def test_weekday_latest_creates_the_assignment_if_missing_and_stores_a_session(client: TestClient) -> None:
    response = save(client, [flex_with_latest()], 0)
    assert response.status_code == 200, response.text
    session = {
        "id": "essay",
        "title": "Draft title",
        "kind": "flexible",
        "duration_min": 90,
        "days": [0, 1, 2, 3, 4],
        "priority": 2,
        "energy": "low",
        "earliest": None,
        "latest": None,
        "start": None,
        "course": "History",
        "assignment_id": AID,
    }
    assert response.json() == {"week_start": WEEK, "blocks": [session], "revision": 1}
    listed = client.get(f"/api/assignments?week_start={WEEK}")
    assert listed.json() == {
        "assignments": [
            {
                "id": AID,
                "title": "Draft title",
                "course": "History",
                "category": None,
                "priority": 2,
                "energy": "low",
                "spotify_url": None,
                "due": "2026-09-10T21:00",
                "estimate_min": 90,
                "focus_minutes": 0,
                "focus_sessions": 0,
                "completed": False,
                "completed_at": None,
                "revision": 1,
                "planned_min": 90,
                "unplanned_min": 0,
            }
        ]
    }


def test_a_later_latest_save_does_not_change_an_existing_assignment(client: TestClient) -> None:
    assert save(client, [flex_with_latest()], 0).status_code == 200
    again = save(client, [flex_with_latest(title="Changed on the block", duration_min=45)], 1)
    assert again.status_code == 200, again.text
    assert again.json()["blocks"][0]["title"] == "Draft title"
    assert again.json()["blocks"][0]["duration_min"] == 45
    assert again.json()["blocks"][0]["assignment_id"] == AID
    body = client.get(f"/api/assignments?week_start={WEEK}").json()["assignments"][0]
    assert body["title"] == "Draft title"
    assert body["estimate_min"] == 90
    assert body["due"] == "2026-09-10T21:00"
    assert body["revision"] == 1


def test_a_stale_latest_save_leaves_no_new_assignment(client: TestClient) -> None:
    school = {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "duration_min": 390,
        "days": [0],
        "start": "08:00",
    }
    first = save(client, [school], 0)
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1
    stale = save(client, [flex_with_latest()], 0)
    assert stale.status_code == 409
    assert client.get(f"/api/assignments?week_start={WEEK}").json() == {"assignments": []}
    saved = client.get(f"/api/week?week_start={WEEK}").json()
    assert saved["revision"] == 1
    assert [block["id"] for block in saved["blocks"]] == ["school"]


def test_assignment_id_and_latest_together_are_rejected(client: TestClient) -> None:
    response = save(client, [flex_with_latest(assignment_id=AID)], 0)
    assert response.status_code == 422
