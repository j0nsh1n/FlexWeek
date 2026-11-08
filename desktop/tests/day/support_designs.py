"""Putting a light window on one of the layout designs (Bento, Mission control) with a week to look at,
for the screens the pictures photograph. It only prepares the state; what is right on the picture is
the reviewer's call."""

from __future__ import annotations

from datetime import datetime

from backend.tests.fake_clock import CLOCK
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until

# The test week of the clock (Monday 2 November 2026): the clock starts on its Thursday evening.
THURSDAY = "2026-11-05"
FRIDAY = "2026-11-06"


def at(hour: int, minute: int = 0, day: int = 5) -> None:
    """Move the clock to a time on the test week: Thursday (day 5 of November) unless told."""
    CLOCK.set(datetime(2026, 11, day, hour, minute))


def locked(block_id: str, title: str, category: str, start: str, minutes: int, days: list[int]) -> dict:
    return {"id": block_id, "title": title, "kind": "locked", "category": category, "start": start,
            "duration_min": minutes, "days": days}


def seed_week(window: NativeWindow, *, shared: bool = True, extra: tuple[dict, ...] = ()) -> None:
    """A school week: School and Dinner, homework due this week (one session placed, the rest waiting),
    and, when `shared`, two blocks that share a quarter hour on Monday. `extra` adds more blocks."""
    session = window.session
    blocks = [
        {"id": "school", "title": "School", "kind": "locked", "category": "class", "start": "08:00",
         "duration_min": 390, "days": [0, 1, 2, 3, 4]},
        {"id": "dinner", "title": "Dinner", "kind": "locked", "category": "meals", "start": "18:00",
         "duration_min": 30, "days": [0, 1, 2, 3, 4, 5, 6]},
    ]
    if shared:
        blocks += [
            {"id": "club", "title": "Robotics club", "kind": "locked", "category": "extra",
             "start": "15:15", "duration_min": 45, "days": [0]},
            {"id": "maths", "title": "Maths", "kind": "locked", "category": "class",
             "start": "15:45", "duration_min": 45, "days": [0]},
        ]
    blocks += extra
    for block in blocks:
        session.add_block(block)
    for key, title, due, minutes in (
        ("chem", "Chem lab report", "2026-11-05T23:59", 90),
        ("essay", "History essay", "2026-11-06T21:00", 60),
        ("poster", "Science fair poster", "2026-11-08T20:00", 120),
    ):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": minutes, "revision": 0})
    for block in session.blocks:
        if block.get("assignment_id") == "essay":
            session.add_block({**block, "days": [3], "start": "18:45"})
    session.save()
    wait_until(None, lambda: not session.busy and not session.dirty)


def show_design(
    window: NativeWindow,
    design: str,
    *,
    surface: str = "week",
    iso_day: str = THURSDAY,
    **options: str,
) -> object:
    """Open `design` (with the given options, such as look="midnight") on the week, the day `iso_day`
    or the month, and return the design's view."""
    window._layout = sanitize_layout({"main": design, "day": "one", "options": {design: options}})
    window._apply_appearance()
    session = window.session
    if surface == "day":
        session.open_day(iso_day)
        wait_until(None, lambda: not session.busy and session.day_data is not None)
    elif surface == "month":
        session.open_month()
        wait_until(None, lambda: not session.busy and session.month_data is not None)
    window._on_week()
    wait_until(None, lambda: not session.busy)
    return window._views[design]
