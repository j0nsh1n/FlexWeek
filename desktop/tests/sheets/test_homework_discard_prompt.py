"""Leaving Add homework after typing asks "Discard what you typed?" with Keep editing as the safe answer;
leaving it untouched, or closing it from code, never asks."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from desktop.native.widgets import HomeworkDialog
from desktop.tests.sheets.support_homework import host, opened
from desktop.tests.window_support import free, qapp  # noqa: F401


def esc(dialog: HomeworkDialog) -> None:
    QTest.keyClick(dialog, Qt.Key.Key_Escape)


def test_esc_on_untouched_add_homework_closes(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    esc(dialog)
    assert dialog.result() == QDialog.DialogCode.Rejected
    free(dialog)
    free(parent)


def test_esc_after_typing_asks_discard_what_you_typed(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")
    seen: dict[str, object] = {}

    def peek() -> None:
        sheet = QApplication.activeModalWidget()
        seen["title"] = sheet.windowTitle() if sheet is not None else None
        seen["question"] = sheet.question.text() if sheet is not None else None
        seen["stay"] = sheet.buttons["stay"].text() if sheet is not None else None
        seen["discard"] = sheet.buttons["discard"].text() if sheet is not None else None
        seen["default"] = sheet.buttons["stay"].isDefault() if sheet is not None else None
        if sheet is not None:
            sheet.buttons["stay"].click()

    QTimer.singleShot(0, peek)
    esc(dialog)
    qapp.processEvents()
    assert seen["title"] == "Discard what you typed?"
    assert seen["question"] == "Discard what you typed?"
    assert seen["stay"] == "Keep editing"
    assert seen["discard"] == "Discard"
    assert seen["default"] is True
    assert dialog.isVisible()
    assert dialog.title.text() == "History essay"
    assert dialog.step_prompt.text() == "What is it?"
    free(dialog)
    free(parent)


def test_discard_closes_typed_add_homework(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")

    def peek() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is not None:
            sheet.buttons["discard"].click()

    QTimer.singleShot(0, peek)
    esc(dialog)
    qapp.processEvents()
    assert dialog.result() == QDialog.DialogCode.Rejected
    free(dialog)
    free(parent)


def test_esc_on_the_question_itself_keeps_editing(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")

    def peek() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is not None:
            QTest.keyClick(sheet, Qt.Key.Key_Escape)

    QTimer.singleShot(0, peek)
    esc(dialog)
    qapp.processEvents()
    assert dialog.isVisible()
    assert dialog.title.text() == "History essay"
    free(dialog)
    free(parent)


def test_cancel_after_typing_asks_too(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")
    asked: list[bool] = []

    def peek() -> None:
        sheet = QApplication.activeModalWidget()
        asked.append(sheet is not None)
        if sheet is not None:
            sheet.buttons["stay"].click()

    QTimer.singleShot(0, peek)
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel).click()
    qapp.processEvents()
    assert asked == [True]
    assert dialog.isVisible()
    free(dialog)
    free(parent)


def test_closing_from_code_never_asks(qapp: QApplication) -> None:  # noqa: F811
    """A close that is not a key or a button has nobody to answer the question: it must not wait."""
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert QApplication.activeModalWidget() is None
    free(dialog)
    free(parent)
