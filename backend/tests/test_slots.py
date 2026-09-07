import pytest
from pydantic import ValidationError

from backend.models import TimeBlock
from backend.slots import (
    SLOTS_PER_DAY,
    hhmm_to_minutes,
    hhmm_to_slot,
    minutes_to_hhmm,
    overlaps,
    slot_to_hhmm,
)
from backend.solver import solve


def test_slots_per_day_is_68() -> None:
    assert SLOTS_PER_DAY == 68


def test_hhmm_roundtrip() -> None:
    assert minutes_to_hhmm(hhmm_to_minutes("06:00")) == "06:00"
    assert minutes_to_hhmm(hhmm_to_minutes("23:00")) == "23:00"
    assert slot_to_hhmm(hhmm_to_slot("06:00")) == "06:00"
    assert slot_to_hhmm(hhmm_to_slot("16:00")) == "16:00"


def test_rejects_off_grid_time() -> None:
    with pytest.raises(ValueError):
        hhmm_to_slot("08:10")


def test_rejects_before_day_start() -> None:
    with pytest.raises(ValueError):
        hhmm_to_slot("05:45")


def test_rejects_day_end_as_start() -> None:
    with pytest.raises(ValueError):
        hhmm_to_slot("23:00")
    with pytest.raises(ValueError):
        slot_to_hhmm(SLOTS_PER_DAY)


def test_rejects_bad_hhmm() -> None:
    with pytest.raises(ValueError):
        hhmm_to_minutes("8")
    with pytest.raises(ValueError):
        hhmm_to_minutes("24:00")


def test_overlaps_half_open() -> None:
    assert overlaps(8 * 60, 9 * 60, 8 * 60 + 30, 9 * 60 + 30)
    assert not overlaps(8 * 60, 9 * 60, 9 * 60, 10 * 60)
    assert not overlaps(10 * 60, 11 * 60, 8 * 60, 9 * 60)


def test_duration_must_be_multiple_of_15() -> None:
    with pytest.raises(ValidationError):
        TimeBlock(
            id="bad",
            title="Bad",
            kind="flexible",
            duration_min=10,
            days=[0],
        )


def test_days_must_be_in_week() -> None:
    with pytest.raises(ValidationError):
        TimeBlock(
            id="bad",
            title="Bad",
            kind="locked",
            duration_min=15,
            days=[7],
            start="08:00",
        )


def test_stub_solver_keeps_locked_unplaces_flexible() -> None:
    locked = TimeBlock(
        id="school",
        title="School",
        kind="locked",
        duration_min=60,
        days=[0],
        start="08:00",
    )
    flexible = TimeBlock(
        id="hw",
        title="HW",
        kind="flexible",
        duration_min=30,
        days=[0],
    )
    trace = solve([locked, flexible])
    assert [block.id for block in trace.placed] == ["school"]
    assert [block.id for block in trace.unplaced] == ["hw"]
    assert trace.complete is False


def test_empty_week_is_complete() -> None:
    trace = solve([])
    assert trace.complete is True
    assert trace.placed == []
    assert trace.unplaced == []
