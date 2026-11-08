"""Pictures of the Material My day rows. The lead gathers this fragment into screens_myday.py."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.day.support_material_day import bridge_of, seed_thursday
from desktop.tests.material_support import pump, show_material
from desktop.tests.pictures.screen import Screen


def _category_colours(window: NativeWindow) -> None:
    qapp = QApplication.instance()
    # Early on Thursday nothing is over, so School, Soccer and the essay are all in Up next.
    seed_thursday(qapp, window, hour=7, soccer=True)
    show_material(qapp, window)
    bridge_of(window).showPage("myday")
    pump(qapp)


SCREENS: list[Screen] = [
    Screen(
        id="myday.category_colours",
        area="myday",
        prepare=_category_colours,
        checks=(
            "Thursday at 07:00, so School, Soccer and the History essay are all in Up next. Each row has a "
            "faint tint of its class colour as its fill and the full colour on its edge. In light: School "
            "fill #e4ebf7 with edge #3d6fc4; Soccer (sports) fill #e1f0e9 with edge #2b9665; the essay "
            "(work) fill #f3ecde with edge #a87512. In dark: fills #1e2c44, #1a352e and #382e1a with the "
            "same edges. Icons are school, schedule and edit_note."
        ),
        sources=("desktop/native/material",),
        main=True,
        styles=("material",),
    ),
]
