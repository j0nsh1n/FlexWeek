"""Block reminders follow today, not the week on screen; alarms that fall due together ring one at a time."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import soccer
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# Monday, five minutes before Soccer (Monday 16:00) with a five minute lead.
FIVE_TO_FOUR = datetime(2026, 11, 2, 15, 55)
NEXT_WEEK = "2026-11-09"


def test_reminders_ignore_a_week_that_is_not_today(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    clock.set(FIVE_TO_FOUR)
    session = open_light().session
    wait_until(qapp, lambda: session.preferences is not None)
    session.week_start = NEXT_WEEK
    session.blocks = [soccer()]
    session.preferences = {**(session.preferences or {}), "reminders_enabled": True, "reminder_lead_min": 5}
    notices: list[dict] = []
    session.alerts.connect(notices.extend)
    session.check_alerts()
    assert notices == []
    wait_until(qapp, lambda: session._reminder_fetching is None, what="today's week was fetched")
    assert notices == []


def test_todays_reminders_still_fire_while_another_week_is_on_screen(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    clock.set(FIVE_TO_FOUR)
    session = open_light().session
    wait_until(qapp, lambda: session.preferences is not None)
    session.week_start = NEXT_WEEK
    session.blocks = [{**soccer(), "id": "band", "title": "Band", "start": "18:00"}]
    session._reminder_week = "2026-11-02"
    session._reminder_blocks = [soccer()]
    session.preferences = {**(session.preferences or {}), "reminders_enabled": True, "reminder_lead_min": 5}
    notices: list[dict] = []
    session.alerts.connect(notices.extend)
    session.check_alerts()
    assert [item["title"] for item in notices] == ["Soccer starts soon"]


def test_a_second_alarm_waits_until_the_first_is_dismissed(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    clock.set(datetime(2026, 11, 2, 7, 0))
    session = open_light().session
    wait_until(qapp, lambda: session.preferences is not None)
    session.preferences = {
        **(session.preferences or {}),
        "alarms": [
            {"id": "early", "name": "Early", "time": "07:00", "days": [0], "enabled": True},
            {"id": "also", "name": "Also", "time": "07:00", "days": [0], "enabled": True},
        ],
    }
    session.last_alarm_check = None
    session.check_alerts()
    assert session.active_alarm is not None and session.active_alarm["id"] == "early"
    assert [item["id"] for item in session.alarm_queue] == ["also"]
    session.finish_alarm(False)
    assert session.active_alarm is not None and session.active_alarm["id"] == "also"
    assert session.alarm_queue == []
