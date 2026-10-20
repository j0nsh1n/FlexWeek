"""Regression for fix-specs.md item 1b: homework left unfinished in a past week is invisible to Plan and
to More.

The spec's guard: homework due Wednesday of week 2 with its only session on Friday of week 1, never
ticked; open week 2 (clock: Monday 07:00 of week 2): More shows 1 unfinished; Plan leaves the session
where it is and shows the "1 left from last week" chip; "Plan into this week" places it in week 2 before
Wednesday; in a second run "Mark as finished" marks it done, More shows 0 and Plan then places nothing new.

The chip and its buttons follow the 1.0.0 decision: "1 left from last week" is hidden while the
"Overdue and left from last week" panel is open, so the tests hide that panel before finding the chip.
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
PLAN_IT = "Plan into this week"
FINISHED = "Mark as finished"


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
    assert session.hand_move(block["id"], -1, FRIDAY, 16 * 60, 17 * 60)
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


def hide_the_panel(qapp, window) -> None:
    hide = window.findChild(QPushButton, "unfinishedDismiss")
    if hide is not None and hide.isVisible():
        hide.click()
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
    hide_the_panel(qapp, window)
    chip = [label.text() for label in window.findChildren(QLabel) if label.isVisible()]
    assert "1 left from last week" in chip, chip
    assert visible_button(window, PLAN_IT) and visible_button(window, FINISHED)


def test_plan_them_places_it_in_week_two_before_wednesday(qapp, window) -> None:
    left_in_week_one(qapp, window)
    plan(qapp, window)
    hide_the_panel(qapp, window)
    button = visible_button(window, PLAN_IT)
    assert button is not None, f"no {PLAN_IT}"
    button.click()
    settled(qapp, window)
    placed = [b for b in lab_sessions(window) if b.get("start")]
    assert placed and all(b["days"][0] < WEDNESDAY or b["days"] == [WEDNESDAY] for b in placed), placed


def test_i_did_these_marks_it_done_more_shows_none_and_plan_places_nothing(qapp, window) -> None:
    left_in_week_one(qapp, window)
    plan(qapp, window)
    hide_the_panel(qapp, window)
    button = visible_button(window, FINISHED)
    assert button is not None, f"no {FINISHED}"
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


def test_the_past_week_tag_survives_editing_the_assignment(qapp, window) -> None:
    left_in_week_one(qapp, window)
    session = window.session
    session.add_homework({**session.assignments["lab"], "title": "Updated lab report"})
    session.save()
    settled(qapp, window)

    item = next(item for item in session.unfinished() if item["id"] == "lab")
    assert item["left_over_state"] == "left_from_last_week"
