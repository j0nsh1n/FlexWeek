"""Week's screens: the fragments, one per behaviour group, gathered for the renderer."""

from __future__ import annotations

from desktop.tests.pictures import (
    week_clock,
    week_drag,
    week_hand,
    week_material,
    week_painter,
    week_pastnext,
    week_typing,
    week_weekview,
    week_zoom,
)
from desktop.tests.pictures.screen import Screen

SCREENS: list[Screen] = [
    *week_painter.SCREENS,
    *week_hand.SCREENS,
    *week_zoom.SCREENS,
    *week_drag.SCREENS,
    *week_material.SCREENS,
    *week_weekview.SCREENS,
    *week_typing.SCREENS,
    *week_clock.SCREENS,
    *week_pastnext.SCREENS,
]
