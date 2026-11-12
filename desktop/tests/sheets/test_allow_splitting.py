"""Allow splitting on an In one go homework that does not fit spreads its whole estimate over sessions,
every minute with a time."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
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


def test_allow_splitting_places_every_session_when_the_read_lands_before_plan(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
) -> None:
    """The same lab, with the Plan that Allow splitting starts held until the server's numbers for the three
    new sessions have been read (planned 180). The lab is due 9 days out, so a fair share would give it
    180 x 5 / 8 = 112.5, a quarter hour up 120, this week (Mon to Fri of the 8 study days to the Wednesday
    after next) and keep 60 back. The sessions Allow splitting makes get no fair share: all three, 180 in
    all, get a time this week, whichever comes first, the read or the Plan."""
    CLOCK.set(MONDAY_16_30)
    window = open_light()
    session = window.session
    assert session.save_availability([], None, [WEEKDAYS])
    settled(qapp, window)
    session.selected_day = session.today_iso()
    monday = date.fromisoformat(session.week_start)
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
    real_solve = session.solve
    planned_when_plan_ran: list[object] = []

    def solve_after_the_read(**kwargs) -> None:
        if not kwargs.get("join"):
            real_solve(**kwargs)
            return
        if session.assignments["lab"].get("planned_min") != 180:
            QTimer.singleShot(10, lambda: solve_after_the_read(**kwargs))
            return
        planned_when_plan_ran.append(session.assignments["lab"].get("planned_min"))
        real_solve(**kwargs)

    session.solve = solve_after_the_read  # type: ignore[method-assign]
    assert session.allow_splitting("lab")

    def pieces() -> list[dict]:
        return [block for block in session.blocks if block.get("assignment_id") == "lab"]

    wait_until(
        qapp,
        lambda: bool(planned_when_plan_ran)
        and not session.busy
        and not session.dirty
        and len(pieces()) == 3
        and all(block.get("start") for block in pieces()),
        timeout=20,
        what=lambda: f"{session.message!r}, plan saw {planned_when_plan_ran}, pieces {pieces()}",
    )
    settled(qapp, window)
    assert planned_when_plan_ran == [180]
    assert sum(block["duration_min"] for block in pieces()) == 180, pieces()


def test_a_later_replan_all_gives_the_split_homework_its_fair_share(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
) -> None:
    """Only the Plan that Allow splitting starts skips the fair share. After it placed all three sessions,
    Replan all plans them again under the usual rule: 180 x 5 / 8 = 112.5, a quarter hour up 120 this week
    (two of the 60 minute sessions), and the other 60 waits with no time."""
    CLOCK.set(MONDAY_16_30)
    window = open_light()
    session = window.session
    assert session.save_availability([], None, [WEEKDAYS])
    settled(qapp, window)
    session.selected_day = session.today_iso()
    monday = date.fromisoformat(session.week_start)
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

    wait_until(
        qapp,
        lambda: not session.busy
        and not session.dirty
        and len(pieces()) == 3
        and all(block.get("start") for block in pieces()),
        timeout=20,
        what=lambda: f"{session.message!r}, pieces {pieces()}",
    )
    settled(qapp, window)
    session.solve(everything=True)
    wait_until(
        qapp,
        lambda: not session.planning and not session.busy and not session.dirty,
        timeout=20,
        what="Replan all finished",
    )
    settled(qapp, window)
    placed = sorted(block["duration_min"] for block in pieces() if block.get("start"))
    waiting = sorted(block["duration_min"] for block in pieces() if not block.get("start"))
    assert (placed, waiting) == ([60, 60], [60]), pieces()
