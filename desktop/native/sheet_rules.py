"""Rules and wording the block, homework and running-late sheets share."""

from __future__ import annotations

import json
import re
from datetime import date
from uuid import uuid4

import flexweek_engine  # type: ignore[import-untyped]

from backend.slots import (
    DAY_END_MIN,
    SLOT_MIN,
    hhmm_to_minutes,
)
from desktop.native.calendar import (
    CATEGORIES,
    DAY_FULL,
    DAYS,
    date_for_day,
    day_full_names,
    day_in_week,
    day_long,
    day_names,
    weekdays_on_week,
)
from desktop.native.hours.geometry import next_slot
from desktop.native.weekmodel import (
    clock_text,
    due_label,
    hhmm_text,
    range_label,
)

# Meals first: 18:00–19:30 sits inside the afternoon activity window.
_MEAL_WINDOWS = ((7 * 60, 8 * 60), (12 * 60, 13 * 60), (18 * 60, 19 * 60 + 30))
_SCHOOL_START = hhmm_to_minutes(CATEGORIES["class"]["preset"]["start"])
_SCHOOL_END = hhmm_to_minutes(CATEGORIES["class"]["preset"]["end"])


def guess_locked_category(start: str) -> str:
    """A category for a new fixed time, from when it starts, until the student picks one."""
    minute = hhmm_to_minutes(start)
    for low, high in _MEAL_WINDOWS:
        if low <= minute < high:
            return "meals"
    if _SCHOOL_START <= minute < _SCHOOL_END:
        return "class"
    return "extra"


def short_day_name(week_start: str, day: int) -> str:
    """Day `day` of the week from `week_start` named from its date ("Wed"); Monday first with no week."""
    return (day_names(week_start) if week_start else DAYS)[day]


def same_weekday(day: int, from_week: str, to_week: str) -> int:
    """Day `day` of the week from `from_week` as the day of the week from `to_week` with its weekday: the
    same date when that week holds it."""
    if not from_week or not to_week or from_week == to_week:
        return day
    return day_in_week(date_for_day(from_week, day), to_week) % 7


def full_day_name(week_start: str, day: int) -> str:
    """`short_day_name` written out: "Wednesday"."""
    return (day_full_names(week_start) if week_start else DAY_FULL)[day]


def turn_days_keeping_weekdays(
    days: list[int] | tuple[int, ...], from_week: str, to_week: str
) -> tuple[list[int], list[tuple[int, int]]]:
    """Day numbers turned to the week now open, with the ones whose date changed as (old, new)
    pairs. Nothing turns between two weeks from the same first day, or with no week on either
    side: then nothing could have moved."""
    if not from_week or not to_week or from_week == to_week:
        return sorted(days), []
    turned = [(day, same_weekday(day, from_week, to_week)) for day in days]
    # Another week from the same first day (Next, Previous) keeps every day's place: nothing moved.
    if date.fromisoformat(from_week).weekday() == date.fromisoformat(to_week).weekday():
        return sorted(new for _, new in turned), []
    moved = [(old, new) for old, new in turned if date_for_day(from_week, old) != date_for_day(to_week, new)]
    return sorted(new for _, new in turned), moved


def first_day_changed(from_week: str, to_week: str) -> bool:
    """Whether the two weeks start on different days of the week."""
    return (
        bool(from_week)
        and bool(to_week)
        and date.fromisoformat(from_week).weekday() != date.fromisoformat(to_week).weekday()
    )


def moved_day_names(old_day: int, from_week: str, new_day: int, to_week: str) -> tuple[str, str]:
    """A moved tick's old and new names the way the note names them: "Monday 2" and "Monday 9". A pair
    whose two dates fall in different months names both with their month ("Monday 30 November",
    "Monday 7 December")."""
    old_date = date_for_day(from_week, old_day)
    new_date = date_for_day(to_week, new_day)
    if old_date[:7] == new_date[:7]:
        return (
            f"{full_day_name(from_week, old_day)} {int(old_date[8:])}",
            f"{full_day_name(to_week, new_day)} {int(new_date[8:])}",
        )
    # The engine's own long date is English whatever the computer's language; its year shows only
    # outside the reference year, so each date is its own reference.
    return day_long(old_date, old_date), day_long(new_date, new_date)


def moved_across_months(old_day: int, from_week: str, new_day: int, to_week: str) -> bool:
    """Whether a moved tick's old and new dates are in different months."""
    return date_for_day(from_week, old_day)[:7] != date_for_day(to_week, new_day)[:7]


def moved_days_note(moves: list[tuple[str, str]]) -> str:
    """Old/new "Monday 2" label pairs as the one line under the row: "Monday 2 isn't in this week
    any more, so it moved to Monday 9." Empty with no moves."""
    if not moves:
        return ""
    olds = [old for old, _ in moves]
    news = [new for _, new in moves]
    if len(moves) == 1:
        return f"{olds[0]} isn't in this week any more, so it moved to {news[0]}."
    old_words = ", ".join(olds[:-1]) + f" and {olds[-1]}"
    new_words = ", ".join(news[:-1]) + f" and {news[-1]}"
    return f"{old_words} aren't in this week any more, so they moved to {new_words}."


def day_range_words(days: list[int] | tuple[int, ...], week_start: str = "") -> str:
    """Three or more days in a row as a range ("Mon–Fri"); otherwise a list ("Mon, Wed, Fri"). With
    `week_start`, days of that week named from their dates: the week may start on any day."""
    if not days:
        return ""
    names = day_names(week_start) if week_start else DAYS
    ordered = sorted(set(days))
    runs: list[list[int]] = [[ordered[0]]]
    for day in ordered[1:]:
        if day == runs[-1][-1] + 1:
            runs[-1].append(day)
        else:
            runs.append([day])
    parts: list[str] = []
    for run in runs:
        if len(run) >= 3:
            parts.append(f"{names[run[0]]}–{names[run[-1]]}")
        else:
            parts.extend(names[day] for day in run)
    return ", ".join(parts)


def day_range_and_words(days: list[int] | tuple[int, ...], week_start: str = "") -> str:
    words = day_range_words(days, week_start)
    if ", " not in words:
        return words
    head, last = words.rsplit(", ", 1)
    return f"{head} and {last}"


SPREAD_NOTHING = "Nothing left to spread: all of this homework is already done or has focus time recorded."

# No-break space before the last word, so a narrow sheet never leaves "45." alone on a line.
SLOT_HINT = "Use a multiple of 15 minutes, such as 15, 30, or\u00a045."

DUE_PASSED = "That due time has passed. Choose a later one."
ESTIMATE_ERROR = "That time isn't a multiple of 15 minutes."
ESTIMATE_SHORT = "Give it at least 15 minutes."
ESTIMATE_LONG = "That's more than 24 hours. Split it into parts and add each part as its own homework."
HOMEWORK_PROBLEMS = {
    "due": "Choose a valid due date.",
    "course": "Keep the course name under 40 characters.",
    "spotify_url": "Paste a Spotify share link from open.spotify.com.",
    "notes": "Keep notes under 4,000 characters.",
    "priority": "Choose a type from the list.",
    "energy": "Choose a time of day from the list.",
    "completed_at": "Set a valid time for finished homework.",
}
HOMEWORK_REFUSED = "Check the homework details and try again."

REPEAT_NOTE = "Pick every day it happens."

LATE_WAIT = "Press Preview first to see what moves."

# What the block editor says when the server's rules refuse a block, by the field they name. Their own
# words ("Value error, spotify_url must be ...") are for a developer, not a student.
BLOCK_PROBLEMS = {
    "title": "Give it a title.",
    "days": "Tick at least one day.",
    "spotify_url": "That's not a Spotify share link. Paste one that starts with https://open.spotify.com, "
    "or leave it empty.",
}
BLOCK_REFUSED = "FlexWeek can't keep this block as it is. Check its title, days and times."


def block_sheet_problem(block: dict) -> tuple[str, str] | None:
    """First failing field and student-facing sentence for a block sheet, or None when valid."""
    return flexweek_engine.block_sheet_problem(json.dumps(block))


def homework_sheet_problem(homework: dict) -> tuple[str, str] | None:
    """First failing field and student-facing sentence for a homework sheet, or None when valid."""
    return flexweek_engine.homework_sheet_problem(json.dumps(homework))


def _preset_locked(
    category: str | None, day: int, start: str, duration_min: int, week_start: str = ""
) -> dict:
    """A new fixed time with its category's preset. A preset's days are weekdays (0 Monday), so in
    the week from `week_start` they become that week's days."""
    info = CATEGORIES.get(category or "")
    days = [day]
    title = ""
    chosen_start = start
    chosen_duration = duration_min
    if info is not None:
        title = info["label"]
        preset = info["preset"]
        if duration_min == 60 and start == "16:00" and "start" in preset:
            chosen_start = preset["start"]
            chosen_duration = hhmm_to_minutes(preset["end"]) - hhmm_to_minutes(preset["start"])
            days = list(preset.get("days") or [day])
            if week_start and preset.get("days"):
                days = weekdays_on_week(week_start, days)
        elif "start" not in preset:
            chosen_duration = preset.get("duration_min", duration_min)
    return {
        "id": str(uuid4()),
        "kind": "locked",
        "title": title,
        "days": days,
        "start": chosen_start,
        "duration_min": chosen_duration,
        "category": category,
    }


def spread_words(sessions: list[dict], due: str, today: date) -> str:
    """What spreading will do, for the grey line under the choice: "2 × 60 min on different days before
    it is due Sun 4 Oct."."""
    if not sessions:
        return SPREAD_NOTHING
    sizes = [int(item["duration_min"]) for item in sessions]
    full = sizes[0]
    whole = sizes.count(full)
    lead = f"{whole} × {full} min" if whole > 1 else f"{full} min"
    parts = lead if whole == len(sizes) else f"{lead} and {sizes[-1]} min"
    ahead = f"before it's due {due_label(due, today)}."
    if len(sizes) == 1:
        return f"{parts} in one session {ahead}"
    days = len({item["date"] for item in sessions})
    if days == len(sizes):
        return f"{parts} on different days {ahead}"
    return f"{parts} on the same day {ahead}" if days == 1 else f"{parts} over {days} days {ahead}"


def today_from_words(minute: int) -> str:
    """ "Today from 3:15 PM onward.": the next quarter hour from `minute`, rounded up the way the past-time
    sentence rounds it (no 6:00 AM floor), or nothing once the day has no quarter hour left."""
    ahead, slot = next_slot(minute, first=0, last=DAY_END_MIN - SLOT_MIN)
    if ahead:
        return ""
    return f"Today from {clock_text(slot)} onward."


# The evenings "No homework after" offers, in Setup and in Availability alike.
CUTOFFS = ("20:00", "20:30", "21:00", "21:30", "22:00", "22:30", "23:00")


def _unbroken_time(text: str) -> str:
    """Keep AM/PM on the same line as the time in Running late's preview. Only a time's own AM/PM:
    a title such as "PM review" keeps its plain space."""
    return re.sub(r"(?<=\d) ([AP]M)\b", "\u00a0\\1", text)


def _late_summary(moved: int) -> str:
    if not moved:
        return "Nothing needs to move."
    return f"{moved} task{'s' if moved != 1 else ''} {'moves' if moved == 1 else 'move'}"


def _late_move(move: dict, block: dict, title: str, week_start: str = "") -> str:
    was, now = move.get("from_start"), move.get("to_start")
    duration = int(block.get("duration_min") or 0)
    old_day, new_day = move.get("from_day"), move.get("to_day")
    if was and now and old_day is not None and new_day is not None:
        old = range_label(hhmm_to_minutes(was), hhmm_to_minutes(was) + duration)
        new = range_label(hhmm_to_minutes(now), hhmm_to_minutes(now) + duration)
        was_day, new_name = short_day_name(week_start, old_day), short_day_name(week_start, new_day)
        return _unbroken_time(f"{title}: {was_day} {old} → {new_name} {new}")
    if now and was:
        return _unbroken_time(f"{title}: from {hhmm_text(was)} to {hhmm_text(now)}")
    if now and new_day is not None:
        return _unbroken_time(f"{title}, placed {short_day_name(week_start, new_day)} {hhmm_text(now)}")
    if now:
        return _unbroken_time(f"{title}: placed at {hhmm_text(now)}")
    if was:
        return _unbroken_time(f"{title}: moves off {hhmm_text(was)} and isn't placed")
    return f"{title}: not placed"
