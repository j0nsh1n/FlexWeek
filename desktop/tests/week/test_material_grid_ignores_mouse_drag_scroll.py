"""Pressing and dragging with the mouse does not pan the Material Week or Day grid (it fights drag-to-create).
The wheel and the keyboard still scroll it.

Expected values come from the requirement: a mouse drag leaves the scroll position where it was, wherever
it starts (the hour column, a block, free time); a wheel step and moving the keyboard focus to a block that
is out of view each change it. A touchscreen drag must still flick the grid, but QTest's touch events do not
reach a Flickable on the offscreen platform (checked: they move it on neither the old code nor the new), so
that one is checked by hand, not here.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import pump, qml  # noqa: E402
from desktop.tests.sheets.support_material_sheets import (  # noqa: E402
    block_named,
    bridge,
    material_week,
    week_monday,
)
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_zoom import wheel  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

THURSDAY = 3
SCREENS = ["week", "day"]


def screen_scroller(qapp, window: NativeWindow, screen: str) -> tuple[QObject, QObject]:
    """Material on Week or on Day (opened on Thursday): the QML root and the grid's Flickable, scrolled to
    a place in the day where it can move both ways."""
    root = material_week(qapp, window)
    name = "weekScroller"
    if screen == "day":
        window.session.open_day((week_monday(window) + timedelta(days=THURSDAY)).isoformat())
        bridge(window).showPage("day")
        pump(qapp)
        name = "dayScroller"
        wait_until(qapp, lambda: root.findChild(QObject, name) is not None)
    scroller = qml(root, name)
    scroller.setProperty("contentY", 300.0)
    pump(qapp)
    assert float(scroller.property("contentY")) == 300.0
    return root, scroller


def scene_point(scroller: QObject, x: float, y: float) -> QPoint:
    spot = scroller.mapToScene(QPointF(x, y))
    return QPoint(int(spot.x()), int(spot.y()))


def mouse_drag(window: NativeWindow, start: QPoint, dy: int) -> None:
    quick = window._material_page._quick
    app = QApplication.instance()
    QTest.mouseMove(quick, start)
    pump(app, 4)
    QTest.mousePress(quick, Qt.MouseButton.LeftButton, pos=start)
    pump(app, 4)
    for step in range(1, 9):
        QTest.mouseMove(quick, QPoint(start.x(), start.y() + dy * step // 8))
        pump(app, 2)
    QTest.mouseRelease(quick, Qt.MouseButton.LeftButton, pos=QPoint(start.x(), start.y() + dy))
    pump(app, 6)


@pytest.mark.parametrize("screen", SCREENS)
def test_the_grid_takes_no_mouse_button_for_flicking(qapp, window: NativeWindow, screen: str) -> None:
    """Qt's own switch for it (Flickable.acceptedButtons, since Qt 6.9): a touchscreen is not a mouse
    button, so it still flicks. On the offscreen platform QTest's mouse drags do not pan the grid even
    with the switch off, so the drag tests below guard the behaviour and this one names the cause."""
    _root, scroller = screen_scroller(qapp, window, screen)
    assert scroller.property("acceptedButtons") == Qt.MouseButton.NoButton


@pytest.mark.parametrize("screen", SCREENS)
def test_a_mouse_drag_on_the_hour_column_does_not_scroll(qapp, window: NativeWindow, screen: str) -> None:
    _root, scroller = screen_scroller(qapp, window, screen)
    mouse_drag(window, scene_point(scroller, 30, 300), -150)
    assert float(scroller.property("contentY")) == 300.0


@pytest.mark.parametrize("screen", SCREENS)
def test_a_mouse_drag_that_starts_on_a_block_does_not_scroll(qapp, window: NativeWindow, screen: str) -> None:
    root, scroller = screen_scroller(qapp, window, screen)
    block = block_named(root, "School")
    inside = block.mapToScene(QPointF(block.width() / 2, 120))
    start = QPoint(int(inside.x()), int(inside.y()))
    mouse_drag(window, start, -150)
    assert float(scroller.property("contentY")) == 300.0


@pytest.mark.parametrize("screen", SCREENS)
def test_dragging_across_free_time_still_offers_to_add_there_and_does_not_scroll(
    qapp, window: NativeWindow, screen: str
) -> None:
    _root, scroller = screen_scroller(qapp, window, screen)
    # Before School starts (08:00), in a column with nothing in it: Saturday in Week, anywhere in Day.
    x = scroller.width() * (0.85 if screen == "week" else 0.5)
    mouse_drag(window, scene_point(scroller, x, 70), 40)
    assert float(scroller.property("contentY")) == 300.0
    menu = qml(window._material_page.root, "blockMenu")
    assert menu.property("open") is True


@pytest.mark.parametrize("screen", SCREENS)
def test_the_wheel_still_scrolls(qapp, window: NativeWindow, screen: str) -> None:
    _root, scroller = screen_scroller(qapp, window, screen)
    at = scroller.mapToScene(QPointF(scroller.width() / 2, 200))
    wheel(window._material_page._quick, at, -1, ctrl=False)
    # The wheel eases the grid to its place over a few frames.
    wait_until(qapp, lambda: float(scroller.property("contentY")) != 300.0, what="the wheel to scroll")


@pytest.mark.parametrize("screen", SCREENS)
def test_moving_the_keyboard_to_a_block_out_of_view_scrolls_to_it(
    qapp, window: NativeWindow, screen: str
) -> None:
    root, scroller = screen_scroller(qapp, window, screen)
    scroller.setProperty("contentY", 0.0)
    pump(qapp)
    essay = block_named(root, "History essay")
    essay.forceActiveFocus()
    pump(qapp, 10)
    assert float(scroller.property("contentY")) > 0.0
