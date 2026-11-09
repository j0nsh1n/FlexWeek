"""Day dial, the clock-face day screen: what its card, list, week strip and buttons say and do for a
given minute of the day. The face is covered in test_dial_face.py; how it looks is in the pictures
(desktop/tests/pictures/_day_g02.py)."""

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
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QScrollArea, QWidget

    from desktop.native.layouts.dial import DialFace
    from desktop.native.layouts.registry import DESIGN_LOOKS
    from desktop.tests.day.support_dial import actions, rows, shown, text
    from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, block


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-dial-test"])
    yield application


def test_between_blocks_the_left_card_follows_the_clock(qapp: QApplication) -> None:
    view = shown(qapp, "15:40")
    assert text(view, "dialKicker") == "Up next"
    assert text(view, "dialFreeLine") == "2 h 20 min free until 18:00"
    assert text(view, "dialListLabel") == "3 things left today"
    assert view.findChild(QFrame, "dialCard") is None
    # One filled button, the step this minute is for: with no homework on, Running late.
    assert actions(view) == [("dialLate", "main"), ("dialBack", "")]


def test_during_homework_the_left_card_counts_down_and_actions_stay_in_one_row(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    assert text(view, "dialKicker") == "Now"
    assert text(view, "dialFreeLine") == "45 min left"
    assert text(view, "dialListLabel") == "2 things left today"
    assert actions(view) == [
        ("dialFinished", "main"),
        ("dialFocus", ""),
        ("dialLate", ""),
        ("dialBack", ""),
    ]


def test_the_list_reads_the_day_in_columns_marking_what_is_over_done(qapp: QApplication) -> None:
    assert rows(shown(qapp, "19:00")) == [
        ("08:00–14:30", "School", "6 h 30 min", "Done", "past"),
        ("18:00–18:30", "Dinner", "30 min", "Done", "past"),
        ("18:45–19:45", "Essay-1", "1 h", "Now", "now"),
        ("20:00–21:30", "Chem-1", "1 h 30 min", "", ""),
    ]


def test_the_free_line_and_list_name_their_empty_states(qapp: QApplication) -> None:
    assert text(shown(qapp, "15:40"), "dialFreeLine") == "2 h 20 min free until 18:00"
    empty = shown(qapp, "13:40", [])
    assert text(empty, "dialFreeLine") == "Free until 22:00"
    assert text(empty, "dialListEmpty") == "Nothing planned"
    late = shown(qapp, "22:30")
    assert text(late, "dialFreeLine") == "Nothing left today"
    assert late.findChild(QLabel, "dialListEmpty") is None, "the day's rows are still listed, all over"


def test_homework_with_no_time_is_counted_in_the_waiting_strip(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    assert text(view, "dialWaitingStrip") == "1 homework not placed yet"
    vocab = {"id": "vocab", "title": "Spanish vocab", "due": "2026-09-19T08:00", "completed": False}
    more = [*BLOCKS, block("vocab-1", "flexible", [], None, 30, assignment_id="vocab")]
    view = shown(qapp, "19:00", more, homework={**HOMEWORK, "vocab": vocab})
    assert text(view, "dialWaitingStrip") == "2 homework not placed yet"


def test_the_weeks_small_dials_are_labelled_and_only_todays_is_marked(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    strip = view.findChild(QWidget, "dialStrip")
    names = [item.text() for item in strip.findChildren(QLabel, "dialMiniName")]
    dates = strip.findChildren(QLabel, "dialMiniDate")
    assert list(zip(names, [item.text() for item in dates], strict=True)) == [
        ("Mon", "14"),
        ("Tue", "15"),
        ("Wed", "16"),
        ("Thu", "17"),
        ("Fri", "18"),
        ("Sat", "19"),
        ("Sun", "20"),
    ]
    assert [item.property("today") for item in dates] == [False, False, False, True, False, False, False]
    assert len(view.findChildren(DialFace)) == 8


def test_a_small_dial_opens_that_day_and_today_is_one_press_back(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    QTest.mouseClick(view.findChild(DialFace, "dialMini0"), Qt.MouseButton.LeftButton)
    assert text(view, "dialKicker") == "Monday"
    assert text(view, "dialListLabel") == "Monday"
    assert [(name, tag, state) for _time, name, _length, tag, state in rows(view)] == [
        ("School", "Done", "past"),
        ("Math-1", "Done", "past"),
        ("Dinner", "Done", "past"),
    ]
    view.findChild(QPushButton, "dialToday").click()
    assert text(view, "dialKicker") == "Now"


def test_in_another_week_it_shows_the_week_but_claims_no_now(qapp: QApplication) -> None:
    view = shown(qapp, "19:00", today=None)
    assert text(view, "dialKicker") == "Monday"
    assert text(view, "dialWeekNotice") == (
        "Not this week — Go back to planning and open this week to see today."
    )
    assert view.findChild(QPushButton, "dialToday") is None
    assert view.findChild(QPushButton, "dialFinished") is None
    assert view.findChild(QPushButton, "dialBack") is not None


def test_the_list_and_week_options_remove_them(qapp: QApplication) -> None:
    assert rows(shown(qapp, "19:00", list="hide")) == []
    assert len(shown(qapp, "19:00").findChildren(DialFace)) == 8
    hidden = shown(qapp, "19:00", week="hide")
    assert len(hidden.findChildren(DialFace)) == 1
    assert hidden.findChild(QWidget, "dialStrip").isVisible() is False
    assert shown(qapp, "19:00").findChild(QWidget, "dialStrip").isVisible() is True


def test_the_first_look_the_dial_offers_is_night(qapp: QApplication) -> None:
    assert DESIGN_LOOKS["dial"][0] == ("preset:dial-midnight", "Night")


def test_the_rows_replace_the_separate_ring_key(qapp: QApplication) -> None:
    assert shown(qapp, "15:40").findChild(QFrame, "dialKey") is None


def test_the_list_sits_in_a_scroller_of_its_own(qapp: QApplication) -> None:
    view = shown(qapp, "13:40")
    scroll = view.findChild(QScrollArea, "dialListScroll")
    assert scroll is not None and scroll.isVisibleTo(view)
