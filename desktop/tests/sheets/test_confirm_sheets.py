"""Questions the window asks on an answer sheet: the safe answer is the default, Esc answers nothing,
Return presses the answer that has the keyboard, and the window acts only on a yes. How wide the
answers are and whether they stand side by side is a look: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

from desktop.native import window as window_module
from desktop.native.settings import AccountDialog, RestoreDialog
from desktop.native.widgets import ConfirmSheet, confirm, confirm_sheet
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_dialogs import shown, when_open
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free

THREE = (
    ("stay", "Cancel", "outlined"),
    ("week", "This week only", ""),
    ("every", "This week and later", "danger"),
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-confirm-sheets-test"])


def test_a_confirmation_is_a_sheet_whose_default_is_cancel_and_whose_answer_is_red_only_when_it_destroys(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    for danger in (True, False):
        sheet = confirm_sheet(window, "Delete event", "Delete Soccer?", "Delete", danger=danger)
        shown(qapp, sheet)
        assert sheet.sheet
        assert sheet.buttons["stay"].isDefault() and not sheet.buttons["yes"].isDefault()
        assert bool(sheet.buttons["yes"].property("danger")) is danger
        assert not sheet.buttons["stay"].property("danger")
        QTest.keyClick(sheet, Qt.Key.Key_Escape)
        assert sheet.answer is None and sheet.result() == QDialog.DialogCode.Rejected
        free(sheet)


def test_return_on_sign_out_presses_the_focused_button(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    """Return activates the focused answer, not always Cancel."""
    sheet = ConfirmSheet(
        window,
        "Sign out",
        "Your week is saved on this computer, under this account. Sign in again to see it.",
        (("stay", "Cancel", "outlined"), ("yes", "Sign out", "")),
        default="stay",
    )
    shown(qapp, sheet)
    sheet.buttons["yes"].setFocus()
    QTest.keyClick(sheet, Qt.Key.Key_Return)
    assert sheet.answer == "yes"
    free(sheet)
    again = ConfirmSheet(
        window,
        "Sign out",
        "Sure?",
        (("stay", "Cancel", "outlined"), ("yes", "Sign out", "")),
        default="stay",
    )
    shown(qapp, again)
    again.question.setFocus()
    QTest.keyClick(again, Qt.Key.Key_Return)
    assert again.answer == "stay"
    free(again)


def test_confirm_answers_true_only_for_the_yes_button(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    check = when_open(lambda sheet: sheet.buttons["yes"].click())
    assert confirm(window, "Sign out", "Sure?", "Sign out", danger=False) is True
    check()
    check = when_open(lambda sheet: sheet.buttons["stay"].click())
    assert confirm(window, "Sign out", "Sure?", "Sign out", danger=False) is False
    check()


def test_stacking_keeps_the_default_answer_and_the_tab_order(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    """In a narrow window the answers stand one above the other; the keyboard still starts on the
    default and Tab goes down them in order."""
    window.resize(480, 800)
    qapp.processEvents()
    sheet = ConfirmSheet(window, "Question?", "Which one?", THREE, default="stay")
    shown(qapp, sheet)
    assert sheet.buttons["stay"].isDefault()
    assert QApplication.focusWidget() is sheet.buttons["stay"], "the keyboard starts on the default"
    order = []
    for _ in range(3):
        order.append(QApplication.focusWidget().property("answer"))
        QTest.keyClick(sheet, Qt.Key.Key_Tab)
    assert order == ["stay", "week", "every"]
    free(sheet)


def test_the_sign_out_sheet_says_where_the_week_lives_and_does_not_draw_sign_out_red(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[str, str, str, bool]] = []

    def confirm_it(_parent: object, title: str, question: str, yes: str, *, danger: bool = True) -> bool:
        asked.append((title, question, yes, danger))
        return False

    monkeypatch.setattr(window_module, "confirm", confirm_it)
    wait_until(qapp, lambda: window.session.storage_info is not None)
    window.findChild(QPushButton, "signOut").click()
    assert asked == [
        (
            "Sign out",
            "Your week is saved on this computer, under this account. Sign in again to see it.",
            "Sign out",
            False,
        )
    ]
    window.session.storage_info = {"mode": "hosted"}
    window.findChild(QPushButton, "signOut").click()
    assert asked[-1][1] == (
        "Your week is saved on your FlexWeek server, under this account. Sign in again to see it."
    )


def test_the_app_says_sign_out_and_never_log_out(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    """The top bar's button, and the Manage account note about the codes."""
    from PySide6.QtWidgets import QLabel

    assert window.findChild(QPushButton, "signOut").text() == "Sign out"
    account = AccountDialog(window, 0, {"username": "student"})
    assert account.findChild(QLabel, "recoveryCount").text() == (
        "No unused recovery codes remain. Replace them before signing out."
    )
    free(account)


def test_replace_timer_asks_in_a_sheet_not_a_message_box(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
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
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
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
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
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
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
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
