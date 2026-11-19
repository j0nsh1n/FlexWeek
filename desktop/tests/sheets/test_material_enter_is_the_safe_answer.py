# ruff: noqa: F811
"""Enter on a prompt that asks before deleting or discarding gives the safe answer (Cancel, or Keep editing),
never the destructive one. A student who presses Enter without reading loses nothing."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
    type_homework,
)
from desktop.tests.sheets.support_soccer import soccer  # noqa: E402


def _press_enter(qapp: QApplication, shell: NativeWindow) -> None:
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Return)
    pump(qapp, 30)


def test_enter_on_delete_a_fixed_time_keeps_it(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    shell.session.add_block(soccer())
    shell.session.save()
    settle(qapp, shell)
    sheets.askDeleteBlock("soccer", 3)
    pump(qapp, 30)
    assert [answer["id"] for answer in sheets.ask["answers"]] == ["stay", "delete"]
    _press_enter(qapp, shell)
    assert sheets.ask == {}
    assert [item["id"] for item in shell.session.blocks if item["id"] == "soccer"] == ["soccer"]
    assert sheets.notice == ""


def test_enter_on_delete_homework_keeps_it(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    sheets.editHomework("essay")
    sheets.remove()
    pump(qapp, 30)
    assert sheets.ask["id"] == "delete-homework"
    _press_enter(qapp, shell)
    assert sheets.ask == {}
    assert "essay" in shell.session.assignments
    assert sheets.notice == ""


def test_enter_on_delete_unfinished_homework_keeps_it(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.askDeleteUnfinished("essay")
    pump(qapp, 30)
    assert sheets.ask["id"] == "delete-unfinished"
    _press_enter(qapp, shell)
    assert sheets.ask == {}
    assert "essay" in shell.session.assignments


def test_enter_on_discard_your_changes_keeps_editing(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    sheets.openHomework()
    type_homework(sheets, "Essay")
    sheets.closeSheet()
    pump(qapp, 30)
    assert sheets.ask["title"] == "Discard your changes?"
    _press_enter(qapp, shell)
    assert sheets.ask == {}
    assert sheets.kind == "homework", "the sheet is still open"
    assert sheets.form["title"] == "Essay", "and what was typed is kept"
