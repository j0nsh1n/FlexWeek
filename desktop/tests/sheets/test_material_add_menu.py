# ruff: noqa: F811
"""The Add button asks what to add: homework or a fixed time, on every screen that has the button."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump, qml, show_material
from desktop.tests.sheets.support_material_sheets import click
from desktop.tests.window_support import qapp  # noqa: F401


def _open_menu(qapp: QApplication, window: NativeWindow, screen: str) -> tuple[QObject, QObject]:
    root = show_material(qapp, window)
    window._material_page.bridge.showPage(screen)
    pump(qapp, 40)
    click(window, qml(root, "materialFab"))
    menu = qml(root, "addMenu")
    assert menu.property("open") is True
    return root, menu


def _rows(menu: QObject) -> list[str]:
    return [str(row["label"]) for row in menu.property("entries").toVariant()]


@pytest.mark.parametrize("screen", ["week", "day", "month", "myday"])
def test_the_add_button_offers_homework_and_fixed_time_on_each_screen(
    qapp: QApplication, window: NativeWindow, screen: str
) -> None:
    _root, menu = _open_menu(qapp, window, screen)
    assert _rows(menu) == ["Add homework", "Add fixed time"]


@pytest.mark.parametrize("screen", ["week", "month", "myday"])
def test_add_fixed_time_opens_the_fixed_time_sheet(
    qapp: QApplication, window: NativeWindow, screen: str
) -> None:
    _root, _menu = _open_menu(qapp, window, screen)
    quick = window._material_page._quick
    QTest.keyClick(quick, Qt.Key.Key_Down)
    QTest.keyClick(quick, Qt.Key.Key_Return)
    pump(qapp, 20)
    sheets = window._material_page.bridge.sheets
    assert sheets.kind == "block"
    assert window._material_page.bridge.screen == screen


def test_add_homework_from_the_menu_opens_the_homework_sheet(
    qapp: QApplication, window: NativeWindow
) -> None:
    _root, menu = _open_menu(qapp, window, "week")
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    pump(qapp, 20)
    assert window._material_page.bridge.sheets.kind == "homework"
    assert menu.property("open") is False


def test_esc_closes_the_menu_and_the_keyboard_goes_back_to_the_button(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, menu = _open_menu(qapp, window, "week")
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert menu.property("open") is False
    assert window._material_page.bridge.sheets.kind == ""
    assert qml(root, "materialFab").property("activeFocus") is True
