"""Overdue and left-over homework as the student reads and uses it: the chip and the planning box, the
More badge, the Unfinished rows, the week list and the focus list. Held-clock scenario: Bio reading
placed Wednesday 3:15 PM of the open week, due Friday 23:59, not ticked, clock Saturday 10:00."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from backend.tests.fake_clock import CLOCK
from desktop.native.weekmodel import length_label, range_label
from desktop.tests.grid_support import qapp, signed_in, window  # noqa: F401
from desktop.tests.planner.support import (
    FRIDAY,
    WEDNESDAY,
    left_in_week_one,
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


def test_the_more_badge_opens_the_shared_left_over_rows(qapp, window) -> None:
    left_in_week_one(qapp, window)
    window.unfinished_panel._collapse()
    window.findChild(QPushButton, "unfinishedOpen").click()
    settled(qapp, window)
    assert window.unfinished_panel.isVisible()
    row = window.unfinished_panel.list.itemWidget(window.unfinished_panel.list.item(0))
    due = date.fromisoformat(window.session.assignments["lab"]["due"][:10])
    words = (
        f"Lab report · 1 h left · due {due.strftime('%a')} {due.day} {due.strftime('%b')} "
        "· Left from last week"
    )
    assert row.accessibleName() == words
    assert row.findChild(QLabel, "unfinishedRow").text() == words
    focus = row.findChild(QPushButton, "focusUnfinished-lab")
    assert focus is not None and focus.text() == "Start focus"
    assert focus.accessibleName() == "Start focus on Lab report"


def test_the_overdue_chip_hides_with_the_unfinished_list_and_returns_when_it_is_hidden(qapp, window) -> None:
    overdue_this_week(qapp, window)
    monday = date.fromisoformat(window.session.week_start)
    due = (monday + timedelta(days=FRIDAY)).isoformat() + "T23:59"
    window.session.add_homework(
        {"id": "chem", "title": "Chem lab", "due": due, "estimate_min": 60, "revision": 0}
    )
    window.session.save()
    settled(qapp, window)
    window._on_week()
    settled(qapp, window)
    if window.unfinished_panel.isVisibleTo(window):
        window.unfinished_panel.findChild(QPushButton, "unfinishedDismiss").click()
        settled(qapp, window)
    assert window.left_chip.isVisibleTo(window)

    window.findChild(QPushButton, "unfinishedOpen").click()
    settled(qapp, window)
    assert window.unfinished_panel.isVisibleTo(window)
    assert not window.left_chip.isVisibleTo(window)
    window.session.week_changed.emit()
    settled(qapp, window)
    assert not window.left_chip.isVisibleTo(window)

    window.unfinished_panel.findChild(QPushButton, "unfinishedDismiss").click()
    settled(qapp, window)
    assert not window.unfinished_panel.isVisibleTo(window)
    assert window.left_chip.isVisibleTo(window)


@pytest.mark.parametrize("page", ["week", "settings"])
def test_the_deadline_passing_refreshes_tags_the_sidebar_and_the_focus_list(
    qapp, window, monkeypatch, page
) -> None:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    friday = monday + timedelta(days=FRIDAY)
    due = friday.isoformat() + "T23:59"
    session.add_homework({"id": "bio", "title": "Bio reading", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(item for item in session.blocks if item.get("assignment_id") == "bio")
    assert session.hand_move(block["id"], -1, WEDNESDAY, 15 * 60 + 15, 16 * 60 + 15)
    session.save()
    settled(qapp, window)
    if page == "settings":
        window._open_settings()
        settled(qapp, window)
    announcements = []
    monkeypatch.setattr(
        "desktop.native.window.announce",
        lambda widget, words, assertive=False: announcements.append((widget, words, assertive)),
    )
    before = datetime.combine(friday, datetime.min.time()).replace(hour=23, minute=58)
    after = before + timedelta(minutes=3)
    CLOCK.set(before)
    session.week_changed.emit()
    settled(qapp, window)
    assert not session.unfinished()
    assert 0 < window._deadline_tick.remainingTime() <= 61_000
    CLOCK.set(after)
    window._deadline_tick.timeout.emit()
    settled(qapp, window)
    assert session.unfinished()[0]["left_over_state"] == "overdue"
    rows = [window.week_access_list.item(i).text() for i in range(window.week_access_list.count())]
    due_words = f"Overdue, was due {friday.strftime('%a')} {friday.day} {friday.strftime('%b')}"
    times = range_label(15 * 60 + 15, 16 * 60 + 15)
    expected = f"Wednesday: Bio reading, {times} · {length_label(60)} · {due_words} · Pinned"
    bio_rows = [row for row in rows if row.startswith("Wednesday: Bio reading, ")]
    assert bio_rows == [expected]
    assert window.rail.none_waiting.text() == "Everything has a time."
    assert any(item["title"] == "Bio reading, overdue" for item in session.focus_tasks())
    target = window if page == "settings" else window.more_button
    assert target.isVisible()
    said = [item for item in announcements if item[0] is target]
    assert said == [(target, "1 overdue", False)]
    window._deadline_changed()
    settled(qapp, window)
    assert [item for item in announcements if item[0] is target] == said


def test_the_overdue_focus_row_starts_from_the_homework(qapp, window) -> None:
    block_id = overdue_this_week(qapp, window)
    row = next(item for item in window.session.focus_tasks() if item["title"] == "Bio reading, overdue")
    assert row["id"] == "bio" and row["id"] != block_id
    assert window.session.start_focus(row["id"], row["day"]) is True
    focus = window.session.focus
    assert focus["title"] == "Bio reading, overdue"
    assert focus["assignmentId"] == "bio" and focus["blockId"] is None


def test_focus_started_from_the_unfinished_list_is_restored_and_credits_the_homework(qapp, window) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    session.preferences["timer_work_min"] = 25
    window._show_unfinished()
    settled(qapp, window)
    assert window.unfinished_panel.isVisibleTo(window)
    row = window.unfinished_panel.list.itemWidget(window.unfinished_panel.list.item(0))
    button = row.findChild(QPushButton, "focusUnfinished-bio")
    assert button is not None
    assert button.accessibleName() == "Start focus on Bio reading"
    button.click()
    assert session.focus["assignmentId"] == "bio"
    session._reset_focus(persist=False)
    session._restore_focus()
    assert session.focus["title"] == "Bio reading"
    session.advance_focus(completed=True)
    settled(qapp, window)
    session.reload()
    settled(qapp, window)
    assert session.assignments["bio"]["focus_minutes"] == 25
    assert session.assignments["bio"]["focus_sessions"] == 1
    assert session.assignments["bio"]["completed"] is False
