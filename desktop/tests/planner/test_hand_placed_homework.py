# ruff: noqa: F811
"""Homework the student puts somewhere by hand: dropped on the calendar, chosen in a dialog, moved to
another day. It is pinned, it is one Undo step, and Replan all leaves it where it was put."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    settled,
    window,  # noqa: F401
)


def test_homework_moved_by_hand_to_another_day_is_saved_pinned(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The server accepts the pin, and it survives a reload."""
    work = next(block for block in window.session.blocks if block.get("assignment_id") == "essay")
    assert window.session.hand_move(work["id"], 3, 4, 19 * 60, 20 * 60)
    window.session.save()
    settled(qapp, window)
    window.session.load_week(window.session.week_start, discard=True)
    settled(qapp, window)
    moved = next(block for block in window.session.blocks if block["id"] == work["id"])
    assert (moved["days"], moved["start"], moved.get("pinned")) == ([4], "19:00", True)




