"""Stage 4 occupancy, lateness and project-spread planning. No HTTP, no database."""

from __future__ import annotations

from datetime import date, timedelta

from backend.assignments import unplanned_minutes
from backend.models import GridWindow, ProtectedWindow, parse_naive_stamp
from backend.slots import DAY_END_MIN, DAY_START_MIN, SLOT_MIN, SLOTS_PER_DAY, occupancy_mask
from backend.weeks import monday_of

LATE_COPY = "Moved after you ran late so the rest of the day still fits."
CLUSTER_COPY = (
    "Several tasks are short on time. Shorten a session, pick another day, "
    "or free some protected hours. Work that cannot fit stays unplaced."
)


def add_occupancy(occ: list[int], day: int, start_min: int, end_min: int) -> None:
    if start_min < DAY_START_MIN:
        start_min = DAY_START_MIN
    if end_min > DAY_END_MIN:
        end_min = DAY_END_MIN
    if start_min >= end_min or start_min >= DAY_END_MIN:
        return
    offset = start_min - DAY_START_MIN
    slot = offset // SLOT_MIN
    n = min(max(0, (end_min - DAY_START_MIN) // SLOT_MIN - slot), SLOTS_PER_DAY - slot)
    if n:
        occ[day] |= occupancy_mask(slot, n)


def occupancy_from_windows(
    protected: list[ProtectedWindow] | list[GridWindow],
    day_cutoff: str | None,
) -> list[int]:
    occ = [0] * 7
    for window in protected:
        hour, minute = map(int, window.start.split(":"))
        start = hour * 60 + minute
        for day in window.days:
            add_occupancy(occ, day, start, start + window.duration_min)
    if day_cutoff:
        hour, minute = map(int, day_cutoff.split(":"))
        cutoff = hour * 60 + minute
        for day in range(7):
            add_occupancy(occ, day, cutoff, DAY_END_MIN)
    return occ


def lateness_occupancy(day: int, from_start: str, minutes: int) -> list[int]:
    occ = [0] * 7
    hour, minute = map(int, from_start.split(":"))
    start = hour * 60 + minute
    add_occupancy(occ, day, start, start + minutes)
    return occ


def study_prefers(windows: list[GridWindow], day: int, start_min: int, duration_min: int) -> bool:
    for window in windows:
        if day not in window.days:
            continue
        hour, minute = map(int, window.start.split(":"))
        begin = hour * 60 + minute
        # The whole session must fit inside the window, not just its start.
        if begin <= start_min and start_min + duration_min <= begin + window.duration_min:
            return True
    return False


def merge_occupancy(base: list[int], extra: list[int]) -> list[int]:
    return [left | right for left, right in zip(base, extra, strict=True)]


def spread_sessions(
    *,
    estimate_min: int,
    focus_minutes: int,
    planned_min: int,
    due: str,
    session_min: int,
    from_date: str,
) -> tuple[list[dict[str, object]], int]:
    remaining = unplanned_minutes(estimate_min, focus_minutes, planned_min)
    # Sessions stay on the grid; the sub-15-minute remainder is unschedulable,
    # not zero, and comes back in remaining_min instead of being dropped.
    remainder = remaining % SLOT_MIN
    grid_total = remaining - remainder
    due_day, _ = parse_naive_stamp(due)
    start = date.fromisoformat(from_date)
    if remaining == 0 or start > due_day:
        return [], remaining
    dates: list[date] = []
    cursor = start
    while cursor <= due_day:
        dates.append(cursor)
        cursor += timedelta(days=1)
    sizes: list[int] = []
    left = grid_total
    while left >= session_min:
        sizes.append(session_min)
        left -= session_min
    if left:
        sizes.append(left)
    sessions: list[dict[str, object]] = []
    for index, duration in enumerate(sizes):
        day = dates[index % len(dates)]
        sessions.append(
            {
                "week_start": monday_of(day.isoformat()),
                "date": day.isoformat(),
                "days": [day.weekday()],
                "duration_min": duration,
            }
        )
    return sessions, remainder
