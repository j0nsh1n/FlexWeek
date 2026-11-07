"""Restore points: making one, previewing and restoring it, the 20-point cap, and that they belong to one account."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.storage import connect
from backend.tests.account_support import PASSWORD, WEEK, WRITE, assignment, school

STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d\Z")


@pytest.fixture()
def app(tmp_path: Path) -> FastAPI:
    return create_app(database=tmp_path / "test.db", origin="http://testserver")


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def alice(client: TestClient) -> TestClient:
    assert (
        client.post(
            "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
        ).status_code
        == 201
    )
    return client


def save_week(client: TestClient, blocks: list[dict], revision: int = 0, week_start: str = WEEK):
    return client.put(
        "/api/week",
        json={"week_start": week_start, "blocks": blocks, "revision": revision},
        headers=WRITE,
    )


def put_assignment(client: TestClient, body: dict):
    return client.put(f"/api/assignments/{body['id']}", json=body, headers=WRITE)


def create_point(client: TestClient, label: str, operation_id: str):
    return client.post(
        "/api/restore-points",
        json={"label": label, "operation_id": operation_id},
        headers=WRITE,
    )


def test_a_new_account_has_no_restore_points(alice: TestClient) -> None:
    response = alice.get("/api/restore-points")
    assert response.status_code == 200, response.text
    assert response.json() == {"restore_points": []}


def test_a_restore_point_snapshots_the_weeks_and_homework(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    assert save_week(alice, [school()]).status_code == 200
    created = create_point(alice, "Before finals week", "op-rp-1")
    assert created.status_code == 200, created.text
    point = created.json()
    assert STAMP.fullmatch(point["created_at"])
    assert point["label"] == "Before finals week"
    assert point["weeks"] == 1
    assert point["assignments"] == 1
    assert point["id"].startswith("rp-")
    listed = alice.get("/api/restore-points")
    assert listed.json() == {"restore_points": [point]}
    retry = create_point(alice, "Before finals week", "op-rp-1")
    assert retry.json() == point


def test_restoring_after_a_preview_replaces_the_account_and_keeps_a_before_restore_point(
    alice: TestClient,
) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    assert save_week(alice, [school()]).status_code == 200
    original = create_point(alice, "School week", "op-rp-school")
    point_id = original.json()["id"]
    assert put_assignment(alice, assignment(title="Rewrite", revision=1)).status_code == 200
    assert save_week(alice, [], revision=1).status_code == 200
    preview = alice.get(f"/api/restore-points/{point_id}/preview")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["id"] == point_id
    assert body["changes"] == {
        "weeks": {"added": [], "changed": [WEEK], "removed": []},
        "assignments": {
            "added": [],
            "changed": [{"id": "hw-essay", "title": "Essay"}],
            "removed": [],
        },
    }
    token = body["state_token"]
    restored = alice.post(
        f"/api/restore-points/{point_id}/restore",
        json={"state_token": token, "operation_id": "op-restore-1"},
        headers=WRITE,
    )
    assert restored.status_code == 200, restored.text
    week = alice.get(f"/api/week?week_start={WEEK}").json()
    assert [block["id"] for block in week["blocks"]] == ["school"]
    homework = alice.get(f"/api/assignments?week_start={WEEK}").json()["assignments"]
    assert homework[0]["title"] == "Essay"
    points = alice.get("/api/restore-points").json()["restore_points"]
    assert [item["label"] for item in points][0].startswith("Before restore — ")
    assert {item["id"] for item in points} >= {point_id}
    retry = alice.post(
        f"/api/restore-points/{point_id}/restore",
        json={"state_token": token, "operation_id": "op-restore-1"},
        headers=WRITE,
    )
    assert retry.json() == restored.json()


def test_restoring_from_an_out_of_date_preview_is_refused_and_changes_nothing(alice: TestClient) -> None:
    assert save_week(alice, [school()]).status_code == 200
    point_id = create_point(alice, "School", "op-rp-stale").json()["id"]
    token = alice.get(f"/api/restore-points/{point_id}/preview").json()["state_token"]
    assert save_week(alice, [], revision=1).status_code == 200
    failed = alice.post(
        f"/api/restore-points/{point_id}/restore",
        json={"state_token": token, "operation_id": "op-restore-stale"},
        headers=WRITE,
    )
    assert failed.status_code == 409
    assert alice.get(f"/api/week?week_start={WEEK}").json()["blocks"] == []
    assert alice.get("/api/restore-points").json()["restore_points"][0]["id"] == point_id


def test_a_save_with_a_snapshot_label_makes_no_point_when_its_week_is_stale(alice: TestClient) -> None:
    assert save_week(alice, [school()]).status_code == 200
    failed = alice.post(
        "/api/changes",
        json={
            "operation_id": "op-clear-1",
            "snapshot_label": "Before clear week",
            "weeks": [{"week_start": WEEK, "blocks": [], "revision": 0}],
            "assignments": [],
        },
        headers=WRITE,
    )
    assert failed.status_code == 409
    assert alice.get("/api/restore-points").json() == {"restore_points": []}
    assert [block["id"] for block in alice.get(f"/api/week?week_start={WEEK}").json()["blocks"]] == ["school"]


def test_a_save_with_a_snapshot_label_makes_a_point_then_writes(alice: TestClient) -> None:
    assert save_week(alice, [school()]).status_code == 200
    cleared = alice.post(
        "/api/changes",
        json={
            "operation_id": "op-clear-2",
            "snapshot_label": "Before clear week",
            "weeks": [{"week_start": WEEK, "blocks": [], "revision": 1}],
            "assignments": [],
        },
        headers=WRITE,
    )
    assert cleared.status_code == 200, cleared.text
    assert alice.get(f"/api/week?week_start={WEEK}").json()["blocks"] == []
    points = alice.get("/api/restore-points").json()["restore_points"]
    assert points[0]["label"] == "Before clear week"
    assert points[0]["weeks"] == 1
    retry = alice.post(
        "/api/changes",
        json={
            "operation_id": "op-clear-2",
            "snapshot_label": "Before clear week",
            "weeks": [{"week_start": WEEK, "blocks": [], "revision": 1}],
            "assignments": [],
        },
        headers=WRITE,
    )
    assert retry.json() == cleared.json()
    assert len(alice.get("/api/restore-points").json()["restore_points"]) == 1


def test_reusing_an_operation_id_with_a_different_save_is_refused(alice: TestClient) -> None:
    first = alice.post(
        "/api/changes",
        json={"operation_id": "op-same", "weeks": [], "assignments": []},
        headers=WRITE,
    )
    assert first.status_code == 200, first.text
    clash = alice.post(
        "/api/changes",
        json={
            "operation_id": "op-same",
            "weeks": [{"week_start": WEEK, "blocks": [], "revision": 0}],
            "assignments": [],
        },
        headers=WRITE,
    )
    assert clash.status_code == 409


def test_only_the_newest_20_restore_points_are_kept(alice: TestClient) -> None:
    ids = []
    for index in range(20):
        point = create_point(alice, f"Point {index}", f"op-cap-{index}").json()
        ids.append(point["id"])
    extra = create_point(alice, "Point 20", "op-cap-20")
    assert extra.status_code == 200, extra.text
    remaining = [item["id"] for item in alice.get("/api/restore-points").json()["restore_points"]]
    assert ids[0] not in remaining
    assert extra.json()["id"] in remaining
    assert len(remaining) == 20


def test_restoring_the_oldest_point_does_not_delete_it(alice: TestClient) -> None:
    ids = [create_point(alice, f"Point {index}", f"op-keep-{index}").json()["id"] for index in range(20)]
    oldest = ids[0]
    token = alice.get(f"/api/restore-points/{oldest}/preview").json()["state_token"]
    restored = alice.post(
        f"/api/restore-points/{oldest}/restore",
        json={"state_token": token, "operation_id": "op-keep-oldest"},
        headers=WRITE,
    )
    assert restored.status_code == 200, restored.text
    remaining = {item["id"] for item in alice.get("/api/restore-points").json()["restore_points"]}
    assert oldest in remaining
    assert len(remaining) == 20


def test_restore_point_routes_need_a_session(client: TestClient) -> None:
    assert client.get("/api/storage-info").status_code == 401
    assert client.get("/api/restore-points").status_code == 401
    assert create_point(client, "Nope", "op-no").status_code == 401
    assert client.get("/api/restore-points/rp-1/preview").status_code == 401
    assert (
        client.post(
            "/api/restore-points/rp-1/restore",
            json={"state_token": "x", "operation_id": "op-no"},
            headers=WRITE,
        ).status_code
        == 401
    )


def test_the_same_operation_id_in_two_accounts_makes_two_points(app: FastAPI, alice: TestClient) -> None:
    alice_point = create_point(alice, "Alice secret", "shared-op")
    assert alice_point.status_code == 200, alice_point.text
    with TestClient(app) as bob:
        assert (
            bob.post(
                "/api/auth/register", json={"username": "bob", "password": PASSWORD}, headers=WRITE
            ).status_code
            == 201
        )
        bob_point = create_point(bob, "Bob point", "shared-op")
        assert bob_point.status_code == 200, bob_point.text
        assert bob_point.json()["label"] == "Bob point"
        assert bob_point.json()["id"] != alice_point.json()["id"]
        assert alice.get("/api/restore-points").json()["restore_points"][0]["label"] == "Alice secret"
        assert bob.get("/api/restore-points").json()["restore_points"][0]["label"] == "Bob point"


def test_a_save_with_a_snapshot_label_makes_no_point_when_it_names_unknown_homework(
    alice: TestClient,
) -> None:
    session = {
        "id": "w1",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "medium",
        "assignment_id": "missing",
    }
    failed = alice.post(
        "/api/changes",
        json={
            "snapshot_label": "Before bad write",
            "weeks": [{"week_start": WEEK, "blocks": [session], "revision": 0}],
            "assignments": [],
        },
        headers=WRITE,
    )
    assert failed.status_code == 422
    assert alice.get("/api/restore-points").json() == {"restore_points": []}
    assert alice.get(f"/api/week?week_start={WEEK}").json()["blocks"] == []


def test_another_account_can_not_list_preview_or_restore_my_points(app: FastAPI, alice: TestClient) -> None:
    assert save_week(alice, [school()]).status_code == 200
    point_id = create_point(alice, "Alice only", "op-alice").json()["id"]
    with TestClient(app) as bob:
        assert (
            bob.post(
                "/api/auth/register", json={"username": "bob", "password": PASSWORD}, headers=WRITE
            ).status_code
            == 201
        )
        assert bob.get("/api/restore-points").json() == {"restore_points": []}
        assert bob.get(f"/api/restore-points/{point_id}/preview").status_code == 404
        assert (
            bob.post(
                f"/api/restore-points/{point_id}/restore",
                json={"state_token": "nope", "operation_id": "op-bob"},
                headers=WRITE,
            ).status_code
            == 404
        )
        assert alice.get("/api/restore-points").json()["restore_points"][0]["id"] == point_id


def test_restore_points_with_the_same_id_stay_with_their_account(app: FastAPI, tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    with TestClient(app) as alice, TestClient(app) as bob:
        for client, name in ((alice, "alice"), (bob, "bob")):
            registered = client.post(
                "/api/auth/register", json={"username": name, "password": PASSWORD}, headers=WRITE
            )
            assert registered.status_code == 201, registered.text
        bob_id = bob.get("/api/auth/me").json()["id"]
        assert save_week(alice, [{**school(), "title": "Alice school"}], 0).status_code == 200
        assert save_week(bob, [{**school(), "title": "Bob school"}], 0).status_code == 200
        point_a = create_point(alice, "Alice", "op-1").json()
        # Bob's point has the same id as Alice's but a different label, and it holds no weeks at all.
        with connect(database) as db:
            db.execute(
                "INSERT INTO restore_points(user_id, id, label, created_at, weeks_count, assignments_count, body)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (bob_id, point_a["id"], "Bob", "2026-09-14T08:00", 0, 0, '{"weeks":[],"assignments":[]}'),
            )
        listed_a = alice.get("/api/restore-points").json()["restore_points"]
        listed_b = bob.get("/api/restore-points").json()["restore_points"]
        assert [(item["id"], item["label"]) for item in listed_a] == [(point_a["id"], "Alice")]
        assert listed_b == [
            {
                "id": point_a["id"],
                "label": "Bob",
                "created_at": "2026-09-14T08:00",
                "weeks": 0,
                "assignments": 0,
            }
        ]
        preview = bob.get(f"/api/restore-points/{point_a['id']}/preview").json()
        assert preview["id"] == point_a["id"]
        # Bob's point holds no weeks, so his one week would go; Alice's point would only change hers.
        assert preview["changes"] == {
            "weeks": {"added": [], "changed": [], "removed": [WEEK]},
            "assignments": {"added": [], "changed": [], "removed": []},
        }
        restored = bob.post(
            f"/api/restore-points/{point_a['id']}/restore",
            json={"state_token": preview["state_token"], "operation_id": "op-bob"},
            headers=WRITE,
        )
        assert restored.status_code == 200, restored.text
        assert bob.get(f"/api/week?week_start={WEEK}").json() == {
            "week_start": WEEK,
            "blocks": [],
            "revision": 0,
        }
        assert alice.get(f"/api/week?week_start={WEEK}").json()["blocks"][0]["title"] == "Alice school"
        missing = alice.get("/api/restore-points/rp-nothing/preview")
        assert (missing.status_code, missing.json()) == (404, {"detail": "Restore point not found"})
