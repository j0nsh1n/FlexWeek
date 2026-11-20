"""A notice after a block is added or homework is placed names the day from its date. The clock is Thursday
5 November 2026, so a week from Wednesday runs Wed 4 to Tue 10 and a week from Sunday runs Sun 1 to Sat 7.
Column 2 is Friday 6 in the first and column 6 is Saturday 7 in the second (a Monday week would call them
Wed and Sun)."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from backend.tests.fake_clock import CLOCK, START
from desktop.native import fields
from desktop.native.calendar import sunday_due
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import (
    _bridge,
    _homework,
    _pump,
    _show_material,
    _snack,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


@pytest.mark.parametrize(
    ("first_day", "iso", "column", "named"),
    [("wednesday", "2026-11-04", 2, "Fri"), ("sunday", "2026-11-01", 6, "Sat")],
)
def test_the_added_and_the_placed_notice_name_the_day_from_its_date(
    qapp, window, first_day: str, iso: str, column: int, named: str
) -> None:
    session = window.session
    fields.save_week_starts_on(first_day)
    wait_until(qapp, lambda: session.week_start == iso and not session.busy)
    settled(qapp, window)
    CLOCK.set(START.replace(hour=12, minute=0))
    _show_material(qapp, window)
    bridge = _bridge(window)
    sheets = bridge.sheets
    sheets.openBlockAt(column, 15 * 60, 16 * 60)
    sheets.setText("title", "Club")
    _pump(qapp, 20)
    sheets.save()
    wait_until(qapp, lambda: any(block["title"] == "Club" for block in session.blocks))
    settled(qapp, window)
    wait_until(qapp, lambda: sheets.notice != "", what="the added notice")
    said = [sheets.notice]

    _homework(window, "math", "Math worksheet", 60, sunday_due(session.week_start))
    math = next(block["id"] for block in session.blocks if block.get("assignment_id") == "math")
    bridge.week.placeHomework(math, column, 18 * 60)
    wait_until(qapp, lambda: next(b for b in session.blocks if b["id"] == math).get("start") == "18:00")
    settled(qapp, window)
    said.append(_snack(window))
    assert said == [
        f"Added Club on {named} 3:00 PM.",
        f"Placed Math worksheet on {named} 6:00 PM.",
    ]


def test_a_day_deleted_from_a_wednesday_week_is_said_by_its_own_name(qapp, window) -> None:
    """Club on Wednesday and Monday: day 5 of a week from Wednesday is Monday 9 November."""
    session = window.session
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: session.week_start == "2026-11-04" and not session.busy)
    club = {"id": "club", "title": "Club", "kind": "locked", "start": "16:00", "duration_min": 60}
    session.add_block({**club, "days": [0, 5]})
    session.save()
    settled(qapp, window)
    _show_material(qapp, window)
    sheets = _bridge(window).sheets
    sheets.askDeleteBlock("club", 5)
    sheets.answer("delete")
    settled(qapp, window)
    assert sheets.notice == "Deleted Club on Monday from this week."
