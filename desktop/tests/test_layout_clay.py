"""Clay deck: the middle card is real buttons, the neighbours are painted and lean, and the pager is
their keyboard twin."""

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
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.clay import ClayDeckView, SideCard
    from desktop.native.layouts.registry import options_for, tokens_for
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week, minute_of


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-clay-test"])
    yield application


def shown(qapp: QApplication, today: int | None = 3, **chosen: str) -> ClayDeckView:
    options = {**options_for(None, "clay"), **chosen}
    palette = resolved_palette("light-frost", False, None, "default")
    view = ClayDeckView()
    view.resize(1366, 760)
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    view.show_week(
        Scene(week, today, minute_of("13:40"), options, tokens_for("clay", options["colour"], palette))
    )
    view.show()
    qapp.processEvents()
    return view


def pills(view: ClayDeckView) -> list[str]:
    return [item.text() for item in view.findChildren(QPushButton) if item.property("kind") == "pill"]


def sides(view: ClayDeckView) -> list[tuple[int, float]]:
    return [(card.day, card.tilt) for card in view.findChildren(SideCard)]


def test_today_is_in_the_middle_with_its_blocks_as_buttons(qapp: QApplication) -> None:
    view = shown(qapp)
    assert view.findChild(QLabel, "clayCentreTitle").text() == "Thursday 17 · today"
    assert pills(view) == [
        "School\n08:00 · 6 h 30 min",
        "Dinner\n18:00 · 30 min",
        "Essay-1\n18:45 · 1 h · limited room",
        "Chem-1\n20:00 · 1 h 30 min · very little room",
    ]


def test_the_neighbours_lean_away_from_the_middle(qapp: QApplication) -> None:
    assert sides(shown(qapp)) == [(1, -7.0), (2, -3.5), (4, 3.5), (5, 7.0)]


def test_a_click_on_a_neighbour_brings_it_to_the_middle(qapp: QApplication) -> None:
    view = shown(qapp)
    QTest.mouseClick(view.findChild(SideCard, "claySide4"), Qt.MouseButton.LeftButton)
    assert view.findChild(QLabel, "clayCentreTitle").text() == "Friday 18"
    assert view.findChild(QLabel, "claySub").text() == "Friday is in the middle."


def test_the_pager_and_the_flip_buttons_reach_every_day(qapp: QApplication) -> None:
    view = shown(qapp)
    view.findChild(QPushButton, "clayDay0").click()
    assert view.findChild(QLabel, "clayCentreTitle").text() == "Monday 14"
    assert view.findChild(QPushButton, "clayEarlier").isEnabled() is False
    assert sides(view) == [(1, 3.5), (2, 7.0)]
    view.findChild(QPushButton, "clayLater").click()
    assert view.findChild(QLabel, "clayCentreTitle").text() == "Tuesday 15"
    view.findChild(QPushButton, "clayToday").click()
    assert view.findChild(QLabel, "clayCentreTitle").text() == "Thursday 17 · today"


def test_a_neighbour_is_described_for_a_screen_reader(qapp: QApplication) -> None:
    card = shown(qapp).findChild(SideCard, "claySide4")
    assert card.accessibleName() == "Friday 18: 08:00  School, 18:00  Dinner. Click to open."


def test_the_tray_names_what_has_no_time_yet(qapp: QApplication) -> None:
    waiting = shown(qapp).findChild(QPushButton, "clayWaiting0")
    assert (waiting.text(), waiting.toolTip()) == (
        "Poster-1 · 2 h",
        "There is no slot left before this deadline.",
    )


def test_option_three_cards_and_straight_cards(qapp: QApplication) -> None:
    assert sides(shown(qapp, cards="three")) == [(2, -3.5), (4, 3.5)]
    assert sides(shown(qapp, tilt="off")) == [(1, 0.0), (2, 0.0), (4, 0.0), (5, 0.0)]


def test_option_colours_repaint_the_deck_and_the_middle_card(qapp: QApplication) -> None:
    def seen(view: ClayDeckView) -> tuple[str, str]:
        card = view.findChild(QFrame, "clayCentre")
        return view.grab().toImage().pixelColor(4, 4).name(), card.grab().toImage().pixelColor(30, 12).name()

    assert seen(shown(qapp)) == ("#f3ecff", "#e6e6fa")
    assert seen(shown(qapp, colour="mint")) == ("#ecfbf3", "#f4f3b3")


def test_a_side_card_says_when_it_has_cut_a_title(qapp: QApplication) -> None:
    """Qt clips drawText to its rect, so a long title was cut mid-word with nothing to show for it."""
    long_title = [
        {**block, "title": "Saturday shift at the cafe until late in the evening"}
        if block["id"] == "school"
        else block
        for block in BLOCKS
    ]
    options = {**options_for(None, "clay"), "tilt": "off"}
    palette = resolved_palette("light-frost", False, None, "default")
    view = ClayDeckView()
    view.resize(1366, 760)
    view.show_week(
        Scene(
            build_week(WEEK, long_title, HOMEWORK, TRACE),
            3,
            minute_of("13:40"),
            options,
            tokens_for("clay", options["colour"], palette),
        )
    )
    view.show()
    qapp.processEvents()
    card = view.findChild(SideCard, "claySide1")
    assert card is not None
    painted = card.painted_lines()
    assert painted, "the card should have lines to paint"
    cut = [line for line in painted if line != card._lines[painted.index(line)]]
    assert cut, "the long title should not have fitted"
    assert all(line.endswith("\u2026") for line in cut), painted


def test_a_short_title_is_left_alone(qapp: QApplication) -> None:
    card = shown(qapp).findChild(SideCard, "claySide4")
    assert card.painted_lines() == card._lines
