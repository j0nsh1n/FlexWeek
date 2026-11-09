"""Planning overdue and left-over homework into the open week: Plan into this week keeps the one
session, leaves other blocks and other homework alone, and a failed or roomless plan adds nothing."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from backend.tests.fake_clock import CLOCK
from desktop.native.client import ApiError
from desktop.tests.blocks_helper import put_block
from desktop.tests.grid_support import qapp, signed_in, window  # noqa: F401
from desktop.tests.planner.support import (
    FRIDAY,
    SATURDAY,
    WEDNESDAY,
    overdue_this_week,
)
from desktop.tests.window_support import settled


def test_next_week_does_not_call_current_week_work_carried(qapp, window) -> None:
    session = window.session
    week = session.week_start
    monday = date.fromisoformat(week)
    CLOCK.set(datetime.combine(monday, datetime.min.time()))
    earlier = (monday - timedelta(days=7)).isoformat()
    session.load_week(earlier)
    settled(qapp, window)
    session.add_block(
        {
            "id": "old",
            "title": "Old class",
            "kind": "locked",
            "days": [0],
            "start": "08:00",
            "duration_min": 60,
        }
    )
    session.save()
    settled(qapp, window)
    session.load_week(week)
    settled(qapp, window)
    session.add_homework(
        {
            "id": "future",
            "title": "Future",
            "estimate_min": 60,
            "due": (monday + timedelta(days=6)).isoformat() + "T23:59",
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    block = next(item for item in session.blocks if item.get("assignment_id") == "future")
    assert session.hand_move(block["id"], -1, WEDNESDAY, 15 * 60, 15 * 60 + block["duration_min"])
    session.save()
    settled(qapp, window)
    session.load_week((monday + timedelta(days=7)).isoformat())
    settled(qapp, window)
    assert session.assignments["future"]["unplanned_min"] == 60
    assert session.unfinished() == []


def test_plan_overdue_reuses_the_session_and_keeps_other_blocks(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    session = window.session
    session.save_preferences({"work_windows": [{"days": [SATURDAY], "start": "10:00", "end": "14:00"}]})
    settled(qapp, window)
    session.add_block(
        {
            "id": "class",
            "title": "Class",
            "kind": "locked",
            "days": [SATURDAY],
            "start": "10:00",
            "duration_min": 60,
        }
    )
    session.save()
    settled(qapp, window)
    before_class = next(item.copy() for item in session.blocks if item["id"] == "class")
    due = session.assignments["bio"]["due"]
    session.plan_left(["bio"])
    settled(qapp, window)
    bio = [item for item in session.blocks if item.get("assignment_id") == "bio"]
    assert len(bio) == 1
    # The class ends at 11:00 and the default leaves 15 minutes after it.
    assert (bio[0]["id"], bio[0]["days"], bio[0]["start"]) == (session_id, [SATURDAY], "11:15")
    assert session.message == "Placed 1 homework block."
    assert session.assignments["bio"]["due"] == due
    assert next(item for item in session.blocks if item["id"] == "class") == before_class
    session.plan_left(["bio"])
    settled(qapp, window)
    assert len([item for item in session.blocks if item.get("assignment_id") == "bio"]) == 1
    session.add_block(
        {
            "id": "lunch",
            "title": "Lunch",
            "kind": "locked",
            "days": [SATURDAY],
            "start": "13:00",
            "duration_min": 30,
        }
    )
    session.save()
    settled(qapp, window)
    session.reload()
    settled(qapp, window)
    bio = next(item for item in session.blocks if item["id"] == session_id)
    assert (bio["days"], bio["start"]) == ([SATURDAY], "11:15")
    session.add_homework({**session.assignments["bio"], "title": "Biology reading"})
    session.save()
    settled(qapp, window)
    bio = next(item for item in session.blocks if item["id"] == session_id)
    assert (bio["title"], bio["days"], bio["start"]) == ("Biology reading", [SATURDAY], "11:15")


def test_overdue_plan_with_no_room_does_not_add_an_unplaced_block(qapp, window) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    session.save_preferences({"work_windows": [{"days": [SATURDAY], "start": "10:00", "end": "11:00"}]})
    settled(qapp, window)
    session.add_block(
        {
            "id": "class",
            "title": "Class",
            "kind": "locked",
            "days": [SATURDAY],
            "start": "10:00",
            "duration_min": 60,
        }
    )
    session.save()
    settled(qapp, window)
    before = [item.copy() for item in session.blocks]
    session.plan_left(["bio"])
    settled(qapp, window)
    assert session.blocks == before
    assert session.message == "Nothing placed."
    session.reload()
    settled(qapp, window)
    assert session.blocks == before


def test_planning_the_selected_overdue_homework_leaves_other_homework_alone(qapp, window) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    monday = date.fromisoformat(session.week_start)
    due = (monday + timedelta(days=6)).isoformat() + "T23:59"
    for key in ("other", "waiting"):
        session.add_homework(
            {"id": key, "title": key.title(), "estimate_min": 60, "due": due, "revision": 0}
        )
    session.save()
    settled(qapp, window)
    other = next(item for item in session.blocks if item.get("assignment_id") == "other")
    waiting = next(item for item in session.blocks if item.get("assignment_id") == "waiting")
    assert session.hand_move(other["id"], -1, SATURDAY, 12 * 60, 13 * 60)
    session.delete_block(waiting["id"])
    session.save()
    settled(qapp, window)
    before_other = next(item.copy() for item in session.blocks if item["id"] == other["id"])
    before_ids = {item["id"] for item in session.blocks}
    session.plan_left(["bio"])
    settled(qapp, window)
    assert {item["id"] for item in session.blocks} == before_ids
    assert next(item for item in session.blocks if item["id"] == other["id"]) == before_other

    bio = next(item for item in session.blocks if item.get("assignment_id") == "bio")
    assert (bio["days"], bio["start"]) == ([SATURDAY], "10:00")
    session.plan_left(["bio"])
    settled(qapp, window)
    assert {item["id"] for item in session.blocks} == before_ids
    assert next(item for item in session.blocks if item["id"] == other["id"]) == before_other


def test_overdue_homework_still_asks_for_the_hour_that_never_had_a_time(qapp, window) -> None:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    due = (monday + timedelta(days=FRIDAY)).isoformat() + "T23:59"
    session.add_homework({"id": "essay", "title": "Essay", "due": due, "estimate_min": 120, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    block["duration_min"] = 60
    session._touch()
    assert session.hand_move(block["id"], -1, WEDNESDAY, 15 * 60, 15 * 60 + block["duration_min"])
    session.save()
    settled(qapp, window)
    saturday = datetime.fromisoformat(session.week_start) + timedelta(days=SATURDAY, hours=10)
    CLOCK.set(saturday)
    session.week_changed.emit()
    settled(qapp, window)
    item = next(row for row in session.unfinished() if row["id"] == "essay")
    assert (item["left_over_state"], item["remaining_min"]) == ("overdue", 120)
    # Past its deadline it is in Unfinished, and its hour that never had a time still asks for one this
    # week (Jonathan, 2026-11-07); the missed Wednesday hour is not counted again.
    assert session.homework_time_needed() == [
        {"assignment_id": "essay", "title": "Essay", "minutes": 60, "period": "this_week"}
    ]


def test_plan_overdue_moves_a_future_session(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    session = window.session
    session.save_preferences({"work_windows": [{"days": [SATURDAY], "start": "10:00", "end": "16:00"}]})
    settled(qapp, window)
    put_block(session, session_id, SATURDAY, 14 * 60, 15 * 60)
    session.add_block(
        {
            "id": "class",
            "title": "Class",
            "kind": "locked",
            "days": [SATURDAY],
            "start": "10:00",
            "duration_min": 60,
        }
    )
    session.save()
    settled(qapp, window)
    session.plan_left(["bio"])
    settled(qapp, window)
    bio = next(item for item in session.blocks if item["id"] == session_id)
    # The class ends at 11:00 and the default leaves 15 minutes after it.
    assert (bio["days"], bio["start"]) == ([SATURDAY], "11:15")
    assert session.message == "Placed 1 homework block."
    assert "prefer_earliest" not in bio


def test_an_overdue_plan_survives_the_next_edit(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    session = window.session
    session.save_preferences({"work_windows": [{"days": [SATURDAY], "start": "10:00", "end": "14:00"}]})
    settled(qapp, window)
    session.add_block(
        {
            "id": "class",
            "title": "Class",
            "kind": "locked",
            "days": [SATURDAY],
            "start": "10:00",
            "duration_min": 60,
        }
    )
    session.save()
    settled(qapp, window)
    session.plan_left(["bio"])
    settled(qapp, window)
    session.add_block(
        {
            "id": "lunch",
            "title": "Lunch",
            "kind": "locked",
            "days": [SATURDAY],
            "start": "13:00",
            "duration_min": 30,
        }
    )
    session.save()
    settled(qapp, window)
    bio = next(item for item in session.blocks if item["id"] == session_id)
    # The class ends at 11:00 and the default leaves 15 minutes after it.
    assert (bio["days"], bio["start"]) == ([SATURDAY], "11:15")


def test_a_failed_overdue_plan_request_does_not_leave_a_new_block(qapp, window, monkeypatch) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    before = [item.copy() for item in session.blocks]
    request = session.client.request

    def fail_plan(method, path, payload, ok, err):
        if path == "/api/solve":
            err(ApiError(503, "The planner is unavailable."))
        else:
            request(method, path, payload, ok, err)

    monkeypatch.setattr(session.client, "request", fail_plan)
    session.plan_left(["bio"])
    settled(qapp, window)
    assert session.blocks == before
    assert session.message == "The planner is unavailable."
