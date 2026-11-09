"""Deleting an account removes everything of that account, asks for its password, and leaves the others."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.tests.account_support import PASSWORD, WEEK, WRITE, assignment, school

WRONG_PASSWORD = {"detail": "Incorrect password"}
WRONG_LOGIN = {"detail": "Incorrect username or password"}
PASSWORD_A = "alice-long-password"
PASSWORD_B = "bobby-long-password"


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def app(database: Path) -> FastAPI:
    return create_app(database=database, origin="http://testserver")


@pytest.fixture()
def alice(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
        )
        assert response.status_code == 201, response.text
        yield client


def routine() -> dict:
    return {
        "id": "r-1",
        "name": "School week",
        "blocks": [
            {
                "template_id": "school",
                "title": "School",
                "days": [0, 1, 2, 3, 4],
                "start": "08:00",
                "duration_min": 390,
                "category": "School",
                "course": None,
                "priority": 1,
                "energy": "medium",
                "spotify_url": None,
            }
        ],
        "revision": 0,
    }


def table_count(database: Path, table: str, user_id: int | None = None) -> int:
    with sqlite3.connect(database) as db:
        if user_id is None:
            row = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        else:
            row = db.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,)).fetchone()
    assert row is not None
    return int(row[0])


def test_deleting_an_account_removes_all_of_its_rows_and_only_its_rows(
    app: FastAPI, database: Path, alice: TestClient
) -> None:
    assert (
        alice.put(
            "/api/week", json={"week_start": WEEK, "blocks": [school()], "revision": 0}, headers=WRITE
        ).status_code
        == 200
    )
    assert alice.put("/api/assignments/hw-essay", json=assignment(), headers=WRITE).status_code == 200
    assert alice.put("/api/routines/r-1", json=routine(), headers=WRITE).status_code == 200
    assert (
        alice.post(
            "/api/restore-points", json={"label": "Keep me", "operation_id": "op-keep"}, headers=WRITE
        ).status_code
        == 200
    )
    alice_id = alice.get("/api/auth/me").json()["id"]
    with TestClient(app) as bob:
        assert (
            bob.post(
                "/api/auth/register", json={"username": "bob", "password": PASSWORD}, headers=WRITE
            ).status_code
            == 201
        )
        assert (
            bob.put(
                "/api/week", json={"week_start": WEEK, "blocks": [school()], "revision": 0}, headers=WRITE
            ).status_code
            == 200
        )
        bob_id = bob.get("/api/auth/me").json()["id"]
        removed = alice.request("DELETE", "/api/auth/account", json={"password": PASSWORD}, headers=WRITE)
        assert removed.status_code == 204, removed.text
        assert alice.get("/api/auth/me").status_code == 401
        assert bob.get("/api/auth/me").json()["username"] == "bob"
        assert bob.get(f"/api/week?week_start={WEEK}").json()["blocks"][0]["id"] == "school"
        assert table_count(database, "users") == 1
        assert table_count(database, "weeks", alice_id) == 0
        assert table_count(database, "assignments", alice_id) == 0
        assert table_count(database, "routines", alice_id) == 0
        assert table_count(database, "restore_points", alice_id) == 0
        assert table_count(database, "sessions", alice_id) == 0
        assert table_count(database, "recovery_codes", alice_id) == 0
        assert table_count(database, "preferences", alice_id) == 0
        assert table_count(database, "weeks", bob_id) == 1
    again = alice.post("/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE)
    assert again.status_code == 201, again.text
    assert alice.get(f"/api/assignments?week_start={WEEK}").json() == {"assignments": []}


def test_deleting_an_account_asks_for_its_own_password_and_frees_the_name(app: FastAPI) -> None:
    with TestClient(app) as alice, TestClient(app) as bob:
        for client, name, password in ((alice, "alice", PASSWORD_A), (bob, "bob", PASSWORD_B)):
            registered = client.post(
                "/api/auth/register", json={"username": name, "password": password}, headers=WRITE
            )
            assert registered.status_code == 201, registered.text
        for client, title in ((alice, "Alice school"), (bob, "Bob school")):
            body = assignment(id="hw", title=title, estimate_min=60, due="2026-09-15T23:59")
            assert client.put("/api/assignments/hw", json=body, headers=WRITE).status_code == 200
            week = {"week_start": WEEK, "blocks": [{**school(), "title": title}], "revision": 0}
            assert client.put("/api/week", json=week, headers=WRITE).status_code == 200
        wrong = bob.request("DELETE", "/api/auth/account", json={"password": PASSWORD_A}, headers=WRITE)
        assert (wrong.status_code, wrong.json()) == (401, WRONG_PASSWORD)
        assert bob.get("/api/auth/me").status_code == 200
        removed = bob.request("DELETE", "/api/auth/account", json={"password": PASSWORD_B}, headers=WRITE)
        assert removed.status_code == 204
        assert bob.get("/api/auth/me").status_code == 401
        with TestClient(app) as stranger:
            signed_in = stranger.post(
                "/api/auth/login", json={"username": "bob", "password": PASSWORD_B}, headers=WRITE
            )
            assert signed_in.json() == WRONG_LOGIN
        assert alice.get("/api/auth/me").status_code == 200
        assert alice.get(f"/api/week?week_start={WEEK}").json()["blocks"][0]["title"] == "Alice school"
        assert [
            item["title"] for item in alice.get(f"/api/assignments?week_start={WEEK}").json()["assignments"]
        ] == ["Alice school"]
        # The name is free again, and the new account starts empty.
        with TestClient(app) as again:
            registered = again.post(
                "/api/auth/register", json={"username": "bob", "password": PASSWORD_B}, headers=WRITE
            )
            assert registered.status_code == 201, registered.text
            assert again.get(f"/api/week?week_start={WEEK}").json() == {
                "week_start": WEEK,
                "blocks": [],
                "revision": 0,
            }
            assert again.get(f"/api/assignments?week_start={WEEK}").json() == {"assignments": []}
