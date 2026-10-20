"""The session's hand move runs the one Rust rule, with the values of the rule's own tests
(engine/engine/tests/hand_move.rs): homework the student moves is pinned where they put it, a
fixed block is not, a start that has passed is refused in the calendar's words, and a finished
timed block still moves."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from desktop.server import LocalServer
from desktop.tests.logic_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_in,
)

MONDAY, TUESDAY, THURSDAY = 0, 1, 3
AFTERNOON = 14 * 60 + 30
HOMEWORK_MIN = 90


def held_session(qapp, server: LocalServer) -> object:
    """Signed in with the clock at Monday 08:00 of the open week, as the rule's tests start."""
    session = signed_in(qapp, server.origin, "handmove", create=True)
    monday_8 = datetime.fromisoformat(session.week_start) + timedelta(hours=8)
    session.now_ms = lambda: int(monday_8.timestamp() * 1000)
    return session


def placed_homework(qapp, session) -> dict:
    """The rule's Algebra set 4: one session on Monday 14:30, 90 minutes, due Friday."""
    due = (datetime.fromisoformat(session.week_start).date() + timedelta(days=4)).isoformat() + "T23:59"
    session.add_homework(
        {"id": "algebra-4", "title": "Algebra set 4", "due": due, "estimate_min": HOMEWORK_MIN, "revision": 0}
    )
    session.save()
    settled(qapp, session)
    block = next(item for item in session.blocks if item.get("assignment_id") == "algebra-4")
    session.add_block({**block, "start": "14:30", "days": [MONDAY]})
    return next(item for item in session.blocks if item["id"] == block["id"])


def test_homework_moved_by_hand_is_pinned(qapp, server) -> None:
    session = held_session(qapp, server)
    block = placed_homework(qapp, session)
    assert session.hand_move(block["id"], MONDAY, TUESDAY, AFTERNOON, AFTERNOON + HOMEWORK_MIN) is True
    moved = next(item for item in session.blocks if item["id"] == block["id"])
    assert (moved["days"], moved["start"], moved["duration_min"], moved["pinned"]) == (
        [TUESDAY], "14:30", HOMEWORK_MIN, True,
    )


def test_a_fixed_block_moved_by_hand_is_not_pinned(qapp, server) -> None:
    session = held_session(qapp, server)
    session.add_block(
        {"id": "soccer", "title": "Soccer", "kind": "locked", "days": [MONDAY],
         "start": "17:00", "duration_min": 60}
    )
    assert session.hand_move("soccer", MONDAY, THURSDAY, 17 * 60, 18 * 60) is True
    moved = next(item for item in session.blocks if item["id"] == "soccer")
    assert moved["days"] == [THURSDAY]
    assert moved.get("pinned") is not True


def test_a_past_start_is_refused_in_the_calendar_s_words(qapp, server) -> None:
    session = held_session(qapp, server)
    session.add_block(
        {"id": "school", "title": "School", "kind": "locked", "days": [2],
         "start": "08:00", "duration_min": 390}
    )
    wednesday_noon = datetime.fromisoformat(session.week_start) + timedelta(days=2, hours=12)
    session.now_ms = lambda: int(wednesday_noon.timestamp() * 1000)
    assert session.hand_move("school", 2, 2, 8 * 60 + 30, 15 * 60) is False
    assert session.message == "That time has passed. Choose 12:00 or later today, or another day."


def test_a_finished_timed_block_still_moves(qapp, server) -> None:
    session = held_session(qapp, server)
    block = placed_homework(qapp, session)
    session.blocks = [
        {**item, "completed": True} if item["id"] == block["id"] else item for item in session.blocks
    ]
    assert session.hand_move(block["id"], MONDAY, TUESDAY, AFTERNOON, AFTERNOON + HOMEWORK_MIN) is True
    moved = next(item for item in session.blocks if item["id"] == block["id"])
    assert moved["days"] == [TUESDAY]
    assert moved.get("pinned") is not True
