"""Leaving the fixed-time sheet with typed words: Cancel and the close button ask before throwing them away,
an untouched sheet just closes, and Esc on a new Add sheet closes at once and keeps the typing for the next
plain Add (Jonathan, 2026-11-11). The window-level tests below run the window's own Add paths with `exec`
replaced by a script, for Add homework and Add fixed time alike. Expected values come from the requirement."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from desktop.native.widgets import BlockDialog, ConfirmSheet, HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump
from desktop.tests.sheets.support_settings_keys import shown
from desktop.tests.window_support import free, qapp  # noqa: F401


def press_escape(dialog: QDialog) -> None:
    dialog.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))


def press_cancel(dialog: QDialog) -> None:
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel).click()


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


def test_escape_on_a_typed_new_fixed_time_closes_at_once_and_marks_it_kept(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = shown(qapp, BlockDialog(window))
    try:
        dialog.activateWindow()
        pump(qapp)
        dialog.title.setText("Piano lesson")
        monkeypatch.setattr(ConfirmSheet, "exec", lambda _sheet: pytest.fail("Esc asked a question"))
        press_escape(dialog)
        assert not dialog.isVisible()
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert dialog.kept_on_escape
        assert dialog.title.text() == "Piano lesson"
    finally:
        free(dialog)


def test_a_kept_fixed_time_sheet_shown_again_has_its_words_unselected_with_the_cursor_after_them(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = shown(qapp, BlockDialog(window))
    try:
        dialog.activateWindow()
        pump(qapp)
        dialog.title.setText("Piano lesson")
        press_escape(dialog)
        dialog.reopen()
        dialog.show()
        pump(qapp)
        assert dialog.title.text() == "Piano lesson"
        assert dialog.title.selectedText() == "", "the next key would have replaced the words"
        assert dialog.title.cursorPosition() == len("Piano lesson")
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
        asked: list[str] = []

        def answer(sheet: ConfirmSheet) -> int:
            asked.append(sheet.windowTitle())
            sheet.buttons["stay"].click()
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(ConfirmSheet, "exec", answer)
        press_escape(dialog)
        assert asked == ["Discard what you typed?"]
        assert dialog.isVisible()
        assert not dialog.kept_on_escape
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
    assert script.sheets[1].title.text() == "Piano lesson"


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
