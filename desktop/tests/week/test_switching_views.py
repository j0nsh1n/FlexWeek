"""Switching between My day, Day, Week and Month: the four view buttons are one keyboard radio group that a
screen reader announces as one, and W, D and M switch views while a calendar holds the keyboard. How the
labels fit their buttons is a picture (desktop/tests/pictures/_week_g14.py, week.view_switcher_labels)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QRadioButton

from desktop.native.look import VIEW_BUTTONS
from desktop.native.widgets import SegmentTrack
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-switching-views"])


def views(window: NativeWindow) -> list[QRadioButton]:
    return [window.findChild(QRadioButton, name) for name in VIEW_BUTTONS]


def press(window: NativeWindow, key: Qt.Key) -> None:
    QTest.keyClick(window.windowHandle(), key)
    QApplication.processEvents()


def selected(buttons: list[QRadioButton]) -> int:
    return next(index for index, button in enumerate(buttons) if button.isChecked())


def test_view_switcher_is_one_keyboard_radio_group(qapp: QApplication, window: NativeWindow) -> None:
    buttons = views(window)
    assert window.findChild(SegmentTrack, "segments") is not None
    buttons[1].click()
    qapp.processEvents()
    assert [button for button in buttons if button.focusPolicy() & Qt.FocusPolicy.TabFocus] == [buttons[1]]

    before = buttons[0].previousInFocusChain()
    while before is not None and (
        before in buttons or not (before.isVisible() and before.focusPolicy() & Qt.FocusPolicy.TabFocus)
    ):
        before = before.previousInFocusChain()
    assert before is not None
    before.setFocus(Qt.FocusReason.OtherFocusReason)
    press(window, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is buttons[selected(buttons)]

    for key, expected in (
        (Qt.Key.Key_Left, 0),
        (Qt.Key.Key_Right, 1),
        (Qt.Key.Key_Up, 0),
        (Qt.Key.Key_Down, 1),
        (Qt.Key.Key_Home, 0),
        (Qt.Key.Key_End, 3),
    ):
        press(window, key)
        assert selected(buttons) == expected
        assert QApplication.focusWidget() is buttons[expected]
        assert bool(window._day_mode) is (expected == 3)


def test_view_switcher_has_radio_roles_and_one_accessible_group(window: NativeWindow) -> None:
    buttons = views(window)
    group = window.findChild(SegmentTrack, "segments")
    group_face = QAccessible.queryAccessibleInterface(group)
    assert group_face.role() == QAccessible.Role.Grouping
    assert group_face.text(QAccessible.Text.Name) == "Planner view"
    chosen = selected(buttons)
    for index, button in enumerate(buttons):
        face = QAccessible.queryAccessibleInterface(button)
        assert face.role() == QAccessible.Role.RadioButton
        assert bool(face.state().checked) is (index == chosen)
        assert face.text(QAccessible.Text.Name) == button.text()
        assert face.text(QAccessible.Text.Description) == f"{index + 1} of 4"
        assert face.parent().object() is group


def test_w_d_and_m_switch_views_while_the_calendar_has_the_keyboard(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A click in the calendar gives it the keyboard, and Qt sends keys to the widget that has it. Item
    views keep letter keys for their own type-ahead search, so W, D and M never reached the window. The
    key goes to the calendar itself, as a student's does, not to the window."""
    session = window.session
    QTest.keyClick(window.week_table.hours, Qt.Key.Key_D)
    wait_until(qapp, lambda: session.planner_view == "day" and not session.busy)
    QTest.keyClick(window.day_view.hours, Qt.Key.Key_M)
    wait_until(qapp, lambda: session.planner_view == "month" and not session.busy)
    QTest.keyClick(window.month_grid.canvas, Qt.Key.Key_W)
    wait_until(qapp, lambda: session.planner_view == "week" and not session.busy)
    QTest.keyClick(window.rail.tasks, Qt.Key.Key_M)
    wait_until(qapp, lambda: session.planner_view == "month" and not session.busy)
