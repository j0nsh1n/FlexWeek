"""Screens for the Material sheets: the Add homework sheet on a desktop and on a phone, the Add fixed time
sheet and the discard question. (Fragment of screens_sheets.py, from the views lane's G12.)"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump
from desktop.tests.pictures.screen import Screen
from desktop.tests.sheets.support_material_pictures import material, seed_school_and_essay

_SOURCES = (
    "desktop/native/material/qml/sheets",
    "desktop/native/material/qml/components",
    "desktop/native/material/bridge_sheets.py",
)


def _sheets(window: NativeWindow):
    material(window)
    seed_school_and_essay(window)
    return window._material_page.bridge.sheets


def _homework_how_long(window: NativeWindow) -> None:
    sheets = _sheets(window)
    sheets.openHomework()
    sheets.setText("title", "Chemistry lab")
    sheets.next()
    sheets.next()
    pump(QApplication.instance(), 30)


def _homework_how_long_phone(window: NativeWindow) -> None:
    window.setMinimumWidth(360)
    window.resize(700, 800)
    pump(QApplication.instance())
    _homework_how_long(window)


def _fixed_time_when(window: NativeWindow) -> None:
    sheets = _sheets(window)
    sheets.openBlock()
    sheets.setText("title", "Chess club")
    sheets.next()
    pump(QApplication.instance(), 30)


def _discard_question(window: NativeWindow) -> None:
    sheets = _sheets(window)
    sheets.openHomework()
    sheets.setText("title", "Essay")
    sheets.closeSheet()
    pump(QApplication.instance(), 30)


SCREENS: list[Screen] = [
    Screen(
        id="sheets.material_homework_sheet",
        area="sheets",
        prepare=_homework_how_long,
        checks=(
            "Add homework, step 3 (How long), on a 1280x800 desktop window. The sheet card is 560 px "
            "wide and centred, with an 8 px radius. Its buttons and text fields have a 6 px radius. "
            "The three step crumbs (1. What, 2. When, 3. How long) are pills, radius = height / 2, "
            "with no outline. The quick-length chips (15, 30, 45, 60, 90 min) are pills with 60 min "
            "ticked. Save is the only filled button in the sheet. A focused field shows a 2 px "
            "accent ring just outside it."
        ),
        sources=_SOURCES,
        main=True,
        styles=("material",),
    ),
    Screen(
        id="sheets.material_homework_sheet_phone",
        area="sheets",
        prepare=_homework_how_long_phone,
        checks=(
            "Add homework on a 700 px wide window (a phone width): the sheet is a bottom sheet, as "
            "wide as the window (700 px), and its bottom edge sits on the window's bottom edge. Its "
            "words, chips and the Save button fit inside it."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.material_fixed_time_sheet",
        area="sheets",
        prepare=_fixed_time_when,
        checks=(
            "Add fixed time, step 2 (When), after typing Chess club. The step crumbs (1. What, "
            "2. When, 3. Category) and the day chips are pills (radius = height / 2) with no crumb "
            "outline. The sheet card has an 8 px radius, and Next is the only filled button."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.material_discard_prompt",
        area="sheets",
        prepare=_discard_question,
        checks=(
            "The question 'Discard your changes?' with 'Your changes will be lost.' over the Add "
            "homework sheet. The dialog card has an 8 px radius and sits over a dimmed sheet. Keep "
            "editing and Discard are both readable, and at most one of them is filled."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
]
