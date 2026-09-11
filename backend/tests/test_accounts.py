"""Account, session, cookie and request-guard checks for the accounts slice."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
# The week a parameterless /api/week uses, worked out here rather than from the code under test.
TODAY = date.today()
WEEK = (TODAY - timedelta(days=TODAY.weekday())).isoformat()


def preferences(theme: str = "system") -> dict:
    return {
        "theme": theme,
        "reminders_enabled": False,
        "reminder_lead_min": 5,
        "reminder_sound": True,
        "reminder_dnd_override": False,
        "timer_work_min": 30,
        "timer_break_min": 15,
        "timer_long_break_min": 30,
        "timer_long_break_every": 4,
        "auto_split_pomodoro": False,
        "default_spotify_url": None,
        "alarms": [],
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


def flex(block_id: str, **overrides) -> dict:
    block = {
        "id": block_id,
        "title": "Homework",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "medium",
        "earliest": None,
        "latest": None,
        "start": None,
        "course": None,
    }
    block.update(overrides)
    return block


def cookie_attrs(response) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for part in response.headers["set-cookie"].split(";"):
        name, _, value = part.strip().partition("=")
        attrs[name.lower()] = value.lower()
    return attrs


def user_count(database: Path) -> int:
    with sqlite3.connect(database) as db:
        row = db.execute("SELECT COUNT(*) FROM users").fetchone()
    assert row is not None
    return int(row[0])


def test_registration_starts_with_empty_week(alice: TestClient) -> None:
    assert alice.get("/api/week").json() == {"week_start": WEEK, "blocks": [], "revision": 0}
    me = alice.get("/api/auth/me").json()
    assert set(me) == {"id", "username"}
    assert me["username"] == "alice"
    assert alice.get("/api/preferences").json() == preferences()


def test_usernames_are_normalized_and_unique(alice: TestClient, database: Path) -> None:
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


def test_duplicate_registration_keeps_single_account(alice: TestClient, database: Path) -> None:
    response = register(alice, "alice", "another-long-password")
    assert response.status_code == 409
    assert user_count(database) == 1
    assert login(alice, "alice").status_code == 200


def test_invalid_registration_is_rejected_without_echo(client: TestClient, database: Path) -> None:
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


def test_login_rejects_invalid_credentials(alice: TestClient) -> None:
    wrong = login(alice, "alice", "wrong-password-12")
    assert wrong.status_code == 401
    assert "Incorrect username or password" in wrong.json()["detail"]

    unknown = login(alice, "nobody")
    assert unknown.status_code == 401

    assert login(alice, "alice").status_code == 200


def test_session_cookie_flags_over_http(client: TestClient) -> None:
    response = register(client, "alice")
    assert response.status_code == 201
    attrs = cookie_attrs(response)
    assert attrs["httponly"] == ""
    assert attrs["samesite"] == "strict"
    assert attrs["path"] == "/"
    assert attrs["max-age"] == str(7 * 24 * 60 * 60)
    assert "secure" not in attrs


def test_session_cookie_is_secure_over_https(tmp_path: Path) -> None:
    app = create_app(database=tmp_path / "test.db", origin="https://testserver")
    write = {"X-FlexWeek-Request": "1", "Origin": "https://testserver"}
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=write
        )
        assert response.status_code == 201
        assert cookie_attrs(response)["secure"] == ""
        assert client.get("/api/auth/me").json()["username"] == "alice"


def test_protected_endpoints_require_session(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/week").status_code == 401
    assert client.get("/api/preferences").status_code == 401
    assert client.post("/api/solve", json={"blocks": []}, headers=WRITE).status_code == 401
    unsaved = {"week_start": WEEK, "blocks": [], "revision": 0}
    assert client.put("/api/week", json=unsaved, headers=WRITE).status_code == 401
    assert client.put("/api/preferences", json=preferences("slate"), headers=WRITE).status_code == 401
    forged = {"Cookie": "flexweek_session=forged-token"}
    assert client.get("/api/auth/me", headers=forged).status_code == 401


def test_private_responses_are_not_cached(alice: TestClient) -> None:
    response = alice.get("/api/week")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_two_accounts_are_isolated(app: FastAPI, alice: TestClient) -> None:
    mine = flex("a-hw", title="Alice homework")
    first = alice.put("/api/week", json={"week_start": WEEK, "blocks": [mine], "revision": 0}, headers=WRITE)
    assert first.status_code == 200
    assert first.json()["revision"] == 1

    with TestClient(app) as bob:
        assert register(bob, "bob").status_code == 201
        assert bob.get("/api/week").json() == {"week_start": WEEK, "blocks": [], "revision": 0}
        theirs = flex("b-hw", title="Bob homework", duration_min=30, days=[1])
        assert (
            bob.put(
                "/api/week", json={"week_start": WEEK, "blocks": [theirs], "revision": 0}, headers=WRITE
            ).status_code
            == 200
        )

        stale = alice.put(
            "/api/week",
            json={"week_start": WEEK, "blocks": [flex("a-x")], "revision": 0},
            headers=WRITE,
        )
        assert stale.status_code == 409
        assert alice.get("/api/week").json() == {"week_start": WEEK, "blocks": [mine], "revision": 1}
        assert bob.get("/api/week").json() == {"week_start": WEEK, "blocks": [theirs], "revision": 1}

        assert alice.put("/api/preferences", json=preferences("slate"), headers=WRITE).status_code == 200
        assert alice.get("/api/preferences").json() == preferences("slate")
        assert bob.get("/api/preferences").json() == preferences()

        extra = flex("a-second", duration_min=30, days=[2])
        advance = alice.put(
            "/api/week", json={"week_start": WEEK, "blocks": [mine, extra], "revision": 1}, headers=WRITE
        )
        assert advance.status_code == 200
        assert advance.json()["revision"] == 2
        assert bob.get("/api/week").json()["blocks"] == [theirs]


def test_logout_revokes_session(client: TestClient) -> None:
    assert register(client, "alice").status_code == 201
    token = client.cookies.get("flexweek_session")
    assert token is not None
    assert client.get("/api/auth/me").status_code == 200

    response = client.post("/api/auth/logout", headers=WRITE)
    assert response.status_code == 204
    assert cookie_attrs(response)["max-age"] == "0"
    assert client.get("/api/auth/me").status_code == 401

    client.cookies.clear()
    reused = client.get("/api/auth/me", headers={"Cookie": f"flexweek_session={token}"})
    assert reused.status_code == 401


def test_logout_without_session_is_accepted(client: TestClient) -> None:
    assert client.post("/api/auth/logout", headers=WRITE).status_code == 204


def test_expired_session_is_rejected(client: TestClient, database: Path) -> None:
    assert register(client, "alice").status_code == 201
    assert client.get("/api/auth/me").status_code == 200

    with sqlite3.connect(database) as db:
        db.execute("UPDATE sessions SET expires = 0")

    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/week").status_code == 401


def test_write_requests_reject_spoofed_origins(alice: TestClient) -> None:
    url = "/api/preferences"
    payload = preferences("slate")
    missing = alice.put(url, json=payload, headers={"Origin": "http://testserver"})
    assert missing.status_code == 403
    wrong_token = alice.put(
        url, json=payload, headers={"X-FlexWeek-Request": "0", "Origin": "http://testserver"}
    )
    assert wrong_token.status_code == 403
    evil = alice.put(url, json=payload, headers={"X-FlexWeek-Request": "1", "Origin": "https://evil.example"})
    assert evil.status_code == 403
    cross = alice.put(url, json=payload, headers={"X-FlexWeek-Request": "1", "sec-fetch-site": "cross-site"})
    assert cross.status_code == 403

    same = alice.put(url, json=payload, headers={"X-FlexWeek-Request": "1", "sec-fetch-site": "same-origin"})
    assert same.status_code == 200
    assert alice.get(url).json() == preferences("slate")
    assert alice.put(url, json=payload, headers=WRITE).status_code == 200
    cross_get = alice.get("/api/week", headers={"sec-fetch-site": "cross-site"})
    assert cross_get.status_code == 200


def test_login_is_throttled_per_username(client: TestClient) -> None:
    assert register(client, "carol").status_code == 201
    for _ in range(9):
        assert login(client, "carol", "wrong-password-12").status_code == 401

    blocked = login(client, "carol")
    assert blocked.status_code == 429
    assert "Too many attempts" in blocked.json()["detail"]
    assert blocked.headers["retry-after"] == "300"

    assert register(client, "dave").status_code == 201


def test_accounts_and_weeks_survive_restart(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    blocks = [flex("a")]

    app_one = create_app(database=database, origin="http://testserver")
    with TestClient(app_one) as first:
        assert register(first, "alice").status_code == 201
        assert (
            first.put(
                "/api/week", json={"week_start": WEEK, "blocks": blocks, "revision": 0}, headers=WRITE
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
            "week_start": WEEK,
            "blocks": blocks,
            "revision": 1,
        }
        assert login(second, "alice").status_code == 200


def test_theme_is_system_by_default_and_only_system_light_or_dark(alice: TestClient) -> None:
    assert alice.get("/api/preferences").json()["theme"] == "system"
    for theme in ("slate", "nocturne", "system"):
        assert alice.put("/api/preferences", json=preferences(theme), headers=WRITE).status_code == 200
        assert alice.get("/api/preferences").json()["theme"] == theme
    for label in ("light", "dark", ""):
        assert alice.put("/api/preferences", json=preferences(label), headers=WRITE).status_code == 422
