"""The week the design tests share (dragging, zoom, Month in a design): School on weekdays, the History
essay put down on Thursday 19:00, and a Math worksheet that still needs a time, with the clock held on
Thursday 10:00. Built on a light window from desktop.tests.light_app."""

# ruff: noqa: E402
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.layouts.base import LayoutView
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until

SIZE = (1280, 860)


def spin(qapp: QApplication, rounds: int = 10) -> None:
    """Let the events already waiting (layouts, queued redraws) run; nothing here waits on a time."""
    for _ in range(rounds):
        qapp.processEvents()


def settled(qapp: QApplication, window: NativeWindow) -> None:
    """No request is out, nothing is unsaved, and no reply is on its way to the window."""

    def quiet() -> bool:
        session = window.session
        return not session.busy and not session.dirty and not getattr(session.client, "pending", 0)

    wait_until(qapp, quiet, what="the window to finish saving")
    spin(qapp, 5)
    wait_until(qapp, quiet, what="the window to finish saving")


def session_of(window: NativeWindow, assignment_id: str) -> dict:
    return next(block for block in window.session.blocks if block.get("assignment_id") == assignment_id)


def placed(window: NativeWindow, assignment_id: str) -> tuple[list[int], str | None, bool]:
    block = session_of(window, assignment_id)
    return list(block["days"]), block.get("start"), bool(block.get("pinned"))


def plan_week(qapp: QApplication, made: NativeWindow) -> NativeWindow:
    """Fill the open week as described above and hold the clock on Thursday 10:00."""
    session = made.session
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=10)
    CLOCK.set(thursday)
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    due = sunday_due(session.week_start)
    for key, title in (("essay", "History essay"), ("math", "Math worksheet")):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, made)
    session.add_block({**session_of(made, "essay"), "start": "19:00", "days": [3]})
    session.save()
    settled(qapp, made)
    return made


def use(qapp: QApplication, window: NativeWindow, main: str, day: str = "one") -> LayoutView:
    """Show `main` as the window's main view and return it."""
    window._layout = sanitize_layout({"main": main, "day": day})
    window._apply_appearance()
    window._on_week()
    spin(qapp)
    shown = window.planner.currentWidget()
    assert isinstance(shown, LayoutView)
    return shown


def named(view: QWidget, name: str) -> QWidget:
    found = view.findChild(QWidget, name)
    assert found is not None, name
    return found
