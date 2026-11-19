"""Overdue and left-over homework as the student reads and uses it: the chip and the planning box, the
More badge, the Unfinished rows, the week list and the focus list. Held-clock scenario: Bio reading
placed Wednesday 3:15 PM of the open week, due Friday 23:59, not ticked, clock Saturday 10:00."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


from desktop.tests.grid_support import qapp, signed_in, window  # noqa: F401
from desktop.tests.planner.support import (
    overdue_this_week,
)


def test_the_overdue_focus_row_starts_from_the_homework(qapp, window) -> None:
    block_id = overdue_this_week(qapp, window)
    row = next(item for item in window.session.focus_tasks() if item["title"] == "Bio reading, overdue")
    assert row["id"] == "bio" and row["id"] != block_id
    assert window.session.start_focus(row["id"], row["day"]) is True
    focus = window.session.focus
    assert focus["title"] == "Bio reading, overdue"
    assert focus["assignmentId"] == "bio" and focus["blockId"] is None
