# ruff: noqa: F811
"""A tap on a row of an open picker list belongs to the list, even when the row hangs outside the sheet's
card: it picks the row, the sheet stays open and no "Discard your changes?" question appears. Esc with a
list open closes only the list, and a real tap on the dimmed area with no list open still asks.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.material_support import pump, show_material, visuals  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    DISCARD,
    find_named,
    open_light,
    qapp,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until  # noqa: E402

ROW = 44


def _scene(shell: NativeWindow) -> QObject:
    return shell._material_page._quick.quickWindow().contentItem()


def _open_due_list(qapp: QApplication, shell: NativeWindow, sheets, height: int) -> tuple[QObject, QObject]:
    """Add homework in a window short enough that the Due list hangs below the card. Returns (card, list)."""
    shell.resize(1280, height)
    pump(qapp, 30)
    sheets.openHomework()
    sheets.setText("title", "Essay")
    pump(qapp, 40)
    root = shell._material_page._quick.rootObject()
    find_named(root, "homeworkDue").forceActiveFocus()
    pump(qapp)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Space)
    pump(qapp, 10)
    lists = [item for item in visuals(_scene(shell)) if str(item.objectName()) == "pickerList"]
    assert lists, "the due list did not open"
    return find_named(root, "sheetCard"), lists[0]


def _tap(shell: NativeWindow, spot: QPoint) -> None:
    """A real left tap. The pointer arrives first, as it does on a screen: a row takes a tap only once the
    pointer has been over it."""
    quick = shell._material_page._quick
    QTest.mouseMove(quick, spot)
    pump(QApplication.instance(), 5)
    QTest.mousePress(quick, Qt.MouseButton.LeftButton, pos=spot)
    pump(QApplication.instance(), 5)
    QTest.mouseRelease(quick, Qt.MouseButton.LeftButton, pos=spot)
    pump(QApplication.instance(), 20)


def _is_shown(item: QObject) -> bool:
    """Whether the item and everything above it is visible: a closed popup hides its own wrapper."""
    while item is not None:
        if not item.isVisible():
            return False
        item = item.parentItem()
    return True


def _bottom_of(item: QObject) -> float:
    return item.mapToScene(item.boundingRect().bottomLeft()).y()


def _row_point(picker: QObject, index: int) -> QPoint:
    top = index * ROW - picker.property("contentY")
    spot = picker.mapToScene(QPointF(picker.boundingRect().center().x(), top + ROW / 2))
    return QPoint(int(spot.x()), int(spot.y()))


def _row_outside_the_card(card: QObject, picker: QObject) -> int:
    visible_top = picker.property("contentY")
    for index in range(picker.property("count")):
        spot = _row_point(picker, index)
        row_top = index * ROW
        inside_list = visible_top <= row_top and row_top + ROW <= visible_top + picker.property("height")
        if inside_list and spot.y() > _bottom_of(card):
            return index
    raise AssertionError("no row of the list lies outside the card")


def test_tapping_a_row_that_hangs_outside_the_card_picks_it_and_keeps_the_sheet(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    show_material(qapp, shell)
    card, picker = _open_due_list(qapp, shell, sheets, 560)
    index = _row_outside_the_card(card, picker)
    wanted = sheets.form["dueOptions"][index]["value"]
    assert wanted != sheets.form["dueDate"], "the row must be a change, or the pick shows nothing"
    _tap(shell, _row_point(picker, index))
    assert sheets.form["dueDate"] == wanted
    assert sheets.kind == "homework", "the sheet stayed open"
    assert sheets.ask == {}, "no Discard question"
    assert sheets.form["title"] == "Essay"
    sheets.forceClose()
    pump(qapp, 5)


def test_esc_with_a_list_open_closes_only_the_list(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    show_material(qapp, shell)
    _card, picker = _open_due_list(qapp, shell, sheets, 560)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Escape)
    pump(qapp, 20)
    wait_until(qapp, lambda: not _is_shown(picker), what="the list to close")
    assert sheets.kind == "homework"
    assert sheets.ask == {}
    sheets.forceClose()
    pump(qapp, 5)


def test_a_tap_on_the_dimmed_area_with_no_list_open_still_asks_to_discard(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    show_material(qapp, shell)
    sheets.openHomework()
    sheets.setText("title", "Essay")
    pump(qapp, 40)
    _tap(shell, QPoint(20, 20))
    assert sheets.ask["title"] == DISCARD
    sheets.forceClose()
    pump(qapp, 5)
