"""Setup's Style page: one style's picture large in the middle with the neighbours peeking, arrows and a
dot for each, the name and one note; whatever stands in the middle is the chosen style."""

# ruff: noqa: F811  (a test's fixture parameter has the name of the imported fixture)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.layouts.registry import LAYOUTS, sanitize_layout
from desktop.native.setup import (
    EXPERIMENTAL_TAG,
    LOOK,
    STYLE,
    STYLES,
    WEEK,
    SetupPage,
    style_layout,
    style_look,
)
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.setup.support_setup_page import show_setup
from desktop.tests.window_support import qapp  # noqa: F401

ORDER = ["plain", "night", "dashboard", "retro"]


@pytest.fixture()
def style_page(qapp: QApplication, window: NativeWindow) -> SetupPage:
    return show_setup(qapp, window)


def middle(setup: SetupPage) -> str:
    return setup.carousel.key()


def test_the_plain_calendar_is_chosen_from_the_start_and_next_keeps_it(style_page: SetupPage) -> None:
    setup = style_page
    assert setup.style_cards["plain"].is_selected()
    assert [key for key, slide in setup.style_cards.items() if slide.is_selected()] == ["plain"]
    assert setup.carousel.dots["plain"].property("chosen") is True
    assert not any(setup.carousel.dots[key].property("chosen") for key in ORDER[1:])
    answer = setup._answer(STYLE)
    assert answer is not None
    assert answer["layout"]["main"] == "classic" and answer["pack"] == "light-frost"


def test_next_keeps_whichever_style_is_in_the_middle(style_page: SetupPage) -> None:
    setup = style_page
    kept = []
    setup.left.connect(lambda step, destination, answer: kept.append((step, destination, answer)))
    setup.carousel.step(1)
    setup.next.click()
    step, destination, answer = kept[0]
    assert (step, destination) == (STYLE, WEEK)
    assert answer["layout"]["main"] == "timeline"
    assert answer["look"]["knobs"]["density"] == "compact"


def test_skipping_the_style_page_keeps_the_look_it_had_even_with_a_style_in_the_middle(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    setup = show_setup(qapp, window, pack="system")
    kept = []
    setup.left.connect(lambda step, destination, answer: kept.append(answer))
    setup.carousel.step(1)
    setup.skip.click()
    assert kept == [None]
    assert setup._pack == "system"


def test_left_and_right_move_the_middle_and_wrap_round(style_page: SetupPage) -> None:
    setup = style_page
    seen = []
    setup.previewed.connect(lambda shown: seen.append(shown["layout"]["main"]))
    setup.carousel.setFocus()
    QTest.keyClick(setup.carousel, Qt.Key.Key_Right)
    assert middle(setup) == "night"
    assert setup.style_cards["night"].is_selected() and not setup.style_cards["plain"].is_selected()
    QTest.keyClick(setup.carousel, Qt.Key.Key_Left)
    QTest.keyClick(setup.carousel, Qt.Key.Key_Left)
    assert middle(setup) == "retro", "the last style stands left of the first"
    assert seen == ["timeline", "classic", "retro"], "each move shows the look as it is picked"
    QTest.keyClick(setup.carousel, Qt.Key.Key_Right)
    assert middle(setup) == "plain"


def test_home_and_end_go_to_the_first_and_last_style(style_page: SetupPage) -> None:
    """Home and End jump to the ends of the row, as they do in a radio group."""
    setup = style_page
    order = [style.key for style in setup.carousel._order]
    setup.carousel.setFocus()
    QTest.keyClick(setup.carousel, Qt.Key.Key_End)
    assert middle(setup) == order[-1] == "retro"
    assert setup.carousel.is_chosen()
    QTest.keyClick(setup.carousel, Qt.Key.Key_Home)
    assert middle(setup) == order[0] == "plain"


def test_each_dot_says_its_place_in_the_row(style_page: SetupPage) -> None:
    """A dot is announced with its number, as "Show Plain calendar, 1 of 4"."""
    order = style_page.carousel._order
    for number, style in enumerate(order, start=1):
        name = style_page.carousel.dots[style.key].accessibleName()
        assert name == f"Show {style.name}, {number} of {len(order)}"


def test_style_dots_are_radio_buttons_with_the_current_style_checked(style_page: SetupPage) -> None:
    setup = style_page
    for number, style in enumerate(setup.carousel._order, start=1):
        dot = setup.carousel.dots[style.key]
        face = QAccessible.queryAccessibleInterface(dot)
        assert face.role() == QAccessible.Role.RadioButton
        assert bool(face.state().checked) is (style.key == middle(setup))
        assert face.text(QAccessible.Text.Description) == f"{number} of {len(setup.carousel._order)}"


def test_the_arrows_and_the_dots_move_the_middle_too(style_page: SetupPage) -> None:
    setup = style_page
    setup.carousel.following.click()
    assert middle(setup) == "night"
    setup.carousel.previous.click()
    setup.carousel.previous.click()
    assert middle(setup) == "retro"
    setup.carousel.dots["dashboard"].click()
    assert middle(setup) == "dashboard"
    assert setup.carousel.dots["dashboard"].property("chosen") is True
    assert setup.carousel.dots["retro"].property("chosen") is False


def test_a_click_on_a_peeking_card_brings_it_to_the_middle(style_page: SetupPage) -> None:
    setup = style_page
    peeking = setup.style_cards["night"]
    stage = setup.carousel.stage
    # A point in the part of it that shows, in its own coordinates.
    visible = QPoint(stage.width() - 10 - peeking.x(), peeking.height() // 2)
    QTest.mouseClick(peeking, Qt.MouseButton.LeftButton, pos=visible)
    assert middle(setup) == "night"
    assert setup.style_cards["night"].is_selected()


def test_the_name_and_one_note_belong_to_the_middle_style(style_page: SetupPage) -> None:
    setup = style_page
    assert (setup.carousel.name.text(), setup.carousel.note.text()) == (
        "Plain calendar",
        "Your week as a timetable grid",
    )
    setup.carousel.step(2)
    assert setup.carousel.name.text() == "Dashboard"
    assert setup.carousel.note.text() == "Next up and due soon, as tiles"


def test_no_style_note_repeats_the_name_of_its_layout() -> None:
    for style in STYLES:
        if style.key == "retro":
            continue  # its note is the mock-up's own words; "Retro" is both the style and the design
        assert LAYOUTS[style.main].label.casefold() not in style.note.casefold(), style.key
        assert "·" not in style.note


def test_only_the_experimental_styles_carry_the_tag_and_they_come_last(style_page: SetupPage) -> None:
    setup = style_page
    assert list(setup.style_cards) == ORDER
    tagged = [key for key, slide in setup.style_cards.items() if slide.tag is not None]
    assert tagged == ["dashboard", "retro"]
    for key in tagged:
        assert setup.style_cards[key].tag.text() == EXPERIMENTAL_TAG


def test_running_setup_again_opens_on_the_style_in_use_and_a_look_of_their_own_chooses_nothing(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    night = next(style for style in STYLES if style.key == "night")
    setup = show_setup(
        qapp,
        window,
        first_run=False,
        layout=style_layout(night, sanitize_layout(None)),
        look=style_look(night),
        pack=night.pack,
    )
    assert middle(setup) == "night" and setup.style_cards["night"].is_selected()
    setup = show_setup(qapp, window, first_run=False, layout={"main": "mission"})
    assert not any(slide.is_selected() for slide in setup.style_cards.values())
    assert setup._answer(STYLE) is None, "Next on a look of their own keeps it"


def test_choose_my_own_look_opens_the_look_page(style_page: SetupPage) -> None:
    setup = style_page
    own = setup.pages[STYLE].findChild(QPushButton, "setupOwnLook")
    own.click()
    assert setup.step == LOOK
