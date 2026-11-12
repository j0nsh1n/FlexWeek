"""Leaving Add homework after typing with Cancel or the close button asks "Discard what you typed?" with Keep
editing as the safe answer; leaving it untouched, or closing it from code, never asks. Esc on a new Add sheet
with typing closes at once and hands the window a draft: the fields the student typed or picked, as plain
values (Jonathan, 2026-11-11). Edit homework still asks on Esc."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt, QTime, QTimer
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from desktop.native.widgets import SPREAD_MIN, ConfirmSheet, HomeworkDialog
from desktop.tests.sheets.support_homework import TODAY, essay, host, opened
from desktop.tests.window_support import free, qapp  # noqa: F401


def esc(dialog: HomeworkDialog) -> None:
    QTest.keyClick(dialog, Qt.Key.Key_Escape)


def cancel(dialog: HomeworkDialog) -> None:
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel).click()


def test_esc_on_untouched_add_homework_closes(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    esc(dialog)
    assert dialog.result() == QDialog.DialogCode.Rejected
    free(dialog)
    free(parent)


def test_cancel_after_typing_asks_discard_what_you_typed(qapp: QApplication) -> None:  # noqa: F811
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
    cancel(dialog)
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
    cancel(dialog)
    qapp.processEvents()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert not dialog.kept_on_escape, "Discard keeps nothing"
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
    cancel(dialog)
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


def test_esc_on_untouched_add_homework_closes_and_keeps_nothing(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    esc(dialog)
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert not dialog.kept_on_escape
    assert dialog.draft() == {}
    free(dialog)
    free(parent)


def test_esc_after_typing_closes_add_homework_at_once_and_marks_it_kept(
    qapp: QApplication,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ConfirmSheet, "exec", lambda _sheet: pytest.fail("Esc asked a question"))
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")
    esc(dialog)
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert not dialog.isVisible()
    assert dialog.kept_on_escape
    assert dialog.draft() == {"title": "History essay"}
    free(dialog)
    free(parent)


def test_esc_after_typing_on_a_later_page_keeps_the_words_too(
    qapp: QApplication,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ConfirmSheet, "exec", lambda _sheet: pytest.fail("Esc asked a question"))
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")
    dialog._save.click()
    dialog._save.click()
    qapp.processEvents()
    assert dialog._add_step == 2
    dialog.estimate.setValue(45)
    esc(dialog)
    assert dialog.kept_on_escape
    assert dialog.draft() == {"title": "History essay", "estimate": 45}
    free(dialog)
    free(parent)


def test_esc_on_a_typed_edit_homework_still_asks_and_keeps_nothing(
    qapp: QApplication,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[str] = []

    def answer(sheet: ConfirmSheet) -> int:
        asked.append(sheet.windowTitle())
        sheet.buttons["stay"].click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ConfirmSheet, "exec", answer)
    parent = host()
    dialog = opened(parent, essay())
    dialog.title.setText("History essay, redone")
    esc(dialog)
    assert asked == ["Discard what you typed?"]
    assert dialog.isVisible()
    assert not dialog.kept_on_escape
    free(dialog)
    free(parent)


# What a homework draft holds --------------------------------------------------------------


def test_a_homework_draft_holds_only_what_was_typed_or_picked(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.title.setText("History essay")
    assert dialog.draft() == {"title": "History essay"}, "the due, length, pin and spread were never touched"
    dialog.due.set_value("2026-09-18")
    dialog.estimate.setValue(SPREAD_MIN * 4)
    dialog.spread_choice.setCurrentIndex(dialog.spread_choice.findData("spread"))
    assert dialog.draft() == {
        "title": "History essay",
        "due": "2026-09-18",
        "estimate": 240,
        "spread": "spread",
    }
    free(dialog)
    free(parent)


def test_a_due_time_is_kept_with_its_time(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    dialog = opened(parent)
    dialog.due.set_value("2026-09-18T09:30")
    assert dialog.draft() == {"due": "2026-09-18T09:30"}
    free(dialog)
    free(parent)


def test_switching_to_a_pin_without_touching_its_time_keeps_the_choice_not_the_time(
    qapp: QApplication,  # noqa: F811
) -> None:
    """A new sheet offers a pin time of its own (the next quarter hour from its clock). Taking it as offered
    keeps "Pin to a time" and leaves the time and day to the next sheet."""
    parent = host()
    dialog = opened(parent)
    dialog.when.setCurrentIndex(dialog.when.findData("fixed"))
    assert dialog.draft() == {"when": "fixed"}
    free(dialog)
    free(parent)


def test_a_pin_time_and_day_the_student_set_are_kept_even_when_they_equal_the_ones_offered(
    qapp: QApplication,  # noqa: F811
) -> None:
    parent = host()
    dialog = opened(parent)
    offered_day, offered_minutes = dialog._day, dialog.when_time.minutes()
    dialog.when.setCurrentIndex(dialog.when.findData("fixed"))
    dialog.when_time.setTime(QTime(offered_minutes // 60, offered_minutes % 60))
    dialog.when_day.set_days([offered_day])
    dialog._pick_day()
    assert dialog.draft() == {
        "when": "fixed",
        "pin_day": offered_day,
        "pin_time": f"{offered_minutes // 60:02d}:{offered_minutes % 60:02d}",
    }
    free(dialog)
    free(parent)


def test_a_homework_draft_fills_a_new_sheet_with_those_fields_only(qapp: QApplication) -> None:  # noqa: F811
    parent = host()
    first = opened(parent)
    first.title.setText("History essay")
    first.due.set_value("2026-09-18T09:30")
    first.when.setCurrentIndex(first.when.findData("fixed"))
    first.when_day.buttons[3].click()
    first.when_time.setTime(QTime(17, 0))
    first.estimate.setValue(90)
    draft = first.draft()
    free(first)
    second = HomeworkDialog(parent, None, TODAY)
    second.apply_draft(draft)
    second.show()
    qapp.processEvents()
    assert second.title.text() == "History essay"
    assert second.due.value() == "2026-09-18T09:30"
    assert second.when.currentData() == "fixed"
    assert second._day == 3
    assert second.when_time.minutes() == 17 * 60
    assert second.estimate.value() == 90
    assert second.spread_choice.currentData() == "one"
    assert second.draft() == draft
    free(second)
    free(parent)


def test_a_draft_with_only_a_title_leaves_the_new_sheets_own_due_pin_and_length(
    qapp: QApplication,  # noqa: F811
) -> None:
    parent = host()
    fresh = opened(parent)
    expected = (fresh.due.value(), fresh._day, fresh.when_time.minutes(), fresh.estimate.value())
    free(fresh)
    second = HomeworkDialog(parent, None, TODAY)
    second.apply_draft({"title": "History essay"})
    second.show()
    qapp.processEvents()
    assert (second.due.value(), second._day, second.when_time.minutes(), second.estimate.value()) == expected
    assert second.when.currentData() == "plan"
    free(second)
    free(parent)


def test_a_sheet_opened_from_a_draft_counts_as_typed(
    qapp: QApplication,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = host()
    dialog = HomeworkDialog(parent, None, TODAY)
    dialog.apply_draft({"title": "History essay"})
    dialog.show()
    qapp.processEvents()
    asked: list[str] = []

    def answer(sheet: ConfirmSheet) -> int:
        asked.append(sheet.windowTitle())
        sheet.buttons["stay"].click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ConfirmSheet, "exec", answer)
    cancel(dialog)
    assert asked == ["Discard what you typed?"]
    monkeypatch.setattr(ConfirmSheet, "exec", lambda _sheet: pytest.fail("Esc asked a question"))
    esc(dialog)
    assert dialog.kept_on_escape
    assert dialog.draft() == {"title": "History essay"}
    free(dialog)
    free(parent)


def test_the_words_a_homework_sheet_reopens_with_are_not_selected_when_qt_focuses_the_title(
    qapp: QApplication,  # noqa: F811
) -> None:
    """`exec` gives the first field a Tab focus-in after showEvent, which selects all of it, so the next key
    replaced the kept words. The same focus-in is sent here, before the event loop runs."""
    parent = host()
    dialog = HomeworkDialog(parent, None, TODAY)
    dialog.apply_draft({"title": "History essay"})
    dialog.show()
    QApplication.sendEvent(dialog.title, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
    assert dialog.title.selectedText() == "History essay", "Qt's focus-in selects the title"
    qapp.processEvents()
    assert dialog.title.selectedText() == ""
    assert dialog.title.cursorPosition() == len("History essay")
    QTest.keyClicks(dialog.title, " draft")
    assert dialog.title.text() == "History essay draft"
    free(dialog)
    free(parent)


def test_an_edit_homework_sheet_keeps_selecting_its_title_the_way_it_did(
    qapp: QApplication,  # noqa: F811
) -> None:
    parent = host()
    dialog = HomeworkDialog(parent, essay(), TODAY)
    dialog.show()
    QApplication.sendEvent(dialog.title, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
    qapp.processEvents()
    assert dialog.title.selectedText() == "History essay"
    free(dialog)
    free(parent)
