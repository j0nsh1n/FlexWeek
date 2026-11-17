"""Homework added today is this week's whatever day the week starts on: it is not "left from last
week" and Plan my homework does not ask "Before planning" about it. A session that passed unfinished
before the week on screen still is left from last week, even when the stored (Monday) week it is in
also holds the first days of the week on screen. The clock is Thursday 19 November 2026, 3:40 PM, or
Monday 23 November: with the week starting on Friday the week on screen runs Friday 13 to Thursday
19, and its first three days are stored in Monday 9's week, which starts before it."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from backend.tests.fake_clock import FakeClock
from desktop.native import window as window_module
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.e2e.saved_weeks import read_week
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.logic_support import settled
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

THURSDAY = datetime(2026, 11, 19, 15, 40)
MONDAY = datetime(2026, 11, 23, 15, 40)
# Tuesday (1) to Sunday (6): every first day but Monday.
FIRST_DAYS = {"Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}


def stored_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def opened(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    clock: FakeClock,
    now: datetime,
    first_weekday: int,
) -> tuple[NativeWindow, date]:
    """The window on the week from `first_weekday` that holds `now`, and that week's first day."""
    clock.set(now)
    window = open_light()
    session = window.session
    session.follow_first_weekday(first_weekday)
    first = now.date() - timedelta(days=(now.date().weekday() - first_weekday) % 7)
    wait_until(qapp, lambda: session.week_start == first.isoformat() and not session.busy, what="the week")
    settled(qapp, session)
    return window, first


def saved(qapp: QApplication, session: NativeSession) -> None:
    session.save()
    wait_until(qapp, lambda: not session.busy and session.pending_save is None and not session.dirty)
    settled(qapp, session)


def asked_before_planning(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The questions Plan asks before planning, each answered Not now."""
    asked: list[str] = []

    class Sheet:
        answer = "not"

        def __init__(self, _parent, title, question, *_args, **_kwargs) -> None:  # type: ignore[no-untyped-def]
            asked.append(f"{title}: {question}")

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(window_module, "ConfirmSheet", Sheet)
    return asked


def press_plan(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    window.findChild(QPushButton, "solveButton").click()
    wait_until(
        qapp,
        lambda: (
            not session.busy and not session.planning and session.pending_save is None and not session.dirty
        ),
        what="the plan saved",
    )
    settled(qapp, session)


@pytest.mark.parametrize("first_weekday", FIRST_DAYS.values(), ids=FIRST_DAYS.keys())
@pytest.mark.parametrize("now", [THURSDAY, MONDAY], ids=["thursday-19", "monday-23"])
def test_homework_added_today_is_not_left_over_and_plan_gives_it_a_time(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
    first_weekday: int,
) -> None:
    window, first = opened(qapp, open_light, clock, now, first_weekday)
    session = window.session
    asked = asked_before_planning(monkeypatch)
    today = now.date()
    session.add_homework(
        {
            "id": "poster",
            "title": "Science poster",
            "due": f"{today.isoformat()}T21:00",
            "estimate_min": 60,
            "revision": 0,
        }  # fmt: skip
    )
    saved(qapp, session)
    # Saved once, in a stored week, on days of the week on screen.
    homes = []
    for monday in sorted({stored_monday(first), stored_monday(first + timedelta(days=6))}):
        for block in read_week(qapp, session, monday.isoformat())["blocks"]:
            if block.get("assignment_id") == "poster":
                homes.append({monday + timedelta(days=day) for day in block["days"]})
    assert len(homes) == 1, homes
    assert homes[0] & {first + timedelta(days=day) for day in range(7)}, (first, homes)
    assert session.unfinished() == []
    press_plan(qapp, window)
    assert asked == []
    (poster,) = [block for block in session.blocks if block.get("assignment_id") == "poster"]
    assert poster.get("start") and poster["duration_min"] == 60, (poster, session.message)


@pytest.mark.parametrize("first_weekday", FIRST_DAYS.values(), ids=FIRST_DAYS.keys())
def test_a_session_passed_unfinished_the_day_before_the_week_on_screen_is_left_from_last_week(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    first_weekday: int,
) -> None:
    window, first = opened(qapp, open_light, clock, THURSDAY, first_weekday)
    session = window.session
    asked = asked_before_planning(monkeypatch)
    last = first + timedelta(days=6)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": f"{last.isoformat()}T21:00",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    saved(qapp, session)
    # The essay's one session was at 4 PM the day before the week on screen and was not done. That day is
    # in the stored week that also holds the week's first days. The new account has nothing else of its
    # own saved in either stored week (School stands in them from setup and is kept apart).
    before = first - timedelta(days=1)
    monday = stored_monday(before)
    passed = {"id": "essay-1", "title": "Essay", "kind": "flexible", "assignment_id": "essay",
              "duration_min": 60, "start": "16:00", "days": [before.weekday()]}  # fmt: skip
    weeks = [
        {
            "week_start": week_start.isoformat(),
            "blocks": [passed] if week_start == monday else [],
            "revision": read_week(qapp, session, week_start.isoformat())["revision"],
        }
        for week_start in sorted({monday, stored_monday(last)})
    ]
    got: dict = {}
    session.client.request(
        "POST",
        "/api/changes",
        {"weeks": weeks, "repeats": []},
        lambda data: got.setdefault("ok", data),
        lambda error: got.setdefault("err", error),
    )
    wait_until(qapp, lambda: bool(got))
    assert "ok" in got, got.get("err")
    session.reload()
    settled(qapp, session)
    assert [(item["id"], item["left_over_state"]) for item in session.unfinished()] == [
        ("essay", "left_from_last_week")
    ]
    window.findChild(QPushButton, "solveButton").click()
    assert asked == ["Before planning: 1 left from last week"]
