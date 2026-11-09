"""Saving a week: conflicts, retries, what is refused, the fields that must survive, and what a restart keeps."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.storage import initialize
from backend.tests.account_support import HOSTED_WRITE, PASSWORD, THIS_WEEK, WEEK, WRITE, school

OLD_WEEK = "2026-09-07"
READING = {"id": "b17", "title": "Reading", "kind": "flexible", "duration_min": 17, "days": [0]}


def register(client: TestClient, username: str = "student") -> None:
    response = client.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201, response.text


def test_two_different_saves_at_once_keep_one_and_refuse_the_other(tmp_path: Path) -> None:
    app = create_app(tmp_path / "accounts.db", "http://testserver")
    with TestClient(app, headers=WRITE) as client:
        register(client)

        def save(title: str) -> tuple[int, str]:
            block = {"id": "task", "title": title, "kind": "flexible", "duration_min": 60, "days": [0]}
            result = client.put("/api/week", json={"week_start": THIS_WEEK, "blocks": [block], "revision": 0})
            return result.status_code, title

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, ["Math", "History"]))
        assert sorted(status for status, _ in results) == [200, 409]
        winner = next(title for status, title in results if status == 200)
        saved = client.get("/api/week").json()
        assert saved["revision"] == 1
        assert saved["blocks"][0]["title"] == winner


def test_saving_the_same_week_twice_is_one_revision_and_a_bad_save_never_replaces_it(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "accounts.db", "http://testserver"), headers=WRITE) as client:
        register(client)
        block = {"id": "task", "title": "Math", "kind": "flexible", "duration_min": 60, "days": [0]}
        week = {"week_start": THIS_WEEK, "blocks": [block], "revision": 0}
        assert client.put("/api/week", json=week).json()["revision"] == 1
        assert client.put("/api/week", json=week).json()["revision"] == 1
        invalid = [
            [{**block, "days": [7]}],
            [{**block, "title": "x" * 81}],
            [{**block, "latest": "invalid"}],
            [{**block, "kind": "locked", "start": "23:30", "duration_min": 60}],
            [block, block],
            [{**block, "id": str(index)} for index in range(101)],
        ]
        for blocks in invalid:
            assert (
                client.put(
                    "/api/week", json={"week_start": THIS_WEEK, "blocks": blocks, "revision": 1}
                ).status_code
                == 422
            )
        assert client.put("/api/week", content=b"x" * (256 * 1024 + 1)).status_code == 413
        saved = client.get("/api/week").json()
        assert saved["revision"] == 1
        assert len(saved["blocks"]) == 1
        assert saved["blocks"][0]["title"] == "Math"
        assert client.get("/api/demos/alex").status_code == 404
        empty = client.post("/api/solve", json={"blocks": []})
        assert empty.status_code == 200
        assert empty.json()["placed"] == []
        assert empty.json()["unplaced"] == []


def test_a_done_block_keeps_its_done_day_and_category(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "week.db", "http://testserver"), headers=WRITE) as client:
        register(client, "alice")
        block = {
            "id": "hw",
            "title": "Essay",
            "kind": "flexible",
            "duration_min": 60,
            "days": [0],
            "priority": 3,
            "energy": "medium",
            "completed": True,
            "completed_day": 0,
            "start": "09:00",
            "category": "assignments",
        }
        put = client.put("/api/week", json={"week_start": OLD_WEEK, "blocks": [block], "revision": 0})
        assert put.status_code == 200
        loaded = client.get(f"/api/week?week_start={OLD_WEEK}").json()["blocks"][0]
        assert loaded["completed"] is True
        assert loaded["completed_day"] == 0
        assert loaded["category"] == "assignments"


def test_focus_and_pomodoro_fields_survive_a_save_and_a_bad_link_or_overlap_is_refused(
    tmp_path: Path,
) -> None:
    block = {
        "id": "essay-focus-1",
        "title": "Essay focus 1/2",
        "kind": "locked",
        "duration_min": 30,
        "days": [0],
        "priority": 3,
        "energy": "medium",
        "start": "16:00",
        "spotify_url": "https://open.spotify.com/album/album123",
        "focus_sessions": 2,
        "focus_minutes": 60,
        "pomodoro_parent_id": "essay",
        "pomodoro_role": "work",
        "pomodoro_index": 1,
    }
    with TestClient(create_app(tmp_path / "focus.db", "http://testserver"), headers=WRITE) as client:
        register(client, "alice")
        saved = client.put("/api/week", json={"week_start": OLD_WEEK, "blocks": [block], "revision": 0})
        assert saved.status_code == 200
        loaded = client.get(f"/api/week?week_start={OLD_WEEK}").json()["blocks"][0]
        assert {key: loaded[key] for key in block} == block
        unsafe = {**block, "spotify_url": "https://evil.example/track/album123"}
        assert (
            client.put(
                "/api/week", json={"week_start": OLD_WEEK, "blocks": [unsafe], "revision": 1}
            ).status_code
            == 422
        )
        parent = {
            "id": "essay",
            "title": "Essay",
            "kind": "flexible",
            "duration_min": 60,
            "days": [0],
            "priority": 3,
            "energy": "medium",
        }
        overlap = client.put(
            "/api/week", json={"week_start": OLD_WEEK, "blocks": [parent, block], "revision": 1}
        )
        assert overlap.status_code == 422
        assert client.get(f"/api/week?week_start={OLD_WEEK}").json()["blocks"][0]["id"] == "essay-focus-1"


def test_a_17_minute_block_survives_a_restart_and_the_account_still_exports(tmp_path: Path) -> None:
    path = tmp_path / "accounts.db"
    with TestClient(create_app(path, "http://testserver"), headers=WRITE) as client:
        register(client)
        saved = client.put("/api/week", json={"week_start": THIS_WEEK, "blocks": [READING], "revision": 0})
        assert saved.status_code == 200
    initialize(path)
    with TestClient(create_app(path, "http://testserver"), headers=WRITE) as client:
        signed_in = client.post("/api/auth/login", json={"username": "student", "password": PASSWORD})
        assert signed_in.status_code == 200
        exported = client.post("/api/account-export", json={"password": PASSWORD})
        assert exported.status_code == 200, exported.text
        snapshot = exported.json()
        assert snapshot["assignments"] == []
        [week] = [week for week in snapshot["weeks"] if week["week_start"] == THIS_WEEK]
        assert as_typed(week["blocks"]) == [READING]
        shown = client.get("/api/week", params={"week_start": THIS_WEEK}).json()
        assert as_typed(shown["blocks"]) == [READING]


def as_typed(blocks: list[dict]) -> list[dict]:
    """The fields the student typed, and no link to homework (the schema's defaults are left out)."""
    assert all(block.get("assignment_id") is None for block in blocks)
    return [{key: block[key] for key in READING} for block in blocks]


def test_two_devices_signed_in_to_a_hosted_server_share_a_week_and_the_stale_one_conflicts(
    tmp_path: Path,
) -> None:
    app = create_app(tmp_path / "hosted.db", "https://flexweek.example")
    with (
        TestClient(app, base_url="https://flexweek.example") as browser,
        TestClient(app, base_url="https://flexweek.example") as desktop,
    ):
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
