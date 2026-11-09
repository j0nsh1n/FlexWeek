"""D, M and W switch the planner between Day, Month and Week."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_keyboard_switches_week_day_and_month(qapp: QApplication, window: NativeWindow) -> None:
    window.setFocus()
    QTest.keyClick(window, Qt.Key.Key_D)
    wait_until(qapp, lambda: window.session.planner_view == "day")
    QTest.keyClick(window, Qt.Key.Key_M)
    wait_until(qapp, lambda: window.session.planner_view == "month")
    QTest.keyClick(window, Qt.Key.Key_W)
    wait_until(qapp, lambda: window.session.planner_view == "week")
