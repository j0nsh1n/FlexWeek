"""The session cookie, signing out, and the checks every request passes before the app acts on it."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from http.cookies import SimpleCookie
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.storage import connect, digest
from backend.tests.account_support import (
    PASSWORD,
    REPLACEMENT,
    THIS_WEEK,
    WRITE,
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


def cookie_attrs(response) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for part in response.headers["set-cookie"].split(";"):
        name, _, value = part.strip().partition("=")
        attrs[name.lower()] = value.lower()
    return attrs


def test_the_session_cookie_is_http_only_strict_and_lasts_a_week_over_http(client: TestClient) -> None:
    response = register(client, "alice")
    assert response.status_code == 201
    attrs = cookie_attrs(response)
    assert attrs["httponly"] == ""
    assert attrs["samesite"] == "strict"
    assert attrs["path"] == "/"
    assert attrs["max-age"] == str(7 * 24 * 60 * 60)
    assert "secure" not in attrs


@pytest.mark.parametrize(("endpoint", "keep", "days"), [("register", False, 7), ("login", False, 7), ("login", True, 30)])
def test_the_cookie_lasts_as_long_as_the_stored_session(
    client: TestClient, database: Path, clock, endpoint: str, keep: bool, days: int
) -> None:
    """Moved here from test_session_lifetime.py, whose other checks are Rust tests now."""
    opened_at = int(clock())
    response = register(client, "alice")
    if endpoint == "login":
        login = {"username": "alice", "password": PASSWORD, "keep": keep}
        response = client.post("/api/auth/login", json=login, headers=WRITE)
    assert response.status_code in (200, 201), response.text
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    token = cookie["flexweek_session"].value
    with connect(database) as db:
        expires = db.execute("SELECT expires FROM sessions WHERE token_hash = ?", (digest(token),)).fetchone()[0]
    assert int(cookie["flexweek_session"]["max-age"]) == expires - opened_at == days * 24 * 60 * 60


def test_the_session_cookie_is_secure_over_https(tmp_path: Path) -> None:
    app = create_app(database=tmp_path / "test.db", origin="https://testserver")
    write = {"X-FlexWeek-Request": "1", "Origin": "https://testserver"}
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=write
        )
        assert response.status_code == 201
        assert cookie_attrs(response)["secure"] == ""
        assert client.get("/api/auth/me").json()["username"] == "alice"


def test_every_private_route_answers_401_without_a_session(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/week").status_code == 401
    assert client.get("/api/assignments?week_start=" + THIS_WEEK).status_code == 401
    assert client.get("/api/day?date=" + THIS_WEEK).status_code == 401
    assert client.get("/api/month?month=2026-09").status_code == 401
    assert client.get("/api/routines").status_code == 401
    assert client.get("/api/restore-points").status_code == 401
    assert client.get("/api/storage-info").status_code == 401
    assert client.get("/api/preferences").status_code == 401
    assert client.post("/api/solve", json={"blocks": []}, headers=WRITE).status_code == 401
    unsaved = {"week_start": THIS_WEEK, "blocks": [], "revision": 0}
    assert client.put("/api/week", json=unsaved, headers=WRITE).status_code == 401
    assert (
        client.put(
            "/api/assignments/hw-essay",
            json={
                "id": "hw-essay",
                "title": "Essay",
                "due": "2026-09-15T23:59",
                "estimate_min": 60,
                "revision": 0,
            },
            headers=WRITE,
        ).status_code
        == 401
    )
    assert client.delete("/api/assignments/hw-essay?revision=1", headers=WRITE).status_code == 401
    assert (
        client.post("/api/changes", json={"weeks": [], "assignments": []}, headers=WRITE).status_code == 401
    )
    assert (
        client.put(
            "/api/routines/r-1",
            json={"id": "r-1", "name": "School week", "blocks": [], "revision": 0},
            headers=WRITE,
        ).status_code
        == 401
    )
    assert client.delete("/api/routines/r-1?revision=1", headers=WRITE).status_code == 401
    assert (
        client.post(
            "/api/restore-points", json={"label": "Before", "operation_id": "op-1"}, headers=WRITE
        ).status_code
        == 401
    )
    assert client.put("/api/preferences", json=preferences("slate"), headers=WRITE).status_code == 401
    forged = {"Cookie": "flexweek_session=forged-token"}
    assert client.get("/api/auth/me", headers=forged).status_code == 401


def test_the_day_answer_needs_a_date(alice: TestClient) -> None:
    """The route refuses a request with no date before asking the service (moved here from
    test_day_endpoint.py, whose other checks are Rust tests now)."""
    missing = alice.get("/api/day")
    assert (missing.status_code, missing.json()) == (
        422,
        {"detail": "date must be YYYY-MM-DD between 2000-01-01 and 2099-12-31"},
    )


def test_the_month_answer_needs_a_month_and_a_first_day_from_monday_to_sunday(alice: TestClient) -> None:
    """The route's own checks, before it asks the service (moved here from test_month_endpoint.py, whose
    other checks are Rust tests now)."""
    missing = alice.get("/api/month")
    assert (missing.status_code, missing.json()) == (
        422,
        {"detail": "month must be YYYY-MM between 2000-01 and 2099-12"},
    )
    assert alice.get("/api/month?month=2026-12&first_day=-1").status_code == 422
    assert alice.get("/api/month?month=2026-12&first_day=7").status_code == 422


def test_private_answers_are_marked_not_to_be_cached(alice: TestClient) -> None:
    response = alice.get("/api/week")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_signing_out_ends_the_session_and_the_old_cookie_stops_working(client: TestClient) -> None:
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


def test_signing_out_with_no_session_is_accepted(client: TestClient) -> None:
    assert client.post("/api/auth/logout", headers=WRITE).status_code == 204


def test_an_expired_session_is_refused(client: TestClient, database: Path) -> None:
    assert register(client, "alice").status_code == 201
    assert client.get("/api/auth/me").status_code == 200

    with sqlite3.connect(database) as db:
        db.execute("UPDATE sessions SET expires = 0")

    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/week").status_code == 401


def test_a_write_needs_the_request_header_and_our_own_origin(alice: TestClient) -> None:
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


def test_account_writes_without_the_request_header_are_refused(client: TestClient) -> None:
    registered = register(client, "alice")
    codes = registered.json()["recovery_codes"]
    assert (
        client.post(
            "/api/auth/recover", json={"username": "alice", "code": codes[0], "password": REPLACEMENT}
        ).status_code
        == 403
    )
    assert client.post("/api/account-export", json={"password": PASSWORD}).status_code == 403
    assert client.request("DELETE", "/api/auth/account", json={"password": PASSWORD}).status_code == 403
    assert client.post("/api/auth/recovery-codes", json={"password": PASSWORD}).status_code == 403
    assert (
        client.post(
            "/api/auth/password", json={"current_password": PASSWORD, "new_password": REPLACEMENT}
        ).status_code
        == 403
    )
    exported = client.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE).json()
    assert client.post("/api/account-import/preview", json={"snapshot": exported}).status_code == 403
    assert (
        client.post(
            "/api/account-import", json={"snapshot": exported, "state_token": "x", "operation_id": "op"}
        ).status_code
        == 403
    )


def test_a_browser_that_names_an_older_account_can_not_read_write_or_sign_out_the_new_one(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(tmp_path / "accounts.db", "http://testserver"), headers=WRITE) as client:
        first = client.post("/api/auth/register", json={"username": "first", "password": PASSWORD}).json()
        second = client.post("/api/auth/register", json={"username": "second", "password": PASSWORD}).json()
        client.headers["X-FlexWeek-Account"] = str(first["id"])
        assert client.get("/api/week").status_code == 401
        assert (
            client.put("/api/week", json={"week_start": THIS_WEEK, "blocks": [], "revision": 0}).status_code
            == 401
        )
        assert client.post("/api/auth/logout").status_code == 401
        del client.headers["X-FlexWeek-Account"]
        assert client.get("/api/auth/me").json()["id"] == second["id"]
