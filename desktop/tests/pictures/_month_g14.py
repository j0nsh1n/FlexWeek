"""Month screens for the window chrome: its scroll bar, and the focus ring on Material's date cells (look
checks of test_top_bar and test_pr5b_toast_rings_textsize)."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump as pump_material
from desktop.tests.material_support import show_material, visuals
from desktop.tests.pictures.screen import Screen


def _material_date_cell(window: NativeWindow) -> QObject:
    show_material(QApplication.instance(), window)
    window._material_page.bridge.showPage("month")
    pump_material(QApplication.instance(), 10)
    root = window._material_page.root
    cells = [
        item for item in visuals(root) if item.objectName() and item.objectName().startswith("monthDate-")
    ]
    return cells[0] if cells else None


SCREENS: list[Screen] = [
    Screen(
        id="month.date_cell_ring",
        area="month",
        prepare=_material_date_cell,
        checks=(
            "A Material Month date cell's focus ring has a 14 px radius (the card's 12 px plus the 2 px "
            "margin) and is in the theme's primary colour, the same ring the other Material controls use."
        ),
        sources=("desktop/native/material",),
        styles=("material",),
    ),
]
