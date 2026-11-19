"""Overdue and left-over homework as the student reads and uses it: the chip and the planning box, the
More badge, the Unfinished rows, the week list and the focus list. Held-clock scenario: Bio reading
placed Wednesday 3:15 PM of the open week, due Friday 23:59, not ticked, clock Saturday 10:00."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.weekmodel import length_label, range_label
from desktop.tests.grid_support import qapp, signed_in, window  # noqa: F401
from desktop.tests.planner.support import (
    overdue_this_week,
)
from desktop.tests.window_support import settled


def test_the_chip_and_the_planning_box_say_plan_into_this_week_and_mark_as_finished(qapp, window) -> None:
    overdue_this_week(qapp, window)
    assert window.findChild(QPushButton, "leftPlan").text() == "Plan into this week"
    assert window.findChild(QPushButton, "leftDone").text() == "Mark as finished"
    asked: list[list[str]] = []

    def look() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is None:
            QTimer.singleShot(0, look)
            return
        asked.append([b.text() for b in sheet.findChildren(QPushButton)])
        sheet.reject()

    # The planning box runs its own event loop; the timer fires inside it and closes it.
    QTimer.singleShot(0, look)
    window.findChild(QPushButton, "solveButton").click()
    settled(qapp, window)
    assert asked and "Plan into this week" in asked[0] and "Mark as finished" in asked[0], asked
    assert "I did these" not in asked[0] and "Plan them" not in asked[0], asked


def test_the_week_list_row_says_overdue_with_the_due_date(qapp, window) -> None:
    overdue_this_week(qapp, window)
    listing = window.week_access_list
    rows = [
        listing.item(i).text()
        for i in range(listing.count())
        if listing.item(i).text().startswith("Wednesday: Bio reading, ")
    ]
    due = date.fromisoformat(window.session.assignments["bio"]["due"][:10])
    due_words = f"Overdue, was due {due.strftime('%a')} {due.day} {due.strftime('%b')}"
    times = range_label(15 * 60 + 15, 16 * 60 + 15)
    expected = f"Wednesday: Bio reading, {times} · {length_label(60)} · {due_words} · Pinned"
    assert rows == [expected]


def test_the_overdue_focus_row_starts_from_the_homework(qapp, window) -> None:
    block_id = overdue_this_week(qapp, window)
    row = next(item for item in window.session.focus_tasks() if item["title"] == "Bio reading, overdue")
    assert row["id"] == "bio" and row["id"] != block_id
    assert window.session.start_focus(row["id"], row["day"]) is True
    focus = window.session.focus
    assert focus["title"] == "Bio reading, overdue"
    assert focus["assignmentId"] == "bio" and focus["blockId"] is None
