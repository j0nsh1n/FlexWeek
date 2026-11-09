# ruff: noqa: F811
"""The Material month's actions: pick a date to open its bar, open that day, move the month, and the
study-time switch. Each asks the session or the shell for the change; none draws anything."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.tests.month.support_month_bridge import (  # noqa: E402, F401
    FakeSession,
    bridge_for,
    deadlines,
    isos,
    snapshot,
    week_start,
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    existing = QApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.fail("Month tests need QApplication; a different Qt application is already running")
    yield existing or QApplication(["flexweek-material-month"])


def test_the_study_switch_starts_off_and_only_changes_the_screen(qapp, week_start) -> None:
    month, _ = bridge_for(FakeSession("2026-11", snapshot("2026-11")))
    assert month.showStudyTime is False
    month.setShowStudyTime(True)
    assert month.showStudyTime is True
    month.setShowStudyTime(False)
    assert month.showStudyTime is False


def test_picking_a_date_opens_its_bar_and_picking_it_again_closes_it(qapp, week_start) -> None:
    session = FakeSession("2026-11", deadlines())
    session.today = "2026-11-04"
    month, _ = bridge_for(session)
    assert month.barOpen is False
    month.selectDate("2026-11-05")
    assert month.barOpen is True
    assert month.selectedIso == "2026-11-05"
    assert month.heading == "Thursday 5 November"
    assert month.lines.rowCount() == 2
    month.selectDate("2026-11-05")
    assert month.barOpen is False
    month.selectDate("2026-11-30")
    month.closeDate()
    assert month.barOpen is False
    month.selectDate("2030-01-01")
    assert month.barOpen is False


def test_an_empty_date_says_nothing_planned(qapp, week_start) -> None:
    month, _ = bridge_for(FakeSession("2026-11", snapshot("2026-11")))
    month.selectDate("2026-11-10")
    assert month.heading == "Tuesday 10 November"
    assert [month.lines.data(month.lines.index(row, 0), 257) for row in range(month.lines.rowCount())] == [
        "Nothing planned"
    ]


def test_open_day_goes_to_that_date_through_the_shell(qapp, week_start) -> None:
    session = FakeSession("2026-11", deadlines())
    month, shell = bridge_for(session)
    month.openDay()
    assert session.calls == [] and shell.pages == []
    month.selectDate("2026-11-05")
    month.openDay()
    assert session.calls == [("open_day", "2026-11-05")]
    assert shell.pages == ["day keeping the date"]


def test_a_date_that_leaves_the_grid_closes_its_bar(qapp, week_start) -> None:
    session = FakeSession("2026-11", deadlines())
    month, _ = bridge_for(session)
    month.selectDate("2026-11-05")
    session.selected_month = "2027-02"
    session.month_data = snapshot("2027-02")
    month.reload()
    assert month.barOpen is False
    assert isos(month.cellRows)[0] == "2027-02-01"


def test_previous_and_next_ask_the_session_to_move_the_month(qapp, week_start) -> None:
    session = FakeSession("2026-11", snapshot("2026-11"))
    month, _ = bridge_for(session)
    month.nextMonth()
    month.previousMonth()
    assert session.calls == [("shift_month", 1), ("shift_month", -1)]
    session.planner_view = "week"
    month.nextMonth()
    assert session.calls[-2:] == [("open_month", None), ("shift_month", 1)]
