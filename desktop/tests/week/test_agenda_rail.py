"""The Agenda rail on Today's app's week lists a long homework title whole for a screen reader, with
the day it is due and Start focus beside it. (That nothing runs past the rail's edge is a picture:
week.agenda-rail-long-title.)"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

LONG = "A very long assignment title that must fit the narrow Agenda rail"


def test_a_long_homework_title_is_listed_whole_with_its_day_and_start_focus(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    # Thursday 15:40 of the week, before the window opens, so the 16:00 session is next.
    clock.set(clock.now().replace(hour=15, minute=40))
    window = open_light((1280, 860))
    session = window.session
    friday = date.fromisoformat(session.week_start) + timedelta(days=4)
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.add_homework(
        {
            "id": "rail-work",
            "title": LONG,
            "due": f"{friday.isoformat()}T23:59",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    block = next(item["id"] for item in session.blocks if item.get("assignment_id") == "rail-work")
    session.hand_move(block, -1, 3, 16 * 60, 17 * 60)
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    rail = window.rail
    focus = rail.findChild(QPushButton, "railNextFocus")
    wait_until(qapp, lambda: focus.isVisible(), what="Start focus on the next card")
    # The rows in the list now; a row replaced by this refresh waits for the event loop to delete it.
    listed = [rail.due_list.itemAt(index).widget() for index in range(rail.due_list.count())]
    rows = [row.findChild(QLabel, "railDueTitle") for row in listed if row is not None]
    assert rows, "the long homework is due this week"
    for title in rows:
        when = title.parentWidget().findChild(QLabel, "railDueWhen")
        assert when.text() == "Fri"
    long_row = next(title for title in rows if title.full_text() == LONG)
    assert long_row.accessibleName() == LONG
