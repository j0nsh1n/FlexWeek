"""Bento's tiles around the week: Not placed yet, Due soon, Next, Homework load, legend and day tiles."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from desktop.native.fonts import load_fonts  # noqa: E402
from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.layouts.bento import DayTile, LoadBars, time_left  # noqa: E402
from desktop.tests.day.support_bento import shown, text, texts  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-bento-tiles-test"])


def test_waiting_homework_is_a_hand_chip_and_due_soon_says_where_each_is(qapp: QApplication) -> None:
    view = shown(qapp)
    chip = view.findChild(TrayChip, "bentoWaiting0")
    assert chip is not None
    assert chip.hand is view.hand
    assert text(view, "bentoWaitingLabel") == "Not placed yet"
    # Soonest due first: Chem due tonight, the essay tomorrow, the poster on Sunday and not placed.
    # Where each is placed says so, and is never read as when it is due, which the figure says.
    assert texts(view, "bentoDueMeta") == [
        "placed Thu 20:00",
        "placed Thu 18:45",
        "Not placed",
    ]
    rows = [view.findChild(QPushButton, f"bentoDue{index}") for index in range(3)]
    assert [row.property("block_id") for row in rows] == ["chem-1", "essay-1", "poster-1"]
    assert text(view, "bentoDuePlaced") == "2 of 3 placed"
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    rows[2].click()
    assert opened == ["poster-1"]


@pytest.mark.parametrize("size", [(1280, 764), (1150, 768)])
def test_every_due_row_says_where_it_is_placed_the_same_way(
    qapp: QApplication, size: tuple[int, int]
) -> None:
    """In the window's face and body size a Due soon row had no room for "1 h 30 · placed Thu 20:00".
    Short of room the rows say where the homework is placed, whole, and say it the same way: all with
    each length, or all without, never one row without its length among rows with theirs. (That the
    tile does not cut the time is the picture week.bento_due_rows.)"""
    load_fonts()
    usual = QFont(qapp.font())
    font = QFont("Inter")
    font.setPointSize(13)
    qapp.setFont(font)
    try:
        view = shown(qapp, size=size)
        metas = [item for item in view.findChildren(QLabel, "bentoDueMeta") if item.isVisible()]
        ends = ("placed Thu 20:00", "placed Thu 18:45", "Not placed")
        assert len(metas) == 3
        assert all(meta.text().endswith(end) for meta, end in zip(metas, ends, strict=True))
        assert len({" · " in meta.text() for meta in metas}) == 1, [meta.text() for meta in metas]
    finally:
        qapp.setFont(usual)


def test_due_soon_counts_down_to_the_first_homework_due(qapp: QApplication) -> None:
    due = shown(qapp).findChild(QWidget, "bentoDue")
    # Chem lab report is due at the end of today, Thursday, and it is 13:40.
    figure = (due.findChild(QLabel, "bentoFigure").text(), due.findChild(QLabel, "bentoDueUntil").text())
    assert figure == ("10 h 20 min", "left · due by the end of today")


def test_due_soon_words_the_time_left_by_how_far_off_it_is() -> None:
    thursday = date(2026, 9, 17)
    assert time_left("2026-09-20T20:00", thursday, 820) == ("3 days", "left · due Sunday 20", False)
    assert time_left("2026-09-18T21:00", thursday, 820) == ("1 day", "left · due Friday 18", False)
    assert time_left("2026-09-17T21:00", thursday, 820) == ("7 h 20 min", "left · due at 21:00", False)
    assert time_left("2026-09-17T12:00", thursday, 820) == ("Past due", "was due at 12:00", True)
    assert time_left("2026-09-16T21:00", thursday, 820) == ("Past due", "was due Wednesday 16", True)


def test_next_says_what_is_on_now_and_the_two_that_follow(qapp: QApplication) -> None:
    view = shown(qapp)
    assert text(view, "bentoNextLabel") == "Now"
    assert text(view, "bentoNextTitle") == "School"
    assert text(view, "bentoNextIn") == "50 min left"
    assert text(view, "bentoNextWhen") == "08:00 · 6 h 30 min"
    then = view.findChild(QLabel, "bentoNextThen").text()
    assert "Dinner at 18:00" in then and "Essay-1 at 18:45" in then and "Chem" not in then
    later = shown(qapp, clock="15:40")
    assert (text(later, "bentoNextLabel"), text(later, "bentoNextTitle")) == ("Next", "Dinner")
    assert text(later, "bentoNextIn") == "in 2 h 20 min"


def test_next_is_left_out_on_a_week_that_is_not_this_one(qapp: QApplication) -> None:
    view = shown(qapp, today=None)
    assert view.findChild(QWidget, "bentoNext") is None
    # With no now, Due soon has nothing to count down from, and still lists what is due.
    assert view.findChild(QLabel, "bentoDueUntil") is None
    assert view.findChild(QPushButton, "bentoDue0").property("block_id") == "chem-1"
    assert text(view, "bentoWaitingLabel") == "Not placed yet"


def test_the_load_tile_charts_the_weeks_homework_by_day(qapp: QApplication) -> None:
    view = shown(qapp)
    labels = [item.text() for item in view.findChild(QWidget, "bentoLoad").findChildren(QLabel)]
    # Monday's finished Math worksheet and Thursday's essay and Chem report, placed; the poster to go.
    assert {"3 h 15 min", "placed, 2h to go"} <= set(labels)
    assert view.findChild(LoadBars, "bentoLoadBars").minutes == [45, 0, 0, 150, 0, 0, 0]


def test_the_legend_names_only_the_categories_the_week_has(qapp: QApplication) -> None:
    view = shown(qapp)
    assert view.findChild(QWidget, "bentoLegend").accessibleName() == "Colours: School, Homework, Meals"


def test_a_day_tile_says_its_first_item_its_load_its_homework_and_what_is_due(qapp: QApplication) -> None:
    view = shown(qapp, hero="today")

    def said(day: int) -> str:
        return view.findChild(DayTile, f"bentoDay{day}").accessibleDescription()

    # Monday: School, the finished Math worksheet and Dinner. Friday: the essay is due. Sunday: the
    # poster is due and only Dinner is planned.
    assert said(0) == "Monday 14, first School at 08:00, 45 min planned, 1 homework"
    assert said(4) == "Friday 18, first School at 08:00, Nothing planned, 1 due"
    assert said(6) == "Sunday 20, first Dinner at 18:00, Nothing planned, 1 due"
