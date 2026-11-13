"""Week-date arithmetic. The engine does the work. These names stay."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import cast

import flexweek_engine  # type: ignore[import-untyped]
from flexweek_engine import (  # type: ignore[import-untyped]
    is_calendar_date,
    is_month_label,
    is_week_start,
    monday_of,
    month_grid,
    parse_month,
)

from backend import clock

FIRST_DAY = date(2000, 1, 1)
LAST_DAY = date(2099, 12, 31)
FIRST_WEEK_START = date(1999, 12, 27)
# date.fromisoformat also accepts "20260907" and "2026-W37-1"; a week label is
# always the padded calendar form, so the shape is pinned before parsing.
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# [0-9], not \d: date.fromisoformat guards ISO_DATE against Unicode digits, but
# parse_month feeds int() directly, which would accept them.
ISO_MONTH = re.compile(r"[0-9]{4}-[0-9]{2}")

__all__ = [
    "FIRST_DAY",
    "FIRST_WEEK_START",
    "ISO_DATE",
    "ISO_MONTH",
    "LAST_DAY",
    "compose_shown_week",
    "current_week_start",
    "is_calendar_date",
    "is_month_label",
    "is_week_start",
    "monday_of",
    "month_grid",
    "parse_month",
    "repeat_changes_from_shown_week",
    "shown_week_parts",
    "split_shown_week",
]


def current_week_start() -> str:
    """This week's Monday on the app's clock (the engine's own version reads the real date)."""
    return str(monday_of(clock.today().isoformat()))


def shown_week_parts(week_start: str) -> tuple[str, str, int] | None:
    """The two stored (Monday) weeks a week on screen from `week_start` covers, and how many days into
    the first it starts; None for a Monday."""
    return cast("tuple[str, str, int] | None", flexweek_engine.shown_week_parts(week_start))


def compose_shown_week(week_start: str, first: list[dict], second: list[dict]) -> list[dict]:
    shown: list[dict] = json.loads(
        flexweek_engine.compose_shown_week(week_start, json.dumps(first), json.dumps(second))
    )
    return shown


def split_shown_week(
    week_start: str, shown: list[dict], first: list[dict], second: list[dict]
) -> tuple[list[dict], list[dict]]:
    first_text, second_text = flexweek_engine.split_shown_week(
        week_start, json.dumps(shown), json.dumps(first), json.dumps(second)
    )
    return json.loads(first_text), json.loads(second_text)


def repeat_changes_from_shown_week(changes: list[dict], week_start: str) -> list[dict]:
    moved: list[dict] = json.loads(
        flexweek_engine.repeat_changes_from_shown_week(json.dumps(changes), week_start)
    )
    return moved
