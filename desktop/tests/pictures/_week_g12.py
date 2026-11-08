"""Screens for the Material week's blocks, homework drawer, Add button and rail. (Fragment of
screens_week.py, from the views lane's G12; the blocks are drawn on the week.)"""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump, qml
from desktop.tests.pictures.screen import Screen
from desktop.tests.sheets.support_material_pictures import (
    add_block,
    add_homework,
    material,
    seed_school_and_essay,
    settle,
)

_SOURCES = (
    "desktop/native/material/qml/components",
    "desktop/native/material/qml/week",
    "desktop/native/material/theme.py",
)


def _day(window: NativeWindow, offset: int) -> str:
    return (date.fromisoformat(window.session.week_start) + timedelta(days=offset)).isoformat()


def _class_blocks(window: NativeWindow) -> None:
    material(window)
    seed_school_and_essay(window)
    # Tuesday has gone by on Thursday evening, so its copies show faded; Friday's are still to come.
    both = [1, 4]
    add_block(window, "sports", "Sports", "exercise", "15:00", 60, both)
    add_block(window, "activity", "Activity", "extra", "16:15", 60, both)
    add_block(window, "study", "Study", "study", "17:30", 60, both)
    add_block(window, "dinner", "Dinner", "meals", "18:45", 45, both)
    add_block(window, "lab", "Chemistry lab report write-up", "class", "19:45", 30, both)
    window.session.save()
    settle(window)
    pump(QApplication.instance(), 30)


def _drawer_with_homework_waiting(window: NativeWindow) -> None:
    material(window)
    seed_school_and_essay(window)
    add_homework(window, "reading", "Reading log", f"{_day(window, 6)}T21:00", 30)
    add_homework(window, "lab", "Chemistry lab", f"{_day(window, 4)}T17:00", 120)
    add_homework(window, "maths", "Maths sheet", f"{_day(window, 0)}T08:00", 45)
    window.session.save()
    settle(window)
    pump(QApplication.instance(), 30)


def _drawer_all_planned(window: NativeWindow) -> None:
    material(window)
    seed_school_and_essay(window)
    pump(QApplication.instance(), 30)


def _add_button_focused_by_key(window: NativeWindow) -> None:
    root = material(window)
    seed_school_and_essay(window)
    quick = window._material_page._quick
    window.activateWindow()
    quick.setFocus()
    qml(root, "materialFab").forceActiveFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(quick, Qt.Key.Key_Shift)
    pump(QApplication.instance(), 30)


SCREENS: list[Screen] = [
    Screen(
        id="week.material_class_blocks",
        area="week",
        prepare=_class_blocks,
        checks=(
            "Week blocks of every class: School (class), Sports (exercise), Activity (extra), "
            "History essay (assignments), Study, Dinner (meals, drawn as other) and a 30-minute "
            "'Chemistry lab report write-up'. Each block's bar, fill and title come from its class, "
            "never from the purple family (#eae6fa, #2a244d, #7c6cd6, #9b8cf0). Block text is the "
            "ink colour (#0f172a light, #ececec dark), never white and never the class colour; the "
            "time line under a title follows the same rule. Title text reaches 4.5:1 on its fill, "
            "and a bar reaches 3:1 on the card (today's column) and on the page. Blocks on days "
            "already past (Tuesday) fade their fill and bar to 0.55 opacity while the title and "
            "time stay at full opacity in the muted ink. The 30-minute block is 36 px tall: its "
            "two-line title and time are clipped inside the block and do not paint into the next hour."
        ),
        sources=_SOURCES + ("desktop/native/tokens.py",),
        styles=("material",),
    ),
    Screen(
        id="week.material_homework_drawer",
        area="week",
        prepare=_drawer_with_homework_waiting,
        checks=(
            "The homework drawer with homework waiting for a time: Plan is the one filled button. Each "
            "homework's status chip carries an icon (check, schedule or warning) and a word on a tint "
            "of its status colour, as a pill (radius = height / 2). The word is the status ink on the "
            "tint and reaches 4.5:1. A plain chip stays neutral with no icon."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="week.material_homework_drawer_all_planned",
        area="week",
        prepare=_drawer_all_planned,
        checks=(
            "The homework drawer when nothing is left to plan: Plan is a text button (no fill), "
            "disabled, and 'Everything has a time.' stays under it in the muted ink. Plan's words and "
            "icon are the muted ink at full opacity, not the 38 % disabled ink."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="week.material_add_button_and_rail",
        area="week",
        prepare=_add_button_focused_by_key,
        checks=(
            "The Add button is 56 px square with a 6 px radius, filled with the card colour (#ffffff "
            "light, #14171c dark), a 1 px edge (#e5e9f0 light, #252a33 dark) and an accent icon "
            "(#3d6fc4 light, #7fa8ff dark). The selected rail item (Week) has a secondaryContainer "
            "tint (#e6edf8 light), a primary icon (#3d6fc4), a 56 by 32 pill and no outline. The Add "
            "button was focused by a key, so it shows a 2 px accent ring (radius 10) that stands 4 px "
            "clear of it on every side, 8 px wider than the button; the rail item shows no ring."
        ),
        sources=_SOURCES + ("desktop/native/material/focus_visible.py",),
        main=True,
        styles=("material",),
    ),
]
