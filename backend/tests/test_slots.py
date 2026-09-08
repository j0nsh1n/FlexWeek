import pytest
from pydantic import ValidationError

from backend.models import TimeBlock
from backend.slots import (
    SLOTS_PER_DAY,
    hhmm_to_minutes,
    hhmm_to_slot,
    minutes_to_hhmm,
    overlaps,
    parse_deadline,
    slot_to_hhmm,
)


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


def test_parse_deadline_english_weekday() -> None:
    assert parse_deadline("Thursday 21:00", [0, 1, 2, 3, 4]) == (3, 21 * 60)
    assert parse_deadline("Wednesday 07:45", [0, 1, 2]) == (2, 7 * 60 + 45)


def test_parse_deadline_iso_timestamp_uses_time_only() -> None:
    assert parse_deadline("2026-09-10T21:00", [0, 1, 2, 3]) == (3, 21 * 60)


def test_parse_deadline_bare_time_uses_last_day() -> None:
    assert parse_deadline("21:00", [0, 1, 4]) == (4, 21 * 60)


def test_parse_deadline_none() -> None:
    assert parse_deadline(None, [0]) is None
    assert parse_deadline("", [0]) is None
