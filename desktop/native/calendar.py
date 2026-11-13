"""Week-grid edits and Day/Month helpers for the native calendar. No Qt."""

from __future__ import annotations

import json
from datetime import date, datetime
from functools import cache
from uuid import uuid4

import flexweek_engine  # type: ignore[import-untyped]

from backend import clock as wall_clock

LOCKED_CATEGORIES = ("class", "exercise", "extra", "meals", "sleep", "free")
FLEX_CATEGORIES = ("assignments", "study")
WEEKDAYS = [0, 1, 2, 3, 4]
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_FULL = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
FIRST_MONTH = "2000-01"
LAST_MONTH = "2099-12"
# One family (decision 9 of 0.17), worked out from each hue by `family_colours` in tokens.py and held
# to it by test_tokens.py. In a light look `color` is the pale fill and `mark` the strong colour of
# outlines and edges; `dark` and `contrast` are (tone, mark) for the dark looks and High contrast, which
# sink the tone into their own card for a fill.
CATEGORIES = {
    "class": {
        "icon": "school",
        "label": "School",
        "hue": 250,
        "color": "#cfe8ff",
        "mark": "#398ad6",
        "dark": ("#59aaf8", "#59aaf8"),
        "contrast": ("#5ebdff", "#5ebdff"),
        "kind": "locked",
        "preset": {"start": "08:00", "end": "14:30", "days": WEEKDAYS},
    },
    "assignments": {
        "icon": "book-open",
        "label": "Homework",
        "hue": 25,
        "color": "#ffdad6",
        "mark": "#831a1d",
        "dark": ("#f07f77", "#a43b38"),
        "contrast": ("#ff8a82", "#c04442"),
        "kind": "flexible",
        "preset": {"duration_min": 60},
    },
    "study": {
        "icon": "pencil",
        "label": "Study",
        "hue": 320,
        "color": "#f2dbf8",
        "mark": "#ab68ba",
        "dark": ("#cb86db", "#cb86db"),
        "contrast": ("#e493f6", "#e493f6"),
        "kind": "flexible",
        "preset": {"duration_min": 60},
    },
    "exercise": {
        "icon": "target",
        "label": "Sports",
        "hue": 150,
        "color": "#d0eed5",
        "mark": "#399d57",
        "dark": ("#5bbd74", "#5bbd74"),
        "contrast": ("#5fd37f", "#5fd37f"),
        "kind": "locked",
        "preset": {"start": "15:30", "end": "17:00"},
    },
    "extra": {
        "icon": "sparkles",
        "label": "Activity",
        "hue": 200,
        "color": "#c3eef0",
        "mark": "#009ea7",
        "dark": ("#00bec7", "#00bec7"),
        "contrast": ("#00d4df", "#00d4df"),
        "kind": "locked",
        "preset": {"start": "17:00", "end": "18:00"},
    },
    "meals": {
        "icon": "clock",
        "label": "Meals",
        "hue": 70,
        "color": "#f9e0c5",
        "mark": "#bb7400",
        "dark": ("#dc932e", "#dc932e"),
        "contrast": ("#f7a224", "#f7a224"),
        "kind": "locked",
        "preset": {"start": "18:00", "end": "18:30"},
    },
    "sleep": {
        "icon": "moon",
        "label": "Sleep",
        "hue": 280,
        "color": "#c4c8e8",
        "mark": "#5656b0",
        "dark": ("#7174d1", "#7174d1"),
        "contrast": ("#8184f1", "#8184f1"),
        "kind": "locked",
        "preset": {"start": "22:00", "end": "23:00"},
    },
    "free": {
        "label": "Free",
        "hue": 250,
        "color": "#e0e5eb",
        "mark": "#82878c",
        "dark": ("#a0a5ab", "#a0a5ab"),
        "contrast": ("#b3b8be", "#b3b8be"),
        "kind": "locked",
        "preset": {"start": "19:00", "end": "20:00"},
    },
}


def category_title(category: str | None) -> str:
    return str(flexweek_engine.calendar_category_title(category))


def is_series(block: dict) -> bool:
    return bool(flexweek_engine.calendar_is_series(json.dumps(block)))


def iso_of(day: date | str | None) -> str:
    return wall_clock.today().isoformat() if day is None else day if isinstance(day, str) else day.isoformat()


# The app's one short and one long way to write a date, made by the engine (datetext.rs). `today`
# decides whether the year shows; leave it out for the machine's own date.
def day_short(day: date | str, today: date | str | None = None) -> str:
    """Thu 1 Oct, or Fri 8 Jan 2027 outside this year."""
    return str(flexweek_engine.date_day_short(iso_of(day), iso_of(today)))


def day_long(day: date | str, today: date | str | None = None) -> str:
    """Thursday 1 October, or Friday 8 January 2027 outside this year."""
    return str(flexweek_engine.date_day_long(iso_of(day), iso_of(today)))


def week_range(start: date | str, today: date | str | None = None) -> str:
    """The week from `start`: 28 Sep – 4 Oct, 28 Dec – 3 Jan 2027 across New Year."""
    return str(flexweek_engine.date_week_range(iso_of(start), iso_of(today)))


def month_title(day: date | str, short: bool = False) -> str:
    """October 2026, or Oct 2026 where space is short."""
    return str(flexweek_engine.date_month_title(iso_of(day), short))


def monday_of(iso_day: str) -> str:
    return str(flexweek_engine.calendar_monday_of(iso_day))


def week_start_on(iso_day: str, first_weekday: int) -> str:
    """The first date of the shown week holding `iso_day` (0 Monday to 6 Sunday as its first day)."""
    return str(flexweek_engine.calendar_week_start_on(iso_day, first_weekday))


def day_in_week(iso_day: str, week_start: str) -> int:
    """How many days `iso_day` comes after `week_start`: 0 on it, negative before it."""
    return int(flexweek_engine.calendar_due_day(json.dumps(iso_day), week_start))


def stored_weeks_of(week_start: str) -> list[str]:
    """The stored (Monday) weeks the week on screen from `week_start` covers, first first."""
    return list(flexweek_engine.shown_week_stores(week_start))


def blocks_by_weekday(week_start: str, blocks: list[dict]) -> list[dict]:
    """The week's blocks with their days as weekdays (0 Monday), as a routine keeps them."""
    turned: list[dict] = json.loads(
        flexweek_engine.shown_week_blocks_by_weekday(week_start, json.dumps(blocks))
    )
    return turned


def routine_on_week(week_start: str, routine: dict) -> dict:
    """A routine with its days as days of the week from `week_start`, to copy into that week."""
    turned: dict = json.loads(flexweek_engine.shown_week_routine(week_start, json.dumps(routine)))
    return turned


def weekdays_on_week(week_start: str, weekdays: list[int]) -> list[int]:
    """Weekdays (0 Monday) as days of the week from `week_start`, in order."""
    return list(flexweek_engine.shown_week_weekdays(week_start, weekdays))


def windows_on_week(week_start: str, windows: list[dict]) -> list[dict]:
    """Work windows kept by weekday, with their days as days of the week from `week_start`."""
    moved: list[dict] = json.loads(flexweek_engine.shown_week_windows(week_start, json.dumps(windows)))
    return moved


def week_columns(week_start: str, weekends: bool) -> list[int]:
    """The days of the week on screen that get a column: all seven, or all but Saturday and Sunday."""
    return list(flexweek_engine.shown_week_columns(week_start, weekends))


@cache
def day_names(week_start: str) -> tuple[str, ...]:
    """Each day of the week on screen named from its date ("Wed" first for a week from Wednesday)."""
    return tuple(flexweek_engine.shown_week_day_names(week_start, False))


@cache
def day_full_names(week_start: str) -> tuple[str, ...]:
    """`day_names` written out: "Wednesday"."""
    return tuple(flexweek_engine.shown_week_day_names(week_start, True))


def weekday_order(first_weekday: int) -> list[int]:
    """The weekdays (0 Monday to 6 Sunday) in the order a week starting on `first_weekday` runs."""
    return list(flexweek_engine.calendar_weekday_order(first_weekday))


def month_rows(first: date, last: date, first_weekday: int) -> tuple[date, date]:
    """The first and last dates of a month's whole rows when they start on `first_weekday`."""
    start, end = flexweek_engine.month_grid(first, last, first_weekday)
    return start, end


def date_for_day(week_start: str, day: int) -> str:
    return str(flexweek_engine.calendar_date_for_day(week_start, json.dumps(day)))


def sunday_due(week_start: str) -> str:
    return str(flexweek_engine.calendar_sunday_due(week_start))


def local_stamp(now: datetime | None = None) -> str:
    moment = now or wall_clock.now()
    return str(flexweek_engine.calendar_local_stamp(moment.strftime("%Y-%m-%dT%H:%M")))


def occupied_intervals(blocks: list[dict], day: int) -> list[tuple[int, int]]:
    found = json.loads(flexweek_engine.calendar_occupied(json.dumps(blocks), json.dumps(day)))
    return [(begin, end) for begin, end in found]


def create_click_range(begin: int, occupied: list[tuple[int, int]]) -> tuple[int, int] | None:
    """Up to an hour from `begin`, which the hand has already put on its step, stopping where the next
    block starts."""
    span = flexweek_engine.calendar_click_range(begin, json.dumps(occupied))
    if span is None:
        return None
    start, stop = json.loads(span)
    return start, stop


def apply_block_times(block: dict, start_min: int, end_min: int, day: int | None = None) -> dict | None:
    """The block at a new time, and on `day` when it moved to another one."""
    raw = flexweek_engine.calendar_apply_times(json.dumps(block), start_min, end_min, day)
    return None if raw is None else json.loads(raw)


def hand_move(
    blocks: list[dict],
    assignments: dict[str, dict],
    block_id: str,
    clock: tuple[str, str, int, int],
    span: tuple[int, int, int, int],
) -> dict:
    """A block let go by hand, through the one rule the phone shares: `clock` is (week start, local
    date, local minute, the student's time step) and `span` is (day it was dragged from, day it lands
    on, start, end)."""
    return json.loads(
        flexweek_engine.calendar_hand_move(
            json.dumps(blocks), json.dumps(assignments), block_id, clock, span
        )
    )


def split_occurrence(blocks: list[dict], block_id: str, day: int) -> tuple[list[dict], str | None]:
    updated, new_id = flexweek_engine.calendar_split(
        json.dumps(blocks), json.dumps(block_id), json.dumps(day)
    )
    return json.loads(updated), new_id


def delete_occurrence(blocks: list[dict], block_id: str, day: int | None) -> list[dict]:
    return json.loads(
        flexweek_engine.calendar_delete(json.dumps(blocks), json.dumps(block_id), json.dumps(day))
    )


def apply_block_edit(
    blocks: list[dict], block: dict, *, scope: str = "series", day: int | None = None
) -> list[dict]:
    return json.loads(
        flexweek_engine.calendar_apply_edit(
            json.dumps(blocks), json.dumps(block), json.dumps(scope), json.dumps(day)
        )
    )


def relocate_block(
    source: list[dict],
    block_id: str,
    from_day: int,
    to_day: int,
    dest: list[dict] | None = None,
) -> tuple[list[dict], list[dict] | None, str] | None:
    """One day's copy of a block, moved onto `to_day`. `dest` is None when that day is in the same week."""
    moved = flexweek_engine.calendar_relocate(
        json.dumps(source),
        json.dumps(block_id),
        json.dumps(from_day),
        json.dumps(to_day),
        None if dest is None else json.dumps(dest),
    )
    if moved is None:
        return None
    source_out, dest_out, made = moved
    return json.loads(source_out), None if dest_out is None else json.loads(dest_out), json.loads(made)


def first_plannable_day(week_start: str, today: date | None = None) -> int:
    today = today or wall_clock.today()
    return int(flexweek_engine.calendar_first_day(week_start, today.isoformat()))


def due_day_in_week(due: str | None, week_start: str) -> int | None:
    return flexweek_engine.calendar_due_day(json.dumps(due), week_start)


def days_through(due_day: int | None, first_day: int = 0) -> list[int]:
    return flexweek_engine.calendar_days_through(due_day, first_day)


def month_for_view(iso_day: str) -> str:
    return str(flexweek_engine.calendar_month_for_view(iso_day))


def shifted_month(month: str, amount: int) -> str | None:
    return flexweek_engine.calendar_shifted_month(month, amount)


def month_anchor_date(selected_month: str, today: str) -> str:
    return str(flexweek_engine.calendar_month_anchor(selected_month, today))


def due_soon_for(iso_day: str, assignments: dict[str, dict]) -> list[dict]:
    return json.loads(flexweek_engine.calendar_due_soon(iso_day, json.dumps(assignments)))


# One sentinel, at module scope, because it is compared by identity. Built inside each function it
# would be a different object every call, so "is NOT_TODAY" was never true: the sentinel escaped into
# the agenda as a block's start time and the sort of those starts raised, which took the whole Day
# view down with it.
NOT_TODAY = object()


def placement_on(block: dict, day: int, trace: dict | None) -> str | None | object:
    """Where this block sits on this day: a time, None if it has none, or NOT_TODAY if it is not on
    this day at all."""
    found = json.loads(
        flexweek_engine.calendar_placement(
            json.dumps(block), json.dumps(day), None if trace is None else json.dumps(trace)
        )
    )
    return NOT_TODAY if found.get("not_today") else found["start"]


def agenda_for(
    week_start: str,
    iso_day: str,
    blocks: list[dict],
    assignments: dict[str, dict],
    trace: dict | None,
    day_data: dict | None,
) -> dict:
    return json.loads(
        flexweek_engine.calendar_agenda(
            week_start,
            iso_day,
            json.dumps(blocks),
            json.dumps(assignments),
            None if trace is None else json.dumps(trace),
            None if day_data is None else json.dumps(day_data),
        )
    )


def next_action_for(
    sessions: list[dict],
    due_soon: list[dict],
    assignments: dict[str, dict],
    day_data: dict | None,
) -> dict:
    return json.loads(
        flexweek_engine.calendar_next_action(
            json.dumps(sessions),
            json.dumps(due_soon),
            json.dumps(assignments),
            None if day_data is None else json.dumps(day_data),
        )
    )


# The blocks setup makes, found again by id when setup runs a second time. "sport" is the one the
# first-week card made before setup had pages.
SETUP_SCHOOL_ID = "school"
SETUP_ACTIVITY_PREFIX = "activity-"


def is_setup_block(block: dict) -> bool:
    return bool(flexweek_engine.calendar_setup_block(json.dumps(block)))


def block_family(block_id: str) -> str:
    """The block a piece split off at a week's seam belongs to: `school` for `school@20261111`."""
    return str(flexweek_engine.calendar_block_family(block_id))


def new_activity_id() -> str:
    """An id for an activity Setup adds. A new one never takes a number an earlier activity had, so
    removing or reordering activities leaves every other activity's id, and its weeks, as they were."""
    return f"{SETUP_ACTIVITY_PREFIX}{uuid4().hex[:8]}"


def repeat_changes(before: list[dict], after: list[dict], from_date: str) -> list[dict]:
    """The changes from the repeats standing in a week to the ones the session now holds, as the save
    sends them (`flexweek_engine::repeats`)."""
    made = flexweek_engine.repeat_intents_between(json.dumps(before), json.dumps(after), from_date)
    return json.loads(made)


def apply_repeat_changes(
    blocks: list[dict], repeats: list[dict], changes: list[dict], week_start: str
) -> tuple[list[dict], list[dict]]:
    """The open week from `week_start` and its repeats after `changes`, by the rule the store applies to
    saved weeks. Repeats keep their days by weekday; the week's count from its first day."""
    week, after = flexweek_engine.repeat_apply_to_week(
        json.dumps(blocks), json.dumps(repeats), json.dumps(changes), week_start
    )
    return json.loads(week), json.loads(after)


def this_week_line(blocks: list[dict], repeats: list[dict], clock_24h: bool, week_start: str) -> str | None:
    """'This week: no School on Wednesday.' for a form that shows the repeats, or None. `blocks` is the
    week from `week_start`."""
    return flexweek_engine.repeat_this_week_line(
        json.dumps(blocks), json.dumps(repeats), clock_24h, week_start
    )


def one_day_note(block: dict, day: int, school_hours: bool, week_start: str) -> str | None:
    """What moving day `day` of the week from `week_start` of a repeating block adds to its notice; None
    for a block that does not repeat."""
    return flexweek_engine.repeat_one_day_note(json.dumps(block), day, school_hours, week_start)


def past_problem(
    kind: str, week_start: str, day: int, start_min: int, now_iso: str, now_min: int, step_min: int
) -> str | None:
    """Why this start is already over, or None. `kind` is the block's own ("locked" for a fixed time,
    which may start in the past); `now_iso` and `now_min` are the local date and minute; `step_min` is
    the student's time step, which the words use to name the next time offered."""
    return flexweek_engine.calendar_past_problem(
        kind, week_start, day, start_min, now_iso, now_min, step_min
    )


def span_problem(
    blocks: list[dict],
    block_id: str,
    day: int,
    start_min: int,
    end_min: int,
    due: tuple[int, int] | None,
) -> str | None:
    """Why a block cannot go at this time, in words, or None. Landing on another block is allowed, as
    in Daily Scheduler: the two sit side by side. What cannot stand is time FlexWeek does not plan in,
    and homework that would end after it is due."""
    return flexweek_engine.calendar_span_problem(day, start_min, end_min, json.dumps(due), type(due).__name__)


def span_clash(blocks: list[dict], block_id: str, day: int, start_min: int, end_min: int) -> str | None:
    """The name of a block this time would sit beside, for the words that go with a drop."""
    return flexweek_engine.calendar_span_clash(
        json.dumps(blocks), json.dumps(block_id), json.dumps(day), start_min, end_min
    )


def category_icon(category: str | None) -> str | None:
    return flexweek_engine.calendar_category_icon(category)
