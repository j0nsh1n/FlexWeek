"""Clay deck's row of cards on Week, one day in front: which cards are live hours, what the front says,
the dish of homework with no time, and what a refresh or a reveal keeps."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

from desktop.native.hours.zoom import HoursScroll  # noqa: E402
from desktop.native.layouts.clay import ClayChip  # noqa: E402
from desktop.tests.week.support_clay import (  # noqa: E402, F401
    again,
    front,
    shown,
    still,
    visible_scrolls,
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-clay-test"])
    yield application


def test_the_day_in_front_is_the_one_hours_that_scroll_and_zoom_and_its_neighbours_are_live(
    qapp: QApplication,
) -> None:
    view = shown(qapp)
    assert [scroll.objectName() for scroll in visible_scrolls(view)] == ["clayWeekScroll"]
    hours = front(view)
    assert hours.parentWidget() is visible_scrolls(view)[0].viewport()
    assert [(track.day, track.first, track.last) for track in hours.tracks] == [(3, 0, 1440)]
    assert hours.block_rect("essay-1", 3) is not None
    days = [track.day for surface in view.hours_surfaces() for track in surface.tracks]
    assert days == [3, 0, 1, 2, 4, 5, 6]
    assert all(surface.hand is view.hand for surface in view.hours_surfaces())


def test_neighbours_show_the_stretch_the_day_in_front_opened_at_and_stay_still_while_it_scrolls(
    qapp: QApplication,
) -> None:
    """Scrolling the card in front used to scroll its neighbours with it. They keep the stretch the day
    opened at, on the drag's step."""
    view = shown(qapp)
    # Painted once before the student scrolls, as on screen: a paint settling the page late once left
    # the neighbours taking the scrolled stretch after the scroll.
    view.grab()
    qapp.processEvents()
    scroll = visible_scrolls(view)[0]
    track = front(view).tracks[0]
    x = track.area.center().x()
    top = scroll.verticalScrollBar().value()
    first = track.minute_at(QPointF(x, top))
    last = track.minute_at(QPointF(x, top + scroll.viewport().height()))
    step = view.hand.step
    for surface in view.hours_surfaces()[1:]:
        (peek,) = surface.tracks
        assert peek.first % step == 0 and peek.last % step == 0
        assert peek.first <= first < peek.first + step
        assert peek.last - step < last <= peek.last
    held = [(surface.tracks[0].first, surface.tracks[0].last) for surface in view.hours_surfaces()[1:]]
    for value in (top - 120, 0, scroll.verticalScrollBar().maximum()):
        scroll.verticalScrollBar().setValue(value)
        qapp.processEvents()
        qapp.processEvents()
        assert front(view).tracks[0].minute_at(QPointF(x, scroll.verticalScrollBar().value())) != first
        now = [(surface.tracks[0].first, surface.tracks[0].last) for surface in view.hours_surfaces()[1:]]
        assert now == held


def test_the_front_names_its_day_and_how_much_it_holds(qapp: QApplication) -> None:
    view = shown(qapp)
    note = view.findChild(QPushButton, "clayWeekFront").findChild(QLabel, "clayNote")
    assert note.text() == "Today · 4 things"
    view.findChild(QPushButton, "clayAhead").click()
    assert note.text() == "2 things"
    view.findChild(QPushButton, "clayAhead").click()
    assert note.text() == "1 thing"


def test_with_the_days_either_side_hidden_only_the_front_is_hours(qapp: QApplication) -> None:
    view = shown(qapp, peek="hide")
    assert [track.day for surface in view.hours_surfaces() for track in surface.tracks] == [3]
    view.findChild(QPushButton, "clayAhead").click()
    assert [track.day for surface in view.hours_surfaces() for track in surface.tracks] == [4]


def test_the_dish_holds_what_is_not_placed_yet_with_when_it_is_due(qapp: QApplication) -> None:
    view = shown(qapp)
    assert view.findChild(QLabel, "clayTrayLabel").text() == "Not placed yet"
    assert view.findChild(QLabel, "clayDue").text() == "Due Sun 20 Sep"
    assert view.findChild(QLabel, "clayHint").text() == "Drag a chip onto a day."
    chips = view.findChildren(ClayChip)
    assert [chip.block_id for chip in chips] == ["poster-1"]
    assert all(chip.hand is view.hand for chip in chips)


def test_scroll_and_zoom_survive_a_scene_refresh(qapp: QApplication) -> None:
    view = shown(qapp)
    scroll = view.findChild(HoursScroll, "clayWeekScroll")
    scroll.zoom_by(1)
    scroll.verticalScrollBar().setValue(240)
    before = (scroll.px, scroll.verticalScrollBar().value())
    again(qapp, view, minute=view.scene.minute + 15)
    assert view.findChild(HoursScroll, "clayWeekScroll") is scroll
    assert (scroll.px, scroll.verticalScrollBar().value()) == before
    assert front(view).now_min == view.scene.minute


def test_day_and_week_keep_separate_scrolls(qapp: QApplication) -> None:
    view = shown(qapp)
    week_scroll = view.findChild(HoursScroll, "clayWeekScroll")
    week_scene = view.scene
    again(qapp, view, surface="day")
    day_scroll = view.findChild(HoursScroll, "clayDayScroll")
    assert day_scroll is not week_scroll
    assert visible_scrolls(view) == [day_scroll]
    view.show_week(week_scene)
    qapp.processEvents()
    assert visible_scrolls(view) == [week_scroll]


def test_day_names_open_their_day_and_every_day_has_one(qapp: QApplication) -> None:
    view = shown(qapp)
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    names = {item.property("day_target") for item in view.findChildren(QPushButton)} - {None}
    assert names == set(range(7))
    QTest.mouseClick(view.findChild(QPushButton, "clayDay4"), Qt.MouseButton.LeftButton)
    QTest.mouseClick(view.findChild(QPushButton, "clayWeekFront"), Qt.MouseButton.LeftButton)
    week = view.scene.week
    assert opened == [week.date_of(4).isoformat(), week.date_of(3).isoformat()]


def test_a_name_past_the_rows_edge_is_brought_to_the_front_before_it_is_found(qapp: QApplication) -> None:
    view = shown(qapp)
    hours = front(view)
    friday = view.findChild(QPushButton, "clayDay4")
    assert friday.rect().contains(friday.mapFromGlobal(hours.day_name(4)))
    assert view.row.front == 3
    point = hours.day_name(6)
    assert view.row.front == 6
    head = view.findChild(QPushButton, "clayWeekFront")
    assert head.rect().contains(head.mapFromGlobal(point))
    assert view.row.rect().contains(view.row.mapFromGlobal(point))


def test_reveal_brings_a_day_to_the_front_and_its_time_into_view(qapp: QApplication) -> None:
    view = shown(qapp)
    view.hours_surfaces()[-1].reveal(5, 9 * 60, 10 * 60)
    qapp.processEvents()
    assert view.row.front == 5
    hours = front(view)
    assert hours.track_for(5, 9 * 60) is not None
    assert hours.in_view(5, 9 * 60) and hours.in_view(5, 10 * 60)

