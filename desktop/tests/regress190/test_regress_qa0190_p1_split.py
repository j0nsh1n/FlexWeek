"""Regression for QA's P1 (fix-specs-0190.md): Plan's fair share cuts a homework's stored length and the
remainder exists nowhere (Fresh Eyes F1/F2/F4, Assistant Local L4, Timmy's rules a-d).

Session level (NativeSession over a LocalServer), with a held clock (`session.now_ms`), as in Coder's
probe. The week is the real current week; the clock is put on its Saturday or Monday. Rule: Plan never
makes a homework's time shorter than its estimate, and what is not placed this week is still there.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from desktop.tests.logic_support import qapp, server, settled, signed_in, wait_until  # noqa: F401

WEEKDAYS = {"days": [0, 1, 2, 3, 4], "start": "19:00", "end": "21:00"}
WEEKEND = {"days": [5, 6], "start": "10:00", "end": "12:00"}


def student(qapp, server, name: str, *, weekend: bool = False):
    session = signed_in(qapp, server.origin, name, create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    assert session.save_availability([], None, [WEEKDAYS, WEEKEND] if weekend else [WEEKDAYS])
    wait_until(qapp, lambda: not session.busy)
    return session


def hold(session, day: int, hour: int, minute: int) -> None:
    held = datetime.fromisoformat(session.week_start) + timedelta(days=day, hours=hour, minutes=minute)
    session.now_ms = lambda: int(held.timestamp() * 1000)


def homework(qapp, session, items: list[tuple[str, int, int]]) -> None:
    """(id, estimate, due day counted from this Monday)."""
    monday = date.fromisoformat(session.week_start)
    for ident, estimate, due in items:
        session.add_homework({"id": ident, "title": ident.title(), "estimate_min": estimate, "revision": 0,
                              "due": (monday + timedelta(days=due)).isoformat() + "T23:59"})
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled(qapp, session)


def plan(qapp, session) -> list[str]:
    said: list[str] = []
    session.status.connect(said.append)
    session.solve()
    wait_until(qapp, lambda: not session.planning and not session.busy and not session.dirty, timeout=20)
    settled(qapp, session)
    session.status.disconnect(said.append)
    return said


def minutes(session, ident: str, *, placed: bool = False) -> int:
    return sum(
        block.get("duration_min") or 0
        for block in session.blocks
        if block.get("assignment_id") == ident and (block.get("start") or not placed)
    )


def next_week(qapp, session) -> None:
    later = (date.fromisoformat(session.week_start) + timedelta(days=7)).isoformat()
    session.load_week(later)
    wait_until(qapp, lambda: not session.busy and session.week_start == later, timeout=10)
    settled(qapp, session)


FRESH_EYES = [("math", 45, 9), ("history", 120, 10), ("bio", 60, 11)]  # due next Wed, Thu, Fri


def test_p1_1_saturday_1345_without_weekend_hours_plan_cuts_nothing(qapp, server) -> None:
    session = student(qapp, server, "p1_sat_cut")
    hold(session, 5, 13, 45)
    homework(qapp, session, FRESH_EYES)
    plan(qapp, session)
    kept = {ident: minutes(session, ident) for ident, _e, _d in FRESH_EYES}
    assert kept == {ident: estimate for ident, estimate, _d in FRESH_EYES}


def test_p1_1_next_weeks_plan_places_all_three_whole_before_their_due_days(qapp, server) -> None:
    session = student(qapp, server, "p1_sat_next")
    hold(session, 5, 13, 45)
    homework(qapp, session, FRESH_EYES)
    plan(qapp, session)
    next_week(qapp, session)
    said = plan(qapp, session)
    assert "All your homework already has a time." not in said, said
    placed = {ident: minutes(session, ident, placed=True) for ident, _e, _d in FRESH_EYES}
    assert placed == {ident: estimate for ident, estimate, _d in FRESH_EYES}, placed


def test_p1_8_monday_1630_lab_report_180_due_next_wednesday_keeps_180(qapp, server) -> None:
    """Assistant Local's weekday repro: one 2 h 30 block on Friday, the 30 min gone."""
    session = student(qapp, server, "p1_mon_lab")
    hold(session, 0, 16, 30)
    homework(qapp, session, [("lab", 180, 9)])
    plan(qapp, session)
    seen = [(b.get("days"), b.get("start"), b.get("duration_min"))
            for b in session.blocks if b.get("assignment_id")]
    assert minutes(session, "lab") == 180, seen


def test_p1_auto_split_off_saturday_45_due_wednesday_stays_one_45_session(qapp, server) -> None:
    """Timmy's addition: rule a, work due within the coming week is never split."""
    session = student(qapp, server, "p1_sat_45")
    done: list = []
    session.save_preferences({"auto_split": False}, done.append)
    wait_until(qapp, lambda: bool(done) and not session.busy)
    hold(session, 5, 13, 45)
    homework(qapp, session, [("math", 45, 9)])
    plan(qapp, session)
    sessions = [b.get("duration_min") for b in session.blocks if b.get("assignment_id") == "math"]
    assert sessions == [45], sessions


def test_p1_guard_weekday_item_due_within_the_week_is_placed_whole(qapp, server) -> None:
    """Assistant Local: weekday items due within the week were placed whole. Keep it."""
    session = student(qapp, server, "p1_mon_whole")
    hold(session, 0, 16, 30)
    homework(qapp, session, [("essay", 90, 3)])
    plan(qapp, session)
    assert minutes(session, "essay", placed=True) == 90


def test_allow_splitting_replaces_one_unplaced_session_with_the_full_estimate(qapp, server) -> None:
    session = student(qapp, server, "p1_allow_split")
    hold(session, 0, 16, 30)
    session.selected_day = session.today_iso()
    homework(qapp, session, [("lab", 180, 9)])
    assert session.allow_splitting("lab")
    def split_complete() -> bool:
        pieces = [block for block in session.blocks if block.get("assignment_id") == "lab"]
        return (
            not session.busy
            and not session.dirty
            and len(pieces) == 3
            and all(block.get("start") for block in pieces)
        )

    wait_until(qapp, split_complete, timeout=20)
    assert split_complete(), {
        "message": session.message,
        "pieces": [block for block in session.blocks if block.get("assignment_id") == "lab"],
        "spread_preview": session.spread_preview,
        "assignments": session.assignments,
        "needs_time": session.needs_time,
    }
    settled(qapp, session)
    pieces = [block for block in session.blocks if block.get("assignment_id") == "lab"]
    assert len(pieces) == 3, pieces
    assert all(block.get("start") for block in pieces), pieces
    assert sum(block.get("duration_min") or 0 for block in pieces) == 180, pieces
