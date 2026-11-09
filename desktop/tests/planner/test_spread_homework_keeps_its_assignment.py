"""Spreading a homework over the week adds sessions of the same assignment, and the preview says how
much time is ready and when it is due."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.calendar import sunday_due
from desktop.native.weekmodel import due_label
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import session_in_the_planned_week
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_spread_keeps_assignment_identity_across_sessions(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    due = sunday_due(session.week_start)
    session.add_homework(
        {
            "id": "project",
            "title": "Project",
            "due": due,
            "estimate_min": 180,
            "category": "assignments",
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and "project" in session.assignments)
    session.blocks = []
    session._touch("clearing sessions")
    session.save()
    wait_until(qapp, lambda: not session.busy and session.blocks == [])
    session.preview_spread("project", 60, session.week_start)
    wait_until(qapp, lambda: session.spread_preview is not None and not session.busy)
    assert session.spread_preview["rows"]
    assert all(row["block"]["assignment_id"] == "project" for row in session.spread_preview["rows"])
    # Time, not a count of sessions, and the deadline as a student says it.
    assert session.spread_preview["summary"] == (
        f"Project: 3 h ready to add before {due_label(due, session.week_start)}."
    )
    assert session.confirm_spread()
    wait_until(qapp, lambda: not session.busy)
    sessions = [block for block in session.blocks if block.get("assignment_id") == "project"]
    assert len(sessions) >= 2
