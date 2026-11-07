"""Exporting an account to a file and importing it into another one, and the limits on both."""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.storage import connect
from backend.tests.account_support import (
    HOSTED_WRITE,
    PASSWORD,
    WEEK,
    WRITE,
    assignment,
    preferences,
    school,
)

STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d\Z")


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def alice(database: Path) -> Iterator[TestClient]:
    with TestClient(create_app(database=database, origin="http://testserver")) as client:
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


def test_an_export_needs_the_password_and_can_be_imported_into_another_server(tmp_path: Path) -> None:
    local_app = create_app(tmp_path / "local.db", "http://testserver")
    hosted_app = create_app(tmp_path / "hosted.db", "https://flexweek.example")
    with (
        TestClient(local_app) as local,
        TestClient(hosted_app, base_url="https://flexweek.example") as hosted,
        TestClient(hosted_app, base_url="https://flexweek.example") as eve,
    ):
        assert (
            local.post(
                "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
            ).status_code
            == 201
        )
        prefs = {**preferences("nocturne"), "reminders_enabled": False, "alert_volume": 40}
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
        assert (
            local.put(
                "/api/week",
                json={"week_start": WEEK, "blocks": [school(), session], "revision": 0},
                headers=WRITE,
            ).status_code
            == 200
        )
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


def test_an_import_preview_goes_stale_when_the_account_changes_before_applying(alice: TestClient) -> None:
    exported = alice.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE)
    snapshot = exported.json()
    preview = alice.post("/api/account-import/preview", json={"snapshot": snapshot}, headers=WRITE)
    assert preview.status_code == 200, preview.text
    assert (
        alice.put(
            "/api/week", json={"week_start": WEEK, "blocks": [school()], "revision": 0}, headers=WRITE
        ).status_code
        == 200
    )
    stale = alice.post(
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


def test_a_file_that_links_a_session_to_homework_it_does_not_hold_is_refused(alice: TestClient) -> None:
    snapshot = alice.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE).json()
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
    preview = alice.post("/api/account-import/preview", json={"snapshot": snapshot}, headers=WRITE)
    assert preview.status_code == 422


def test_an_export_holds_more_than_four_hundred_small_weeks(database: Path, alice: TestClient) -> None:
    user_id = alice.get("/api/auth/me").json()["id"]
    start = date(2018, 1, 1)
    with connect(database) as db:
        for index in range(401):
            monday = (start + timedelta(weeks=index)).isoformat()
            db.execute(
                "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?, ?, ?, 0)",
                (user_id, monday, "[]"),
            )
    exported = alice.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE)
    assert exported.status_code == 200, exported.text
    assert len(exported.json()["weeks"]) == 401


def test_an_export_is_refused_when_importing_it_would_pass_the_transfer_limit(alice: TestClient) -> None:
    notes = "n" * 4000
    for index in range(80):
        body = assignment(id=f"hw-{index:03d}", title=f"Item {index:03d}", notes=notes)
        saved = alice.put(f"/api/assignments/{body['id']}", json=body, headers=WRITE)
        assert saved.status_code == 200, saved.text
    exported = alice.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE)
    assert exported.status_code == 413, exported.text
    assert exported.json()["detail"] == "This account is larger than the 256 KiB transfer limit."
