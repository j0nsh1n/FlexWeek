"""Where Month opens, and when it scrolls: on its first row, and either scrolling or fitting its five
weeks into the view when panels above take the room."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.month import build_month  # noqa: E402
from desktop.native.hours.month import MonthGrid  # noqa: E402
from desktop.tests.month.support_month import club_day, september  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-scroll-test"])


def first_row_shown(grid: MonthGrid) -> int:
    """The row at the top of the view: the one whose top the scroll bar stands at, or -1."""
    canvas, value = grid.canvas, grid.scroll.verticalScrollBar().value()
    return next((row for row in range(canvas.rows()) if round(canvas.cell_rect(row * 7).top()) == value), -1)


def opens_on_its_first_row(grid: MonthGrid) -> bool:
    """The first row is at the top and the canvas is tall enough that nothing is cut off below."""
    below = grid.canvas.height() - grid.scroll.verticalScrollBar().value()
    return first_row_shown(grid) == 0 and below >= grid.scroll.viewport().height()


def test_month_opens_on_its_first_row_wherever_this_week_sits(qapp: QApplication) -> None:
    grid = MonthGrid()
    grid.resize(900, 700)
    grid.set_month(september(), False, "2026-09-16")
    grid.show()
    qapp.processEvents()
    canvas = grid.canvas
    assert canvas.rows() * canvas.least_row() < grid.scroll.viewport().height(), (
        "the whole month fits, as on a laptop"
    )
    for iso in ("2026-09-03", "2026-09-24", "2026-09-30"):
        grid.reveal(iso)
        wait_until(
            qapp,
            lambda iso=iso: opens_on_its_first_row(grid) and canvas.selected == iso,
            what=lambda iso=iso: f"{iso}: row {first_row_shown(grid)}, selected {canvas.selected}",
        )
    grid.close()


def test_a_month_revealed_before_its_first_layout_still_opens_on_the_first_row(qapp: QApplication) -> None:
    """The window asks as the month is switched to, before it has a height of its own."""
    grid = MonthGrid()
    grid.resize(900, 700)
    grid.set_month(september(), False)
    grid.reveal("2026-09-24")
    grid.show()
    wait_until(qapp, lambda: opens_on_its_first_row(grid), what=lambda: f"row {first_row_shown(grid)}")
    grid.close()


def busy_september() -> dict:
    """September with a quiet week, a date with one chip and a date with five."""
    snapshot = build_month("2026-09", [], [])
    club_day(snapshot, "2026-09-16", range(8, 13))
    solo = next(day for day in snapshot["days"] if day["date"] == "2026-09-09")
    solo["blocks"] = [{"id": "solo", "title": "Piano", "start": "17:00", "duration_min": 60}]
    return snapshot


def tight_grid(qapp: QApplication, height: int, tight: bool) -> MonthGrid:
    grid = MonthGrid()
    grid.resize(1024, height)
    grid.set_tight(tight)
    grid.set_month(busy_september(), False, "2026-09-16")
    grid.show()
    qapp.processEvents()
    return grid


def test_with_panels_open_every_week_fits_the_view_and_a_date_still_shows_a_chip(qapp: QApplication) -> None:
    """At 1024 x 640 the plan and Unfinished panels left Month about 300 px, so its last row was half
    cut and a scroll bar came. Tight, the five rows share the view with no scroll bar; each date
    keeps a chip and counts the rest."""
    grid = tight_grid(qapp, 360, True)
    canvas = grid.canvas
    assert canvas.rows() == 5
    assert grid.scroll.verticalScrollBar().maximum() == 0, "no scroll bar"
    shown, more = canvas.chip_boxes(canvas.index_of("2026-09-09"))
    assert [chip.words for chip, _box in shown] == ["17:00 Piano"] and more == 0
    shown, more = canvas.chip_boxes(canvas.index_of("2026-09-16"))
    assert len(shown) == 1 and more == 4, "a busy date shows one chip and counts the rest"
    grid.close()


def test_a_row_with_one_line_keeps_its_chip_and_counts_the_rest(qapp: QApplication) -> None:
    grid = tight_grid(qapp, 360, True)
    canvas = grid.canvas
    overhead = grid.height() - grid.scroll.viewport().height()
    grid.resize(1024, 5 * canvas.tight_row() + overhead + 2)
    qapp.processEvents()
    shown, more = canvas.chip_boxes(canvas.index_of("2026-09-16"))
    assert len(shown) == 1 and more == 4
    grid.close()


def test_without_panels_the_month_still_scrolls_rather_than_squeezing(qapp: QApplication) -> None:
    """The same view that fits when tight scrolls when nothing is open."""
    grid = tight_grid(qapp, 360, False)
    assert grid.scroll.verticalScrollBar().maximum() > 0
    grid.close()


def test_a_view_too_short_for_the_tight_rows_scrolls_as_before(qapp: QApplication) -> None:
    grid = tight_grid(qapp, 180, True)
    assert grid.scroll.verticalScrollBar().maximum() > 0
    grid.close()
