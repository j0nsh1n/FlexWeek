"""The week list opens from More or Ctrl+Shift+L without moving the grid.
Esc closes it and returns the keyboard to its previous control.

How the list sits over the week and how its menu entry is drawn is judged on the pictures
(pictures/week_clock.py: week.week-list-panel, week.more-menu-week-list-entry)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp, settled  # noqa: F401

CTRL_SHIFT = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
ROW_NAME = "Week as a list"


def key(window, k, mods=Qt.KeyboardModifier.NoModifier) -> None:
    QTest.keyClick(window.windowHandle(), k, mods)
    for _ in range(3):
        QApplication.processEvents()


def with_school(qapp, window) -> None:
    window.session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:30",
            "duration_min": 405,
            "days": [0, 1, 2, 3, 4],
        }
    )
    settled(qapp, window)


def grid_top(window) -> int:
    return window.planner.mapTo(window, QPoint(0, 0)).y()


def menu_entry(window):
    window._sync_more_menu()
    return next(action for action, button in window._more_pairs if button is window.week_list_row)






















def test_the_week_list_no_longer_resizes_the_window_with_focus() -> None:
    from desktop.native import window as module

    assert not hasattr(module, "WEEK_LIST_OPEN") and not hasattr(module, "WEEK_LIST_FOLDED")


