"""What the planner tests and the planner screens share: the states they put the window in.

Plain helpers, no fixtures and no tests. The screens (desktop/tests/pictures/screens_planner.py) call
them with `qapp=None`: waiting never needs the application object."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.window import NativeWindow
from desktop.tests.blocks_helper import put_block
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import settled

WEDNESDAY, FRIDAY, SATURDAY = 2, 4, 5
EVENT_PASSES = 20

WEEK = "2026-09-14"
TITLES = {"poster": "Science fair poster", "essay": "History essay", "chem": "Chem lab report"}
TRACE = {
    "placed": [{"id": "essay"}, {"id": "chem"}],
    "unplaced": [{"id": "poster", "title": "Science fair poster"}],
    "moves": [
        {
            "block_id": "essay",
            "reason": "RESHUFFLE_AFTER_MISS",
            "from_day": 3,
            "from_start": "18:45",
            "to_day": 4,
            "to_start": "10:00",
        }
    ],
    "explanations": [
        {
            "block_id": "poster",
            "reason": "DEADLINE_MISS",
            "message": "There isn't enough time left before it's due, even with nothing else planned.",
        },
        {
            "block_id": "chem",
            "message": "Finishes only 29 min before it's due.",
            "slack_min": 29,
            "slack_status": "danger",
        },
        {
            "block_id": "essay",
            "message": "Finishes 5 h before it's due.",
            "slack_min": 300,
            "slack_status": "ok",
        },
    ],
}
ONE_UNPLACED = {
    "placed": [],
    "unplaced": [{"id": "poster", "title": "Science fair poster"}],
    "moves": [],
    "explanations": [],
}

LONG_FOCUS_TASKS = [
    {
        "id": "long",
        "day": 0,
        "start": "19:00",
        "title": "A long history essay title with many words that must wrap",
    },
    {
        "id": "next",
        "day": 0,
        "start": "20:00",
        "title": "Another long chemistry report title that must also wrap",
    },
    {"id": "short", "day": 1, "start": "19:00", "title": "Math"},
]


def overdue_this_week(qapp: QApplication | None, window: NativeWindow) -> str:
    """Bio reading placed Wednesday 3:15 PM of the open week, due Friday 23:59, not ticked, the clock
    Saturday 10:00. Returns the id of its block."""
    session = window.session
    monday = date.fromisoformat(session.week_start)
    due = (monday + timedelta(days=FRIDAY)).isoformat() + "T23:59"
    session.add_homework({"id": "bio", "title": "Bio reading", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(b for b in session.blocks if b.get("assignment_id") == "bio")
    put_block(session, block["id"], WEDNESDAY, 15 * 60 + 15, 16 * 60 + 15, pinned=True)
    session.save()
    settled(qapp, window)
    saturday = datetime.fromisoformat(session.week_start) + timedelta(days=SATURDAY, hours=10)
    CLOCK.set(saturday)
    session.week_changed.emit()
    settled(qapp, window)
    return block["id"]


def left_in_week_one(qapp: QApplication | None, window: NativeWindow) -> tuple[str, str]:
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
    CLOCK.set(datetime.fromisoformat(week2) + timedelta(hours=7))
    session.load_week(week2)
    wait_until(qapp, lambda: session.week_start == week2 and not session.busy)
    settled(qapp, window)
    return week1, week2


def open_unfinished(window: NativeWindow) -> None:
    """Classic week with the Unfinished list open, at the window's own size and text size."""
    window._layout = sanitize_layout({"main": "classic", "day": "one", "options": {}})
    window._apply_appearance()
    window._on_week()
    window.show()
    window._show_unfinished()
    for _ in range(EVENT_PASSES):
        QApplication.processEvents()


def unfinished_row_buttons(window: NativeWindow):
    """The first Unfinished row and its Start focus, Plan and Delete buttons."""
    row = window.unfinished_panel.list.itemWidget(window.unfinished_panel.list.item(0))
    return row, [
        button
        for button in row.findChildren(QPushButton)
        if button.objectName().split("-")[0] in {"focusUnfinished", "planUnfinished", "deleteUnfinished"}
    ]


def unfinished_words(window: NativeWindow) -> QLabel:
    row, _buttons = unfinished_row_buttons(window)
    return row.findChild(QLabel, "unfinishedRow")


def agenda_week(window: NativeWindow) -> None:
    """Thursday 15:40: Soccer practice next and Dinner after it, the essay placed at 19:00 and Chem on
    Monday, the worksheet with no time; the classic week, at the window's own size."""
    session = window.session
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=15, minutes=40)
    CLOCK.set(thursday)
    session.add_block(
        {
            "id": "soccer",
            "title": "Soccer practice",
            "kind": "locked",
            "category": "extra",
            "start": "16:00",
            "duration_min": 90,
            "days": [1, 3],
        }
    )
    session.add_block(
        {
            "id": "dinner",
            "title": "Dinner",
            "kind": "locked",
            "category": "meals",
            "start": "18:30",
            "duration_min": 30,
            "days": [3],
        }
    )
    due = sunday_due(session.week_start)
    for key, title in (("essay", "History essay"), ("math", "Math worksheet"), ("chem", "Chem lab report")):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(None, window)
    for key, day, start in (("essay", 3, "19:00"), ("chem", 0, "20:00")):
        block = next(block for block in session.blocks if block.get("assignment_id") == key)
        session.add_block({**block, "start": start, "days": [day], "pinned": True})
    session.save()
    settled(None, window)
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._apply_appearance()
    session.set_view("week")
    window._on_week()
    for _ in range(5):
        QApplication.processEvents()


def week_list_action(window: NativeWindow):
    """More's row for Week as a list."""
    window._sync_more_menu()
    for action, button in window._more_pairs:
        if button.objectName() == "weekListRow":
            return action
    raise AssertionError("More has no Week as a list")
