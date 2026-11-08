"""The week the planning tests plan in: the light app opened on Monday 2 November 2026, before anything
in it, since Plan puts nothing before now."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from backend.tests.fake_clock import FakeClock
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.logic_support import fixed

MONDAY_MORNING = datetime(2026, 11, 2, 0, 0)


def session_in_the_planned_week(open_light: Callable[..., NativeWindow], clock: FakeClock) -> NativeSession:
    clock.set(MONDAY_MORNING)
    return open_light().session


def soccer() -> dict:
    return fixed("soccer", "Soccer", 0, "16:00")


def auto_split_preferences() -> dict:
    return {
        "auto_split_pomodoro": True,
        "timer_work_min": 30,
        "timer_break_min": 15,
        "timer_long_break_min": 30,
        "timer_long_break_every": 4,
    }
