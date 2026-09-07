from __future__ import annotations

from backend.models import TimeBlock

SLOT_MIN = 15
DAY_START_MIN = 6 * 60
DAY_END_MIN = 23 * 60
SLOTS_PER_DAY = (DAY_END_MIN - DAY_START_MIN) // SLOT_MIN


def hhmm_to_minutes(hhmm: str) -> int:
    parts = hhmm.split(":")
    if len(parts) != 2:
        raise ValueError(f"expected HH:MM, got {hhmm!r}")
    hour, minute = int(parts[0]), int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"invalid time {hhmm!r}")
    return hour * 60 + minute


def minutes_to_hhmm(minutes: int) -> str:
    hour, minute = divmod(minutes, 60)
    return f"{hour:02d}:{minute:02d}"


def minutes_to_slot(minutes: int) -> int:
    # Grid is half-open [06:00, 23:00); 23:00 is the end of the last slot, not a start.
    if minutes < DAY_START_MIN or minutes >= DAY_END_MIN:
        raise ValueError("time is outside 06:00–23:00")
    offset = minutes - DAY_START_MIN
    if offset % SLOT_MIN:
        raise ValueError("time must land on a 15-minute slot")
    return offset // SLOT_MIN


def hhmm_to_slot(hhmm: str) -> int:
    return minutes_to_slot(hhmm_to_minutes(hhmm))


def slot_to_hhmm(slot: int) -> str:
    if slot < 0 or slot >= SLOTS_PER_DAY:
        raise ValueError("slot out of range")
    return minutes_to_hhmm(DAY_START_MIN + slot * SLOT_MIN)


def duration_to_slots(duration_min: int) -> int:
    if duration_min <= 0 or duration_min % SLOT_MIN:
        raise ValueError("duration must be a positive multiple of 15")
    return duration_min // SLOT_MIN


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def block_interval_on_day(block: TimeBlock, day: int) -> tuple[int, int] | None:
    if day not in block.days or block.start is None:
        return None
    start = hhmm_to_minutes(block.start)
    end = start + block.duration_min
    return start, end
