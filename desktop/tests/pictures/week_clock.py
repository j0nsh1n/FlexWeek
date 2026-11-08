"""Screens for the hour words, the time-now pill, a block's time range and the week list: the looks
the clock-gutter, block-range and week-list tests used to check in code."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QAbstractButton, QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still

SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:30",
    "duration_min": 405,
    "days": [0, 1, 2, 3, 4],
}
LONG_TITLE = "A very long Thursday block title that must elide at the right edge"


def _saved(window: NativeWindow) -> None:
    session = window.session
    wait_until(None, lambda: not session.busy and not session.dirty)


def _add(window: NativeWindow, *blocks: dict) -> None:
    for block in blocks:
        window.session.add_block(dict(block))
    _saved(window)


def _twelve_hour_clock_at_the_widest_minute(window: NativeWindow) -> None:
    """12:58 PM is the widest the time-now pill gets on the 12-hour clock."""
    session = window.session
    session.preferences = {**session.preferences, "clock_24h": False}
    CLOCK.set(datetime.combine(CLOCK.today(), CLOCK.now().time().replace(hour=12, minute=58)))
    window._sync_chrome()


def _hours_in_the_week(window: NativeWindow) -> None:
    _twelve_hour_clock_at_the_widest_minute(window)
    _add(window, SCHOOL)
    window.findChild(QAbstractButton, "viewWeek").click()
    _saved(window)
    window._refresh_layout()
    still(window)
    QApplication.processEvents()


def _hours_on_the_day(window: NativeWindow) -> None:
    _twelve_hour_clock_at_the_widest_minute(window)
    _add(window, SCHOOL)
    window.findChild(QAbstractButton, "viewDay").click()
    _saved(window)
    window.session.open_day(CLOCK.today().isoformat())
    _saved(window)
    window._refresh_layout()
    still(window)
    QApplication.processEvents()


def _one_hour_block_in_a_narrow_column(window: NativeWindow) -> object:
    _add(
        window,
        {
            "id": "school-hour",
            "title": "School hours block",
            "kind": "locked",
            "category": "class",
            "start": "16:45",
            "duration_min": 60,
            "days": [0],
        },
    )
    window.findChild(QAbstractButton, "viewWeek").click()
    _saved(window)
    hours = window.week_table.hours
    hours.reveal(0, 16 * 60, 19 * 60)
    still(window)
    QApplication.processEvents()
    return hours


def _more_menu_open(window: NativeWindow) -> object:
    _add(window, SCHOOL)
    window.findChild(QAbstractButton, "viewWeek").click()
    _saved(window)
    window._sync_more_menu()
    window.more_button.click()
    QApplication.processEvents()
    return window.more_button.menu()


def _week_list_open(window: NativeWindow) -> None:
    _add(
        window,
        SCHOOL,
        {
            "id": "long-title",
            "title": LONG_TITLE,
            "kind": "locked",
            "category": "extra",
            "start": "11:00",
            "duration_min": 30,
            "days": [3],
        },
    )
    window.findChild(QAbstractButton, "viewWeek").click()
    _saved(window)
    window._toggle_week_access_list()
    still(window)
    QApplication.processEvents()


SCREENS: list[Screen] = [
    Screen(
        id="week.hour-labels-and-now-pill",
        area="week",
        prepare=_hours_in_the_week,
        checks=(
            "every hour word fits inside the box it is written in and is whole, with no edge of the hours "
            "cutting it; no two hour words run together (Mission writes every other hour, or fewer when "
            "the words are wide, and keeps an hour moved in from the edge clear of its neighbour); the "
            "time-now pill 12:58 PM is whole beside the hours, clear of the first day's blocks in the "
            "Timeline design; at Large text on the 12-hour clock nothing is cut"
        ),
        sources=("desktop/native/hours", "desktop/native/layouts"),
        main=True,
    ),
    Screen(
        id="week.hour-labels-on-day",
        area="week",
        prepare=_hours_on_the_day,
        checks=(
            "on Day, at each zoom level the hours offer, every hour word fits its box, is whole and runs "
            "into no other word, and the time-now pill 12:58 PM is whole"
        ),
        sources=("desktop/native/hours", "desktop/native/layouts"),
    ),
    Screen(
        id="week.block-time-range-in-narrow-column",
        area="week",
        prepare=_one_hour_block_in_a_narrow_column,
        checks=(
            "a one-hour block from 16:45 keeps its time range before its title gives way, in every look "
            "and text size; in a narrow column the range is whole or the start alone, never cut in the "
            "middle (16:45–1…)"
        ),
        sources=("desktop/native/hours/canvas.py",),
    ),
    Screen(
        id="week.more-menu-week-list-entry",
        area="week",
        prepare=_more_menu_open,
        checks=(
            "the Week as a list entry in the More menu shows all its words, at least a line tall, in "
            "every design, look and text size"
        ),
        sources=("desktop/native/window.py", "desktop/native/menus.py"),
    ),
    Screen(
        id="week.week-list-panel",
        area="week",
        prepare=_week_list_open,
        checks=(
            "on a wide window the week list floats as a 360 px panel as tall as the grid; on a narrow "
            "window it covers the whole grid, from the grid's top-left corner; the More button sits above "
            "the grid, not over it; a very long row is cut with an ellipsis at the right edge and the "
            "list shows no sideways scroll bar"
        ),
        sources=("desktop/native/window.py",),
        main=True,
    ),
]
