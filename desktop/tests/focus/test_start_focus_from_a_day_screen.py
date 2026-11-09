# ruff: noqa: F811
"""Start focus on a day screen opens the timer and Escape comes back to the planning page with the focus
panel in view."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    click,
    one_thing,
    qapp,  # noqa: F401
    wait_until,
    window,  # noqa: F401
)


def test_start_focus_keeps_the_timer_in_view_on_a_day_screen(
    qapp: QApplication, window: NativeWindow
) -> None:
    one_thing(window)
    click(window, "viewMyDay")
    assert window.focus_panel.isVisible() is False
    click(window, "oneFocus")
    wait_until(qapp, lambda: window.session.focus is not None)
    assert window.session.focus["title"] == "History essay"
    assert window._stack.currentWidget() is window.focus_screen
    QTest.keyClick(window.focus_screen, Qt.Key.Key_Escape)
    assert window._stack.currentWidget().objectName() == "weekPage"
    assert window.focus_panel.isVisible() is True
    assert window.solve_button.isVisible() is True
