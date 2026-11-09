"""Where the hours open and where they stay: now or the first block when a week or day is opened, the
student's scroll kept across Day, Week, Month, Focus, Settings, a new look and a new text size, Today
bringing this week back to now, and Plan scrolling to the first homework it placed."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QAbstractButton, QApplication, QScrollBar  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.hours.geometry import Axis  # noqa: E402
from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week import support_zoom  # noqa: E402
from desktop.tests.week.support_zoom import (  # noqa: E402
    DESIGNS,
    HELD,
    HELD_MONDAY,
    NOW,
    hours,
    opens_at,
    span_shown,
)

qapp = support_zoom.qapp  # fixtures are found by their name in the test module
window = support_zoom.window


def test_todays_app_opens_an_empty_next_week_at_eight_once_there_is_homework(
    qapp: QApplication, window: NativeWindow
) -> None:
    """With homework on the account an empty week keeps its hours, and they open at 08:00 even though
    they grow as the page lays out."""
    session = window.session
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._apply_appearance()
    window._on_week()
    for name in ("viewWeek", "nextWeek"):
        window.findChild(QAbstractButton, name).click()
        wait_until(qapp, lambda: not session.busy)
    assert window.planner.currentWidget() is not window.empty_week
    opens_at(qapp, window, 8 * 60, "classic next Week, empty")


def test_every_design_opens_at_now_or_the_first_block_and_again_on_another_day_or_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    thursday = (date.fromisoformat(session.week_start) + timedelta(days=3)).isoformat()

    def press(name: str) -> None:
        window.findChild(QAbstractButton, name).click()
        wait_until(qapp, lambda: not session.busy)

    for design in DESIGNS:
        window._layout = sanitize_layout({"main": design, "day": "one"})
        window._apply_appearance()
        window._on_week()
        press("viewWeek")
        opens_at(qapp, window, NOW, f"{design} Week")
        press("nextWeek")
        if design == "classic":
            # #16: a later empty week keeps its hours, with the offers on a card over them.
            assert window.planner.currentWidget() is window.week_table
            assert window.empty_week.parentWidget() is window.week_table and window.empty_week.isVisible()
        else:
            opens_at(qapp, window, 8 * 60, f"{design} next Week, empty")
        press("prevWeek")
        opens_at(qapp, window, NOW, f"{design} Week again")
        press("viewDay")
        # As a click on Thursday's name does: the day this computer calls today may be another.
        session.open_day(thursday)
        wait_until(qapp, lambda: not session.busy)
        opens_at(qapp, window, NOW, f"{design} Day, today")
        press("nextWeek")
        press("nextWeek")
        assert date.fromisoformat(session.selected_day).weekday() == 5
        opens_at(qapp, window, 18 * 60, f"{design} Saturday, first block")
        press("prevWeek")
        opens_at(qapp, window, 8 * 60, f"{design} Friday, first block")
        press("prevWeek")
        opens_at(qapp, window, NOW, f"{design} Thursday again")


def test_todays_app_keeps_its_scroll_after_a_page_or_look_change(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The 0.17.2 scroll decision replaces reopening at now after a page or look change."""
    from desktop.native.look import sanitize_look

    session = window.session
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._apply_appearance()
    window._on_week()

    def press(name: str) -> None:
        window.findChild(QAbstractButton, name).click()
        wait_until(qapp, lambda: not session.busy)

    def away() -> None:
        hours(window).verticalScrollBar().setValue(0)
        qapp.processEvents()

    def new_look() -> None:
        window._look = sanitize_look({"preset": "high-contrast"})
        window._apply_appearance()
        window._on_week()

    def settings() -> None:
        window._open_settings()
        window._close_settings(save=False)

    press("viewWeek")
    opens_at(qapp, window, NOW, "Week")
    away()
    session.save()
    wait_until(qapp, lambda: not session.busy)
    window._on_week()
    assert hours(window).verticalScrollBar().value() == 0, "a refresh moved the week the student scrolled"
    for how, act in (
        ("after Month", lambda: (press("viewMonth"), press("viewWeek"))),
        ("in a new look", new_look),
        ("back from Settings", settings),
    ):
        away()
        act()
        assert hours(window).verticalScrollBar().value() == 0, how


@pytest.mark.parametrize("design", DESIGNS)
def test_day_reached_from_week_opens_at_now(qapp: QApplication, window: NativeWindow, design: str) -> None:
    window.session.selected_day = HELD.date().isoformat()
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._apply_appearance()
    window._on_week()
    window.findChild(QAbstractButton, "viewWeek").click()
    wait_until(qapp, lambda: not window.session.busy)
    window.findChild(QAbstractButton, "viewDay").click()
    wait_until(qapp, lambda: not window.session.busy)
    opens_at(qapp, window, NOW, "Day reached from Week")
    first, last = span_shown(hours(window))
    assert first <= 18 * 60 <= last, "Day opened at now but left the next block out of view"


def test_after_plan_the_week_scrolls_to_the_first_homework_it_placed(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Decision 34 of 0.17: the blocks a plan placed landed off screen while the week stayed where it
    was, so what it did went unseen."""
    session = window.session
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._apply_appearance()
    window._on_week()
    window.findChild(QAbstractButton, "viewWeek").click()
    wait_until(qapp, lambda: not session.busy)
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    hours(window).verticalScrollBar().setValue(0)
    qapp.processEvents()
    session.solve()
    wait_until(qapp, lambda: session.plan_first is not None and not session.busy)
    for _ in range(4):
        qapp.processEvents()
    placed = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    assert placed.get("start"), "the plan gave the essay a time"
    start = int(placed["start"][:2]) * 60 + int(placed["start"][3:])
    first, last = span_shown(hours(window))
    assert first <= start <= last, f"{placed['start']} is not on screen ({first:.0f} to {last:.0f})"


@pytest.mark.parametrize("design", DESIGNS)
def test_each_design_keeps_day_and_week_scroll_until_today_is_pressed(
    qapp: QApplication, window: NativeWindow, design: str
) -> None:
    session = window.session
    today = datetime.fromtimestamp(session.now_ms() / 1000).date().isoformat()
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._apply_appearance()
    window._on_week()

    def press(name: str) -> None:
        window.findChild(QAbstractButton, name).click()
        wait_until(qapp, lambda: not session.busy)
        for _ in range(4):
            qapp.processEvents()

    def away() -> None:
        scroll = hours(window)
        bar = scroll.verticalScrollBar() if scroll.axis is Axis.DOWN else scroll.horizontalScrollBar()
        bar.setValue(0)
        qapp.processEvents()

    def stays(where: str) -> None:
        scroll = hours(window)
        bar = scroll.verticalScrollBar() if scroll.axis is Axis.DOWN else scroll.horizontalScrollBar()
        assert bar.value() == 0, f"{design} {where} moved the hours away from midnight"

    press("viewWeek")
    away()
    session.open_day(today)
    wait_until(qapp, lambda: not session.busy)
    away()
    press("viewWeek")
    stays("Week after Day")
    press("viewDay")
    stays("Day after Week")
    session.open_day((date.fromisoformat(today) + timedelta(days=1)).isoformat())
    wait_until(qapp, lambda: not session.busy)
    session.open_day(today)
    wait_until(qapp, lambda: not session.busy)
    stays("Day after another day")
    press("viewWeek")
    press("viewMonth")
    press("viewWeek")
    stays("Week after Month")
    window._open_focus_screen()
    window._close_focus_screen()
    qapp.processEvents()
    stays("Week after Focus")
    press("todayWeek")
    opens_at(qapp, window, NOW, f"{design} Today")
    away()
    press("nextWeek")
    press("prevWeek")
    opens_at(qapp, window, NOW, f"{design} returning to this week")
    press("nextWeek")
    session.add_block(
        {
            "id": "future-dinner",
            "title": "Dinner",
            "kind": "locked",
            "category": "meals",
            "start": "18:00",
            "duration_min": 30,
            "days": [0],
        }
    )
    wait_until(qapp, lambda: not session.busy)
    away()
    press("prevWeek")
    opens_at(qapp, window, NOW, f"{design} returning to this week after scrolling next week")
    press("nextWeek")
    stays("next week after Today reopened this week")


@pytest.mark.parametrize("design", DESIGNS)
def test_today_opens_this_week_at_now_and_leaves_the_week_it_was_pressed_from_where_it_was(
    qapp: QApplication, window: NativeWindow, design: str
) -> None:
    """Today opens this week at now. Next week, scrolled before Today was pressed, is where the student
    left it when they go forward to it again."""
    session = window.session
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._apply_appearance()
    window._on_week()

    def press(name: str) -> None:
        window.findChild(QAbstractButton, name).click()
        wait_until(qapp, lambda: not session.busy)
        for _ in range(4):
            qapp.processEvents()

    def bar() -> QScrollBar:
        scroll = hours(window)
        return scroll.verticalScrollBar() if scroll.axis is Axis.DOWN else scroll.horizontalScrollBar()

    press("viewWeek")
    press("nextWeek")
    # Today's app shows an empty week as one button, not hours.
    session.add_block(
        {
            "id": "future-dinner",
            "title": "Dinner",
            "kind": "locked",
            "category": "meals",
            "start": "18:00",
            "duration_min": 30,
            "days": [0],
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    for _ in range(4):
        qapp.processEvents()
    opened = bar().value()
    bar().setValue(opened + 40 if opened + 40 <= bar().maximum() else opened - 40)
    left = bar().value()
    assert abs(left - opened) == 40, f"{design}: next week's hours have no room to scroll"
    press("todayWeek")
    assert session.week_start == HELD_MONDAY
    opens_at(qapp, window, NOW, f"{design} Today from next week")
    press("nextWeek")
    assert bar().value() == left, f"{design}: Today lost where next week was scrolled to"


@pytest.mark.parametrize("design", DESIGNS)
def test_each_design_keeps_the_week_where_it_was_through_a_new_text_size(
    qapp: QApplication, window: NativeWindow, design: str
) -> None:
    """Timeline and Bento make their hours again for a new text size. Those are where the student left
    the week, not at now, like every other look change."""
    from desktop.native.look import sanitize_look

    session = window.session
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._apply_appearance()
    window._on_week()
    window.findChild(QAbstractButton, "viewWeek").click()
    wait_until(qapp, lambda: not session.busy)
    for _ in range(4):
        qapp.processEvents()
    scroll = hours(window)
    bar = scroll.verticalScrollBar() if scroll.axis is Axis.DOWN else scroll.horizontalScrollBar()
    opened = bar.value()
    bar.setValue(opened + 40 if opened + 40 <= bar.maximum() else opened - 40)
    assert bar.value() != opened
    left = span_shown(scroll)[0]
    window._look = sanitize_look({"knobs": {"text": "large"}})
    window._apply_appearance()
    window._on_week()
    for _ in range(4):
        qapp.processEvents()
    top = span_shown(hours(window))[0]
    assert abs(top - left) <= 2, f"{design}: a new text size moved the week from {left:.0f} to {top:.0f}"
