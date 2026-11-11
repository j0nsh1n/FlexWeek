"""The current-time line in Material Week and Day (Jonathan, 2026-11-10): it runs through today's column
only, is drawn over every block, and its dot sits on that column's left edge. Today brings it back into
view, and the line moves when the app comes back to the front. The colour and the look where it crosses a
block are judged in the picture review (pictures/week_material.py).

Expected positions are relations to what a student sees: today's day header for the column, the blocks'
stacking for "over", the scroll area for "in view". Thursday 19:00 is the clock, the History essay (18:45
to 19:45) is the block running now.
"""

# ruff: noqa: F811
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPointF, Qt  # noqa: E402

from backend.tests.fake_clock import CLOCK  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_material import (  # noqa: E402
    NOW_DAY,
    _block_named,
    _bridge,
    _click,
    _named,
    _pump,
    _qml,
    _reset,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

EDGE = 1.5


def _scene_x(item: QObject, x: float = 0.0) -> float:
    return item.mapToScene(QPointF(x, 0)).x()


def _scene_y(item: QObject, y: float = 0.0) -> float:
    return item.mapToScene(QPointF(0, y)).y()


def _show_day(qapp, window) -> QObject:
    """Day for today (Thursday)."""
    root = _reset(window, qapp)
    window.session.open_day((_week_monday(window) + timedelta(days=NOW_DAY)).isoformat())
    _bridge(window).showPage("day")
    _pump(qapp, 60)
    return _qml(root, "materialDay")


def _line_and_dot(pane: QObject) -> tuple[QObject, QObject]:
    return _named(pane, "nowLine")[0], _named(pane, "nowDot")[0]


def _over_every_block(qapp, pane: QObject, focused: QObject | None = None) -> None:
    line, dot = _line_and_dot(pane)
    blocks = _named(pane, "weekBlock")
    assert blocks
    if focused is not None:
        focused.forceActiveFocus()
        _pump(qapp, 5)
        assert focused.property("activeFocus") is True
    for block in blocks:
        assert float(line.property("z")) > float(block.property("z")), "the line is over every block"
        assert float(dot.property("z")) > float(block.property("z")), "the dot is over every block"


def test_week_line_runs_through_todays_column_only(qapp, window) -> None:
    root = _reset(window, qapp)
    header = _named(root, "dayHeader")[NOW_DAY]
    line, _dot = _line_and_dot(root)
    assert abs(_scene_x(line) - _scene_x(header)) <= EDGE, "the line starts at today's column"
    assert abs(_scene_x(line, line.property("width")) - _scene_x(header, header.property("width"))) <= EDGE, (
        "and stops at its far edge"
    )


def test_week_line_and_dot_are_over_every_block_even_a_focused_one(qapp, window) -> None:
    root = _reset(window, qapp)
    _over_every_block(qapp, root)
    _over_every_block(qapp, root, focused=_block_named(root, "History essay"))
    line, _dot = _line_and_dot(root)
    assert float(_qml(root, "dropSlot").property("z")) > float(line.property("z")), (
        "a homework held over a slot still outlines it above the line"
    )


def test_week_dot_sits_on_todays_left_edge(qapp, window) -> None:
    root = _reset(window, qapp)
    header = _named(root, "dayHeader")[NOW_DAY]
    _line, dot = _line_and_dot(root)
    centre = _scene_x(dot, float(dot.property("width")) / 2)
    assert abs(centre - _scene_x(header)) <= EDGE


def test_day_line_fills_the_one_column_and_is_over_every_block(qapp, window) -> None:
    day = _show_day(qapp, window)
    line, dot = _line_and_dot(day)
    hours = _qml(day, "dayScroller")
    assert float(line.property("width")) > 0.8 * float(hours.property("width")), "one column: the whole width"
    centre = _scene_x(dot, float(dot.property("width")) / 2)
    assert abs(centre - _scene_x(line)) <= EDGE, "the dot is on the column's left edge"
    _over_every_block(qapp, day)
    _over_every_block(qapp, day, focused=_named(day, "weekBlock")[-1])


def _in_view(root: QObject, scroller_name: str) -> bool:
    scroller = _qml(root, scroller_name)
    line = _named(root, "nowLine")[0]
    top = _scene_y(scroller)
    return top <= _scene_y(line) <= top + float(scroller.property("height"))


def test_today_brings_the_line_back_when_this_week_is_open_and_scrolled_away(qapp, window) -> None:
    root = _reset(window, qapp)
    scroller = _qml(root, "weekScroller")
    wait_until(qapp, lambda: _in_view(root, "weekScroller"), what="the week to open on the line")
    scroller.setProperty("contentY", 0.0)
    _pump(qapp, 20)
    assert not _in_view(root, "weekScroller"), "the student scrolled the line out of sight"
    _click(window, _qml(root, "weekToday"))
    wait_until(qapp, lambda: _in_view(root, "weekScroller"), what="Today to bring the line into view")


def test_today_brings_the_line_back_when_the_student_returns_from_another_week(qapp, window) -> None:
    root = _reset(window, qapp)
    home = window.session.week_start
    scroller = _qml(root, "weekScroller")
    wait_until(qapp, lambda: _in_view(root, "weekScroller"), what="the week to open on the line")
    scroller.setProperty("contentY", 0.0)
    _pump(qapp, 20)
    _click(window, _qml(root, "weekNext"))
    wait_until(qapp, lambda: window.session.week_start != home and not window.session.busy)
    _click(window, _qml(root, "weekToday"))
    wait_until(qapp, lambda: window.session.week_start == home and not window.session.busy)
    wait_until(qapp, lambda: _in_view(root, "weekScroller"), what="Today to bring the line into view")


def test_the_clock_tick_does_not_chase_the_line_after_the_student_scrolls(qapp, window) -> None:
    root = _reset(window, qapp)
    scroller = _qml(root, "weekScroller")
    scroller.setProperty("contentY", 0.0)
    _pump(qapp, 20)
    CLOCK.set(CLOCK.now() + timedelta(minutes=20))
    window._tick_material_clock()
    _pump(qapp, 20)
    assert float(scroller.property("contentY")) == 0.0


def test_the_line_moves_when_the_app_comes_back_to_the_front(qapp, window) -> None:
    root = _reset(window, qapp)
    line, _dot = _line_and_dot(root)
    before_y, before_minute = _scene_y(line), int(_bridge(window).property("nowMinute"))
    moved = datetime.fromisoformat(window.session.week_start) + timedelta(days=NOW_DAY, hours=19, minutes=30)
    CLOCK.set(moved)
    window._application_state_changed(Qt.ApplicationState.ApplicationActive)
    _pump(qapp, 20)
    assert int(_bridge(window).property("nowMinute")) == before_minute + 30
    assert _scene_y(line) > before_y, "the line is drawn at the new time"
    assert _qml(root, "materialClock").property("text") == "19:30"
