"""What the tests of More's Unfinished row, count and panel share (and test_planning_agenda imports)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QApplication, QLabel

from backend.tests.fake_clock import CLOCK
from desktop.native.window import NativeWindow
from desktop.tests.blocks_helper import put_block
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import settled

WEDNESDAY, FRIDAY, SATURDAY = 2, 4, 5


def due_in(window: NativeWindow, days: int) -> str:
    return (date.fromisoformat(window.session.week_start) + timedelta(days=days)).isoformat() + "T23:59"


def add(window: NativeWindow, key: str, title: str, minutes: int, due: str) -> None:
    window.session.add_homework(
        {"id": key, "title": title, "estimate_min": minutes, "revision": 0, "due": due}
    )


def more_row(window: NativeWindow) -> tuple[bool, str]:
    """Whether More's Unfinished row can be pressed, and what it says (its name, a tab, its count)."""
    window._sync_more_menu()
    for action, button in window._more_pairs:
        if button.objectName() == "unfinishedOpen":
            return action.isEnabled(), action.text()
    raise AssertionError("More has no Unfinished row")


def panel_rows(window: NativeWindow) -> list[str]:
    panel = window.unfinished_panel
    return [
        label.text()
        for label in panel.findChildren(QLabel)
        if label.objectName() == "unfinishedRow" and label.isVisibleTo(window)
    ]


def left_over_week_two(qapp: QApplication, window: NativeWindow) -> None:
    """An essay due three days ago with its time deleted, seen from the week after: homework from an
    earlier week. Then work due that week, and work due the week after, neither placed."""
    session = window.session
    week = date.fromisoformat(session.week_start)
    session.add_block({"id": "school", "title": "School", "kind": "locked", "start": "08:00",
                       "duration_min": 390, "days": [0, 1, 2, 3, 4]})
    overdue = (CLOCK.today() - timedelta(days=3)).isoformat()
    add(window, "essay", "History essay", 120, overdue + "T12:00")
    session.save()
    settled(qapp, window)
    planned = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    session.delete_block(planned["id"])
    session.save()
    settled(qapp, window)
    later = (week + timedelta(days=7)).isoformat()
    session.load_week(later)
    wait_until(qapp, lambda: session.week_start == later and not session.busy)
    add(window, "math", "Math worksheet", 60, due_in(window, 4))
    add(window, "lab", "Chem lab", 90, due_in(window, 10))
    session.save()
    settled(qapp, window)
    window._on_week()
    qapp.processEvents()


def overdue_this_week(qapp: QApplication, window: NativeWindow) -> str:
    """Bio reading placed on Wednesday 3:15 PM of the open week, due Friday 23:59, not ticked, with the
    clock moved to Saturday 10:00. Returns the planned block's id."""
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
