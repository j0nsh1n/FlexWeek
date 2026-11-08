"""Which dates the Month grid shows, which one is marked as today, and what it keeps while the next
month is on its way."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.month import build_month  # noqa: E402
from desktop.native import fields  # noqa: E402
from desktop.native.hours.month import LEAST_CHIPS, MonthGrid, month_cells  # noqa: E402
from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.tests.month.support_month import ESSAY, MONDAY, club_day, september  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-dates-test"])


def dates_shown(grid: MonthGrid) -> list[str]:
    return [cell.iso for cell in grid.canvas.cells]


@pytest.mark.parametrize(
    ("month", "first", "last"),
    (("2026-11", "2026-11-01", "2026-12-05"), ("2026-10", "2026-09-27", "2026-10-31")),
)
def test_sunday_month_rows_start_on_sunday_and_end_on_saturday(
    monkeypatch: pytest.MonkeyPatch, tmp_path, month: str, first: str, last: str
) -> None:
    path = tmp_path / "week-start.json"
    path.write_text('{"week_starts_on":"sunday"}', encoding="utf-8")
    monkeypatch.setattr(fields, "_week_starts_file", lambda: path)

    cells = month_cells(build_month(month, [], []), {}, "")

    assert cells[0].iso == first
    assert cells[-1].iso == last
    assert len(cells) % 7 == 0
    assert [date.fromisoformat(cell.iso).weekday() for cell in cells[::7]] == [6] * (len(cells) // 7)
    assert [date.fromisoformat(cell.iso).weekday() for cell in cells[6::7]] == [5] * (len(cells) // 7)


def test_monday_month_rows_keep_the_existing_monday_to_sunday_dates(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    path = tmp_path / "week-start.json"
    path.write_text('{"week_starts_on":"monday"}', encoding="utf-8")
    monkeypatch.setattr(fields, "_week_starts_file", lambda: path)
    cells = month_cells(september(), {}, "")

    assert cells[0].iso == "2026-08-31"
    assert cells[-1].iso == "2026-10-04"


def test_a_six_week_month_shows_its_last_week(qapp: QApplication) -> None:
    # August 2026 starts on a Saturday: 27 July to 6 September, and the 31st is a Monday of week six.
    snapshot = build_month("2026-08", [], [])
    assert len(snapshot["days"]) == 42
    grid = MonthGrid()
    grid.resize(900, 700)
    grid.set_month(snapshot, False)
    grid.show()
    qapp.processEvents()
    assert dates_shown(grid) == [day["date"] for day in snapshot["days"]]
    opened: list[str] = []
    grid.day_activated.connect(opened.append)
    where = grid.canvas.cell_rect(35).center().toPoint()
    QTest.mouseClick(grid.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, where)
    assert opened == []
    assert grid.canvas.selected == "2026-08-31"
    assert grid.pane.heading.text() == "Monday 31 August"
    grid.pane.open.click()
    assert opened == ["2026-08-31"]
    grid.close()


def test_a_four_week_month_leaves_no_rows_from_the_month_before(qapp: QApplication) -> None:
    grid = MonthGrid()
    grid.set_month(build_month("2026-08", [], []), False)
    # February 2027 starts on a Monday and has 28 days: exactly four weeks.
    february = build_month("2027-02", [], [])
    assert len(february["days"]) == 28
    grid.set_month(february, False)
    assert dates_shown(grid) == [day["date"] for day in february["days"]]
    assert grid.canvas.rows() == 4
    grid.close()


def test_the_month_marks_the_today_it_is_given_not_the_clocks(qapp: QApplication) -> None:
    """A preview draws the month for its own day; the clock (Thursday 5 November) is another."""
    grid = MonthGrid()
    grid.set_month(september(), False, "2026-09-16")
    marked = [cell.iso for cell in grid.canvas.cells if cell.today]
    grid.close()
    assert marked == ["2026-09-16"]


def test_loading_month_has_its_final_dates_and_height_before_the_reply(qapp: QApplication) -> None:
    """Switching to Month, it was short with empty space, then grew when the month arrived. While the
    reply is on its way the grid already has every date of the month, at the height the reply gives a
    month with no more chips on a day than a row always has room for."""
    grid = MonthGrid()
    grid.resize(900, 700)
    grid.set_month(None, False, "2026-10-15", "student", "2026-10")
    grid.show()
    qapp.processEvents()
    first_cells = tuple(cell.iso for cell in grid.canvas.cells)
    first_height = grid.canvas.height()
    first_rows = tuple(grid.canvas.cell_rect(row * 7).height() for row in range(5))

    snapshot = build_month("2026-10", [], [])
    club_day(snapshot, "2026-10-15", range(8, 8 + LEAST_CHIPS))
    grid.set_month(snapshot, False, "2026-10-15", "student", "2026-10")
    qapp.processEvents()

    assert len(first_cells) == 35
    assert first_cells == tuple(cell.iso for cell in grid.canvas.cells)
    assert first_height == grid.canvas.height()
    assert first_rows == tuple(grid.canvas.cell_rect(row * 7).height() for row in range(5))
    grid.close()


def test_a_month_on_its_way_keeps_the_last_one_drawn_under_loading_month(qapp: QApplication) -> None:
    """Week to Month flashed an empty grid while the new month was fetched. The grid the student last
    had stays, with "Loading month…", until the new one arrives."""
    grid = MonthGrid()
    grid.set_week(build_week(MONDAY, [ESSAY], {}, None))
    grid.set_month(september(), False, "2026-09-16", "ana")
    kept = dates_shown(grid)
    assert kept and "2026-09-16" in kept
    grid.set_month(None, False, "2026-09-16", "ana")
    assert dates_shown(grid) == kept, "the old grid is still drawn"
    assert grid.warning.text() == "Loading month…" and not grid.warning.isHidden()
    # A change to the open week while it waits redraws the kept grid, not an empty one.
    grid.set_unsaved({})
    assert dates_shown(grid) == kept
    november = build_month("2026-11", [], [])
    grid.set_month(november, False, "2026-09-16", "ana")
    assert grid.canvas.cells and grid.canvas.cells[10].iso in {day["date"] for day in november["days"]}
    assert dates_shown(grid) != kept, "the new month replaces it"
    assert grid.warning.text() == "" and grid.warning.isHidden()
    grid.close()


def test_a_month_never_shows_another_students_grid_while_it_loads(qapp: QApplication) -> None:
    """The kept grid is the same student's: after another one signs in, loading shows nothing."""
    grid = MonthGrid()
    grid.set_week(build_week(MONDAY, [ESSAY], {}, None))
    grid.set_month(september(), False, "2026-09-16", "ana")
    assert grid.canvas.cells
    grid.set_month(None, False, "2026-09-16", "ben")
    assert grid.canvas.cells == []
    assert grid.warning.text() == "Loading month…"
    grid.set_month(september(), False, "2026-09-16", "ana")
    grid.set_month(None, False, "2026-09-16", None)
    assert grid.canvas.cells == [], "with nobody named there is nothing to be sure of"
    grid.close()
