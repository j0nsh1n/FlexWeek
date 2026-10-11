"""A week that repeats a block id is refused by the store, not only by the request model (R10)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app import create_app, save_week_row
from backend.storage import connect

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
WEEK = "2026-09-14"


def school(title: str = "School") -> dict:
    return {
        "id": "school",
        "title": title,
        "kind": "locked",
        "duration_min": 390,
        "days": [0, 1, 2, 3, 4],
        "priority": 1,
        "energy": "medium",
        "start": "08:00",
        "category": "School",
    }


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def app(database: Path) -> FastAPI:
    return create_app(database=database, origin="http://testserver")


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        registered = test_client.post(
            "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
        )
        assert registered.status_code == 201, registered.text
        yield test_client


def stored_weeks(path: Path) -> list[tuple]:
    plain = sqlite3.connect(path)
    try:
        return plain.execute(
            "SELECT user_id, week_start, blocks, revision FROM weeks ORDER BY rowid"
        ).fetchall()
    finally:
        plain.close()


def test_the_store_refuses_a_doubled_id_in_words_and_writes_nothing(
    client: TestClient, database: Path
) -> None:
    with connect(database) as db:
        user_id = db.execute("SELECT id FROM users WHERE username = 'alice'").fetchone()[0]
        with pytest.raises(HTTPException) as refused:
            save_week_row(db, user_id, WEEK, [school(), school("School again")], 0)
    assert refused.value.status_code == 422
    assert (
        refused.value.detail == 'Two blocks in this week share the id "school". Each block needs its own id.'
    )
    assert stored_weeks(database) == []


def test_a_backup_file_with_a_doubled_id_is_refused_and_the_account_stays_as_it_was(
    client: TestClient, database: Path
) -> None:
    saved = client.put(
        "/api/week", json={"week_start": WEEK, "blocks": [school()], "revision": 0}, headers=WRITE
    )
    assert saved.status_code == 200, saved.text
    snapshot = client.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE).json()
    preview = client.post("/api/account-import/preview", json={"snapshot": snapshot}, headers=WRITE)
    assert preview.status_code == 200, preview.text
    before = stored_weeks(database)

    snapshot["weeks"][0]["blocks"] = [school(), school("School again")]
    refused_preview = client.post("/api/account-import/preview", json={"snapshot": snapshot}, headers=WRITE)
    refused_apply = client.post(
        "/api/account-import",
        json={
            "snapshot": snapshot,
            "state_token": preview.json()["state_token"],
            "operation_id": "op-doubled",
        },
        headers=WRITE,
    )

    for refused in (refused_preview, refused_apply):
        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"].startswith("Invalid input.")
    assert stored_weeks(database) == before
    assert client.get(f"/api/week?week_start={WEEK}").json()["blocks"][0]["title"] == "School"
