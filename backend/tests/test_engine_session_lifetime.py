"""The browser cookie and stored session use the engine's 7-day and 30-day lengths."""

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

DAY = 24 * 60 * 60
ACCOUNT = {"username": "student", "password": "a-long-test-password"}
HEADERS = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}


def hold_clock(monkeypatch: pytest.MonkeyPatch, clock: list[int]) -> None:
    monkeypatch.setattr("backend.storage.time.time", lambda: clock[0])
    monkeypatch.setattr("backend.app.time.time", lambda: clock[0])


def cookie_token(response) -> str:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return cookie["flexweek_session"].value


def cookie_age(response) -> int:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return int(cookie["flexweek_session"]["max-age"])


@contextmanager
def signed_in(tmp_path: Path, keep: bool) -> Iterator[tuple[TestClient, str, Path]]:
    path = tmp_path / "sessions.db"
    with TestClient(create_app(database=path, origin="http://testserver")) as client:
        assert client.post("/api/auth/register", json=ACCOUNT, headers=HEADERS).status_code == 201
        response = client.post("/api/auth/login", json={**ACCOUNT, "keep": keep}, headers=HEADERS)
        assert response.status_code == 200, response.text
        yield client, cookie_token(response), path


@pytest.mark.parametrize("endpoint", ["register", "login"])
def test_cookie_age_matches_the_stored_session_lifetime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    opened_at = 1_800_000_000
    hold_clock(monkeypatch, [opened_at])
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


def test_a_ticked_session_is_valid_at_day_29_and_gone_at_day_31_unused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [1_800_000_000]
    hold_clock(monkeypatch, clock)
    with signed_in(tmp_path, True) as (client, token, path):
        assert cookie_age(client.post("/api/auth/login", json={**ACCOUNT, "keep": True}, headers=HEADERS)) == (
            SESSION_SECONDS_KEEP
        )
        token = cookie_token(client.post("/api/auth/login", json={**ACCOUNT, "keep": True}, headers=HEADERS))
        with connect(path) as db:
            expires, lifetime = db.execute(
                "SELECT expires, lifetime FROM sessions WHERE token_hash = ?", (digest(token),)
            ).fetchone()
        assert lifetime == SESSION_SECONDS_KEEP
        assert expires - clock[0] == SESSION_SECONDS_KEEP
        clock[0] += 29 * DAY
        client.cookies.set("flexweek_session", token)
        assert client.get("/api/auth/me").status_code == 200
    clock = [1_800_000_000]
    hold_clock(monkeypatch, clock)
    with signed_in(tmp_path / "idle", True) as (client, token, _path):
        clock[0] += 31 * DAY
        client.cookies.set("flexweek_session", token)
        gone = client.get("/api/auth/me")
        assert gone.status_code == 401
        assert gone.json()["detail"] == SESSION_ENDED


def test_an_unticked_session_is_gone_at_day_8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1_800_000_000]
    hold_clock(monkeypatch, clock)
    with signed_in(tmp_path, False) as (client, token, _path):
        clock[0] += 8 * DAY
        client.cookies.set("flexweek_session", token)
        assert client.get("/api/auth/me").status_code == 401


def test_a_used_unticked_session_is_valid_at_day_12(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1_800_000_000]
    hold_clock(monkeypatch, clock)
    with signed_in(tmp_path, False) as (client, token, _path):
        clock[0] += 6 * DAY
        client.cookies.set("flexweek_session", token)
        assert client.get("/api/auth/me").status_code == 200
        clock[0] += 6 * DAY
        assert client.get("/api/auth/me").status_code == 200


def test_a_session_row_with_no_length_is_seven_days(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1_800_000_000]
    hold_clock(monkeypatch, clock)
    with signed_in(tmp_path, False) as (client, token, path):
        with connect(path) as db:
            db.execute(
                "UPDATE sessions SET lifetime = NULL, expires = ? WHERE token_hash = ?",
                (clock[0] + SESSION_SECONDS, digest(token)),
            )
        clock[0] += 8 * DAY
        client.cookies.set("flexweek_session", token)
        ended = client.get("/api/auth/me")
        assert ended.status_code == 401
        assert ended.json()["detail"] == SESSION_ENDED


def test_login_401_keeps_its_own_words(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1_800_000_000]
    hold_clock(monkeypatch, clock)
    with TestClient(create_app(database=tmp_path / "login.db", origin="http://testserver")) as client:
        assert client.post("/api/auth/register", json=ACCOUNT, headers=HEADERS).status_code == 201
        wrong = client.post(
            "/api/auth/login",
            json={"username": "student", "password": "not-the-password"},
            headers=HEADERS,
        )
        assert wrong.status_code == 401
        assert wrong.json()["detail"] == "Incorrect username or password"
        from desktop.native.client import SESSION_ENDED as CLIENT_ENDED
        from desktop.native.client import SIGN_IN_WRONG, _error

        assert _error(401, "Incorrect username or password").message == SIGN_IN_WRONG
        assert _error(401, SESSION_ENDED).message == CLIENT_ENDED
        assert CLIENT_ENDED == "Your session ended. Sign in again."
