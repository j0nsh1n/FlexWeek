"""The store behind the routes: answers to huge revisions, the text of a delete's reply, reads, and writes that roll back together."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import app
from backend.app import create_app, replace_account
from backend.models import Routine
from backend.storage import connect, initialize
from backend.tests.account_support import PASSWORD, WRITE, school

WEEK_A = "2026-09-07"
WEEK_B = "2026-09-14"
CONFLICT = "This assignment changed in another window. Reload before saving."
# Beyond what a 64-bit integer holds, in both directions.
HUGE = [2**63, -(2**63) - 1, 2**200]


def seed_users(db: Any) -> None:
    for user_id, name in ((1, "ada"), (2, "bob"), (3, "cy")):
        db.execute("INSERT INTO users(id, username, password_hash) VALUES (?, ?, 'x')", (user_id, name))
    for user_id in (1, 2):
        db.execute(
            "INSERT INTO preferences(user_id, reminders_enabled, prefs_version) VALUES (?, 1, 1)", (user_id,)
        )


@pytest.fixture()
def server(tmp_path: Path) -> FastAPI:
    return create_app(database=tmp_path / "test.db", origin="http://testserver")


@pytest.fixture()
def alice(server: FastAPI) -> Iterator[TestClient]:
    with TestClient(server) as client:
        registered = client.post(
            "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
        )
        assert registered.status_code == 201, registered.text
        yield client


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


def stored_session_week(client: TestClient) -> None:
    assert client.put("/api/assignments/hw-essay", json=assignment_body(), headers=WRITE).status_code == 200
    put_week(client, WEEK_B, [session("w1")], 0)


@pytest.mark.parametrize("revision", HUGE)
def test_deleting_homework_with_a_revision_beyond_64_bits_answers_404_then_409(
    alice: TestClient, revision: int
) -> None:
    missing = alice.delete(f"/api/assignments/hw-essay?revision={revision}", headers=WRITE)
    assert (missing.status_code, missing.json()) == (404, {"detail": "Assignment not found"})
    assert alice.put("/api/assignments/hw-essay", json=assignment_body(), headers=WRITE).status_code == 200
    stale = alice.delete(f"/api/assignments/hw-essay?revision={revision}", headers=WRITE)
    assert (stale.status_code, stale.json()) == (409, {"detail": CONFLICT})
    assert alice.delete("/api/assignments/hw-essay?revision=1", headers=WRITE).status_code == 200


@pytest.mark.parametrize("revision", HUGE)
def test_deleting_a_routine_with_a_revision_beyond_64_bits_answers_404_then_409(
    alice: TestClient, revision: int
) -> None:
    missing = alice.delete(f"/api/routines/r1?revision={revision}", headers=WRITE)
    assert (missing.status_code, missing.json()) == (404, {"detail": "Routine not found"})
    assert alice.put("/api/routines/r1", json=routine_body(), headers=WRITE).status_code == 200
    stale = alice.delete(f"/api/routines/r1?revision={revision}&operation_id=op-1", headers=WRITE)
    assert (stale.status_code, stale.json()) == (
        409,
        {"detail": "This routine changed in another window. Reload before saving."},
    )
    assert alice.delete("/api/routines/r1?revision=1", headers=WRITE).status_code == 200


def test_the_reply_to_deleting_homework_lists_each_changed_week_before_its_revision(
    alice: TestClient,
) -> None:
    stored_session_week(alice)
    deleted = alice.delete("/api/assignments/hw-essay?revision=1", headers=WRITE)
    assert deleted.status_code == 200, deleted.text
    assert f'"changed_weeks":[{{"week_start":"{WEEK_B}","revision":2}}]' in deleted.text


def test_the_reply_to_a_batch_of_changes_lists_each_changed_week_before_its_revision(
    alice: TestClient,
) -> None:
    stored_session_week(alice)
    batch = alice.post(
        "/api/changes",
        json={"weeks": [], "assignments": [{"id": "hw-essay", "assignment": None, "revision": 1}]},
        headers=WRITE,
    )
    assert batch.status_code == 200, batch.text
    assert f'"changed_weeks":[{{"week_start":"{WEEK_B}","revision":2}}]' in batch.text


def test_listing_routines_and_preferences_reads_through_the_store_not_raw_sql(
    alice: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert alice.put("/api/routines/r1", json=routine_body(), headers=WRITE).status_code == 200
    calls: list[tuple[str, tuple]] = []

    class Spy:
        def __init__(self, db: Any) -> None:
            self.db = db

        def __getattr__(self, name: str) -> Any:
            member = getattr(self.db, name)

            def recorded(*args: Any) -> Any:
                calls.append((name, args))
                return member(*args)

            return recorded

    @contextmanager
    def spied(path: Path) -> Iterator[Spy]:
        with connect(path) as db:
            yield Spy(db)

    monkeypatch.setattr(app, "connect", spied)
    routines = alice.get("/api/routines")
    preferences = alice.get("/api/preferences")
    assert routines.status_code == preferences.status_code == 200
    assert [item["id"] for item in routines.json()["routines"]] == ["r1"]
    assert preferences.json()["theme"] == "system"
    names = [name for name, _args in calls]
    assert "list_routines" in names
    assert "preference_row" in names
    statements = [args[0] for name, args in calls if name == "execute"]
    assert not [text for text in statements if "routines" in text or "preferences" in text]


def test_a_write_is_undone_when_a_later_write_in_the_same_connection_fails(tmp_path: Path) -> None:
    path = tmp_path / "week.sqlite"
    initialize(path)
    with connect(path) as db:
        seed_users(db)
        db.insert_assignment(1, "hw-essay", '{"id":"hw-essay"}')
    with pytest.raises(sqlite3.IntegrityError), connect(path) as db:
        db.execute(
            "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (1, ?, '[]', 1)", (WEEK_A,)
        )
        db.insert_assignment(1, "hw-essay", '{"id":"hw-essay"}')
    with connect(path) as db:
        assert db.execute("SELECT COUNT(*) AS n FROM weeks").fetchone()["n"] == 0
        assert db.count_assignments(1) == 1


def test_a_batch_that_saves_homework_then_hits_a_stale_week_leaves_no_homework(alice: TestClient) -> None:
    put_week(alice, WEEK_A, [], 0)
    fresh = assignment_body()
    fresh.pop("revision")
    stale = alice.post(
        "/api/changes",
        json={
            "weeks": [{"week_start": WEEK_A, "blocks": [school()], "revision": 7}],
            "assignments": [{"id": "hw-essay", "assignment": fresh, "revision": 0}],
        },
        headers=WRITE,
    )
    assert stale.status_code == 409, stale.text
    listed = alice.get(f"/api/assignments?week_start={WEEK_A}")
    assert listed.json() == {"assignments": []}


def test_replacing_an_account_that_fails_after_its_deletes_leaves_the_account_as_it_was(
    tmp_path: Path,
) -> None:
    path = tmp_path / "week.sqlite"
    initialize(path)
    with connect(path) as db:
        seed_users(db)
        db.execute(
            'INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (1, ?, \'[{"id":"old"}]\', 3)',
            (WEEK_A,),
        )
        db.insert_assignment(1, "old", '{"id":"old"}')
    twice = {"week_start": WEEK_B, "blocks": [], "revision": 1}
    with pytest.raises(sqlite3.IntegrityError), connect(path) as db:
        replace_account(db, 1, {"weeks": [twice, twice], "assignments": []})
    with connect(path) as db:
        weeks = db.execute("SELECT week_start, blocks, revision FROM weeks WHERE user_id = 1").fetchall()
        assert [(row["week_start"], row["blocks"], row["revision"]) for row in weeks] == [
            (WEEK_A, '[{"id":"old"}]', 3)
        ]
        assert db.count_assignments(1) == 1
