# ruff: noqa: F811
"""Material 3's More sheet lists the planning actions (and the Widgets menu is left alone), and the Add
button opens the homework sheet from the keyboard and gets focus back when it closes.
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
from desktop.tests.day.support_material_window import material_window, qapp  # noqa: E402, F401
from desktop.tests.material_support import (  # noqa: E402
    named,
    pump,
    qml,
    show_material,
)


def test_material_more_lists_the_planning_actions(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    show_material(qapp, window)
    bridge = window._material_page.bridge

    bridge.openMore()
    pump(qapp)

    assert QApplication.activePopupWidget() is None
    assert bridge.sheets.moreOpen is True
    labels = [row["label"] for row in bridge.sheets.moreEntries if row["id"]]
    assert labels == [
        "Running late",
        "Unfinished",
        "Week as a list",
        "Routines",
        "Quick focus",
        "Replan all my homework",
        "Copy day",
        "Copy last week's fixed times",
        "Copies of this week",
        "Reload this week",
        "Help",
        "About FlexWeek",
        "Account",
        "Sign out",
    ]
    bridge.sheets.closeMore()


def test_the_add_button_opens_homework_from_the_keyboard(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    root = show_material(qapp, window)
    fab = qml(root, "materialFab")
    assert "Rectangle" not in fab.metaObject().className()
    assert fab.property("activeFocusOnTab") is True
    sheets = window._material_page.bridge.sheets
    window.activateWindow()
    quick = window._material_page._quick
    quick.setFocus()
    fab.forceActiveFocus()
    pump(qapp)

    QTest.keyClick(quick, Qt.Key.Key_Space)
    pump(qapp)
    # The Add button asks which; Add homework is the first row.
    QTest.keyClick(quick, Qt.Key.Key_Return)
    pump(qapp)

    assert sheets.kind == "homework"
    assert named(root, "sheetTitle")[0].property("text") == "Add homework"
    assert QApplication.activeModalWidget() is None
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert sheets.kind == ""
    assert quick.quickWindow().activeFocusItem() is fab
