"""The month grid shows every day the API returns, and a student can read what each day holds.

GET /api/month returns whole weeks: the Monday on or before the 1st through the Sunday on or after the
last day. That is 28, 35 or 42 days. The grid was built with five fixed rows, so a six-week month lost
its last week, and rows one line tall cut off what a date held.
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
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from backend.month import build_month
    from desktop.native.hours.month import MonthGrid, more_label


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-month-test"])
    yield application


def dates_shown(grid: MonthGrid) -> list[str]:
    return [cell.iso for cell in grid.canvas.cells]


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


def test_a_four_week_month_leaves_no_rows_from_the_month_before(qapp: QApplication) -> None:
    grid = MonthGrid()
    grid.set_month(build_month("2026-08", [], []), False)
    # February 2027 starts on a Monday and has 28 days: exactly four weeks.
    february = build_month("2027-02", [], [])
    assert len(february["days"]) == 28
    grid.set_month(february, False)
    assert dates_shown(grid) == [day["date"] for day in february["days"]]
    assert grid.canvas.rows() == 4


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
    canvas = grid.canvas
    shown, more = canvas.chip_boxes(15)
    words = [chip.words for chip, _box in shown]
    assert len(shown) == 3
    assert words[:2] == ["Due History essay", "08:00 Club 8"]
    assert more == 4
    assert more_label(more) == "and 4 more"
    assert canvas.cell_rect(15).contains(shown[-1][1]), (
        "the last chip that is shown is wholly inside its date"
    )
