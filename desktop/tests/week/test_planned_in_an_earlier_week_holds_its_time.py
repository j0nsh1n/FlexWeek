"""A session in any week holds its time when it is ticked done or its time is still ahead of now; only a
session whose time passed unfinished needs a new one (spec.md, the count of time still needed). The case
a student saw (Widgets, in test_next_week_nothing_left.py): all homework planned later this week, Next
week pressed, nothing is left. Calendar: the clock reads Thursday 5 November 2026, 19:00 (the shared fake
clock); this week is Monday 2 November, so Friday 6 at 10:00 is ahead and Wednesday 4 at 10:00 is over."""

# ruff: noqa: F811
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import (
    _bridge,
    _homework,
    _pump,
    _qml,
    _reset,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401

FRIDAY = 4
WEDNESDAY = 2


def _sunday(window) -> str:
    return (_week_monday(window) + timedelta(days=6)).isoformat() + "T23:59"


def _hold(window, qapp, key: str, day: int, start: str, *, pinned: bool = True) -> None:
    """The homework's one 60 minute session at `start` on `day` of this week, saved."""
    session = window.session
    block = next(item for item in session.blocks if item.get("assignment_id") == key)
    block.update(duration_min=60, pinned=pinned, start=start, days=[day])
    session._touch()
    session.save()
    settled(qapp, window)


def _open_next_week(window, qapp, *, read: bool = True) -> None:
    session = window.session
    session.load_week((_week_monday(window) + timedelta(days=7)).isoformat())
    settled(qapp, window)
    if read:
        wait_until(qapp, lambda: all("planned_min" in item for item in session.assignments.values()))
    _pump(qapp)


def _needed(window) -> dict[str, int]:
    return {item["assignment_id"]: item["minutes"] for item in window.session.homework_time_needed()}


def test_material_next_week_has_nothing_left_when_this_week_holds_all_of_it(qapp, window) -> None:
    """The same in the Material drawer. Three 60 minute homework due this Sunday, each with its session on
    Friday (10:00, 11:30, 13:00), ahead of Thursday 19:00. Next week open: the server counts them as held
    (planned 60 each), so 0 are needed, the drawer lists no card and no line, Plan is off, and a Plan that
    is pressed anyway places nothing and says nothing is left needing a time."""
    root = _reset(window, qapp)
    session = window.session
    due = _sunday(window)
    _homework(window, "math", "Math worksheet", 60, due)
    _homework(window, "chem", "Chem lab report", 60, due)
    for key, start in (("essay", "10:00"), ("math", "11:30"), ("chem", "13:00")):
        _hold(window, qapp, key, FRIDAY, start)
    _open_next_week(window, qapp)
    wait_until(qapp, lambda: all(item.get("planned_min") == 60 for item in session.assignments.values()))
    _pump(qapp)

    assert _needed(window) == {}
    assert _bridge(window).week.property("homeworkCount") == 0
    assert str(_bridge(window).week.property("leftoverWords")) == ""
    assert _qml(root, "planHomework").property("enabled") is False
    session.solve()
    settled(qapp, window)
    assert "still needs a time" not in session.message, session.message
    assert _needed(window) == {}


@pytest.mark.parametrize(
    ("day", "start", "needed"),
    [
        # Friday 10:00 is ahead of Thursday 19:00: it holds its 60 minutes, 60 - 60 = 0 needed.
        (FRIDAY, "10:00", 0),
        # Wednesday 10:00 is over and unfinished: it holds nothing, so all 60 need a time.
        (WEDNESDAY, "10:00", 60),
    ],
)
def test_next_week_counts_a_session_of_this_week_by_whether_its_time_is_ahead(
    qapp, window, day: int, start: str, needed: int
) -> None:
    """Essay (60) with its one session this week, next week open. Pinned or not, a session whose time is
    ahead of now holds it; one whose time passed unfinished does not, and its minutes are still needed."""
    _reset(window, qapp)
    _hold(window, qapp, "essay", day, start)
    _open_next_week(window, qapp)
    wait_until(qapp, lambda: window.session.assignments["essay"].get("planned_min") == 60 - needed)

    assert _needed(window).get("essay", 0) == needed


def test_a_session_ticked_done_in_this_week_is_not_needed_again_next_week(qapp, window) -> None:
    """Essay (60), its session on Wednesday 10:00 (over) ticked done: that is 60 minutes of done time, so
    next week still needs 0, with no help from the clock."""
    _reset(window, qapp)
    _hold(window, qapp, "essay", WEDNESDAY, "10:00")
    block = next(item for item in window.session.blocks if item.get("assignment_id") == "essay")
    block["completed"] = True
    window.session._touch()
    window.session.save()
    settled(qapp, window)
    _open_next_week(window, qapp)
    wait_until(qapp, lambda: window.session.assignments["essay"].get("done_min") == 60)

    assert _needed(window).get("essay", 0) == 0
