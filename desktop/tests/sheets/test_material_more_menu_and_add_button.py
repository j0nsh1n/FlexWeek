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
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from desktop.native.window import WEEK_LIST_NAME, NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import material_window, qapp  # noqa: E402, F401
from desktop.tests.material_support import named, pump, qml, show_material  # noqa: E402


def _menu_labels(menu: QWidget) -> list[str]:
    labels: list[str] = []
    for action in menu.actions():
        if action.isSeparator() or not action.isVisible():
            continue
        labels.append(action.text().split("\t", 1)[0])
        inner = action.menu()
        if inner is not None:
            labels.extend(_menu_labels(inner))
    return labels


def test_material_more_lists_the_planning_actions_and_leaves_the_widgets_menu_alone(
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
        "Help",
        "About FlexWeek",
        "Sign out",
    ]
    bridge.sheets.closeMore()
    window._use_widgets_styles()
    pump(qapp)
    window.more_menu.popup(window.more_button.mapToGlobal(window.more_button.rect().bottomLeft()))
    pump(qapp)
    try:
        assert "Unfinished" in _menu_labels(window.more_menu)
        assert WEEK_LIST_NAME in _menu_labels(window.more_menu)
    finally:
        window.more_menu.close()


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
    if sheets.kind != "homework":
        QTest.keyClick(quick, Qt.Key.Key_Return)
        pump(qapp)

    assert sheets.kind == "homework"
    assert named(root, "sheetTitle")[0].property("text") == "Add homework"
    assert QApplication.activeModalWidget() is None
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert sheets.kind == ""
    assert quick.quickWindow().activeFocusItem() is fab
