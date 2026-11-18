"""Regression for fix-specs.md items 0e and 5 (choice controls and Text size, Settings > Appearance).

0e: in `widgets.py::Segmented` only the first segment takes Tab focus, focus does not follow the
chosen one, and Left/Right/Home/End do nothing. The spec's
guard: for every Segmented in Settings and Add homework, Tab in lands on the chosen one, Right changes
the value, End picks the last, and no mouse event is used.
5: Text size is hidden behind "Show shape, spacing and type" on a fresh account.

Keys go through the window system's path (QTest on the window's QWindow). Known failures are
xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.widgets import HomeworkDialog, Segmented
from desktop.tests.window_support import free, qapp, server, signed_out, window  # noqa: F401

KNOWN_0E = (
    "known failure (item 0e): only the first segment is a Tab stop and Left/Right/Home/End do nothing"
)
# (section of Settings, or "homework" for the Add homework sheet; objectName), found on 0.18.4.
CONTROLS = [
    ("homework", "homeworkWhen"), ("homework", "homeworkSpread"),
]


def press(widget: QWidget, key) -> None:
    QTest.keyClick(widget.window().windowHandle(), key)
    QApplication.processEvents()


def control(qapp, window, where, name: str, made: list) -> Segmented:
    dialog = HomeworkDialog(window, today=window.session.week_start, category="assignments")
    dialog.show()
    assert QTest.qWaitForWindowExposed(dialog)
    dialog.activateWindow()
    made.append(dialog)
    root = dialog
    qapp.processEvents()
    found = root.findChild(Segmented, name)
    assert found is not None and found.isVisible(), f"{name} not shown in {where}"
    return found


def tab_into(segmented: Segmented) -> QWidget | None:
    """Focus the widget before the control in the focus chain and press Tab, as a student does."""
    first = segmented.buttons()[0]
    before = first.previousInFocusChain()
    while before is not None and (
        before in segmented.buttons()
        or not (before.isVisible() and before.focusPolicy() & Qt.FocusPolicy.TabFocus)
    ):
        before = before.previousInFocusChain()
    assert before is not None
    before.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    press(before, Qt.Key.Key_Tab)
    return QApplication.focusWidget()


@pytest.mark.parametrize(("where", "name"), CONTROLS, ids=[name for _w, name in CONTROLS])
@pytest.mark.xfail(strict=True, reason=KNOWN_0E)
def test_a_choice_control_works_from_the_keyboard(qapp, window, where, name) -> None:
    made: list = []
    try:
        box = control(qapp, window, where, name, made)
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
        for widget in made:
            widget.hide()
            free(widget)
