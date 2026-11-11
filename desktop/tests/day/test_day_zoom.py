# ruff: noqa: F811
"""Zooming the Material Day hour column: the keys, the plus button and Ctrl with the wheel change the
Day's hour row and leave Week's alone; the zoom is kept in the look file; the visible time stays where
the student put it, through a zoom, an evening zoom and a clock tick.

The hour row steps (56, 72, 96 at Comfortable) are the zoom's own states. How tall a row looks at each
density is a picture (pictures/_day_g01.py).
"""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.tests.fake_clock import FakeClock  # noqa: E402
from desktop.native.hours.zoom import sanitize_zoom  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import (  # noqa: E402
    bridge_of,
    click,
    day_item,
    look,
    open_day_page,
    seed_thursday,
    wheel,
)
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import pump, qml  # noqa: E402
from desktop.tests.window_support import look_file, qapp, settled  # noqa: E402, F401


@pytest.fixture()
def window(qapp: QApplication, open_light) -> NativeWindow:
    return seed_thursday(qapp, open_light((1280, 800)), hour=19, soccer=True)


def _ctrl(window: NativeWindow, key: Qt.Key) -> None:
    quick = window._material_page._quick
    QTest.keyClick(quick, key, Qt.KeyboardModifier.ControlModifier)
    pump(QApplication.instance())


def test_zoom_on_day_changes_the_day_hour_row_and_leaves_week_untouched(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = open_day_page(qapp, window)
    bridge = bridge_of(window)
    quick = window._material_page._quick
    quick.setFocus()
    pump(qapp)
    assert int(bridge.property("dayHourRow")) == 56
    assert int(bridge.property("hourRow")) == 56
    _ctrl(window, Qt.Key.Key_Equal)
    assert int(bridge.property("dayHourRow")) == 72
    assert int(bridge.property("hourRow")) == 56
    assert window._zoom["material.day"] == 72
    assert "material.week" not in window._zoom
    stored = json.loads(look_file().read_text())
    assert sanitize_zoom(stored.get("zoom"))["material.day"] == 72

    _ctrl(window, Qt.Key.Key_0)
    assert int(bridge.property("dayHourRow")) == 56
    assert "material.day" not in window._zoom

    plus = qml(day_item(root), "weekZoomIn")
    assert plus.property("accessName") == "Zoom in"
    click(window, plus)
    assert int(bridge.property("dayHourRow")) == 72
    assert int(bridge.property("hourRow")) == 56

    scroller = qml(day_item(root), "dayScroller")
    at = scroller.mapToScene(QPointF(68.0 + 40.0, 120.0))
    held_week = int(bridge.property("hourRow"))
    wheel(quick, at, 1)
    pump(qapp)
    assert int(bridge.property("dayHourRow")) == 96
    assert int(bridge.property("hourRow")) == held_week
    wheel(quick, at, -1, ctrl=False)
    pump(qapp)
    assert int(bridge.property("dayHourRow")) == 96


def test_the_compact_look_gives_day_and_week_the_same_smaller_hour_row(
    qapp: QApplication, window: NativeWindow
) -> None:
    open_day_page(qapp, window)
    bridge = bridge_of(window)
    comfortable = int(bridge.property("dayHourRow"))
    look(window, density="compact")
    pump(qapp)
    assert int(bridge.property("dayHourRow")) < comfortable
    assert int(bridge.property("dayHourRow")) == int(bridge.property("hourRow"))


def _no_blank_past_midnight(scroller: object, row: int) -> None:
    content_y = float(scroller.property("contentY"))
    view_h = float(scroller.property("height"))
    if 24 * row >= view_h:
        assert content_y + view_h <= 24 * row + 1, (content_y, view_h, row)


def test_an_evening_zoom_keeps_the_essay_and_no_blank_past_midnight(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Day opens with the evening near the top and room past midnight; zooming from there anchors a
    time in the day and never leaves midnight above the bottom while earlier time could show."""
    root = open_day_page(qapp, window)
    quick = window._material_page._quick
    quick.setFocus()
    pump(qapp)
    for expected, key in ((72, Qt.Key.Key_Equal), (96, Qt.Key.Key_Equal), (56, Qt.Key.Key_0)):
        _ctrl(window, key)
        row = int(bridge_of(window).property("dayHourRow"))
        assert row == expected
        scroller = qml(day_item(root), "dayScroller")
        _no_blank_past_midnight(scroller, row)
        content_y = float(scroller.property("contentY"))
        view_h = float(scroller.property("height"))
        assert content_y <= 18.75 * row and 19.75 * row <= content_y + view_h, (
            expected,
            content_y,
            view_h,
        )


def test_a_clock_tick_does_not_move_day_scroll_or_a_zoom_anchor(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    root = open_day_page(qapp, window)
    scroller = qml(day_item(root), "dayScroller")
    row = int(bridge_of(window).property("dayHourRow"))
    school_y = 8 * row
    scroller.setProperty("contentY", float(school_y))
    pump(qapp)
    held = float(scroller.property("contentY"))
    assert abs(held - school_y) < 2
    clock.move(minutes=1)
    bridge_of(window).refresh()
    pump(qapp)
    assert abs(float(scroller.property("contentY")) - held) < 2

    view_y = float(scroller.property("height")) / 2
    minute = ((float(scroller.property("contentY")) + view_y) / row) * 60
    quick = window._material_page._quick
    quick.setFocus()
    pump(qapp)
    _ctrl(window, Qt.Key.Key_Equal)
    row = int(bridge_of(window).property("dayHourRow"))
    assert row == 72
    after_zoom = ((float(scroller.property("contentY")) + view_y) / row) * 60
    assert abs(after_zoom - minute) < 1
    bridge_of(window).refresh()
    pump(qapp)
    after_tick = ((float(scroller.property("contentY")) + view_y) / row) * 60
    assert abs(after_tick - minute) < 1


def test_day_steps_through_the_two_closer_levels_and_stops_at_256(
    qapp: QApplication, window: NativeWindow
) -> None:
    open_day_page(qapp, window)
    bridge = bridge_of(window)
    quick = window._material_page._quick
    quick.setFocus()
    pump(qapp)
    seen = [int(bridge.property("dayHourRow"))]
    for _ in range(6):
        _ctrl(window, Qt.Key.Key_Equal)
        seen.append(int(bridge.property("dayHourRow")))
    assert seen == [56, 72, 96, 128, 192, 256, 256]
    assert bridge.property("canZoomIn") is False
    for _ in range(8):
        _ctrl(window, Qt.Key.Key_Minus)
    assert int(bridge.property("dayHourRow")) == 32
