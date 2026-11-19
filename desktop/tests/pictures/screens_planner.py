"""The planner's screens: the Agenda rail beside the Week, the focus list in the rail, the Unfinished
rows, and the plan review box. What the code tests of desktop/tests/planner/ used to measure in pixels
is judged on these pictures."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures import planner_moves_screens
from desktop.tests.pictures.screen import Screen
from desktop.tests.planner.support import (
    agenda_week,
    open_unfinished,
    overdue_this_week,
    week_list_action,
)

UNFINISHED_SOURCES = ("desktop/native/widgets.py", "desktop/native/window.py")




def _week_with_large_day_names(window: NativeWindow) -> object:
    agenda_week(window)
    return None


def _week_list_over_the_grid(window: NativeWindow) -> object:
    agenda_week(window)
    week_list_action(window).trigger()
    for _ in range(3):
        QApplication.processEvents()
    return None






def _unfinished_row(window: NativeWindow) -> object:
    overdue_this_week(None, window)
    open_unfinished(window)
    return None


def _three_wrapped_unfinished_rows(window: NativeWindow) -> object:
    overdue_this_week(None, window)
    session = window.session
    for key, title in (("chemistry", "Long chemistry report"), ("history", "Long history essay")):
        session.add_homework(
            {
                "id": key,
                "title": title,
                "due": session.assignments["bio"]["due"],
                "estimate_min": 1440,
                "revision": 0,
                "spread": "one",
            }
        )
    session.save()
    open_unfinished(window)
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
    Screen(
        id="planner.week_list_over_the_grid",
        area="planner",
        prepare=_week_list_over_the_grid,
        checks=(
            "Week as a list is open over the grid. The calendar underneath has not moved: its top edge is "
            "where it is in planner.agenda_rail, and the list does not push the plan bar or the rail."
        ),
        sources=("desktop/native/window.py",),
    ),
    Screen(
        id="planner.unfinished_row",
        area="planner",
        prepare=_unfinished_row,
        checks=(
            "The Unfinished list with one overdue row (Bio reading) in the classic week. Its buttons (Start "
            "focus, Plan, Delete) are whole: each is at least its natural width, wholly inside the "
            "panel, the list and the row, and none is squeezed or past the right edge. The words are not "
            "cut off (or wrap with the row tall enough). At 1024 x 640 with Large text the buttons sit "
            "under the words, none above their bottom, and the list has no sideways scroll bar. At "
            "1280 x 800 with Normal text the buttons share the words' line, their centres within 4 px of "
            "the words' centre, and no second line of buttons is shown."
        ),
        sources=UNFINISHED_SOURCES,
        main=True,
    ),
    Screen(
        id="planner.unfinished_rows_three_wrapped",
        area="planner",
        prepare=_three_wrapped_unfinished_rows,
        checks=(
            "The Unfinished list with three rows (Bio reading, Long chemistry report, Long history "
            "essay). At 1024 x 640 with Large text the Hide button stays inside the window, the list "
            "scrolls (it is taller than its view), and the window is not pushed past 640 px."
        ),
        sources=UNFINISHED_SOURCES,
        main=True,
    ),
]

SCREENS = [*SCREENS, *planner_moves_screens.SCREENS]
