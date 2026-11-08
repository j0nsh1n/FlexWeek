"""Screens for the classic hours: the looks the hand, chips, column and grid-keyboard tests used to
check in code (heights, widths, clipping, text fit, the focus ring)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.hours.geometry import LAST
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

HOURS = "desktop/native/hours"
WEDNESDAY = 2
SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "days": [0, 1, 2, 3, 4],
    "start": "08:00",
    "duration_min": 405,
}
GYM = {
    "id": "gym",
    "title": "Gym",
    "kind": "locked",
    "category": "exercise",
    "days": [5],
    "start": "10:00",
    "duration_min": 90,
}
SOCCER = {
    "id": "soccer",
    "title": "Soccer practice",
    "kind": "locked",
    "category": "extra",
    "days": [5],
    "start": "16:00",
    "duration_min": 90,
}
CLUB = {
    "id": "club",
    "title": "Club",
    "kind": "locked",
    "category": "extra",
    "days": [3],
    "start": "19:00",
    "duration_min": 60,
}
PIANO = {
    "id": "piano",
    "title": "Piano",
    "kind": "locked",
    "category": "extra",
    "days": [WEDNESDAY],
    "start": "15:00",
    "duration_min": 60,
}


def _settled(window: NativeWindow) -> None:
    wait_until(None, lambda: not window.session.busy and not window.session.dirty)


def _classic_week(window: NativeWindow, blocks: tuple[dict, ...]) -> QWidget:
    window.resize(1280, 860)
    window._layout = {"main": "classic", "day": "one", "options": {}}
    for block in blocks:
        window.session.add_block(dict(block))
    window.session.save()
    _settled(window)
    window.findChild(QAbstractButton, "viewWeek").click()
    _settled(window)
    return window.week_table


def _homework(window: NativeWindow, title: str, start: str | None = None, day: int = 3) -> None:
    """One homework item of 45 minutes; given a start, it is put on `day` at that time."""
    session = window.session
    session.add_homework(
        {
            "id": "work",
            "title": title,
            "due": sunday_due(session.week_start),
            "estimate_min": 45,
            "revision": 0,
        }
    )
    session.save()
    _settled(window)
    if start is not None:
        block = next(block for block in session.blocks if block.get("assignment_id") == "work")
        session.add_block({**block, "start": start, "days": [day], "pinned": True})
        session.save()
        _settled(window)


def _hour_edges(window: NativeWindow) -> QWidget:
    return _classic_week(window, (CLUB,))


def _weekend_empty(window: NativeWindow) -> QWidget:
    return _classic_week(window, (SCHOOL,))


def _weekend_with_gym(window: NativeWindow) -> QWidget:
    return _classic_week(window, (SCHOOL, GYM))


def _narrow_weekend_block(window: NativeWindow) -> QWidget:
    return _classic_week(window, (SCHOOL, SOCCER))


def _end_of_day(window: NativeWindow) -> QWidget:
    table = _classic_week(window, (SCHOOL,))
    table.hours.reveal(3, LAST - 60, LAST)
    return table


def _rail_long_title(window: NativeWindow) -> QWidget:
    _classic_week(window, ())
    _homework(window, "Science poster on the water cycle for Ms Alvarez")
    return window.rail


def _rail_row(title: str) -> Callable[[NativeWindow], QWidget]:
    def prepare(window: NativeWindow) -> QWidget:
        _classic_week(window, ())
        _homework(window, title, start="20:00")
        window.rail.setFont(QFont("Inter", 11))
        return window.rail

    return prepare


def _sunday_header(window: NativeWindow) -> QWidget:
    session = window.session
    _classic_week(window, ())
    _homework(window, "Sunday reading", start="16:00", day=6)
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._apply_appearance()
    session.set_view("week")
    window.resize(810, 860)
    window._on_week()
    return window.week_table


def _ring_on_a_slot(window: NativeWindow) -> QWidget:
    table = _classic_week(window, (SCHOOL,))
    CLOCK.set(
        datetime.fromisoformat(window.session.week_start) + timedelta(days=WEDNESDAY, minutes=14 * 60 + 7)
    )
    window._fill_classic()
    table.hours.setFocus(Qt.FocusReason.TabFocusReason)
    return table


def _ring_on_a_block(window: NativeWindow) -> QWidget:
    table = _classic_week(window, (SCHOOL, PIANO))
    CLOCK.set(
        datetime.fromisoformat(window.session.week_start) + timedelta(days=WEDNESDAY, minutes=14 * 60 + 7)
    )
    window._fill_classic()
    table.hours.setFocus(Qt.FocusReason.TabFocusReason)
    for _ in range(4):
        QTest.keyClick(window.windowHandle(), Qt.Key.Key_Down)
    return table


SCREENS: list[Screen] = [
    Screen(
        "week.classic-hour-edges",
        "week",
        _hour_edges,
        "A 60-minute block on the classic Week is tall enough to show a top edge, a middle and a bottom "
        "edge for the pointer (at least two edge zones and a margin of 6 px), and an hour is the Week's "
        "set hour height.",
        (HOURS,),
    ),
    Screen(
        "week.classic-weekend-columns",
        "week",
        _weekend_empty,
        "Saturday and Sunday with nothing on them are narrower than the five full days but still wide "
        "enough to read a block; each day's name sits over its own column and is as wide as it.",
        (HOURS,),
    ),
    Screen(
        "week.classic-weekend-day-with-a-block",
        "week",
        _weekend_with_gym,
        "Saturday with Gym on it is as wide as a weekday; empty Sunday stays narrower; each day's name "
        "sits over its own column and is as wide as it.",
        (HOURS,),
    ),
    Screen(
        "week.classic-narrow-weekend-block",
        "week",
        _narrow_weekend_block,
        "A block on the narrowest weekend day keeps the start of its name (the first word whole) and "
        "its times inside the block.",
        (HOURS,),
    ),
    Screen(
        "week.classic-end-of-day",
        "week",
        _end_of_day,
        "Scrolled to the end of the day, the 24:00 (12:00 AM) label is whole and the room below the last "
        "rule is kept, at least 12 px, so the label is never cut.",
        (HOURS,),
    ),
    Screen(
        "week.rail-chip-long-title",
        "week",
        _rail_long_title,
        "A long homework title in the rail shortens to at most two lines ending in an ellipsis, the "
        "length ('45 min') stays whole beside it, the chip does not run past the rail's right edge and "
        "the rail keeps its width.",
        (HOURS,),
    ),
    Screen(
        "week.rail-focus-row",
        "week",
        _rail_row("Math worksheet"),
        "A homework row in the rail says 'Math worksheet' whole beside or under its day and time "
        "('Today 20:00') when there is room; where the row is too narrow for both beside each other the "
        "time drops under the name, and the time is always whole.",
        (HOURS,),
        main=True,
    ),
    Screen(
        "week.rail-focus-row-one-long-word",
        "week",
        _rail_row("Supercalifragilisticexpialidocious"),
        "A single word wider than the whole row is the only thing cut, with an ellipsis at its end, and "
        "the day and time are still said whole.",
        (HOURS,),
    ),
    Screen(
        "week.sunday-header-total",
        "week",
        _sunday_header,
        "At 810 px wide, Sunday's homework total ('45 min') is whole inside its column header: not "
        "clipped, and its text stays within the header's box, with the Agenda rail shown.",
        (HOURS,),
        main=True,
    ),
    Screen(
        "week.grid-focus-ring-on-a-slot",
        "week",
        _ring_on_a_slot,
        "The keyboard-focused slot has a ring in the accent colour whose contrast against what lies "
        "just outside it is at least 3 to 1.",
        (HOURS,),
        main=True,
    ),
    Screen(
        "week.grid-focus-ring-on-a-block",
        "week",
        _ring_on_a_block,
        "The ring goes round the whole focused block (its top-left corner within a pixel or two of the "
        "block's) and is drawn in the accent colour.",
        (HOURS,),
    ),
]
