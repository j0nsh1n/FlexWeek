# ruff: noqa: F811
"""Holding and moving a block on the week's hours with the mouse: one day of School moves alone, a block
held when the view changes is let go, and a move made while a save is under way is not lost."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.blocks_helper import put_block  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    drag_on_the_week,
    qapp,  # noqa: F401
    settled,
    wait_until,
    waiting_math,
    window,  # noqa: F401
)


def test_a_block_held_on_the_week_goes_back_when_the_student_switches_to_day(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Switching away while holding a block is letting go of it, as Escape is: nothing moves and nothing
    is saved, whatever lies under the pointer on the view that comes up."""
    settled(qapp, window)
    revision = window.session.revision
    drag_on_the_week(qapp, window, 2, "10:00", 2, "11:00", between=lambda: window._choose_view("day"))
    settled(qapp, window)
    assert window.session.planner_view == "day"
    assert not window.hand.busy
    assert window.session.revision == revision, "a save was made"
    school = [block for block in window.session.blocks if block["title"] == "School"]
    assert [(tuple(block["days"]), block["start"]) for block in school] == [((0, 1, 2, 3, 4), "08:00")]


def test_dragging_one_day_of_school_moves_that_day_only(qapp: QApplication, window: NativeWindow) -> None:
    drag_on_the_week(qapp, window, 2, "10:00", 2, "11:00")
    settled(qapp, window)
    school = [block for block in window.session.blocks if block["title"] == "School"]
    assert sorted((tuple(block["days"]), block["start"]) for block in school) == [
        ((0, 1, 3, 4), "08:00"),
        ((2,), "09:00"),
    ]
    window.session.undo()
    settled(qapp, window)
    school = [block for block in window.session.blocks if block["title"] == "School"]
    assert [(block["days"], block["start"]) for block in school] == [([0, 1, 2, 3, 4], "08:00")], (
        "one Undo step"
    )


def test_a_block_moved_on_the_week_while_a_save_is_under_way_is_not_lost(
    qapp: QApplication, window: NativeWindow
) -> None:
    waiting = waiting_math(qapp, window)
    put_block(window.session, waiting["id"], 2, 16 * 60, 16 * 60 + waiting["duration_min"], pinned=True)
    window.session.save()
    settled(qapp, window)
    window.session.add_homework(
        {"id": "poster", "title": "Poster", "due": sunday_due(window.session.week_start), "estimate_min": 30}
    )
    window.session.save()
    assert window.session.busy
    # To Friday: the clock is Thursday 19:00, and a time already past is refused.
    drag_on_the_week(qapp, window, 2, "16:30", 4, "17:30")
    settled(qapp, window)
    wait_until(
        qapp, lambda: next(b for b in window.session.blocks if b["id"] == waiting["id"])["days"] == [4]
    )
    settled(qapp, window)
    moved = next(block for block in window.session.blocks if block["id"] == waiting["id"])
    assert (moved["days"], moved["start"]) == ([4], "17:00")
    assert "poster" in window.session.assignments, "the save under way went through too"
