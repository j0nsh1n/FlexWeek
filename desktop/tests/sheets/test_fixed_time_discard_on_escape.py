"""Leaving the fixed-time sheet with typed words: Cancel and the close button ask before throwing them
away, an untouched sheet just closes, and Esc on a new Add sheet closes at once and keeps what was typed, as
plain values, for the next plain Add of that kind (Jonathan, 2026-11-11: "Yes plain should follow"
Material). The window-level tests run the window's own Add paths with `exec` replaced by a script, for Add
homework and Add fixed time alike. Expected values come from the requirement."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt, QTime
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from backend.tests.fake_clock import CLOCK
from desktop.native.widgets import BlockDialog, ConfirmSheet, HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump
from desktop.tests.sheets.support_settings_keys import shown
from desktop.tests.window_support import free, qapp, turn_on_letter_keys  # noqa: F401


def press_escape(dialog: QDialog) -> None:
    dialog.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))


def press_cancel(dialog: QDialog) -> None:
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel).click()


def refuse_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ConfirmSheet, "exec", lambda _sheet: pytest.fail("a question was asked"))


def answer_keep_editing(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Answers the discard question with Keep editing and returns the questions asked."""
    asked: list[str] = []

    def answer(sheet: ConfirmSheet) -> int:
        asked.append(sheet.windowTitle())
        sheet.buttons["stay"].click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ConfirmSheet, "exec", answer)
    return asked


def test_cancel_on_a_typed_fixed_time_asks_to_discard(
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

        press_cancel(dialog)
        assert asked == [("Discard what you typed?", "Discard what you typed?")]
        assert dialog.isVisible(), "Keep editing leaves the sheet open"

        press_cancel(dialog)
        assert len(asked) == 2
        assert not dialog.isVisible()
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert not dialog.kept_on_escape, "Discard keeps nothing"
    finally:
        free(dialog)


def test_escape_on_an_empty_fixed_time_just_closes_and_keeps_nothing(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = shown(qapp, BlockDialog(window))
    try:
        dialog.activateWindow()
        pump(qapp)
        assert dialog.isVisible()
        press_escape(dialog)
        pump(qapp)
        assert not dialog.isVisible()
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert not dialog.kept_on_escape
        assert dialog.draft() == {}
    finally:
        free(dialog)


def test_escape_on_a_typed_new_fixed_time_closes_at_once_and_marks_it_kept(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = shown(qapp, BlockDialog(window))
    try:
        dialog.activateWindow()
        pump(qapp)
        dialog.title.setText("Piano lesson")
        refuse_questions(monkeypatch)
        press_escape(dialog)
        assert not dialog.isVisible()
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert dialog.kept_on_escape
        assert dialog.draft() == {"title": "Piano lesson"}
    finally:
        free(dialog)


def test_escape_on_a_typed_edit_fixed_time_still_asks_and_keeps_nothing(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    block = {
        "id": "piano",
        "title": "Piano",
        "kind": "locked",
        "category": "personal",
        "days": [2],
        "start": "16:00",
        "duration_min": 60,
    }
    dialog = shown(qapp, BlockDialog(window, block))
    try:
        dialog.activateWindow()
        pump(qapp)
        dialog.title.setText("Piano lesson")
        asked = answer_keep_editing(monkeypatch)
        press_escape(dialog)
        assert asked == ["Discard what you typed?"]
        assert dialog.isVisible()
        assert not dialog.kept_on_escape
    finally:
        free(dialog)


# What a fixed-time draft holds ----------------------------------------------------------


def test_a_fixed_time_draft_holds_only_what_was_typed_or_picked(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Start 08:00 moves the guessed category and the end by itself; neither is the student's pick, so only
    the start (and the title) are kept and the new sheet works the rest out."""
    dialog = shown(qapp, BlockDialog(window, day=2, start="16:00"))
    try:
        dialog.title.setText("Piano lesson")
        dialog.start.setTime(QTime(8, 0))
        assert dialog.category.currentData() == "class", "the guess followed the start"
        assert dialog.draft() == {"title": "Piano lesson", "start": "08:00"}
    finally:
        free(dialog)


def test_a_start_picked_equal_to_the_one_shown_is_still_kept(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The sheet shows 16:00 when it opens. Typing 16:00 is a pick: a sheet opened at another hour offers
    its own start, and the student's must win."""
    dialog = shown(qapp, BlockDialog(window, day=2, start="16:00"))
    try:
        dialog.title.setText("Piano lesson")
        dialog.start.setTime(QTime(16, 0))
        assert dialog.draft() == {"title": "Piano lesson", "start": "16:00"}
    finally:
        free(dialog)


def test_a_fixed_time_draft_holds_days_length_and_a_chosen_category(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = shown(qapp, BlockDialog(window, day=2, start="16:00"))
    try:
        dialog.days[4].setChecked(True)
        dialog.end.setTime(QTime(17, 30))
        dialog.category.setCurrentIndex(dialog.category.findData("exercise"))
        assert dialog.draft() == {"days": [2, 4], "length": 90, "category": "exercise"}
    finally:
        free(dialog)


def test_an_end_typed_by_hand_is_kept_as_typed(qapp: QApplication, window: NativeWindow) -> None:
    dialog = shown(qapp, BlockDialog(window, day=2, start="16:00"))
    try:
        line = dialog.end.lineEdit()
        dialog.end.setFocus()
        line.selectAll()
        QTest.keyClicks(line, "17:30")
        QTest.keyClick(line, Qt.Key.Key_Return)
        assert dialog.end.time() == QTime(17, 30)
        assert dialog.draft() == {"length": 90, "end_by_hand": True}
    finally:
        free(dialog)


def test_a_fixed_time_draft_fills_a_new_sheet_with_those_fields_only(
    qapp: QApplication, window: NativeWindow
) -> None:
    first = shown(qapp, BlockDialog(window, day=2, start="16:00"))
    try:
        first.title.setText("Piano lesson")
        first.days[4].setChecked(True)
        first.start.setTime(QTime(9, 0))
        first.end.setTime(QTime(11, 30))
        first.category.setCurrentIndex(first.category.findData("exercise"))
        draft = first.draft()
    finally:
        free(first)
    # A sheet that opens for another day and hour: only the draft's fields are the student's.
    second = BlockDialog(window, day=1, start="20:00")
    try:
        second.apply_draft(draft)
        shown(qapp, second)
        assert second.title.text() == "Piano lesson"
        assert [index for index, check in enumerate(second.days) if check.isChecked()] == [2, 4]
        assert second.start.time() == QTime(9, 0)
        assert second.end.time() == QTime(11, 30)
        assert second.category.currentData() == "exercise"
        assert second.draft() == draft, "the kept values are the sheet's draft again"
    finally:
        free(second)


def test_a_draft_without_a_start_leaves_the_new_sheets_own_start_and_end(
    qapp: QApplication, window: NativeWindow
) -> None:
    second = BlockDialog(window, day=1, start="20:00")
    try:
        second.apply_draft({"title": "Piano lesson"})
        shown(qapp, second)
        assert second.title.text() == "Piano lesson"
        assert second.start.time() == QTime(20, 0)
        assert second.end.time() == QTime(21, 0)
        assert [index for index, check in enumerate(second.days) if check.isChecked()] == [1]
    finally:
        free(second)


def test_a_length_kept_without_a_start_follows_the_new_sheets_start(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The student made it 90 minutes long and never touched the start: the next sheet's own start, plus
    their 90 minutes, not an end time from the old hour."""
    second = BlockDialog(window, day=1, start="20:00")
    try:
        second.apply_draft({"length": 90})
        shown(qapp, second)
        assert second.start.time() == QTime(20, 0)
        assert second.end.time() == QTime(21, 30)
    finally:
        free(second)


def test_a_fixed_time_sheet_opened_from_a_draft_counts_as_typed(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = BlockDialog(window)
    dialog.apply_draft({"title": "Piano lesson"})
    shown(qapp, dialog)
    try:
        assert dialog.draft() == {"title": "Piano lesson"}, "measured from the fresh sheet, the words show"
        asked = answer_keep_editing(monkeypatch)
        press_cancel(dialog)
        assert asked == ["Discard what you typed?"], "Cancel on a reopened sheet asks"
        refuse_questions(monkeypatch)
        press_escape(dialog)
        assert dialog.kept_on_escape, "Esc keeps the draft again"
        assert dialog.draft() == {"title": "Piano lesson"}
    finally:
        free(dialog)


def test_the_words_a_fixed_time_sheet_reopens_with_are_not_selected_when_qt_focuses_the_title(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Showing a dialog with `exec` gives its first field a Tab focus-in after showEvent, which selects all
    of it, so the next key replaced the kept words. The same focus-in is sent here, before the event loop
    runs, as `exec` sends it."""
    dialog = BlockDialog(window)
    dialog.apply_draft({"title": "Piano lesson"})
    try:
        dialog.show()
        QApplication.sendEvent(dialog.title, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
        assert dialog.title.selectedText() == "Piano lesson", "Qt's focus-in selects the title"
        pump(qapp)
        assert dialog.title.selectedText() == ""
        assert dialog.title.cursorPosition() == len("Piano lesson")
        QTest.keyClicks(dialog.title, " Tuesday")
        assert dialog.title.text() == "Piano lesson Tuesday"
    finally:
        free(dialog)


ANOTHER_BLOCK = {
    "id": "piano",
    "title": "Piano",
    "kind": "locked",
    "category": "personal",
    "days": [2],
    "start": "16:00",
    "duration_min": 60,
}


def test_an_edit_sheet_keeps_selecting_its_title_the_way_it_did(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = BlockDialog(window, dict(ANOTHER_BLOCK))
    try:
        dialog.show()
        QApplication.sendEvent(dialog.title, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
        pump(qapp)
        assert dialog.title.selectedText() == "Piano"
    finally:
        free(dialog)


# The window's own Add paths ----------------------------------------------------------

KINDS = ["homework", "block"]
DIALOGS = {"homework": HomeworkDialog, "block": BlockDialog}
PLAIN_ADD = {"homework": "_add_homework", "block": "_add_fixed"}
ADD_WITH_VALUES = {
    "homework": lambda window: window._add_homework_due("2026-09-30"),
    "block": lambda window: window._add_fixed_at(2, 735),
}


class Script:
    """Stands in for `exec` on one kind of sheet: each call runs the next action on the sheet it is given
    and records which sheet it was and what its title held when it opened."""

    def __init__(self, kind: str, monkeypatch: pytest.MonkeyPatch, *actions) -> None:
        self.actions = list(actions)
        self.sheets: list[QDialog] = []
        self.titles: list[str] = []

        def run(dialog: QDialog) -> int:
            dialog.show()
            self.sheets.append(dialog)
            self.titles.append(dialog.title.text())
            return self.actions.pop(0)(dialog)

        monkeypatch.setattr(DIALOGS[kind], "exec", run)


def type_then_escape(dialog: QDialog) -> int:
    dialog.title.setText("Piano lesson")
    press_escape(dialog)
    return int(dialog.result())


def only_look(dialog: QDialog) -> int:
    dialog.reject()
    return int(QDialog.DialogCode.Rejected)


def save(dialog: QDialog) -> int:
    dialog.accept()
    return int(QDialog.DialogCode.Accepted)


def cancel_and_discard(monkeypatch: pytest.MonkeyPatch):
    def run(dialog: QDialog) -> int:
        def discard(sheet: ConfirmSheet) -> int:
            sheet.buttons["discard"].click()
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(ConfirmSheet, "exec", discard)
        press_cancel(dialog)
        return int(dialog.result())

    return run


@pytest.fixture()
def quiet_commit(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> NativeWindow:
    """What the window does with a saved sheet goes to the backend; it is not what these tests are about,
    so the session's writes are stubbed and the window's own keep-or-drop code still runs."""
    for name in ("add_homework", "add_block", "save", "plan_after_save"):
        monkeypatch.setattr(window.session, name, lambda *args, **kwargs: None)
    return window
































# What the next sheet works out for itself -----------------------------------------------


def at(hour: int, minute: int = 0, *, day: int = 0) -> datetime:
    base = CLOCK.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base.replace(day=base.day + day)


def pin_state(sheet: HomeworkDialog) -> list:
    fixed = sheet._fixed_at()
    over = sheet._fixed_problem(fixed, sheet._chosen_due()) if fixed else ""
    return [
        sheet.when.currentData(),
        sheet._day,
        sheet.when_time.minutes(),
        over,
        sheet.when_from.text(),
    ]




def pin_state_for_new_sheet_at(window: NativeWindow, moment: datetime, *, pinned: bool) -> list:
    CLOCK.set(moment)
    sheet = HomeworkDialog(window, today=window._today(), category="assignments")
    try:
        if pinned:
            sheet.when.setCurrentIndex(sheet.when.findData("fixed"))
        return pin_state(sheet)
    finally:
        free(sheet)












def test_a_fixed_time_reopened_with_its_kept_start_says_its_length_not_that_the_end_moved(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The kept start is put into the new sheet by the app, not moved by the student in it, so the line
    under the times says "1 h" as on any new sheet, not "End moved to 6:30 PM to keep it 1 h."."""
    sheet = shown(qapp, BlockDialog(window, day=2, start="16:00", duration_min=60, category=None))
    sheet.apply_draft({"title": "Piano lesson", "start": "17:30"})
    assert sheet.duration_line.text() == "1 h"
    free(sheet)


def test_a_fixed_time_sheet_built_ahead_of_time_says_its_length_not_that_the_end_moved(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The window builds one Add fixed time sheet ahead and fills it in when Add is pressed. Filling in
    the start is not the student moving it."""
    sheet = BlockDialog(window, day=0, start="09:00", duration_min=60, category=None)
    sheet.fill_new(day=2, start="19:15", category=None)
    shown(qapp, sheet)
    assert sheet.duration_line.text() == "1 h"
    free(sheet)


def _look(seen: list) -> Callable[[QDialog], int]:
    """Record the days the sheet opened with, by their pill names and numbers, then close it."""

    def run(dialog: QDialog) -> int:
        picker = dialog.day_picker if isinstance(dialog, BlockDialog) else dialog.when_day
        names = [button.text().split("\n")[0] for button in picker.buttons if button.isChecked()]
        seen.append((picker.days(), names))
        return only_look(dialog)

    return run


def _pick_friday_then_escape(dialog: QDialog) -> int:
    dialog.title.setText("Piano lesson")
    if isinstance(dialog, BlockDialog):
        for index, check in enumerate(dialog.days):
            check.setChecked(index == 4)
    else:
        dialog.when.setCurrentIndex(dialog.when.findData("fixed"))
        dialog.when_day.buttons[4].click()
    press_escape(dialog)
    return int(dialog.result())






def _pick_monday_then_escape(dialog: QDialog) -> int:
    dialog.title.setText("Piano lesson")
    if isinstance(dialog, BlockDialog):
        for index, check in enumerate(dialog.days):
            check.setChecked(index == 0)
    else:
        dialog.when.setCurrentIndex(dialog.when.findData("fixed"))
        # As if kept on Monday, when Monday was still tickable: past days are greyed by Thursday.
        dialog.when_day.buttons[0].setChecked(True)
    press_escape(dialog)
    return int(dialog.result())


def _moved_pill(picker, day: int) -> tuple[bool, bool, str]:
    button = picker.buttons[day]
    return button.isChecked(), bool(button.property("moved")), button.accessibleName()
