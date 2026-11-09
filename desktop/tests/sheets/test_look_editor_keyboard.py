"""The look editor with the keyboard: Esc closes it, and Tab reaches Done in five presses."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump
from desktop.tests.sheets.support_settings_keys import open_editor
from desktop.tests.window_support import qapp  # noqa: F401


def test_escape_closes_the_look_editor(qapp: QApplication, window: NativeWindow) -> None:
    window._use_widgets_styles()
    page, editor = open_editor(qapp, window)
    window.activateWindow()
    pump(qapp)
    assert editor.isVisible()

    editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    pump(qapp)
    assert page.editor is None or not page.editor.isVisible()


def test_tab_reaches_done_in_the_look_editor_in_five_presses(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._use_widgets_styles()
    _page, editor = open_editor(qapp, window)
    window.activateWindow()
    pump(qapp)
    assert editor.isVisible()

    editor.back.setFocus()
    pump(qapp)
    assert editor.back.hasFocus() or QApplication.focusWidget() is editor.back

    presses = 0
    for _ in range(5):
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        pump(qapp)
        presses += 1
        if editor.done.hasFocus() or QApplication.focusWidget() is editor.done:
            break

    assert editor.done.hasFocus() or QApplication.focusWidget() is editor.done
    assert presses <= 5
