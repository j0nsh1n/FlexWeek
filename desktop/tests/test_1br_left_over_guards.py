"""Guards for 1b-R beyond Regression Tester's suite: the More badge opens the shared left-over rows, the
deadline timer refreshes tags, sidebar and focus list, and the week list names the due date.

Same held-clock scenarios as desktop/tests/regress190/test_regress_qa0190_1br_left_over.py: Bio reading
placed Wednesday 3:15 PM of the open week, due Friday 23:59, not ticked, clock Saturday 10:00.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel, QPushButton

from desktop.native.weekmodel import length_label, range_label
from desktop.tests.grid_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_in,
    signed_out,
    wait_until,
    window,
)
from desktop.tests.regress184.test_regress_item1b_unfinished_past_week import left_in_week_one

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


def test_1br_the_week_list_row_says_overdue_with_the_due_date(qapp, window) -> None:
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


def test_1br_more_badge_opens_the_shared_left_over_rows(qapp, window) -> None:
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
    due = friday
    due_words = f"Overdue, was due {due.strftime('%a')} {due.day} {due.strftime('%b')}"
    times = range_label(15 * 60 + 15, 16 * 60 + 15)
    expected = f"Wednesday: Bio reading, {times} · {length_label(60)} · {due_words} · Pinned"
    bio_rows = [row for row in rows if row.startswith("Wednesday: Bio reading, ")]
    assert bio_rows == [expected]
    leftover_words = "1 overdue · 1 h still needs a time"
    assert window.rail.none_waiting.text() == leftover_words
    assert any(item["title"] == "Bio reading, overdue" for item in session.focus_tasks())
    sidebar = [item for item in announcements if item[0] is window.rail.none_waiting]
    assert sidebar == [(window.rail.none_waiting, leftover_words, False)]
    window._deadline_changed()
    settled(qapp, window)
    assert [item for item in announcements if item[0] is window.rail.none_waiting] == sidebar


def test_1br_the_overdue_focus_row_starts_from_the_homework(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    row = next(item for item in window.session.focus_tasks() if item["title"] == "Bio reading, overdue")
    assert row["id"] == "bio" and row["id"] != session_id
    assert window.session.start_focus(row["id"], row["day"]) is True
    focus = window.session.focus
    assert focus["title"] == "Bio reading, overdue"
    assert focus["assignmentId"] == "bio" and focus["blockId"] is None
