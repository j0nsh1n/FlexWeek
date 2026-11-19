"""Screens for how the Week's times, dates and now line look; the behaviour beside them is in
desktop/tests/week/test_week_dates_and_times_at_every_width.py and test_the_day_and_the_now_line.py."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
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




def _narrow_week(window: NativeWindow) -> object:
    _school_week(window)
    window.resize(810, 800)
    window._on_week()
    QApplication.processEvents()
    return window












SCREENS: list[Screen] = [
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
]
