"""Add homework as three questions, pick C of forms.html: What, When, How long.

Due and Estimated time are not on the first page. Jonathan picked this over the one-page Add
dialog. Empty title is `Give the homework a title.` Enter on What advances. Edit stays one page.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QPushButton, QWidget

from desktop.native.widgets import HomeworkDialog
from desktop.tests.test_homework_form import go_length, go_when, host, opened
from desktop.tests.window_support import free, qapp  # noqa: F401


def crumbs(dialog: HomeworkDialog) -> list[str]:
    return [dialog.findChild(QPushButton, f"homeworkCrumb{index}").text() for index in range(3)]


def test_add_homework_opens_on_what_and_hides_due_and_estimated_time(
    qapp: QApplication,  # noqa: F811
) -> None:
    parent = host()
    dialog = opened(parent)
    assert dialog.step_prompt.text() == "What is it?"
    assert crumbs(dialog) == ["1 What", "2 When", "3 How long"]
    assert dialog.title.isVisibleTo(dialog)
    assert not dialog.due.isVisibleTo(dialog)
    assert not dialog.stepper.isVisibleTo(dialog)
    assert not dialog.more_details.isVisibleTo(dialog)
    assert dialog._save.text() == "Next"
    assert not dialog.back_button.isVisibleTo(dialog)
    cancel = next(button for button in dialog.findChildren(QPushButton) if button.text() == "Cancel")
    assert cancel.isVisibleTo(dialog)
    free(dialog)
    free(parent)


def test_empty_title_on_next_says_give_the_homework_a_title(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog._save.click()
    QApplication.processEvents()
    assert dialog.step_prompt.text() == "What is it?"
    assert dialog.title_problem.text() == "Give the homework a title."
    assert dialog.title_problem.isVisibleTo(dialog)
    assert dialog._save.text() == "Next"
    free(dialog)
    free(parent)


def test_next_then_crumbs_and_when_then_how_long(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")
    dialog._save.click()
    QApplication.processEvents()
    assert dialog.step_prompt.text() == "When is it due?"
    assert crumbs(dialog) == ["✓ History essay", "2 When", "3 How long"]
    assert dialog.due.isVisibleTo(dialog)
    assert dialog.when.isVisibleTo(dialog)
    assert not dialog.title.isVisibleTo(dialog)
    assert not dialog.stepper.isVisibleTo(dialog)
    assert dialog.back_button.isVisibleTo(dialog) and dialog.back_button.text() == "Back"
    assert dialog._save.text() == "Next"
    dialog._save.click()
    QApplication.processEvents()
    assert dialog.step_prompt.text() == "How long will it take?"
    assert crumbs(dialog) == ["✓ History essay", "✓ due Tue 15 Sep, FlexWeek picks", "3 How long"]
    assert dialog.stepper.isVisibleTo(dialog)
    assert dialog._save.text() == "Save"
    assert not dialog.due.isVisibleTo(dialog)
    free(dialog)
    free(parent)


def test_do_it_at_crumb_says_do_it_at(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")
    go_when(dialog)
    dialog.when.setCurrentIndex(1)
    dialog._save.click()
    QApplication.processEvents()
    assert crumbs(dialog)[1] == "✓ due Tue 15 Sep, pinned"
    free(dialog)
    free(parent)


def test_a_done_crumb_goes_back_to_that_question(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")
    go_length(dialog)
    dialog.findChild(QPushButton, "homeworkCrumb0").click()
    QApplication.processEvents()
    assert dialog.step_prompt.text() == "What is it?"
    assert dialog.title.isVisibleTo(dialog)
    assert dialog.title.text() == "History essay"
    free(dialog)
    free(parent)


def test_enter_on_what_advances_when_the_title_is_filled(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")
    dialog.title.setFocus()
    QTest.keyClick(dialog.title, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert dialog.step_prompt.text() == "When is it due?"
    free(dialog)
    free(parent)


def test_edit_homework_stays_one_page(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(
        parent,
        {
            "id": "essay",
            "title": "History essay",
            "due": "2026-09-25",
            "estimate_min": 60,
            "category": "assignments",
            "revision": 0,
        },
    )
    assert dialog.windowTitle() == "Edit homework"
    assert dialog.findChild(QWidget, "homeworkSteps") is None
    assert dialog.title.isVisibleTo(dialog)
    assert dialog.due.isVisibleTo(dialog)
    assert dialog.stepper.isVisibleTo(dialog)
    assert dialog._save.text() == "Save"
    labels = [label.text() for label in dialog.findChildren(QLabel) if label.objectName() == "fieldLabel"]
    assert "Due" in labels
    assert "Estimated time" in labels
    free(dialog)
    free(parent)


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
