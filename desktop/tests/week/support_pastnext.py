"""Setup shared by the Week tests about past times, last week's leftovers, the empty week, the rail
and Running late: small copies of what the old files took from other test modules."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QAbstractButton, QApplication

from backend.slots import minutes_to_hhmm
from backend.tests.fake_clock import CLOCK
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import settled

MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = range(7)


def classic_week(qapp: QApplication, window: NativeWindow) -> NativeWindow:
    """The light window on the classic Week at the size a laptop shows."""
    window.resize(1280, 860)
    window._layout = {"main": "classic", "day": "one", "options": {}}
    window.findChild(QAbstractButton, "viewWeek").click()
    settled(qapp, window)
    wait_until(qapp, window.isVisible)
    return window


def hold_clock(window: NativeWindow, day: int, minute: int) -> None:
    """The one clock at `minute` of the day on `day` of the open week, and the hours redrawn."""
    CLOCK.set(datetime.fromisoformat(window.session.week_start) + timedelta(days=day, minutes=minute))
    window._fill_classic()
    QApplication.processEvents()


def settled_session(qapp: QApplication, session: NativeSession) -> None:
    """The foreground request and the background refreshes it starts are done."""
    wait_until(qapp, lambda: not session.busy)
    wait_until(qapp, lambda: not any(session.client._replies.values()))


def put_block(
    session: NativeSession,
    block_id: str,
    day: int,
    start_min: int,
    end_min: int | None = None,
    *,
    pinned: bool | None = None,
) -> None:
    """Plant a block at a time without the hand-move rule, which refuses a past start."""
    block = next(item for item in session.blocks if item["id"] == block_id)
    block["start"] = minutes_to_hhmm(start_min)
    block["days"] = [day]
    if end_min is not None:
        block["duration_min"] = end_min - start_min
    if pinned is not None:
        block["pinned"] = pinned
    session.needs_time.pop(block_id, None)
