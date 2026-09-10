"""Week-date arithmetic. Imports no framework, like models.py."""

from __future__ import annotations

import re
from datetime import date, timedelta

FIRST_DAY = date(2000, 1, 1)
LAST_DAY = date(2099, 12, 31)
# date.fromisoformat also accepts "20260907" and "2026-W37-1"; a week label is
# always the padded calendar form, so the shape is pinned before parsing.
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _parse(value: str) -> date:
    if not ISO_DATE.fullmatch(value):
        raise ValueError("date must be written YYYY-MM-DD")
    day = date.fromisoformat(value)
    if not FIRST_DAY <= day <= LAST_DAY:
        raise ValueError("date must be between 2000-01-01 and 2099-12-31")
    return day


def monday_of(date_str: str) -> str:
    """The Monday of the week holding date_str. Raises on a malformed or out-of-range date."""
    day = _parse(date_str)
    return (day - timedelta(days=day.weekday())).isoformat()


def current_week_start() -> str:
    """The Monday of the server's local today."""
    return monday_of(date.today().isoformat())


def is_week_start(value: str) -> bool:
    """True when value is a well-formed, in-range Monday."""
    try:
        return _parse(value).weekday() == 0
    except ValueError:
        return False
