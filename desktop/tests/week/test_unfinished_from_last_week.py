"""Homework left unfinished in a past week shows in More and in Plan, and Plan never moves it alone.

The case: homework due Wednesday of week 2 whose only session is on Friday of week 1, never ticked;
week 2 is open at Monday 07:00. "1 left from last week" is hidden while the "Overdue and left from
last week" panel is open, so the tests hide that panel before finding the chip."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from backend.tests.fake_clock import CLOCK
from desktop.native.window import NONE_UNFINISHED, NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_pastnext import FRIDAY, WEDNESDAY, classic_week
from desktop.tests.window_support import qapp, settled  # noqa: F401

PLAN_IT = "Plan into this week"
FINISHED = "Mark as finished"


def left_in_week_one(qapp: QApplication, window: NativeWindow) -> tuple[str, str]:
    """Week 1 (the open week): the Lab report, due Wednesday of week 2, its one session on Friday 16:00
    of week 1, not ticked. Then the clock moves to Monday 07:00 of week 2 and week 2 is opened.
    Returns (week 1, week 2)."""
    classic_week(qapp, window)
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
    CLOCK.set(datetime.fromisoformat(week2) + timedelta(hours=7))
    session.load_week(week2)
    wait_until(qapp, lambda: session.week_start == week2 and not session.busy)
    settled(qapp, window)
    return week1, week2


def more_unfinished_row(window: NativeWindow) -> tuple[bool, str]:
    window._sync_more_menu()
    for action, button in window._more_pairs:
        if button.objectName() == "unfinishedOpen":
            return action.isEnabled(), action.text()
    raise AssertionError("More has no Unfinished row")


def lab_sessions(window: NativeWindow) -> list[dict]:
    return [b for b in window.session.blocks if b.get("assignment_id") == "lab"]


def visible_button(window: NativeWindow, words: str) -> QPushButton | None:
    for button in window.findChildren(QPushButton):
        if button.isVisible() and button.text().replace("&", "") == words:
            return button
    return None


def plan(qapp: QApplication, window: NativeWindow) -> None:
    window.session.solve()
    wait_until(qapp, lambda: not window.session.planning and not window.session.busy)
    settled(qapp, window)


def hide_the_panel(qapp: QApplication, window: NativeWindow) -> None:
    hide = window.findChild(QPushButton, "unfinishedDismiss")
    if hide is not None and hide.isVisible():
        hide.click()
        settled(qapp, window)


def test_more_counts_the_session_left_in_last_week(qapp, window) -> None:
    left_in_week_one(qapp, window)
    enabled, words = more_unfinished_row(window)
    assert enabled and NONE_UNFINISHED not in words and "1" in words, words


def test_plan_never_moves_last_weeks_session_on_its_own(qapp, window) -> None:
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


def test_marking_it_finished_empties_more_and_plan_places_nothing(qapp, window) -> None:
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


def test_left_over_session_turns_overdue_when_the_clock_passes_its_due_time(qapp, window) -> None:
    _week1, week2 = left_in_week_one(qapp, window)
    session = window.session
    item = next(item for item in session.unfinished() if item["id"] == "lab")
    assert item["left_over_state"] == "left_from_last_week"
    CLOCK.set(datetime.fromisoformat(week2) + timedelta(days=WEDNESDAY + 1, minutes=1))
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


def test_time_already_planned_this_week_is_not_left_from_last_week(qapp, window) -> None:
    """Last week's hour was never done, but the same hour now has a time on Tuesday: nothing is left
    over, so there is no line and no Plan into this week to press (audit F-009)."""
    left_in_week_one(qapp, window)
    session = window.session
    assert [item["id"] for item in session.unfinished()] == ["lab"]
    session.add_block(
        {
            "id": "lab-again",
            "title": "Lab report",
            "kind": "flexible",
            "assignment_id": "lab",
            "duration_min": 60,
            "days": [1],
            "start": "15:00",
        }
    )
    session.save()
    settled(qapp, window)
    assert session.unfinished() == []
    plan(qapp, window)
    hide_the_panel(qapp, window)
    chip = [label.text() for label in window.findChildren(QLabel) if label.isVisible()]
    assert not [text for text in chip if "left from last week" in text], chip
    assert visible_button(window, PLAN_IT) is None


def test_the_line_shows_only_the_minutes_that_still_have_no_time(qapp, window) -> None:
    """The lab report is 60 minutes and none of it is done. Half an hour of it now has a time this
    week, so the line is for the other 30 and Plan into this week places those 30."""
    left_in_week_one(qapp, window)
    session = window.session
    session.add_block(
        {
            "id": "lab-half",
            "title": "Lab report",
            "kind": "flexible",
            "assignment_id": "lab",
            "duration_min": 30,
            "days": [1],
            "start": "15:00",
        }
    )
    session.save()
    settled(qapp, window)
    assert [(item["id"], item["remaining_min"]) for item in session.unfinished()] == [("lab", 30)]
    plan(qapp, window)
    hide_the_panel(qapp, window)
    button = visible_button(window, PLAN_IT)
    assert button is not None, f"no {PLAN_IT}"
    button.click()
    settled(qapp, window)
    new_hours = [b for b in lab_sessions(window) if b["id"] != "lab-half" and b["duration_min"] == 30]
    assert new_hours, lab_sessions(window)


def test_plan_into_this_week_places_the_hour_this_week_already_holds_without_a_time(qapp, window) -> None:
    """The line lists minutes that have no time, a session waiting for one included, and pressing Plan
    into this week gives that session its time instead of saying the homework is fully planned."""
    left_in_week_one(qapp, window)
    session = window.session
    session.add_block(
        {
            "id": "lab-waiting",
            "title": "Lab report",
            "kind": "flexible",
            "assignment_id": "lab",
            "duration_min": 60,
            "days": [0, 1, 2],
        }
    )
    session.save()
    settled(qapp, window)
    assert [(item["id"], item["remaining_min"]) for item in session.unfinished()] == [("lab", 60)]
    hide_the_panel(qapp, window)
    button = visible_button(window, PLAN_IT)
    assert button is not None, f"no {PLAN_IT}"
    button.click()
    settled(qapp, window)
    assert [b for b in lab_sessions(window) if b.get("start")], lab_sessions(window)
    assert "fully planned" not in session.message, session.message
