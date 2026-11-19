# ruff: noqa: F811
"""Today's app keeps its own clock day and chip month."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    click,
    qapp,  # noqa: F401
    settled,
    window,  # noqa: F401
)


def test_todays_app_keeps_the_clock_day_and_chip_month(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {}}
    click(window, "viewDay")
    assert window.planner.currentWidget() is window.day_view
    assert window.solve_button.isVisible() is True
    click(window, "viewMonth")
    settled(qapp, window)
    assert window.planner.currentWidget() is window.month_grid
