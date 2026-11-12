"""Leaving the fixed-time sheet with typed words: Cancel and the close button ask before throwing them
away, an untouched sheet just closes, and Esc on a new Add sheet closes at once and keeps what was typed, as
plain values, for the next plain Add of that kind (Jonathan, 2026-11-11: "Yes plain should follow"
Material). The window-level tests run the window's own Add paths with `exec` replaced by a script, for Add
homework and Add fixed time alike. Expected values come from the requirement."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt, QTime
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from backend.tests.fake_clock import CLOCK
from desktop.native.weekmodel import set_clock_24h
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


def test_escape_through_the_sheets_own_shortcut_keeps_the_words_too(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fixed-time sheet has an Esc shortcut as well as the key handler; a real key press takes the
    shortcut, so it must do what the key handler does."""
    dialog = shown(qapp, BlockDialog(window))
    try:
        dialog.activateWindow()
        pump(qapp)
        dialog.title.setText("Piano lesson")
        refuse_questions(monkeypatch)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        assert not dialog.isVisible()
        assert dialog.kept_on_escape
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


@pytest.mark.parametrize("kind", KINDS)
def test_the_next_plain_add_opens_with_what_esc_kept(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    script = Script(kind, monkeypatch, type_then_escape, only_look)
    add = getattr(quiet_commit, PLAIN_ADD[kind])
    add()
    pump(qapp)
    add()
    assert script.titles == ["", "Piano lesson"]
    assert script.sheets[1] is not script.sheets[0], "a new sheet, filled in; not the closed one again"


@pytest.mark.parametrize("kind", KINDS)
def test_esc_leaves_no_sheet_behind_in_the_window(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Only plain values are kept between Esc and the next Add; the closed sheet is freed."""
    script = Script(kind, monkeypatch, type_then_escape)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    pump(qapp)
    from shiboken6 import isValid

    assert not isValid(script.sheets[0])
    for kept in quiet_commit._kept_adds.values():
        assert not any(isinstance(part, QDialog) for part in kept)


@pytest.mark.parametrize("kind", KINDS)
def test_the_kept_typing_is_used_once(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    script = Script(kind, monkeypatch, type_then_escape, only_look, only_look)
    add = getattr(quiet_commit, PLAIN_ADD[kind])
    for _ in range(3):
        add()
        pump(qapp)
    assert script.titles == ["", "Piano lesson", ""]


@pytest.mark.parametrize("kind, other", [("homework", "block"), ("block", "homework")])
def test_the_other_kinds_add_opens_empty(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str, other: str
) -> None:
    script = Script(kind, monkeypatch, type_then_escape)
    other_script = Script(other, monkeypatch, only_look)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    pump(qapp)
    getattr(quiet_commit, PLAIN_ADD[other])()
    assert script.titles == [""]
    assert other_script.titles == [""]


@pytest.mark.parametrize("kind", KINDS)
def test_an_untouched_sheet_closed_with_esc_keeps_nothing(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    def esc_only(dialog: QDialog) -> int:
        press_escape(dialog)
        return int(dialog.result())

    script = Script(kind, monkeypatch, esc_only, only_look)
    add = getattr(quiet_commit, PLAIN_ADD[kind])
    add()
    pump(qapp)
    add()
    assert script.titles == ["", ""]
    assert quiet_commit._kept_adds == {}


@pytest.mark.parametrize("kind", KINDS)
def test_an_add_that_brings_its_own_values_ignores_the_kept_typing_and_leaves_it(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    script = Script(kind, monkeypatch, type_then_escape, only_look, only_look)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    pump(qapp)
    ADD_WITH_VALUES[kind](quiet_commit)
    pump(qapp)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    assert script.titles == ["", "", "Piano lesson"]


@pytest.mark.parametrize("kind", KINDS)
def test_esc_with_typing_in_an_add_that_brings_its_own_values_replaces_the_kept_typing(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    def type_other_then_escape(dialog: QDialog) -> int:
        dialog.title.setText("Chemistry")
        press_escape(dialog)
        return int(dialog.result())

    script = Script(kind, monkeypatch, type_then_escape, type_other_then_escape, only_look)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    pump(qapp)
    ADD_WITH_VALUES[kind](quiet_commit)
    pump(qapp)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    assert script.titles == ["", "", "Chemistry"]


@pytest.mark.parametrize("kind", KINDS)
def test_a_save_clears_the_kept_typing(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    script = Script(kind, monkeypatch, type_then_escape, save, only_look)
    add = getattr(quiet_commit, PLAIN_ADD[kind])
    for _ in range(3):
        add()
        pump(qapp)
    assert script.titles == ["", "Piano lesson", ""]


@pytest.mark.parametrize("kind", KINDS)
def test_cancel_and_discard_clear_the_kept_typing(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    script = Script(kind, monkeypatch, type_then_escape, cancel_and_discard(monkeypatch), only_look)
    add = getattr(quiet_commit, PLAIN_ADD[kind])
    for _ in range(3):
        add()
        pump(qapp)
    assert script.titles == ["", "Piano lesson", ""]


@pytest.mark.parametrize("kind", KINDS)
def test_a_reopened_sheet_closed_with_esc_keeps_the_typing_again(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    def escape_untouched(dialog: QDialog) -> int:
        press_escape(dialog)
        return int(dialog.result())

    script = Script(kind, monkeypatch, type_then_escape, escape_untouched, only_look, only_look)
    add = getattr(quiet_commit, PLAIN_ADD[kind])
    for _ in range(3):
        add()
        pump(qapp)
    assert script.titles == ["", "Piano lesson", "Piano lesson"]


@pytest.mark.parametrize("account", [None, {"id": "someone-else", "username": "other"}])
@pytest.mark.parametrize("kind", KINDS)
def test_signing_out_or_switching_account_clears_the_kept_typing(
    qapp: QApplication,
    quiet_commit: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    account: dict | None,
) -> None:
    script = Script(kind, monkeypatch, type_then_escape, only_look)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    pump(qapp)
    quiet_commit.session.account_changed.emit(account)
    pump(qapp)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    assert script.titles == ["", ""]


@pytest.mark.parametrize("kind", KINDS)
def test_the_same_account_signalled_again_keeps_the_typing(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    script = Script(kind, monkeypatch, type_then_escape, only_look)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    pump(qapp)
    quiet_commit.session.account_changed.emit(quiet_commit.session.account)
    pump(qapp)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    assert script.titles == ["", "Piano lesson"]


def test_homework_drawn_on_a_day_and_kept_by_esc_is_saved_on_that_day_from_the_next_add(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A drag across free time on Wednesday opens Add homework for that day. Esc keeps the typing; saving it
    from the next plain Add must still put the homework on Wednesday, not leave it without a day."""
    saved: list = []

    def record(body: dict, **how) -> None:
        saved.append((body["title"], how.get("days")))

    monkeypatch.setattr(quiet_commit.session, "add_homework", record)
    monkeypatch.setattr(quiet_commit.session, "armed_category", "assignments")
    script = Script("homework", monkeypatch, type_then_escape, save)
    quiet_commit._create_range(2, 16 * 60, 17 * 60)
    pump(qapp)
    quiet_commit._add_homework()
    assert script.titles == ["", "Piano lesson"]
    assert saved == [("Piano lesson", [2])]


def test_the_day_a_drag_gave_stays_through_a_second_esc(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved: list = []
    monkeypatch.setattr(
        quiet_commit.session,
        "add_homework",
        lambda body, **how: saved.append((body["title"], how.get("days"))),
    )
    monkeypatch.setattr(quiet_commit.session, "armed_category", "assignments")

    def escape_again(dialog: QDialog) -> int:
        press_escape(dialog)
        return int(dialog.result())

    Script("homework", monkeypatch, type_then_escape, escape_again, save)
    quiet_commit._create_range(2, 16 * 60, 17 * 60)
    pump(qapp)
    quiet_commit._add_homework()
    pump(qapp)
    quiet_commit._add_homework()
    assert saved == [("Piano lesson", [2])]


@pytest.mark.parametrize("kind", KINDS)
def test_nothing_treats_a_kept_draft_as_an_open_sheet(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """The plain look's keys wait while a sheet is open (`activeModalWidget`); a kept draft is not one."""
    Script(kind, monkeypatch, type_then_escape)
    getattr(quiet_commit, PLAIN_ADD[kind])()
    pump(qapp)
    assert QApplication.activeModalWidget() is None
    assert not [item for item in quiet_commit.findChildren(DIALOGS[kind]) if item.isVisible()]


@pytest.mark.parametrize("key", [Qt.Key.Key_N, Qt.Key.Key_C])
def test_ctrl_n_and_the_c_key_reopen_the_kept_homework(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, key: Qt.Key
) -> None:
    """Both keys run the same plain Add as the button, so they pick the kept typing up."""
    script = Script("homework", monkeypatch, type_then_escape, only_look)
    quiet_commit._add_homework()
    pump(qapp)
    if key == Qt.Key.Key_C:
        turn_on_letter_keys()
    quiet_commit.setFocus()
    QTest.keyClick(
        quiet_commit,
        key,
        Qt.KeyboardModifier.ControlModifier if key == Qt.Key.Key_N else Qt.KeyboardModifier.NoModifier,
    )
    pump(qapp)
    assert script.titles == ["", "Piano lesson"]


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


@pytest.mark.parametrize("switched_to_pin", [False, True])
def test_a_title_kept_at_3_pm_and_a_pin_time_never_touched_gets_the_7_pm_pin_time(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, switched_to_pin: bool
) -> None:
    """At 3 PM a new sheet offers 4 PM (the day's earliest start). The student typed a title (and maybe
    chose to pin, taking the time as offered). At 7 PM the next Add shows the title and the time a new sheet
    offers at 7 PM, 7:15 PM; the 4 PM it picked at 3 PM was never theirs."""
    window = quiet_commit
    seen: list = []

    def keep(sheet: HomeworkDialog) -> int:
        sheet.title.setText("Piano practice")
        if switched_to_pin:
            sheet.when.setCurrentIndex(sheet.when.findData("fixed"))
        press_escape(sheet)
        return int(sheet.result())

    def look(sheet: HomeworkDialog) -> int:
        seen.append((sheet.title.text(), *pin_state(sheet)))
        return only_look(sheet)

    Script("homework", monkeypatch, keep, look)
    CLOCK.set(at(15))
    window._add_homework()
    pump(qapp)
    CLOCK.set(at(19))
    window._add_homework()
    when, day, minutes, _over, _from = seen[0][1:]
    assert seen[0][0] == "Piano practice"
    assert when == ("fixed" if switched_to_pin else "plan")
    assert minutes == 19 * 60 + 15
    assert [when, day, minutes] == pin_state_for_new_sheet_at(window, at(19), pinned=switched_to_pin)[:3]


def pin_state_for_new_sheet_at(window: NativeWindow, moment: datetime, *, pinned: bool) -> list:
    CLOCK.set(moment)
    sheet = HomeworkDialog(window, today=window._today(), category="assignments")
    try:
        if pinned:
            sheet.when.setCurrentIndex(sheet.when.findData("fixed"))
        return pin_state(sheet)
    finally:
        free(sheet)


def test_a_pin_chosen_at_3_pm_comes_back_at_7_pm_and_says_it_is_over_as_a_new_sheet_would(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = quiet_commit
    today = at(15).weekday()
    seen: list = []

    def pin_4_pm_today(sheet: HomeworkDialog) -> None:
        sheet.when.setCurrentIndex(sheet.when.findData("fixed"))
        sheet.when_day.set_days([today])
        sheet._pick_day()
        sheet.when_time.setTime(QTime(16, 0))

    def keep(sheet: HomeworkDialog) -> int:
        sheet.title.setText("Piano practice")
        pin_4_pm_today(sheet)
        press_escape(sheet)
        return int(sheet.result())

    def look(sheet: HomeworkDialog) -> int:
        seen.append((sheet.title.text(), pin_state(sheet)))
        return only_look(sheet)

    Script("homework", monkeypatch, keep, look)
    CLOCK.set(at(15))
    window._add_homework()
    pump(qapp)
    CLOCK.set(at(19))
    window._add_homework()
    # What a new sheet says at 7 PM when 4 PM today is picked on it.
    CLOCK.set(at(19))
    reference = HomeworkDialog(window, today=window._today(), category="assignments")
    try:
        pin_4_pm_today(reference)
        expected = pin_state(reference)
    finally:
        free(reference)
    title, state = seen[0]
    assert title == "Piano practice"
    assert state == expected
    assert state[0] == "fixed" and state[2] == 16 * 60, "the 4 PM the student chose"
    assert state[3], "4 PM today is over at 7 PM, and the sheet says so"
    assert "7:00 PM" in state[4] or "19:00" in state[4], state[4]


@pytest.mark.parametrize("kind", KINDS)
def test_typing_kept_before_midnight_comes_back_on_the_new_days_sheet(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    window = quiet_commit
    seen: list = []

    def look(sheet: QDialog) -> int:
        seen.append(sheet)
        return only_look(sheet)

    Script(kind, monkeypatch, type_then_escape, look)
    CLOCK.set(datetime(2026, 11, 5, 23, 50))
    getattr(window, PLAIN_ADD[kind])()
    pump(qapp)
    CLOCK.set(datetime(2026, 11, 6, 0, 10))
    getattr(window, PLAIN_ADD[kind])()
    sheet = seen[0]
    assert sheet.title.text() == "Piano lesson"
    if kind == "homework":
        # Tomorrow of the new day, not of the day it was typed on; and the pin starts from the new day.
        assert sheet.due.value() == "2026-11-07"
        assert sheet._day == 4, "Friday 6 November"
        assert sheet.when_time.minutes() == 16 * 60
    else:
        assert [index for index, check in enumerate(sheet.days) if check.isChecked()] == [4]
        assert sheet.start.minutes() == 0 * 60 + 15, "the next quarter hour of the new day"


@pytest.mark.parametrize("kind", KINDS)
def test_typing_kept_before_a_12_or_24_hour_switch_comes_back_with_times_written_the_new_way(
    qapp: QApplication, quiet_commit: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    window = quiet_commit
    seen: list = []

    def look(sheet: QDialog) -> int:
        field = sheet.when_time if kind == "homework" else sheet.start
        seen.append((sheet.title.text(), field.text()))
        return only_look(sheet)

    Script(kind, monkeypatch, type_then_escape, look)
    CLOCK.set(at(15))
    set_clock_24h(True)
    getattr(window, PLAIN_ADD[kind])()
    pump(qapp)
    set_clock_24h(False)
    getattr(window, PLAIN_ADD[kind])()
    title, text = seen[0]
    assert title == "Piano lesson"
    assert text.upper().endswith(("AM", "PM")), text
