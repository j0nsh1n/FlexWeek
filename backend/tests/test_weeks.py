"""Unit checks for the week-date helpers in backend/weeks.py."""

from __future__ import annotations

from datetime import date

import pytest

from backend.weeks import is_month_label, is_week_start, monday_of, month_grid, parse_month


def test_monday_of_maps_every_day_of_one_week_to_its_monday() -> None:
    # 2026-09-07..2026-09-13 is one Monday..Sunday week.
    for day in (
        "2026-09-07",
        "2026-09-08",
        "2026-09-09",
        "2026-09-10",
        "2026-09-11",
        "2026-09-12",
        "2026-09-13",
    ):
        assert monday_of(day) == "2026-09-07"


def test_monday_of_rejects_malformed_and_non_calendar_shapes() -> None:
    # "20260907" and "2026-W37-1" parse under date.fromisoformat but are not a week label's shape.
    for value in ("", "2026-09-7", "not-a-date", "2026-13-40", "20260907", "2026-W37-1"):
        with pytest.raises(ValueError):
            monday_of(value)


def test_monday_of_accepts_the_range_boundaries_and_rejects_outside_them() -> None:
    assert monday_of("2000-01-01") == "1999-12-27"
    assert monday_of("2000-01-03") == "2000-01-03"
    assert monday_of("2099-12-31") == "2099-12-28"
    with pytest.raises(ValueError):
        monday_of("1999-12-31")
    with pytest.raises(ValueError):
        monday_of("2100-01-01")


def test_is_week_start_is_true_only_for_an_in_range_monday() -> None:
    assert is_week_start("2026-09-07") is True
    assert is_week_start("1999-12-27") is True
    for value in (
        "2026-09-08",
        "2026-09-13",
        "2026-9-7",
        "20260907",
        "2026-W37-1",
        "1999-12-20",
        "1999-12-28",
        "2100-01-04",
    ):
        assert is_week_start(value) is False


def test_monday_of_crosses_month_and_year_boundaries() -> None:
    assert monday_of("2026-10-01") == "2026-09-28"
    assert monday_of("2027-01-01") == "2026-12-28"


def test_parse_month_returns_first_and_last_calendar_dates() -> None:
    assert parse_month("2026-09") == (date(2026, 9, 1), date(2026, 9, 30))
    assert parse_month("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert parse_month("2000-01") == (date(2000, 1, 1), date(2000, 1, 31))
    assert parse_month("2099-12") == (date(2099, 12, 1), date(2099, 12, 31))


def test_parse_month_rejects_malformed_and_out_of_range_labels() -> None:
    for value in ("", "2026-9", "2026-09-01", "2026-13", "1999-12", "2100-01", "202609"):
        with pytest.raises(ValueError):
            parse_month(value)
        assert is_month_label(value) is False
    assert is_month_label("2026-09") is True


def test_month_grid_pads_complete_weeks_and_clips_the_supported_range() -> None:
    assert month_grid(date(2026, 9, 1), date(2026, 9, 30)) == (date(2026, 8, 31), date(2026, 10, 4))
    assert month_grid(date(2000, 1, 1), date(2000, 1, 31)) == (date(2000, 1, 1), date(2000, 2, 6))
    assert month_grid(date(2099, 12, 1), date(2099, 12, 31)) == (date(2099, 11, 30), date(2099, 12, 31))
