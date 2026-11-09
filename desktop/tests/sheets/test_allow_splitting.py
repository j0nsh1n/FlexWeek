"""Allow splitting on an In one go homework that does not fit spreads its whole estimate over sessions,
every minute with a time."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.sheets.support_homework_week import settled
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

WEEKDAYS = {"days": [0, 1, 2, 3, 4], "start": "19:00", "end": "21:00"}
MONDAY_16_30 = datetime(2026, 11, 2, 16, 30)


def test_allow_splitting_replaces_one_unplaced_session_with_the_full_estimate(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
) -> None:
    CLOCK.set(MONDAY_16_30)
    window = open_light()
    session = window.session
    assert session.save_availability([], None, [WEEKDAYS])
    settled(qapp, window)
    session.selected_day = session.today_iso()
    monday = date.fromisoformat(session.week_start)
    # 180 minutes in evenings that hold two hours each, so it cannot be placed whole.
    session.add_homework(
        {
            "id": "lab",
            "title": "Lab",
            "estimate_min": 180,
            "revision": 0,
            "due": (monday + timedelta(days=9)).isoformat() + "T23:59",
        }
    )
    session.save()
    settled(qapp, window)
    assert session.allow_splitting("lab")

    def pieces() -> list[dict]:
        return [block for block in session.blocks if block.get("assignment_id") == "lab"]

    def split_complete() -> bool:
        return (
            not session.busy
            and not session.dirty
            and len(pieces()) == 3
            and all(block.get("start") for block in pieces())
        )

    wait_until(
        qapp,
        split_complete,
        timeout=20,
        what=lambda: f"{session.message!r}, pieces {pieces()}, needs time {session.needs_time}",
    )
    settled(qapp, window)
    assert len(pieces()) == 3, pieces()
    assert all(block.get("start") for block in pieces()), pieces()
    assert sum(block.get("duration_min") or 0 for block in pieces()) == 180, pieces()
