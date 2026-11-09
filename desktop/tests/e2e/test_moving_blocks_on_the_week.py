"""Dragging a block moves it; on a repeating block it moves only that day, and editing one occurrence
leaves the rest of the series as it was."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import session_in_the_planned_week, soccer
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def school(days: list[int], start: str = "08:00") -> dict:
    return {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "duration_min": 390,
        "days": days,
        "start": start,
        "category": "class",
    }


def test_a_repeating_block_dragged_on_one_day_moves_only_that_day(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(school([0, 1, 2]))
    assert session.hand_move("school", 0, 3, 9 * 60, 15 * 60) is True
    assert len(session.blocks) == 2
    days = {tuple(block["days"]): block for block in session.blocks}
    series = days[(1, 2)]
    assert series["id"] == "school" and series["start"] == "08:00"
    copy = days[(3,)]
    assert copy["id"] != "school"
    assert copy["start"] == "09:00"
    assert copy["duration_min"] == 360
    assert copy.get("pinned") is not True


def test_moving_and_resizing_a_one_day_block_updates_it(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(soccer())
    assert session.hand_move("soccer", 0, 0, 630, 705) is True
    assert session.blocks[0]["start"] == "10:30"
    assert session.blocks[0]["duration_min"] == 75
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)


def test_editing_one_occurrence_leaves_the_rest_of_the_series(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(school([0, 1, 2, 3, 4]))
    session.add_block(school([2], "09:00"), scope="occurrence", day=2)
    days = {tuple(block["days"]): block["start"] for block in session.blocks}
    assert days[(0, 1, 3, 4)] == "08:00"
    assert days[(2,)] == "09:00"
