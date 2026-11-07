"""The browser cookie and the stored session use the engine's 7-day and 30-day lengths.

The test clock (the `clock` fixture) is the time the app and the session check read, so a day passes
by moving it."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from http.cookies import SimpleCookie
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
import pytest
from fastapi.testclient import TestClient

from backend.app import SESSION_ENDED, create_app
from backend.storage import SESSION_SECONDS, SESSION_SECONDS_KEEP, connect, digest
from backend.tests.fake_clock import FakeClock

ACCOUNT = {"username": "student", "password": "a-long-test-password"}
HEADERS = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}


def cookie_token(response) -> str:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return cookie["flexweek_session"].value


def cookie_age(response) -> int:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return int(cookie["flexweek_session"]["max-age"])


@contextmanager
def signed_in(tmp_path: Path, keep: bool) -> Iterator[tuple[TestClient, object, Path]]:
    """A client that has registered and signed in; yields it, the sign-in response and the database."""
    path = tmp_path / "sessions.db"
    with TestClient(create_app(database=path, origin="http://testserver")) as client:
        assert client.post("/api/auth/register", json=ACCOUNT, headers=HEADERS).status_code == 201
        response = client.post("/api/auth/login", json={**ACCOUNT, "keep": keep}, headers=HEADERS)
        assert response.status_code == 200, response.text
        yield client, response, path


@pytest.mark.parametrize("endpoint", ["register", "login"])
def test_cookie_age_matches_the_stored_session_lifetime(
    tmp_path: Path, clock: FakeClock, endpoint: str
) -> None:
    opened_at = int(clock())
    path = tmp_path / "sessions.db"
    with TestClient(create_app(database=path, origin="http://testserver")) as client:
        response = client.post("/api/auth/register", json=ACCOUNT, headers=HEADERS)
        assert response.status_code == 201, response.text
        if endpoint == "login":
            response = client.post("/api/auth/login", json=ACCOUNT, headers=HEADERS)
            assert response.status_code == 200, response.text
        token = cookie_token(response)
        with connect(path) as db:
            expires = db.execute(
                "SELECT expires FROM sessions WHERE token_hash = ?", (digest(token),)
            ).fetchone()[0]
        lifetime = expires - opened_at
        assert getattr(flexweek_engine, "SESSION_SECONDS", None) == lifetime
        assert cookie_age(response) == lifetime


def test_a_ticked_session_is_stored_for_thirty_days(tmp_path: Path, clock: FakeClock) -> None:
    opened_at = int(clock())
    with signed_in(tmp_path, True) as (_client, response, path):
        assert cookie_age(response) == SESSION_SECONDS_KEEP
        with connect(path) as db:
            expires, lifetime = db.execute(
                "SELECT expires, lifetime FROM sessions WHERE token_hash = ?",
                (digest(cookie_token(response)),),
            ).fetchone()
        assert lifetime == SESSION_SECONDS_KEEP
        assert expires - opened_at == SESSION_SECONDS_KEEP


def test_a_ticked_session_used_on_day_29_is_still_valid(tmp_path: Path, clock: FakeClock) -> None:
    with signed_in(tmp_path, True) as (client, response, _path):
        clock.move(days=29)
        client.cookies.set("flexweek_session", cookie_token(response))
        assert client.get("/api/auth/me").status_code == 200


def test_a_ticked_session_left_alone_is_gone_on_day_31(tmp_path: Path, clock: FakeClock) -> None:
    with signed_in(tmp_path, True) as (client, response, _path):
        clock.move(days=31)
        client.cookies.set("flexweek_session", cookie_token(response))
        gone = client.get("/api/auth/me")
        assert gone.status_code == 401
        assert gone.json()["detail"] == SESSION_ENDED


def test_an_unticked_session_is_gone_on_day_8(tmp_path: Path, clock: FakeClock) -> None:
    with signed_in(tmp_path, False) as (client, response, _path):
        clock.move(days=8)
        client.cookies.set("flexweek_session", cookie_token(response))
        assert client.get("/api/auth/me").status_code == 401


def test_a_used_unticked_session_is_still_valid_on_day_12(tmp_path: Path, clock: FakeClock) -> None:
    with signed_in(tmp_path, False) as (client, response, _path):
        clock.move(days=6)
        client.cookies.set("flexweek_session", cookie_token(response))
        assert client.get("/api/auth/me").status_code == 200
        clock.move(days=6)
        assert client.get("/api/auth/me").status_code == 200


def test_a_session_row_with_no_length_is_seven_days(tmp_path: Path, clock: FakeClock) -> None:
    with signed_in(tmp_path, False) as (client, response, path):
        token = cookie_token(response)
        with connect(path) as db:
            db.execute(
                "UPDATE sessions SET lifetime = NULL, expires = ? WHERE token_hash = ?",
                (int(clock()) + SESSION_SECONDS, digest(token)),
            )
        clock.move(days=8)
        client.cookies.set("flexweek_session", token)
        ended = client.get("/api/auth/me")
        assert ended.status_code == 401
        assert ended.json()["detail"] == SESSION_ENDED


def test_a_wrong_password_keeps_its_own_words(tmp_path: Path) -> None:
    with TestClient(create_app(database=tmp_path / "login.db", origin="http://testserver")) as client:
        assert client.post("/api/auth/register", json=ACCOUNT, headers=HEADERS).status_code == 201
        wrong = client.post(
            "/api/auth/login",
            json={"username": "student", "password": "not-the-password"},
            headers=HEADERS,
        )
        assert wrong.status_code == 401
        assert wrong.json()["detail"] == "Incorrect username or password"
        # How the desktop words these two 401s is checked in desktop/tests/test_auth_words.py: this
        # suite runs where PySide6 is not installed.
