"""Seven lanes whose time runs across (Mission control's week): both ends of the day can be reached,
the time asked for is at the left, the lanes keep it when a design parks them between renders or the
focus moves on, a drag at the page's edge scrolls the page, and a plan eases the lanes to its homework."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget  # noqa: E402

from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week import support_zoom  # noqa: E402
from desktop.tests.week.support_zoom import (  # noqa: E402
    ESSAY,
    HOSTS,
    MONDAY,
    ManualTime,
    a_lane_week,
    a_side,
    minute_across,
    settle,
)

qapp = support_zoom.qapp  # fixtures are found by their name in the test module
manual_time = support_zoom.manual_time


def lanes_beside_a_panel(qapp: QApplication):
    """The lanes and a panel in a row, shown and active, scrolled to 19:00 and holding the focus, as
    Mission lays them out after a drag."""
    scroll = a_lane_week(qapp)
    host = QWidget()
    HOSTS.append(host)
    row = QHBoxLayout(host)
    row.addWidget(scroll, 1)
    side = a_side(host)
    row.addWidget(side)
    host.move(0, 0)
    host.resize(800, 480)
    host.show()
    settle(qapp)
    scroll.restore({"lanes.week": 96})
    scroll.scroll_to(19 * 60, above=0)
    host.activateWindow()
    wait_until(qapp, host.isActiveWindow, what="the host window becoming active")
    scroll.canvas.setFocus(Qt.FocusReason.MouseFocusReason)
    settle(qapp)
    return scroll, host, row, side


def test_both_ends_of_a_lanes_day_can_be_reached(qapp: QApplication) -> None:
    scroll = a_lane_week(qapp)
    for level in scroll.scale.levels:
        scroll.restore({"lanes.week": level})
        scroll.canvas.reveal(3, 0, 60)
        settle(qapp)
        assert scroll.canvas.in_view(3, 0), f"00:00 at {level} px an hour"
        scroll.canvas.reveal(3, 23 * 60, 24 * 60)
        settle(qapp)
        assert scroll.canvas.in_view(3, 24 * 60), f"24:00 at {level} px an hour"


def test_scrolling_the_lanes_to_a_time_puts_it_at_the_left(qapp: QApplication) -> None:
    scroll = a_lane_week(qapp)
    scroll.scroll_to(6 * 60, above=0)
    settle(qapp)
    assert 5 * 60 + 45 <= minute_across(scroll, 0) <= 6 * 60 + 15, "06:00 is at the left"


@pytest.mark.parametrize("new_side", [False, True])
def test_lanes_keep_their_time_when_a_design_parks_them_between_renders(
    qapp: QApplication, new_side: bool
) -> None:
    """Mission keeps its hours between renders and parks them on each one: hidden, out of its layout,
    back in, shown. The canvas still has the focus from the drag just finished, and hiding a scroll
    area that holds the focus moves it on and scrolls the hours to their middle. Mission also builds
    a new panel beside them on each render, which Qt shows only after the hours, so they are shown
    wider than they end up, too wide for 19:00 to be at the left. They must come back where they
    were, so the block just moved is still on screen."""
    scroll, host, row, side = lanes_beside_a_panel(qapp)
    assert QApplication.focusWidget() is scroll.canvas
    assert 18 * 60 + 45 <= minute_across(scroll, 0) <= 19 * 60 + 15, "19:00 is at the left"
    width = scroll.viewport().width()
    scroll.hide()
    row.removeWidget(scroll)
    if new_side:
        row.removeWidget(side)
        side.deleteLater()
        side = a_side(host)
    row.insertWidget(0, scroll, 1)
    if new_side:
        row.addWidget(side)
    scroll.show()
    settle(qapp)
    assert scroll.viewport().width() == width
    at = minute_across(scroll, 0)
    assert 18 * 60 + 45 <= at <= 19 * 60 + 15, (
        f"the lanes came back at {int(at) // 60:02d}:{int(at) % 60:02d}"
    )


def test_tab_moves_the_focus_on_and_leaves_the_hours_where_they_are(qapp: QApplication) -> None:
    """A scroll area shows the child that had the focus when the focus moves on, which for hours
    longer than what shows means jumping to their middle. Tab must only move the focus."""
    scroll, _host, _row, _side = lanes_beside_a_panel(qapp)
    QTest.keyClick(scroll.canvas, Qt.Key.Key_Tab)
    settle(qapp)
    at = minute_across(scroll, 0)
    assert 18 * 60 + 45 <= at <= 19 * 60 + 15, (
        f"after Tab the lanes start at {int(at) // 60:02d}:{int(at) % 60:02d}"
    )
    assert QApplication.focusWidget() is not scroll.canvas, "Tab left the focus on the hours"


def test_resting_at_the_edge_of_the_page_around_the_lanes_scrolls_the_page(qapp: QApplication) -> None:
    """Lanes that scroll sideways on a page that scrolls down when the window is short, as 0.16's
    Timeline laid its week out. Resting at the page's bottom edge over the lanes scrolls the page,
    which the lanes cannot, so a block can be carried to a day below the fold; resting at the lanes'
    right edge still scrolls the lanes.

    The hand starts scrolling after the pointer rests at an edge for its dwell, which it measures on
    the system clock, so these wait on the bars moving."""
    scroll = a_lane_week(qapp)
    scroll.canvas.set_week(
        build_week(MONDAY, [{**ESSAY, "days": [1], "start": "10:00"}], {}, None).occurrences
    )
    content = QWidget()
    column = QVBoxLayout(content)
    column.setContentsMargins(0, 0, 0, 0)
    column.addWidget(scroll)
    scroll.setFixedHeight(420)
    page = QScrollArea()
    HOSTS.append(page)
    page.setWidgetResizable(True)
    page.setWidget(content)
    page.move(0, 0)
    page.resize(760, 250)
    page.show()
    settle(qapp)
    scroll.scroll_to(10 * 60)
    settle(qapp)
    down, across = page.verticalScrollBar(), scroll.horizontalScrollBar()
    assert down.maximum() > 0 and down.value() == 0, "the page is too short for the lanes"
    assert 0 < across.value() < across.maximum(), "the lanes can scroll on through the day"

    canvas = scroll.canvas
    held = Qt.MouseButton.LeftButton

    def send(kind: QEvent.Type, at: QPoint) -> None:
        event = QMouseEvent(
            kind, QPointF(canvas.mapFromGlobal(at)), QPointF(at), held, held, Qt.KeyboardModifier.NoModifier
        )
        QApplication.sendEvent(canvas, event)

    start = canvas.point_for(1, 10 * 60 + 30)
    send(QEvent.Type.MouseButtonPress, start)
    send(QEvent.Type.MouseMove, start + QPoint(20, 0))
    assert canvas.hand.preview is not None, "the essay was not picked up"
    middle = scroll.viewport().width() // 2
    bottom = page.viewport().mapToGlobal(QPoint(0, page.viewport().height() - 10)).y()
    send(QEvent.Type.MouseMove, QPoint(scroll.viewport().mapToGlobal(QPoint(middle, 0)).x(), bottom))
    wait_until(
        qapp,
        lambda: down.value() > 0,
        timeout=3.0,
        what="rested at the page's bottom edge over the lanes: the page scrolls down",
    )

    port = page.viewport()
    right = scroll.viewport().mapToGlobal(QPoint(scroll.viewport().width() - 10, 0)).x()
    was = across.value()
    send(QEvent.Type.MouseMove, QPoint(right, port.mapToGlobal(QPoint(0, port.height() // 2)).y()))
    wait_until(
        qapp,
        lambda: across.value() > was,
        timeout=3.0,
        what="rested at the lanes' right edge: the lanes scroll on",
    )
    send(QEvent.Type.MouseButtonRelease, start)
    canvas.hand.cancel()


def test_after_a_plan_the_hours_ease_to_homework_off_screen_and_stay_for_homework_on_it(
    qapp: QApplication, manual_time: ManualTime
) -> None:
    """Grok Bot's 0.17.0 audit (T7): after Plan the grid jumped, even to homework already in sight."""
    scroll = a_lane_week(qapp)
    # About seven hours show, so 17:00 is off screen from 09:00.
    scroll.resize(400, 420)
    settle(qapp)
    bar = scroll.horizontalScrollBar()
    scroll.scroll_to(9 * 60, above=0)
    settle(qapp)
    at_nine = bar.value()
    scroll.reveal(11 * 60, 60, "normal")
    manual_time.advance(1000)
    assert bar.value() == at_nine, "11:00 already shows: nothing moves"
    scroll.reveal(17 * 60, 60, "normal")
    assert bar.value() == at_nine, "it starts from where it was"
    manual_time.advance(1000)
    assert abs(minute_across(scroll, 0) - 16 * 60) <= 1, "and eases to an hour before 17:00"
    scroll.scroll_to(9 * 60, above=0)
    settle(qapp)
    scroll.reveal(17 * 60, 60, "reduce")
    assert abs(minute_across(scroll, 0) - 16 * 60) <= 1, "under Reduce it goes at once"
