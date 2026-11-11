"""Material Week and Day: a draw or a click on empty time lands on the time step the student chose
(5 or 15 minutes), the same setting dragging a homework card uses."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import timedelta

import pytest
from PySide6.QtCore import QObject, QPointF
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import _pref
from desktop.tests.week.test_material_drag_to_add_homework import (  # noqa: F401
    NOW_DAY,
    _choose,
    _click_at,
    _drag_pos,
    _grid_geometry,
    _pump,
    _qml,
    _reset,
    _week_monday,
    qapp,
    settled,
    window,
)


def _use_step(window: NativeWindow, qapp: QApplication, minutes: int) -> None:
    _pref(window, drag_step_min=minutes)
    window._material_page.publish()
    _pump(qapp)


def _minute_y(row: int, hour: int, minute: int) -> float:
    return (hour + minute / 60) * row


# A draw from 10:10 to 10:40 rounds each end to the nearest mark, 2.5 minutes from where the rounding flips:
# 10:15-10:45 on quarter hours (10:00 and 10:30 would be a round down), 10:10-10:40 on fives.
@pytest.mark.parametrize(("step", "start", "end"), [(15, "10:15", 10 * 60 + 45), (5, "10:10", 10 * 60 + 40)])
def test_a_draw_on_empty_week_time_lands_on_the_students_step(
    qapp: QApplication, window: NativeWindow, step: int, start: str, end: int
) -> None:
    root = _reset(window, qapp)
    _use_step(window, qapp, step)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", 0.0)
    _pump(qapp)
    x = gutter + saturday * day_width + day_width / 2
    p1 = hours_item.mapToScene(QPointF(x, _minute_y(row, 10, 10)))
    p2 = hours_item.mapToScene(QPointF(x, _minute_y(row, 10, 40)))
    _drag_pos(window, p1.toPoint(), p2.toPoint())
    _choose(window, root, "Add fixed time here")

    form = window._material_page.bridge.sheets.form
    assert (form["start"], form["end"]) == (start, end)


@pytest.mark.parametrize(("step", "start"), [(15, "10:15"), (5, "10:10")])
def test_a_click_on_empty_week_time_lands_on_the_students_step(
    qapp: QApplication, window: NativeWindow, step: int, start: str
) -> None:
    root = _reset(window, qapp)
    _use_step(window, qapp, step)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", float(8 * row))
    _pump(qapp)
    _click_at(window, hours_item, gutter + saturday * day_width + day_width / 2, _minute_y(row, 10, 10))
    _choose(window, root, "Add fixed time here")

    assert window._material_page.bridge.sheets.form["start"] == start


@pytest.mark.parametrize(("step", "start", "end"), [(15, "15:15", 15 * 60 + 45), (5, "15:10", 15 * 60 + 40)])
def test_a_draw_on_empty_day_time_lands_on_the_students_step(
    qapp: QApplication, window: NativeWindow, step: int, start: str, end: int
) -> None:
    _reset(window, qapp)
    _use_step(window, qapp, step)
    # Thursday, after School ends at 14:30.
    thursday = (_week_monday(window) + timedelta(days=NOW_DAY)).isoformat()
    window.session.open_day(thursday)
    settled(qapp, window)
    bridge = window._material_page.bridge
    bridge.showPage("day")
    _pump(qapp, 6)
    try:
        root: QObject = window._material_page.root
        scroller = _qml(root, "dayScroller")
        hours_item = scroller.childItems()[0].childItems()[0]
        day_pane = scroller.parentItem()
        gutter = int(day_pane.property("gutter"))
        row = int(day_pane.property("row"))
        # The grid first scrolls itself to the opening hour; the test's own scroll comes after it settles.
        _pump(qapp, 40)
        scroller.setProperty("contentY", float(12 * row))
        wait_until(qapp, lambda: float(scroller.property("contentY")) == float(12 * row), what="the scroll")
        _pump(qapp, 20)
        x = gutter + 200
        p1 = hours_item.mapToScene(QPointF(x, _minute_y(row, 15, 10)))
        p2 = hours_item.mapToScene(QPointF(x, _minute_y(row, 15, 40)))
        _drag_pos(window, p1.toPoint(), p2.toPoint())
        _choose(window, root, "Add fixed time here")

        form = bridge.sheets.form
        assert (form["start"], form["end"]) == (start, end)
    finally:
        bridge.sheets.forceClose()
        bridge.showPage("week")
        _pump(qapp, 4)


def test_a_draw_one_step_short_of_a_quarter_hour_still_offers_to_add_on_five_minute_steps(
    qapp: QApplication, window: NativeWindow
) -> None:
    """On 5-minute steps a 10-minute draw is a real range, as the plain look makes it: letting go offers
    to add there instead of doing nothing."""
    root = _reset(window, qapp)
    _use_step(window, qapp, 5)
    hours_item, row, gutter, day_width, saturday = _grid_geometry(root, window)
    _qml(root, "weekScroller").setProperty("contentY", 0.0)
    _pump(qapp)
    x = gutter + saturday * day_width + day_width / 2
    p1 = hours_item.mapToScene(QPointF(x, _minute_y(row, 10, 10)))
    p2 = hours_item.mapToScene(QPointF(x, _minute_y(row, 10, 20)))
    _drag_pos(window, p1.toPoint(), p2.toPoint())
    _choose(window, root, "Add fixed time here")

    form = window._material_page.bridge.sheets.form
    assert (form["start"], form["end"]) == ("10:10", 10 * 60 + 20)
