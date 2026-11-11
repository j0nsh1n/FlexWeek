# ruff: noqa: F811
"""The times Material's Add and Edit fixed time and homework sheets offer follow the time step the student
chose (5 or 15 minutes): 96 start times a day on quarter hours, 288 on fives. A time already on the block
stays listed whatever the step, and on today the times already over stay hidden.

The clock is Thursday 19:00 of the open week (index 3). Counts come from the day: 24 hours of 60 / step.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.tests.fake_clock import CLOCK
from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)

THURSDAY, FRIDAY = 3, 4
STEPS = pytest.mark.parametrize(("step", "count"), [(15, 96), (5, 288)])


def _use_step(shell: NativeWindow, minutes: int) -> None:
    shell.session.preferences = {**(shell.session.preferences or {}), "drag_step_min": minutes}


def _minutes(clock: str) -> int:
    return int(clock[:2]) * 60 + int(clock[3:])


@STEPS
def test_add_fixed_time_offers_starts_and_ends_at_the_step(
    qapp, shell, sheets, step: int, count: int
) -> None:
    _use_step(shell, step)
    sheets.openBlock()
    pump(qapp)
    form = sheets.form
    starts = [item["value"] for item in form["startOptions"]]
    ends = [item["value"] for item in form["endOptions"]]
    assert len(starts) == count
    assert (starts[0], starts[-1]) == ("00:00", f"23:{60 - step}")
    assert [_minutes(clock) for clock in starts] == list(range(0, 24 * 60, step))
    assert ends == list(range(step, 24 * 60 + 1, step))


@STEPS
def test_edit_fixed_time_keeps_an_off_step_time_the_block_already_has(
    qapp, shell, sheets, step: int, count: int
) -> None:
    shell.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "09:20",
            "duration_min": 50,
            "days": [FRIDAY],
        }
    )
    shell.session.save()
    settle(qapp, shell)
    _use_step(shell, step)
    sheets.editBlock("club", FRIDAY)
    pump(qapp)
    form = sheets.form
    starts = [item["value"] for item in form["startOptions"]]
    ends = [item["value"] for item in form["endOptions"]]
    # 09:20 is a mark at 5 minutes and not at 15; the end, 10:10, likewise.
    on_step_already = step == 5
    assert len(starts) == count + (0 if on_step_already else 1)
    assert len(ends) == count + (0 if on_step_already else 1)
    assert starts.count("09:20") == 1
    assert ends.count(10 * 60 + 10) == 1


@STEPS
def test_homework_due_time_and_pinned_time_lists_follow_the_step(
    qapp, shell, sheets, step: int, count: int
) -> None:
    _use_step(shell, step)
    sheets.openHomework()
    pump(qapp)
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", FRIDAY)
    form = sheets.form
    due = [item["value"] for item in form["timeOptions"]]
    pinned = [item["value"] for item in form["pinnedTimeOptions"]]
    assert due == ["", *(f"{m // 60:02d}:{m % 60:02d}" for m in range(0, 24 * 60, step))]
    assert len(due) == count + 1
    assert [_minutes(clock) for clock in pinned] == list(range(0, 24 * 60, step))


@STEPS
def test_today_hides_the_pinned_times_already_over(qapp, shell, sheets, step: int, count: int) -> None:
    _use_step(shell, step)
    sheets.openHomework()
    pump(qapp)
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", THURSDAY)
    pinned = [_minutes(item["value"]) for item in sheets.form["pinnedTimeOptions"]]
    # The clock is 19:00 exactly, so 19:00 is still ahead.
    assert pinned == list(range(19 * 60, 24 * 60, step))


def test_a_clock_between_marks_starts_todays_pinned_times_at_the_next_mark_of_the_step(
    qapp, shell, sheets
) -> None:
    CLOCK.set(
        datetime.fromisoformat(shell.session.week_start) + timedelta(days=THURSDAY, hours=19, minutes=2)
    )
    for step, first in ((5, 19 * 60 + 5), (15, 19 * 60 + 15)):
        _use_step(shell, step)
        sheets.openHomework()
        pump(qapp)
        sheets.setText("when", "fixed")
        sheets.setNumber("whenDay", THURSDAY)
        pinned = [_minutes(item["value"]) for item in sheets.form["pinnedTimeOptions"]]
        assert pinned[0] == first, step
        sheets.forceClose()
        pump(qapp)


@STEPS
def test_edit_homework_keeps_its_off_step_pin_in_the_list(qapp, shell, sheets, step: int, count: int) -> None:
    work = next(block for block in shell.session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:55", "days": [FRIDAY], "pinned": True})
    shell.session.add_block(work)
    shell.session.save()
    settle(qapp, shell)
    _use_step(shell, step)
    sheets.editHomework("essay")
    pump(qapp)
    pinned = [item["value"] for item in sheets.form["pinnedTimeOptions"]]
    assert pinned.count("18:55") == 1
    # 18:55 is a mark at 5 minutes and not at 15.
    assert len(pinned) == count + (0 if step == 5 else 1)
