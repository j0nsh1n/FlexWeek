"""Month screens from the Material month tests (views lane, group G04). The lead folds SCREENS into
screens_month.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from desktop.tests.month.support_material_month import open_month, seed_school_and_essay
from desktop.tests.pictures.screen import Screen

if TYPE_CHECKING:
    from desktop.native.window import NativeWindow


def _material_month(window: NativeWindow) -> None:
    """November 2026 with School on weekday mornings and the History essay on Thursday evening."""
    seed_school_and_essay(window)
    open_month(QApplication.instance(), window)


SCREENS: list[Screen] = [
    Screen(
        id="month.dates_outside_the_month",
        area="month",
        prepare=_material_month,
        checks=(
            "Dates outside the shown month (26 to 31 October, 1 to 6 December): only the date's fill and "
            "its number fade, to 0.45 of full strength; the cell itself stays at opacity 1.0, so the chips "
            "in those dates keep their contrast. Dates inside the month are at full strength (fade 1.0)."
        ),
        sources=(
            "desktop/native/material/bridge_month.py",
            "desktop/native/material/qml/month",
        ),
        main=True,
        styles=("material",),
    ),
]
