"""Another week's blocks come from that week, the open week's from memory, and a failed load is
said instead of being shown as an empty week."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.client import ApiError
from desktop.native.controller import NativeSession
from desktop.tests.logic_support import fail_once, fixed, week_after
from desktop.tests.planner.session_without_a_window import settled, sign_up  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# The fixtures are used by name, so each test's argument list redefines them.
# ruff: noqa: F811


def saved_soccer(qapp: QApplication, sign_up: Callable[[str], NativeSession], clock: FakeClock, name: str):
    session = sign_up(name)
    clock.set(datetime.fromisoformat(session.week_start).replace(hour=9))
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled(qapp, session)
    return session


def watch_weeks(session: NativeSession) -> list[str]:
    gets: list[str] = []
    real = session.client.request

    def request(
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        if method == "GET" and path.startswith("/api/week?"):
            gets.append(path)
        real(method, path, payload, on_success, on_error)

    session.client.request = request  # type: ignore[method-assign, assignment]
    return gets


def test_week_blocks_uses_this_week_without_a_request(
    qapp: QApplication, sign_up: Callable[[str], NativeSession], clock: FakeClock
) -> None:
    session = saved_soccer(qapp, sign_up, clock, "week_here")
    gets = watch_weeks(session)
    got: list[list[dict]] = []
    session.week_blocks(session.week_start, got.append)
    assert len(got) == 1
    assert any(block["id"] == "soccer" for block in got[0])
    assert gets == []


def test_week_blocks_loads_another_week(
    qapp: QApplication, sign_up: Callable[[str], NativeSession], clock: FakeClock
) -> None:
    session = saved_soccer(qapp, sign_up, clock, "week_there")
    gets = watch_weeks(session)
    dest = week_after(session.week_start)
    got: list[list[dict]] = []
    session.week_blocks(dest, got.append)
    wait_until(qapp, lambda: len(got) == 1)
    settled(qapp, session)
    assert gets == [f"/api/week?week_start={dest}"]
    assert all(block["id"] != "soccer" for block in got[0])


def test_a_failed_week_load_is_said_and_not_applied(
    qapp: QApplication, sign_up: Callable[[str], NativeSession]
) -> None:
    session = sign_up("week_down")
    dest = week_after(session.week_start)
    fail_once(session, "GET", "/api/week")
    got: list[list[dict]] = []
    session.week_blocks(dest, got.append)
    wait_until(
        qapp,
        lambda: session.message == "Storage is unavailable. Keep your changes and try again shortly.",
    )
    assert got == []
