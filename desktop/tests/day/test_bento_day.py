"""Bento's day: one live full-day track on the shared hand, the day's summary and free time beside it,
and the day tiles that open a day."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from desktop.native.hours import canvas as canvas_module  # noqa: E402
from desktop.native.hours.hand import Hand, Verdict  # noqa: E402
from desktop.native.layouts.bento import BentoView, DayTile, free_slots  # noqa: E402
from desktop.native.weekmodel import build_week, minute_of  # noqa: E402
from desktop.tests.day.support_bento import hours, scene, shown, text, texts  # noqa: E402
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-bento-day-test"])


def test_day_hero_is_one_live_full_day_track_with_window_hand(qapp: QApplication) -> None:
    host = QWidget()
    hand = Hand(lambda *_: Verdict(True, ""), host)
    view = BentoView(hand=hand)
    view.resize(1150, 768)
    view.show_week(scene("day"))
    view.show()
    qapp.processEvents()
    canvas = hours(view)
    assert view.hand is hand
    assert [(track.day, track.first, track.last) for track in canvas.tracks] == [(3, 0, 1440)]
    assert canvas.hand is hand
    assert text(view, "bentoHeroTitle") == "Today"


@pytest.mark.parametrize("hero", ["week", "today"])
def test_the_day_draws_no_add_of_its_own(qapp: QApplication, hero: str) -> None:
    """The top bar has Add in every design (decision 11 of 0.17)."""
    view = shown(qapp, "day", hero=hero)
    assert not [item.objectName() for item in view.findChildren(QPushButton) if "Add" in item.objectName()]


def test_the_day_lists_what_waits_and_says_how_to_place_it(qapp: QApplication) -> None:
    day = shown(qapp, "day")
    assert day.findChild(QPushButton, "bentoDue0") is not None
    assert text(day, "bentoWaitingHint") == "Drag one onto your day."


def test_day_puts_the_days_summary_and_its_free_time_beside_its_hours(qapp: QApplication) -> None:
    view = shown(qapp, "day", clock="15:40")
    # School 6 h 30 min, Dinner 30 min, the essay 1 h and the Chem report 1 h 30 min.
    assert text(view, "bentoSumPlanned") == "2 h 30 min planned"
    # In the legend's order, the category's order in the app.
    assert texts(view, "bentoSumRowName") == ["School", "Homework", "Meals"]
    assert text(view, "bentoFreeLabel") == "Free from now"
    assert texts(view, "bentoFreeRowName") == ["15:40–18:00", "21:30–22:00"]
    friday = shown(qapp, "day", iso_day="2026-09-18")
    assert text(friday, "bentoHeroTitle") == "Friday 18"
    assert text(friday, "bentoFreeLabel") == "Free time"
    assert friday.findChild(QWidget, "bentoNext") is not None, "the tiles stay on Day"


def test_bento_says_nothing_free_now_after_the_last_study_hour(qapp: QApplication) -> None:
    view = shown(qapp, "day", clock="22:49")
    assert text(view, "bentoFreeNone") == "Nothing free now"


def test_free_time_runs_from_the_first_block_to_ten_and_from_now_on_today() -> None:
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    thursday = week.on_day(3)
    # School to 14:30, Dinner 18:00, the essay 18:45 to 19:45, Chem 20:00 to 21:30: the quarter hours
    # between them are too short to list.
    assert free_slots(thursday, None) == [(870, 1080), (1290, 1320)]
    assert free_slots(thursday, minute_of("15:40")) == [(940, 1080), (1290, 1320)]
    assert free_slots((), None) == [(480, 1320)]


def test_a_half_hour_block_says_its_range_on_the_day(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dinner is half an hour. A block always shows its range; the title is what gets cut."""
    written: list[str] = []
    real = canvas_module._paint_layout

    def spy(painter, lay, *rest, **kwargs) -> None:
        written.extend(line.text for line in lay)
        real(painter, lay, *rest, **kwargs)

    monkeypatch.setattr(canvas_module, "_paint_layout", spy)
    hours(shown(qapp, "day"), "bentoDayHours").grab()
    assert "18:00–18:30" in written, written


def test_a_day_tile_on_day_opens_that_day(qapp: QApplication) -> None:
    view = shown(qapp, "day", hero="today")
    assert [track.day for track in hours(view).tracks] == [3]
    assert view.findChild(QLabel, "bentoSumPlanned") is not None
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    view.findChild(DayTile, "bentoDay4").click()
    assert opened == ["2026-09-18"]
