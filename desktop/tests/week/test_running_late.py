"""Running late: which blocks it moves, and how Plan treats the time that has passed."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.sheet_rules import _unbroken_time
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_pastnext import settled_session
from desktop.tests.window_support import qapp  # noqa: F401


def test_running_late_leaves_homework_that_waits_for_a_time_out_of_the_replan(qapp, window) -> None:
    session = window.session
    timed = {
        "id": "essay-1",
        "title": "Essay",
        "kind": "flexible",
        "category": "work",
        "assignment_id": "essay",
        "start": "16:00",
        "duration_min": 60,
        "days": [0],
    }
    waiting = {**timed, "id": "essay-2", "start": None}
    fixed = {
        "id": "gym",
        "title": "Gym",
        "kind": "locked",
        "category": "extra",
        "start": "18:00",
        "duration_min": 60,
        "days": [0],
    }
    session.blocks = [timed, waiting, fixed]
    assert [block["id"] for block in session._late_blocks()] == ["essay-1", "gym"]


# Plan and Replan from the time that has passed --------------------------------------------------


def _plan_at_monday_five(qapp: QApplication, window: NativeWindow, *, everything: bool) -> list[dict]:
    session = window.session
    wait_until(qapp, lambda: session.preferences is not None)
    monday = datetime.fromisoformat(session.week_start)
    CLOCK.set(monday + timedelta(hours=17))
    session.add_homework(
        {
            "id": "floor-homework",
            "title": "Floor homework",
            "estimate_min": 60,
            "revision": 0,
            "due": (monday.date() + timedelta(days=3)).isoformat() + "T23:59",
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled_session(qapp, session)
    session.solve(everything=everything)
    wait_until(qapp, lambda: not session.planning and not session.busy and not session.dirty, timeout=20)
    settled_session(qapp, session)
    return [block for block in session.blocks if block.get("assignment_id") == "floor-homework"]


def _assert_not_before_monday_five(blocks: list[dict]) -> None:
    for block in blocks:
        if not block.get("start"):
            continue
        day = min(block.get("days") or [0])
        hour, minute = map(int, block["start"].split(":"))
        assert (day, hour * 60 + minute) >= (0, 17 * 60), block


def test_plan_keeps_everything_at_or_after_now_on_an_empty_monday(qapp, window) -> None:
    blocks = _plan_at_monday_five(qapp, window, everything=False)
    assert any(block.get("start") for block in blocks)
    _assert_not_before_monday_five(blocks)


def test_replan_keeps_everything_at_or_after_now_on_an_empty_monday(qapp, window) -> None:
    blocks = _plan_at_monday_five(qapp, window, everything=True)
    assert any(block.get("start") for block in blocks)
    _assert_not_before_monday_five(blocks)


def test_only_a_times_own_am_pm_is_kept_with_it() -> None:
    assert _unbroken_time("PM club AMERICAN: Mon 4:45–5:45 PM → Tue 7 AM") == (
        "PM club AMERICAN: Mon 4:45–5:45 PM → Tue 7 AM"
    )
