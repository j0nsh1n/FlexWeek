"""Assignment HTTP API from docs/stage1-contract.md. Expected values are from the contract, not a recorded run."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
WEEK_ONE = "2026-09-07"
WEEK_TWO = "2026-09-14"


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
        client.post("/api/auth/register", json={"username": username, "password": PASSWORD}, headers=WRITE).status_code
        == 201
    )


def assignment(assignment_id: str = "hw-essay", **overrides) -> dict:
    body = {
        "id": assignment_id,
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


def session(block_id: str, assignment_id: str, **overrides) -> dict:
    block = {
        "id": block_id,
        "title": "stale title",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "medium",
        "assignment_id": assignment_id,
    }
    block.update(overrides)
    return block


def save_week(client: TestClient, week_start: str, blocks: list[dict], revision: int):
    return client.put(
        "/api/week",
        json={"week_start": week_start, "blocks": blocks, "revision": revision},
        headers=WRITE,
    )


def put_assignment(client: TestClient, body: dict):
    return client.put(f"/api/assignments/{body['id']}", json=body, headers=WRITE)


def test_put_revision_zero_creates_at_revision_one_and_identical_body_does_not_bump(alice: TestClient) -> None:
    created = put_assignment(alice, assignment())
    assert created.status_code == 200, created.text
    assert created.json() == assignment(revision=1)
    again = put_assignment(alice, assignment())
    assert again.json() == assignment(revision=1)
    stale_same = put_assignment(alice, assignment(revision=0))
    assert stale_same.json() == assignment(revision=1)
    listed = alice.get(f"/api/assignments?week_start={WEEK_ONE}")
    assert listed.json() == {
        "assignments": [{**assignment(revision=1), "planned_min": 0, "unplanned_min": 120}]
    }


def test_stale_assignment_revision_conflicts(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    stale = put_assignment(alice, assignment(title="New title", revision=0))
    assert stale.status_code == 409
    assert alice.get(f"/api/assignments?week_start={WEEK_ONE}").json()["assignments"][0]["title"] == "Essay"


def test_list_orders_open_by_due_and_include_completed_adds_finished_ones(alice: TestClient) -> None:
    assert put_assignment(alice, assignment("later", title="Later", due="2026-09-16T12:00")).status_code == 200
    assert put_assignment(alice, assignment("sooner", title="Sooner", due="2026-09-14T08:00")).status_code == 200
    assert put_assignment(
        alice,
        assignment(
            "done",
            title="Done",
            due="2026-09-08T09:00",
            completed=True,
            completed_at="2026-09-08T10:00",
        ),
    ).status_code == 200
    open_only = alice.get(f"/api/assignments?week_start={WEEK_ONE}")
    assert [item["id"] for item in open_only.json()["assignments"]] == ["sooner", "later"]
    with_done = alice.get(f"/api/assignments?week_start={WEEK_ONE}&include_completed=true")
    assert [item["id"] for item in with_done.json()["assignments"]] == ["done", "sooner", "later"]


def test_planned_and_unplanned_minutes_count_open_sessions_in_this_week_and_later(alice: TestClient) -> None:
    assert put_assignment(alice, assignment(estimate_min=180)).status_code == 200
    first = save_week(alice, WEEK_ONE, [session("w1", "hw-essay", duration_min=60, days=[6])], 0)
    second = save_week(alice, WEEK_TWO, [session("w2", "hw-essay", duration_min=45, days=[0])], 0)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    week_one = alice.get(f"/api/assignments?week_start={WEEK_ONE}").json()["assignments"][0]
    week_two = alice.get(f"/api/assignments?week_start={WEEK_TWO}").json()["assignments"][0]
    assert week_one["planned_min"] == 105
    assert week_one["unplanned_min"] == 75
    assert week_two["planned_min"] == 45
    assert week_two["unplanned_min"] == 135


def test_week_put_rewrites_session_copies_and_rejects_another_accounts_assignment(
    app: FastAPI, alice: TestClient
) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    saved = save_week(alice, WEEK_ONE, [session("w1", "hw-essay", days=[6])], 0)
    assert saved.status_code == 200, saved.text
    rewritten = {
        "id": "w1",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [6],
        "priority": 2,
        "energy": "low",
        "earliest": None,
        "latest": None,
        "start": None,
        "course": "History",
        "assignment_id": "hw-essay",
    }
    assert saved.json() == {"week_start": WEEK_ONE, "blocks": [rewritten], "revision": 1}
    assert alice.get(f"/api/week?week_start={WEEK_ONE}").json() == {
        "week_start": WEEK_ONE,
        "blocks": [rewritten],
        "revision": 1,
    }
    renamed = put_assignment(alice, assignment(title="Renamed essay", revision=1))
    assert renamed.status_code == 200, renamed.text
    loaded = alice.get(f"/api/week?week_start={WEEK_ONE}").json()
    assert loaded["revision"] == 1
    assert loaded["blocks"][0]["title"] == "Renamed essay"
    with TestClient(app) as bob:
        register(bob, "bob")
        stolen = save_week(bob, WEEK_ONE, [session("w1", "hw-essay")], 0)
        assert stolen.status_code == 422
        assert bob.get(f"/api/week?week_start={WEEK_ONE}").json() == {
            "week_start": WEEK_ONE,
            "blocks": [],
            "revision": 0,
        }


def test_delete_removes_sessions_in_every_week_and_bumps_those_revisions(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    assert save_week(alice, WEEK_ONE, [session("w1", "hw-essay", days=[6])], 0).status_code == 200
    assert save_week(alice, WEEK_TWO, [session("w2", "hw-essay", days=[0])], 0).status_code == 200
    deleted = alice.delete("/api/assignments/hw-essay?revision=1", headers=WRITE)
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["changed_weeks"] == [
        {"week_start": WEEK_ONE, "revision": 2},
        {"week_start": WEEK_TWO, "revision": 2},
    ]
    assert list(body["removed_sessions"][WEEK_ONE]) == [
        {
            "id": "w1",
            "title": "Essay",
            "kind": "flexible",
            "duration_min": 60,
            "days": [6],
            "priority": 2,
            "energy": "low",
            "earliest": None,
            "latest": None,
            "start": None,
            "course": "History",
            "assignment_id": "hw-essay",
        }
    ]
    assert alice.get(f"/api/week?week_start={WEEK_ONE}").json() == {
        "week_start": WEEK_ONE,
        "blocks": [],
        "revision": 2,
    }
    assert alice.get(f"/api/week?week_start={WEEK_TWO}").json() == {
        "week_start": WEEK_TWO,
        "blocks": [],
        "revision": 2,
    }
    assert alice.get(f"/api/assignments?week_start={WEEK_ONE}").json() == {"assignments": []}
    missing = alice.delete("/api/assignments/hw-essay?revision=1", headers=WRITE)
    assert missing.status_code == 404


def test_delete_stale_revision_is_409(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    assert alice.delete("/api/assignments/hw-essay?revision=0", headers=WRITE).status_code == 409
    assert alice.get(f"/api/assignments?week_start={WEEK_ONE}").json()["assignments"][0]["id"] == "hw-essay"


def test_changes_with_one_stale_revision_stores_nothing(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    assert put_assignment(alice, assignment("other", title="Other", due="2026-09-16T12:00")).status_code == 200
    moved = assignment(title="Moved")
    moved.pop("revision")
    nope = assignment("other", title="Nope")
    nope.pop("revision")
    response = alice.post(
        "/api/changes",
        json={
            "weeks": [],
            "assignments": [
                {"id": "hw-essay", "assignment": moved, "revision": 1},
                {"id": "other", "assignment": nope, "revision": 0},
            ],
        },
        headers=WRITE,
    )
    assert response.status_code == 409
    titles = {item["id"]: item["title"] for item in alice.get(f"/api/assignments?week_start={WEEK_ONE}").json()["assignments"]}
    assert titles == {"hw-essay": "Essay", "other": "Other"}


def test_one_thousand_assignments_is_the_limit(alice: TestClient, database: Path) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    user_id = alice.get("/api/auth/me").json()["id"]
    with sqlite3.connect(database) as db:
        for index in range(999):
            body = assignment(f"seed-{index}", title=f"Seed {index}", due="2026-09-20T12:00", revision=1)
            body.pop("revision")
            db.execute(
                "INSERT INTO assignments(user_id, id, body, revision) VALUES (?, ?, ?, 1)",
                (user_id, body["id"], json.dumps(body, sort_keys=True, separators=(",", ":"))),
            )
    over = put_assignment(alice, assignment("one-too-many", title="Overflow", due="2026-09-21T12:00"))
    assert over.status_code == 422
    listed = alice.get(f"/api/assignments?week_start={WEEK_ONE}")
    assert listed.status_code == 200
    assert len(listed.json()["assignments"]) == 1000
