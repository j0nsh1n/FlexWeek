"""Screens for the Material month's chips and dots. (Fragment of screens_month.py, from the views lane's
G12.)"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump
from desktop.tests.pictures.screen import Screen
from desktop.tests.sheets.support_material_pictures import (
    add_homework,
    material,
    seed_school_and_essay,
    settle,
)

_SOURCES = (
    "desktop/native/material/qml/month",
    "desktop/native/material/bridge_month.py",
    "desktop/native/material/theme.py",
)


def _month_with_due_and_overdue(window: NativeWindow) -> None:
    material(window)
    seed_school_and_essay(window)
    # Monday 2 November is past on Thursday evening, so this one is overdue. 1 December sits outside
    # November, on the grid's last row.
    add_homework(window, "overdue", "Lab write-up", f"{window.session.week_start}T09:00", 45)
    add_homework(window, "december", "December essay", "2026-12-01T17:00", 60)
    window.session.save()
    settle(window)
    window._material_page.bridge.showPage("month")
    pump(QApplication.instance(), 40)
    settle(window)


def _month_on_a_phone(window: NativeWindow) -> None:
    material(window)
    seed_school_and_essay(window)
    add_homework(window, "overdue", "Lab write-up", f"{window.session.week_start}T09:00", 45)
    window.session.save()
    settle(window)
    window.setMinimumWidth(360)
    window.resize(400, 800)
    bridge = window._material_page.bridge
    bridge.showPage("month")
    pump(QApplication.instance(), 40)
    # The essay is due Sunday 8 November; picking that date gives it the accent fill under its dots.
    bridge._month.selectDate("2026-11-08")
    pump(QApplication.instance(), 30)


SCREENS: list[Screen] = [
    Screen(
        id="month.material_month_chips",
        area="month",
        prepare=_month_with_due_and_overdue,
        checks=(
            "November 2026 in Material. A due chip (History essay, Sunday 8 November) wears the "
            "homework class fill and ink with the edit icon and a left bar in the homework bar colour. "
            "An overdue chip (Lab write-up, Monday 2 November) wears the overdue tint and ink with the "
            "warning icon and no bar. A planned time (8:00 AM School) is neutral: the muted surface, "
            "muted ink, no icon, no bar. All chips are pills (radius = height / 2). No chip is in the "
            "purple family (#eae6fa, #2a244d, #7c6cd6, #9b8cf0, #fad8fd, #705574) or the tertiary "
            "container colour, and no chip's words are white or the bar colour. On dates outside the "
            "month (the last row, 1 December) only the cell fill and the day number fade, to 0.45 "
            "opacity; the chip and its words stay at full opacity."
        ),
        sources=_SOURCES,
        main=True,
        styles=("material",),
    ),
    Screen(
        id="month.material_month_dots_phone",
        area="month",
        prepare=_month_on_a_phone,
        checks=(
            "November 2026 in Material at a 400 px wide window (phone width): each day shows dots, not "
            "chips. A due dot is the homework bar colour, an overdue dot is the overdue status colour, "
            "and none is in the purple family. On the picked date (Sunday 8 November, whose cell is "
            "filled with the accent container) the dots sit on a card-coloured pill, and each dot "
            "reaches 3:1 against that card colour, including in High contrast."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
]
