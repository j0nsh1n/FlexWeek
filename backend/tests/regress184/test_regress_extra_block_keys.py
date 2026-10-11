"""Regression (no fix-specs item; Sammy's finding 6): a block is keyed by (user, week_start, id).

The weeks table's primary key covers (user_id, week_start) and the API refuses a week whose block list
repeats an id, so the full key stays unique. The same id may repeat across weeks and accounts (Setup's
School is always "school"). The store layer's own check is in
engine/store/tests/test_regress_extra_block_keys.rs.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
WEEK = "2026-10-05"  # a Monday
NEXT = "2026-10-12"


def school(block_id: str = "school", title: str = "School") -> dict:
    return {
        "id": block_id,
        "title": title,
        "kind": "locked",
        "category": "class",
        "start": "08:30",
        "duration_min": 405,
        "days": [0, 1, 2, 3, 4],
    }


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    return tmp_path / "keys.db"


@pytest.fixture()
def client(database: Path) -> Iterator[TestClient]:
    with TestClient(create_app(database=database, origin="http://testserver")) as test_client:
        yield test_client


def register(client: TestClient, name: str) -> None:
    client.cookies.clear()
    response = client.post("/api/auth/register", json={"username": name, "password": PASSWORD}, headers=WRITE)
    assert response.status_code == 201, response.text


def put(client: TestClient, week: str, blocks: list[dict], revision: int):
    return client.put(
        "/api/week", json={"week_start": week, "blocks": blocks, "revision": revision}, headers=WRITE
    )


def test_weeks_table_key_is_user_and_week_start(client: TestClient, database: Path) -> None:
    with sqlite3.connect(database) as db:
        rows = db.execute("PRAGMA table_info(weeks)").fetchall()
    key = [name for _cid, name, *_rest, pk in sorted(rows, key=lambda r: r[5]) if pk]
    assert key == ["user_id", "week_start"]


def test_a_week_that_repeats_a_block_id_is_refused_and_nothing_is_stored(client: TestClient) -> None:
    register(client, "keys_ann")
    response = put(client, WEEK, [school(), school(title="School copy")], 0)
    assert response.status_code == 422, response.text
    stored = client.get("/api/week", params={"week_start": WEEK}).json()
    assert stored["blocks"] == [] and stored["revision"] == 0


def test_the_week_model_names_the_repeated_id_rule() -> None:
    from pydantic import ValidationError

    from backend.models import WeekRequest

    with pytest.raises(ValidationError, match="block ids must be unique"):
        WeekRequest.model_validate({"blocks": [school(), school(title="School copy")]})


def test_saving_a_week_again_upserts_it_in_place(client: TestClient, database: Path) -> None:
    register(client, "keys_ann")
    assert put(client, WEEK, [school()], 0).status_code == 200
    second = put(client, WEEK, [school(title="School 9-3")], 1)
    assert second.status_code == 200, second.text
    assert second.json()["revision"] == 2
    with sqlite3.connect(database) as db:
        (count,) = db.execute("SELECT COUNT(*) FROM weeks WHERE week_start = ?", (WEEK,)).fetchone()
    assert count == 1
    assert [b["title"] for b in client.get("/api/week", params={"week_start": WEEK}).json()["blocks"]] == [
        "School 9-3"
    ]


def test_a_stale_second_insert_of_the_same_week_is_a_conflict_not_a_second_row(
    client: TestClient, database: Path
) -> None:
    register(client, "keys_ann")
    assert put(client, WEEK, [school()], 0).status_code == 200
    assert put(client, WEEK, [school(title="Other")], 0).status_code == 409
    with sqlite3.connect(database) as db:
        (count,) = db.execute("SELECT COUNT(*) FROM weeks WHERE week_start = ?", (WEEK,)).fetchone()
    assert count == 1


def test_the_same_id_may_repeat_across_weeks_and_accounts(client: TestClient) -> None:
    register(client, "keys_ann")
    assert put(client, WEEK, [school()], 0).status_code == 200
    assert put(client, NEXT, [school(title="School next")], 0).status_code == 200
    assert client.get("/api/week", params={"week_start": WEEK}).json()["blocks"][0]["title"] == "School"
    register(client, "keys_ben")
    assert put(client, WEEK, [school(title="Ben school")], 0).status_code == 200
    assert client.get("/api/week", params={"week_start": WEEK}).json()["blocks"][0]["title"] == "Ben school"


def test_import_refuses_a_snapshot_week_that_repeats_a_block_id(client: TestClient) -> None:
    register(client, "keys_ann")
    assert put(client, WEEK, [school()], 0).status_code == 200
    exported = client.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE)
    assert exported.status_code == 200, exported.text
    snapshot = exported.json()
    snapshot["weeks"][0]["blocks"].append(school(title="School twin"))
    preview = client.post("/api/account-import/preview", json={"snapshot": snapshot}, headers=WRITE)
    assert preview.status_code == 422, preview.text
