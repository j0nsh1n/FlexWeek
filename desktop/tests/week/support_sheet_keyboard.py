"""What the keyboard-after-a-sheet tests share: School on Monday, a click on the hours that opens a real
modal sheet, and the keys that answer it. Every click and key goes through the window system's path
(QTest on `window.windowHandle()`), so Dialog.showEvent/hideEvent and _give_focus_back run as in the
app."""

# ruff: noqa: E402
from __future__ import annotations

from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from desktop.native.hours.canvas import HoursCanvas
from desktop.native.widgets import BlockDialog
from desktop.tests.grid_support import NONE
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still

MONDAY, TUESDAY, THURSDAY = 0, 1, 3
SCHOOL = {"id": "school", "title": "School", "kind": "locked", "category": "class", "start": "08:00",
          "duration_min": 390, "days": [0, 1, 2, 3, 4]}

# The sheet is looked for again this often while it opens, at most this many times.
LOOK_MS, LOOKS = 5, 400


class SheetAnswer:
    """Answers the next modal sheet that opens. The call that opens a sheet does not return until it
    closes, so the answer is sent from a timer inside the sheet's own event loop."""

    def __init__(self, answer: Callable[[QDialog], None]) -> None:
        self.answer = answer
        self.seen: list[str] = []
        self.opener_returned = False
        self._looked = 0

    def arm(self) -> None:
        QTimer.singleShot(0, self._reply)

    def _reply(self) -> None:
        sheet = QApplication.activeModalWidget()
        handle = sheet.windowHandle() if sheet is not None else None
        up = handle is not None and handle.isExposed()
        self._looked += 1
        if not up and self._looked < LOOKS and not (self.opener_returned and sheet is None):
            QTimer.singleShot(LOOK_MS, self._reply)
            return
        if sheet is None:
            return
        # The sheet fades and rises as it opens; a key sent during that is answered by the end of it.
        still(sheet)
        self.seen.append(sheet.objectName())
        self.answer(sheet)

    def finish(self, qapp) -> list[str]:
        """After the opening call returned: the sheet is closed and has handed the keyboard back."""
        self.opener_returned = True
        wait_until(qapp, lambda: QApplication.activeModalWidget() is None, what="the sheet to close")
        # The sheet hands the keyboard back on the turn after it hides.
        for _ in range(10):
            qapp.processEvents()
        return self.seen


def click_with_sheet(qapp, window, hours: HoursCanvas, day: int, minute: int,
                     answer: Callable[[QDialog], None]) -> list[str]:
    """Click the grid at (day, minute); `answer` is given the sheet that opens. Returns its objectName."""
    hours.reveal(day, minute, minute + 60)
    qapp.processEvents()
    answering = SheetAnswer(answer)
    answering.arm()
    at = window.mapFromGlobal(hours.point_for(day, minute + 7))
    QTest.mouseClick(window.windowHandle(), Qt.MouseButton.LeftButton, NONE, at)
    return answering.finish(qapp)


def escape(sheet: QDialog) -> None:
    QTest.keyClick(sheet.windowHandle(), Qt.Key.Key_Escape)


def name_and_save(sheet: QDialog) -> None:
    title = sheet.findChild(BlockDialog) or sheet
    title.title.setFocus()
    for char in "Club":
        QTest.keyClick(sheet.windowHandle(), char)
    for _ in range(3):
        QTest.keyClick(sheet.windowHandle(), Qt.Key.Key_Return)
