"""Regression for QA's L12 (fix-specs-0190.md): Running late moves a running block to noon or another day.

Session level, the held "now" handed to preview_running_late (as the window does). Monday of the real
current week, 17:00; "Late test" homework placed 16:45-17:45 that day, the rest of Monday empty (noon free).
Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from desktop.tests.logic_support import qapp, server, settled, signed_in, wait_until  # noqa: F401
from desktop.tests.regress190.test_regress_qa0190_p1_split import homework

KNOWN = (
    "known failure (L12): late_from_start ignores the running block and the solve has no now floor, so the "
    "running block moves to the earliest free gap (noon, or another day)"
)
KNOWN_WORDS = "known failure (L12.3): the preview says '1 tasks move · 0 tasks no longer fit'"


def late(qapp, server, name: str, minutes: int, pinned: bool = False) -> tuple[dict, dict, list[str]]:
    session = signed_in(qapp, server.origin, name, create=True)  # no homework hours: any time of day
    wait_until(qapp, lambda: session.preferences is not None)
    monday_5pm = datetime.fromisoformat(session.week_start) + timedelta(hours=17)
    session.now_ms = lambda: int(monday_5pm.timestamp() * 1000)
    homework(qapp, session, [("late", 60, 3)])
    block = next(b for b in session.blocks if b.get("assignment_id") == "late")
    assert session.hand_move(block["id"], -1, 0, 16 * 60 + 45, 17 * 60 + 45)
    # As Plan would have left it: placed, not pinned by hand (a pinned block is never moved).
    if not pinned:
        session.blocks = [{**b, "pinned": False} if b["id"] == block["id"] else b for b in session.blocks]
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled(qapp, session)
    said: list[str] = []
    session.status.connect(said.append)
    session.preview_running_late(minutes, monday_5pm)
    wait_until(qapp, lambda: session.late_preview is not None and not session.busy, timeout=15)
    trace = session.late_preview["trace"]
    placed = next(p for p in trace.get("placed") or [] if p["id"] == block["id"])
    return block, placed, said


@pytest.mark.parametrize("minutes", [15, 30, 60])
def test_l12_the_running_block_shifts_by_the_delay_and_keeps_its_length(qapp, server, minutes) -> None:
    _block, placed, _said = late(qapp, server, f"l12_{minutes}", minutes)
    start = 16 * 60 + 45 + minutes
    wanted = ([0], f"{start // 60:02d}:{start % 60:02d}", 60)
    assert (placed.get("days"), placed.get("start"), placed.get("duration_min")) == wanted, placed


def test_l12_nothing_lands_before_now(qapp, server) -> None:
    _block, placed, _said = late(qapp, server, "l12_floor", 30)
    day = (placed.get("days") or [None])[0]
    hh, mm = map(int, placed["start"].split(":"))
    assert day == 0 and hh * 60 + mm >= 17 * 60, placed


def test_l12_the_preview_says_1_task_moves(qapp, server) -> None:
    _block, _placed, said = late(qapp, server, "l12_words", 30)
    assert said[-1].startswith("1 task moves"), said


KNOWN_PINNED = (
    "known failure (L12, pinned variant): a pinned running block is not moved at all, so it overlaps the "
    "late block (preview: '0 tasks move')"
)


def test_l12_a_pinned_running_block_also_shifts_by_the_delay(qapp, server) -> None:
    """Rule 1 names no exception for a block the student placed by hand; left where it is, it overlaps
    the 17:00-17:30 late block."""
    _block, placed, said = late(qapp, server, "l12_pinned", 30, pinned=True)
    assert (placed.get("days"), placed.get("start")) == ([0], "17:15"), (placed.get("start"), said)
