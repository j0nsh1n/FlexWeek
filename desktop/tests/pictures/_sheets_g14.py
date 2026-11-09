"""The command bar (Ctrl+K): how its rows look when letters are typed and when the pointer is on one, and
that its box stays inside the window (look checks of the old test_keys_0182)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton

from desktop.native.calendar import sunday_due
from desktop.native.command_bar import KEY_ROLE
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_bar_pictures import WIDGETS_DESIGNS, idle, pump


def _open_bar(window: NativeWindow, typed: str = "") -> None:
    window.resize(1280, 860)
    session = window.session
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    idle(window)
    window.findChild(QAbstractButton, "viewWeek").click()
    wait_until(None, lambda: not session.busy)
    window.week_table.hours.setFocus()
    QTest.keyClick(window.week_table.hours, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    if typed:
        QTest.keyClicks(window.command_bar.input, typed)
    pump()


def _typed_letters(window: NativeWindow) -> None:
    _open_bar(window, "hist")
    return None


def _pointer_on_a_row(window: NativeWindow) -> None:
    _open_bar(window)
    bar = window.command_bar
    other = next(
        bar.list.item(row)
        for row in range(bar.list.count())
        if bar.list.item(row).data(KEY_ROLE) and bar.list.item(row).text() == "Week"
    )
    QTest.mouseMove(bar.list.viewport(), bar.list.visualItemRect(other).center())
    pump()
    return None


SCREENS: list[Screen] = [
    Screen(
        id="sheets.command_bar_typed_letters",
        area="sheets",
        prepare=_typed_letters,
        checks=(
            "After Ctrl+K and typing 'hist' the History essay row marks the typed letters in the accent "
            "colour (closer to the accent than to the plain text colour). The command box is wholly "
            "inside the 1280x860 window: its top is not above the window and its bottom is not below it."
        ),
        sources=("desktop/native/command_bar.py", "desktop/native/look.py"),
        styles=WIDGETS_DESIGNS,
    ),
    Screen(
        id="sheets.command_bar_pointer_on_a_row",
        area="sheets",
        prepare=_pointer_on_a_row,
        checks=(
            "The row Enter would choose is filled with 14 % of the accent over the panel; the row under "
            "the pointer (Week) is filled with 6 %, visibly lighter than the Enter row (more than 8 "
            "levels apart in red and green together)."
        ),
        sources=("desktop/native/command_bar.py", "desktop/native/look.py"),
        styles=WIDGETS_DESIGNS,
    ),
]
