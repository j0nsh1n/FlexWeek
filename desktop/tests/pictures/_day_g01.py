"""Pictures of the Material Day hour column: what the old layout tests asserted in pixels. The lead
gathers this fragment into screens_day.py."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.day.support_material_day import look, open_day_page, seed_thursday
from desktop.tests.pictures.screen import Screen

SOURCES = ("desktop/native/material", "desktop/native/hours")


def _hour_column(window: NativeWindow) -> None:
    qapp = QApplication.instance()
    seed_thursday(qapp, window, hour=19, soccer=True)
    open_day_page(qapp, window)


def _compact_hour_column(window: NativeWindow) -> None:
    _hour_column(window)
    look(window, density="compact")


SCREENS: list[Screen] = [
    Screen(
        id="day.hour_column",
        area="day",
        prepare=_hour_column,
        checks=(
            "Thursday at 19:00 with School 08:00-14:30, Soccer 16:00-17:30 and the History essay "
            "18:45-19:45. "
            "An hour row is 56 px high at Comfortable. Each block's top is on its start time: School at the "
            "08:00 row, Soccer at the 16:00 row, the essay three quarters of the way down the 18:00 row. "
            "School and Soccer are over and look past; the essay does not. The now line is at the 19:00 row "
            "and runs behind every block, while its dot stays on top of them. Blocks end 16 px short of the "
            "right edge so the now line can be seen passing the end of the essay. Only the hour column is "
            "drawn: no Up next or Done lists on Day."
        ),
        sources=SOURCES,
        main=True,
        styles=("material",),
    ),
    Screen(
        id="day.compact_hour_column",
        area="day",
        prepare=_compact_hour_column,
        checks=(
            "The same Thursday with the Compact look: an hour row is 44 px high on Day, the same as on Week, "
            "and blocks and the now line still sit on their times."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
]
