"""Week screen for Material's rows at larger text. The Widgets top bar's pictures went with the top bar."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump as pump_material
from desktop.tests.material_support import show_material
from desktop.tests.pictures.screen import Screen


def _material_week_rows(window: NativeWindow) -> None:
    show_material(QApplication.instance(), window)
    window._material_page.bridge.showPage("week")
    pump_material(QApplication.instance(), 10)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="week.material_larger_text_rows",
        area="week",
        prepare=_material_week_rows,
        checks=(
            "Material's Week at Normal text has 56 px hour rows; at Larger text they are at least 1.5 "
            "times that (84 px), and the rows' text is not clipped."
        ),
        sources=("desktop/native/material",),
        styles=("material",),
    ),
]
