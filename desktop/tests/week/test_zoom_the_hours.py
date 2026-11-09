"""Zooming the hours: the wheel with Ctrl, the buttons, the stop at each end, the line that says why a
button is greyed, and that nothing zooms while a block is held.

These send Qt events, so they prove the rules; the rig zooms with a real pointer on the real window."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.classic import DAY_SCALE, WEEK_SCALE  # noqa: E402
from desktop.tests.week import support_zoom  # noqa: E402
from desktop.tests.week.support_zoom import (  # noqa: E402
    SCHOOL,
    a_day,
    a_lane_week,
    a_week,
    minute_across,
    minute_at,
    settle,
    wheel,
)

qapp = support_zoom.qapp  # a fixture is found by its name in the test module


def test_ctrl_and_the_wheel_zoom_about_the_pointer(qapp: QApplication) -> None:
    view = a_week(qapp)
    port = view.scroll.viewport()
    y = port.height() * 0.7
    before = minute_at(view, y)
    wheel(view.hours, QPointF(300, view.scroll.verticalScrollBar().value() + y), 1)
    assert view.scroll.px == 64
    assert abs(minute_at(view, y) - before) <= 1, "the minute under the pointer stayed under it"
    wheel(view.hours, QPointF(300, view.scroll.verticalScrollBar().value() + y), 0.5)
    assert view.scroll.px == 64, "half a notch from a touchpad is not a step yet"
    wheel(view.hours, QPointF(300, view.scroll.verticalScrollBar().value() + y), 0.5)
    assert view.scroll.px == 96, "two half notches are one step"
    wheel(view.hours, QPointF(300, view.scroll.verticalScrollBar().value() + y), -2)
    assert view.scroll.px == 48
    top = view.scroll.verticalScrollBar().value()
    wheel(view.hours, QPointF(300, top + y), -1, ctrl=False)
    assert view.scroll.px == 48, "without Ctrl the wheel only scrolls"


def test_the_buttons_zoom_about_the_middle_and_stop_at_each_end(qapp: QApplication) -> None:
    """The keys are the window's, and test_zoom_hours_with_the_keyboard presses them there."""
    view = a_week(qapp)
    middle = view.scroll.viewport().height() / 2
    before = minute_at(view, middle)
    QTest.mouseClick(view.scroll.buttons.into, Qt.MouseButton.LeftButton)
    assert view.scroll.px == 64
    assert abs(minute_at(view, middle) - before) <= 1
    for _ in range(6):
        QTest.mouseClick(view.scroll.buttons.into, Qt.MouseButton.LeftButton)
    assert view.scroll.px == WEEK_SCALE.levels[-1]
    assert not view.scroll.buttons.into.isEnabled() and view.scroll.buttons.out.isEnabled()
    view.scroll.zoom_by(0)
    assert view.scroll.px == WEEK_SCALE.default
    for _ in range(6):
        QTest.mouseClick(view.scroll.buttons.out, Qt.MouseButton.LeftButton)
    assert view.scroll.px == WEEK_SCALE.levels[0]
    assert not view.scroll.buttons.out.isEnabled()


def test_nothing_zooms_while_a_block_is_held(qapp: QApplication) -> None:
    view = a_week(qapp, [SCHOOL])
    view.scroll.scroll_to(9 * 60)
    press = view.hours.mapFromGlobal(view.hours.point_for(0, 10 * 60))
    QTest.mousePress(view.hours, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, press)
    assert view.hours.hand.busy
    view.scroll.zoom_by(1)
    assert view.scroll.px == WEEK_SCALE.default
    view.hours.hand.cancel()
    QTest.mouseRelease(view.hours, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, press)


def test_lanes_zoom_about_the_pointer_and_the_plain_wheel_moves_them_through_the_day(
    qapp: QApplication,
) -> None:
    scroll = a_lane_week(qapp)
    assert scroll.verticalScrollBar().maximum() == 0, "the lanes fit the height; only time scrolls"
    x = scroll.viewport().width() * 0.6
    before = minute_across(scroll, x)
    wheel(scroll.canvas, QPointF(scroll.horizontalScrollBar().value() + x, 100), 1)
    assert scroll.px == 64
    assert abs(minute_across(scroll, x) - before) <= 1, "the minute under the pointer stayed under it"
    at = scroll.horizontalScrollBar().value()
    # A real wheel passes from the canvas, which leaves it, to the viewport; a sent one stops where
    # it is sent, so it goes where a real one arrives.
    wheel(scroll.viewport(), QPointF(x, 100), -1, ctrl=False)
    assert scroll.px == 64
    assert scroll.horizontalScrollBar().value() > at, "the wheel moved the lanes on through the day"


def test_a_greyed_zoom_says_why_in_one_line_under_the_pill(qapp: QApplication) -> None:
    """A disabled button shows no tooltip, so after zooming to a limit the - or + stays greyed and one
    caption line under the pill says "Smallest zoom reached" or "Largest zoom reached"; away from a
    limit there is no line. Where the line sits is a screen (week.zoom-pill-at-a-limit)."""
    view = a_week(qapp)
    scroll = view.scroll
    assert not scroll.reason.isVisible()
    for _ in range(8):
        QTest.mouseClick(scroll.buttons.into, Qt.MouseButton.LeftButton)
    assert scroll.px == WEEK_SCALE.levels[-1]
    assert not scroll.buttons.into.isEnabled() and scroll.buttons.into.isVisible()
    assert scroll.reason.isVisible() and scroll.reason.words == "Largest zoom reached"
    scroll.zoom_by(0)
    assert not scroll.reason.isVisible()
    for _ in range(8):
        QTest.mouseClick(scroll.buttons.out, Qt.MouseButton.LeftButton)
    assert scroll.px == WEEK_SCALE.levels[0]
    assert not scroll.buttons.out.isEnabled() and scroll.buttons.out.isVisible()
    assert scroll.reason.isVisible() and scroll.reason.words == "Smallest zoom reached"
    scroll.zoom_by(1)
    assert not scroll.reason.isVisible(), "the line stays after the zoom left its limit"


def test_a_view_opened_at_a_zoom_limit_says_nothing_about_it(qapp: QApplication) -> None:
    """Day opens at its smallest zoom, so "Smallest zoom reached" showed all the time. The line is for
    a student who has just zoomed to a limit, not for a view that opens at one."""
    day = a_day(qapp, [], 3)
    scroll = day.scroll
    assert scroll.px == DAY_SCALE.levels[0], "Day opens at its smallest zoom"
    assert not scroll.buttons.out.isEnabled(), "the button is still greyed at the limit"
    assert not scroll.reason.isVisible() and scroll.reason.words == ""
    week = a_week(qapp)
    week.scroll.restore({WEEK_SCALE.key: WEEK_SCALE.levels[-1]})
    settle(qapp)
    assert week.scroll.px == WEEK_SCALE.levels[-1] and not week.scroll.buttons.into.isEnabled()
    assert not week.scroll.reason.isVisible() and week.scroll.reason.words == ""


def zoom_with_button(view, steps: int) -> None:
    button = view.scroll.buttons.into if steps > 0 else view.scroll.buttons.out
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)


def zoom_with_keyboard(view, steps: int) -> None:
    """The window's Ctrl+= and Ctrl+- call zoom_by on whichever hours show."""
    view.scroll.zoom_by(steps)


def zoom_with_wheel(view, steps: int) -> None:
    wheel(view.hours, QPointF(300, view.scroll.verticalScrollBar().value() + 100), steps)


@pytest.mark.parametrize("how", [zoom_with_button, zoom_with_keyboard, zoom_with_wheel])
@pytest.mark.parametrize("steps", [-1, 1])
def test_zooming_to_a_limit_says_so_for_about_three_seconds_then_gives_the_line_back(
    qapp: QApplication, how, steps: int
) -> None:
    """By the button, the keyboard or the wheel. The caption goes on its own after about 3 seconds
    (the timer is driven here, not slept on), the header gives its line back, and the button stays
    greyed."""
    view = a_week(qapp)
    scroll = view.scroll
    plain_top = scroll.viewportMargins().top()
    limit = WEEK_SCALE.levels[-1] if steps > 0 else WEEK_SCALE.levels[0]
    words = "Largest zoom reached" if steps > 0 else "Smallest zoom reached"
    while scroll.px != limit:
        assert not scroll.reason.isVisible(), "no line on the way to the limit"
        how(view, steps)
        settle(qapp)
    assert scroll.px == limit
    assert scroll.reason.isVisible() and scroll.reason.words == words
    assert scroll.viewportMargins().top() > plain_top, "the header makes room for the line"
    assert scroll.reason_timer.isActive() and scroll.reason_timer.interval() == 3000
    scroll.reason_timer.timeout.emit()
    settle(qapp)
    assert not scroll.reason.isVisible() and scroll.reason.words == ""
    assert scroll.viewportMargins().top() == plain_top, "the header gives its line back"
    greyed = scroll.buttons.into if steps > 0 else scroll.buttons.out
    assert not greyed.isEnabled(), "the button stays greyed at the limit"


def test_pressing_on_at_a_limit_says_so_again_and_leaving_it_clears_the_line_at_once(
    qapp: QApplication,
) -> None:
    """The keyboard and the wheel still ask while the button is greyed, so asking past the end gets the
    line back; zooming away from the limit takes it away before its time is up."""
    view = a_week(qapp)
    scroll = view.scroll
    scroll.zoom_by(10)
    scroll.reason_timer.timeout.emit()
    assert not scroll.reason.isVisible()
    scroll.zoom_by(1)
    assert scroll.reason.isVisible() and scroll.reason.words == "Largest zoom reached"
    scroll.zoom_by(-1)
    assert not scroll.reason.isVisible() and not scroll.reason_timer.isActive()


def test_a_press_on_the_edge_of_a_zoom_button_still_counts_for_it(qapp: QApplication) -> None:
    """The pill's buttons are drawn inside its edge; a press on the outer side, top or bottom of a
    button's press area, as the buttons report it, still counts for it. The area's size (24 pixels
    square, the button drawn smaller) is a screen (week.zoom-pill-at-a-limit)."""
    view = a_week(qapp)
    buttons = view.scroll.buttons
    view.scroll.zoom_by(1)
    view.scroll.zoom_by(-1)
    assert view.scroll.px == WEEK_SCALE.default
    for button, edge in ((buttons.out, "left"), (buttons.into, "right")):
        area = buttons.hit_area(button)
        middle = area.center().y()
        side = area.left() if edge == "left" else area.right()
        across = area.center().x()
        for at in (QPoint(side, middle), QPoint(across, area.top()), QPoint(across, area.bottom())):
            before = view.scroll.px
            QTest.mouseClick(buttons.pill, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at)
            assert view.scroll.px != before, (button.objectName(), at)
            view.scroll.zoom_by(0)
