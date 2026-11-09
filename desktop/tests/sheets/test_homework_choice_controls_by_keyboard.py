"""The choice controls of Add homework (when to do it, how to spread it) work from the keyboard: Tab lands on
the chosen segment, Right/Left change the value, End picks the last, Home the first, and the keyboard follows
the chosen segment."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.widgets import HomeworkDialog, Segmented
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_homework import go_length, go_when
from desktop.tests.sheets.support_keys import press, tab_into
from desktop.tests.window_support import free, qapp  # noqa: F401

STEPS = {"homeworkWhen": go_when, "homeworkSpread": go_length}


@pytest.mark.parametrize("name", list(STEPS))
def test_a_homework_choice_control_works_from_the_keyboard(qapp, window, name) -> None:
    dialog = HomeworkDialog(window, today=window.session.week_start, category="assignments")
    try:
        dialog.show()
        assert QTest.qWaitForWindowExposed(dialog)
        dialog.activateWindow()
        STEPS[name](dialog)
        qapp.processEvents()
        box = dialog.findChild(Segmented, name)
        assert box is not None and box.isVisible(), f"{name} not shown"
        chosen = box.currentIndex()
        landed = tab_into(box)
        said = f"Tab landed on {landed and landed.objectName()}, chosen {chosen}"
        assert landed is box.buttons()[chosen], said
        step = Qt.Key.Key_Right if chosen < box.count() - 1 else Qt.Key.Key_Left
        press(box, step)
        assert box.currentIndex() != chosen, "Right/Left did not change the value"
        press(box, Qt.Key.Key_End)
        assert box.currentIndex() == box.count() - 1, "End did not pick the last"
        press(box, Qt.Key.Key_Home)
        assert box.currentIndex() == 0, "Home did not pick the first"
        assert QApplication.focusWidget() is box.buttons()[0], "focus did not follow the chosen segment"
    finally:
        dialog.hide()
        free(dialog)
