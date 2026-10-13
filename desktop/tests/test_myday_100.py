"""My day A and B hold their measured layout and clock behavior at every demo size."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

from desktop.tests.test_weekmodel import HOMEWORK, TRACE, WEEK, block

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QScrollArea

    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.dial import DayDialView, DialFace
    from desktop.native.layouts.one_thing import OneThingView
    from desktop.native.layouts.registry import options_for, tokens_for
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week, minute_of, set_clock_24h

THURSDAY = 3
DEMO_BLOCKS = [
    block("school", "locked", [0, 1, 2, 3, 4], "08:00", 390),
    block("bio-1", "flexible", [2], "17:00", 60, assignment_id="bio"),
    block("soccer", "locked", [3], "16:00", 90, category="exercise"),
    block("essay-1", "flexible", [3], "19:00", 60, assignment_id="essay"),
    block("poster-1", "flexible", [], None, 60, assignment_id="poster"),
    block("math-1", "flexible", [], None, 60, assignment_id="math"),
]
DEMO_HOMEWORK = {
    **HOMEWORK,
    "math": {**HOMEWORK["math"], "title": "Math worksheet", "completed": False},
    "poster": {**HOMEWORK["poster"], "title": "Science poster"},
}


def on_one_line(text_label: QLabel) -> bool:
    """True when the label cannot wrap and is at least as wide as its own text, so nothing is cut."""
    return not text_label.wordWrap() and text_label.width() >= text_label.sizeHint().width()


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-myday-100-test"])
    yield application


@pytest.fixture(autouse=True)
def demo_clock() -> Iterator[None]:
    set_clock_24h(False)
    yield
    set_clock_24h(True)


def shown(
    qapp: QApplication,
    view_type: type[OneThingView] | type[DayDialView],
    clock: str,
    width: int = 1280,
    height: int = 800,
    large: bool = False,
    dark: bool = False,
    blocks: list[dict] | None = None,
) -> OneThingView | DayDialView:
    layout = "one" if view_type is OneThingView else "dial"
    options = options_for(None, layout)
    palette = resolved_palette("light-frost", dark, None, "default")
    week = build_week(WEEK, DEMO_BLOCKS if blocks is None else blocks, DEMO_HOMEWORK)
    view = view_type()
    view.resize(width, height)
    view.show_week(
        Scene(
            week,
            THURSDAY,
            minute_of(clock),
            options,
            tokens_for(layout, options["colour"], palette),
            scale=1.2 if large else 1.0,
        )
    )
    view.show()
    qapp.processEvents()
    return view


@pytest.mark.parametrize("width,height", [(1024, 640), (1280, 800), (1440, 900)])
@pytest.mark.parametrize("large,dark", [(False, False), (False, True), (True, False), (True, True)])
def test_one_thing_ring_matches_demo_tier_and_keeps_one_action_row(
    qapp: QApplication, width: int, height: int, large: bool, dark: bool
) -> None:
    view = shown(qapp, OneThingView, "19:10", width, height, large, dark)
    expected_ring = 440 if width == 1440 else 320 if width == 1280 else 200 if large else 280
    ring = view._ring
    assert ring.size().width() == expected_ring
    names = ("oneFinished", "oneFocus", "oneLate", "oneBack")
    actions = [view.findChild(QPushButton, name) for name in names]
    assert all(action is not None and action.isVisibleTo(view) for action in actions)
    assert len({action.mapTo(view, action.rect().center()).y() for action in actions if action}) == 1
    assert view.findChild(QLabel, "oneWaiting").parentWidget().height() == 36


@pytest.mark.parametrize("width,height", [(1024, 640), (1280, 800), (1440, 900)])
@pytest.mark.parametrize("large,dark", [(False, False), (False, True), (True, False), (True, True)])
def test_one_thing_then_row_time_stays_one_piece(
    qapp: QApplication, width: int, height: int, large: bool, dark: bool
) -> None:
    # At 15:40 the demo's Soccer is next and the History essay is the one Then row.
    view = shown(qapp, OneThingView, "15:40", width, height, large, dark)
    times = view.findChildren(QLabel, "oneRowTime")
    assert [time.text() for time in times] == ["7:00 PM"]
    assert on_one_line(times[0])


@pytest.mark.parametrize("width,height", [(1024, 640), (1280, 800), (1440, 900)])
@pytest.mark.parametrize("large,dark", [(False, False), (False, True), (True, False), (True, True)])
def test_day_dial_keeps_the_clock_rows_and_action_row_at_demo_sizes(
    qapp: QApplication, width: int, height: int, large: bool, dark: bool
) -> None:
    view = shown(qapp, DayDialView, "15:40", width, height, large, dark)
    rows = view.findChildren(QPushButton)
    row_times = [row.findChild(QLabel, "dialRowTime") for row in rows if row.property("kind") == "row"]
    assert [time.text() for time in row_times] == [
        "8 AM–2:30 PM",
        "4–5:30 PM",
        "7–8 PM",
    ]
    for time in row_times:
        assert on_one_line(time)
    action_names = ("dialLate", "dialBack")
    actions = [view.findChild(QPushButton, name) for name in action_names]
    assert all(action is not None and action.isVisibleTo(view) for action in actions)
    assert len({action.mapTo(view, action.rect().center()).y() for action in actions if action}) == 1
    assert view.findChild(QLabel, "dialWaitingStrip").parentWidget().height() == 36
    assert view.findChild(DialFace, "dialFace").width() == 320
    face = view.findChild(DialFace, "dialFace")
    arcs = {face.block_at(point).block_id for point in _arc_points(face)}
    assert arcs == {row.property("blockId") for row in rows if row.property("kind") == "row"}
    assert view.findChild(QPushButton, "dialRowFinished2") is not None
    # The demo gives Start focus to the current or next row only; at 15:40 that is Soccer, not the essay.
    assert view.findChild(QPushButton, "dialRowFocus2") is None


def _arc_points(face: DialFace) -> list:
    return [
        point
        for minute in (8 * 60 + 30, 16 * 60 + 30, 19 * 60 + 30)
        if (point := face.track.point_for(minute)) is not None
    ]


def test_one_thing_then_list_scrolls_after_four_rows(qapp: QApplication) -> None:
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
    scroll = view.findChild(QScrollArea, "oneThenScroll")
    assert len(view.findChildren(QLabel, "oneRowTime")) == 6
    assert scroll.widget().height() > scroll.viewport().height()
    fourth = view.findChildren(QFrame, "oneRow")[3]
    assert fourth.mapTo(scroll.viewport(), fourth.rect().bottomLeft()).y() < scroll.viewport().height()
    assert scroll.maximumHeight() <= 220


def test_day_letters_switch_the_displayed_day(qapp: QApplication) -> None:
    view = shown(qapp, OneThingView, "15:40")
    changed: list[str] = []
    view.watched_day_changed.connect(changed.append)
    QTest.mouseClick(view.findChild(QPushButton, "oneDay0"), Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert changed == ["2026-09-14"]
    assert view.findChild(QLabel, "oneLabel").text() == "Mon"


def test_monday_is_chosen_and_other_days_offer_only_back_to_planning(qapp: QApplication) -> None:
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


def test_dial_marks_the_next_row_and_empty_then_says_so(qapp: QApplication) -> None:
    view = shown(qapp, DayDialView, "15:40")
    rows = [row for row in view.findChildren(QPushButton) if row.property("kind") == "row"]
    tags = [
        (row.property("blockId"), [word.text() for word in row.findChildren(QLabel, "dialRowTagText")])
        for row in rows
    ]
    assert tags == [("school", ["Done"]), ("soccer", ["Up next"]), ("essay-1", [])]
    empty = shown(qapp, OneThingView, "13:00", blocks=[block("school", "locked", [3], "08:00", 390)])
    assert empty.findChild(QLabel, "oneThenEmpty").text() == "Nothing planned"


def test_shared_action_visibility_and_evening_copy_follow_the_clock(qapp: QApplication) -> None:
    view = shown(qapp, OneThingView, "15:40")
    names = [button.objectName() for button in view.findChildren(QPushButton)]
    assert names == [*(f"oneDay{day}" for day in range(7)), "oneLate", "oneBack"]
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


def test_dial_actions_follow_the_shared_order_when_homework_is_active(qapp: QApplication) -> None:
    view = shown(qapp, DayDialView, "19:10")
    actions = [
        view.findChild(QPushButton, name)
        for name in ("dialFinished", "dialFocus", "dialLate", "dialBack")
    ]
    assert [action.text() for action in actions] == [
        "Homework finished",
        "Start focus",
        "Running late",
        "Back to planning",
    ]
    assert len({action.mapTo(view, action.rect().center()).y() for action in actions}) == 1


def test_running_late_disappears_without_homework_left(qapp: QApplication) -> None:
    blocks = [block("school", "locked", [3], "08:00", 390)]
    for view_type, prefix in ((OneThingView, "one"), (DayDialView, "dial")):
        view = shown(qapp, view_type, "15:40", blocks=blocks)
        assert view.findChild(QPushButton, f"{prefix}Late") is None
        assert view.findChild(QPushButton, f"{prefix}Back") is not None


def test_another_week_notice_stays_on_one_line(qapp: QApplication) -> None:
    view = OneThingView()
    options = options_for(None, "one")
    palette = resolved_palette("light-frost", False, None, "default")
    week = build_week(WEEK, DEMO_BLOCKS, HOMEWORK, TRACE)
    view.resize(1024, 640)
    view.show_week(
        Scene(week, None, minute_of("15:40"), options, tokens_for("one", options["colour"], palette))
    )
    view.show()
    qapp.processEvents()
    notice = view.findChild(QLabel, "oneWeekNotice")
    assert notice.text() == "Go back to planning and open this week to see today."
    assert on_one_line(notice)

    dial = DayDialView()
    options = options_for(None, "dial")
    palette = resolved_palette("light-frost", False, None, "default")
    dial.resize(1024, 640)
    dial.show_week(
        Scene(week, None, minute_of("15:40"), options, tokens_for("dial", options["colour"], palette))
    )
    dial.show()
    qapp.processEvents()
    dial_notice = dial.findChild(QLabel, "dialWeekNotice")
    assert dial_notice.text() == "Not this week — Go back to planning and open this week to see today."
    assert on_one_line(dial_notice)


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


def test_another_week_says_then_not_later_today(qapp: QApplication) -> None:
    view = OneThingView()
    options = options_for(None, "one")
    palette = resolved_palette("light-frost", False, None, "default")
    week = build_week(WEEK, DEMO_BLOCKS, DEMO_HOMEWORK)
    view.resize(1024, 640)
    scene = Scene(week, None, minute_of("15:40"), options, tokens_for("one", options["colour"], palette))
    view.show_week(scene)
    view.show()
    qapp.processEvents()
    assert view.findChild(QLabel, "oneThenLabel").text() == "Then"
