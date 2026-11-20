"""The planner's screens: the Agenda rail beside the Week, the focus list in the rail, the Unfinished
rows, and the plan review box. What the code tests of desktop/tests/planner/ used to measure in pixels
is judged on these pictures."""

from __future__ import annotations

from desktop.native.window import NativeWindow
from desktop.tests.pictures import planner_moves_screens
from desktop.tests.pictures.screen import Screen
from desktop.tests.planner.support import (
    agenda_week,
)


def _week_with_large_day_names(window: NativeWindow) -> object:
    agenda_week(window)
    return None
















SCREENS: list[Screen] = [
    Screen(
        id="planner.week_day_names_large_text",
        area="planner",
        prepare=_week_with_large_day_names,
        checks=(
            "At Large text the date sits under the day name in each day heading (two lines), the heading "
            "is taller than at Normal text, and nothing in it is clipped. At Normal the name and date "
            "share a line."
        ),
        sources=("desktop/native/window.py", "desktop/native/weekmodel.py"),
        main=True,
    ),
]

SCREENS = [*SCREENS, *planner_moves_screens.SCREENS]
