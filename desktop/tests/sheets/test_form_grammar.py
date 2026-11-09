"""The form grammar every sheet and account card follows: a problem is one line under its field, a row
of answers stacks when it cannot hold them side by side, and an account card shows one problem at a
time and sends the keyboard to that field.

How wide the problem line is, where captions sit, that no button clips its words and that an account
card does not move when a problem appears are pictures: desktop/tests/pictures/screens_sheets_h8.py
(sheets.problem-lines, sheets.captions-*, sheets.account-card-*).
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop.native.fields import ClockField, ProblemLine
from desktop.native.widgets import SHEET_PAD, AnswerRow, AvailabilityDialog, BlockDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_clock_typing import show_and_focus, type_over
from desktop.tests.sheets.support_soccer import soccer
from desktop.tests.window_support import free, host, qapp  # noqa: F401


def _show_account_card(app: QApplication, opened: NativeWindow, mode: str) -> None:
    """The sign-in page on the card for `mode` ("sign in", "create" or "reset")."""
    opened._show_page("authPage")
    opened._entry_mode = mode
    opened._sync_auth_mode()
    for _ in range(4):
        app.processEvents()


def test_a_clock_field_shows_a_problem_line_for_words_that_are_not_a_time(
    qapp: QApplication,  # noqa: F811
    host: QWidget,  # noqa: F811
) -> None:
    box = QVBoxLayout(host)
    field = ClockField(QTime(9, 0), host)
    field.setObjectName("loneTime")
    field.setFixedWidth(180)
    box.addWidget(field)
    box.addWidget(QLineEdit(host))
    host.resize(400, 200)
    show_and_focus(qapp, host)
    assert host.findChild(ProblemLine) is None or not host.findChild(ProblemLine).isVisibleTo(host)
    type_over(qapp, field, "nope")
    line = host.findChild(ProblemLine)
    assert line is not None and line.isVisibleTo(host)


def test_an_end_before_the_start_shows_a_problem_line_under_the_time_row(
    qapp: QApplication,  # noqa: F811
    host: QWidget,  # noqa: F811
) -> None:
    block = BlockDialog(host, soccer(), occurrence_day=3)
    show_and_focus(qapp, block)
    type_over(qapp, block.end, "08:00")
    assert [line for line in block.findChildren(ProblemLine) if line.isVisibleTo(block)]


def test_the_availability_picker_captions_the_name_field_as_optional(
    qapp: QApplication,  # noqa: F811
    host: QWidget,  # noqa: F811
) -> None:
    dialog = AvailabilityDialog(host, {})
    show_and_focus(qapp, dialog)
    dialog._open_picker(kind="protected", day=0)
    qapp.processEvents()
    assert dialog.picker_title.isVisibleTo(dialog)
    labels = dialog.findChildren(QLabel, "fieldLabel")
    captions = [label.text() for label in labels if label.isVisibleTo(dialog)]
    assert "Name (optional)" in captions


def test_a_row_of_answers_stacks_when_it_is_too_narrow_and_stands_in_a_row_when_it_is_wide(
    qapp: QApplication,  # noqa: F811
) -> None:
    """The four Delete School answers stack when the sheet cannot hold them on one line."""
    row = AnswerRow()
    buttons = []
    for words in ("Cancel", "This day only", "This week only", "This week and later"):
        button = QPushButton(words)
        buttons.append(button)
        row.add(button, stretch_before=len(buttons) == 1)
    narrow = 220
    row.resize(narrow, 40)
    row.fit(narrow)
    row.show()
    qapp.processEvents()
    assert row.row.direction() == QBoxLayout.Direction.TopToBottom
    items = [row.row.itemAt(at) for at in range(row.row.count())]
    in_order = [item.widget() for item in items if item.widget() is not None]
    assert in_order == buttons, "stacked, they keep the order they were added in"
    for button in buttons:
        assert button.minimumWidth() >= button.fontMetrics().horizontalAdvance(button.text())
    wide = row.side_by_side() + SHEET_PAD
    row.fit(wide)
    row.resize(wide, 40)
    qapp.processEvents()
    assert row.row.direction() == QBoxLayout.Direction.LeftToRight
    free(row)


def test_an_account_card_shows_one_problem_and_sends_the_keyboard_to_that_field(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """Only the first problem shows, and the keyboard moves to its field."""
    _show_account_card(qapp, window, "create")
    window.username.setText("ab")
    window.password.setText("short")
    window.create_button.click()
    for _ in range(4):
        qapp.processEvents()
    lines = (
        window.username_problem,
        window.password_problem,
        window.recovery_code_problem,
        window.recovery_password_problem,
    )
    assert [line for line in lines if line.isVisibleTo(window)] == [window.username_problem]
    assert window.focusWidget() is window.username
    window.username.setText("ada_1")
    window.create_button.click()
    for _ in range(4):
        qapp.processEvents()
    assert [line for line in lines if line.isVisibleTo(window)] == [window.password_problem]
    assert window.focusWidget() is window.password
