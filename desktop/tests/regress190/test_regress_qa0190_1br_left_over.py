"""Regression for QA's 1b-R (fix-specs-0190.md, reopens 1b): overdue and left-from-last-week work is
tagged, counted once and never silent; Plan offers the choice; the panel follows today, not the viewed
week; the word "Unfinished" goes.

Window level with a held clock (`session.now_ms`). Scenario "overdue" is Assistant Local's: Bio reading
placed Wednesday 3:15 PM of the open week, due Friday, not ticked, clock Saturday 10:00. Scenario "left"
is our 0.18.4 item 1b one (a Lab report session left in last week, due next Wednesday).
Not covered: custom looks and the clock's real wake-up event; the painter guard covers built-in looks and
the timer guard invokes the same timeout path the real deadline uses.
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


def test_1br_the_overdue_session_says_overdue_in_the_week_list(qapp, window) -> None:
    overdue_this_week(qapp, window)
    listing = window.week_access_list
    rows = [listing.item(i).text() for i in range(listing.count()) if "Bio" in listing.item(i).text()]
    due = date.fromisoformat(window.session.assignments["bio"]["due"][:10])
    due_words = f"Overdue, was due {due.strftime('%a')} {due.day} {due.strftime('%b')}"
    assert rows and all(due_words in row for row in rows), rows


def test_1br_the_sidebar_counts_the_overdue_session(qapp, window) -> None:
    overdue_this_week(qapp, window)
    texts = shown_texts(window)
    assert "Everything has a time." not in texts and any("1 overdue" in t for t in texts), texts


def test_1br_more_counts_the_overdue_session(qapp, window) -> None:
    overdue_this_week(qapp, window)
    _enabled, words = more_unfinished_row(window)
    assert "Overdue" in words and "1" in words, words


def test_1br_more_says_left_from_last_week_not_unfinished(qapp, window) -> None:
    left_in_week_one(qapp, window)
    _enabled, words = more_unfinished_row(window)
    assert "Unfinished" not in words and "Left from last week" in words, words


def test_1br_more_badge_opens_the_shared_left_over_rows(qapp, window) -> None:
    left_in_week_one(qapp, window)
    window.unfinished_panel._collapse()
    window.findChild(QPushButton, "unfinishedOpen").click()
    settled(qapp, window)
    assert window.unfinished_panel.isVisible()
    row = window.unfinished_panel.list.itemWidget(window.unfinished_panel.list.item(0))
    due = date.fromisoformat(window.session.assignments["lab"]["due"][:10])
    assert row.accessibleName() == (
        f"Lab report · 1 h left · due {due.strftime('%a')} {due.day} {due.strftime('%b')} "
        "· Left from last week"
    )


def test_1br_the_focus_timer_does_not_offer_the_past_overdue_session(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    offered = window.session.focus_tasks()
    replacement = next((item for item in offered if item.get("title") == "Bio reading, overdue"), None)
    assert replacement is not None and replacement.get("day") is None, offered
    assert replacement.get("id") != session_id and replacement.get("block_id") == session_id, offered


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


def test_1br_deadline_timer_refreshes_tags_sidebar_and_focus(qapp, window, monkeypatch) -> None:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    friday = monday + timedelta(days=FRIDAY)
    due = friday.isoformat() + "T23:59"
    session.add_homework({"id": "bio", "title": "Bio reading", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(item for item in session.blocks if item.get("assignment_id") == "bio")
    assert session.place_session(block["id"], WEDNESDAY, 15 * 60 + 15)
    session.save()
    settled(qapp, window)
    announcements = []
    monkeypatch.setattr(
        "desktop.native.fields.announce",
        lambda widget, words, assertive=False: announcements.append((widget, words, assertive)),
    )
    before = datetime.combine(friday, datetime.min.time()).replace(hour=23, minute=58)
    after = before + timedelta(minutes=3)
    session.now_ms = lambda: int(before.timestamp() * 1000)
    session.week_changed.emit()
    settled(qapp, window)
    assert not session.unfinished()
    assert 0 < window._deadline_tick.remainingTime() <= 61_000
    session.now_ms = lambda: int(after.timestamp() * 1000)
    window._deadline_tick.timeout.emit()
    settled(qapp, window)
    assert session.unfinished()[0]["left_over_state"] == "overdue"
    rows = [window.week_access_list.item(i).text() for i in range(window.week_access_list.count())]
    assert any("Bio reading" in row and "Overdue" in row for row in rows)
    assert "1 overdue" in window.rail.none_waiting.text()
    assert any(item["title"] == "Bio reading, overdue" for item in session.focus_tasks())
    sidebar = [item for item in announcements if item[0] is window.rail.none_waiting]
    assert sidebar == [(window.rail.none_waiting, "1 overdue · 1 h still needs a time", False)]
    window._deadline_changed()
    settled(qapp, window)
    assert [item for item in announcements if item[0] is window.rail.none_waiting] == sidebar


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
