"""The Day view, read the way a student reads it.

The layout work gave the app a shared vocabulary (`due_label`, `length_label`, the category marks)
and the Day view never got it: it printed `Due 2026-09-17T23:59: Chem lab report`.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication

    from desktop.native.calendar import CATEGORIES
    from desktop.native.widgets import DayAgenda

WEEK = "2026-09-14"
THURSDAY = "2026-09-17"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-day-agenda-test"])
    yield application


def agenda() -> dict:
    return {
        "day_index": 3,
        "due_soon": [
            {"id": "chem", "title": "Chem lab report", "due": "2026-09-17T23:59", "category": "assignments"},
            {"id": "vocab", "title": "Spanish vocab", "due": "2026-09-21T08:00", "category": "study"},
        ],
        "sessions": [
            {
                "start": "18:45",
                "block": {
                    "id": "essay-1",
                    "title": "History essay",
                    "duration_min": 60,
                    "category": "assignments",
                },
            },
            {
                "start": None,
                "block": {
                    "id": "poster-1",
                    "title": "Science fair poster",
                    "duration_min": 120,
                    "category": "assignments",
                },
            },
        ],
        "fixed": [
            {
                "start": "08:00",
                "block": {"id": "school", "title": "School", "duration_min": 390, "category": "class"},
            },
        ],
        "next_action": {"kind": "add"},
    }


def rows(view: DayAgenda) -> list[str]:
    return [view.list.item(i).text() for i in range(view.list.count())]


def swatches(view: DayAgenda) -> list[str]:
    found = []
    for i in range(view.list.count()):
        colour = view.list.item(i).data(Qt.ItemDataRole.DecorationRole)
        if isinstance(colour, QColor):
            found.append(colour.name())
    return found


def test_a_deadline_reads_as_a_student_says_it_not_as_a_timestamp(qapp: QApplication) -> None:
    view = DayAgenda()
    view.set_agenda(THURSDAY, agenda(), None)
    text = "\n".join(rows(view))
    assert "2026-09-17T23:59" not in text
    assert "Chem lab report · due Thu 23:59" in text
    assert "Spanish vocab · due Sep 21 08:00" in text


def test_every_row_carries_its_category_colour(qapp: QApplication) -> None:
    view = DayAgenda()
    view.set_agenda(THURSDAY, agenda(), None)
    assert swatches(view) == [
        CATEGORIES["assignments"]["mark"],
        CATEGORIES["class"]["mark"],
        CATEGORIES["assignments"]["mark"],
        CATEGORIES["assignments"]["mark"],
        CATEGORIES["study"]["mark"],
    ]


def test_the_day_is_in_clock_order(qapp: QApplication) -> None:
    view = DayAgenda()
    view.set_agenda(THURSDAY, agenda(), None)
    text = "\n".join(rows(view))
    assert [row for row in rows(view) if row.isupper()] == []
    assert text.index("08:00 · School") < text.index("18:45 · History essay")
    assert "not placed yet · Science fair poster" in text


def test_lengths_and_unplaced_work_are_said_in_words(qapp: QApplication) -> None:
    view = DayAgenda()
    view.set_agenda(THURSDAY, agenda(), {"workload": {"scheduled_min": 150, "available_min": 990}})
    text = "\n".join(rows(view))
    assert "2 h 30 min planned · 16 h 30 min free" in text
    assert "18:45 · History essay · 1 h" in text
    assert "not placed yet · Science fair poster · 2 h" in text
    assert "unplanned" not in text


def test_an_empty_day_still_says_so(qapp: QApplication) -> None:
    view = DayAgenda()
    view.set_agenda(
        THURSDAY,
        {"day_index": 3, "due_soon": [], "sessions": [], "fixed": [], "next_action": {"kind": "add"}},
        None,
    )
    assert rows(view) == ["Nothing is due soon and nothing is planned for Thursday."]


def test_the_month_opens_on_the_week_the_student_is_in(qapp: QApplication) -> None:
    """It opened on the first row, so on the 19th the current week sat below the fold."""

    from desktop.native.widgets import MonthGrid

    grid = MonthGrid()
    days = [
        {"date": f"2026-09-{day:02d}", "scheduled_min": 0, "due": [], "overdue": []} for day in range(1, 31)
    ]
    grid.set_month({"month": "2026-09", "days": days, "overdue": []}, False)
    grid.resize(700, 200)
    grid.show()
    qapp.processEvents()
    before = grid.table.verticalScrollBar().value()
    grid.reveal("2026-09-19")
    qapp.processEvents()
    after = grid.table.verticalScrollBar().value()
    assert grid.table.verticalScrollBar().maximum() > 0, "the month should be taller than the view"
    assert after > before

    found = [
        grid.table.item(row, column).data(Qt.ItemDataRole.UserRole)
        for row in range(grid.table.rowCount())
        for column in range(7)
        if grid.table.item(row, column) is not None
    ]
    assert "2026-09-19" in found


def test_a_block_that_is_not_on_this_day_is_left_out_rather_than_breaking_the_day() -> None:
    """placement_on says "not on this day" with a sentinel compared by identity. Built fresh inside
    each function it was a different object every call, so the check never matched: the sentinel was
    stored as a block's start time, sorting those starts raised, and the whole Day view went down
    with it. The app looked as though Day simply did nothing."""
    from desktop.native.calendar import agenda_for

    # A block offered on Monday and Tuesday that the solver put on Monday. Tuesday has to leave it
    # out, and that decision is the one the sentinel makes.
    blocks = [
        {"id": "essay", "title": "Essay", "kind": "flexible", "days": [0, 1], "duration_min": 60},
        {"id": "tue", "title": "Tuesday only", "kind": "locked", "start": "09:00", "days": [1]},
    ]
    trace = {"placed": [{"id": "essay", "start": "16:00", "days": [0], "kind": "flexible"}]}
    tuesday = agenda_for("2026-09-14", "2026-09-15", blocks, {}, trace, None)
    assert [row["block"]["id"] for row in tuesday["sessions"]] == []
    assert all(isinstance(row["start"], str) for row in tuesday["fixed"])
    monday = agenda_for("2026-09-14", "2026-09-14", blocks, {}, trace, None)
    assert [row["block"]["id"] for row in monday["sessions"]] == ["essay"]


def test_the_day_stays_in_clock_order_when_something_has_no_time() -> None:
    from desktop.native.calendar import agenda_for

    blocks = [
        {"id": "late", "title": "Late", "kind": "locked", "start": "18:00", "days": [0]},
        {"id": "early", "title": "Early", "kind": "locked", "start": "07:00", "days": [0]},
    ]
    agenda = agenda_for("2026-09-14", "2026-09-14", blocks, {}, None, None)
    assert [row["block"]["id"] for row in agenda["fixed"]] == ["early", "late"]
