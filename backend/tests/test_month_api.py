"""GET /api/month from docs/stage7-contract.md. Grid lengths are from the calendar, not a recorded run."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import MONTH_RULE, create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
MONTH = "2026-09"
WEEK = "2026-09-14"


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


def assignment(assignment_id: str = "hw-essay", **overrides) -> dict:
    body = {
        "id": assignment_id,
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


def session(block_id: str, day: int, start: str, assignment_id: str = "hw-essay", **overrides) -> dict:
    block = {
        "id": block_id,
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [day],
        "priority": 3,
        "energy": "medium",
        "start": start,
        "assignment_id": assignment_id,
        "category": "Homework",
    }
    block.update(overrides)
    return block


def save_week(client: TestClient, blocks: list[dict], revision: int = 0, week_start: str = WEEK):
    return client.put(
        "/api/week",
        json={"week_start": week_start, "blocks": blocks, "revision": revision},
        headers=WRITE,
    )


def put_assignment(client: TestClient, body: dict):
    return client.put(f"/api/assignments/{body['id']}", json=body, headers=WRITE)


def get_month(client: TestClient, month: str = MONTH):
    return client.get(f"/api/month?month={month}")


def day_on(body: dict, date: str) -> dict:
    return next(day for day in body["days"] if day["date"] == date)


def test_empty_september_is_a_five_week_grid(alice: TestClient) -> None:
    response = get_month(alice)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["month"] == MONTH
    assert body["start"] == "2026-09-01"
    assert body["end"] == "2026-09-30"
    assert body["grid_start"] == "2026-08-31"
    assert body["grid_end"] == "2026-10-04"
    assert len(body["days"]) == 35
    assert body["days"][0] == {
        "date": "2026-08-31",
        "week_start": "2026-08-31",
        "in_month": False,
        "due_ids": [],
        "session_count": 0,
        "locked_count": 0,
        "scheduled_min": 0,
        "focus_min": 0,
        "blocks": [],
    }
    assert body["unscheduled"] == {"session_count": 0, "minutes": 0}
    first = day_on(body, "2026-09-01")
    assert first["in_month"] is True
    assert first["week_start"] == "2026-08-31"
    assert body["days"][-1]["date"] == "2026-10-04"
    assert body["deadlines"] == []
    assert body["projects"] == []
    assert body["overdue"] == []


def test_school_week_occupies_only_that_monday_through_friday(alice: TestClient) -> None:
    assert save_week(alice, [school()]).status_code == 200
    body = get_month(alice).json()
    for date in ("2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"):
        cell = day_on(body, date)
        assert cell["locked_count"] == 1
        assert cell["session_count"] == 0
        assert cell["scheduled_min"] == 390
    weekend = day_on(body, "2026-09-19")
    assert weekend["locked_count"] == 0
    assert weekend["scheduled_min"] == 0
    assert day_on(body, "2026-09-07")["scheduled_min"] == 0


def test_open_homework_due_in_month_is_a_deadline_not_a_project(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    body = get_month(alice).json()
    assert body["deadlines"] == [
        {
            "id": "hw-essay",
            "title": "Essay",
            "due": "2026-09-16T23:59",
            "date": "2026-09-16",
            "completed": False,
            "estimate_min": 120,
            "unplanned_min": 120,
            "revision": 1,
        }
    ]
    assert day_on(body, "2026-09-16")["due_ids"] == ["hw-essay"]
    assert body["projects"] == []
    assert body["overdue"] == []


def test_notes_make_the_same_homework_a_project(alice: TestClient) -> None:
    assert put_assignment(alice, assignment(notes="Outline first.")).status_code == 200
    body = get_month(alice).json()
    assert body["projects"] == [
        {
            "id": "hw-essay",
            "title": "Essay",
            "due": "2026-09-16T23:59",
            "date": "2026-09-16",
            "completed": False,
            "estimate_min": 120,
            "unplanned_min": 120,
            "revision": 1,
            "session_dates": [],
            "has_notes": True,
            "has_links": False,
            "checklist_total": 0,
            "checklist_done": 0,
        }
    ]


def test_two_placed_session_dates_make_a_project_without_notes(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    assert save_week(alice, [session("s-tue", 1, "16:00"), session("s-wed", 2, "16:00")]).status_code == 200
    body = get_month(alice).json()
    project = body["projects"][0]
    assert project["id"] == "hw-essay"
    assert project["session_dates"] == ["2026-09-15", "2026-09-16"]
    assert project["has_notes"] is False
    assert project["unplanned_min"] == 0
    assert day_on(body, "2026-09-15")["session_count"] == 1
    assert day_on(body, "2026-09-16")["session_count"] == 1
    assert day_on(body, "2026-09-15")["scheduled_min"] == 60


def test_completed_session_pins_only_its_completed_day(alice: TestClient) -> None:
    # toggleCompleted keeps the candidate list and records the slot in completed_day.
    assert put_assignment(alice, assignment()).status_code == 200
    done = session("s-done", 1, "16:00", days=[1, 2, 3], completed=True, completed_day=2)
    assert save_week(alice, [done]).status_code == 200, save_week(alice, [done]).text
    body = get_month(alice).json()
    assert day_on(body, "2026-09-15")["session_count"] == 0
    assert day_on(body, "2026-09-16")["session_count"] == 1
    assert day_on(body, "2026-09-16")["scheduled_min"] == 60
    assert day_on(body, "2026-09-17")["session_count"] == 0
    assert body["projects"] == []


def test_several_candidate_days_pin_nothing_and_count_as_unscheduled(alice: TestClient) -> None:
    """Open work with a choice of days has no date the server can name (decision 7)."""
    assert put_assignment(alice, assignment()).status_code == 200
    open_session = session("s-tue", 1, "16:00", days=[1, 2, 3])
    del open_session["start"]
    assert save_week(alice, [open_session]).status_code == 200
    body = get_month(alice).json()
    for label in ("2026-09-15", "2026-09-16", "2026-09-17"):
        assert day_on(body, label)["session_count"] == 0, label
        assert day_on(body, label)["scheduled_min"] == 0, label
    assert body["unscheduled"] == {"session_count": 1, "minutes": 60}
    assert body["projects"] == []
    assert body["deadlines"][0]["unplanned_min"] == 60


def test_a_single_candidate_session_with_no_time_is_unscheduled(alice: TestClient) -> None:
    """One possible day is not a plan. Before plans were stored it was the only date the server could
    name; now that Day counts only work with a time, Month does too."""
    assert put_assignment(alice, assignment()).status_code == 200
    open_session = session("s-tue", 1, "16:00")
    del open_session["start"]
    assert save_week(alice, [open_session]).status_code == 200
    body = get_month(alice).json()
    tuesday = day_on(body, "2026-09-15")
    assert tuesday["session_count"] == 0
    assert tuesday["scheduled_min"] == 0
    assert body["unscheduled"] == {"session_count": 1, "minutes": 60}


def test_a_planned_session_is_scheduled_work_on_its_day(alice: TestClient) -> None:
    """A saved plan is a start on one day, and that is the day it counts on."""
    assert put_assignment(alice, assignment()).status_code == 200
    assert save_week(alice, [session("s-tue", 1, "16:00")]).status_code == 200
    body = get_month(alice).json()
    tuesday = day_on(body, "2026-09-15")
    assert (tuesday["session_count"], tuesday["scheduled_min"], tuesday["focus_min"]) == (1, 60, 0)
    assert body["unscheduled"] == {"session_count": 0, "minutes": 0}


def test_completing_undated_work_moves_it_onto_the_day_it_happened(alice: TestClient) -> None:
    """The same session should stop being unscheduled once it has a completed day."""
    assert put_assignment(alice, assignment()).status_code == 200
    done = session("s-tue", 1, "16:00", days=[1, 2, 3], completed=True, completed_day=2)
    assert save_week(alice, [done]).status_code == 200
    body = get_month(alice).json()
    wednesday = day_on(body, "2026-09-16")
    assert wednesday["session_count"] == 1
    assert wednesday["scheduled_min"] == 60
    assert wednesday["focus_min"] == 60
    assert day_on(body, "2026-09-15")["session_count"] == 0
    assert day_on(body, "2026-09-17")["session_count"] == 0
    assert body["unscheduled"] == {"session_count": 0, "minutes": 0}


def test_overdue_open_homework_is_not_a_september_deadline(alice: TestClient) -> None:
    assert put_assignment(alice, assignment(due="2026-08-15T23:59")).status_code == 200
    body = get_month(alice).json()
    assert body["deadlines"] == []
    assert body["overdue"] == [
        {
            "id": "hw-essay",
            "title": "Essay",
            "due": "2026-08-15T23:59",
            "date": "2026-08-15",
            "completed": False,
            "estimate_min": 120,
            "unplanned_min": 120,
            "revision": 1,
        }
    ]
    assert day_on(body, "2026-09-01")["due_ids"] == []


def test_completed_deadline_stays_on_its_date(alice: TestClient) -> None:
    assert (
        put_assignment(alice, assignment(completed=True, completed_at="2026-09-16T20:00")).status_code == 200
    )
    body = get_month(alice).json()
    assert body["deadlines"][0]["completed"] is True
    assert body["projects"] == []
    assert day_on(body, "2026-09-16")["due_ids"] == ["hw-essay"]


def test_pomodoro_work_chunks_count_as_sessions_and_breaks_as_locked(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    work = {
        "id": "essay-w1",
        "title": "Essay",
        "kind": "locked",
        "duration_min": 30,
        "days": [1],
        "priority": 3,
        "energy": "medium",
        "start": "16:00",
        "assignment_id": "hw-essay",
        "category": "Homework",
        "pomodoro_parent_id": "essay",
        "pomodoro_role": "work",
        "pomodoro_index": 1,
    }
    rest = {
        "id": "essay-b1",
        "title": "Break",
        "kind": "locked",
        "duration_min": 15,
        "days": [1],
        "priority": 3,
        "energy": "medium",
        "start": "16:30",
        "category": "Homework",
        "pomodoro_parent_id": "essay",
        "pomodoro_role": "break",
        "pomodoro_index": 1,
    }
    assert save_week(alice, [work, rest]).status_code == 200
    cell = day_on(get_month(alice).json(), "2026-09-15")
    assert cell["session_count"] == 1
    assert cell["locked_count"] == 1
    assert cell["scheduled_min"] == 45


def test_completed_homework_due_before_the_grid_is_not_overdue(alice: TestClient) -> None:
    assert (
        put_assignment(
            alice, assignment(due="2026-08-15T23:59", completed=True, completed_at="2026-08-14T20:00")
        ).status_code
        == 200
    )
    body = get_month(alice).json()
    assert body["overdue"] == []
    assert body["deadlines"] == []


def test_month_rejects_unicode_digits(alice: TestClient) -> None:
    # \d would match these and int() would accept them; the label must be ASCII.
    for value in ("\u0662\u0660\u0662\u0666-\u0660\u0669", "\uff12\uff10\uff12\uff16-\uff10\uff19"):
        response = alice.get(f"/api/month?month={value}")
        assert response.status_code == 422, value
        assert response.json()["detail"] == MONTH_RULE


def test_month_rejects_a_malformed_label(alice: TestClient) -> None:
    assert alice.get("/api/month").status_code == 422
    for value in ("2026-09-01", "2026-9", "2026-13", "1999-12", "2100-01"):
        response = alice.get(f"/api/month?month={value}")
        assert response.status_code == 422, value
        assert response.json()["detail"] == MONTH_RULE


def test_month_requires_a_session(client: TestClient) -> None:
    assert client.get(f"/api/month?month={MONTH}").status_code == 401


def test_month_does_not_show_another_accounts_work(app: FastAPI, alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    assert save_week(alice, [school()]).status_code == 200
    with TestClient(app) as bob:
        assert (
            bob.post(
                "/api/auth/register", json={"username": "bob", "password": PASSWORD}, headers=WRITE
            ).status_code
            == 201
        )
        body = get_month(bob).json()
        assert body["deadlines"] == []
        assert body["projects"] == []
        assert day_on(body, "2026-09-14")["scheduled_min"] == 0


def test_january_2000_clips_the_leading_week(alice: TestClient) -> None:
    body = get_month(alice, "2000-01").json()
    assert body["grid_start"] == "2000-01-01"
    assert body["days"][0]["date"] == "2000-01-01"
    assert body["days"][0]["week_start"] == "1999-12-27"
    assert body["days"][0]["in_month"] is True


def test_december_2099_clips_the_trailing_week(alice: TestClient) -> None:
    body = get_month(alice, "2099-12").json()
    assert body["grid_end"] == "2099-12-31"
    assert body["days"][-1]["date"] == "2099-12-31"
    assert body["days"][-1]["week_start"] == "2099-12-28"
    assert body["days"][-1]["in_month"] is True


def test_an_untimed_deadline_sorts_after_a_morning_one_on_the_same_date(alice: TestClient) -> None:
    assert put_assignment(alice, assignment("allday", title="All day", due="2026-09-15")).status_code == 200
    assert (
        put_assignment(alice, assignment("morning", title="Morning", due="2026-09-15T09:00")).status_code
        == 200
    )
    body = get_month(alice).json()
    assert [item["id"] for item in body["deadlines"]] == ["morning", "allday"]
    assert day_on(body, "2026-09-15")["due_ids"] == ["morning", "allday"]


def test_blank_notes_do_not_turn_a_deadline_into_a_project(alice: TestClient) -> None:
    """Spaces and newlines are not notes, so they must not promote a plain deadline."""
    assert put_assignment(alice, assignment(notes="   \n\t  ")).status_code == 200
    body = get_month(alice).json()
    assert body["projects"] == []
    assert [item["id"] for item in body["deadlines"]] == ["hw-essay"]


def test_a_repeating_block_appears_on_each_of_its_dates_with_the_same_id(alice: TestClient) -> None:
    assert save_week(alice, [school()]).status_code == 200
    body = get_month(alice).json()
    chip = {
        "id": "school",
        "title": "School",
        "start": "08:00",
        "duration_min": 390,
        "category": "School",
        "kind": "locked",
        "assignment_id": None,
        "repeats": True,
        "pinned": False,
        "completed": False,
    }
    for label in ("2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"):
        assert day_on(body, label)["blocks"] == [chip]
    assert day_on(body, "2026-09-19")["blocks"] == []


def test_pinned_homework_appears_with_its_assignment_id(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    placed = session("s-tue", 1, "16:00", pinned=True)
    assert save_week(alice, [placed]).status_code == 200
    tuesday = day_on(get_month(alice).json(), "2026-09-15")
    assert tuesday["blocks"] == [
        {
            "id": "s-tue",
            "title": "Essay",
            "start": "16:00",
            "duration_min": 60,
            "category": "Homework",
            "kind": "flexible",
            "assignment_id": "hw-essay",
            "repeats": False,
            "pinned": True,
            "completed": False,
        }
    ]


def test_homework_without_a_time_is_not_in_blocks(alice: TestClient) -> None:
    assert put_assignment(alice, assignment()).status_code == 200
    waiting = session("s-tue", 1, "16:00")
    del waiting["start"]
    assert save_week(alice, [waiting]).status_code == 200
    body = get_month(alice).json()
    assert day_on(body, "2026-09-15")["blocks"] == []
    assert body["unscheduled"] == {"session_count": 1, "minutes": 60}


def test_blocks_on_a_date_are_in_start_then_title_order(alice: TestClient) -> None:
    assert (
        save_week(
            alice,
            [
                {
                    "id": "late-z",
                    "title": "Yoga",
                    "kind": "locked",
                    "duration_min": 45,
                    "days": [0],
                    "start": "18:00",
                    "category": "exercise",
                },
                {
                    "id": "early-b",
                    "title": "Band",
                    "kind": "locked",
                    "duration_min": 30,
                    "days": [0],
                    "start": "07:00",
                    "category": "extra",
                },
                {
                    "id": "early-a",
                    "title": "Art",
                    "kind": "locked",
                    "duration_min": 30,
                    "days": [0],
                    "start": "07:00",
                    "category": "extra",
                },
            ],
        ).status_code
        == 200
    )
    titles = [item["title"] for item in day_on(get_month(alice).json(), "2026-09-14")["blocks"]]
    assert titles == ["Art", "Band", "Yoga"]


def test_a_block_on_the_last_sunday_and_the_next_month_week_start_stay_on_those_dates(
    alice: TestClient,
) -> None:
    """September's grid ends Sunday 2026-10-04. October's weeks begin Monday 2026-09-28."""
    sunday = {
        "id": "sunday-club",
        "title": "Sunday club",
        "kind": "locked",
        "duration_min": 60,
        "days": [6],
        "start": "10:00",
        "category": "extra",
    }
    monday = {
        "id": "week-open",
        "title": "Week open",
        "kind": "locked",
        "duration_min": 30,
        "days": [0],
        "start": "07:00",
        "category": "extra",
    }
    assert save_week(alice, [sunday, monday], week_start="2026-09-28").status_code == 200
    september = get_month(alice, "2026-09").json()
    october = get_month(alice, "2026-10").json()
    last_sunday = day_on(september, "2026-10-04")["blocks"]
    assert [item["id"] for item in last_sunday] == ["sunday-club"]
    assert last_sunday[0]["start"] == "10:00"
    first_monday = day_on(october, "2026-09-28")["blocks"]
    assert [item["id"] for item in first_monday] == ["week-open"]
    assert first_monday[0]["start"] == "07:00"


def test_a_busy_month_stays_a_compact_read(alice: TestClient) -> None:
    """Five timed blocks a day across the grid, as a packed student week looks."""
    weeks = ("2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28")
    for week_start in weeks:
        blocks = [
            {
                "id": f"{week_start}-{day}-{slot}",
                "title": f"Club {slot}",
                "kind": "locked",
                "duration_min": 45,
                "days": [day],
                "start": f"{8 + slot:02d}:00",
                "category": "extra",
            }
            for day in range(7)
            for slot in range(5)
        ]
        assert save_week(alice, blocks, week_start=week_start).status_code == 200
    encoded = json.dumps(get_month(alice).json(), separators=(",", ":"))
    # A September week document of the same density is already tens of kilobytes; the month
    # read names chips, not whole week rows.
    assert 20_000 < len(encoded) < 80_000, len(encoded)
