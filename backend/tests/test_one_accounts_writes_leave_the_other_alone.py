"""A save, delete, rename or import by one account leaves the rows of another account with the same ids untouched."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import app
from backend.app import create_app
from backend.models import Routine
from backend.tests.account_support import PASSWORD, WRITE, school

WEEK_A = "2026-09-07"
WEEK_B = "2026-09-14"
WEEK_C = "2026-09-21"
# Every table a signed-in account owns rows in.
OWNED = (
    "weeks",
    "assignments",
    "routines",
    "restore_points",
    "operations",
    "preferences",
    "recovery_codes",
)


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def server(database: Path) -> FastAPI:
    return create_app(database=database, origin="http://testserver")


@pytest.fixture()
def alice(server: FastAPI) -> Iterator[TestClient]:
    with TestClient(server) as test_client:
        registered = test_client.post(
            "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
        )
        assert registered.status_code == 201, registered.text
        yield test_client


@pytest.fixture()
def bob(server: FastAPI) -> Iterator[TestClient]:
    with TestClient(server) as test_client:
        registered = test_client.post(
            "/api/auth/register", json={"username": "bob", "password": PASSWORD}, headers=WRITE
        )
        assert registered.status_code == 201, registered.text
        yield test_client


def assignment_body(**overrides: Any) -> dict:
    body = {
        "id": "hw-essay",
        "title": "Essay",
        "course": None,
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


def routine_body() -> dict:
    routine = Routine.model_validate(
        {
            "id": "r1",
            "name": "Morning",
            "revision": 0,
            "blocks": [
                {
                    "template_id": "t1",
                    "title": "Block",
                    "days": [0, 1],
                    "start": "08:00",
                    "duration_min": 60,
                }
            ],
        }
    )
    return {**routine.model_dump(), "revision": 0}


def session(block_id: str) -> dict:
    return {
        "id": block_id,
        "title": "stale title",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "medium",
        "assignment_id": "hw-essay",
    }


def put_week(client: TestClient, week_start: str, blocks: list[dict], revision: int) -> None:
    response = client.put(
        "/api/week",
        json={"week_start": week_start, "blocks": blocks, "revision": revision},
        headers=WRITE,
    )
    assert response.status_code == 200, response.text


def put_assignment(client: TestClient, **overrides: Any) -> Any:
    body = assignment_body(**overrides)
    return client.put(f"/api/assignments/{body['id']}", json=body, headers=WRITE)


def account_rows(path: Path, username: str) -> dict[str, list[tuple]]:
    """Every row one account owns, as stored, to compare before and after the other one acts."""
    plain = sqlite3.connect(path)
    try:
        found = plain.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        return {
            table: plain.execute(
                f"SELECT * FROM {table} WHERE user_id = ? ORDER BY rowid", (found[0],)
            ).fetchall()
            for table in OWNED
        }
    finally:
        plain.close()


def test_deleting_homework_leaves_the_other_accounts_same_id_rows_alone(
    alice: TestClient, bob: TestClient, database: Path
) -> None:
    assert put_assignment(alice).status_code == 200
    assert put_assignment(bob, title="Bob's essay").status_code == 200
    put_week(alice, WEEK_B, [session("a1"), school()], 0)
    put_week(bob, WEEK_B, [session("b1"), {**school(), "id": "bob-keep"}], 0)
    put_week(bob, WEEK_C, [session("b2")], 0)
    before = account_rows(database, "bob")

    deleted = alice.delete("/api/assignments/hw-essay?revision=1", headers=WRITE)

    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["changed_weeks"] == [{"week_start": WEEK_B, "revision": 2}]
    assert [block["id"] for block in body["removed_sessions"][WEEK_B]] == ["a1"]
    assert list(body["removed_sessions"]) == [WEEK_B]
    assert [block["id"] for block in alice.get(f"/api/week?week_start={WEEK_B}").json()["blocks"]] == [
        "school"
    ]
    assert account_rows(database, "bob") == before


def test_saving_and_renaming_homework_leaves_the_other_accounts_same_id_alone(
    alice: TestClient, bob: TestClient, database: Path
) -> None:
    assert put_assignment(bob, title="Bob's essay").status_code == 200
    before = account_rows(database, "bob")

    created = put_assignment(alice)
    assert (created.status_code, created.json()["revision"]) == (200, 1)
    edited = put_assignment(alice, title="Renamed", revision=1)
    assert (edited.status_code, edited.json()["revision"]) == (200, 2)

    assert account_rows(database, "bob") == before
    bobs = bob.get(f"/api/assignments?week_start={WEEK_A}").json()["assignments"]
    assert [(item["id"], item["title"], item["revision"]) for item in bobs] == [
        ("hw-essay", "Bob's essay", 1)
    ]


def test_another_accounts_homework_does_not_count_toward_the_limit(
    alice: TestClient, bob: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app, "MAX_ASSIGNMENTS", 2)
    assert put_assignment(bob, id="b1").status_code == 200
    assert put_assignment(bob, id="b2").status_code == 200
    assert put_assignment(bob, id="b3").status_code == 422
    assert put_assignment(alice, id="a1").status_code == 200


def test_a_deadline_one_account_adopted_is_still_created_for_the_other(
    alice: TestClient, bob: TestClient
) -> None:
    legacy = {
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
    for client in (bob, alice):
        saved = client.put(
            "/api/week", json={"week_start": WEEK_A, "blocks": [legacy], "revision": 0}, headers=WRITE
        )
        assert saved.status_code == 200, saved.text
    mine = alice.get(f"/api/assignments?week_start={WEEK_A}").json()["assignments"]
    assert len(mine) == 1
    assert mine[0]["id"] == alice.get(f"/api/week?week_start={WEEK_A}").json()["blocks"][0]["assignment_id"]


def test_renaming_a_routine_leaves_the_other_accounts_same_id_routine_alone(
    alice: TestClient, bob: TestClient, database: Path
) -> None:
    morning = routine_body()
    assert alice.put("/api/routines/r1", json=morning, headers=WRITE).status_code == 200
    assert bob.put("/api/routines/r1", json={**morning, "name": "Bob's"}, headers=WRITE).status_code == 200
    before = account_rows(database, "bob")

    renamed = alice.put("/api/routines/r1", json={**morning, "name": "Evening", "revision": 1}, headers=WRITE)

    assert (renamed.status_code, renamed.json()["name"], renamed.json()["revision"]) == (200, "Evening", 2)
    assert account_rows(database, "bob") == before
    assert [item["name"] for item in bob.get("/api/routines").json()["routines"]] == ["Bob's"]


def test_importing_into_one_account_leaves_the_other_accounts_rows_alone(
    alice: TestClient, bob: TestClient, database: Path
) -> None:
    morning = routine_body()
    assert alice.put("/api/routines/r1", json=morning, headers=WRITE).status_code == 200
    assert bob.put("/api/routines/r1", json={**morning, "name": "Bob's"}, headers=WRITE).status_code == 200
    assert put_assignment(alice).status_code == 200
    assert put_assignment(bob, title="Bob's essay").status_code == 200
    put_week(bob, WEEK_B, [session("b1")], 0)
    before = account_rows(database, "bob")

    exported = alice.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE)
    assert exported.status_code == 200, exported.text
    snapshot = exported.json()
    snapshot["routines"][0]["name"] = "Evening"
    snapshot["assignments"][0]["body"]["title"] = "Renamed"
    preview = alice.post("/api/account-import/preview", json={"snapshot": snapshot}, headers=WRITE)
    assert preview.status_code == 200, preview.text
    applied = alice.post(
        "/api/account-import",
        json={
            "snapshot": snapshot,
            "state_token": preview.json()["state_token"],
            "operation_id": "op-import",
        },
        headers=WRITE,
    )

    assert applied.status_code == 200, applied.text
    assert [item["name"] for item in alice.get("/api/routines").json()["routines"]] == ["Evening"]
    assert account_rows(database, "bob") == before
