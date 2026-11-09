"""My day's two screens, One thing and Day dial, on the demo's week at every demo size: which buttons
and rows each shows at a minute of the day, what they ask the window for, and how a day letter or
small dial changes the day. Where things sit and how big they are is judged on the pictures
(desktop/tests/pictures/_myday_g02.py)."""

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
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QScrollArea

    from desktop.native.layouts.dial import DayDialView, DialFace
    from desktop.native.layouts.one_thing import OneThingView
    from desktop.native.weekmodel import set_clock_24h
    from desktop.tests.myday.support_demo_day import THURSDAY, shown
    from desktop.tests.test_weekmodel import block

SIZES = [(1024, 640), (1280, 800), (1440, 900)]


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-myday-test"])
    yield application


@pytest.fixture(autouse=True)
def demo_clock() -> None:
    """The demo is written on the 12-hour clock (the next test starts on the 24-hour one again)."""
    set_clock_24h(False)


def row_buttons(view: DayDialView) -> list[QPushButton]:
    return [row for row in view.findChildren(QPushButton) if row.property("kind") == "row"]


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("large", [False, True])
def test_one_thing_keeps_all_four_actions_at_every_demo_size(
    qapp: QApplication, width: int, height: int, large: bool
) -> None:
    view = shown(qapp, OneThingView, "19:10", width, height, large)
    for name in ("oneFinished", "oneFocus", "oneLate", "oneBack"):
        action = view.findChild(QPushButton, name)
        assert action is not None and action.isVisibleTo(view), name


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("large", [False, True])
def test_one_things_then_row_time_is_written_whole_at_every_demo_size(
    qapp: QApplication, width: int, height: int, large: bool
) -> None:
    # At 15:40 the demo's Soccer is next and the History essay is the one Then row.
    view = shown(qapp, OneThingView, "15:40", width, height, large)
    times = view.findChildren(QLabel, "oneRowTime")
    assert [time.text() for time in times] == ["7:00 PM"]
    assert not times[0].wordWrap()


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("large", [False, True])
def test_day_dial_keeps_the_clock_rows_and_actions_at_every_demo_size(
    qapp: QApplication, width: int, height: int, large: bool
) -> None:
    view = shown(qapp, DayDialView, "15:40", width, height, large)
    rows = row_buttons(view)
    row_times = [row.findChild(QLabel, "dialRowTime") for row in rows]
    assert [time.text() for time in row_times] == ["8 AM–2:30 PM", "4–5:30 PM", "7–8 PM"]
    for name in ("dialLate", "dialBack"):
        action = view.findChild(QPushButton, name)
        assert action is not None and action.isVisibleTo(view), name
    # Each row's segment is on the ring, where a click reaches the same block.
    face = view.findChild(DialFace, "dialFace")
    points = [face.track.point_for(minute) for minute in (8 * 60 + 30, 16 * 60 + 30, 19 * 60 + 30)]
    assert {face.block_at(point).block_id for point in points} == {row.property("blockId") for row in rows}
    assert view.findChild(QPushButton, "dialRowFinished2") is not None
    # The demo gives Start focus to the current or next row only; at 15:40 that is Soccer, not the essay.
    assert view.findChild(QPushButton, "dialRowFocus2") is None


def test_one_things_then_list_has_a_row_for_every_thing_left(qapp: QApplication) -> None:
    blocks = [
        block("school", "locked", [3], "08:00", 390),
        block("first", "locked", [3], "14:00", 30),
        block("second", "locked", [3], "14:30", 30),
        block("third", "locked", [3], "15:00", 30),
        block("fourth", "locked", [3], "15:30", 30),
        block("fifth", "locked", [3], "16:00", 30),
        block("sixth", "locked", [3], "16:30", 30),
    ]
    view = shown(qapp, OneThingView, "13:00", blocks=blocks)
    assert view.findChild(QScrollArea, "oneThenScroll") is not None
    assert len(view.findChildren(QLabel, "oneRowTime")) == 6
    assert len(view.findChildren(QFrame, "oneRow")) == 6


def test_day_letters_switch_the_displayed_day(qapp: QApplication) -> None:
    view = shown(qapp, OneThingView, "15:40")
    changed: list[str] = []
    view.watched_day_changed.connect(changed.append)
    QTest.mouseClick(view.findChild(QPushButton, "oneDay0"), Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert changed == ["2026-09-14"]
    assert view.findChild(QLabel, "oneLabel").text() == "Mon"


def test_another_day_is_chosen_and_offers_only_back_to_planning(qapp: QApplication) -> None:
    # Monday is day 0; the demo's `.dl.on` goes to the letter clicked and onHw/hwLeft need isToday.
    view = shown(qapp, OneThingView, "15:40")
    QTest.mouseClick(view.findChild(QPushButton, "oneDay0"), Qt.MouseButton.LeftButton)
    qapp.processEvents()
    chosen = [button.objectName() for button in view.findChildren(QPushButton) if button.isChecked()]
    assert chosen == ["oneDay0"]
    names = ["oneFinished", "oneFocus", "oneLate", "oneBack"]
    assert [name for name in names if view.findChild(QPushButton, name) is not None] == ["oneBack"]
    dial = shown(qapp, DayDialView, "15:40")
    QTest.mouseClick(dial.findChild(DialFace, "dialMini0"), Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert dial.findChild(QLabel, "dialKicker").text() == "Monday"
    names = ["dialFinished", "dialFocus", "dialLate", "dialToday", "dialBack"]
    assert [name for name in names if dial.findChild(QPushButton, name) is not None] == [
        "dialToday",
        "dialBack",
    ]


def test_the_dial_marks_the_next_row_and_an_empty_then_list_says_so(qapp: QApplication) -> None:
    view = shown(qapp, DayDialView, "15:40")
    tags = [
        (row.property("blockId"), [word.text() for word in row.findChildren(QLabel, "dialRowTagText")])
        for row in row_buttons(view)
    ]
    assert tags == [("school", ["Done"]), ("soccer", ["Up next"]), ("essay-1", [])]
    empty = shown(qapp, OneThingView, "13:00", blocks=[block("school", "locked", [3], "08:00", 390)])
    assert empty.findChild(QLabel, "oneThenEmpty").text() == "Nothing planned"


def test_the_actions_and_evening_copy_follow_the_clock(qapp: QApplication) -> None:
    view = shown(qapp, OneThingView, "15:40")
    names = [button.objectName() for button in view.findChildren(QPushButton)]
    assert names == ["oneLate", "oneBack", *(f"oneDay{day}" for day in range(7))]
    assert view.findChild(QLabel, "oneEvening").text() == "Free from 8 PM until 10 PM"
    dial = shown(qapp, DayDialView, "15:40")
    assert dial.findChild(QLabel, "dialFreeLine").text() == "20 min free until 4:00 PM"


def test_dial_row_controls_act_on_the_matching_homework(qapp: QApplication) -> None:
    view = shown(qapp, DayDialView, "19:10")
    finished: list[str] = []
    focused: list[tuple[str, int]] = []
    view.finished_requested.connect(finished.append)
    view.focus_requested.connect(lambda block_id, day: focused.append((block_id, day)))
    view.findChild(QPushButton, "dialRowFinished2").click()
    view.findChild(QPushButton, "dialRowFocus2").click()
    assert finished == ["essay"]
    assert focused == [("essay-1", THURSDAY)]


def test_dial_actions_read_in_the_shared_order_when_homework_is_active(qapp: QApplication) -> None:
    view = shown(qapp, DayDialView, "19:10")
    actions = [
        view.findChild(QPushButton, name) for name in ("dialFinished", "dialFocus", "dialLate", "dialBack")
    ]
    assert [action.text() for action in actions] == [
        "Homework finished",
        "Start focus",
        "Running late",
        "Back to planning",
    ]


def test_running_late_disappears_without_homework_left(qapp: QApplication) -> None:
    blocks = [block("school", "locked", [3], "08:00", 390)]
    for view_type, prefix in ((OneThingView, "one"), (DayDialView, "dial")):
        view = shown(qapp, view_type, "15:40", blocks=blocks)
        assert view.findChild(QPushButton, f"{prefix}Late") is None
        assert view.findChild(QPushButton, f"{prefix}Back") is not None


def test_another_week_says_so_in_one_notice_and_calls_the_list_then(qapp: QApplication) -> None:
    one = shown(qapp, OneThingView, "15:40", 1024, 640, today=None)
    notice = "Go back to planning and open this week to see today."
    assert one.findChild(QLabel, "oneWeekNotice").text() == notice
    assert one.findChild(QLabel, "oneThenLabel").text() == "Then"
    dial = shown(qapp, DayDialView, "15:40", 1024, 640, today=None)
    assert dial.findChild(QLabel, "dialWeekNotice").text() == (
        "Not this week — Go back to planning and open this week to see today."
    )


def test_a_day_letter_starts_that_days_list_at_its_first_block(qapp: QApplication) -> None:
    # Space moves on to the next thing today; a day letter must start the chosen day at its first block.
    view = shown(qapp, OneThingView, "15:40")
    QTest.keyClick(view, Qt.Key.Key_Space)
    qapp.processEvents()
    assert view.findChild(QLabel, "oneTitle").accessibleName() == "Essay-1"
    QTest.mouseClick(view.findChild(QPushButton, "oneDay2"), Qt.MouseButton.LeftButton)
    qapp.processEvents()
    # Wednesday's first block is School at 08:00; a carried-over skip would show its second, Bio-1.
    assert view.findChild(QLabel, "oneTitle").accessibleName() == "School"
