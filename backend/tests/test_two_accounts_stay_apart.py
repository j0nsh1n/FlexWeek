"""Two accounts that hold rows under the same ids: each reads, plans and saves only its own.

Each test registers two accounts, acts as one of them, and checks that no read shows rows of the other.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.tests.account_support import (
    PASSWORD,
    THIS_WEEK,
    WRITE,
    flex,
    migrated_session,
    preferences,
)

PASSWORD_A = "alice-long-password"
PASSWORD_B = "bobby-long-password"
WEEK_1 = "2026-09-14"
WEEK_2 = "2026-09-21"
SIGN_IN = {"detail": "Please sign in"}


@pytest.fixture()
def app(tmp_path: Path) -> FastAPI:
    return create_app(database=tmp_path / "test.db", origin="http://testserver")


@pytest.fixture()
def clients() -> Iterator[ExitStack]:
    with ExitStack() as stack:
        yield stack


def browser(app: FastAPI, clients: ExitStack) -> TestClient:
    return clients.enter_context(TestClient(app))


def register(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/api/auth/register", json={"username": username, "password": password}, headers=WRITE
    )
    assert response.status_code == 201, response.text
    return response.json()


def homework(title: str, estimate: int, due: str, revision: int = 0) -> dict:
    return {
        "id": "hw",
        "title": title,
        "course": None,
        "category": "Homework",
        "priority": 3,
        "energy": "medium",
        "spotify_url": None,
        "due": due,
        "estimate_min": estimate,
        "focus_minutes": 0,
        "focus_sessions": 0,
        "completed": False,
        "completed_at": None,
        "revision": revision,
    }


def monday_school(title: str) -> dict:
    return {
        "id": "school",
        "title": title,
        "kind": "locked",
        "duration_min": 390,
        "days": [0],
        "priority": 1,
        "energy": "medium",
        "start": "08:00",
        "category": "School",
    }


def save_week(client: TestClient, title: str, week_start: str, revision: int):
    return client.put(
        "/api/week",
        json={"week_start": week_start, "blocks": [monday_school(title)], "revision": revision},
        headers=WRITE,
    )


def test_two_accounts_keep_separate_weeks_and_preferences(app: FastAPI, clients: ExitStack) -> None:
    alice = browser(app, clients)
    register(alice, "alice", PASSWORD)
    mine = flex("a-hw", title="Alice homework")
    first = alice.put(
        "/api/week", json={"week_start": THIS_WEEK, "blocks": [mine], "revision": 0}, headers=WRITE
    )
    assert first.status_code == 200
    assert first.json()["revision"] == 1

    bob = browser(app, clients)
    register(bob, "bob", PASSWORD)
    assert bob.get("/api/week").json() == {"week_start": THIS_WEEK, "blocks": [], "revision": 0}
    theirs = flex("b-hw", title="Bob homework", duration_min=30, days=[1])
    assert (
        bob.put(
            "/api/week", json={"week_start": THIS_WEEK, "blocks": [theirs], "revision": 0}, headers=WRITE
        ).status_code
        == 200
    )

    stale = alice.put(
        "/api/week",
        json={"week_start": THIS_WEEK, "blocks": [flex("a-x")], "revision": 0},
        headers=WRITE,
    )
    assert stale.status_code == 409
    assert alice.get("/api/week").json() == {
        "week_start": THIS_WEEK,
        "blocks": [migrated_session(mine)],
        "revision": 1,
    }
    assert bob.get("/api/week").json() == {"week_start": THIS_WEEK, "blocks": [theirs], "revision": 1}

    assert alice.put("/api/preferences", json=preferences("slate"), headers=WRITE).status_code == 200
    assert alice.get("/api/preferences").json() == preferences("slate")
    assert bob.get("/api/preferences").json() == preferences()

    extra = flex("a-second", duration_min=30, days=[2])
    advance = alice.put(
        "/api/week", json={"week_start": THIS_WEEK, "blocks": [mine, extra], "revision": 1}, headers=WRITE
    )
    assert advance.status_code == 200
    assert advance.json()["revision"] == 2
    assert bob.get("/api/week").json()["blocks"] == [theirs]


def test_weeks_homework_day_and_month_reads_stay_with_their_account(app: FastAPI, clients: ExitStack) -> None:
    alice, bob = browser(app, clients), browser(app, clients)
    register(alice, "alice", PASSWORD_A)
    register(bob, "bob", PASSWORD_B)
    # Same ids and the same week in both accounts; revisions and contents differ.
    assert save_week(alice, "Alice school", WEEK_1, 0).status_code == 200
    assert save_week(alice, "Alice school, later", WEEK_1, 1).json()["revision"] == 2
    assert save_week(alice, "Alice again", WEEK_2, 0).status_code == 200
    assert save_week(bob, "Bob school", WEEK_1, 0).json()["revision"] == 1
    assert (
        alice.put(
            "/api/assignments/hw", json=homework("Alice essay", 120, "2026-09-15T23:59"), headers=WRITE
        ).status_code
        == 200
    )
    assert (
        bob.put(
            "/api/assignments/hw", json=homework("Bob lab", 60, "2026-09-22T12:00"), headers=WRITE
        ).status_code
        == 200
    )

    week_a = alice.get(f"/api/week?week_start={WEEK_1}").json()
    week_b = bob.get(f"/api/week?week_start={WEEK_1}").json()
    assert (week_a["revision"], [b["title"] for b in week_a["blocks"]]) == (2, ["Alice school, later"])
    assert (week_b["revision"], [b["title"] for b in week_b["blocks"]]) == (1, ["Bob school"])
    assert bob.get(f"/api/week?week_start={WEEK_2}").json() == {
        "week_start": WEEK_2,
        "blocks": [],
        "revision": 0,
    }
    assert alice.get("/api/weeks").json() == {"weeks": [WEEK_1, WEEK_2]}
    assert bob.get("/api/weeks").json() == {"weeks": [WEEK_1]}
    assert browser(app, clients).get("/api/weeks").json() == SIGN_IN

    listed_a = alice.get(f"/api/assignments?week_start={WEEK_1}").json()["assignments"]
    listed_b = bob.get(f"/api/assignments?week_start={WEEK_1}").json()["assignments"]
    assert [(item["title"], item["estimate_min"]) for item in listed_a] == [("Alice essay", 120)]
    assert [(item["title"], item["estimate_min"]) for item in listed_b] == [("Bob lab", 60)]

    # Monday 14 September: Alice's essay is due the next day, Bob's lab a week later.
    day_a = alice.get("/api/day?date=2026-09-14").json()
    day_b = bob.get("/api/day?date=2026-09-14").json()
    assert [item["title"] for item in day_a["due_soon"]] == ["Alice essay"]
    assert day_b["due_soon"] == []
    assert [block["title"] for block in day_a["locked"]] == ["Alice school, later"]
    assert [block["title"] for block in day_b["locked"]] == ["Bob school"]
    assert day_a["next_action"] == {"kind": "plan", "assignment_id": "hw"}
    assert day_b["next_action"] == {"kind": "add"}
    # Tuesday has no school block of Bob's, and Bob's week 2 is empty.
    assert bob.get("/api/day?date=2026-09-21").json()["locked"] == []
    assert [block["title"] for block in alice.get("/api/day?date=2026-09-21").json()["locked"]] == [
        "Alice again"
    ]

    month_a = alice.get("/api/month?month=2026-09").json()
    month_b = bob.get("/api/month?month=2026-09").json()
    assert [day["date"] for day in month_a["days"] if day["due_ids"]] == ["2026-09-15"]
    assert [day["date"] for day in month_b["days"] if day["due_ids"]] == ["2026-09-22"]
    assert [item["title"] for item in month_a["deadlines"]] == ["Alice essay"]
    assert [item["title"] for item in month_b["deadlines"]] == ["Bob lab"]
    locked_a = {day["date"]: day["locked_count"] for day in month_a["days"] if day["locked_count"]}
    locked_b = {day["date"]: day["locked_count"] for day in month_b["days"] if day["locked_count"]}
    assert locked_a == {"2026-09-14": 1, "2026-09-21": 1}
    assert locked_b == {"2026-09-14": 1}


def test_spreading_homework_reads_the_callers_own_item(app: FastAPI, clients: ExitStack) -> None:
    alice, bob = browser(app, clients), browser(app, clients)
    register(alice, "alice", PASSWORD_A)
    register(bob, "bob", PASSWORD_B)
    # The same school weeks as the reads above, so the sessions are placed around the same blocks.
    assert save_week(alice, "Alice school", WEEK_1, 0).status_code == 200
    assert save_week(alice, "Alice school, later", WEEK_1, 1).status_code == 200
    assert save_week(alice, "Alice again", WEEK_2, 0).status_code == 200
    assert save_week(bob, "Bob school", WEEK_1, 0).status_code == 200
    assert (
        alice.put(
            "/api/assignments/hw", json=homework("Alice essay", 120, "2026-09-15T23:59"), headers=WRITE
        ).status_code
        == 200
    )
    assert (
        bob.put(
            "/api/assignments/hw", json=homework("Bob lab", 60, "2026-09-22T12:00"), headers=WRITE
        ).status_code
        == 200
    )

    # 120 minutes in two hours for Alice, one for Bob.
    spread = {"session_min": 60, "from_date": "2026-09-14"}
    spread_a = alice.post("/api/assignments/hw/spread", json=spread, headers=WRITE).json()
    spread_b = bob.post("/api/assignments/hw/spread", json=spread, headers=WRITE).json()
    assert [session["duration_min"] for session in spread_a["sessions"]] == [60, 60]
    assert [session["duration_min"] for session in spread_b["sessions"]] == [60]
    assert (spread_a["remaining_min"], spread_b["remaining_min"]) == (0, 0)
    assert (
        browser(app, clients).post("/api/assignments/hw/spread", json=spread, headers=WRITE).status_code
        == 401
    )
    ghost = alice.post("/api/assignments/nothing/spread", json=spread, headers=WRITE)
    assert (ghost.status_code, ghost.json()) == (404, {"detail": "Assignment not found"})
    done = homework("Alice essay", 120, "2026-09-15T23:59", revision=1)
    done.update(completed=True, completed_at="2026-09-14T16:00")
    assert alice.put("/api/assignments/hw", json=done, headers=WRITE).status_code == 200
    closed = alice.post("/api/assignments/hw/spread", json=spread, headers=WRITE)
    assert (closed.status_code, closed.json()) == (422, {"detail": "completed assignments cannot be spread"})
    assert bob.post("/api/assignments/hw/spread", json=spread, headers=WRITE).status_code == 200


def test_the_planner_uses_the_callers_day_cutoff_and_not_anothers(app: FastAPI, clients: ExitStack) -> None:
    alice, bob = browser(app, clients), browser(app, clients)
    register(alice, "alice", PASSWORD_A)
    register(bob, "bob", PASSWORD_B)
    prefs = alice.get("/api/preferences").json()
    # Alice's day ends at 06:15; Bob has no cutoff.
    assert (
        alice.put("/api/preferences", json={**prefs, "day_cutoff": "06:15"}, headers=WRITE).status_code == 200
    )
    work = {
        "id": "hw",
        "title": "Homework",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "high",
    }

    def end_minute(client: TestClient) -> int:
        solved = client.post("/api/solve", json={"blocks": [work]}, headers=WRITE)
        assert solved.status_code == 200, solved.text
        placed = next(block for block in solved.json()["placed"] if block["id"] == "hw")
        hour, minute = map(int, placed["start"].split(":"))
        return hour * 60 + minute + int(placed["duration_min"])

    assert end_minute(alice) <= 6 * 60 + 15
    assert end_minute(bob) > 6 * 60 + 15
    assert bob.get("/api/preferences").json().get("day_cutoff") is None
    assert browser(app, clients).post("/api/solve", json={"blocks": [work]}, headers=WRITE).status_code == 401
