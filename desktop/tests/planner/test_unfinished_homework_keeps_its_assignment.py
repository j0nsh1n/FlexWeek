"""Homework left over from last week is planned again as the same assignment, not as a new one."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import session_in_the_planned_week
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_unfinished_homework_keeps_the_same_assignment(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    current = session.week_start
    previous = (date.fromisoformat(current) - timedelta(days=7)).isoformat()
    session.load_week(previous)
    wait_until(qapp, lambda: session.week_start == previous and not session.busy)
    session.add_homework(
        {
            "id": "lab",
            "title": "Lab",
            "due": previous + "T21:00",
            "estimate_min": 60,
            "category": "assignments",
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and session.revision >= 1)
    session.load_week(current)
    wait_until(qapp, lambda: session.week_start == current and not session.busy)
    wait_until(qapp, lambda: previous in session.saved_weeks)
    # Left from last week is judged against today, so the clock is in the week being viewed.
    clock.set(datetime.fromisoformat(current) + timedelta(hours=7))
    items = session.unfinished()
    assert items[0]["id"] == "lab"
    rows = session.plan_unfinished("lab")
    assert rows is not None
    assert rows[0]["block"]["assignment_id"] == "lab"
    assert session.confirm_preview(rows, label="unfinished homework")
    wait_until(qapp, lambda: not session.busy)
    assert any(block.get("assignment_id") == "lab" for block in session.blocks)
