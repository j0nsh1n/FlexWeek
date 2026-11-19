# ruff: noqa: F811
"""Material's week keys, as the plain look has them: Ctrl+N new homework, F1 Help, and Ctrl+C, Ctrl+D and
Delete on the block that has the keyboard focus. None of them works while typing, and the block keys do
nothing when no block has the focus. Real key events through the Material window.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.settings_copy import help_keys  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import material_window, qapp  # noqa: E402, F401
from desktop.tests.material_support import named, pump, show_material  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402

CTRL = Qt.KeyboardModifier.ControlModifier


def _school(root: QObject) -> QObject:
    return next(item for item in named(root, "weekBlock") if item.property("blockId") == "school")


def _focused_school(qapp: QApplication, window: NativeWindow) -> QObject:
    root = show_material(qapp, window)
    block = _school(root)
    block.forceActiveFocus()
    pump(qapp)
    assert block.property("activeFocus") is True
    return block


def test_ctrl_n_opens_new_homework(qapp: QApplication, material_window: NativeWindow) -> None:
    root = show_material(qapp, material_window)
    quick = material_window._material_page._quick
    sheets = material_window._material_page.bridge.sheets
    root.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_N, CTRL)
    pump(qapp)
    assert sheets.kind == "homework"


def test_ctrl_n_does_nothing_while_typing_or_in_settings(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    root = show_material(qapp, material_window)
    quick = material_window._material_page._quick
    bridge = material_window._material_page.bridge
    sheets = bridge.sheets
    # A fixed time's sheet is open and its field has the keys: a second Ctrl+N must not replace it.
    sheets.openBlockAt(0, 9 * 60, 10 * 60)
    pump(qapp)
    assert sheets.kind == "block"
    QTest.keyClick(quick, Qt.Key.Key_N, CTRL)
    pump(qapp)
    assert sheets.kind == "block"
    sheets.forceClose()
    pump(qapp)
    bridge.showPage("settings")
    root.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_N, CTRL)
    pump(qapp)
    assert sheets.kind == ""


def test_f1_opens_help(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = show_material(qapp, material_window)
    heard: list[str] = []
    monkeypatch.setattr(material_window, "_open_help", lambda: heard.append("help"))
    root.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(material_window._material_page._quick, Qt.Key.Key_F1)
    pump(qapp)
    assert heard == ["help"]


def test_f1_does_nothing_while_typing(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    show_material(qapp, material_window)
    heard: list[str] = []
    monkeypatch.setattr(material_window, "_open_help", lambda: heard.append("help"))
    sheets = material_window._material_page.bridge.sheets
    sheets.openHomework()
    pump(qapp)
    QTest.keyClick(material_window._material_page._quick, Qt.Key.Key_F1)
    pump(qapp)
    assert heard == []


def test_ctrl_c_copies_the_focused_block(qapp: QApplication, material_window: NativeWindow) -> None:
    _focused_school(qapp, material_window)
    session = material_window.session
    assert session.clipboard is None
    QTest.keyClick(material_window._material_page._quick, Qt.Key.Key_C, CTRL)
    pump(qapp)
    assert session.clipboard is not None
    assert session.clipboard["kind"] == "block"
    assert session.clipboard["label"].startswith("School")


def test_ctrl_d_previews_a_copy_of_the_focused_block(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _focused_school(qapp, material_window)
    seen: list[dict] = []
    monkeypatch.setattr(
        material_window, "_show_preview", lambda title, words, rows, **kw: seen.append({"rows": rows, **kw})
    )
    QTest.keyClick(material_window._material_page._quick, Qt.Key.Key_D, CTRL)
    pump(qapp)
    assert len(seen) == 1
    assert seen[0]["label"] == "duplicating School"
    assert seen[0]["rows"]
    # The clipboard is left as it was: a duplicate is not a copy.
    assert material_window.session.clipboard is None


def test_delete_asks_first_then_deletes_with_undo(qapp: QApplication, material_window: NativeWindow) -> None:
    block = _focused_school(qapp, material_window)
    session = material_window.session
    sheets = material_window._material_page.bridge.sheets
    before = [dict(item) for item in session.blocks if item["id"] == "school"]
    QTest.keyClick(material_window._material_page._quick, Qt.Key.Key_Delete)
    pump(qapp)
    assert sheets.ask["id"] == "delete-block"
    assert any(item["id"] == "school" for item in session.blocks)
    sheets.answer("stay")
    pump(qapp)
    assert any(item["id"] == "school" for item in session.blocks)
    assert block.property("activeFocus") is True, "Cancel gives the keyboard back to the block"
    QTest.keyClick(material_window._material_page._quick, Qt.Key.Key_Delete)
    pump(qapp)
    sheets.answer("day")
    # School comes from Setup, so the question is the one its menu asks: Monday's copy of it, this day only.
    assert [item for item in session.blocks if item["id"] == "school"] != before
    assert sheets.notice == "Deleted School on Monday from this week."
    assert sheets.noticeUndo is True
    wait_until(qapp, lambda: not session.busy and not session.dirty, what="the delete to be saved")
    sheets.undoNotice()
    assert [item for item in session.blocks if item["id"] == "school"] == before


def test_delete_is_held_while_a_save_is_running(qapp: QApplication, material_window: NativeWindow) -> None:
    _focused_school(qapp, material_window)
    session = material_window.session
    sheets = material_window._material_page.bridge.sheets
    QTest.keyClick(material_window._material_page._quick, Qt.Key.Key_Delete)
    pump(qapp)
    session.busy = True
    try:
        sheets.answer("delete")
        assert any(item["id"] == "school" for item in session.blocks)
        assert sheets.notice == "Saving your last change… Delete will work in a moment."
    finally:
        session.busy = False


def test_block_keys_do_nothing_with_no_block_focused(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = show_material(qapp, material_window)
    session = material_window.session
    sheets = material_window._material_page.bridge.sheets
    seen: list[object] = []
    monkeypatch.setattr(material_window, "_show_preview", lambda *a, **kw: seen.append(a))
    root.forceActiveFocus()
    pump(qapp)
    quick = material_window._material_page._quick
    for key, mods in (
        (Qt.Key.Key_C, CTRL),
        (Qt.Key.Key_D, CTRL),
        (Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier),
    ):
        QTest.keyClick(quick, key, mods)
        pump(qapp)
    assert session.clipboard is None
    assert seen == []
    assert sheets.ask == {}
    assert any(item["id"] == "school" for item in session.blocks)


def test_block_keys_do_nothing_while_typing(qapp: QApplication, material_window: NativeWindow) -> None:
    """A sheet is open: Ctrl+C there is the field's own, and Delete must not reach a block under it."""
    block = _focused_school(qapp, material_window)
    session = material_window.session
    sheets = material_window._material_page.bridge.sheets
    sheets.openHomework()
    pump(qapp)
    assert block.property("activeFocus") is False
    quick = material_window._material_page._quick
    QTest.keyClick(quick, Qt.Key.Key_C, CTRL)
    QTest.keyClick(quick, Qt.Key.Key_Delete)
    pump(qapp)
    assert session.clipboard is None
    assert sheets.ask == {}
    assert any(item["id"] == "school" for item in session.blocks)


def test_help_lists_the_new_keys_in_material() -> None:
    rows = dict(help_keys(True, True, material=True))
    assert rows["[F1]"] == "Help"
    assert rows["[Ctrl]+[N]"] == "Add homework"
    assert rows["[Ctrl]+[C] then [Ctrl]+[V]"].startswith("Copy the selected block")
    assert rows["[Ctrl]+[D]"] == "Duplicate the selected block"
    assert rows["[Delete]"] == "Delete the selected block"
    assert "[Ctrl]+[K]" not in rows


def test_ctrl_shift_l_opens_the_week_as_a_list(qapp: QApplication, material_window: NativeWindow) -> None:
    root = show_material(qapp, material_window)
    quick = material_window._material_page._quick
    sheets = material_window._material_page.bridge.sheets
    root.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_L, CTRL | Qt.KeyboardModifier.ShiftModifier)
    pump(qapp)
    assert sheets.kind == "weekList"


def test_ctrl_shift_l_does_nothing_while_a_sheet_is_open(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    root = show_material(qapp, material_window)
    quick = material_window._material_page._quick
    sheets = material_window._material_page.bridge.sheets
    root.forceActiveFocus()
    sheets.openHomework()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_L, CTRL | Qt.KeyboardModifier.ShiftModifier)
    pump(qapp)
    assert sheets.kind == "homework"
