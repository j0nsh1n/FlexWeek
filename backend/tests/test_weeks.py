"""Unit checks for the week-date helpers in backend/weeks.py."""

from __future__ import annotations

import pytest

from backend.weeks import is_week_start, monday_of


def test_monday_of_maps_every_day_of_one_week_to_its_monday() -> None:
    # 2026-09-07..2026-09-13 is one Monday..Sunday week.
    for day in ("2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-12", "2026-09-13"):
        assert monday_of(day) == "2026-09-07"


def test_monday_of_rejects_malformed_and_non_calendar_shapes() -> None:
    # "20260907" and "2026-W37-1" parse under date.fromisoformat but are not a week label's shape.
    for value in ("", "2026-09-7", "not-a-date", "2026-13-40", "20260907", "2026-W37-1"):
        with pytest.raises(ValueError):
            monday_of(value)


def test_monday_of_accepts_the_range_boundaries_and_rejects_outside_them() -> None:
    assert monday_of("2000-01-03") == "2000-01-03"
    assert monday_of("2099-12-31") == "2099-12-28"
    with pytest.raises(ValueError):
        monday_of("1999-12-31")
    with pytest.raises(ValueError):
        monday_of("2100-01-01")


def test_is_week_start_is_true_only_for_an_in_range_monday() -> None:
    assert is_week_start("2026-09-07") is True
    for value in (
        "2026-09-08",
        "2026-09-13",
        "2026-9-7",
        "20260907",
        "2026-W37-1",
        "1999-12-27",
        "2100-01-04",
    ):
        assert is_week_start(value) is False


def test_monday_of_crosses_month_and_year_boundaries() -> None:
    assert monday_of("2026-10-01") == "2026-09-28"
    assert monday_of("2027-01-01") == "2026-12-28"
