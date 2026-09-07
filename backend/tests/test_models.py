"""Tests for FlexWeek models and slot helpers (≥10 cases)."""

from __future__ import annotations

from datetime import datetime

import pytest

from backend.models import (
    DAYS_PER_WEEK,
    SLOT_MINUTES,
    SLOTS_PER_DAY,
    TOTAL_SLOTS,
    Move,
    SolveTrace,
    TimeBlock,
    all_slots,
    block_end,
    duration_in_slots,
    format_local,
    overlaps,
    parse_local,
    slot_index,
    slot_to_start,
    validate_duration,
    week_start_monday,
)

WEEK = datetime(2026, 9, 7)  # Monday


def test_slots_per_day_and_week_totals():
    assert SLOTS_PER_DAY == 68
    assert DAYS_PER_WEEK == 7
    assert TOTAL_SLOTS == 476
    assert SLOT_MINUTES == 15


def test_all_slots_count_and_bounds():
    slots = all_slots(WEEK)
    assert len(slots) == 476
    assert slots[0] == "2026-09-07T06:00"
    assert slots[67] == "2026-09-07T22:45"
    assert slots[68] == "2026-09-08T06:00"
    assert slots[-1] == "2026-09-13T22:45"


def test_validate_duration_accepts_multiples_of_15():
    assert validate_duration(15) is True
    assert validate_duration(30) is True
    assert validate_duration(90) is True
    assert validate_duration(0) is False
    assert validate_duration(10) is False
    assert validate_duration(-15) is False


def test_duration_in_slots():
    assert duration_in_slots(15) == 1
    assert duration_in_slots(60) == 4
    with pytest.raises(ValueError):
        duration_in_slots(20)


def test_overlaps_partial_and_touching():
    # Partial overlap
    assert overlaps("2026-09-07T10:00", "2026-09-07T11:00", "2026-09-07T10:30", "2026-09-07T11:30")
    # Identical
    assert overlaps("2026-09-07T10:00", "2026-09-07T11:00", "2026-09-07T10:00", "2026-09-07T11:00")
    # Touching endpoints (half-open) — no overlap
    assert not overlaps("2026-09-07T10:00", "2026-09-07T11:00", "2026-09-07T11:00", "2026-09-07T12:00")
    # Disjoint
    assert not overlaps("2026-09-07T08:00", "2026-09-07T09:00", "2026-09-07T10:00", "2026-09-07T11:00")


def test_overlaps_nested_range():
    assert overlaps("2026-09-07T09:00", "2026-09-07T12:00", "2026-09-07T10:00", "2026-09-07T10:30")


def test_parse_and_format_roundtrip():
    s = "2026-09-07T14:30"
    assert format_local(parse_local(s)) == s


def test_block_end():
    assert block_end("2026-09-07T08:00", 90) == "2026-09-07T09:30"
    assert block_end("2026-09-07T22:00", 60) == "2026-09-07T23:00"


def test_week_start_monday():
    assert week_start_monday("2026-09-09T15:00") == WEEK
    assert week_start_monday("2026-09-07T06:00") == WEEK
    assert week_start_monday("2026-09-13T22:00") == WEEK


def test_slot_index_and_inverse():
    idx = slot_index("2026-09-07T06:00", WEEK)
    assert idx == 0
    assert slot_to_start(0, WEEK) == "2026-09-07T06:00"

    idx = slot_index("2026-09-07T14:30", WEEK)
    assert slot_to_start(idx, WEEK) == "2026-09-07T14:30"

    # Tuesday first slot
    assert slot_index("2026-09-08T06:00", WEEK) == 68


def test_slot_index_rejects_outside_hours_and_misaligned():
    with pytest.raises(ValueError):
        slot_index("2026-09-07T05:45", WEEK)
    with pytest.raises(ValueError):
        slot_index("2026-09-07T23:00", WEEK)
    with pytest.raises(ValueError):
        slot_index("2026-09-07T06:10", WEEK)


def test_timeblock_and_solve_trace_dataclasses():
    locked = TimeBlock(
        id="b1",
        title="School",
        kind="locked",
        duration_min=60,
        days=[0],
        priority=1,
        energy="medium",
        start="2026-09-07T08:00",
    )
    flex = TimeBlock(
        id="b2",
        title="Homework",
        kind="flexible",
        duration_min=45,
        days=[0, 1],
        priority=2,
        energy="high",
        latest="2026-09-08T21:00",
    )
    move = Move(block_id="b2", reason="deadline pressure", from_start=None, to_start="2026-09-07T16:00")
    trace = SolveTrace(
        placed=[locked],
        unplaced=[flex],
        moves=[move],
        failed_constraints=["no free slot before latest"],
        solve_ms=0.0,
        complete=False,
    )
    assert locked.kind == "locked"
    assert flex.priority == 2
    assert trace.complete is False
    assert len(trace.moves) == 1


def test_slot_to_start_out_of_range():
    with pytest.raises(ValueError):
        slot_to_start(-1, WEEK)
    with pytest.raises(ValueError):
        slot_to_start(476, WEEK)
