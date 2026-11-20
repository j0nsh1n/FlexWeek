"""On Material, the number keys 1, 3 and 2 switch the planner between Day, Month and Week. (The letters D, M
and W were the Widgets keys; Material's letter keys are P, Z and F.)"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import quick_of
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import _show_material
from desktop.tests.window_support import qapp  # noqa: F401


def test_keyboard_switches_week_day_and_month(qapp: QApplication, window: NativeWindow) -> None:
    _show_material(qapp, window)
    QTest.keyClick(quick_of(window), Qt.Key.Key_1)
    wait_until(qapp, lambda: window.session.planner_view == "day")
    QTest.keyClick(quick_of(window), Qt.Key.Key_3)
    wait_until(qapp, lambda: window.session.planner_view == "month")
    QTest.keyClick(quick_of(window), Qt.Key.Key_2)
    wait_until(qapp, lambda: window.session.planner_view == "week")
