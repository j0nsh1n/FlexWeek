"""Making an account and signing in: the rules for names and passwords, the throttle, and what a restart keeps."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import COOKIE, create_app
from backend.storage import connect
from backend.tests.account_support import (
    PASSWORD,
    THIS_WEEK,
    WRITE,
    flex,
    migrated_session,
    preferences,
)


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


def register(client: TestClient, username: str, password: str = PASSWORD):
    return client.post("/api/auth/register", json={"username": username, "password": password}, headers=WRITE)


def login(client: TestClient, username: str, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password}, headers=WRITE)


def user_count(database: Path) -> int:
    with sqlite3.connect(database) as db:
        row = db.execute("SELECT COUNT(*) FROM users").fetchone()
    assert row is not None
    return int(row[0])


def test_a_new_account_starts_with_an_empty_week_and_the_default_preferences(alice: TestClient) -> None:
    assert alice.get("/api/week").json() == {"week_start": THIS_WEEK, "blocks": [], "revision": 0}
    me = alice.get("/api/auth/me").json()
    assert set(me) == {"id", "username"}
    assert me["username"] == "alice"
    assert alice.get("/api/preferences").json() == preferences()


def test_usernames_are_lower_cased_and_unique(alice: TestClient, database: Path) -> None:
    duplicate = register(alice, "ALICE")
    assert duplicate.status_code == 409

    second = register(alice, "Bob_99")
    assert second.status_code == 201
    assert second.json()["username"] == "bob_99"

    assert login(alice, "BOB_99").status_code == 200
    assert alice.get("/api/auth/me").json()["username"] == "bob_99"

    with sqlite3.connect(database) as db:
        names = {row[0] for row in db.execute("SELECT username FROM users")}
    assert names == {"alice", "bob_99"}


def test_registering_a_taken_name_keeps_the_one_account(alice: TestClient, database: Path) -> None:
    response = register(alice, "alice", "another-long-password")
    assert response.status_code == 409
    assert user_count(database) == 1
    assert login(alice, "alice").status_code == 200


def test_a_bad_username_or_password_is_refused_without_echoing_it(client: TestClient, database: Path) -> None:
    cases = [
        {"username": "ab", "password": PASSWORD},
        {"username": "bad name", "password": PASSWORD},
        {"username": "okname", "password": "short12"},
        {"username": "okname", "password": PASSWORD, "admin": True},
    ]
    for payload in cases:
        response = client.post("/api/auth/register", json=payload, headers=WRITE)
        assert response.status_code == 422
        assert response.json()["detail"] == ("Invalid input. Check field lengths, times and required values.")
    assert "short12" not in client.post("/api/auth/register", json=cases[2], headers=WRITE).text
    assert user_count(database) == 0


def test_a_failed_registration_leaves_no_rows_and_no_cookie(tmp_path: Path) -> None:
    path = tmp_path / "accounts.db"
    with TestClient(create_app(path, "http://testserver"), headers=WRITE) as client:
        with connect(path) as db:
            db.execute("""CREATE TRIGGER reject_preferences BEFORE INSERT ON preferences
                BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END""")
        result = client.post("/api/auth/register", json={"username": "student", "password": PASSWORD})
        assert result.status_code >= 400
        assert COOKIE not in client.cookies
        with connect(path) as db:
            assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM weeks").fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def test_signing_in_fails_for_a_wrong_password_or_an_unknown_name(alice: TestClient) -> None:
    wrong = login(alice, "alice", "wrong-password-12")
    assert wrong.status_code == 401
    assert "Incorrect username or password" in wrong.json()["detail"]

    unknown = login(alice, "nobody")
    assert unknown.status_code == 401

    assert login(alice, "alice").status_code == 200


def test_signing_in_after_signing_out_with_an_unchanged_password_works(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "accounts.db", "http://testserver"), headers=WRITE) as client:
        assert register(client, "student").status_code == 201
        client.post("/api/auth/logout")
        assert login(client, "student").status_code == 200
        assert client.get("/api/auth/me").json()["username"] == "student"


def test_nine_wrong_passwords_block_that_name_for_five_minutes(client: TestClient) -> None:
    assert register(client, "carol").status_code == 201
    for _ in range(9):
        assert login(client, "carol", "wrong-password-12").status_code == 401

    blocked = login(client, "carol")
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many tries. Wait 5 minutes, then try again."
    assert blocked.headers["retry-after"] == "300"

    assert register(client, "dave").status_code == 201


def test_accounts_weeks_and_the_session_survive_a_restart(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    blocks = [flex("a")]

    app_one = create_app(database=database, origin="http://testserver")
    with TestClient(app_one) as first:
        assert register(first, "alice").status_code == 201
        assert (
            first.put(
                "/api/week", json={"week_start": THIS_WEEK, "blocks": blocks, "revision": 0}, headers=WRITE
            ).status_code
            == 200
        )
        token = first.cookies.get("flexweek_session")
        assert token is not None

    app_two = create_app(database=database, origin="http://testserver")
    with TestClient(app_two) as second:
        session_header = {"Cookie": f"flexweek_session={token}"}
        resumed = second.get("/api/auth/me", headers=session_header)
        assert resumed.status_code == 200
        assert resumed.json()["username"] == "alice"
        assert second.get("/api/week", headers=session_header).json() == {
            "week_start": THIS_WEEK,
            "blocks": [migrated_session(flex("a"))],
            "revision": 1,
        }
        assert login(second, "alice").status_code == 200
