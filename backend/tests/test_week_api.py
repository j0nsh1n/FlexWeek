"""API checks for the dated-weeks contract: per-week identity, revisions and validation."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
# Worked out from the calendar, not the code: 2026-09-07 is a Monday, +7 days per week.
WEEK_ONE = "2026-09-07"
WEEK_TWO = "2026-09-14"
WEEK_THREE = "2026-09-21"


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
def account(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
    )
    assert response.status_code == 201, response.text
    return client


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


def save(client: TestClient, week_start: str, blocks: list[dict], revision: int):
    return client.put("/api/week", json={"week_start": week_start, "blocks": blocks, "revision": revision}, headers=WRITE)


def test_two_weeks_of_one_account_hold_independent_blocks_and_revisions(account: TestClient) -> None:
    math = flex("a-math", title="Algebra homework")
    reading = flex("a-read", title="Reading", duration_min=30, days=[3], priority=4)
    assert save(account, WEEK_ONE, [math], 0).json() == {"week_start": WEEK_ONE, "blocks": [math], "revision": 1}
    assert save(account, WEEK_TWO, [reading], 0).json() == {"week_start": WEEK_TWO, "blocks": [reading], "revision": 1}

    saved_one = account.get(f"/api/week?week_start={WEEK_ONE}")
    saved_two = account.get(f"/api/week?week_start={WEEK_TWO}")
    assert saved_one.json() == {"week_start": WEEK_ONE, "blocks": [math], "revision": 1}
    assert saved_two.json() == {"week_start": WEEK_TWO, "blocks": [reading], "revision": 1}


def test_put_rejects_a_non_monday_week_start_and_changes_nothing(account: TestClient) -> None:
    math = flex("a-math", title="Algebra homework")
    assert save(account, WEEK_ONE, [math], 0).status_code == 200

    tuesday = save(account, "2026-09-08", [math], 0)
    assert tuesday.status_code == 422

    saved_one = account.get(f"/api/week?week_start={WEEK_ONE}")
    assert saved_one.json() == {"week_start": WEEK_ONE, "blocks": [math], "revision": 1}
    assert account.get("/api/weeks").json() == {"weeks": [WEEK_ONE]}


def test_get_rejects_non_monday_and_malformed_week_starts(account: TestClient) -> None:
    for week_start in ("2026-09-08", "2026-09-13", "2026-9-7", "20260907", "2026-W37-1"):
        response = account.get(f"/api/week?week_start={week_start}")
        assert response.status_code == 422


def test_out_of_range_week_starts_are_rejected(account: TestClient) -> None:
    # Both are Mondays, so only the range rule can reject them.
    assert account.get("/api/week?week_start=1999-12-27").status_code == 422
    assert account.get("/api/week?week_start=2100-01-04").status_code == 422
    assert save(account, "1999-12-27", [], 0).status_code == 422
    assert account.get("/api/weeks").json() == {"weeks": []}


def test_never_saved_week_reads_empty_then_is_created_by_put(account: TestClient) -> None:
    saved = account.get(f"/api/week?week_start={WEEK_THREE}")
    assert saved.json() == {"week_start": WEEK_THREE, "blocks": [], "revision": 0}

    math = flex("a-math", title="Algebra homework")
    assert save(account, WEEK_THREE, [math], 0).json() == {
        "week_start": WEEK_THREE,
        "blocks": [math],
        "revision": 1,
    }

    # A never-saved week with any other revision has nothing to match.
    assert save(account, WEEK_ONE, [math], 3).status_code == 409
    unsaved = account.get(f"/api/week?week_start={WEEK_ONE}")
    assert unsaved.json() == {"week_start": WEEK_ONE, "blocks": [], "revision": 0}


def test_re_saving_identical_blocks_leaves_revision_unchanged(account: TestClient) -> None:
    math = flex("a-math", title="Algebra homework")
    assert save(account, WEEK_ONE, [math], 0).json()["revision"] == 1

    repeat = save(account, WEEK_ONE, [math], 1)
    assert repeat.json() == {"week_start": WEEK_ONE, "blocks": [math], "revision": 1}
    # The identical-blocks short-circuit runs before the revision check, so even a stale revision succeeds.
    stale = save(account, WEEK_ONE, [math], 0)
    assert stale.json() == {"week_start": WEEK_ONE, "blocks": [math], "revision": 1}

    saved = account.get(f"/api/week?week_start={WEEK_ONE}")
    assert saved.json() == {"week_start": WEEK_ONE, "blocks": [math], "revision": 1}
    assert account.get("/api/weeks").json() == {"weeks": [WEEK_ONE]}


def test_stale_revision_conflicts_on_one_week_without_touching_the_other(account: TestClient) -> None:
    math = flex("a-math", title="Algebra homework")
    reading = flex("a-read", title="Reading", duration_min=30, days=[3], priority=4)
    assert save(account, WEEK_ONE, [math], 0).status_code == 200
    assert save(account, WEEK_TWO, [reading], 0).status_code == 200

    stale = save(account, WEEK_ONE, [flex("a-other")], 0)
    assert stale.status_code == 409

    saved_one = account.get(f"/api/week?week_start={WEEK_ONE}")
    saved_two = account.get(f"/api/week?week_start={WEEK_TWO}")
    assert saved_one.json() == {"week_start": WEEK_ONE, "blocks": [math], "revision": 1}
    assert saved_two.json() == {"week_start": WEEK_TWO, "blocks": [reading], "revision": 1}


def test_weeks_listing_is_ascending_and_per_account(app: FastAPI, account: TestClient) -> None:
    math = flex("a-math", title="Algebra homework")
    reading = flex("a-read", title="Reading", duration_min=30, days=[3], priority=4)
    # Save the later week first, so ascending order is not the insertion order.
    assert save(account, WEEK_TWO, [reading], 0).status_code == 200
    assert save(account, WEEK_ONE, [math], 0).status_code == 200
    assert account.get("/api/weeks").json() == {"weeks": [WEEK_ONE, WEEK_TWO]}

    with TestClient(app) as bob:
        assert (
            bob.post("/api/auth/register", json={"username": "bob", "password": PASSWORD}, headers=WRITE).status_code
            == 201
        )
        assert bob.get("/api/weeks").json() == {"weeks": []}
        saved = bob.get(f"/api/week?week_start={WEEK_ONE}")
        assert saved.json() == {"week_start": WEEK_ONE, "blocks": [], "revision": 0}
