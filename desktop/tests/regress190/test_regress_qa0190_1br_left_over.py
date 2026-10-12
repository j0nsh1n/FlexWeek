"""Regression for QA's 1b-R (fix-specs-0190.md, reopens 1b): overdue and left-from-last-week work is
tagged, counted once and never silent; Plan offers the choice; the panel follows today, not the viewed
week; the word "Unfinished" goes.

Window level with a held clock (`session.now_ms`). Scenario "overdue" is Assistant Local's: Bio reading
placed Wednesday 3:15 PM of the open week, due Friday, not ticked, clock Saturday 10:00. Scenario "left"
is our 0.18.4 item 1b one (a Lab report session left in last week, due next Wednesday).
Not covered: rule 7's look of the tag (no tag exists yet to measure) and rule 6's timer at the deadline
(Fri 23:59 -> Sat 00:01 without a refresh), which needs the fix's timer to drive.
Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.tests.grid_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_in,
    signed_out,
    wait_until,
    window,
)
from desktop.tests.regress184.test_regress_item1b_unfinished_past_week import (
    left_in_week_one,
    more_unfinished_row,
)

WEDNESDAY, FRIDAY, SATURDAY = 2, 4, 5
KNOWN_TAG = "known failure (1b-R.1/A25): the week list row and the block say nothing about overdue"
KNOWN_SIDE = "known failure (1b-R.6/T-W36): the sidebar says 'Everything has a time.' with 1 overdue"
KNOWN_MORE = "known failure (1b-R.3/.6): More reads 'Unfinished · None left' with 1 overdue this week"
KNOWN_FOCUS = "known failure (1b-R.6): focus_candidates takes no clock; it offers the past overdue session"
KNOWN_CHOICE = "known failure (1b-R.5): Plan with overdue work runs at once, no Plan them / I did these"
KNOWN_TODAY = "known failure (1b-R.9): the left-over panel follows the viewed week and hides on Today"
KNOWN_WORD = "known failure (1b-R glossary): More still says 'Unfinished'"


def overdue_this_week(qapp, window) -> str:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    due = (monday + timedelta(days=FRIDAY)).isoformat() + "T23:59"
    session.add_homework({"id": "bio", "title": "Bio reading", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(b for b in session.blocks if b.get("assignment_id") == "bio")
    assert session.place_session(block["id"], WEDNESDAY, 15 * 60 + 15)
    session.save()
    settled(qapp, window)
    saturday = datetime.fromisoformat(session.week_start) + timedelta(days=SATURDAY, hours=10)
    session.now_ms = lambda: int(saturday.timestamp() * 1000)
    session.week_changed.emit()
    settled(qapp, window)
    return block["id"]


def shown_texts(window) -> list[str]:
    return [w.text() for w in window.findChildren(QLabel) if w.isVisible() and w.text()]


@pytest.mark.xfail(strict=True, reason=KNOWN_TAG)
def test_1br_the_overdue_session_says_overdue_in_the_week_list(qapp, window) -> None:
    overdue_this_week(qapp, window)
    listing = window.week_access_list
    rows = [listing.item(i).text() for i in range(listing.count()) if "Bio" in listing.item(i).text()]
    assert rows and all("overdue" in row.lower() for row in rows), rows


@pytest.mark.xfail(strict=True, reason=KNOWN_SIDE)
def test_1br_the_sidebar_counts_the_overdue_session(qapp, window) -> None:
    overdue_this_week(qapp, window)
    texts = shown_texts(window)
    assert "Everything has a time." not in texts and any("1 overdue" in t for t in texts), texts


@pytest.mark.xfail(strict=True, reason=KNOWN_MORE)
def test_1br_more_counts_the_overdue_session(qapp, window) -> None:
    overdue_this_week(qapp, window)
    _enabled, words = more_unfinished_row(window)
    assert "Overdue" in words and "1" in words, words


@pytest.mark.xfail(strict=True, reason=KNOWN_WORD)
def test_1br_more_says_left_from_last_week_not_unfinished(qapp, window) -> None:
    left_in_week_one(qapp, window)
    _enabled, words = more_unfinished_row(window)
    assert "Unfinished" not in words and "Left from last week" in words, words


@pytest.mark.xfail(strict=True, reason=KNOWN_FOCUS)
def test_1br_the_focus_timer_does_not_offer_the_past_overdue_session(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    offered = window.session.focus_tasks()
    ids = [c.get("blockId") or c.get("block_id") or c.get("id") for c in offered]
    assert session_id not in ids, offered


@pytest.mark.xfail(strict=True, reason=KNOWN_CHOICE)
def test_1br_plan_with_overdue_work_asks_first(qapp, window) -> None:
    overdue_this_week(qapp, window)
    asked: list[str] = []

    def look() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is not None:
            asked.append(" ".join(b.text() for b in sheet.findChildren(QPushButton)))
            sheet.reject()

    QTimer.singleShot(300, look)
    window.findChild(QPushButton, "solveButton").click()
    for _ in range(12):
        QTest.qWait(50)
    settled(qapp, window)
    assert asked and "Plan them" in asked[0] and "I did these" in asked[0], asked


def test_1br_guard_plan_never_moves_the_overdue_session(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    window.session.solve()
    wait_until(qapp, lambda: not window.session.planning and not window.session.busy)
    settled(qapp, window)
    bio = next(b for b in window.session.blocks if b["id"] == session_id)
    assert (bio.get("days"), bio.get("start")) == ([WEDNESDAY], "15:15")


@pytest.mark.xfail(strict=True, reason=KNOWN_TODAY)
def test_1br_the_overdue_panel_still_shows_after_viewing_next_week_and_pressing_today(qapp, window) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    week = session.week_start
    later = (date.fromisoformat(week) + timedelta(days=7)).isoformat()
    for target in (later, week):
        session.load_week(target)
        wait_until(qapp, lambda target=target: session.week_start == target and not session.busy)
        settled(qapp, window)
    assert window.unfinished_panel.isVisible(), "the panel went away on the current week"
