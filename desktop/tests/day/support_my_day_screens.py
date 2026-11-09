"""Putting a light window on My day's two screens, One thing and Day dial, for the pictures of them
(desktop/tests/pictures/_day_g02.py and _myday_g02.py). It seeds the week through the session, moves the
one clock, picks the day screen and its options, and opens My day. It asserts nothing."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta

from PySide6.QtWidgets import QAbstractButton

from backend.tests.fake_clock import CLOCK, START_MONDAY
from desktop.native.calendar import sunday_due
from desktop.native.layouts.base import LayoutView
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still

THURSDAY = 3
# What the pictures of these screens are drawn from, for the renderer to know when a change touches them.
DIAL_SOURCES = (
    "desktop/native/layouts/dial.py",
    "desktop/native/layouts/base.py",
    "desktop/native/hours",
    "desktop/native/weekmodel.py",
    "desktop/native/look.py",
)
ONE_THING_SOURCES = (
    "desktop/native/layouts/one_thing.py",
    "desktop/native/layouts/base.py",
    "desktop/native/ring.py",
    "desktop/native/hours",
    "desktop/native/weekmodel.py",
    "desktop/native/look.py",
)
# My day's two screens do not change with the main design, so they are drawn once, in Today's app.
STYLES = ("classic",)

Block = dict[str, object]


def set_time(clock_text: str, day: int = THURSDAY, week: int = 0) -> None:
    """Put the one clock at `clock_text` ("15:40") on `day` of the test week (or `week` weeks on)."""
    hours, minutes = (int(part) for part in clock_text.split(":"))
    moment = START_MONDAY + timedelta(days=day + 7 * week)
    CLOCK.set(datetime.combine(moment, time(hours, minutes)))


def locked(
    block_id: str, title: str, days: list[int], start: str, minutes: int, category: str = "class"
) -> Block:
    return {
        "id": block_id,
        "title": title,
        "kind": "locked",
        "category": category,
        "start": start,
        "duration_min": minutes,
        "days": days,
    }


def homework(
    ident: str, title: str, minutes: int, start: str | None = None, day: int = THURSDAY
) -> dict[str, object]:
    """Homework due on Sunday; with `start` its one session is placed on `day` at that time."""
    return {"id": ident, "title": title, "minutes": minutes, "start": start, "day": day}


def settle_saving(window: NativeWindow) -> None:
    session = window.session
    wait_until(
        None,
        lambda: not session.busy and not session.dirty and not getattr(session.client, "pending", 0),
        what="the window to finish saving",
    )


def seed_week(window: NativeWindow, fixed: list[Block], work: list[dict[str, object]]) -> None:
    """Add the fixed blocks and the homework to the window's week, then place each homework's session."""
    session = window.session
    for item in fixed:
        session.add_block(item)
    for item in work:
        session.add_homework(
            {
                "id": item["id"],
                "title": item["title"],
                "due": sunday_due(session.week_start),
                "estimate_min": item["minutes"],
                "revision": 0,
            }
        )
    session.save()
    settle_saving(window)
    for item in work:
        if item["start"] is None:
            continue
        found = next(block for block in session.blocks if block.get("assignment_id") == item["id"])
        session.add_block({**found, "start": item["start"], "days": [item["day"]]})
    session.save()
    settle_saving(window)


def prefer(window: NativeWindow, **values: object) -> None:
    """Change preferences the way Settings does (accent colour, 12-hour clock) and apply them."""
    window.session.preferences = {**(window.session.preferences or {}), **values}
    window._sync_chrome()


def open_my_day(
    window: NativeWindow, layout_id: str, options: dict[str, str] | None = None
) -> LayoutView:
    """My day on `layout_id` ("one" or "dial") with the given options, still, and the view returned."""
    layout = window._layout
    window._layout = sanitize_layout(
        {
            "main": layout["main"],
            "day": layout_id,
            "options": {**layout["options"], layout_id: options or {}},
        }
    )
    window.findChild(QAbstractButton, "viewMyDay").click()

    def open_now() -> bool:
        shown = window.planner.currentWidget()
        return isinstance(shown, LayoutView) and shown.layout_id == layout_id

    wait_until(None, open_now, what="My day to open on the chosen screen")
    window._refresh_layout()
    still(window)
    view = window.planner.currentWidget()
    assert isinstance(view, LayoutView)
    return view


def prepare_day(
    layout_id: str,
    clock_text: str,
    fixed: list[Block],
    work: list[dict[str, object]],
    options: dict[str, str] | None = None,
    prefs: dict[str, object] | None = None,
    weeks_on: int = 0,
) -> Callable[[NativeWindow], object]:
    """A `prepare` for a Screen: the week as given, the clock at `clock_text`, then My day opened.
    `weeks_on` moves the clock whole weeks past the window's week, so the screen has no today."""

    def prepare(window: NativeWindow) -> object:
        # Seeded before dawn on Monday, when nothing in the week is past.
        set_time("06:00", day=0)
        seed_week(window, fixed, work)
        if prefs:
            prefer(window, **prefs)
        set_time(clock_text, week=weeks_on)
        return open_my_day(window, layout_id, options)

    return prepare
