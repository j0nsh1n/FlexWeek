"""Questions the window asks on an answer sheet: the safe answer is the default, Esc answers nothing,
Return presses the answer that has the keyboard, and the window acts only on a yes. How wide the
answers are and whether they stand side by side is a look: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from desktop.native.widgets import ConfirmSheet, confirm, confirm_sheet
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_dialogs import shown, when_open
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






