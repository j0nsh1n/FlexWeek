"""Reading a week back from the real local server, for the tests that move blocks between weeks."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.controller import NativeSession
from desktop.tests.logic_support import settled


def read_week(qapp: QApplication, session: NativeSession, week_start: str) -> dict:
    """The week as the server stores it, not as the session holds it."""
    got: dict = {}

    def ok(data: dict) -> None:
        got["week"] = data

    def err(error: object) -> None:
        got["error"] = error

    session.client.request("GET", f"/api/week?week_start={week_start}", None, ok, err)
    settled(qapp, session)
    assert "week" in got, got.get("error")
    return got["week"]


def hold_the_clock_at_the_start_of_the_open_week(session: NativeSession) -> None:
    """Moving a block to a date refuses a start before now. A test about moving holds the clock at
    the start of the open week so every day of that week, and the weeks after, are ahead of it."""
    CLOCK.set(datetime.fromisoformat(session.week_start))
