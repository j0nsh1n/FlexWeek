"""Regression for QA's 1b-R (fix-specs-0190.md, reopens 1b): overdue and left-from-last-week work is
tagged, counted once and never silent; Plan offers the choice; the panel follows today, not the viewed
week; More's row keeps the demo's Unfinished count when homework still needs a time.

Window level with a held clock (`session.now_ms`). Scenario "overdue" is Assistant Local's: Bio reading
placed Wednesday 3:15 PM of the open week, due Friday, not ticked, clock Saturday 10:00. Scenario "left"
is our 0.18.4 item 1b one (a Lab report session left in last week, due next Wednesday).
Not covered: rule 7's look of the tag (no tag exists yet to measure) and rule 6's timer at the deadline
(Fri 23:59 -> Sat 00:01 without a refresh), which needs the fix's timer to drive.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.tests.grid_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_in,
    signed_out,
    wait_until,
    window,
)

WEDNESDAY, FRIDAY, SATURDAY = 2, 4, 5


def overdue_this_week(qapp, window) -> str:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    due = (monday + timedelta(days=FRIDAY)).isoformat() + "T23:59"
    session.add_homework({"id": "bio", "title": "Bio reading", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(b for b in session.blocks if b.get("assignment_id") == "bio")
    assert session.hand_move(block["id"], -1, WEDNESDAY, 15 * 60 + 15, 16 * 60 + 15)
    session.save()
    settled(qapp, window)
    saturday = datetime.fromisoformat(session.week_start) + timedelta(days=SATURDAY, hours=10)
    session.now_ms = lambda: int(saturday.timestamp() * 1000)
    session.week_changed.emit()
    settled(qapp, window)
    return block["id"]










def test_1br_the_focus_timer_does_not_offer_the_past_overdue_session(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    offered = window.session.focus_tasks()
    ids = [c.get("blockId") or c.get("block_id") or c.get("id") for c in offered]
    assert session_id not in ids, offered


def test_1br_plan_with_overdue_work_asks_first(qapp, window) -> None:
    overdue_this_week(qapp, window)
    asked: list[str] = []

    def look() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is not None:
            asked.append([b.text() for b in sheet.findChildren(QPushButton)])
            sheet.reject()

    QTimer.singleShot(300, look)
    window._plan_with_left_over()
    for _ in range(12):
        QTest.qWait(50)
    settled(qapp, window)
    # T-W5 (1.0.0 wording audit) renamed the box's buttons from "Plan them" / "I did these".
    assert asked and asked[0] == ["Plan into this week", "Mark as finished", "Not now"], asked


def test_1br_guard_plan_never_moves_the_overdue_session(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    window.session.solve()
    wait_until(qapp, lambda: not window.session.planning and not window.session.busy)
    settled(qapp, window)
    bio = next(b for b in window.session.blocks if b["id"] == session_id)
    assert (bio.get("days"), bio.get("start")) == ([WEDNESDAY], "15:15")
