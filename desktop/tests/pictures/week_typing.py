"""Screens for how the Week's times, dates and now line look; the behaviour beside them is in
desktop/tests/week/test_week_dates_and_times_at_every_width.py and test_the_day_and_the_now_line.py."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QAbstractButton, QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.hours.zoom import HoursScroll
from desktop.native.weekmodel import set_clock_24h
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until


def _school_week(window: NativeWindow, day: int = 3, clock: str = "10:30") -> None:
    """School on weekdays 08:00-14:30 and dinner at 18:00, with the clock on `clock` of `day`."""
    session = window.session
    hour, minute = (int(part) for part in clock.split(":"))
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(days=day, hours=hour, minutes=minute))
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
    session.add_block(
        {
            "id": "dinner",
            "title": "Dinner",
            "kind": "locked",
            "category": "meals",
            "start": "18:00",
            "duration_min": 30,
            "days": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    session.save()
    wait_until(QApplication.instance(), lambda: not session.busy and not session.dirty)


def _now_line_in_school(window: NativeWindow) -> object:
    _school_week(window)
    window.findChild(QAbstractButton, "viewWeek").click()
    window._on_week()
    QApplication.processEvents()
    scroll = next(
        scroll for scroll in window.planner.currentWidget().findChildren(HoursScroll) if scroll.isVisible()
    )
    canvas = scroll.canvas
    canvas.set_week(canvas.occurrences, 3, 10 * 60 + 30)
    return scroll


def _narrow_week(window: NativeWindow) -> object:
    _school_week(window)
    window.resize(810, 800)
    window._on_week()
    QApplication.processEvents()
    return window






def _day_agenda(window: NativeWindow) -> object:
    _school_week(window)
    set_clock_24h(False)
    window.findChild(QAbstractButton, "viewDay").click()
    window.resize(810, 800)
    wait_until(QApplication.instance(), lambda: not window.session.busy)
    return window.day_view.agenda






SCREENS: list[Screen] = [
    Screen(
        id="week.now-line-through-school",
        area="week",
        prepare=_now_line_in_school,
        checks=(
            "During School the now line shows on School's colour, from one side of the block to the other, "
            "and is not hidden by it; School's words and icon are written over the line, which runs under "
            "them with no gap round the words and does not read as crossing the name out; where the block "
            "has no words the line is whole. Holds in every Week design."
        ),
        sources=("desktop/native/hours", "desktop/native/layouts"),
        main=True,
    ),
    Screen(
        id="week.plan-button-at-narrow-widths",
        area="week",
        prepare=_narrow_week,
        checks=(
            "With the window at its narrowest the Plan button's words (Plan, Plan homework or Plan my "
            "homework) are whole, not cut, and fit beside its icon."
        ),
        sources=("desktop/native/window.py",),
    ),
    Screen(
        id="week.day-agenda-times",
        area="week",
        prepare=_day_agenda,
        checks=(
            "On the 12-hour clock every start and end time in the Day agenda fits whole inside its "
            "column, at normal and at large text, with no cut or wrapped AM or PM."
        ),
        sources=("desktop/native/hours/classic.py",),
    ),
]
