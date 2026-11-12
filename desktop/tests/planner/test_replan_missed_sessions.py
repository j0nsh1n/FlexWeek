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


def _add_session(qapp: QApplication, session: NativeSession, work: dict, block_id: str, day: int) -> None:
    session.add_block({**work, "id": block_id, "start": "16:00", "days": [day], "duration_min": 60})
    session.save()
    _settle(qapp, session)


def _log_focus(
    qapp: QApplication, session: NativeSession, work: dict, clock: FakeClock, minutes: int, total: int
) -> None:
    """One timer of `minutes` run on Tuesday at 16:00; the focus kept on the homework is then `total`. The
    timer never ticks a session off, so every session stays unfinished. The clock goes back to Thursday."""
    session.reset_focus()
    clock.set(datetime(2026, 11, 3, 16, 0))
    assert session.start_focus(work["id"], 1) is True
    clock.move(minutes=minutes)
    session.tick_focus()
    _settle(qapp, session)
    wait_until(qapp, lambda: int(session.assignments["essay"].get("focus_minutes") or 0) == total)
    clock.set(datetime(2026, 11, 5, 19, 0))


def _placed(session: NativeSession) -> list[tuple[int, str, int]]:
    """The essay's sessions that have a time, as (day, start, minutes), in time order."""
    return sorted(
        (item["days"][0], item["start"], item["duration_min"])
        for item in session.blocks
        if item.get("assignment_id") == "essay" and item.get("start")
    )


def test_a_session_ending_inside_the_current_quarter_hour_is_not_moved(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """Thursday 18:00 to 19:00 with the clock at 18:50: the student is 50 minutes in. A plan starts at
    19:00 (the clock rounded up), but the session has not ended, so Replan all leaves it and no time is
    needed. At 18:44, a plan start of 18:45, nothing changes either (the control); at 19:00 it is over."""
    session, work = _essay_planned_on_tuesday(qapp, open_light, start="18:00", days=[3])
    for minute in (44, 50):
        clock.set(datetime(2026, 11, 5, 18, minute))
        assert session.homework_time_needed() == []
        assert session.missed_block_ids() == frozenset()
        session.solve(everything=True)
        _settle(qapp, session)
        kept = _block(session, work["id"])
        assert (kept["days"], kept["start"]) == ([3], "18:00"), f"at 18:{minute}"
    clock.set(datetime(2026, 11, 5, 19, 0))
    assert session.missed_block_ids() == frozenset({work["id"]})
    assert [item["minutes"] for item in session.homework_time_needed()] == [60]


def test_focus_time_is_not_taken_off_twice_for_two_missed_sessions(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """Estimate 120, Tuesday and Wednesday 16:00 to 17:00 both missed, 30 min of focus: 90 min are still to
    do. The count says 1 h 30 before and Replan all places 60 + 30 (Tuesday's session first), not 30 + 30."""
    session, work = _essay_planned_on_tuesday(qapp, open_light, estimate=120)
    _add_session(qapp, session, work, "essay-2", 2)
    _log_focus(qapp, session, work, clock, 30, 30)
    assert [item["minutes"] for item in session.homework_time_needed()] == [90]
    assert _sentence(session) == "1 h 30 min still needs a time"
    session.solve(everything=True)
    _settle(qapp, session)
    shares = (_block(session, work["id"])["duration_min"], _block(session, "essay-2")["duration_min"])
    assert shares == (60, 30)
    assert all((day, start) >= THURSDAY_NOW for day, start, _ in _placed(session))
    assert session.homework_time_needed() == []


def test_a_missed_session_covered_by_focus_asks_for_nothing_and_is_not_called_missed(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """Estimate 120, two missed hours, 60 min of focus (two 30 min timers): 60 min are left, so only the
    earlier session needs a new time; the later one is the time the focus covered. Before, both sessions
    were counted against each other and the focus twice, so nothing moved and the count was 0. Now Replan
    all moves one session of 60 and leaves the other where it was, and the count is 60."""
    session, work = _essay_planned_on_tuesday(qapp, open_light, estimate=120)
    _add_session(qapp, session, work, "essay-2", 2)
    _log_focus(qapp, session, work, clock, 30, 30)
    _log_focus(qapp, session, work, clock, 30, 60)
    assert [item["minutes"] for item in session.homework_time_needed()] == [60]
    assert session.missed_block_ids() == frozenset({work["id"]}), "Wednesday's hour is covered, not missed"
    session.solve(everything=True)
    _settle(qapp, session)
    moved = _block(session, work["id"])
    assert moved["duration_min"] == 60
    assert (moved["days"][0], moved["start"]) >= THURSDAY_NOW
    kept = _block(session, "essay-2")
    assert (kept["days"], kept["start"]) == ([2], "16:00")
    assert session.homework_time_needed() == []


def test_one_missed_session_with_focus_comes_back_for_what_is_left(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """The control of the two above: 60 min estimated, 30 of focus, one missed hour: it comes back as 30."""
    session, work = _essay_planned_on_tuesday(qapp, open_light)
    _log_focus(qapp, session, work, clock, 30, 30)
    assert [item["minutes"] for item in session.homework_time_needed()] == [30]
    session.solve(everything=True)
    _settle(qapp, session)
    assert [minutes for _, _, minutes in _placed(session)] == [30]


def test_a_missed_session_never_comes_back_longer_than_itself(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    """180 min estimated and only the missed hour is in this week (the rest sits in a later week): 180 are
    left, but the missed session is 60 min and comes back as 60."""
    session, work = _essay_planned_on_tuesday(qapp, open_light, estimate=180)
    session.solve(everything=True)
    _settle(qapp, session)
    assert _block(session, work["id"])["duration_min"] == 60


def test_a_pinned_session_that_passed_is_called_missed_but_not_counted(
    qapp: QApplication, open_light: Callable[..., NativeWindow]
) -> None:
    """What a pinned missed session shows is not decided by the owner: screens call it missed, as they
    did, and the count of homework needing a time does not include it (no plan moves it)."""
    session, work = _essay_planned_on_tuesday(qapp, open_light, pinned=True)
    assert session.missed_block_ids() == frozenset({work["id"]})
    assert session.homework_time_needed() == []


def test_an_unfinished_session_of_a_week_that_is_over_is_still_called_missed(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """The essay's Tuesday 16:00 session was never done. Looked at on Monday of the next week, that week
    is over: the session must still be called missed, so no look files it under Done or dims it like
    finished work. Finished work in that week is not called missed (the control)."""
    session, work = _essay_planned_on_tuesday(qapp, open_light)
    session.add_homework(
        {
            "id": "maths",
            "title": "Maths sheet",
            "due": due_on(session, 5, "23:59"),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    _settle(qapp, session)
    maths = next(item for item in session.blocks if item.get("assignment_id") == "maths")
    maths.update({"start": "18:00", "days": [1], "duration_min": 60, "completed": True})
    session.add_block(maths)
    session.save()
    _settle(qapp, session)
    clock.set(datetime(2026, 11, 9, 10, 0))
    assert session.missed_block_ids() == frozenset({work["id"]})


def test_a_week_that_is_over_counts_its_missed_session_as_needing_a_time(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """Looked at on Monday of the next week, the essay's unfinished Tuesday hour is called missed, so the
    count of homework needing a time agrees: the essay still needs its 60 minutes, and the status line does
    not say "Everything has a time." On Tuesday at 16:30 the same hour is still on, so it has a time and
    nothing is counted (the control)."""
    session, work = _essay_planned_on_tuesday(qapp, open_light)
    clock.set(datetime(2026, 11, 3, 16, 30))
    assert session.missed_block_ids() == frozenset()
    assert session.homework_time_needed() == []
    clock.set(datetime(2026, 11, 9, 10, 0))
    assert session.missed_block_ids() == frozenset({work["id"]})
    assert [item["minutes"] for item in session.homework_time_needed()] == [60]
    assert _sentence(session) != EVERYTHING
