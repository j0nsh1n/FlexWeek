"""Plan puts a homework session in the week and says what it placed; when a homework has no time, the
reason it gives is the latest one."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import due_on, session_in_the_planned_week, soccer
from desktop.tests.planner.school_week import (
    open_the_school_week,
    plan_the_school_week,
    stored,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_plan_places_the_session_and_explains_the_result(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(soccer())
    session.add_homework(
        {"id": "essay", "title": "Essay", "due": due_on(session, 4), "estimate_min": 60, "revision": 0}
    )
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)
    session.solve()
    wait_until(qapp, lambda: session.trace is not None and not session.busy)
    placed_titles = {block["title"] for block in session.trace["placed"]}
    assert placed_titles == {"Soccer", "Essay"}
    assert session.trace["unplaced"] == []
    assert session.trace["complete"] is True
    essay = next(block for block in session.blocks if block["title"] == "Essay")
    assert essay.get("start")


def test_the_reason_homework_has_no_time_is_the_latest_one(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """A club over Monday afternoon takes Math's 15:15, and "no longer fits Monday at 15:15" is right.
    If Find a new time then finds nothing either, that sentence was kept and came back after the next
    edit, although the real reason by then was that Monday had no room before the deadline."""
    session = open_the_school_week(open_light, clock)
    wait_until(qapp, lambda: session.preferences is not None)
    # Monday is full from 06:00 to 23:00. Without this, the open night would give the homework a time.
    assert session.save_availability(
        [],
        None,
        [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "06:00", "end": "23:00"}],
    )
    wait_until(
        qapp,
        lambda: not session.busy and (session.preferences or {}).get("work_windows"),
    )
    plan_the_school_week(qapp, session)
    for block_id, title, start, minutes in (("club", "Club", "15:00", 360), ("swim", "Swim", "06:00", 120)):
        session.add_block(
            {
                "id": block_id,
                "title": title,
                "kind": "locked",
                "start": start,
                "duration_min": minutes,
                "days": [0],
            }
        )
    math = next(block["id"] for block in session.blocks if block.get("assignment_id") == "math")
    assert "no longer fits" in session.needs_time[math]
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    session.solve(only={math})
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    assert stored(session, math).get("start") is None
    session.add_block(
        {"id": "gym", "title": "Gym", "kind": "locked", "start": "10:00", "duration_min": 60, "days": [5]}
    )
    explained = (session.plan_notes() or {}).get("explanations") or []
    notes = {item["block_id"]: item["message"] for item in explained}
    assert math in notes
    assert "no longer fits" not in notes[math], notes[math]
