"""Today's app's week scrolls a full day at a height where an hour still has edges."""

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
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QWidget

    from desktop.native.hours.canvas import EDGE_PX, BlockPainter, HoursCanvas
    from desktop.native.hours.classic import WEEK_HOUR_PX, ClassicWeek
    from desktop.native.hours.geometry import FIRST, LAST, LinearTrack
    from desktop.native.hours.hand import Hand, Verdict
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-classic-hours-test"])


def week_view(qapp: QApplication) -> ClassicWeek:
    view = ClassicWeek(Hand(lambda block_id, from_day, span: Verdict(True, ""), QWidget()))
    view.set_look(None, resolved_palette("system", False, None))
    view.set_week(build_week("2026-09-21", [], {}, None), 3, 15 * 60 + 40)
    view.resize(980, 500)
    view.show()
    qapp.processEvents()
    view.hours.relayout()
    qapp.processEvents()
    return view


def test_an_hour_on_the_week_is_tall_enough_to_resize(qapp: QApplication) -> None:
    view = week_view(qapp)
    track = view.hours.track_for(3)
    assert track is not None
    hour = track.rect_for(19 * 60, 20 * 60).height()
    assert hour >= 2 * EDGE_PX + 6, f"a 60-minute block is {hour} px; the pointer would only move it"
    assert abs(track.per_minute() * 60 - WEEK_HOUR_PX) < 1


def test_midnight_and_the_end_of_the_day_can_be_scrolled_onto_the_week(qapp: QApplication) -> None:
    view = week_view(qapp)
    hours = view.hours
    assert hours.height() > view.scroll.viewport().height()

    hours.reveal(3, FIRST, FIRST + 60)
    qapp.processEvents()
    assert hours.in_view(3, FIRST), "00:00 is not in the hours viewport"
    assert not hours.in_view(3, LAST), "24:00 still counted as reached while it is clipped"

    hours.reveal(3, LAST - 60, LAST)
    qapp.processEvents()
    assert hours.in_view(3, LAST), "24:00 is not in the hours viewport"
    assert not hours.in_view(3, FIRST), "00:00 still counted as reached while it is clipped"


def test_reach_does_not_substitute_the_edge_of_a_partial_track(qapp: QApplication) -> None:
    scroll = QScrollArea()
    scroll.resize(230, 400)
    hours = HoursCanvas(
        Hand(lambda block_id, from_day, span: Verdict(True, ""), QWidget()),
        BlockPainter(resolved_palette("system", False, None)),
        lambda area: [LinearTrack(3, QRectF(10, 10, 180, 1160), first=6 * 60, last=22 * 60)],
    )
    hours.setFixedSize(200, 1180)
    scroll.setWidget(hours)
    scroll.show()
    qapp.processEvents()
    hours.relayout()

    hours.reveal(3, 0, 60)
    qapp.processEvents()
    assert hours.in_view(3, 6 * 60)
    assert not hours.in_view(3, 0)

    hours.reveal(3, 23 * 60, 24 * 60)
    qapp.processEvents()
    assert hours.in_view(3, 22 * 60)
    assert not hours.in_view(3, 24 * 60)


def test_a_day_name_on_the_week_stays_visible_and_opens_that_day(qapp: QApplication) -> None:
    view = week_view(qapp)
    opened: list[int] = []
    view.day_opened.connect(opened.append)
    view.hours.reveal(3, LAST - 60, LAST)
    qapp.processEvents()
    name = view.findChild(QLabel, "weekDayName4")
    assert name is not None and name.isVisible()
    QTest.mouseClick(name, Qt.MouseButton.LeftButton)
    assert opened == [4]
