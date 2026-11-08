"""The focus timer as the whole window: opened by Start focus, Quick focus or F, closed by Esc or Back."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QLineEdit, QPushButton

from desktop.native.focus import format_countdown, phase_duration_ms, remaining_ms
from desktop.native.focus_screen import READY
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.window import NativeWindow
from desktop.tests.focus.support_focus_screen import (  # noqa: F401
    LEFT,
    focus_window,
    on_screen,
    quick_focus,
    visible_buttons,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_quick_focus_fills_the_window_and_esc_comes_back(
    qapp: QApplication, focus_window: NativeWindow
) -> None:
    window = focus_window
    quick_focus(window)
    screen = window.focus_screen
    assert screen.isVisible() and window.findChild(QPushButton, "solveButton").isVisible() is False
    state = window.session.focus
    assert screen.time_text() == format_countdown(remaining_ms(state, window.session.now_ms()))
    assert screen.ring.left() == 1.0, "a timer just started has the whole ring to go"
    assert screen.phase.text() == "Focus"
    assert screen.task.text() == "Quick focus"
    assert visible_buttons(screen) == ["Back", "Pause", "Skip", "Finish"]

    QTest.keyClick(screen, Qt.Key.Key_Escape)
    assert on_screen(window) == "weekPage"
    assert window.session.focus is not None, "going back leaves the timer running"
    assert window._scene_for("mission").focus == "focusing", "a design is told the timer runs"
    panel = window.focus_panel
    # In Today's app's rail the timer is one line, its time in the words.
    line = panel.task.text()
    assert panel.task.isVisible() and line.startswith("Quick focus · ") and line.endswith(" left")
    assert visible_buttons(panel) == ["Focus screen"], "the strip keeps its line and one way back"
    QTest.mouseClick(panel.screen, LEFT)
    assert on_screen(window) == "focusPage"
    QTest.mouseClick(screen.back, LEFT)
    assert on_screen(window) == "weekPage"


def test_start_focus_from_the_strip_opens_it_on_that_homework(
    qapp: QApplication, focus_window: NativeWindow
) -> None:
    window = focus_window
    tasks = window.rail.tasks
    assert tasks.count() == 1
    tasks.setCurrentRow(0)
    QTest.keyClick(tasks, Qt.Key.Key_Return)
    wait_until(qapp, lambda: window.session.focus is not None)
    assert on_screen(window) == "focusPage"
    assert window.focus_screen.task.text() == "History essay"
    QTest.keyClick(window.focus_screen, Qt.Key.Key_Escape)
    wait_until(qapp, lambda: on_screen(window) == "weekPage")
    assert window.focus_panel.task.text().startswith("History essay · ")
    window.session.reset_focus()
    wait_until(qapp, lambda: window.session.focus is None)


def test_start_focus_on_my_day_opens_it(qapp: QApplication, focus_window: NativeWindow) -> None:
    window = focus_window
    # One thing has the Start focus button; Day dial, the default since 0.16, has none.
    window._layout = sanitize_layout({**window._layout, "day": "one"})
    window.findChild(QAbstractButton, "viewMyDay").click()
    window.findChild(QPushButton, "oneFocus").click()
    wait_until(qapp, lambda: window.session.focus is not None)
    assert on_screen(window) == "focusPage"
    assert window.focus_screen.task.text() == "History essay"
    QTest.keyClick(window.focus_screen, Qt.Key.Key_Escape)
    assert on_screen(window) == "weekPage"
    assert window._day_mode is True, "Esc leaves the focus screen, not My day"


def test_f_opens_it_ready_to_start_unless_typing(qapp: QApplication, focus_window: NativeWindow) -> None:
    window = focus_window
    field = QLineEdit(window.findChild(QPushButton, "solveButton").parentWidget())
    field.show()
    field.setFocus()
    QTest.keyClick(field, Qt.Key.Key_F)
    assert on_screen(window) == "weekPage", "an F typed into a box is a letter"
    field.deleteLater()
    window.week_table.hours.setFocus()

    QTest.keyClick(window.week_table.hours, Qt.Key.Key_F)
    assert on_screen(window) == "focusPage"
    screen = window.focus_screen
    assert window.session.focus is None, "F shows the timer; it does not start one"
    assert screen.phase.text() == READY
    assert screen.time_text() == format_countdown(phase_duration_ms("work", window.session.preferences))
    assert visible_buttons(screen) == ["Back", "Start"]
    QTest.mouseClick(screen.start, LEFT)
    assert window.session.focus is not None and window.session.focus["title"] == "Quick focus"
    assert visible_buttons(screen) == ["Back", "Pause", "Skip", "Finish"]


def test_a_week_change_does_not_take_the_screen_away(qapp: QApplication, focus_window: NativeWindow) -> None:
    window = focus_window
    quick_focus(window)
    window.session.week_changed.emit()
    assert on_screen(window) == "focusPage"
