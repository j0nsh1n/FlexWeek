"""Month screens that stand in for the look checks of the old Month tests (hours canvas, date pane,
Material study-time fill). The lead folds this fragment into screens_month.py.

Every prepare works through the signed-in account: it adds the week's blocks and homework with the
session, then opens Month, so the same state is drawn in every style."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QAbstractButton, QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

SOURCES = (
    "desktop/native/hours/month.py",
    "desktop/native/layouts/base.py",
    "desktop/native/window.py",
    "backend/month.py",
)
MATERIAL_SOURCES = (
    "desktop/native/material/qml/month",
    "desktop/native/material/bridge_month.py",
    "desktop/native/hours/month.py",
)


def _settled(window: NativeWindow) -> None:
    session = window.session
    wait_until(QApplication.instance(), lambda: not session.busy and not session.dirty)


def _fill(window: NativeWindow) -> None:
    """The open week (Monday 2 to Sunday 8 November, today Thursday 5th): School on weekdays, a busy
    Wednesday, a done session, and two deadlines, one already gone and one at 09:00 next Thursday."""
    session = window.session
    monday = datetime.fromisoformat(session.week_start)
    session.add_block(
        {"id": "school", "title": "School", "kind": "locked", "category": "class",
         "start": "08:00", "duration_min": 390, "days": [0, 1, 2, 3, 4]}
    )
    for number in range(4):
        session.add_block(
            {"id": f"club-{number}", "title": f"Club {number + 1}", "kind": "locked",
             "category": "extra", "start": f"{15 + number}:00", "duration_min": 45, "days": [2]}
        )
    gone = (monday + timedelta(days=1)).strftime("%Y-%m-%dT17:00")
    coming = (monday + timedelta(days=10)).strftime("%Y-%m-%dT09:00")
    for key, title, due in (("essay", "History essay", gone), ("oral", "French oral", coming)):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
    # Study time: half a date planned on Tuesday, a full date done on Wednesday, so the fill, the
    # deeper "done" fill and "and N more" over it can all be seen.
    session.add_block(
        {"id": "essay-tue", "title": "History essay", "kind": "flexible", "category": "homework",
         "assignment_id": "essay", "start": "16:00", "duration_min": 90, "days": [1], "pinned": True}
    )
    session.add_block(
        {"id": "oral-wed", "title": "French oral", "kind": "flexible", "category": "homework",
         "assignment_id": "oral", "start": "10:00", "duration_min": 180, "days": [2], "pinned": True,
         "completed": True, "completed_day": 2}
    )
    session.save()
    _settled(window)


def _open_month(window: NativeWindow) -> None:
    session = window.session
    if window._stack.currentWidget().objectName() == "materialPage":
        window._material_page.bridge.showPage("month")
    else:
        window.findChild(QAbstractButton, "viewMonth").click()
    wait_until(
        QApplication.instance(),
        lambda: session.planner_view == "month" and session.month_data is not None and not session.busy,
        what="Month opening",
    )


def _month(window: NativeWindow) -> None:
    _fill(window)
    _open_month(window)


def grid(window: NativeWindow) -> object:
    _month(window)
    return None


def grid_tight(window: NativeWindow) -> object:
    """With the plan and Unfinished panels open the Widgets month is squeezed to fit its view."""
    _month(window)
    window.month_grid.set_tight(True)
    QApplication.processEvents()
    return None


def date_drawer(window: NativeWindow) -> object:
    """Under 1150 px the date pane is a drawer over the right of the grid; open on Saturday."""
    window.resize(1100, 760)
    _month(window)
    window.month_grid._date_chosen("2026-11-07")
    QApplication.processEvents()
    return None


def study_time_widgets(window: NativeWindow) -> object:
    _month(window)
    window.month_grid.pane.load_switch.setChecked(True)
    QApplication.processEvents()
    return None


def study_time_material(window: NativeWindow) -> object:
    _fill(window)
    window._material_page.bridge.setShowStudyTime(True)
    _open_month(window)
    window._material_page.bridge.setShowStudyTime(True)
    QApplication.processEvents()
    return None


SCREENS: list[Screen] = [
    Screen(
        id="month.grid",
        area="month",
        prepare=grid,
        main=True,
        sources=SOURCES,
        checks=(
            "Today (Thursday 5 November) has its number on an accent disc; other numbers are in the text "
            "colour inside November and in the muted colour outside it. A date outside the month is a card "
            "like the rest, in the panel colour, not tinted like today's wash. "
            "This week's row is banded in about 4 % of the text colour, never the accent, and no other "
            "row is banded. "
            "A week's row is as tall as its busiest date's chips (two to three), so Wednesday's row is "
            "taller than a quiet one; the busy Wednesday shows three chips and says \"and N more\", and "
            "the last chip shown sits wholly inside its date. "
            "A block's chip is filled with its category colour as the Week fills it: pale on Light, sunk "
            "into the card on Dark, not the strong mark washed over the card. "
            "A deadline chip is a quiet neutral chip led by Due or Overdue; it is not outlined in "
            "homework's colour and the error colour is not used on it, gone or coming. "
            "A chip that is done keeps its words at full text strength; only its fill is about half as "
            "strong. "
            "At Large text a chip takes two lines, keeps its time and whole words, and fits inside its "
            "date. "
            "Sunday never sits under the scroll bar when the month scrolls."
        ),
    ),
    Screen(
        id="month.grid_tight",
        area="month",
        prepare=grid_tight,
        sources=SOURCES,
        checks=(
            "At 1024 x 640 with the panels open all five week rows fit the view, the last row ends inside "
            "it and no scroll bar shows. Every row is at least the tight row height: its number and one "
            "chip. A busy date shows one chip and counts the rest; the chip and the count both lie "
            "inside the date and the count does not cover the chip. With room for one line only, the "
            "count is written by the number, above the chip."
        ),
    ),
    Screen(
        id="month.date_drawer",
        area="month",
        prepare=date_drawer,
        sources=SOURCES,
        checks=(
            "Under 1150 px wide the date pane is a drawer on the right edge of the grid, exactly 300 px "
            "wide, as tall as the grid below the warning line, with Close visible; it covers the "
            "right of the grid only while open."
        ),
    ),
    Screen(
        id="month.study_time_widgets",
        area="month",
        prepare=study_time_widgets,
        sources=SOURCES,
        checks=(
            "With Show study time per date on, dates with homework show a thin bar for planned time and "
            "a stronger one for completed time, in proportion to the 3-hour cap."
        ),
    ),
    Screen(
        id="month.study_time_material",
        area="month",
        prepare=study_time_material,
        main=True,
        styles=("material",),
        sources=MATERIAL_SOURCES,
        checks=(
            "With Show study time per date on, a date is filled from the bottom, full at the 3-hour cap: "
            "above the planned share the date keeps its own colour, the planned share is the homework "
            "tint, and the done share at the bottom is deeper toward the homework colour. "
            "The day number stays readable on a full date (contrast at least 4.5 : 1 against the fill "
            "beside it). "
            "High contrast keeps its outline drawn over the fill, visibly different from the fill; a "
            "picked date full of study time still looks picked at its side and bottom edges. "
            "\"and N more\" is readable on done time (contrast at least 4.5 : 1), beside the number on a "
            "short date and under the chips on a tall one. "
            "On a narrow date the dots sit on a backing, and the homework dot has contrast of at least "
            "3 : 1 against what is around it."
        ),
    ),
]
