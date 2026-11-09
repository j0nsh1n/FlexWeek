"""What the tests of where the keyboard goes after the week changes share: homework to plan, planning
by key or by click, and whether the keyboard sits on a button that turns the page."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.grid_support import WEDNESDAY, hold_clock, key
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import settled


def add_homework(qapp: QApplication, window: NativeWindow) -> None:
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
    settled(qapp, window)
    hold_clock(window, WEDNESDAY, 14 * 60 + 7)


def plan(qapp: QApplication, window: NativeWindow, with_keys: bool) -> None:
    solve = window.findChild(QPushButton, "solveButton")
    if with_keys:
        solve.setFocus(Qt.FocusReason.TabFocusReason)
        key(window, Qt.Key.Key_Space)
    else:
        QTest.mouseClick(solve, Qt.MouseButton.LeftButton)
    wait_until(qapp, lambda: window.toast.isVisible() and window.toast.button.isVisible())
    settled(qapp, window)


def stray(window: NativeWindow) -> bool:
    """Whether the keyboard sits on a button that turns the page."""
    return window.focusWidget() in (window.prev_nav, window.next_nav)
