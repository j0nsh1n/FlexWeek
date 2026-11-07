"""The state the overdue card needs: one homework left overdue on a Saturday morning, the planning panel
folded away. The overdue card test and the overdue card pictures share it."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from datetime import date, datetime, timedelta

from backend.tests.fake_clock import CLOCK
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.window import NativeWindow
from desktop.tests.blocks_helper import put_block
from desktop.tests.waiting import wait_until

DESIGNS = ("classic", "timeline", "mission", "bento", "retro", "clay")
LONG_WORDS = "1 overdue · 3 left from last week"


def saved(window: NativeWindow) -> None:
    wait_until(None, lambda: not window.session.busy and not window.session.dirty)


def show_overdue_card(window: NativeWindow, main: str) -> None:
    """Bio reading planned for Wednesday afternoon, now Saturday 10:00: it is overdue and the card shows
    on the week page drawn by the `main` design."""
    session = window.session
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "bio",
            "title": "Bio reading",
            "due": (monday + timedelta(days=4)).isoformat() + "T23:59",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    saved(window)
    block = next(b for b in session.blocks if b.get("assignment_id") == "bio")
    # Plant, do not hand-move: the shared rule refuses a Wednesday start once that day is over.
    put_block(session, block["id"], 2, 15 * 60 + 15, 16 * 60 + 15, pinned=True)
    session.save()
    saved(window)
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(days=5, hours=10))
    session.week_changed.emit()
    saved(window)
    window._layout = sanitize_layout({"main": main, "day": "one", "options": {}})
    window._apply_appearance()
    window._on_week()
    window.show()
    window.unfinished_panel._collapse()
    saved(window)
    wait_until(None, lambda: window.left_chip.isVisible(), what="the overdue card showing")
