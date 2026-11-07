"""Day shows the saved day summary, and Month shows whole weeks with the fixed time counted in them."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import session_in_the_planned_week, soccer
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_the_day_view_loads_the_saved_day_summary(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.open_day(session.week_start)
    wait_until(qapp, lambda: session.day_data is not None and not session.busy)
    assert session.planner_view == "day"
    assert session.day_data["date"] == session.week_start
    assert session.day_data["week_start"] == session.week_start
    assert session.day_data["next_action"]["kind"] == "add"
    locked_titles = {item["title"] for item in session.day_data["locked"]}
    assert "Soccer" in locked_titles


def test_the_month_view_covers_whole_weeks_and_counts_the_fixed_time(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.set_view("month")
    wait_until(qapp, lambda: session.month_data is not None)
    body = session.month_data
    # Whole weeks: the Monday on or before the 1st through the Sunday on or after the last day. That
    # is 28, 35 or 42 days, so a fixed 35 would pass in one month and fail in another.
    first = date.fromisoformat(session.selected_month + "-01")
    last = (first + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    grid_start = first - timedelta(days=first.weekday())
    grid_end = last + timedelta(days=6 - last.weekday())
    assert body["days"][0]["date"] == grid_start.isoformat()
    assert body["days"][-1]["date"] == grid_end.isoformat()
    assert len(body["days"]) == (grid_end - grid_start).days + 1
    assert body["month"] == session.selected_month
    assert any(day["locked_count"] >= 1 for day in body["days"])
