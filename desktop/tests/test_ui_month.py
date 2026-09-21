"""The month grid shows every day the API returns, and a student can read what each day holds.

GET /api/month returns whole weeks: the Monday on or before the 1st through the Sunday on or after the
last day. That is 28, 35 or 42 days. The grid was built with five fixed rows, so a six-week month lost
its last week, and rows one line tall showed "14…" where the counts should be.
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
    from PySide6.QtWidgets import QApplication

    from backend.month import build_month
    from desktop.native.widgets import CHIP_ROLE, MonthGrid


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-month-test"])
    yield application


def dates_shown(grid: MonthGrid) -> list[str]:
    table = grid.table
    found = []
    for row in range(table.rowCount()):
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item is not None and item.data(Qt.ItemDataRole.UserRole):
                found.append(item.data(Qt.ItemDataRole.UserRole))
    return found


def test_a_six_week_month_shows_its_last_week(qapp: QApplication) -> None:
    # August 2026 starts on a Saturday: 27 July to 6 September, and the 31st is a Monday of week six.
    snapshot = build_month("2026-08", [], [])
    assert len(snapshot["days"]) == 42
    grid = MonthGrid()
    grid.set_month(snapshot, False)
    assert dates_shown(grid) == [day["date"] for day in snapshot["days"]]
    opened: list[str] = []
    grid.day_activated.connect(opened.append)
    grid.table.cellClicked.emit(5, 0)
    assert opened == ["2026-08-31"]


def test_a_four_week_month_leaves_no_rows_from_the_month_before(qapp: QApplication) -> None:
    grid = MonthGrid()
    grid.set_month(build_month("2026-08", [], []), False)
    # February 2027 starts on a Monday and has 28 days: exactly four weeks.
    february = build_month("2027-02", [], [])
    assert len(february["days"]) == 28
    grid.set_month(february, False)
    assert dates_shown(grid) == [day["date"] for day in february["days"]]
    assert grid.table.rowCount() == 4


def test_every_line_of_a_day_fits_in_its_row(qapp: QApplication) -> None:
    snapshot = build_month("2026-08", [], [])
    busy = snapshot["days"][15]
    busy.update(due_ids=["essay"], session_count=2, locked_count=1)
    snapshot["deadlines"] = [{"id": "essay", "title": "History essay", "category": "assignments"}]
    grid = MonthGrid()
    # About the space the month gets inside the default 1280 x 800 window.
    grid.resize(1240, 420)
    grid.set_month(snapshot, False)
    grid.show()
    qapp.processEvents()
    table = grid.table
    item = table.item(2, 1)
    assert item.text() == busy["date"][-2:].lstrip("0")
    assert item.data(CHIP_ROLE)[0][0] == "History essay"
    line = table.fontMetrics().lineSpacing()
    for row in range(table.rowCount()):
        for column in range(table.columnCount()):
            lines = len(table.item(row, column).text().splitlines())
            assert table.rowHeight(row) >= lines * line, f"row {row} cuts off {lines} lines"
