"""A finished focus session adds its minutes to the homework once, and is not an undo step."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import session_in_the_planned_week
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_focus_credits_homework_once_and_leaves_undo_alone(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.blocks[0]["start"] = "16:00"
    session.blocks[0]["days"] = [0]
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy)
    wait_until(qapp, lambda: "essay" in session.assignments)
    undos = len(session._undo)
    assert session.start_focus(session.blocks[0]["id"], 0) is True
    clock.move(minutes=30)
    session.tick_focus()
    wait_until(qapp, lambda: not session.busy)
    wait_until(qapp, lambda: int(session.assignments["essay"].get("focus_minutes") or 0) == 30)
    assert session.assignments["essay"]["focus_sessions"] == 1
    assert session.focus is not None and session.focus["phase"] == "ended"
    assert len(session._undo) == undos
    # Later ticks, with the session over, credit nothing more.
    clock.move(minutes=20)
    session.tick_focus()
    wait_until(qapp, lambda: not session.busy)
    assert session.assignments["essay"]["focus_minutes"] == 30
    assert session.assignments["essay"]["focus_sessions"] == 1
