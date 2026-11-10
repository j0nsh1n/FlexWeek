# ruff: noqa: F811
"""Edit homework that is pinned to a time off the quarter hour (a pin made by a 5-minute drag): the Pinned
time field shows it, Up and Down step to the next time in order rather than to midnight, and a Save that
does not touch it keeps it.

Expected values come from the pin seeded here: the History essay on Friday at 18:55.
"""

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
    find_named,
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)

FRIDAY = 4


def _pin_essay_at_1855(qapp: QApplication, shell: NativeWindow) -> None:
    session = shell.session
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:55", "days": [FRIDAY], "pinned": True})
    session.add_block(work)
    session.save()
    settle(qapp, shell)


def _open_edit(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    _pin_essay_at_1855(qapp, shell)
    sheets.editHomework("essay")
    pump(qapp)
    assert sheets.form["when"] == "fixed"


def test_the_pinned_time_field_shows_the_pin_and_lists_it_in_order(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_edit(qapp, shell, sheets)
    shell.session.preferences = {**(shell.session.preferences or {}), "clock_24h": True}
    shell._set_clock()
    sheets.editHomework("essay")
    pump(qapp)
    form = sheets.form
    assert form["whenTime"] == "18:55"
    assert [item["label"] for item in form["pinnedTimeOptions"]].count("18:55") == 1
    values = [item["value"] for item in form["pinnedTimeOptions"]]
    assert values == sorted(values)
    root = shell._material_page._quick.rootObject()
    assert find_named(root, "homeworkWhenTime").property("shown") == "18:55"


def test_down_from_the_off_quarter_pin_goes_to_the_next_time_not_to_midnight(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_edit(qapp, shell, sheets)
    root = shell._material_page._quick.rootObject()
    find_named(root, "homeworkWhenTime").forceActiveFocus()
    pump(qapp)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Down)
    pump(qapp, 8)
    assert sheets.form["whenTime"] == "19:00"
    sheets.forceClose()
    pump(qapp, 5)


def test_save_without_touching_the_pin_keeps_it_exactly(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_edit(qapp, shell, sheets)
    sheets.setText("title", "History essay, final")
    sheets.save()
    pump(qapp)
    settle(qapp, shell)
    pinned = next(
        item for item in shell.session.blocks if item.get("assignment_id") == "essay" and item.get("pinned")
    )
    assert pinned["start"] == "18:55"
    assert pinned["days"] == [FRIDAY]
