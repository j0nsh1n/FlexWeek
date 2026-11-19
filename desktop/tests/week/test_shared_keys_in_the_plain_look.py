"""The plain look's one-key shortcuts: 1 to 4 under Number keys (on), the letters under Letter keys (off),
the same two saved settings Material reads. Ctrl+Shift+F is Quick focus. Expected values come from the
decision (one Google-style set in both looks), not from what the window does."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, qapp, turn_on_letter_keys  # noqa: F401

CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
LETTERS = (
    Qt.Key.Key_T,
    Qt.Key.Key_D,
    Qt.Key.Key_W,
    Qt.Key.Key_M,
    Qt.Key.Key_J,
    Qt.Key.Key_K,
    Qt.Key.Key_C,
    Qt.Key.Key_P,
    Qt.Key.Key_Z,
    Qt.Key.Key_F,
)


def _press(
    window: NativeWindow, key: Qt.Key, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
):
    window.setFocus()
    QTest.keyClick(window, key, modifiers)


def _page(window: NativeWindow) -> str:
    return window._stack.currentWidget().objectName()


@pytest.fixture()
def acted(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """What the add, plan, undo and focus keys reach, without opening a sheet that waits for an answer."""
    calls: list[str] = []
    monkeypatch.setattr(window, "_open_focus_screen", lambda: calls.append("focus"))
    monkeypatch.setattr(window, "_add_now", lambda: calls.append("add"))
    monkeypatch.setattr(window, "_plan_with_left_over", lambda everything=False: calls.append("plan"))
    monkeypatch.setattr(window.session, "undo", lambda: calls.append("undo"))
    return calls


def test_number_keys_open_day_week_and_month_by_default(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    _press(window, Qt.Key.Key_1)
    wait_until(qapp, lambda: session.planner_view == "day" and not session.busy)
    _press(window, Qt.Key.Key_3)
    wait_until(qapp, lambda: session.planner_view == "month" and not session.busy)
    _press(window, Qt.Key.Key_2)
    wait_until(qapp, lambda: session.planner_view == "week" and not session.busy)
