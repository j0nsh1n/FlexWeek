"""Routine HTTP API from docs/stage3-contract.md. Expected values are from the contract, not a recorded run."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
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


def school(**overrides) -> dict:
    block = {
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
    block.update(overrides)
    return block


def practice(**overrides) -> dict:
    block = {
        "template_id": "practice",
        "title": "Practice",
        "days": [1, 3],
        "start": "16:00",
        "duration_min": 90,
        "category": "Sport",
        "course": None,
        "priority": 2,
        "energy": "high",
        "spotify_url": None,
    }
    block.update(overrides)
    return block


def routine(routine_id: str = "r-1", **overrides) -> dict:
    body = {
        "id": routine_id,
        "name": "School week",
        "blocks": [school(), practice()],
        "revision": 0,
    }
    body.update(overrides)
    return body


def put_routine(client: TestClient, body: dict):
    return client.put(f"/api/routines/{body['id']}", json=body, headers=WRITE)


def drop_stamps(body: dict) -> tuple[str, str, dict]:
    copied = dict(body)
    created_at = copied.pop("created_at")
    updated_at = copied.pop("updated_at")
    return created_at, updated_at, copied


def test_empty_account_has_no_routines(alice: TestClient) -> None:
    response = alice.get("/api/routines")
    assert response.status_code == 200, response.text
    assert response.json() == {"routines": []}


def test_put_revision_zero_creates_and_identical_body_does_not_bump(alice: TestClient) -> None:
    created = put_routine(alice, routine())
    assert created.status_code == 200, created.text
    created_at, updated_at, body = drop_stamps(created.json())
    assert STAMP.fullmatch(created_at)
    assert created_at == updated_at
    assert body == {**routine(revision=1)}
    again = put_routine(alice, routine())
    assert drop_stamps(again.json()) == (created_at, updated_at, {**routine(revision=1)})
    listed = alice.get("/api/routines")
    assert listed.status_code == 200
    listed_at, listed_updated, listed_body = drop_stamps(listed.json()["routines"][0])
    assert (listed_at, listed_updated, listed_body) == (created_at, updated_at, {**routine(revision=1)})


def test_a_routine_block_at_any_minute_saves(alice: TestClient) -> None:
    body = routine(blocks=[school(start="07:05", duration_min=400)])
    saved = put_routine(alice, body)
    assert saved.status_code == 200, saved.text
    assert [(block["start"], block["duration_min"]) for block in saved.json()["blocks"]] == [("07:05", 400)]


def test_stale_routine_revision_conflicts(alice: TestClient) -> None:
    assert put_routine(alice, routine()).status_code == 200
    stale = put_routine(alice, routine(name="Next week", revision=0))
    assert stale.status_code == 409
    assert alice.get("/api/routines").json()["routines"][0]["name"] == "School week"


def test_update_bumps_revision_and_updated_at(alice: TestClient) -> None:
    first = put_routine(alice, routine())
    created_at, _, _ = drop_stamps(first.json())
    updated = put_routine(alice, routine(name="Busy week", revision=1))
    assert updated.status_code == 200, updated.text
    new_created, new_updated, body = drop_stamps(updated.json())
    assert new_created == created_at
    assert STAMP.fullmatch(new_updated)
    assert body == {**routine(name="Busy week", revision=2)}


def test_path_id_must_match_body(alice: TestClient) -> None:
    response = alice.put("/api/routines/r-1", json=routine("r-2"), headers=WRITE)
    assert response.status_code == 422


def test_overlapping_template_blocks_are_rejected(alice: TestClient) -> None:
    clash = practice(start="14:00", duration_min=120)
    response = put_routine(alice, routine(blocks=[school(), clash]))
    assert response.status_code == 422
    assert alice.get("/api/routines").json() == {"routines": []}


def test_adjacent_template_blocks_are_allowed(alice: TestClient) -> None:
    next_to_school = practice(start="14:30", duration_min=90, days=[0, 1, 2, 3, 4])
    response = put_routine(alice, routine(blocks=[school(), next_to_school]))
    assert response.status_code == 200, response.text
    assert drop_stamps(response.json())[2]["blocks"][1]["start"] == "14:30"


def test_delete_requires_revision_and_retry_with_operation_id_is_idempotent(alice: TestClient) -> None:
    assert put_routine(alice, routine()).status_code == 200
    missing = alice.delete("/api/routines/r-1", headers=WRITE)
    assert missing.status_code == 422
    deleted = alice.delete("/api/routines/r-1?revision=1&operation_id=op-del-1", headers=WRITE)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"id": "r-1"}
    assert alice.get("/api/routines").json() == {"routines": []}
    retry = alice.delete("/api/routines/r-1?revision=1&operation_id=op-del-1", headers=WRITE)
    assert retry.status_code == 200
    assert retry.json() == {"id": "r-1"}
    missing_again = alice.delete("/api/routines/r-1?revision=1", headers=WRITE)
    assert missing_again.status_code == 404


def test_an_account_holds_at_most_50_routines(alice: TestClient) -> None:
    for index in range(50):
        body = routine(f"r-{index}", name=f"Week {index}", blocks=[school(template_id=f"school-{index}")])
        assert put_routine(alice, body).status_code == 200
    overflow = put_routine(alice, routine("r-50", name="Overflow"))
    assert overflow.status_code == 422
    assert len(alice.get("/api/routines").json()["routines"]) == 50


def test_routines_require_a_session(client: TestClient) -> None:
    assert client.get("/api/routines").status_code == 401
    assert put_routine(client, routine()).status_code == 401
    assert client.delete("/api/routines/r-1?revision=1", headers=WRITE).status_code == 401


def test_routines_are_account_owned(app: FastAPI, alice: TestClient) -> None:
    assert put_routine(alice, routine()).status_code == 200
    with TestClient(app) as bob:
        assert (
            bob.post(
                "/api/auth/register", json={"username": "bob", "password": PASSWORD}, headers=WRITE
            ).status_code
            == 201
        )
        assert bob.get("/api/routines").json() == {"routines": []}
        assert bob.delete("/api/routines/r-1?revision=1", headers=WRITE).status_code == 404
        created = put_routine(bob, routine(name="Stolen"))
        assert created.status_code == 200, created.text
        assert drop_stamps(created.json())[2]["name"] == "Stolen"
        assert alice.get("/api/routines").json()["routines"][0]["name"] == "School week"
        assert bob.get("/api/routines").json()["routines"][0]["name"] == "Stolen"
