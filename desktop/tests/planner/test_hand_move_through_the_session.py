"""What the session decides around the one Rust rule for a block moved by hand (the rule's own values
are tested in engine/engine/tests/hand_move.rs): it reads the clock the app reads, applies the answer
to the week, and says the calendar's words when it refuses."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.weekmodel import set_clock_24h
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp, settled  # noqa: F401

MONDAY, TUESDAY = 0, 1
AFTERNOON = 14 * 60 + 30
HOMEWORK_MIN = 90


def at(window: NativeWindow, clock: FakeClock, day: int, hour: int) -> None:
    """The clock on `day` of the open week at `hour`:00."""
    clock.set(datetime.fromisoformat(window.session.week_start) + timedelta(days=day, hours=hour))


def placed_homework(qapp: QApplication, window: NativeWindow) -> dict:
    """Algebra set 4: one session on Monday 14:30, 90 minutes, due Friday."""
    session = window.session
    due = (datetime.fromisoformat(session.week_start).date() + timedelta(days=4)).isoformat() + "T23:59"
    session.add_homework(
        {"id": "algebra-4", "title": "Algebra set 4", "due": due, "estimate_min": HOMEWORK_MIN, "revision": 0}
    )
    session.save()
    settled(qapp, window)
    block = next(item for item in session.blocks if item.get("assignment_id") == "algebra-4")
    session.add_block({**block, "start": "14:30", "days": [MONDAY]})
    return next(item for item in session.blocks if item["id"] == block["id"])


def test_homework_moved_by_hand_lands_on_the_new_day_and_stays_there(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    session = window.session
    at(window, clock, MONDAY, 8)
    block = placed_homework(qapp, window)
    assert session.hand_move(block["id"], MONDAY, TUESDAY, AFTERNOON, AFTERNOON + HOMEWORK_MIN) is True
    moved = next(item for item in session.blocks if item["id"] == block["id"])
    assert (moved["days"], moved["start"], moved["duration_min"], moved["pinned"]) == (
        [TUESDAY], "14:30", HOMEWORK_MIN, True,
    )
    assert session.dirty


def test_a_fixed_time_may_be_moved_to_an_earlier_time_today(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    session = window.session
    session.add_block(
        {"id": "school", "title": "School", "kind": "locked", "days": [2],
         "start": "08:00", "duration_min": 390}
    )
    at(window, clock, 2, 12)
    assert session.hand_move("school", 2, 2, 7 * 60, 13 * 60 + 30) is True
    school = next(item for item in session.blocks if item["id"] == "school")
    assert (school["days"], school["start"]) == ([2], "07:00")


def test_a_fixed_time_may_be_moved_to_an_earlier_day(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    session = window.session
    session.add_block(
        {"id": "club", "title": "Club", "kind": "locked", "days": [2],
         "start": "16:00", "duration_min": 60}
    )
    at(window, clock, 2, 12)
    assert session.hand_move("club", 2, TUESDAY, 16 * 60, 17 * 60) is True
    club = next(item for item in session.blocks if item["id"] == "club")
    assert club["days"] == [TUESDAY]


def test_homework_start_that_has_passed_is_refused_in_the_calendars_words_and_nothing_moves(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    session = window.session
    at(window, clock, MONDAY, 8)
    block = placed_homework(qapp, window)
    at(window, clock, 2, 12)
    # A new account reads the 12-hour clock; the words are checked in the 24-hour one.
    set_clock_24h(True)
    assert session.hand_move(block["id"], MONDAY, 2, 11 * 60, 12 * 60 + HOMEWORK_MIN) is False
    assert session.message == "That time has passed. Choose 12:00 or later today, or another day."
    held = next(item for item in session.blocks if item["id"] == block["id"])
    assert (held["days"], held["start"]) == ([MONDAY], "14:30")
