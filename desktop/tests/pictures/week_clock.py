"""Screens for the hour words, the time-now pill, a block's time range and the week list: the looks
the clock-gutter, block-range and week-list tests used to check in code."""

from __future__ import annotations

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:30",
    "duration_min": 405,
    "days": [0, 1, 2, 3, 4],
}


def _saved(window: NativeWindow) -> None:
    session = window.session
    wait_until(None, lambda: not session.busy and not session.dirty)


def _add(window: NativeWindow, *blocks: dict) -> None:
    for block in blocks:
        window.session.add_block(dict(block))
    _saved(window)














SCREENS: list[Screen] = [
]
