"""Mission control's day: one lane of the chosen date with that day's list, what is still to come today
and the free time left, and the cards that say what they leave out."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

import shiboken6  # noqa: E402
from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget  # noqa: E402

from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.hours.geometry import Axis  # noqa: E402
from desktop.native.layouts.base import Scene  # noqa: E402
from desktop.native.layouts.mission import MissionCanvas, MissionView  # noqa: E402
from desktop.native.layouts.registry import options_for, tokens_for  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.weekmodel import build_week, minute_of  # noqa: E402
from desktop.native.widgets import FittedLabel  # noqa: E402
from desktop.tests.day.support_mission import BLOCKS, block, shown, words  # noqa: E402
from desktop.tests.test_weekmodel import HOMEWORK, TRACE, WEEK  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-mission-day-test"])


def busy_thursday(qapp: QApplication, height: int):
    """Thursday at 15:40 with six things still to come and five stretches of free time left."""
    extra = [
        block("soccer", "locked", [1, 3], "16:00", 90, title="Soccer practice", category="exercise"),
        block("piano", "locked", [3], "19:00", 30, title="Piano", category="extra"),
        block("walk", "locked", [3], "21:00", 30, title="Walk", category="exercise"),
    ]
    return shown(qapp, surface="day", iso_day="2026-09-17", minute="15:40", size=(1280, height),
                 blocks=[*BLOCKS, *extra])


def test_day_is_one_lane_of_the_chosen_date_with_that_days_list(qapp: QApplication) -> None:
    view = shown(qapp, surface="day", iso_day="2026-09-18")
    hours = view.findChild(MissionCanvas, "missionHours")
    assert [(track.day, track.axis) for track in hours.tracks] == [(4, Axis.ACROSS)]
    assert view.findChild(QPushButton, "missionDay4").title.text() == "Fri"
    listed = view.findChild(QFrame, "missionDayList")
    assert listed.findChild(QLabel, "missionLabel").text() == "Friday"
    assert [name.full_text() for name in listed.findChildren(FittedLabel, "missionRowTitle")] == [
        "School",
        "Dinner",
    ]
    # What is still to come is today's alone.
    assert view.findChild(QFrame, "missionUpNext") is None
    assert view.findChild(QFrame, "missionFreeTime") is None


def test_day_says_what_is_still_to_come_today_and_the_free_time_left(qapp: QApplication) -> None:
    view = shown(qapp, surface="day", iso_day="2026-09-17")
    coming = view.findChild(QFrame, "missionUpNext")
    assert words(coming.findChild(QLabel, "missionMuted")) == "3 more today"
    assert [
        (when.text(), name.full_text(), wait.text())
        for when, name, wait in zip(
            coming.findChildren(QLabel, "missionWhen"),
            coming.findChildren(FittedLabel, "missionRowTitle"),
            coming.findChildren(QLabel, "missionIn"),
            strict=True,
        )
    ] == [
        ("18:00", "Dinner", "in 4 h 20 min"),
        ("18:45", "Essay-1", "in 5 h 5 min"),
        ("20:00", "Chem-1", "in 6 h 20 min"),
    ]
    assert words(coming.findChild(QLabel, "missionFoot")) == "Then Friday: School at 08:00."
    free = view.findChild(QFrame, "missionFreeTime")
    assert words(free.findChild(QLabel, "missionMuted")) == "4:30 until 22:00"
    assert [
        (when.text(), length.text())
        for when, length in zip(
            free.findChildren(QLabel, "missionWhen"), free.findChildren(QLabel, "missionFigure"), strict=True
        )
    ] == [("14:30–18:00", "3:30"), ("18:30–18:45", "0:15"), ("19:45–20:00", "0:15"), ("21:30–22:00", "0:30")]
    assert words(free.findChild(QLabel, "missionFoot")) == "Room for Poster-1, 2:00, before 22:00."


def test_up_next_counts_everything_still_to_come_in_the_order_it_comes(qapp: QApplication) -> None:
    """At 15:40 four things are still to come on Thursday. Its head counts all four, however many rows
    the card has room to show. (That it shows only whole rows is the picture day.mission_day_cards.)"""
    soccer = block("soccer", "locked", [1, 3], "16:00", 90, title="Soccer practice", category="exercise")
    view = shown(qapp, surface="day", iso_day="2026-09-17", minute="15:40", size=(1280, 744),
                 blocks=[*BLOCKS, soccer])
    coming = view.findChild(QFrame, "missionUpNext")
    assert words(coming.findChild(QLabel, "missionMuted")) == "4 more today"
    rows = coming.findChildren(QFrame, "missionListRow")
    titles = [row.findChild(FittedLabel, "missionRowTitle").full_text() for row in rows]
    assert titles == ["Soccer practice", "Dinner", "Essay-1", "Chem-1"]


def test_a_card_that_leaves_rows_out_ends_with_and_n_more_that_counts_the_row_it_replaces(
    qapp: QApplication,
) -> None:
    """At 1280 by 800 Up next has six rows and Free time left five, and not all fit. Each shows whole
    rows, then an "and N more" where the next row would be, N counting the row it replaces, so what
    shows and what is left out add up to the head's count."""
    view = busy_thursday(qapp, 800)
    for card_name, total in (("missionUpNext", 6), ("missionFreeTime", 5)):
        card = view.findChild(QFrame, card_name)
        rows = [row for row in card.findChildren(QFrame, "missionListRow") if row.isVisibleTo(card)]
        more = card.findChild(QLabel, "missionMore")
        assert more.isVisibleTo(card), f"{card_name} does not say what it leaves out"
        left = int(re.fullmatch(r"and (\d+) more", more.text()).group(1))
        assert len(rows) + left == total
        assert all(row.property("last") is False for row in rows)


def test_a_card_whose_rows_all_fit_has_no_more_row(qapp: QApplication) -> None:
    view = busy_thursday(qapp, 1100)
    for card_name, total in (("missionUpNext", 6), ("missionFreeTime", 5)):
        card = view.findChild(QFrame, card_name)
        rows = [row for row in card.findChildren(QFrame, "missionListRow") if row.isVisibleTo(card)]
        assert len(rows) == total
        assert not card.findChild(QLabel, "missionMore").isVisibleTo(card)
        assert [row.property("last") for row in rows] == [False] * (total - 1) + [True]


def test_late_in_the_day_the_free_time_says_when_what_waits_will_not_fit(qapp: QApplication) -> None:
    view = shown(qapp, surface="day", iso_day="2026-09-17", minute="20:30")
    free = view.findChild(QFrame, "missionFreeTime")
    assert [when.text() for when in free.findChildren(QLabel, "missionWhen")] == ["21:30–22:00"]
    said = words(free.findChild(QLabel, "missionFoot"))
    assert said == "Poster-1 needs 2:00, more than is free before 22:00."
    coming = view.findChild(QFrame, "missionUpNext")
    assert coming.findChildren(QLabel, "missionWhen") == []
    assert coming.findChild(QLabel, "missionHint").text() == "Nothing else scheduled today."


def test_a_waiting_row_click_opens_homework(qapp: QApplication) -> None:
    view = shown(qapp, surface="day")
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    chip = view.findChild(TrayChip, "missionWaiting0")
    QTest.mouseClick(chip, Qt.MouseButton.LeftButton)
    assert opened == [chip.block_id] == ["poster-1"]


def test_parked_day_scroll_dies_with_its_host(qapp: QApplication) -> None:
    options = options_for(None, "mission")
    palette = resolved_palette("light-frost", False, None, "default")
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    scene = Scene(week, 3, minute_of("13:40"), options,
                  tokens_for("mission", options["look"], palette))
    host = QWidget()
    view = MissionView(host)
    QVBoxLayout(host).addWidget(view)
    view.show_week(scene)
    host.show()
    qapp.processEvents()
    view.show_week(replace(scene, surface="day", iso_day="2026-09-18"))
    parked = view._scrolls["day"]
    view.show_week(scene)
    assert shiboken6.isValid(parked)

    host.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(parked)
