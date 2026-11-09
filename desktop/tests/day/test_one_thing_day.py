"""One thing, the day screen, drawn as 0.17's Countdown. It is tested as a student meets it: what it
says at a given minute, what each button asks the window for, how the keys walk the day, and that
every option in its Layout section changes what is on screen. How it looks is judged on the pictures
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
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from desktop.native.layouts.base import Scene, rules
    from desktop.native.layouts.one_thing import OneThingView
    from desktop.native.weekmodel import build_week, length_label
    from desktop.tests.day.support_one_thing import (
        THURSDAY,
        buttons,
        counts,
        full_title,
        press,
        says,
        scene,
        shown,
        then,
    )
    from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-one-thing-test"])
    yield application


def test_during_school_it_counts_down_what_is_left_of_it(qapp: QApplication) -> None:
    view = shown(qapp, "13:40")
    assert says(view) == ("Now", "School", "08:00–14:30")
    assert counts(view) == ("50", round(50 / 60, 3))
    # The demo's screen A has no date or count line; the Then list heads itself "Later today".
    assert view.findChild(QLabel, "oneThenLabel").text() == "Later today"
    assert then(view) == ["18:00 Dinner 30 min", "18:45 Essay-1 1 h", "20:00 Chem-1 1 h 30 min"]


def test_a_fixed_block_offers_no_homework_buttons(qapp: QApplication) -> None:
    assert buttons(shown(qapp, "13:40")) == ["oneLate", "oneBack"]


def test_during_homework_it_offers_finishing_and_focus(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    assert says(view) == ("Now", "Essay-1", "18:45–19:45")
    assert buttons(view) == ["oneFinished", "oneFocus", "oneLate", "oneBack"]


def test_during_homework_homework_finished_is_the_one_filled_button(qapp: QApplication) -> None:
    view = shown(qapp, "19:00", size=(1280, 800))
    day = [
        button for button in view.findChildren(QPushButton) if not button.objectName().startswith("oneDay")
    ]
    assert [button.objectName() for button in day if button.property("kind") == "main"] == ["oneFinished"]


def test_the_time_left_is_written_under_the_title_while_homework_is_on(qapp: QApplication) -> None:
    view = shown(qapp, "19:00", size=(1280, 800))
    left = view.findChild(QLabel, "oneLeft")
    assert left is not None and left.isVisibleTo(view)
    assert left.text() == f"{length_label(45)} left"
    later = shown(qapp, "15:00", size=(1280, 800))
    assert later.findChild(QLabel, "oneLeft").isVisibleTo(later) is False


def test_between_blocks_it_says_what_is_next_and_when(qapp: QApplication) -> None:
    assert says(shown(qapp, "15:00")) == ("Up next", "Dinner", "18:00–18:30")


def test_when_the_day_is_over_it_says_what_tomorrow_starts_with(qapp: QApplication) -> None:
    view = shown(qapp, "22:30")
    assert says(view)[0] == "Nothing left today"
    assert full_title(view) == "Nothing else scheduled today"
    line = view.findChild(QLabel, "oneLine")
    assert line.text() == ""
    assert line.accessibleName() == "Tomorrow starts with School at 08:00"
    assert line.toolTip() == "Tomorrow starts with School at 08:00"
    assert view.findChild(QLabel, "oneLabel").isVisibleTo(view) is True
    assert counts(view) == ("", 0.0)
    assert then(view) == []
    assert buttons(view) == ["oneBack"]


def test_in_another_week_it_does_not_pretend_to_know_today(qapp: QApplication) -> None:
    view = shown(qapp, "13:40", today=None)
    assert says(view) == ("Not this week", "Day screens show today", "")
    assert buttons(view) == ["oneBack"]


def test_each_button_asks_the_window_for_exactly_one_thing(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    asked: list[tuple] = []
    view.finished_requested.connect(lambda homework: asked.append(("finished", homework)))
    view.focus_requested.connect(lambda block, day: asked.append(("focus", block, day)))
    view.late_requested.connect(lambda: asked.append(("late",)))
    view.back_requested.connect(lambda: asked.append(("back",)))
    for name in ("oneFinished", "oneFocus", "oneLate", "oneBack"):
        view.findChild(QPushButton, name).click()
    assert asked == [("finished", "essay"), ("focus", "essay-1", THURSDAY), ("late",), ("back",)]


def test_space_walks_through_the_rest_of_the_day_and_comes_back_round(qapp: QApplication) -> None:
    view = shown(qapp, "13:40")
    seen = []
    for _ in range(5):
        press(view, Qt.Key.Key_Space)
        seen.append(says(view)[:2])
    assert seen == [
        ("Up next", "Dinner"),
        ("Later today", "Essay-1"),
        ("Later today", "Chem-1"),
        ("Now", "School"),
        ("Up next", "Dinner"),
    ]


def test_enter_opens_the_thing_on_screen(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    press(view, Qt.Key.Key_Return)
    assert opened == ["essay-1"]


def test_a_new_minute_keeps_the_place_but_a_changed_week_starts_over(qapp: QApplication) -> None:
    view = shown(qapp, "13:40")
    press(view, Qt.Key.Key_Space)
    view.show_week(scene("13:41"))
    assert says(view)[:2] == ("Up next", "Dinner")
    done = [{**block, "completed": True} if block["id"] == "essay-1" else block for block in BLOCKS]
    base = scene("13:41")
    view.show_week(
        Scene(build_week(WEEK, done, HOMEWORK, TRACE), THURSDAY, base.minute, base.options, base.tokens)
    )
    assert says(view)[:2] == ("Now", "School")


def test_option_lead_with_what_is_next_skips_what_is_on_now(qapp: QApplication) -> None:
    view = shown(qapp, "13:40", lead="next")
    assert says(view) == ("Up next", "Dinner", "18:00–18:30")
    assert counts(view) == ("4:20", 1.0)


def test_option_buttons_hidden_leaves_only_the_way_back(qapp: QApplication) -> None:
    assert buttons(shown(qapp, "19:00", actions="hide")) == ["oneBack"]


def test_every_selector_in_a_list_is_tied_to_the_view() -> None:
    assert rules("layoutOne", {"#a, #b": "color: red;"}) == "#layoutOne #a, #layoutOne #b { color: red; }"


def test_an_unchanged_scene_leaves_the_screen_alone(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    before = view.findChild(QPushButton, "oneBack")
    view.show_week(scene("19:00"))
    assert view.findChild(QPushButton, "oneBack") is before


def test_a_new_minute_does_not_take_the_keyboard_away(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    view.activateWindow()
    view.findChild(QPushButton, "oneLate").setFocus()
    qapp.processEvents()
    view.show_week(scene("19:01"))
    qapp.processEvents()
    assert QApplication.focusWidget() is view.findChild(QPushButton, "oneLate")


def test_a_long_title_is_shortened_with_an_ellipsis_and_read_out_whole(qapp: QApplication) -> None:
    """Inside the ring there is room for two lines. The rest is shortened with an ellipsis rather than
    cut off or run into the number, and the whole name is in its tooltip and read out."""
    whole = "History essay outline and the annotated bibliography"
    long_title = [{**block, "title": whole} if block["id"] == "essay-1" else block for block in BLOCKS]
    base = scene("19:00")
    view = OneThingView()
    view.resize(1366, 430)
    view.show_week(
        Scene(build_week(WEEK, long_title, HOMEWORK, TRACE), THURSDAY, base.minute, base.options, base.tokens)
    )
    view.show()
    qapp.processEvents()
    title = view.findChild(QLabel, "oneTitle")
    assert title.text().count("\n") <= 1 and title.text().endswith("…")
    assert (title.toolTip(), title.accessibleName()) == (whole, whole)


def test_in_a_short_window_the_then_list_keeps_its_rows(qapp: QApplication) -> None:
    roomy = shown(qapp, "13:40")
    assert len(then(roomy)) == 3
    assert then(shown(qapp, "13:40", size=(1366, 560))) == then(roomy)


@pytest.mark.parametrize("width,height", [(1024, 640), (1280, 800), (1440, 900)])
@pytest.mark.parametrize("large", [False, True])
@pytest.mark.parametrize("line_case", ["timed", "empty", "tomorrow"])
def test_the_line_under_the_title_keeps_its_words_at_every_size(
    qapp: QApplication, width: int, height: int, large: bool, line_case: str
) -> None:
    """Whatever the room, the line says the same to a screen reader, and when it is too long to be
    written it is in the tooltip."""
    minute = {"timed": "13:40", "empty": "13:40", "tomorrow": "22:30"}[line_case]
    base = scene(minute)
    view = OneThingView()
    view.resize(width, height)
    week = build_week(WEEK, [], {}, TRACE) if line_case == "empty" else base.week
    view.show_week(
        Scene(week, base.today, base.minute, base.options, base.tokens, scale=1.2 if large else 1.0)
    )
    view.show()
    qapp.processEvents()
    line = view.findChild(QLabel, "oneLine")
    expected = {
        "timed": "08:00–14:30",
        "empty": "No homework added",
        "tomorrow": "Tomorrow starts with School at 08:00",
    }[line_case]
    assert line.accessibleName() == expected
    if line.text() == "":
        assert line.toolTip() == expected
