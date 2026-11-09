"""Material's Add homework sheet asks "Discard what you typed?" only when the student leaves it: Esc, Cancel
or a click on the scrim. Clicks inside the sheet never ask. Keep editing takes one click and puts the
keyboard back where it was."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump
from desktop.tests.sheets.support_material_sheets import find, open_typed_homework
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

DISCARD = "Discard what you typed?"


def click_item(quick, item, qapp: QApplication) -> None:
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
    pump(qapp, 40)


def asked_to_discard(sheets) -> bool:
    return sheets.ask.get("id") == "discard"


def test_clicking_next_with_text_typed_does_not_ask_to_discard(qapp, window: NativeWindow) -> None:
    root, quick, sheets = open_typed_homework(qapp, window)
    click_item(quick, find(root, "homeworkNext"), qapp)
    wait_until(qapp, lambda: sheets.form["step"] == 1)
    assert sheets.ask == {}
    assert sheets.kind == "homework"


def test_clicking_a_chip_with_text_typed_does_not_ask_to_discard(qapp, window: NativeWindow) -> None:
    root, quick, sheets = open_typed_homework(qapp, window)
    sheets.next()
    wait_until(qapp, lambda: sheets.form["step"] == 1)
    click_item(quick, find(root, "homeworkWhen"), qapp)
    assert sheets.ask == {}
    assert sheets.kind == "homework"


def test_clicking_empty_space_inside_the_sheet_does_not_ask_to_discard(qapp, window: NativeWindow) -> None:
    root, quick, sheets = open_typed_homework(qapp, window)
    card = find(root, "sheetCard")
    pos = card.mapToScene(QPointF(12, 12)).toPoint()
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    pump(qapp, 40)
    assert sheets.ask == {}
    assert sheets.kind == "homework"


def test_clicking_the_scrim_with_text_typed_asks_to_discard(qapp, window: NativeWindow) -> None:
    _root, quick, sheets = open_typed_homework(qapp, window)
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(10, 10))
    wait_until(qapp, lambda: asked_to_discard(sheets))
    assert sheets.ask.get("title") == DISCARD


def test_a_click_on_the_first_pixel_past_the_sheets_edge_asks_to_discard(qapp, window: NativeWindow) -> None:
    root, quick, sheets = open_typed_homework(qapp, window)
    card = find(root, "sheetCard")
    # A Qt Quick item's hit area ends before x == width, so that pixel belongs to the scrim.
    edge = card.mapToScene(QPointF(card.width(), card.height() / 2)).toPoint()
    assert edge.x() < quick.width(), "the wide sheet leaves scrim to its right"
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, edge)
    wait_until(qapp, lambda: asked_to_discard(sheets))


def test_escape_with_text_typed_asks_to_discard(qapp, window: NativeWindow) -> None:
    _root, quick, sheets = open_typed_homework(qapp, window)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    wait_until(qapp, lambda: asked_to_discard(sheets))
    assert sheets.ask.get("title") == DISCARD


def test_the_prompt_says_your_changes_will_be_lost(qapp, window: NativeWindow) -> None:
    _root, quick, sheets = open_typed_homework(qapp, window)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    wait_until(qapp, lambda: asked_to_discard(sheets))
    assert sheets.ask["title"] == DISCARD
    assert sheets.ask["body"] == "Your changes will be lost."


def test_keep_editing_closes_the_prompt_with_one_click_and_returns_focus_to_the_title_field(
    qapp, window: NativeWindow
) -> None:
    root, quick, sheets = open_typed_homework(qapp, window)
    field_input = find(find(root, "homeworkTitle"), "fieldInput")
    field_input.forceActiveFocus()
    pump(qapp, 20)
    assert field_input.property("activeFocus") is True

    QTest.keyClick(quick, Qt.Key.Key_Escape)
    wait_until(qapp, lambda: asked_to_discard(sheets))

    click_item(quick, find(find(root, "sheetPrompt"), "prompt_keep"), qapp)

    assert sheets.ask == {}
    assert sheets.kind == "homework"
    assert field_input.property("activeFocus") is True
    assert sheets.form["title"] == "History essay"


def test_enter_after_keep_editing_does_not_change_the_step(qapp, window: NativeWindow) -> None:
    root, quick, sheets = open_typed_homework(qapp, window)
    sheets.next()
    wait_until(qapp, lambda: sheets.form["step"] == 1)
    due_field = find(root, "homeworkDue")
    due_field.forceActiveFocus()
    pump(qapp, 20)
    assert due_field.property("activeFocus") is True

    QTest.keyClick(quick, Qt.Key.Key_Escape)
    wait_until(qapp, lambda: asked_to_discard(sheets))
    click_item(quick, find(find(root, "sheetPrompt"), "prompt_keep"), qapp)
    assert sheets.ask == {}
    assert due_field.property("activeFocus") is True, "Keep editing returns focus to the Due picker"

    # Enter must not jump back to step 0 ("1. What"), nor move on.
    QTest.keyClick(quick, Qt.Key.Key_Return)
    pump(qapp, 40)
    assert sheets.form["step"] == 1


def test_a_click_on_the_prompt_backdrop_does_not_reach_the_sheet_underneath(
    qapp, window: NativeWindow
) -> None:
    root, quick, sheets = open_typed_homework(qapp, window)
    assert sheets.form["step"] == 0

    QTest.keyClick(quick, Qt.Key.Key_Escape)
    wait_until(qapp, lambda: asked_to_discard(sheets))

    next_btn = find(root, "homeworkNext")
    pos = next_btn.mapToScene(QPointF(next_btn.width() / 2, next_btn.height() / 2)).toPoint()
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    pump(qapp, 40)

    assert sheets.form["step"] == 0
