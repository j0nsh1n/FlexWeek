"""Clay's Day card and Week fan use the shared, live hours canvas."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QPushButton

    from desktop.native.hours.canvas import HoursCanvas
    from desktop.native.hours.chips import TrayChip
    from desktop.native.hours.zoom import HoursScroll
    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.clay import ClayDeckView
    from desktop.native.layouts.registry import options_for, tokens_for
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week, minute_of


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-clay-test"])
    yield application


def shown(qapp: QApplication, *, tab: str = "week", **chosen: str) -> ClayDeckView:
    options = {**options_for(None, "clay"), **chosen}
    palette = resolved_palette("light-frost", False, None, "default")
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    view = ClayDeckView()
    view.resize(1150, 768)
    view.show_week(Scene(
        week, 3, minute_of("13:40"), options,
        tokens_for("clay", options["colour"], palette),
        surface=tab, iso_day=week.date_of(3).isoformat(),
    ))
    view.show()
    qapp.processEvents()
    return view


def canvas(view: ClayDeckView) -> HoursCanvas:
    found = view.hours_surfaces()
    assert len(found) == 1
    assert isinstance(found[0], HoursCanvas)
    return found[0]


def test_day_is_one_full_day_card_with_a_live_dish(qapp: QApplication) -> None:
    view = shown(qapp, tab="day")
    hours = canvas(view)
    assert [(track.day, track.first, track.last, track.turn) for track in hours.tracks] == [
        (3, 0, 1440, 0.0)
    ]
    assert hours.block_rect("school", 3) is not None
    waiting = view.findChildren(TrayChip)
    assert {chip.held.title for chip in waiting} == {"Poster-1"}
    assert all(chip.hand is view.hand for chip in waiting)
    assert view.uses_drawer is False


def test_week_is_seven_tilted_live_cards(qapp: QApplication) -> None:
    view = shown(qapp)
    hours = canvas(view)
    assert [track.day for track in hours.tracks] == list(range(7))
    assert [track.turn for track in hours.tracks] == [-8, -5, -2, 0, 2, 5, 8]
    assert all(track.first == 0 and track.last == 1440 for track in hours.tracks)
    assert hours.block_rect("school", 3) is not None
    for track in hours.tracks:
        for minute in range(0, 1440, 15):
            target = hours.track_at(track.point_for(minute + 7))
            assert target is not None and target.day == track.day, (track.day, minute)
    assert len(view.findChildren(TrayChip)) == 1


def test_day_names_open_their_day_and_remain_visible(qapp: QApplication) -> None:
    view = shown(qapp)
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    hours = canvas(view)
    for day in range(7):
        name = view.findChild(QPushButton, f"clayDay{day}")
        assert name is not None and name.isVisible()
        assert name.rect().contains(name.mapFromGlobal(hours.day_name(day)))
    QTest.mouseClick(view.findChild(QPushButton, "clayDay4"), Qt.MouseButton.LeftButton)
    assert opened == [view.scene.week.date_of(4).isoformat()]


def test_straight_option_is_table_hand(qapp: QApplication) -> None:
    hours = canvas(shown(qapp, tilt="off"))
    assert len(hours.tracks) == 7
    assert all(track.turn == 0 for track in hours.tracks)


def test_scroll_and_zoom_survive_a_scene_refresh(qapp: QApplication) -> None:
    view = shown(qapp)
    scroll = view.findChild(HoursScroll, "clayWeekScroll")
    scroll.zoom_by(1)
    scroll.verticalScrollBar().setValue(240)
    before = (scroll.px, scroll.verticalScrollBar().value())
    previous = view.scene
    view.show_week(Scene(
        previous.week, previous.today, previous.minute + 15, previous.options,
        previous.tokens, surface="week", iso_day=previous.iso_day,
    ))
    qapp.processEvents()
    assert view.findChild(HoursScroll, "clayWeekScroll") is scroll
    assert (scroll.px, scroll.verticalScrollBar().value()) == before
    assert canvas(view).now_min == previous.minute + 15


def test_day_and_week_keep_separate_scrolls(qapp: QApplication) -> None:
    view = shown(qapp)
    week_scroll = view.findChild(HoursScroll, "clayWeekScroll")
    previous = view.scene
    view.show_week(Scene(
        previous.week, previous.today, previous.minute, previous.options,
        previous.tokens, surface="day", iso_day=previous.iso_day,
    ))
    qapp.processEvents()
    day_scroll = view.findChild(HoursScroll, "clayDayScroll")
    assert day_scroll is not week_scroll
    assert canvas(view).tracks[0].day == 3
    view.show_week(previous)
    qapp.processEvents()
    assert view.findChild(HoursScroll, "clayWeekScroll") is week_scroll
