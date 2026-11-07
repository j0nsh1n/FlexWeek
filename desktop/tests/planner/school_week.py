"""The school week the missed-day, running-late and no-time tests plan in: the light app opened on Monday
28 September 2026 at midnight, with school Monday to Friday until 15:15 and two assignments due Monday
and Tuesday evening, so the plan sits on Monday afternoon."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until

PLANNED_WEEK = "2026-09-28"
MONDAY_MORNING = datetime(2026, 9, 28, 0, 0)


def open_the_school_week(open_light: Callable[..., NativeWindow], clock: FakeClock) -> NativeSession:
    clock.set(MONDAY_MORNING)
    session = open_light().session
    assert session.week_start == PLANNED_WEEK
    return session


def plan_the_school_week(qapp: QApplication, session: NativeSession) -> None:
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "duration_min": 435,
            "days": [0, 1, 2, 3, 4],
            "start": "08:00",
            "category": "class",
        }
    )
    for item_id, title, minutes, due in (
        ("math", "Math worksheet", 30, "2026-09-28T21:00"),
        ("english", "English essay", 90, "2026-09-29T21:00"),
    ):
        session.add_homework(
            {"id": item_id, "title": title, "estimate_min": minutes, "due": due, "revision": 0}
        )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    session.solve()
    wait_until(qapp, lambda: not session.busy and not session.dirty)


def stored(session: NativeSession, block_id: str) -> dict:
    return next(block for block in session.blocks if block["id"] == block_id)


def placement(session: NativeSession, block_id: str) -> tuple[list[int], str | None]:
    block = stored(session, block_id)
    return block["days"], block.get("start")
