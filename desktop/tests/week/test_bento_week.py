"""Bento's week: seven live columns on the shared hand, the Today hero and the day tiles around it, and
what the blocks write on themselves."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QEnterEvent, QFont, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native.fonts import load_fonts  # noqa: E402
from desktop.native.hours import canvas as canvas_module  # noqa: E402
from desktop.native.hours.canvas import Drawn  # noqa: E402
from desktop.native.hours.geometry import Span  # noqa: E402
from desktop.native.layouts.bento import RISE, BentoPainter, BentoView, DayTile  # noqa: E402
from desktop.native.layouts.registry import options_for, tokens_for  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.motion import apply_ui_effects  # noqa: E402
from desktop.tests.day.support_bento import Wrote, hours, scene, shown, text  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-bento-week-test"])


def test_week_hero_has_seven_live_columns_and_openable_day_names(qapp: QApplication) -> None:
    view = shown(qapp)
    canvas = hours(view, "bentoWeekHours")
    assert [(track.day, track.first, track.last) for track in canvas.tracks] == [
        (day, 0, 1440) for day in range(7)
    ]
    assert text(view, "bentoHeroTitle") == "This week"
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    pick = view.findChild(QPushButton, "bentoDayName0")
    assert pick is not None
    assert canvas.day_name(0) == pick.mapToGlobal(pick.rect().center())
    pick.click()
    assert opened == ["2026-09-14"]


@pytest.mark.parametrize("hero", ["week", "today"])
def test_the_week_draws_no_add_of_its_own(qapp: QApplication, hero: str) -> None:
    """The top bar has Add in every design (decision 11 of 0.17)."""
    view = shown(qapp, "week", hero=hero)
    assert not [item.objectName() for item in view.findChildren(QPushButton) if "Add" in item.objectName()]


def test_the_today_hero_swaps_in_the_day_a_tile_is_clicked_on(qapp: QApplication) -> None:
    view = shown(qapp, hero="today")
    assert [track.day for track in hours(view).tracks] == [3]
    tiles = {tile.property("day_target") for tile in view.findChildren(DayTile)}
    assert tiles == {0, 1, 2, 4, 5, 6}
    heading = view.findChild(QPushButton, "bentoHeroDay")
    assert heading.property("day_target") == 3
    assert hours(view).day_name(3) == heading.mapToGlobal(heading.rect().center())
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    view.findChild(DayTile, "bentoDay4").click()
    qapp.processEvents()
    assert [track.day for track in hours(view).tracks] == [4]
    assert {tile.property("day_target") for tile in view.findChildren(DayTile) if tile.isVisible()} == {
        0, 1, 2, 3, 5, 6,
    }
    assert opened == []
    # A new minute keeps Friday in the hero.
    view.show_week(scene(hero="today", clock="13:41"))
    qapp.processEvents()
    assert [track.day for track in hours(view).tracks] == [4]


def test_a_pointed_at_day_lifts_and_does_not_rise_with_animations_off_or_reduced(qapp: QApplication) -> None:
    def pointed(view: BentoView) -> DayTile:
        tile = view.findChild(DayTile, "bentoDay4")
        at = QPointF(8, 8)
        QApplication.sendEvent(tile, QEnterEvent(at, at, QPointF(tile.mapToGlobal(QPoint(8, 8)))))
        return tile

    try:
        apply_ui_effects("normal")
        view = shown(qapp, hero="today")
        rest = view.findChild(DayTile, "bentoDay4").card()
        tile = pointed(view)
        wait_until(qapp, lambda: tile.lift == 1.0, what=lambda: f"the lift stayed at {tile.lift}")
        assert tile.card().top() == rest.top() - RISE
        for level in ("off", "reduce"):
            apply_ui_effects(level)
            view = shown(qapp, hero="today")
            tile = pointed(view)
            assert tile.lift == 1.0, f"lifted at once under {level}"
            assert tile.card() == rest, f"and in place under {level}"
    finally:
        apply_ui_effects("normal")


def test_a_half_hour_block_says_its_range_on_the_week(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dinner is half an hour. T-W35: a block always shows its range; the title is what gets cut. In
    the body size the week's 44 pixels an hour leave no room for the name, so the week writes
    18:00–18:30 (the name is in the tooltip)."""
    written: list[str] = []
    real = canvas_module._paint_layout

    def spy(painter, lay, *rest, **kwargs) -> None:
        written.extend(line.text for line in lay)
        real(painter, lay, *rest, **kwargs)

    monkeypatch.setattr(canvas_module, "_paint_layout", spy)
    hours(shown(qapp, "week"), "bentoWeekHours").grab()
    assert "18:00–18:30" in written, written


def test_the_week_keeps_school_s_time_where_its_times_do_not_fit(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In the window's body font a week column at 1280 is too narrow for "08:00–14:30", and School
    said its name alone. It says when it starts instead, as Retro's week does, and a column wide
    enough for the whole range still says it."""
    blocks: list[list[str]] = []
    real = canvas_module._paint_layout

    def spy(painter, lay, *rest, **kwargs) -> None:
        blocks.append([line.text for line in lay])
        real(painter, lay, *rest, **kwargs)

    monkeypatch.setattr(canvas_module, "_paint_layout", spy)
    usual = QFont(qapp.font())
    font = QFont(usual)
    font.setPointSize(13)
    qapp.setFont(font)
    try:
        for size, said in (((1280, 764), "08:00"), ((2400, 764), "08:00–14:30")):
            view = shown(qapp, size=size)
            blocks.clear()
            hours(view, "bentoWeekHours").grab()
            school = [lines for lines in blocks if lines and lines[0] == "School"]
            assert school and all(lines[1:] == [said] for lines in school), (size, school)
    finally:
        qapp.setFont(usual)


def test_a_week_block_at_the_smallest_window_names_itself_and_says_when_it_starts(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In a window 810 pixels across a day on the week is a block 52.4 pixels wide: "Sch…" over
    "08:00", where it said "Sc…" alone; no less than Today's app's Week writes any block that narrow."""
    monkeypatch.setattr(canvas_module, "QPainter", Wrote)
    load_fonts()
    palette = resolved_palette("light-frost", False, None, "default")
    painter = BentoPainter(tokens_for("bento", options_for(None, "bento")["look"], palette))
    drawn = Drawn("school", "School", "class", False, Span(0, 8 * 60, 14 * 60 + 30), 0, 1)
    page = QRectF(0, 0, 200, 300)
    image = QImage(200, 300, QImage.Format.Format_ARGB32)
    paint = Wrote(image)
    paint.setFont(QFont("Inter", 13))
    Wrote.words = []
    painter.block(paint, QRectF(20, 20, 52.4, 200), drawn, page)
    paint.end()
    said = [words for words, _where in Wrote.words]
    assert said[:1] in (["School"], ["Sch…"]), said
    assert "08:00" in said, said
