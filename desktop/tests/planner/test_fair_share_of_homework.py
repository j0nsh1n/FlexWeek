"""Work due within the coming week stays whole. Later deadlines may receive a fair share (the share's own
numbers are tested in engine/engine/tests/test_fair_share.rs); here the session passes the clock's day to
the rule and plans what it returns.

Planned on Saturday 07:00, a 2 h Science project due next Wednesday is within seven days and is not split.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp, settled  # noqa: F401

SATURDAY = 5


def plan_on_saturday(
    qapp: QApplication, window: NativeWindow, clock: FakeClock, due_in_days: int
) -> list[dict]:
    session = window.session
    week = session.week_start
    due = (date.fromisoformat(week) + timedelta(days=due_in_days)).isoformat() + "T23:59"
    session.add_homework(
        {"id": "sci", "title": "Science project", "estimate_min": 120, "revision": 0, "due": due}
    )
    session.save()
    settled(qapp, window)
    clock.set(datetime.fromisoformat(week) + timedelta(days=SATURDAY, hours=7))
    session.solve()
    finished_planning(qapp, window)
    return [b for b in session.blocks if b.get("assignment_id") == "sci"]


def finished_planning(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    wait_until(
        qapp,
        lambda: not session.planning and not session.busy and not session.dirty,
        timeout=20,
        what="Plan finished",
    )
    settled(qapp, window)


def test_due_next_wednesday_stays_whole_this_weekend(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    sessions = plan_on_saturday(qapp, window, clock, 9)  # Wednesday of next week
    placed = [b for b in sessions if b.get("start")]
    assert sum(b["duration_min"] for b in placed) == 120, sessions
    assert all(b["days"][0] >= SATURDAY for b in placed), placed
    assert not (window.session.trace or {}).get("shares")


def test_due_this_sunday_is_planned_whole(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    sessions = plan_on_saturday(qapp, window, clock, 6)
    assert sum(b["duration_min"] for b in sessions if b.get("start")) == 120, sessions
    assert not (window.session.trace or {}).get("shares")


def test_planning_again_keeps_the_same_share(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    plan_on_saturday(qapp, window, clock, 9)
    window.session.solve(everything=True)
    finished_planning(qapp, window)
    placed = [b for b in window.session.blocks if b.get("assignment_id") == "sci" and b.get("start")]
    assert sum(b["duration_min"] for b in placed) == 120, placed
