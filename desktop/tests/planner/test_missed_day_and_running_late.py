"""Missing a school day replans the week and the week still saves; Running late adds a late-start block,
on a week with a missed day too, and one Undo takes the whole late start back."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import session_in_the_planned_week, soccer
from desktop.tests.planner.school_week import (
    PLANNED_WEEK,
    open_the_school_week,
    placement,
    plan_the_school_week,
    stored,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_missed_school_day_is_saved_and_the_week_still_saves_after_it(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """Missing Monday's school replans the week. The recovery used to copy the solver's list of the
    days school still runs onto the block, so Monday was missed but no longer one of its days, and
    every save after that failed: the replan, and anything the student changed later."""
    session = open_the_school_week(open_light, clock)
    plan_the_school_week(qapp, session)
    session.recover_missed("school", 0)
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    sessions = [block["id"] for block in session.blocks if block.get("assignment_id")]
    replanned = {block_id: placement(session, block_id) for block_id in sessions}
    assert all(start for _days, start in replanned.values())
    session.load_week(PLANNED_WEEK, discard=True)
    wait_until(qapp, lambda: not session.busy)
    school = stored(session, "school")
    assert (school["days"], school.get("missed_days")) == ([0, 1, 2, 3, 4], [0])
    after = {block_id: placement(session, block_id) for block_id in replanned}
    assert after == replanned
    session.add_block(
        {"id": "gym", "title": "Gym", "kind": "locked", "duration_min": 60, "days": [5], "start": "10:00"}
    )
    session.save()
    wait_until(qapp, lambda: not session.busy)
    assert session.dirty is False
    assert session.message == "Saved."


def test_running_late_saves_on_a_week_that_already_has_a_missed_day(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = open_the_school_week(open_light, clock)
    plan_the_school_week(qapp, session)
    session.add_block({**stored(session, "school"), "missed_days": [0]})
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    clock.set(datetime(2026, 9, 29, 15, 5))
    session.preview_running_late(30, now=clock.now())
    wait_until(qapp, lambda: session.late_preview is not None and not session.busy)
    assert session.accept_running_late()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    assert any(block["title"] == "Running late" for block in session.blocks)
    assert stored(session, "school")["days"] == [0, 1, 2, 3, 4]


def test_missing_a_fixed_block_stores_the_missed_day(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.recover_missed("soccer", 0)
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    block = next(item for item in session.blocks if item["id"] == "soccer")
    assert block["missed_days"] == [0]


def test_running_late_saves_a_fixed_late_start_block_and_one_undo_takes_it_back(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "category": "assignments",
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    now = datetime.combine(clock.today(), time(14, 7))
    session.preview_running_late(30, now=now)
    wait_until(qapp, lambda: session.late_preview is not None and not session.busy)
    assert session.late_preview["block"]["title"] == "Running late"
    assert session.late_preview["block"]["kind"] == "locked"
    assert session.late_preview["block"]["start"] == "14:00"
    assert session.late_preview["block"]["duration_min"] == 30
    assert session.accept_running_late()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    assert any(block["title"] == "Running late" for block in session.blocks)
    wait_until(qapp, lambda: session.can_undo())
    session.undo()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    # One Undo is the whole late start. A second solve after the save used to leave the block.
    assert not any(block["title"] == "Running late" for block in session.blocks)
