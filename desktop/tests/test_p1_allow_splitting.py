"""P1: "Allow splitting" on an In one go homework that does not fit spreads its whole estimate over sessions,
every minute with a time (moved out of Regression Tester's file, which only loses its xfail marks)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.tests.logic_support import qapp, server, settled, wait_until  # noqa: F401
from desktop.tests.regress190.test_regress_qa0190_p1_split import hold, homework, student


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
