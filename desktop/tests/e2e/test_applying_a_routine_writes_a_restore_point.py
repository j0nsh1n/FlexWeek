"""Applying a saved routine to the next week adds its blocks there and leaves a restore point named for it."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.logic_support import week_after
from desktop.tests.planner.planning_week import session_in_the_planned_week, soccer
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_applying_a_routine_writes_a_restore_point(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.save_routine("Sports week")
    wait_until(qapp, lambda: not session.busy and session.routines)
    nxt = week_after(session.week_start)
    routine_id = next(iter(session.routines))
    assert session.apply_routine(routine_id, nxt, [0, 1, 2, 3, 4, 5, 6])
    wait_until(qapp, lambda: session.week_start == nxt and not session.busy)
    assert any(block["title"] == "Soccer" for block in session.blocks)
    points: list[dict] = []

    def ok(data: dict) -> None:
        points.extend(data.get("restore_points") or [])

    session.client.request("GET", "/api/restore-points", None, ok, lambda _error: None)
    wait_until(qapp, lambda: bool(points))
    assert any("Sports week" in (point.get("label") or "") for point in points)
