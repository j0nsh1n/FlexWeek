"""Plan my homework and Replan all give each homework the time it needs, once, whatever day the week
starts on. The clock is Thursday 19 November 2026, 3:40 PM. With the week starting on Wednesday the
week on screen runs Wednesday 18 to Tuesday 24 November: its first five days are stored in Monday 16's
week, where the homework's waiting sessions live, and Plan once took that stored week for an earlier
one and gave each homework its hour twice."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

import pytest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.e2e.saved_weeks import read_week
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.logic_support import settled
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

THURSDAY = datetime(2026, 11, 19, 15, 40)
TODAY = THURSDAY.date()
HOMEWORK = {"poster": "Science poster", "worksheet": "Math worksheet"}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def stored_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def sessions_of(blocks: list[dict]) -> dict[str, list[int]]:
    """Each homework's sessions by length, waiting or placed, not counting ones ticked done."""
    held: dict[str, list[int]] = {key: [] for key in HOMEWORK}
    for block in blocks:
        if block.get("assignment_id") in held and not block.get("completed"):
            held[block["assignment_id"]].append(block["duration_min"])
    return held


def planned(qapp: QApplication, session: NativeSession) -> None:
    wait_until(
        qapp,
        lambda: (
            not session.busy and not session.planning and session.pending_save is None and not session.dirty
        ),
        what="the plan saved",
    )
    settled(qapp, session)


@pytest.mark.parametrize("first_weekday", range(7), ids=WEEKDAYS)
@pytest.mark.parametrize("today", [TODAY, TODAY + timedelta(days=4)], ids=["thursday-19", "monday-23"])
def test_plan_and_replan_all_keep_each_homeworks_length(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    clock: FakeClock,
    first_weekday: int,
    today: date,
) -> None:
    clock.set(datetime.combine(today, THURSDAY.time()))
    session = open_light().session
    session.follow_first_weekday(first_weekday)
    first = today - timedelta(days=(today.weekday() - first_weekday) % 7)
    wait_until(qapp, lambda: session.week_start == first.isoformat() and not session.busy, what="the week")
    settled(qapp, session)
    last = first + timedelta(days=6)
    for key, title in HOMEWORK.items():
        session.add_homework(
            {"id": key, "title": title, "due": f"{last.isoformat()}T21:00", "estimate_min": 60, "revision": 0}
        )
    session.save()
    planned(qapp, session)
    assert sessions_of(session.blocks) == {key: [60] for key in HOMEWORK}
    stored = sorted({stored_monday(first), stored_monday(last)})
    # What Plan my homework and Replan all my homework do when no homework is left from an earlier week.
    for everything in (False, True):
        session.solve(everything=everything)
        planned(qapp, session)
        assert sessions_of(session.blocks) == {key: [60] for key in HOMEWORK}, (everything, session.message)
        assert all(
            block.get("start") for block in session.blocks if block.get("assignment_id") in HOMEWORK
        ), (everything, session.blocks)
        saved: dict[str, list[int]] = {key: [] for key in HOMEWORK}
        for monday in stored:
            for key, lengths in sessions_of(read_week(qapp, session, monday.isoformat())["blocks"]).items():
                saved[key] += lengths
        assert saved == {key: [60] for key in HOMEWORK}, (everything, saved)
