"""Typing into a sheet's time boxes the way a student does, and the 12-hour clock for the length of a test.

Used by the fixed-time editor's tests and the form-problem tests of this area."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.weekmodel import set_clock_24h
from desktop.tests.waiting import wait_until


@pytest.fixture()
def twelve_hour_clock() -> Iterator[None]:
    """The account's clock as 4:30 PM instead of 16:30, put back to the app's default afterwards."""
    set_clock_24h(False)
    try:
        yield
    finally:
        set_clock_24h(True)


def show_and_focus(app: QApplication, widget: QWidget) -> None:
    """Show `widget` and give its window the keyboard, so typed keys reach it."""
    widget.show()
    handle = widget.window().windowHandle()
    wait_until(app, handle.isExposed)
    widget.window().activateWindow()
    app.processEvents()


def press(field: QWidget, key: Qt.Key | str) -> None:
    QTest.keyClick(field.window().windowHandle(), key)
    QApplication.processEvents()


def type_text(field: QWidget, text: str) -> None:
    for char in text:
        press(field, char)


def tab_into(field: QWidget) -> None:
    """Get the keyboard into a time box with a real Tab from the widget before it in the focus chain.
    The chain is a ring, so stop after one lap if a dialog that was never shown has nothing to start from."""
    inner = field.lineEdit() if hasattr(field, "lineEdit") else field
    before = field.previousInFocusChain()
    for _lap in range(len(QApplication.allWidgets()) + 2):
        if (
            before.isVisible()
            and before.isEnabled()
            and before.focusPolicy() & Qt.FocusPolicy.TabFocus
            and before is not inner
        ):
            break
        before = before.previousInFocusChain()
    else:
        raise AssertionError("no visible, tab-focusable widget before the box: is its dialog shown?")
    before.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    press(field, Qt.Key.Key_Tab)
    assert field.hasFocus() or inner.hasFocus(), "Tab did not give the box the keyboard"


def type_over(app: QApplication, field: QWidget, text: str) -> None:
    """Replace what `field` shows, then Tab away, so a clock settles the way a student leaves it."""
    field.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    line = field.lineEdit() if hasattr(field, "lineEdit") else field
    line.selectAll()
    handle = field.window().windowHandle()
    for char in text:
        QTest.keyClick(handle, char)
        app.processEvents()
    QTest.keyClick(handle, Qt.Key.Key_Tab)
    app.processEvents()
