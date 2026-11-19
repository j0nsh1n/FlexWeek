"""Screens for the classic hours: the looks the hand, chips, column and grid-keyboard tests used to
check in code (heights, widths, clipping, text fit, the focus ring)."""

from __future__ import annotations

from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

HOURS = "desktop/native/hours"
WEDNESDAY = 2
SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "days": [0, 1, 2, 3, 4],
    "start": "08:00",
    "duration_min": 405,
}
GYM = {
    "id": "gym",
    "title": "Gym",
    "kind": "locked",
    "category": "exercise",
    "days": [5],
    "start": "10:00",
    "duration_min": 90,
}
SOCCER = {
    "id": "soccer",
    "title": "Soccer practice",
    "kind": "locked",
    "category": "extra",
    "days": [5],
    "start": "16:00",
    "duration_min": 90,
}
CLUB = {
    "id": "club",
    "title": "Club",
    "kind": "locked",
    "category": "extra",
    "days": [3],
    "start": "19:00",
    "duration_min": 60,
}
PIANO = {
    "id": "piano",
    "title": "Piano",
    "kind": "locked",
    "category": "extra",
    "days": [WEDNESDAY],
    "start": "15:00",
    "duration_min": 60,
}


def _settled(window: NativeWindow) -> None:
    wait_until(None, lambda: not window.session.busy and not window.session.dirty)




def _homework(window: NativeWindow, title: str, start: str | None = None, day: int = 3) -> None:
    """One homework item of 45 minutes; given a start, it is put on `day` at that time."""
    session = window.session
    session.add_homework(
        {
            "id": "work",
            "title": title,
            "due": sunday_due(session.week_start),
            "estimate_min": 45,
            "revision": 0,
        }
    )
    session.save()
    _settled(window)
    if start is not None:
        block = next(block for block in session.blocks if block.get("assignment_id") == "work")
        session.add_block({**block, "start": start, "days": [day], "pinned": True})
        session.save()
        _settled(window)






















SCREENS: list[Screen] = [
]
