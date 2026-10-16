"""Window questions use the same answer sheet on every desktop surface."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from desktop.native.settings import RestoreDialog
from desktop.native.widgets import ConfirmSheet
from desktop.native.window import NativeWindow
from desktop.tests.window_support import qapp, server, signed_out, window  # noqa: F401


def test_replace_timer_asks_in_a_sheet_not_a_message_box(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def message_box(*_args: object) -> QMessageBox.StandardButton:
        calls.append("message box")
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", message_box)
    seen: list[tuple[str, str, dict[str, str], str | None]] = []

    def show(sheet: ConfirmSheet) -> int:
        title = sheet.findChild(type(sheet.question), "sheetTitle")
        assert title is not None, "the confirmation sheet has a title"
        seen.append(
            (
                title.text(),
                sheet.question.text(),
                {key: button.text() for key, button in sheet.buttons.items()},
                next((key for key, button in sheet.buttons.items() if button.isDefault()), None),
            )
        )
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ConfirmSheet, "exec", show)
    window._confirm_replace_focus("History essay", "Chem lab report")
    assert not calls, "Replace timer does not open a system message box"
    assert seen == [
        (
            "Replace timer",
            "Stop the timer for History essay and start Chem lab report instead?",
            {"keep": "Keep current timer", "replace": "Replace timer"},
            "keep",
        )
    ], "Replace timer uses a sheet with the safe answer as default"


def test_restore_asks_in_a_sheet_not_a_message_box(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def message_box(*_args: object) -> QMessageBox.StandardButton:
        calls.append("message box")
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", message_box)
    window.session.restore_points = [{"id": "restore-1", "label": "Before exams"}]

    def choose_restore(dialog: RestoreDialog) -> int:
        dialog.action = "restore"
        dialog.selected_id = "restore-1"
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(RestoreDialog, "exec", choose_restore)
    seen: list[tuple[str, str, dict[str, str], str | None]] = []

    def show(sheet: ConfirmSheet) -> int:
        title = sheet.findChild(type(sheet.question), "sheetTitle")
        assert title is not None, "the confirmation sheet has a title"
        seen.append(
            (
                title.text(),
                sheet.question.text(),
                {key: button.text() for key, button in sheet.buttons.items()},
                next((key for key, button in sheet.buttons.items() if button.isDefault()), None),
            )
        )
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ConfirmSheet, "exec", show)
    window._open_restore()
    assert not calls, "Restore does not open a system message box"
    assert seen == [
        (
            "Restore",
            "Restore this snapshot? FlexWeek saves a restore point first.",
            {"not": "Not now", "restore": "Restore"},
            "not",
        )
    ], "Restore uses a sheet with the safe answer as default"


@pytest.mark.parametrize(("answer", "replaced"), [("replace", True), ("keep", False), (None, False)])
def test_replace_timer_replaces_only_when_the_student_says_so(
    qapp: QApplication,
    window: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
    answer: str | None,
    replaced: bool,
) -> None:
    asked: list[bool] = []
    monkeypatch.setattr(window.session, "confirm_replace_focus", lambda: asked.append(True) or False)

    def show(sheet: ConfirmSheet) -> int:
        sheet.answer = answer
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ConfirmSheet, "exec", show)
    window._confirm_replace_focus("History essay", "Chem lab report")
    assert bool(asked) is replaced, f"answer {answer!r} replaces the timer: {replaced}"


@pytest.mark.parametrize(("answer", "restored"), [("restore", True), ("not", False), (None, False)])
def test_restore_applies_only_when_the_student_says_so(
    qapp: QApplication,
    window: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
    answer: str | None,
    restored: bool,
) -> None:
    applied: list[str] = []
    monkeypatch.setattr(window.session, "apply_restore_point", applied.append)
    window.session.restore_points = [{"id": "restore-1", "label": "Before exams"}]

    def choose_restore(dialog: RestoreDialog) -> int:
        dialog.action = "restore"
        dialog.selected_id = "restore-1"
        return QDialog.DialogCode.Accepted

    def show(sheet: ConfirmSheet) -> int:
        sheet.answer = answer
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(RestoreDialog, "exec", choose_restore)
    monkeypatch.setattr(ConfirmSheet, "exec", show)
    window._open_restore()
    assert applied == (["restore-1"] if restored else []), f"answer {answer!r} restores: {restored}"
