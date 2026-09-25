"""Splitting a placed block into focus chunks and breaks, checked as data.

Expected behaviour comes from the web client, which has had this feature all along: pomodoroPlan,
buildPomodoroBlocks, solveInputBlocks and autoSplitSolvedBlocks in frontend/app.js.
"""

from __future__ import annotations

import pytest

from desktop.native.pomodoro import (
    BREAK_TITLE,
    MAX_BLOCKS,
    TITLE_MAX,
    child_title,
    inflate_for_solve,
    plan_for,
    split_children,
    split_solved,
    splittable,
)

PREFS = {
    "auto_split_pomodoro": True,
    "timer_work_min": 30,
    "timer_break_min": 15,
    "timer_long_break_min": 30,
    "timer_long_break_every": 4,
}


def essay(**fields: object) -> dict:
    return {
        "id": "essay",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 90,
        "days": [0, 1, 2, 3, 4],
        "category": "assignments",
        **fields,
    }


def placed_at(start: str = "16:00", day: int = 3) -> dict:
    return {"id": "essay", "start": start, "days": [day], "kind": "flexible"}


def test_a_plan_alternates_work_and_breaks() -> None:
    plan = plan_for(90, PREFS)
    assert plan["error"] is None
    assert [(s["role"], s["duration_min"]) for s in plan["segments"]] == [
        ("work", 30),
        ("break", 15),
        ("work", 30),
        ("break", 15),
        ("work", 30),
    ]
    assert plan["total_min"] == 120


def test_off_grid_lengths_are_refused_rather_than_making_starts_the_server_rejects() -> None:
    plan = plan_for(90, {**PREFS, "timer_work_min": 25})
    assert plan["error"] and plan["segments"] == []


def test_a_long_break_arrives_on_the_cadence() -> None:
    plan = plan_for(300, {**PREFS, "timer_long_break_every": 2})
    breaks = [s["duration_min"] for s in plan["segments"] if s["role"] == "break"]
    assert breaks[1] == PREFS["timer_long_break_min"]


def test_chunks_are_laid_end_to_end_from_where_the_solver_put_the_block() -> None:
    children = split_children(essay(), placed_at("16:00"), plan_for(90, PREFS))
    assert [(c["start"], c["duration_min"]) for c in children] == [
        ("16:00", 30),
        ("16:30", 15),
        ("16:45", 30),
        ("17:15", 15),
        ("17:30", 30),
    ]


def test_every_chunk_lands_on_the_one_day_the_solver_chose() -> None:
    """The source is a flexible block with five candidate days; a chunk has a real place."""
    children = split_children(essay(), placed_at(day=3), plan_for(90, PREFS))
    assert {tuple(child["days"]) for child in children} == {(3,)}
    assert {child["kind"] for child in children} == {"locked"}


def test_a_chunk_is_numbered_and_a_break_is_named() -> None:
    children = split_children(essay(), placed_at(), plan_for(90, PREFS))
    assert [c["title"] for c in children if c["pomodoro_role"] == "work"] == [
        "Essay · focus 1/3",
        "Essay · focus 2/3",
        "Essay · focus 3/3",
    ]
    assert {c["title"] for c in children if c["pomodoro_role"] == "break"} == {BREAK_TITLE}


def test_a_title_at_the_limit_still_produces_one_the_server_accepts() -> None:
    """The week is changed before it is saved, so a title the save rejects strands the split."""
    assert len(child_title("x" * TITLE_MAX, 2, 9)) <= TITLE_MAX


def test_only_the_first_chunk_inherits_the_focus_history() -> None:
    """Copying it onto every chunk would count the same minutes once per chunk."""
    children = split_children(essay(focus_minutes=45, focus_sessions=2), placed_at(), plan_for(90, PREFS))
    assert [c["focus_minutes"] for c in children] == [45, 0, 0, 0, 0]


def test_progress_on_an_assignment_is_never_copied_onto_a_chunk() -> None:
    """It lives on the assignment, so a chunk carrying it would double-count on credit."""
    children = split_children(essay(assignment_id="a1", focus_minutes=45), placed_at(), plan_for(90, PREFS))
    assert {c["focus_minutes"] for c in children} == {0}
    assert all("assignment_id" not in c for c in children if c["pomodoro_role"] == "break")


def test_a_break_carries_none_of_the_work_details() -> None:
    children = split_children(
        essay(course="English", spotify_url="https://open.spotify.com/track/a"),
        placed_at(),
        plan_for(90, PREFS),
    )
    breaks = [c for c in children if c["pomodoro_role"] == "break"]
    assert all(c["course"] is None and c["spotify_url"] is None for c in breaks)
    assert all(c["category"] == "free" for c in breaks)


def test_the_solver_is_asked_for_the_time_the_breaks_need_as_well() -> None:
    """Without this the solver reserves 90 minutes and the 120 minutes of chunks land on top of
    whatever it put next."""
    assert inflate_for_solve([essay()], PREFS)[0]["duration_min"] == 120


def test_nothing_is_inflated_when_the_setting_is_off() -> None:
    assert inflate_for_solve([essay()], {**PREFS, "auto_split_pomodoro": False})[0]["duration_min"] == 90


def test_a_block_no_longer_than_one_chunk_is_left_alone() -> None:
    short = essay(duration_min=30)
    assert splittable(short, PREFS) is False
    assert inflate_for_solve([short], PREFS)[0]["duration_min"] == 30


@pytest.mark.parametrize("fields", [{"completed": True}, {"pomodoro_role": "work"}, {"kind": "locked"}])
def test_finished_already_split_and_fixed_blocks_are_left_alone(fields: dict) -> None:
    assert splittable(essay(**fields), PREFS) is False


def test_the_week_is_rebuilt_with_the_chunks_in_place_of_the_block() -> None:
    other = {"id": "dinner", "title": "Dinner", "kind": "locked", "duration_min": 60, "days": [3]}
    blocks = [essay(), other]
    split, count = split_solved(blocks, {"placed": [placed_at()]}, PREFS)
    assert count == 1
    assert [b["id"] for b in split][-1] == "dinner"
    assert len(split) == 6


def test_a_block_the_solver_could_not_place_is_not_split() -> None:
    split, count = split_solved([essay()], {"placed": [], "unplaced": [{"id": "essay"}]}, PREFS)
    assert count == 0 and split[0]["id"] == "essay"


def test_chunks_that_would_run_past_the_end_of_the_day_leave_the_block_whole() -> None:
    split, count = split_solved([essay()], {"placed": [placed_at("23:00")]}, PREFS)
    assert count == 0 and len(split) == 1


def test_a_split_that_would_break_the_week_limit_is_skipped_whole() -> None:
    """The server caps a week at 100 blocks, and a partial split is worse than none."""
    filler = [
        {"id": f"f{i}", "title": "x", "kind": "locked", "duration_min": 30, "days": [0]}
        for i in range(MAX_BLOCKS - 2)
    ]
    split, count = split_solved([essay(), *filler], {"placed": [placed_at()]}, PREFS)
    assert count == 0
    assert len(split) == MAX_BLOCKS - 1


def test_nothing_is_split_when_the_setting_is_off() -> None:
    split, count = split_solved([essay()], {"placed": [placed_at()]}, {**PREFS, "auto_split_pomodoro": False})
    assert count == 0 and len(split) == 1
