"""Bento, the tile home screen: what each tile says, and that its options change the board."""

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
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.bento import BentoView
    from desktop.native.layouts.registry import options_for, tokens_for
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week, minute_of


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-bento-test"])
    yield application


def shown(
    qapp: QApplication,
    clock: str = "13:40",
    today: int | None = 3,
    blocks: list[dict] | None = None,
    **chosen: str,
) -> BentoView:
    options = {**options_for(None, "bento"), **chosen}
    palette = resolved_palette("light-frost", False, None, "default")
    week = build_week(WEEK, BLOCKS if blocks is None else blocks, HOMEWORK, TRACE)
    view = BentoView()
    view.resize(1366, 700)
    view.show_week(
        Scene(week, today, minute_of(clock), options, tokens_for("bento", options["colour"], palette))
    )
    view.show()
    qapp.processEvents()
    return view


def text(view: BentoView, name: str) -> str:
    return view.findChild(QLabel, name).text()


def tiles(view: BentoView) -> list[str]:
    return sorted(item.objectName() for item in view.findChildren(QFrame) if item.property("tile"))


def test_the_big_tile_is_what_comes_next_and_how_soon(qapp: QApplication) -> None:
    view = shown(qapp)
    assert text(view, "bentoHeroKicker") == "UP NEXT · IN 4 H 20 MIN"
    assert text(view, "bentoHeroTitle") == "Dinner"
    assert text(view, "bentoHeroLine") == "18:00–18:30 · Meals"


def test_late_at_night_the_big_tile_says_the_day_is_done(qapp: QApplication) -> None:
    assert text(shown(qapp, "22:30"), "bentoHeroTitle") == "Nothing else today"


def test_deadlines_come_most_squeezed_first_in_the_solvers_words(qapp: QApplication) -> None:
    view = shown(qapp)
    assert [view.findChild(QPushButton, f"bentoDeadline{index}").text() for index in range(2)] == [
        "Chem-1\nThu 23:59 · Very little room",
        "Essay-1\nFri 21:00 · Limited room",
    ]


def test_what_has_no_time_is_listed_with_the_solvers_reason(qapp: QApplication) -> None:
    view = shown(qapp)
    assert text(view, "bentoWaitingKicker") == "NOT PLACED YET (1)"
    assert view.findChild(QPushButton, "bentoWaiting0").text() == (
        "Poster-1 · 2 h\nThere is no slot left before this deadline."
    )
    assert view.findChild(QPushButton, "bentoPlan").text() == "Plan it"


def test_an_empty_tile_says_what_to_do_next(qapp: QApplication) -> None:
    view = shown(qapp, blocks=[])
    assert text(view, "bentoWaitingEmpty") == "Nothing waiting"
    assert text(view, "bentoDeadlinesEmpty") == "Nothing is due. Add homework when you get some."
    assert view.findChild(QPushButton, "bentoAddSmall") is not None


def test_tonight_offers_focus_on_the_next_homework(qapp: QApplication) -> None:
    view = shown(qapp)
    asked: list[tuple] = []
    view.focus_requested.connect(lambda block, day: asked.append((block, day)))
    view.findChild(QPushButton, "bentoFocus").click()
    assert asked == [("essay-1", 3)]
    assert view.findChild(QPushButton, "bentoTonightTitle").text() == "Essay-1"


def test_the_week_total_counts_planned_homework(qapp: QApplication) -> None:
    view = shown(qapp)
    assert (text(view, "bentoTotalBig"), text(view, "bentoTotalLine")) == (
        "3 h 15 min",
        "3 h 15 min planned · 45 min done",
    )


def test_picking_a_day_in_the_load_chart_moves_the_strip(qapp: QApplication) -> None:
    view = shown(qapp)
    assert text(view, "bentoStripKicker") == "TODAY, THURSDAY 17"
    view.findChild(QPushButton, "bentoDay0").click()
    assert text(view, "bentoStripKicker") == "MONDAY 14"
    chips = [item.text() for item in view.findChildren(QPushButton) if item.property("kind") == "chip"]
    assert chips == ["08:00\nSchool", "15:45\nMath-1", "18:00\nDinner"]
    assert view.findChild(QPushButton, "bentoDay0").property("chosen") == "true"


def test_the_load_chart_says_each_days_minutes(qapp: QApplication) -> None:
    view = shown(qapp)
    assert [view.findChild(QPushButton, f"bentoDay{day}").text() for day in range(7)] == [
        "Mon 45",
        "Tue 0",
        "Wed 0",
        "Thu 150",
        "Fri 0",
        "Sat 0",
        "Sun 0",
    ]


def test_option_essentials_keeps_four_tiles_and_everything_a_main_view_needs(qapp: QApplication) -> None:
    assert tiles(shown(qapp)) == [
        "bentoDeadlines",
        "bentoHero",
        "bentoLoad",
        "bentoNew",
        "bentoStrip",
        "bentoTonight",
        "bentoTotal",
        "bentoWaiting",
    ]
    assert tiles(shown(qapp, tiles="essentials")) == [
        "bentoDeadlines",
        "bentoHero",
        "bentoStrip",
        "bentoWaiting",
    ]


def test_option_corners_and_colours_repaint_the_board(qapp: QApplication) -> None:
    assert "border-radius: 24px" in shown(qapp).styleSheet()
    assert "border-radius: 6px" in shown(qapp, corners="square").styleSheet()
    assert "border-radius: 24px" not in shown(qapp, corners="square").styleSheet()

    def hero(view: BentoView) -> str:
        tile = view.findChild(QFrame, "bentoHero")
        return tile.grab().toImage().pixelColor(tile.width() // 2, 30).name()

    assert hero(shown(qapp)) == "#4f46e5"
    assert hero(shown(qapp, colour="sunset")) == "#c2410c"
    assert (
        hero(shown(qapp, colour="match")) == resolved_palette("light-frost", False, None, "default")["accent"]
    )


def test_a_tile_does_not_hold_its_buttons_a_screen_away_from_its_text(qapp: QApplication) -> None:
    """The stretch belongs under the buttons. Above them it left a 165px hole in a 297px tile."""
    for blocks in (None, []):
        view = shown(qapp, blocks=blocks)
        tile = view.findChild(QFrame, "bentoWaiting")
        labels = tile.findChildren(QLabel)
        buttons = tile.findChildren(QPushButton)
        assert labels and buttons
        lowest_text = max(x.mapTo(tile, x.rect().bottomLeft()).y() for x in labels)
        highest_button = min(x.mapTo(tile, x.rect().topLeft()).y() for x in buttons)
        assert highest_button - lowest_text < 40, f"gap is {highest_button - lowest_text}px"


def narrow(qapp: QApplication, width: int) -> BentoView:
    options = options_for(None, "bento")
    palette = resolved_palette("light-frost", False, None, "default")
    view = BentoView()
    view.resize(width, 640)
    view.show()
    qapp.processEvents()
    view.show_week(
        Scene(
            build_week(WEEK, BLOCKS, HOMEWORK, TRACE),
            3,
            minute_of("13:40"),
            options,
            tokens_for("bento", options["colour"], palette),
        )
    )
    qapp.processEvents()
    return view


def test_a_narrow_window_gets_two_columns_not_four(qapp: QApplication) -> None:
    """Bento wanted 1130px. On a 1024 window that pushed Add and Plan off the side."""
    wide = narrow(qapp, 1366)
    assert wide.cramped is False
    assert wide._grid.columnCount() == 4

    tight = narrow(qapp, 1024)
    assert tight.cramped is True
    assert tight._grid.columnCount() == 2


def test_no_two_tiles_land_on_top_of_each_other_when_narrow(qapp: QApplication) -> None:
    """The first two-column arrangement overlapped the hero and the deadlines tile."""
    view = narrow(qapp, 1024)
    boxes = [
        (tile.objectName(), tile.geometry()) for tile in view.findChildren(QFrame) if tile.property("tile")
    ]
    for index, (name, box) in enumerate(boxes):
        for other_name, other in boxes[index + 1 :]:
            assert not box.intersects(other), f"{name} overlaps {other_name}"
