"""Homework dropped on the Material week: it gets that time, is pinned, is one Undo step, and Replan all
leaves it where it was put, even over School, where the two lie one over the other.

Thursday 19:00 is the clock, School runs Monday to Friday 08:00 to 14:30. Friday is ahead of the clock,
so a drop there is allowed (a time already past is refused)."""

# ruff: noqa: F811
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from desktop.tests.week.support_material import (
    _block_named,
    _bridge,
    _homework,
    _named,
    _pump,
    _reset,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401

FRIDAY = 4


def _waiting_math(qapp, window) -> dict:
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "math", "Math worksheet", 60, due)
    settled(qapp, window)
    return next(block for block in window.session.blocks if block.get("assignment_id") == "math")


def _block(window, block_id: str) -> dict:
    return next(block for block in window.session.blocks if block["id"] == block_id)


def test_homework_dropped_on_the_calendar_gets_that_time_and_keeps_it(qapp, window) -> None:
    _reset(window, qapp)
    waiting = _waiting_math(qapp, window)
    assert not waiting.get("start")
    _bridge(window).week.placeHomework(waiting["id"], FRIDAY, 16 * 60)
    settled(qapp, window)
    placed = _block(window, waiting["id"])
    assert (placed["days"], placed["start"], placed.get("pinned")) == ([FRIDAY], "16:00", True)
    window.session.undo()
    settled(qapp, window)
    assert not _block(window, waiting["id"]).get("start"), "the drop is one Undo step"
    window.session.redo()
    settled(qapp, window)
    window.session.solve(everything=True)
    settled(qapp, window)
    replanned = _block(window, waiting["id"])
    assert (replanned["days"], replanned["start"]) == ([FRIDAY], "16:00"), "Replan all leaves it put"


def test_a_drop_over_school_sits_over_it_and_no_plan_moves_it_off(qapp, window) -> None:
    """Two blocks at one time are allowed, each visible, and the pin keeps the planner from making way."""
    root = _reset(window, qapp)
    waiting = _waiting_math(qapp, window)
    _bridge(window).week.placeHomework(waiting["id"], FRIDAY, 10 * 60)
    settled(qapp, window)
    placed = _block(window, waiting["id"])
    assert (placed["days"], placed["start"], placed.get("pinned")) == ([FRIDAY], "10:00", True)
    _pump(qapp)
    assert _block_named(root, "Math worksheet") is not None
    assert len(_named(root, "weekBlock")) >= 2 and _block_named(root, "School") is not None
    window.session.solve(everything=True)
    settled(qapp, window)
    replanned = _block(window, waiting["id"])
    assert (replanned["days"], replanned["start"]) == ([FRIDAY], "10:00")
