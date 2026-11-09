"""Plan with "split into focus chunks" on: chunks and breaks land on the grid, the solver is given room
for the breaks, titles keep their numbers, and a sibling session keeps the time Plan gave it."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from PySide6.QtWidgets import QApplication

from backend.slots import hhmm_to_minutes
from backend.tests.fake_clock import FakeClock
from desktop.native.calendar import sunday_due
from desktop.native.controller import NativeSession
from desktop.native.reuse import apply_plan
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.planner.planning_week import auto_split_preferences, session_in_the_planned_week
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def turn_on_auto_split(qapp: QApplication, session: NativeSession) -> None:
    wait_until(qapp, lambda: session.preferences is not None)
    session.save_preferences(auto_split_preferences())
    wait_until(qapp, lambda: bool((session.preferences or {}).get("auto_split_pomodoro")))


def save_the_week(qapp: QApplication, session: NativeSession) -> None:
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)


def essay_of(session: NativeSession, estimate_min: int, title: str = "Essay") -> dict:
    return {
        "id": "essay",
        "title": title,
        "due": sunday_due(session.week_start),
        "estimate_min": estimate_min,
        "revision": 0,
    }


def plan_and_wait_for_the_split(qapp: QApplication, session: NativeSession) -> None:
    session.solve()
    wait_until(qapp, lambda: session.trace is not None and not session.busy)
    wait_until(qapp, lambda: any(b.get("pomodoro_role") for b in session.blocks))
    wait_until(qapp, lambda: not session.busy and not session.dirty)


def test_planning_with_auto_split_leaves_focus_chunks_on_the_grid(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """This goes through a real solve and a real save, because the chunks have to survive validation."""
    session = session_in_the_planned_week(open_light, clock)
    turn_on_auto_split(qapp, session)
    session.add_homework(essay_of(session, 90))
    save_the_week(qapp, session)
    session.solve()
    wait_until(qapp, lambda: not session.busy and session.trace is not None)
    wait_until(qapp, lambda: any(b.get("pomodoro_role") for b in session.blocks))
    chunks = [b for b in session.blocks if b.get("pomodoro_role") == "work"]
    breaks = [b for b in session.blocks if b.get("pomodoro_role") == "break"]
    assert len(chunks) == 3, [b["title"] for b in session.blocks]
    assert len(breaks) == 2
    assert all(b["kind"] == "locked" and len(b["days"]) == 1 for b in chunks + breaks)
    # Every chunk sits on the 15-minute grid the server enforces.
    assert all(hhmm_to_minutes(b["start"]) % 15 == 0 for b in chunks + breaks)
    wait_until(qapp, lambda: not session.busy)
    assert session.conflict is False


def test_planning_without_auto_split_leaves_one_block(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    session = session_in_the_planned_week(open_light, clock)
    wait_until(qapp, lambda: session.preferences is not None)
    session.add_homework(essay_of(session, 90))
    save_the_week(qapp, session)
    session.solve()
    wait_until(qapp, lambda: not session.busy and session.trace is not None)
    assert not any(b.get("pomodoro_role") for b in session.blocks)


def test_the_solver_is_asked_to_reserve_the_breaks_as_well(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """Splitting after the solve without asking for the extra time first would lay the chunks and
    breaks over whatever the solver placed next, because it only reserved the homework's own length."""
    session = session_in_the_planned_week(open_light, clock)
    turn_on_auto_split(qapp, session)
    session.add_homework(essay_of(session, 90))
    save_the_week(qapp, session)
    sent: list[dict] = []
    original = session.client.request

    def spy(method: str, path: str, body: object, *args: object, **kwargs: object) -> object:
        if path == "/api/solve" and isinstance(body, dict):
            sent.append(body)
        return original(method, path, body, *args, **kwargs)

    session.client.request = spy  # type: ignore[method-assign]
    session.solve()
    wait_until(qapp, lambda: not session.busy and session.trace is not None)
    session.client.request = original  # type: ignore[method-assign]
    assert sent, "the solve never went out"
    asked = {block["title"]: block["duration_min"] for block in sent[0]["blocks"]}
    # 90 minutes of work plus the two 15-minute breaks that will sit between the chunks.
    assert asked["Essay"] == 120


def test_a_chunk_of_plain_homework_keeps_its_number(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """A flexible block with no assignment behind it keeps the numbering the split gave it."""
    session = session_in_the_planned_week(open_light, clock)
    turn_on_auto_split(qapp, session)
    session.add_block(
        {
            "id": "rev",
            "title": "Revision",
            "kind": "flexible",
            "duration_min": 90,
            "days": [0, 1, 2, 3, 4],
            "category": "study",
        }
    )
    save_the_week(qapp, session)
    plan_and_wait_for_the_split(qapp, session)
    assert [b["title"] for b in session.blocks if b.get("pomodoro_role") == "work"] == [
        "Revision · focus 1/3",
        "Revision · focus 2/3",
        "Revision · focus 3/3",
    ]


def test_a_chunk_of_a_tracked_assignment_takes_the_assignment_title_back(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """Not a defect in the split, and not something to fix here: the server rewrites the title of
    every block carrying an assignment_id (rewrite_session in backend/assignments.py), so the web's
    chunks are renamed in exactly the same way. Dropping the id to keep the number would stop focus
    time being credited to the assignment, which matters more than the label."""
    session = session_in_the_planned_week(open_light, clock)
    turn_on_auto_split(qapp, session)
    session.add_homework(essay_of(session, 90, "History essay"))
    save_the_week(qapp, session)
    plan_and_wait_for_the_split(qapp, session)
    chunks = [b for b in session.blocks if b.get("pomodoro_role") == "work"]
    assert len(chunks) == 3
    assert {b["title"] for b in chunks} == {"History essay"}
    # What the split is actually for still holds: the chunks are real placed blocks on one day.
    assert all(b["kind"] == "locked" and len(b["days"]) == 1 for b in chunks)


def mixed_split_week(session: NativeSession) -> tuple[dict, dict, dict]:
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "duration_min": 360,
            "days": [0],
            "start": "08:00",
            "category": "school",
        }
    )
    session.add_homework(essay_of(session, 90))
    session.add_homework(
        {
            "id": "quiz",
            "title": "Quiz",
            "due": sunday_due(session.week_start),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    school = next(block for block in session.blocks if block["id"] == "school")
    essay = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    quiz = next(block for block in session.blocks if block.get("assignment_id") == "quiz")
    return school, essay, quiz


def week_sent_by_save(qapp: QApplication, session: NativeSession) -> dict:
    sent: list[dict] = []
    original = session.client.request

    def spy(method: str, path: str, body: object, *args: object, **kwargs: object) -> object:
        if path == "/api/changes" and isinstance(body, dict):
            sent.append(deepcopy(body))
        return original(method, path, body, *args, **kwargs)

    session.client.request = spy  # type: ignore[method-assign]
    session.save()
    wait_until(qapp, lambda: not session.busy)
    session.client.request = original  # type: ignore[method-assign]
    assert sent, "the split week was not saved"
    weeks = sent[0].get("weeks") or []
    assert weeks, sent[0]
    return weeks[0]


def test_auto_split_keeps_a_sibling_sessions_solver_start_and_cleared_pin(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock
) -> None:
    """A 90-minute essay that splits must not throw away apply_plan's start on a newly placed
    30-minute quiz, or restore a pin the solver dropped on an unplaced one. The single-session chunk
    tests never have a sibling, so they stay green on the pre-plan week."""
    session = session_in_the_planned_week(open_light, clock)
    turn_on_auto_split(qapp, session)
    school, essay, quiz = mixed_split_week(session)
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)

    planned = deepcopy(session.blocks)
    placed_trace = {
        "placed": [
            {**school, "start": "08:00", "days": [0], "duration_min": 360},
            {**quiz, "start": "15:30", "days": [1], "duration_min": 30},
            {**essay, "start": "16:00", "days": [1], "duration_min": 120},
        ],
        "unplaced": [],
    }
    applied = apply_plan(
        planned,
        placed_trace,
        targets={essay["id"], quiz["id"]},
        assignments=session.assignments,
        week_start=session.week_start,
    )
    session.blocks = [{**block, "days": [2]} if block["id"] == "school" else block for block in applied]
    session._apply_auto_split(placed_trace, planned)

    placed_quiz = next(block for block in session.blocks if block.get("assignment_id") == "quiz")
    assert placed_quiz.get("start") == "15:30", placed_quiz
    assert placed_quiz.get("days") == [1], placed_quiz
    assert not placed_quiz.get("pinned")
    work = [block for block in session.blocks if block.get("pomodoro_role") == "work"]
    assert [block["duration_min"] for block in work] == [30, 30, 30]
    assert [block["title"] for block in work] == [
        "Essay · focus 1/3",
        "Essay · focus 2/3",
        "Essay · focus 3/3",
    ]
    assert {block.get("assignment_id") for block in work} == {"essay"}
    assert len([block for block in session.blocks if block.get("assignment_id") == "quiz"]) == 1
    assert len(session.assignments) == 2
    kept_school = next(block for block in session.blocks if block["id"] == "school")
    assert kept_school.get("days") == [2], kept_school

    saved = week_sent_by_save(qapp, session)["blocks"]
    saved_quiz = next(block for block in saved if block.get("assignment_id") == "quiz")
    assert saved_quiz.get("start") == "15:30"
    assert saved_quiz.get("days") == [1]
    assert not saved_quiz.get("pinned")
    saved_work = [block for block in saved if block.get("pomodoro_role") == "work"]
    assert [block["duration_min"] for block in saved_work] == [30, 30, 30]
    assert [block["title"] for block in saved_work] == [
        "Essay · focus 1/3",
        "Essay · focus 2/3",
        "Essay · focus 3/3",
    ]
    assert len([block for block in saved if block.get("assignment_id") == "essay"]) == 3
    assert len([block for block in saved if block.get("assignment_id") == "quiz"]) == 1

    pinned_week = deepcopy(planned)
    for block in pinned_week:
        if block.get("assignment_id") == "quiz":
            block["start"] = "15:00"
            block["days"] = [0]
            block["pinned"] = True
    unplaced_trace = {
        "placed": [
            {**school, "start": "08:00", "days": [0], "duration_min": 360},
            {**essay, "start": "16:00", "days": [1], "duration_min": 120},
        ],
        "unplaced": [{**quiz, "duration_min": 30, "days": [0, 1, 2, 3, 4]}],
    }
    session.blocks = apply_plan(
        pinned_week,
        unplaced_trace,
        targets={essay["id"], quiz["id"]},
        assignments=session.assignments,
        week_start=session.week_start,
    )
    session._apply_auto_split(unplaced_trace, pinned_week)

    leftover = next(block for block in session.blocks if block.get("assignment_id") == "quiz")
    assert leftover.get("start") in (None, ""), leftover
    assert not leftover.get("pinned"), leftover
    leftover_work = [block for block in session.blocks if block.get("pomodoro_role") == "work"]
    assert [block["duration_min"] for block in leftover_work] == [30, 30, 30]
    assert [block["title"] for block in leftover_work] == [
        "Essay · focus 1/3",
        "Essay · focus 2/3",
        "Essay · focus 3/3",
    ]
    assert len([block for block in session.blocks if block.get("assignment_id") == "essay"]) == 3
    assert len([block for block in session.blocks if block.get("assignment_id") == "quiz"]) == 1

    leftover_saved = week_sent_by_save(qapp, session)["blocks"]
    leftover_quiz = next(block for block in leftover_saved if block.get("assignment_id") == "quiz")
    assert leftover_quiz.get("start") in (None, "")
    assert not leftover_quiz.get("pinned")
    leftover_saved_work = [block for block in leftover_saved if block.get("pomodoro_role") == "work"]
    assert [block["duration_min"] for block in leftover_saved_work] == [30, 30, 30]
    assert len([block for block in leftover_saved if block.get("assignment_id") == "essay"]) == 3
    assert len([block for block in leftover_saved if block.get("assignment_id") == "quiz"]) == 1
