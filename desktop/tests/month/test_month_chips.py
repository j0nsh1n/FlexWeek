"""What a date on Month lists: homework due first, then its blocks at their times; the words on
each chip; and how many chips a busy date shows before it says "and N more"."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.month import build_month  # noqa: E402
from desktop.native.hours.month import MOST_CHIPS, MonthChip, MonthGrid, month_cells, more_label  # noqa: E402
from desktop.native.tokens import text_knob, type_pt  # noqa: E402
from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.tests.month.support_month import (  # noqa: E402
    ESSAY,
    MONDAY,
    SCHOOL,
    club_day,
    september,
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-chips-test"])


def test_a_date_lists_what_is_due_then_its_blocks_at_their_times() -> None:
    """The open week comes from what the student has now, saved or not; other weeks come from what
    the month reply says is on each date."""
    snapshot = september()
    next_monday = next(day for day in snapshot["days"] if day["date"] == "2026-09-28")
    next_monday["blocks"] = [
        {"id": "piano", "title": "Piano", "start": "18:00", "duration_min": 45, "category": "extra"},
        {"id": "run", "title": "Run", "start": "07:00", "duration_min": 30, "category": "exercise"},
    ]
    unsaved = {**ESSAY, "start": "20:15"}
    week = build_week(MONDAY, [unsaved, SCHOOL], {}, None)
    cells = {cell.iso: cell for cell in month_cells(snapshot, {MONDAY: week}, "")}
    assert [chip.words for chip in cells["2026-09-24"].chips] == ["08:00 School", "20:15 History essay"]
    assert [chip.words for chip in cells["2026-09-27"].chips] == ["Due History essay"]
    assert [chip.words for chip in cells["2026-09-28"].chips] == ["07:00 Run", "18:00 Piano"]
    assert [chip.words for chip in cells["2026-09-29"].chips] == ["Due 09:00 French oral"]
    assert [chip.carried for chip in cells["2026-09-29"].chips] == [False], "a deadline is not carried"


def test_a_week_left_unsaved_is_drawn_as_the_student_has_it() -> None:
    """A week the student changed and left without saving is drawn from those changes, as the open
    week is; a week with none still comes from the month reply."""
    snapshot = september()
    replied = {
        "2026-10-01": [{"id": "essay-1", "title": "History essay", "start": "19:00", "duration_min": 60}],
        "2026-09-24": [{"id": "essay-1", "title": "History essay", "start": "19:00", "duration_min": 60}],
        "2026-09-17": [{"id": "piano", "title": "Piano", "start": "18:00", "duration_min": 45}],
    }
    for day in snapshot["days"]:
        day["blocks"] = replied.get(day["date"], [])
    open_week = build_week(MONDAY, [ESSAY], {}, None)
    left = build_week("2026-09-28", [{**ESSAY, "start": "20:15"}], {}, None)
    cells = {cell.iso: cell for cell in month_cells(snapshot, {MONDAY: open_week, "2026-09-28": left}, "")}
    assert [chip.words for chip in cells["2026-10-01"].chips] == ["20:15 History essay"]
    assert [chip.words for chip in cells["2026-09-24"].chips] == ["19:00 History essay"]
    assert [chip.words for chip in cells["2026-09-17"].chips] == ["18:00 Piano"]


def test_the_grid_draws_the_open_week_and_the_weeks_left_unsaved(qapp: QApplication) -> None:
    snapshot = september()
    for day in snapshot["days"]:
        if day["date"] == "2026-10-01":
            day["blocks"] = [
                {"id": "essay-1", "title": "History essay", "start": "19:00", "duration_min": 60}
            ]
    grid = MonthGrid()
    grid.set_week(build_week(MONDAY, [ESSAY], {}, None))
    grid.set_month(snapshot, True)
    assert grid.canvas.chip_words("essay-1", "2026-10-01") == "19:00 History essay"
    grid.set_unsaved({"2026-09-28": build_week("2026-09-28", [{**ESSAY, "start": "20:15"}], {}, None)})
    assert grid.canvas.chip_words("essay-1", "2026-10-01") == "20:15 History essay"
    assert grid.canvas.chip_words("essay-1", "2026-09-24") == "19:00 History essay"
    grid.close()


def test_a_deadline_says_overdue_in_words_once_its_date_has_gone() -> None:
    """A deadline is a chip led by "Due" or "Overdue"; it is late only on a date before today and
    only while the homework is not done."""
    cells = {cell.iso: cell for cell in month_cells(september(), {}, "2026-09-28")}
    gone, coming = cells["2026-09-27"].chips[0], cells["2026-09-29"].chips[0]
    assert (gone.late, coming.late) == (True, False)
    assert (gone.flag, coming.flag) == ("Overdue", "Due 09:00")
    assert "Overdue" in gone.words


def test_a_finished_deadline_on_a_gone_date_is_not_overdue() -> None:
    snapshot = september()
    snapshot["deadlines"][0]["completed"] = True
    cells = {cell.iso: cell for cell in month_cells(snapshot, {}, "2026-09-28")}
    chip = cells["2026-09-27"].chips[0]
    assert chip.late is False and chip.flag == "Due"


def test_a_month_block_names_its_carried_history() -> None:
    chip = MonthChip(
        "block:bio", "Bio reading", "assignments", block_id="bio", start=14 * 60 + 30,
        history="Left from last week",
    )
    assert chip.words == "Left from last week 14:30 Bio reading"


def test_a_busy_date_shows_its_chips_and_says_how_many_more_there_are(qapp: QApplication) -> None:
    """A date shows at most three chips; the rest are "and N more" and live in the date pane."""
    snapshot = build_month("2026-08", [], [])
    busy = snapshot["days"][15]
    busy.update(due_ids=["essay"])
    busy["blocks"] = [
        {"id": f"b{hour}", "title": f"Club {hour}", "start": f"{hour:02d}:00", "duration_min": 60}
        for hour in range(8, 14)
    ]
    snapshot["deadlines"] = [{"id": "essay", "title": "History essay", "category": "assignments"}]
    grid = MonthGrid()
    # About the space the month gets inside the default 1280 x 800 window.
    grid.resize(1240, 420)
    grid.set_month(snapshot, False, "2026-08-01")
    grid.show()
    qapp.processEvents()
    shown, more = grid.canvas.chip_boxes(15)
    words = [chip.words for chip, _box in shown]
    assert len(shown) == 3
    assert words[:2] == ["Due History essay", "08:00 Club 8"]
    assert more == 4
    assert more_label(more) == "and 4 more"
    grid.close()


def test_a_weeks_busiest_date_shows_three_chips_and_counts_the_rest(qapp: QApplication) -> None:
    """A week's row grows with its busiest date, up to three chips; the rest are counted."""
    snapshot = build_month("2026-09", [], [])
    club_day(snapshot, "2026-09-16", range(8, 17))
    grid = MonthGrid()
    grid.resize(900, 300)
    grid.set_month(snapshot, False)
    grid.canvas.set_cells(month_cells(snapshot, {}, "2026-09-16"))
    grid.show()
    qapp.processEvents()
    shown, more = grid.canvas.chip_boxes(16)
    assert (len(shown), more) == (MOST_CHIPS, 9 - MOST_CHIPS)
    grid.close()


def test_month_chip_keeps_its_time_and_elides_its_title_on_a_one_line_row(qapp: QApplication) -> None:
    snapshot = build_month("2026-08", [], [])
    snapshot["days"][0]["blocks"] = [
        {"id": "timed", "title": "An assignment name that is too long", "start": "08:00",
         "duration_min": 30}
    ]
    grid = MonthGrid()
    grid.resize(900, 700)
    grid.set_month(snapshot, False, "2026-08-01")
    grid.show()
    qapp.processEvents()
    chip, _box = grid.canvas.chip_boxes(0)[0][0]
    shown = grid.canvas.painter.chip_title(chip, 92, grid.canvas._small())
    assert chip.start == 8 * 60
    assert shown.endswith("…")
    assert len(shown) < len(chip.title)
    grid.close()


def test_a_chip_at_large_text_keeps_its_time_and_whole_words(qapp: QApplication) -> None:
    """At Large text a chip takes two lines, so its words are kept whole rather than elided."""
    grid = MonthGrid()
    font = QFont(grid.canvas.font())
    font.setPointSizeF(type_pt("body", "large"))
    grid.canvas.setFont(font)
    grid.resize(1280, 700)
    snapshot = september()
    for day in snapshot["days"]:
        if day["date"] == "2026-09-10":
            day["blocks"] = [
                {"id": "read", "title": "History essay reading", "start": "08:00", "duration_min": 60}
            ]
    grid.set_month(snapshot, False, "2026-09-10")
    grid.show()
    qapp.processEvents()
    assert text_knob(grid.canvas.font().pointSizeF()) == "large"
    assert grid.canvas._chip_lines() == 2
    assert grid.canvas.chip_words("read", "2026-09-10") == "08:00 History essay reading"
    grid.close()
