"""Core data models and slot helpers for FlexWeek.

Times are naive local strings in YYYY-MM-DDTHH:mm (America/Los_Angeles).
No timezone math — treat strings as opaque local clock times.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

BlockKind = Literal["locked", "flexible"]
Priority = Literal[1, 2, 3, 4]  # 1 = test, 4 = reading
Energy = Literal["high", "medium", "low"]

DAY_START_HOUR = 6
DAY_END_HOUR = 23
SLOT_MINUTES = 15
SLOTS_PER_DAY = ((DAY_END_HOUR - DAY_START_HOUR) * 60) // SLOT_MINUTES  # 68
DAYS_PER_WEEK = 7
TOTAL_SLOTS = SLOTS_PER_DAY * DAYS_PER_WEEK  # 476

TIME_FMT = "%Y-%m-%dT%H:%M"


@dataclass
class TimeBlock:
    id: str
    title: str
    kind: BlockKind
    duration_min: int  # multiple of 15
    days: list[int]  # 0–6
    priority: Priority
    energy: Energy
    earliest: str | None = None
    latest: str | None = None
    start: str | None = None
    course: str | None = None


@dataclass
class Move:
    block_id: str
    reason: str
    from_start: str | None = None
    to_start: str | None = None


@dataclass
class SolveTrace:
    placed: list[TimeBlock]
    unplaced: list[TimeBlock]
    moves: list[Move]
    failed_constraints: list[str]
    solve_ms: float
    complete: bool


def parse_local(ts: str) -> datetime:
    """Parse a naive local YYYY-MM-DDTHH:mm timestamp."""
    return datetime.strptime(ts, TIME_FMT)


def format_local(dt: datetime) -> str:
    """Format a datetime as YYYY-MM-DDTHH:mm."""
    return dt.strftime(TIME_FMT)


def validate_duration(duration_min: int) -> bool:
    """Return True if duration is a positive multiple of 15 minutes."""
    return isinstance(duration_min, int) and duration_min > 0 and duration_min % SLOT_MINUTES == 0


def overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    """Return True if the half-open ranges [a_start, a_end) and [b_start, b_end) overlap."""
    a0, a1 = parse_local(a_start), parse_local(a_end)
    b0, b1 = parse_local(b_start), parse_local(b_end)
    return a0 < b1 and b0 < a1


def block_end(start: str, duration_min: int) -> str:
    """Return the end timestamp for a block starting at start lasting duration_min."""
    return format_local(parse_local(start) + timedelta(minutes=duration_min))


def week_start_monday(any_day: str) -> datetime:
    """Return Monday 00:00 of the week containing any_day (YYYY-MM-DDTHH:mm or date-ish)."""
    dt = parse_local(any_day) if "T" in any_day else datetime.strptime(any_day[:10], "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def slot_index(start: str, week_monday: datetime | None = None) -> int:
    """Map a start time to a 0-based slot index within the Mon–Sun 6:00–23:00 grid.

    Raises ValueError if outside the week grid or not aligned to 15 minutes.
    """
    dt = parse_local(start)
    if week_monday is None:
        week_monday = week_start_monday(start)
    day = (dt.date() - week_monday.date()).days
    if day < 0 or day >= DAYS_PER_WEEK:
        raise ValueError(f"start {start} is outside the target week")
    minutes = dt.hour * 60 + dt.minute
    day_start = DAY_START_HOUR * 60
    day_end = DAY_END_HOUR * 60
    if minutes < day_start or minutes >= day_end:
        raise ValueError(f"start {start} is outside {DAY_START_HOUR}:00–{DAY_END_HOUR}:00")
    if (minutes - day_start) % SLOT_MINUTES != 0:
        raise ValueError(f"start {start} is not aligned to {SLOT_MINUTES}-minute slots")
    return day * SLOTS_PER_DAY + (minutes - day_start) // SLOT_MINUTES


def slot_to_start(index: int, week_monday: datetime) -> str:
    """Inverse of slot_index: slot index → YYYY-MM-DDTHH:mm."""
    if index < 0 or index >= TOTAL_SLOTS:
        raise ValueError(f"slot index {index} out of range 0..{TOTAL_SLOTS - 1}")
    day = index // SLOTS_PER_DAY
    slot_in_day = index % SLOTS_PER_DAY
    minutes = DAY_START_HOUR * 60 + slot_in_day * SLOT_MINUTES
    dt = week_monday + timedelta(days=day, hours=minutes // 60, minutes=minutes % 60)
    return format_local(dt)


def all_slots(week_monday: datetime) -> list[str]:
    """Return all 476 slot start times for Mon–Sun 6:00–23:00."""
    return [slot_to_start(i, week_monday) for i in range(TOTAL_SLOTS)]


def duration_in_slots(duration_min: int) -> int:
    """Convert a validated duration to number of 15-min slots."""
    if not validate_duration(duration_min):
        raise ValueError(f"duration_min {duration_min} must be a positive multiple of {SLOT_MINUTES}")
    return duration_min // SLOT_MINUTES
