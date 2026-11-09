"""Add homework and the block editor: every field has an accessible name that is not just its value (a combo
box has a label as its buddy), and Tab leaves the Notes box instead of typing a tab into it."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QWidget

from desktop.native.widgets import BlockDialog, HomeworkDialog
from desktop.tests.sheets.support_keys import fields_of, press, unnamed, up
from desktop.tests.window_support import free, qapp  # noqa: F401


@pytest.fixture()
def made(qapp):
    owned: list[QWidget] = []
    yield owned
    for widget in owned:
        widget.hide()
        free(widget)


def open_add_homework(qapp, made) -> HomeworkDialog:
    host = QWidget()
    made.append(host)
    dialog = HomeworkDialog(host, today="2026-10-05", category="assignments")
    made.insert(0, dialog)
    up(qapp, dialog)
    dialog.more_details.setChecked(True)
    qapp.processEvents()
    return dialog


def open_block_editor(qapp, made) -> BlockDialog:
    host = QWidget()
    made.append(host)
    dialog = BlockDialog(host, day=2, start="16:00", duration_min=60)
    made.insert(0, dialog)
    up(qapp, dialog)
    qapp.processEvents()
    return dialog


SHEETS = {"add-homework": open_add_homework, "block-editor": open_block_editor}


@pytest.mark.parametrize("sheet", list(SHEETS))
def test_every_field_has_a_name_that_is_not_its_value_and_combos_have_a_buddy(qapp, made, sheet) -> None:
    root = SHEETS[sheet](qapp, made)
    assert fields_of(root), "found no fields"
    assert unnamed(root) == []


def test_tab_leaves_notes_and_shift_tab_comes_back(qapp, made) -> None:
    dialog = open_add_homework(qapp, made)
    notes = dialog.findChild(QPlainTextEdit, "homeworkNotes")
    notes.setFocus(Qt.FocusReason.OtherFocusReason)
    qapp.processEvents()
    press(notes, Qt.Key.Key_Tab)
    assert notes.toPlainText() == "" and QApplication.focusWidget() is not notes
    press(notes, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    assert QApplication.focusWidget() is notes
