"""Day screens for the window chrome: Timeline day's top bar at Large text, and Material's day rows at larger
text (look checks of test_window_screens and test_pr5b_toast_rings_textsize)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump as pump_material
from desktop.tests.material_support import show_material
from desktop.tests.pictures.screen import Screen


def _material_day_rows(window: NativeWindow) -> None:
    show_material(QApplication.instance(), window)
    window._material_page.bridge.showPage("day")
    pump_material(QApplication.instance(), 10)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="day.material_larger_text_rows",
        area="day",
        prepare=_material_day_rows,
        checks=(
            "Material's Day at Larger text has rows at least 1.5 times the height they have at Normal text "
            "(56 px), and their text is not clipped."
        ),
        sources=("desktop/native/material",),
        styles=("material",),
    ),
]
