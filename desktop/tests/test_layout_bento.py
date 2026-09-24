"""Bento's two live hero surfaces and their retained scroll state."""

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
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

    from desktop.native.hours.canvas import HoursCanvas
    from desktop.native.hours.chips import TrayChip
    from desktop.native.hours.hand import Hand, Verdict
    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.bento import BentoView
    from desktop.native.layouts.registry import options_for, tokens_for
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week, minute_of


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-bento-test"])
    yield application


def scene(surface: str = "week", *, clock: str = "13:40", blocks: list[dict] | None = None,
          homework: dict | None = None, iso_day: str = "2026-09-17", **chosen: str) -> Scene:
    options = {**options_for(None, "bento"), **chosen}
    palette = resolved_palette("light-frost", False, None, "default")
    week = build_week(
        WEEK, BLOCKS if blocks is None else blocks,
        HOMEWORK if homework is None else homework, TRACE,
    )
    return Scene(
        week, 3, minute_of(clock), options,
        tokens_for("bento", options["colour"], palette), surface=surface,
        month={"month": "2026-09", "days": []} if surface == "month" else None,
        iso_day=iso_day,
    )


def shown(qapp: QApplication, surface: str = "week", **chosen: str) -> BentoView:
    view = BentoView()
    view.resize(1150, 768)
    view.show_week(scene(surface, **chosen))
    view.show()
    qapp.processEvents()
    return view


def text(view: BentoView, name: str) -> str:
    found = view.findChild(QLabel, name)
    assert found is not None
    return found.text()


def test_day_hero_is_one_live_full_day_track_with_window_hand(qapp: QApplication) -> None:
    host = QWidget()
    hand = Hand(lambda *_: Verdict(True, ""), host)
    view = BentoView(hand=hand)
    view.resize(1150, 768)
    view.show_week(scene("day"))
    view.show()
    qapp.processEvents()
    hours = view.findChild(HoursCanvas, "bentoDayHours")
    assert view.hand is hand
    assert view.uses_drawer is False
    assert [(track.day, track.first, track.last) for track in hours.tracks] == [(3, 0, 1440)]
    assert hours.hand is hand
    assert text(view, "bentoHeroKicker") == "THURSDAY 17 · YOUR DAY"
    assert view.drawer is None


def test_week_hero_has_seven_live_columns_and_openable_day_names(qapp: QApplication) -> None:
    view = shown(qapp)
    hours = view.findChild(HoursCanvas, "bentoWeekHours")
    assert [(track.day, track.first, track.last) for track in hours.tracks] == [
        (day, 0, 1440) for day in range(7)
    ]
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    pick = view.findChild(QPushButton, "bentoDayName0")
    assert pick is not None
    assert hours.day_name(0) == pick.mapToGlobal(pick.rect().center())
    pick.click()
    assert opened == ["2026-09-14"]


def test_waiting_homework_is_a_hand_chip_and_appears_in_deadlines(qapp: QApplication) -> None:
    view = shown(qapp)
    chip = view.findChild(TrayChip, "bentoWaiting0")
    assert chip is not None
    assert chip.hand is view.hand
    assert text(view, "bentoWaitingKicker") == "NOT PLACED YET"
    deadlines = [item.text() for item in view.findChildren(QPushButton)
                 if item.objectName().startswith("bentoDeadline")]
    assert any("Poster-1" in words and "Not placed yet" in words for words in deadlines)
    day = shown(qapp, "day")
    assert day.findChild(QPushButton, "bentoTonightDeadline0") is not None


def test_day_rail_uses_the_opened_day(qapp: QApplication) -> None:
    view = shown(qapp, "day", iso_day="2026-09-18")
    assert text(view, "bentoHeroKicker") == "FRIDAY 18 · YOUR DAY"
    assert text(view, "bentoTonightKicker") == "ON FRIDAY"
    assert text(view, "bentoTonightTitle") == "No homework this day"


def test_day_and_week_keep_their_scroll_and_zoom_through_redraw(qapp: QApplication) -> None:
    view = shown(qapp)
    week = view._scrolls["week"]
    week.zoom_by(1)
    week_px = week.px
    week.verticalScrollBar().setValue(260)
    view.show_week(scene("week", clock="13:41"))
    qapp.processEvents()
    assert view._scrolls["week"] is week
    assert week.px == week_px
    assert week.verticalScrollBar().value() > 0
    view.show_week(scene("day"))
    qapp.processEvents()
    day = view._scrolls["day"]
    day.zoom_by(1)
    view.show_week(scene("week", clock="13:42"))
    qapp.processEvents()
    assert view._scrolls["week"] is week
    assert view._scrolls["day"] is day
    assert week.px == week_px
    view.show_week(scene("day", clock="13:43"))
    qapp.processEvents()
    assert view._scrolls["day"] is day
    assert day.px == 128
    view.show_week(scene("month"))
    qapp.processEvents()
    assert view.hours_surfaces() == []
    assert view.month_surfaces()
    assert shiboken6.isValid(week)
    assert shiboken6.isValid(day)
    view.close()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(week)
    assert not shiboken6.isValid(day)


def test_rail_stays_beside_the_hero_in_a_small_window(qapp: QApplication) -> None:
    view = shown(qapp, "day")
    hero = view.findChild(QLabel, "bentoHeroKicker")
    waiting = view.findChild(TrayChip, "bentoWaiting0")
    assert waiting.isVisible()
    assert waiting.mapToGlobal(waiting.rect().center()).x() > hero.mapToGlobal(hero.rect().center()).x()


def test_month_uses_the_shared_grid(qapp: QApplication) -> None:
    view = shown(qapp, "month")
    assert view.hours_surfaces() == []
    assert view.month_surfaces()
