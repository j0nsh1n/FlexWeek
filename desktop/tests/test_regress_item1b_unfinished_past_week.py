"""Regression for fix-specs.md item 1b: homework left unfinished in a past week is invisible to Plan and
to More.

The spec's guard: homework due Wednesday of week 2 with its only session on Friday of week 1, never
ticked; open week 2 (clock: Monday 07:00 of week 2): More shows 1 unfinished; Plan leaves the session
where it is and shows the "1 unfinished from last week" chip; "Plan them" places it in week 2 before
Wednesday; in a second run "I did these" marks it done, More shows 0 and Plan then places nothing new.

The chip and its two buttons are found by their words (UI Designer's: "... unfinished from last
week", "Plan them", "I did these"), design-agnostic.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel, QPushButton

from desktop.native.window import NONE_UNFINISHED
from desktop.tests.grid_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_in,
    signed_out,
    wait_until,
    window,
)

FRIDAY, WEDNESDAY = 4, 2


def left_in_week_one(qapp, window) -> tuple[str, str]:
    """Week 1 (the open week): the Lab report, due Wednesday of week 2, its one session on Friday 16:00
    of week 1, not ticked. Then the clock moves to Monday 07:00 of week 2 and week 2 is opened.
    Returns (week 1, week 2)."""
    session = window.session
    week1 = session.week_start
    week2 = (date.fromisoformat(week1) + timedelta(days=7)).isoformat()
    due = (date.fromisoformat(week2) + timedelta(days=WEDNESDAY)).isoformat() + "T23:59"
    session.add_homework({"id": "lab", "title": "Lab report", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(b for b in session.blocks if b.get("assignment_id") == "lab")
    assert session.place_session(block["id"], FRIDAY, 16 * 60)
    session.save()
    settled(qapp, window)
    monday_7 = datetime.fromisoformat(week2) + timedelta(hours=7)
    session.now_ms = lambda: int(monday_7.timestamp() * 1000)
    session.load_week(week2)
    wait_until(qapp, lambda: session.week_start == week2 and not session.busy)
    settled(qapp, window)
    return week1, week2


def more_unfinished_row(window) -> tuple[bool, str]:
    window._sync_more_menu()
    for action, button in window._more_pairs:
        if button.objectName() == "unfinishedOpen":
            return action.isEnabled(), action.text()
    raise AssertionError("More has no Unfinished row")


def lab_sessions(window) -> list[dict]:
    return [b for b in window.session.blocks if b.get("assignment_id") == "lab"]


def visible_button(window, words: str) -> QPushButton | None:
    for button in window.findChildren(QPushButton):
        if button.isVisible() and button.text().replace("&", "") == words:
            return button
    return None


def plan(qapp, window) -> None:
    window.session.solve()
    wait_until(qapp, lambda: not window.session.planning and not window.session.busy)
    settled(qapp, window)


def test_more_counts_the_session_left_in_last_week(qapp, window) -> None:
    left_in_week_one(qapp, window)
    enabled, words = more_unfinished_row(window)
    assert enabled and NONE_UNFINISHED not in words and "1" in words, words


def test_plan_never_moves_last_weeks_session_on_its_own(qapp, window) -> None:
    """Guard (Timmy): Plan leaves an un-ticked past-week session where it is; nothing lands in week 2."""
    left_in_week_one(qapp, window)
    plan(qapp, window)
    assert [b for b in lab_sessions(window) if b.get("start")] == []


def test_plan_shows_the_unfinished_from_last_week_chip(qapp, window) -> None:
    left_in_week_one(qapp, window)
    plan(qapp, window)
    chip = [
        label.text() for label in window.findChildren(QLabel)
        if label.isVisible() and "left from last week" in label.text()
    ]
    assert chip and visible_button(window, "Plan them") and visible_button(window, "I did these")


def test_plan_them_places_it_in_week_two_before_wednesday(qapp, window) -> None:
    left_in_week_one(qapp, window)
    plan(qapp, window)
    button = visible_button(window, "Plan them")
    assert button is not None, "no Plan them"
    button.click()
    settled(qapp, window)
    placed = [b for b in lab_sessions(window) if b.get("start")]
    assert placed and all(b["days"][0] < WEDNESDAY or b["days"] == [WEDNESDAY] for b in placed), placed


def test_i_did_these_marks_it_done_more_shows_none_and_plan_places_nothing(qapp, window) -> None:
    left_in_week_one(qapp, window)
    plan(qapp, window)
    button = visible_button(window, "I did these")
    assert button is not None, "no I did these"
    button.click()
    settled(qapp, window)
    enabled, words = more_unfinished_row(window)
    assert not enabled and NONE_UNFINISHED in words
    plan(qapp, window)
    assert [b for b in lab_sessions(window) if b.get("start")] == []


def test_left_over_classification_uses_the_session_clock(qapp, window) -> None:
    """Changing the held clock moves the same session from carried to overdue."""
    _week1, week2 = left_in_week_one(qapp, window)
    session = window.session
    item = next(item for item in session.unfinished() if item["id"] == "lab")
    assert item["left_over_state"] == "left_from_last_week"
    after_due = datetime.fromisoformat(week2) + timedelta(days=WEDNESDAY + 1, minutes=1)
    session.now_ms = lambda: int(after_due.timestamp() * 1000)
    window._sync_more_menu()
    session.week_changed.emit()
    settled(qapp, window)
    item = next(item for item in session.unfinished() if item["id"] == "lab")
    assert item["left_over_state"] == "overdue"
