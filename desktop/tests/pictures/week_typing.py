"""Screens for how the Week's times, dates and now line look; the behaviour beside them is in
desktop/tests/week/test_week_dates_and_times_at_every_width.py and test_the_day_and_the_now_line.py."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.hours.geometry import LinearTrack
from desktop.native.hours.zoom import HoursScroll
from desktop.native.layouts.clay import ClayPainter
from desktop.native.layouts.dial import DialFace
from desktop.native.layouts.registry import MATCH, tokens_for
from desktop.native.look import resolved_palette
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


def _my_day_late(window: NativeWindow) -> object:
    session = window.session
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    block = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    session.hand_move(block["id"], -1, 3, 19 * 60, 19 * 60 + block["duration_min"])
    session.save()
    wait_until(QApplication.instance(), lambda: not session.busy and not session.dirty)
    window.findChild(QAbstractButton, "viewMyDay").click()
    QApplication.processEvents()
    return window.findChild(QPushButton, "dialLate")


def _my_day_dial(window: NativeWindow) -> object:
    _school_week(window, clock="10:00")
    window.findChild(QAbstractButton, "viewMyDay").click()
    QApplication.processEvents()
    return window.findChild(DialFace, "dialFace")


def _day_agenda(window: NativeWindow) -> object:
    _school_week(window)
    set_clock_24h(False)
    window.findChild(QAbstractButton, "viewDay").click()
    window.resize(810, 800)
    wait_until(QApplication.instance(), lambda: not window.session.busy)
    return window.day_view.agenda


class _ClayNow(QWidget):
    """Clay's hour labels and its now pill on a track of hours 40 pixels each, left of the hours."""

    def __init__(self) -> None:
        super().__init__()
        self.resize(800, 520)
        self.painting = ClayPainter(
            tokens_for("clay", MATCH, resolved_palette("light-frost", False, None)), full=True
        )
        self.painting.now_minute = 10 * 60 + 20
        self.track = LinearTrack(0, QRectF(120, 20, 600, 480), first=8 * 60, last=20 * 60)

    def paintEvent(self, event) -> None:  # noqa: N802
        paint = QPainter(self)
        try:
            paint.fillRect(self.rect(), self.palette().window())
            paint.setFont(QFont("Inter", 12))
            self.painting.hour_labels(paint, self.track, 56)
            self.painting.now(paint, self.track, self.painting.now_minute)
        finally:
            paint.end()


def _clay_now(window: NativeWindow) -> object:
    set_clock_24h(True)
    probe = _ClayNow()
    window._clay_now_probe = probe  # keeps the widget alive while it is photographed
    return probe


def _recovery_codes(window: NativeWindow) -> object:
    window.session.recovery_codes.emit([f"aaaa-bbbb-cccc-dd{n:02d}" for n in range(8)])
    QApplication.processEvents()
    return window.recovery_list


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
        id="week.my-day-late-button-icon",
        area="week",
        prepare=_my_day_late,
        checks=(
            "Running late's icon is at least 4 px wider than it is tall and leaves a clear gap on its "
            "right, so the icon does not touch the button's words."
        ),
        sources=("desktop/native/layouts",),
    ),
    Screen(
        id="week.my-day-dial-ticks",
        area="week",
        prepare=_my_day_dial,
        checks=(
            "The dial labels every second hour and draws a tick only between labels (12 ticks), so no "
            "tick next to a label reads as a minus sign."
        ),
        sources=("desktop/native/layouts/dial.py",),
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
    Screen(
        id="week.clay-now-pill",
        area="week",
        prepare=_clay_now,
        checks=(
            "Clay's now pill lies left of the hours, outside the blocks, and never over their words; "
            "the hour label under the pill (10:00 at 10:20) is left out and the label clear of it "
            "(11:00) is written."
        ),
        sources=("desktop/native/layouts/clay.py",),
    ),
    Screen(
        id="week.recovery-codes-in-mono",
        area="week",
        prepare=_recovery_codes,
        checks=(
            "The recovery codes are written in the bundled monospace face (JetBrains Mono), one code to "
            "a line, so every digit and letter has the same width."
        ),
        sources=("desktop/native/look.py", "desktop/native/window.py"),
    ),
]
