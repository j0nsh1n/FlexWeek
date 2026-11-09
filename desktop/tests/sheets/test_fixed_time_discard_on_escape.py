"""Esc on the fixed-time sheet: after typing it asks before throwing the words away, and an untouched sheet
just closes."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog

from desktop.native.widgets import BlockDialog, ConfirmSheet
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump
from desktop.tests.sheets.support_settings_keys import shown
from desktop.tests.window_support import free, qapp  # noqa: F401


def press_escape(dialog: QDialog) -> None:
    dialog.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))


def test_escape_on_a_typed_fixed_time_asks_to_discard(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = shown(qapp, BlockDialog(window))
    try:
        dialog.activateWindow()
        pump(qapp)
        assert dialog.isVisible()
        dialog.title.setText("Piano lesson")
        pump(qapp)

        asked: list[tuple[str, str]] = []
        answers = iter(["stay", "discard"])

        def answer(sheet: ConfirmSheet) -> int:
            asked.append((sheet.windowTitle(), sheet.question.text()))
            sheet.buttons[next(answers)].click()
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(ConfirmSheet, "exec", answer)

        press_escape(dialog)
        assert asked == [("Discard what you typed?", "Discard what you typed?")]
        assert dialog.isVisible(), "Keep editing leaves the sheet open"

        press_escape(dialog)
        assert len(asked) == 2
        assert not dialog.isVisible()
        assert dialog.result() == QDialog.DialogCode.Rejected
    finally:
        free(dialog)


def test_escape_on_an_empty_fixed_time_just_closes(qapp: QApplication, window: NativeWindow) -> None:
    dialog = shown(qapp, BlockDialog(window))
    try:
        dialog.activateWindow()
        pump(qapp)
        assert dialog.isVisible()
        press_escape(dialog)
        pump(qapp)
        assert not dialog.isVisible()
        assert dialog.result() == QDialog.DialogCode.Rejected
    finally:
        free(dialog)
