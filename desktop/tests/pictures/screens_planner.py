"""The planner's screens: the Agenda rail beside the Week, the focus list in the rail, the Unfinished
rows, and the plan review box. What the code tests of desktop/tests/planner/ used to measure in pixels
is judged on these pictures."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import QApplication

from desktop.native.hours.rail import BOOK_GAP, SPACING, TITLE_GAP
from desktop.native.window import NativeWindow
from desktop.tests.pictures import planner_keep_signed_in_screens, planner_moves_screens
from desktop.tests.pictures.screen import Screen
from desktop.tests.planner.support import (
    LONG_FOCUS_TASKS,
    ONE_UNPLACED,
    TITLES,
    TRACE,
    WEEK,
    agenda_week,
    open_unfinished,
    overdue_this_week,
    week_list_action,
)

RAIL_SOURCES = ("desktop/native/hours/rail.py", "desktop/native/window.py", "desktop/native/look.py")
UNFINISHED_SOURCES = ("desktop/native/widgets.py", "desktop/native/window.py")


def _agenda_rail(window: NativeWindow) -> object:
    agenda_week(window)
    return window.rail


def _week_with_large_day_names(window: NativeWindow) -> object:
    agenda_week(window)
    return None


def _week_list_over_the_grid(window: NativeWindow) -> object:
    agenda_week(window)
    week_list_action(window).trigger()
    for _ in range(3):
        QApplication.processEvents()
    return None


def _focus_rows_with_wrapped_titles(window: NativeWindow) -> object:
    agenda_week(window)
    rail = window.rail
    rail.set_tasks(LONG_FOCUS_TASKS, 0)
    # The Agenda rail does not show the old focus list; the list's rows are still measured and drawn.
    rail.focus.setVisible(True)
    QApplication.processEvents()
    return rail


def _focus_rows_in_a_narrow_list(window: NativeWindow) -> object:
    agenda_week(window)
    rail = window.rail
    rail.set_tasks([{"id": "one", "day": 2, "start": "19:00", "title": "Chem lab"}], 0)
    rail.focus.setVisible(True)
    QApplication.processEvents()
    tasks = rail.tasks
    index = tasks.indexFromItem(tasks.item(0))
    _lines, _below, timing = tasks.itemDelegate().row_lines(index, tasks.viewport().width())
    body, _small = rail.fonts()
    # The width at which the title and its time just fit on one line; the list is made narrower.
    beside = (
        SPACING[1]
        + 16
        + BOOK_GAP
        + QFontMetricsF(body).horizontalAdvance("Chem lab")
        + TITLE_GAP
        + QFontMetricsF(timing).horizontalAdvance(str(index.data(Qt.ItemDataRole.ToolTipRole)))
        + SPACING[1]
    )
    rail.focus.setFixedWidth(int(beside) - 8)
    QApplication.processEvents()
    return rail


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


def _plan_review_many_rows(window: NativeWindow) -> object:
    window.plan_review.set_trace(TRACE, TITLES, WEEK, (1, 1), window.session.assignments)
    QApplication.processEvents()
    return window.plan_review


def _plan_review_one_row(window: NativeWindow) -> object:
    window.plan_review.set_trace(ONE_UNPLACED, TITLES, WEEK, (0, 1), window.session.assignments)
    QApplication.processEvents()
    return window.plan_review


SCREENS: list[Screen] = [
    Screen(
        id="planner.agenda_rail",
        area="planner",
        prepare=_agenda_rail,
        checks=(
            "The rail stands left of the week at its full width, not folded; the mini month, the old focus "
            "list and the Show month control are not in it. Sections in order: the Next card (Soccer "
            "practice, 4:00 PM, in 20 min, then Dinner), the rows with their Start focus buttons, No time "
            "yet with its one chip (Math worksheet, 1 h), and Due this week (Chem lab report, History "
            "essay, Math worksheet, each Sun). The count beside No time yet is plain ink: no pill, no "
            "background, no rounded corners, no padding. Every section heading is in the ink colour, "
            "not a tint; the sections are spaced evenly by the same gap; no status strip sits above the "
            "calendar and the calendar sits right under the plan bar."
        ),
        sources=RAIL_SOURCES,
        main=True,
    ),
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
        id="planner.focus_rows_with_wrapped_titles",
        area="planner",
        prepare=_focus_rows_with_wrapped_titles,
        checks=(
            "The focus list at the rail's own width (narrower than the window). The two long titles each "
            "wrap onto two lines, and each such row is taller than a one-line row (more than 30 px). Every "
            "row is at least as tall as the lines drawn in it, spans the list's full width, and no two "
            "rows touch or overlap; the short title (Math) below them has its own row under the second "
            "long one. The list is at least as tall as all its rows together, nothing is cut off."
        ),
        sources=("desktop/native/hours/rail.py",),
    ),
    Screen(
        id="planner.focus_rows_in_a_narrow_list",
        area="planner",
        prepare=_focus_rows_in_a_narrow_list,
        checks=(
            "The focus list made narrower than the width where the title and its time fit side by side. "
            "The title wraps and the row is taller than a one-line row would be; the row still holds all "
            "its lines, and the list is as tall as the row. At Large text the rows are measured again "
            "with the larger font and still hold their text."
        ),
        sources=("desktop/native/hours/rail.py",),
        main=True,
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
    Screen(
        id="planner.plan_review_many_rows",
        area="planner",
        prepare=_plan_review_many_rows,
        checks=(
            "The plan review box heading 'Placed 1' with 'without a time' count, its details open with "
            "three rows (not placed with why, the move, the tight deadline). The list is as tall as "
            "its three rows need and no taller than 132 px; no row is cut off."
        ),
        sources=("desktop/native/widgets.py",),
    ),
    Screen(
        id="planner.plan_review_one_row",
        area="planner",
        prepare=_plan_review_one_row,
        checks=(
            "The plan review box with a single row (Science fair poster has no time yet, and why). The "
            "list is only as tall as that one line, clearly shorter than the list in "
            "planner.plan_review_many_rows: one line in a box four lines deep reads as an error."
        ),
        sources=("desktop/native/widgets.py",),
    ),
]

SCREENS = [*SCREENS, *planner_moves_screens.SCREENS]
SCREENS = [*SCREENS, *planner_keep_signed_in_screens.SCREENS]
