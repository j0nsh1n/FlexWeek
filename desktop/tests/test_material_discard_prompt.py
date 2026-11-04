"""Tests for Material Homework sheet's discard prompt and focus behavior.

Verifies:
- Only Esc, Cancel, or scrim click outside sheet asks to discard.
- Clicks inside the sheet do not ask to discard.
- The prompt is modal and Keep editing works with one click.
- Focus returns to the exact control that had it before.
- Prompt body text is 'Your changes will be lost.'
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

pytest_plugins = ["desktop.tests.test_material_sheets"]

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.test_material_sheets import (  # noqa: E402
    _find,
    _type_homework,
)
from desktop.tests.test_material_window import _pump, _show_material  # noqa: E402


def _click(quick, item, qapp: QApplication | None = None) -> None:
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        centre,
    )
    if qapp is not None:
        _pump(qapp, 40)


def test_clicking_next_with_text_typed_does_not_ask_to_discard(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    _pump(qapp, 60)
    next_btn = _find(root, "homeworkNext")
    _click(quick, next_btn, qapp)
    assert sheets.ask == {}
    assert sheets.kind == "homework"
    assert sheets.form["step"] == 1


def test_clicking_a_chip_with_text_typed_does_not_ask_to_discard(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    _pump(qapp, 60)
    sheets.next()
    _pump(qapp, 40)
    assert sheets.form["step"] == 1
    when_btn = _find(root, "homeworkWhen")
    _click(quick, when_btn, qapp)
    assert sheets.ask == {}
    assert sheets.kind == "homework"


def test_clicking_empty_space_inside_the_sheet_does_not_ask_to_discard(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    _pump(qapp, 60)
    card = _find(root, "sheetCard")
    pos = card.mapToScene(QPointF(12, 12)).toPoint()
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    _pump(qapp, 40)
    assert sheets.ask == {}
    assert sheets.kind == "homework"


def test_clicking_the_scrim_with_text_typed_asks_to_discard(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    _pump(qapp, 60)
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(10, 10))
    _pump(qapp, 40)
    assert sheets.ask.get("id") == "discard"
    assert sheets.ask.get("title") == "Discard what you typed?"


def test_a_click_on_the_first_pixel_past_the_sheets_edge_asks_to_discard(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    _pump(qapp, 60)
    card = _find(root, "sheetCard")
    # A Qt Quick item's hit area ends before x == width, so that pixel belongs to the scrim.
    edge = card.mapToScene(QPointF(card.width(), card.height() / 2)).toPoint()
    assert edge.x() < quick.width(), "the wide sheet leaves scrim to its right"
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, edge)
    _pump(qapp, 40)
    assert sheets.ask.get("id") == "discard"


def test_escape_with_text_typed_asks_to_discard(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    _pump(qapp, 60)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    _pump(qapp, 40)
    assert sheets.ask.get("id") == "discard"
    assert sheets.ask.get("title") == "Discard what you typed?"


def test_keep_editing_closes_the_prompt_with_one_click_and_returns_focus_to_the_title_field(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    _pump(qapp, 60)
    title_field = _find(root, "homeworkTitle")
    field_input = _find(title_field, "fieldInput")
    field_input.forceActiveFocus()
    _pump(qapp, 20)
    assert field_input.property("activeFocus") is True

    QTest.keyClick(quick, Qt.Key.Key_Escape)
    _pump(qapp, 40)
    assert sheets.ask.get("id") == "discard"

    sheet_prompt = _find(root, "sheetPrompt")
    keep_btn = _find(sheet_prompt, "prompt_keep")
    _click(quick, keep_btn, qapp)

    assert sheets.ask == {}
    assert sheets.kind == "homework"
    assert field_input.property("activeFocus") is True
    assert sheets.form["title"] == "History essay"


def test_enter_after_keep_editing_does_not_change_the_step(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    _pump(qapp, 60)
    sheets.next()
    _pump(qapp, 40)
    assert sheets.form["step"] == 1
    step_before = sheets.form["step"]

    due_field = _find(root, "homeworkDue")
    due_field.forceActiveFocus()
    _pump(qapp, 20)
    assert due_field.property("activeFocus") is True

    QTest.keyClick(quick, Qt.Key.Key_Escape)
    _pump(qapp, 40)
    assert sheets.ask.get("id") == "discard"

    sheet_prompt = _find(root, "sheetPrompt")
    keep_btn = _find(sheet_prompt, "prompt_keep")
    _click(quick, keep_btn, qapp)
    assert sheets.ask == {}
    assert due_field.property("activeFocus") is True, "Keep editing returns focus to the Due picker"

    # Enter must not jump back to step 0 / crumb 0 ("1. What"), nor move on.
    QTest.keyClick(quick, Qt.Key.Key_Return)
    _pump(qapp, 40)
    assert sheets.form["step"] == step_before


def test_a_click_on_the_prompt_backdrop_does_not_reach_the_sheet_underneath(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    _pump(qapp, 60)
    assert sheets.form["step"] == 0

    QTest.keyClick(quick, Qt.Key.Key_Escape)
    _pump(qapp, 40)
    assert sheets.ask.get("id") == "discard"

    next_btn = _find(root, "homeworkNext")
    pos = next_btn.mapToScene(QPointF(next_btn.width() / 2, next_btn.height() / 2)).toPoint()

    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    _pump(qapp, 40)

    assert sheets.form["step"] == 0


def test_the_prompt_says_your_changes_will_be_lost(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    _show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    _pump(qapp, 60)

    QTest.keyClick(quick, Qt.Key.Key_Escape)
    _pump(qapp, 40)
    assert sheets.ask["title"] == "Discard what you typed?"
    assert sheets.ask["body"] == "Your changes will be lost."
