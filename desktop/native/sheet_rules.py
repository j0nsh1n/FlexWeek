"""Rules and wording the block, homework and running-late sheets share."""

from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

import flexweek_engine  # type: ignore[import-untyped]

SPREAD_NOTHING = flexweek_engine.VIEW_SPREAD_NOTHING
SLOT_HINT = flexweek_engine.VIEW_SLOT_HINT
DUE_PASSED = flexweek_engine.VIEW_DUE_PASSED
ESTIMATE_ERROR = flexweek_engine.VIEW_ESTIMATE_ERROR
ESTIMATE_SHORT = flexweek_engine.VIEW_ESTIMATE_SHORT
ESTIMATE_LONG = flexweek_engine.VIEW_ESTIMATE_LONG
HOMEWORK_PROBLEMS = flexweek_engine.VIEW_HOMEWORK_PROBLEMS
HOMEWORK_REFUSED = flexweek_engine.VIEW_HOMEWORK_REFUSED
REPEAT_NOTE = flexweek_engine.VIEW_REPEAT_NOTE
LATE_WAIT = flexweek_engine.VIEW_LATE_WAIT
BLOCK_PROBLEMS = flexweek_engine.VIEW_BLOCK_PROBLEMS
BLOCK_REFUSED = flexweek_engine.VIEW_BLOCK_REFUSED
CUTOFFS = flexweek_engine.VIEW_CUTOFFS


def guess_locked_category(start: str) -> str:
    """A category for a new fixed time, from when it starts, until the student picks one."""
    return flexweek_engine.view_guess_locked_category(start)


def short_day_name(week_start: str, day: int) -> str:
    """Day `day` of the week from `week_start` named from its date ("Wed"); Monday first with no week."""
    return flexweek_engine.view_short_day_name(week_start, day)


def same_weekday(day: int, from_week: str, to_week: str) -> int:
    """Day `day` of the week from `from_week` as the day of the week from `to_week` with its weekday."""
    return flexweek_engine.view_same_weekday(day, from_week, to_week)


def full_day_name(week_start: str, day: int) -> str:
    """`short_day_name` written out: "Wednesday"."""
    return flexweek_engine.view_full_day_name(week_start, day)


def turn_days_keeping_weekdays(
    days: list[int] | tuple[int, ...], from_week: str, to_week: str
) -> tuple[list[int], list[tuple[int, int]]]:
    """Day numbers turned to the week now open, with the ones whose date changed as (old, new) pairs."""
    return flexweek_engine.view_turn_days_keeping_weekdays(json.dumps(days), from_week, to_week)


def first_day_changed(from_week: str, to_week: str) -> bool:
    """Whether the two weeks start on different days of the week."""
    return flexweek_engine.view_first_day_changed(from_week, to_week)


def moved_day_names(old_day: int, from_week: str, new_day: int, to_week: str) -> tuple[str, str]:
    """A moved tick's old and new names the way the note names them."""
    return flexweek_engine.view_moved_day_names(old_day, from_week, new_day, to_week)


def moved_across_months(old_day: int, from_week: str, new_day: int, to_week: str) -> bool:
    """Whether a moved tick's old and new dates are in different months."""
    return flexweek_engine.view_moved_across_months(old_day, from_week, new_day, to_week)


def moved_days_note(moves: list[tuple[str, str]]) -> str:
    """Old and new day names as the one line under the row. Empty with no moves."""
    return flexweek_engine.view_moved_days_note(json.dumps(moves))


def day_range_words(days: list[int] | tuple[int, ...], week_start: str = "") -> str:
    """Three or more days in a row as a range; otherwise a list. Days follow `week_start`."""
    return flexweek_engine.view_day_range_words(json.dumps(days), week_start)


def day_range_and_words(days: list[int] | tuple[int, ...], week_start: str = "") -> str:
    return flexweek_engine.view_day_range_and_words(json.dumps(days), week_start)


def block_sheet_problem(block: dict) -> tuple[str, str] | None:
    """First failing field and student-facing sentence for a block sheet, or None when valid."""
    return flexweek_engine.block_sheet_problem(json.dumps(block))


def homework_sheet_problem(homework: dict) -> tuple[str, str] | None:
    """First failing field and student-facing sentence for a homework sheet, or None when valid."""
    return flexweek_engine.homework_sheet_problem(json.dumps(homework))


def _preset_locked(
    category: str | None, day: int, start: str, duration_min: int, week_start: str = ""
) -> dict:
    """A new fixed time with its category's preset. The fresh id stays here: Rust does not draw one."""
    fresh = str(uuid4())
    return json.loads(
        flexweek_engine.view_preset_locked(
            json.dumps(
                {
                    "id": fresh,
                    "category": category,
                    "day": day,
                    "start": start,
                    "duration_min": duration_min,
                    "week_start": week_start,
                }
            )
        )
    )


def spread_words(sessions: list[dict], due: str, today: date) -> str:
    """What spreading will do, for the grey line under the choice."""
    return flexweek_engine.view_spread_words(json.dumps(sessions), due, today.isoformat())


def today_from_words(minute: int) -> str:
    """The next quarter hour from `minute`, or nothing once the day has no quarter hour left."""
    return flexweek_engine.view_today_from_words(minute)


def _unbroken_time(text: str) -> str:
    """Keep a time's own AM/PM on the same line. A title such as "PM review" keeps its plain space."""
    return flexweek_engine.view_unbroken_time(text)


def _late_summary(moved: int) -> str:
    return flexweek_engine.view_late_summary(moved)


def _late_move(move: dict, block: dict, title: str, week_start: str = "") -> str:
    return flexweek_engine.view_late_move(json.dumps(move), json.dumps(block), title, week_start)
