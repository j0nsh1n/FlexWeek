# ruff: noqa: F811
"""A homework session whose time has passed and that the student did not finish is not "handled".

The clock is Thursday 5 November 2026 at 19:00 (backend.tests.fake_clock), in the week of Monday
2 November. The essay was planned on Tuesday 3 November, 16:00 to 17:00, and nothing was done. Replan all
my homework gives it a new time ahead of now, or no time when none fits before it is due. Plan my homework
keeps the times already planned (spec.md). Nothing is ever placed before now, a pinned or finished session
is never touched, and what the status line says is true afterwards."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.controller import NativeSession
from desktop.native.weekmodel import homework_time_sentence
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import due_on
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

EVERYTHING = "Everything has a time."
THURSDAY_NOW = (3, "19:00")


def _settle(qapp: QApplication, session: NativeSession) -> None:
    wait_until(qapp, lambda: not session.busy and session.pending_save is None)
    qapp.processEvents()


def _essay_planned_on_tuesday(
    qapp: QApplication,
    open_light: Callable[..., NativeWindow],
    *,
    due: str | None = None,
    estimate: int = 60,
    **block: object,
) -> tuple[NativeSession, dict]:
    """The essay with one session, Tuesday 16:00 to 17:00, as it was saved on Monday."""
    session = open_light().session
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": due or due_on(session, 5, "23:59"),
            "estimate_min": estimate,
            "revision": 0,
        }
    )
    session.save()
    _settle(qapp, session)
    work = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    work.update({"start": "16:00", "days": [1], "duration_min": 60, **block})
    session.add_block(work)
    session.save()
    _settle(qapp, session)
    return session, next(item for item in session.blocks if item["id"] == work["id"])


def _block(session: NativeSession, block_id: str) -> dict:
    return next(item for item in session.blocks if item["id"] == block_id)


def _sentence(session: NativeSession) -> str:
    return homework_time_sentence(session.unfinished(), session.homework_time_needed())


def test_the_status_does_not_say_everything_has_a_time_for_a_missed_session(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    """Tuesday 16:00 to 17:00 ended 50 h before Thursday 19:00: the essay needs its 60 min planned again."""
    session, _ = _essay_planned_on_tuesday(qapp, open_light)
    assert [item["minutes"] for item in session.homework_time_needed()] == [60]
    assert _sentence(session) == "1 h still needs a time"


def test_replan_all_moves_the_missed_essay_to_a_time_ahead_by_the_planners_usual_rules(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    """The essay goes where the planner puts any session of the same length and deadline, and that is
    ahead of Thursday 19:00 (day 3, 19:00). The same essay with no time at all, planned by Plan, is the
    reference."""
    session, work = _essay_planned_on_tuesday(qapp, open_light)
    session.solve(everything=True)
    _settle(qapp, session)
    moved = _block(session, work["id"])
    spot = (moved["days"][0], moved["start"])
    assert spot >= THURSDAY_NOW, "never placed before now"
    assert moved["duration_min"] == 60
    assert not moved.get("pinned")
    assert session.homework_time_needed() == []
    assert _sentence(session) == EVERYTHING
    assert session.message == "Placed 1 homework block."
    fresh = {key: value for key, value in moved.items() if key != "start"}
    fresh["days"] = [0, 1, 2, 3, 4, 5]
    session.add_block(fresh)
    session.save()
    _settle(qapp, session)
    session.solve()
    _settle(qapp, session)
    again = _block(session, work["id"])
    assert (again["days"][0], again["start"]) == spot


def test_replan_all_leaves_the_essay_with_no_time_when_none_fits_before_it_is_due(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    """Due Thursday 19:30: only 30 min lie between now (19:00) and the deadline, for a 60 min session."""
    session, work = _essay_planned_on_tuesday(qapp, open_light, due="2026-11-05T19:30")
    session.solve(everything=True)
    _settle(qapp, session)
    left = _block(session, work["id"])
    assert not left.get("start"), "its Tuesday time is gone and it was not put in the past"
    assert left["duration_min"] == 60
    assert [item["minutes"] for item in session.homework_time_needed()] == [60]
    assert _sentence(session) == "1 h still needs a time"
    assert session.message == "Nothing placed. 1 with no time yet."


def test_plan_keeps_the_missed_time_and_says_the_time_is_needed(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    """spec.md: Plan places only homework that has no time yet and keeps the times already planned."""
    session, work = _essay_planned_on_tuesday(qapp, open_light)
    session.solve()
    _settle(qapp, session)
    kept = _block(session, work["id"])
    assert (kept["days"], kept["start"]) == ([1], "16:00")
    assert session.message == "1 h still needs a time"


def test_replan_all_never_touches_a_pinned_session_that_passed(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    session, work = _essay_planned_on_tuesday(qapp, open_light, pinned=True)
    session.solve(everything=True)
    _settle(qapp, session)
    kept = _block(session, work["id"])
    assert (kept["days"], kept["start"], kept.get("pinned")) == ([1], "16:00", True)
    assert session.homework_time_needed() == [], "the student chose that time, so it is not waiting"


def test_replan_all_never_touches_a_finished_session_in_the_past(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    session, work = _essay_planned_on_tuesday(qapp, open_light, completed=True, completed_day=1)
    session.solve(everything=True)
    _settle(qapp, session)
    kept = _block(session, work["id"])
    assert (kept["days"], kept["start"], kept["completed"]) == ([1], "16:00", True)
    assert session.homework_time_needed() == []


def test_a_session_that_is_on_now_stays_where_it_is(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    """Thursday 18:30 to 19:30 has begun and not ended at 19:00."""
    session, work = _essay_planned_on_tuesday(qapp, open_light, start="18:30", days=[3])
    session.solve(everything=True)
    _settle(qapp, session)
    kept = _block(session, work["id"])
    assert (kept["days"], kept["start"]) == ([3], "18:30")
    assert session.homework_time_needed() == []


def test_a_session_partly_done_by_the_timer_comes_back_for_what_is_left(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """On Tuesday at 16:00 the student runs one 30 minute timer of the 60 minute session and stops. Focus
    minutes are kept on the homework, so 60 - 30 = 30 min are still needed, and Replan all plans 30."""
    session, work = _essay_planned_on_tuesday(qapp, open_light)
    clock.set(datetime(2026, 11, 3, 16, 0))
    assert session.start_focus(work["id"], 1) is True
    clock.move(minutes=30)
    session.tick_focus()
    _settle(qapp, session)
    wait_until(qapp, lambda: int(session.assignments["essay"].get("focus_minutes") or 0) == 30)
    clock.set(datetime(2026, 11, 5, 19, 0))
    assert [item["minutes"] for item in session.homework_time_needed()] == [30]
    session.solve(everything=True)
    _settle(qapp, session)
    moved = _block(session, work["id"])
    assert moved["duration_min"] == 30
    assert (moved["days"][0], moved["start"]) >= THURSDAY_NOW


def test_replan_all_never_places_homework_before_now(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    """Two missed sessions and one ahead on Friday: every session ends up from Thursday 19:00 on."""
    session, work = _essay_planned_on_tuesday(qapp, open_light, estimate=180)
    other = {**work, "id": "essay-2", "start": "16:00", "days": [2], "duration_min": 60}
    third = {**work, "id": "essay-3", "start": "16:00", "days": [4], "duration_min": 60}
    session.add_block(other)
    session.add_block(third)
    session.save()
    _settle(qapp, session)
    session.solve(everything=True)
    _settle(qapp, session)
    spots = sorted(
        (item["days"][0], item["start"]) for item in session.blocks if item.get("assignment_id") == "essay"
    )
    assert len(spots) == 3
    assert all(spot >= THURSDAY_NOW for spot in spots), spots
