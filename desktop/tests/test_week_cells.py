"""What a calendar cell says. A 15-minute row holds one line, so a block spreads its words over rows.

The port wrote "title, newline, time and labels" into every row. Qt elided that to "School…" and never
drew the second line, so a student could not see a block's time, or that it was missed or done.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from datetime import datetime

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from backend.slots import DAY_START_MIN, SLOT_MIN
    from desktop.native.widgets import WeekTable

WEEK = "2026-09-14"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-cells-test"])
    yield application


def block(**fields: object) -> dict:
    return {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "start": "08:00",
        "duration_min": 60,
        "days": [0],
        **fields,
    }


def column(table: WeekTable, day: int) -> list[str]:
    return [table.item(row, day).text() for row in range(table.rowCount()) if table.item(row, day)]


def test_a_block_says_its_title_then_its_time_and_the_rest_stay_quiet(qapp: QApplication) -> None:
    table = WeekTable()
    table.set_week(WEEK, [block()], None)
    assert column(table, 0) == ["School", "08:00 · Fixed", "", ""]
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item is not None:
            assert "\n" not in item.text(), "a row is one line tall, so a second line is never drawn"
            assert item.toolTip() == "School\n08:00 · Fixed"


def test_missed_and_done_can_be_seen_without_hovering(qapp: QApplication) -> None:
    table = WeekTable()
    missed = block(missed_days=[0])
    done = block(
        id="essay",
        title="Essay",
        kind="flexible",
        start="16:00",
        duration_min=30,
        days=[1, 2],
        completed=True,
        completed_day=1,
    )
    table.set_week(WEEK, [missed, done], None)
    assert column(table, 0)[1] == "08:00 · Fixed · Missed"
    assert column(table, 1) == ["Essay", "16:00 · Work · Done"]
    assert column(table, 2) == [], "finished work sits only on the day it was done"


def test_a_fifteen_minute_block_says_everything_on_its_one_row(qapp: QApplication) -> None:
    table = WeekTable()
    table.set_week(WEEK, [block(id="quiz", title="Quiz", start="09:00", duration_min=15)], None)
    assert column(table, 0) == ["Quiz · 09:00 · Fixed"]


def test_double_clicking_any_row_of_a_block_opens_it_even_a_blank_one(qapp: QApplication) -> None:
    table = WeekTable()
    table.set_week(WEEK, [block()], None)
    opened: list[str] = []
    table.block_activated.connect(opened.append)
    rows = [row for row in range(table.rowCount()) if table.item(row, 0)]
    assert table.item(rows[3], 0).text() == ""
    table._activate(rows[3], 0)
    assert opened == ["school"]


def test_the_current_week_opens_scrolled_to_now_not_dawn(qapp: QApplication) -> None:
    table = WeekTable()
    table.resize(960, 320)
    table.show()
    qapp.processEvents()
    table.set_week(WEEK, [block()], None)
    now = datetime(2026, 9, 17, 13, 40)
    table.reveal(WEEK, int(now.timestamp() * 1000))
    qapp.processEvents()
    now_row = (now.hour * 60 + now.minute - DAY_START_MIN) // SLOT_MIN
    bar = table.verticalScrollBar()
    top = table.rowAt(1)
    bottom = table.rowAt(table.viewport().height() - 1)
    assert bar.value() > 0
    assert top <= now_row <= bottom


def test_blocks_sharing_a_cell_are_named_from_the_blocks_not_from_the_cell(qapp: QApplication) -> None:
    table = WeekTable()
    club = block(id="club", title="Chess club", start="08:30", duration_min=30)
    table.set_week(WEEK, [block(), club], None)
    rows = [row for row in range(table.rowCount()) if table.item(row, 0)]
    shared = table.item(rows[3], 0)
    # School's fourth row is blank, the club's second row is its time: the cell alone cannot name them.
    assert shared.text() == "08:30 · Fixed"
    assert table.block_titles(shared.data(0x0100)) == ["School", "Chess club"]
    assert table.item(rows[2], 0).text() == "Chess club"
