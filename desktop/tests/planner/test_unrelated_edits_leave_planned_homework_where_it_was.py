"""Ticking one homework off, undoing it, or adding a block never moves the other homework Plan placed."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import session_in_the_planned_week, soccer
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def two_assignments(session: NativeSession) -> None:
    session.add_block(soccer())
    monday = date.fromisoformat(session.week_start)
    for key, title, day in (("math", "Math worksheet", 4), ("english", "English essay", 5)):
        session.add_homework(
            {
                "id": key,
                "title": title,
                "due": (monday + timedelta(days=day)).isoformat() + "T21:00",
                "estimate_min": 60,
                "revision": 0,
            }
        )


def test_unrelated_edits_keep_other_homework_where_it_was(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    two_assignments(session)
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    session.solve()
    wait_until(qapp, lambda: session.trace is not None and not session.busy and not session.dirty)
    before = {item["title"]: dict(item) for item in session.blocks if item.get("assignment_id")}
    assert before["Math worksheet"].get("start")
    assert before["English essay"].get("start")

    session.complete_homework("math")
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    english = next(item for item in session.blocks if item.get("assignment_id") == "english")
    assert english.get("start") == before["English essay"].get("start")
    assert list(english.get("days") or []) == list(before["English essay"].get("days") or [])
    math = next(item for item in session.blocks if item.get("assignment_id") == "math")
    assert math.get("completed") is True

    wait_until(qapp, lambda: session.can_undo())
    session.undo()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    math = next(item for item in session.blocks if item.get("assignment_id") == "math")
    english = next(item for item in session.blocks if item.get("assignment_id") == "english")
    assert math.get("completed") is not True
    assert math.get("start") == before["Math worksheet"].get("start")
    assert english.get("start") == before["English essay"].get("start")

    session.add_block(
        {
            "id": "saturday",
            "title": "Meet friends",
            "kind": "locked",
            "category": "social",
            "start": "14:00",
            "duration_min": 120,
            "days": [5],
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    later = {item["title"]: item.get("start") for item in session.blocks if item.get("assignment_id")}
    assert later["Math worksheet"] == before["Math worksheet"].get("start")
    assert later["English essay"] == before["English essay"].get("start")
