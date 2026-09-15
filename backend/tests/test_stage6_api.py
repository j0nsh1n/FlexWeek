"""Stage 6 authenticated API: recovery, password, deletion, storage status and transfer."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import COOKIE, create_app
from backend.storage import connect

PASSWORD = "a-long-test-password"
REPLACEMENT = "replacement-pw-1"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
HOSTED_WRITE = {"X-FlexWeek-Request": "1", "Origin": "https://flexweek.example"}
WEEK = "2026-09-14"
DISPLAY = re.compile(r"[0-9a-f]{4}(?:-[0-9a-f]{4}){3}\Z")
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d\Z")
RECOVER_WRONG = "Incorrect username or recovery code"


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
def registered(client: TestClient) -> tuple[TestClient, list[str]]:
    response = client.post(
        "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
    )
    assert response.status_code == 201, response.text
    codes = response.json()["recovery_codes"]
    return client, codes


def defaults() -> dict:
    return {
        "theme": "system",
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


def school() -> dict:
    return {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "duration_min": 390,
        "days": [0, 1, 2, 3, 4],
        "priority": 1,
        "energy": "medium",
        "start": "08:00",
        "category": "School",
    }


def assignment(**overrides) -> dict:
    body = {
        "id": "hw-essay",
        "title": "Essay",
        "course": None,
        "category": "Homework",
        "priority": 3,
        "energy": "medium",
        "spotify_url": None,
        "due": "2026-09-16T23:59",
        "estimate_min": 120,
        "focus_minutes": 0,
        "focus_sessions": 0,
        "completed": False,
        "completed_at": None,
        "revision": 0,
    }
    body.update(overrides)
    return body


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


def test_register_returns_eight_codes_that_are_not_stored_plaintext(
    registered: tuple[TestClient, list[str]], database: Path
) -> None:
    client, codes = registered
    body = client.get("/api/auth/me").json()
    created = client.post(
        "/api/auth/login", json={"username": "alice", "password": PASSWORD}, headers=WRITE
    )
    assert created.status_code == 200, created.text
    assert created.json() == {"id": body["id"], "username": "alice"}
    assert len(codes) == 8
    assert len(set(codes)) == 8
    assert all(DISPLAY.fullmatch(code) for code in codes)
    with connect(database) as db:
        hashes = [row["code_hash"] for row in db.execute("SELECT code_hash FROM recovery_codes")]
    assert len(hashes) == 8
    assert not set(codes) & set(hashes)
    assert client.get("/api/auth/recovery-status").json() == {"remaining": 8}


def test_recover_signs_in_with_new_password_and_consumes_the_code(
    registered: tuple[TestClient, list[str]],
) -> None:
    client, codes = registered
    client.post("/api/auth/logout", headers=WRITE)
    recovered = client.post(
        "/api/auth/recover",
        json={"username": "ALICE", "code": codes[0].replace("-", "").upper(), "password": REPLACEMENT},
        headers=WRITE,
    )
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["username"] == "alice"
    assert client.get("/api/auth/me").json()["username"] == "alice"
    assert client.get("/api/auth/recovery-status").json() == {"remaining": 7}
    assert (
        client.post(
            "/api/auth/login", json={"username": "alice", "password": PASSWORD}, headers=WRITE
        ).status_code
        == 401
    )
    reused = client.post(
        "/api/auth/recover",
        json={"username": "alice", "code": codes[0], "password": PASSWORD},
        headers=WRITE,
    )
    assert reused.status_code == 401
    assert reused.json()["detail"] == RECOVER_WRONG


def test_recover_does_not_reveal_whether_the_username_exists(client: TestClient) -> None:
    unknown = client.post(
        "/api/auth/recover",
        json={"username": "nobody", "code": "a1b2-c3d4-e5f6-7890", "password": REPLACEMENT},
        headers=WRITE,
    )
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == RECOVER_WRONG
    registered = client.post(
        "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
    )
    assert registered.status_code == 201
    wrong = client.post(
        "/api/auth/recover",
        json={"username": "alice", "code": "a1b2-c3d4-e5f6-7890", "password": REPLACEMENT},
        headers=WRITE,
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == RECOVER_WRONG


def test_recover_is_throttled_per_username(client: TestClient) -> None:
    assert (
        client.post(
            "/api/auth/register", json={"username": "carol", "password": PASSWORD}, headers=WRITE
        ).status_code
        == 201
    )
    for _ in range(9):
        denied = client.post(
            "/api/auth/recover",
            json={"username": "carol", "code": "a1b2-c3d4-e5f6-7890", "password": REPLACEMENT},
            headers=WRITE,
        )
        assert denied.status_code == 401
    blocked = client.post(
        "/api/auth/recover",
        json={"username": "carol", "code": "a1b2-c3d4-e5f6-7890", "password": REPLACEMENT},
        headers=WRITE,
    )
    assert blocked.status_code == 429
    assert "Too many attempts" in blocked.json()["detail"]
    assert blocked.headers["retry-after"] == "300"


def test_regenerating_codes_invalidates_leftover_codes(
    registered: tuple[TestClient, list[str]],
) -> None:
    client, codes = registered
    refreshed = client.post("/api/auth/recovery-codes", json={"password": PASSWORD}, headers=WRITE)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["remaining"] == 8
    assert len(refreshed.json()["recovery_codes"]) == 8
    assert codes[0] not in refreshed.json()["recovery_codes"]
    client.post("/api/auth/logout", headers=WRITE)
    stale = client.post(
        "/api/auth/recover",
        json={"username": "alice", "code": codes[0], "password": REPLACEMENT},
        headers=WRITE,
    )
    assert stale.status_code == 401
    recovered = client.post(
        "/api/auth/recover",
        json={"username": "alice", "code": refreshed.json()["recovery_codes"][0], "password": REPLACEMENT},
        headers=WRITE,
    )
    assert recovered.status_code == 200, recovered.text


def test_change_password_keeps_this_session_and_revokes_a_copied_cookie(
    app: FastAPI, registered: tuple[TestClient, list[str]]
) -> None:
    alice, _codes = registered
    token = alice.cookies.get(COOKIE)
    assert token
    changed = alice.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": REPLACEMENT},
        headers=WRITE,
    )
    assert changed.status_code == 200, changed.text
    assert alice.get("/api/auth/me").status_code == 200
    with TestClient(app) as other:
        other.cookies.set(COOKIE, token)
        assert other.get("/api/auth/me").status_code == 401
    same = alice.post(
        "/api/auth/password",
        json={"current_password": REPLACEMENT, "new_password": REPLACEMENT},
        headers=WRITE,
    )
    assert same.status_code == 422
    assert same.json()["detail"] == "New password must be different"


def test_delete_account_removes_only_that_user(
    app: FastAPI, database: Path, registered: tuple[TestClient, list[str]]
) -> None:
    alice, _codes = registered
    assert alice.put("/api/week", json={"week_start": WEEK, "blocks": [school()], "revision": 0}, headers=WRITE).status_code == 200
    assert alice.put("/api/assignments/hw-essay", json=assignment(), headers=WRITE).status_code == 200
    assert alice.put("/api/routines/r-1", json=routine(), headers=WRITE).status_code == 200
    assert alice.post(
        "/api/restore-points", json={"label": "Keep me", "operation_id": "op-keep"}, headers=WRITE
    ).status_code == 200
    alice_id = alice.get("/api/auth/me").json()["id"]
    with TestClient(app) as bob:
        assert (
            bob.post(
                "/api/auth/register", json={"username": "bob", "password": PASSWORD}, headers=WRITE
            ).status_code
            == 201
        )
        assert bob.put(
            "/api/week", json={"week_start": WEEK, "blocks": [school()], "revision": 0}, headers=WRITE
        ).status_code == 200
        bob_id = bob.get("/api/auth/me").json()["id"]
        removed = alice.request(
            "DELETE", "/api/auth/account", json={"password": PASSWORD}, headers=WRITE
        )
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
    again = alice.post(
        "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
    )
    assert again.status_code == 201, again.text
    assert alice.get(f"/api/assignments?week_start={WEEK}").json() == {"assignments": []}


def test_storage_info_includes_username_and_origin_not_the_database_path(
    registered: tuple[TestClient, list[str]], database: Path
) -> None:
    client, _codes = registered
    response = client.get("/api/storage-info")
    assert response.json() == {
        "mode": "local",
        "label": "On this device",
        "username": "alice",
        "origin": "http://testserver",
    }
    assert "test.db" not in response.text
    assert str(database) not in response.text


def test_export_requires_password_and_import_copies_onto_another_database(tmp_path: Path) -> None:
    local_app = create_app(tmp_path / "local.db", "http://testserver")
    hosted_app = create_app(tmp_path / "hosted.db", "https://flexweek.example")
    with TestClient(local_app) as local, TestClient(
        hosted_app, base_url="https://flexweek.example"
    ) as hosted, TestClient(hosted_app, base_url="https://flexweek.example") as eve:
        assert (
            local.post(
                "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
            ).status_code
            == 201
        )
        prefs = {**defaults(), "theme": "nocturne", "alert_volume": 40}
        assert local.put("/api/preferences", json=prefs, headers=WRITE).status_code == 200
        assert local.put("/api/assignments/hw-essay", json=assignment(), headers=WRITE).status_code == 200
        session = {
            "id": "w1",
            "title": "Essay",
            "kind": "flexible",
            "duration_min": 60,
            "days": [0],
            "priority": 3,
            "energy": "medium",
            "assignment_id": "hw-essay",
        }
        assert local.put(
            "/api/week", json={"week_start": WEEK, "blocks": [school(), session], "revision": 0}, headers=WRITE
        ).status_code == 200
        assert local.put("/api/routines/r-1", json=routine(), headers=WRITE).status_code == 200
        denied = local.post("/api/account-export", json={"password": "wrong-password-12"}, headers=WRITE)
        assert denied.status_code == 401
        exported = local.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE)
        assert exported.status_code == 200, exported.text
        snapshot = exported.json()
        assert snapshot["format"] == 3
        assert STAMP.fullmatch(snapshot["exported_at"])
        assert snapshot["username"] == "alice"
        assert (
            hosted.post(
                "/api/auth/register",
                json={"username": "hosted_alice", "password": PASSWORD},
                headers=HOSTED_WRITE,
            ).status_code
            == 201
        )
        preview = hosted.post(
            "/api/account-import/preview", json={"snapshot": snapshot}, headers=HOSTED_WRITE
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["source_username"] == "alice"
        assert preview.json()["changes"]["weeks"]["added"] == [WEEK]
        assert preview.json()["changes"]["preferences_changed"] is True
        applied = hosted.post(
            "/api/account-import",
            json={
                "snapshot": snapshot,
                "state_token": preview.json()["state_token"],
                "operation_id": "op-import-1",
            },
            headers=HOSTED_WRITE,
        )
        assert applied.status_code == 200, applied.text
        assert hosted.get("/api/preferences").json()["theme"] == "nocturne"
        assert hosted.get("/api/preferences").json()["alert_volume"] == 40
        assert hosted.get(f"/api/week?week_start={WEEK}").json()["blocks"][0]["id"] == "school"
        listed = hosted.get(f"/api/assignments?week_start={WEEK}")
        assert listed.status_code == 200, listed.text
        assert listed.json()["assignments"][0]["title"] == "Essay"
        assert hosted.get("/api/routines").json()["routines"][0]["name"] == "School week"
        retry = hosted.post(
            "/api/account-import",
            json={
                "snapshot": snapshot,
                "state_token": preview.json()["state_token"],
                "operation_id": "op-import-1",
            },
            headers=HOSTED_WRITE,
        )
        assert retry.status_code == 200
        assert retry.json() == applied.json()
        assert (
            eve.post(
                "/api/auth/register", json={"username": "eve", "password": PASSWORD}, headers=HOSTED_WRITE
            ).status_code
            == 201
        )
        assert eve.get(f"/api/assignments?week_start={WEEK}").json() == {"assignments": []}
        local_listed = local.get(f"/api/assignments?week_start={WEEK}")
        assert local_listed.status_code == 200, local_listed.text
        assert local_listed.json()["assignments"][0]["title"] == "Essay"


def test_stale_import_token_is_conflict(registered: tuple[TestClient, list[str]]) -> None:
    client, _codes = registered
    exported = client.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE)
    snapshot = exported.json()
    preview = client.post("/api/account-import/preview", json={"snapshot": snapshot}, headers=WRITE)
    assert preview.status_code == 200, preview.text
    assert client.put(
        "/api/week", json={"week_start": WEEK, "blocks": [school()], "revision": 0}, headers=WRITE
    ).status_code == 200
    stale = client.post(
        "/api/account-import",
        json={
            "snapshot": snapshot,
            "state_token": preview.json()["state_token"],
            "operation_id": "op-stale",
        },
        headers=WRITE,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "This preview is out of date. Refresh it before importing."


def test_hostile_snapshot_assignment_is_rejected(registered: tuple[TestClient, list[str]]) -> None:
    client, _codes = registered
    exported = client.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE)
    snapshot = exported.json()
    snapshot["weeks"] = [
        {
            "week_start": WEEK,
            "revision": 1,
            "blocks": [
                {
                    "id": "w1",
                    "title": "Essay",
                    "kind": "flexible",
                    "duration_min": 60,
                    "days": [0],
                    "priority": 3,
                    "energy": "medium",
                    "assignment_id": "missing",
                }
            ],
        }
    ]
    preview = client.post("/api/account-import/preview", json={"snapshot": snapshot}, headers=WRITE)
    assert preview.status_code == 422


def test_csrf_rejects_account_writes(registered: tuple[TestClient, list[str]]) -> None:
    client, codes = registered
    assert client.post(
        "/api/auth/recover", json={"username": "alice", "code": codes[0], "password": REPLACEMENT}
    ).status_code == 403
    assert client.post("/api/account-export", json={"password": PASSWORD}).status_code == 403
    assert client.request("DELETE", "/api/auth/account", json={"password": PASSWORD}).status_code == 403


def test_two_hosted_sessions_share_a_week_and_conflict_on_stale_revision(tmp_path: Path) -> None:
    app = create_app(tmp_path / "hosted.db", "https://flexweek.example")
    with TestClient(app, base_url="https://flexweek.example") as browser, TestClient(
        app, base_url="https://flexweek.example"
    ) as desktop:
        assert (
            browser.post(
                "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=HOSTED_WRITE
            ).status_code
            == 201
        )
        assert (
            desktop.post(
                "/api/auth/login", json={"username": "alice", "password": PASSWORD}, headers=HOSTED_WRITE
            ).status_code
            == 200
        )
        saved = browser.put(
            "/api/week", json={"week_start": WEEK, "blocks": [school()], "revision": 0}, headers=HOSTED_WRITE
        )
        assert saved.status_code == 200, saved.text
        seen = desktop.get(f"/api/week?week_start={WEEK}")
        assert seen.status_code == 200
        assert seen.json()["blocks"][0]["id"] == "school"
        assert seen.json()["revision"] == 1
        stale = desktop.put(
            "/api/week", json={"week_start": WEEK, "blocks": [], "revision": 0}, headers=HOSTED_WRITE
        )
        assert stale.status_code == 409
        assert desktop.get("/api/storage-info").json() == {
            "mode": "hosted",
            "label": "On your FlexWeek server",
            "username": "alice",
            "origin": "https://flexweek.example",
        }
