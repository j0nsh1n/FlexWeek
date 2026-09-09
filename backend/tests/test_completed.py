"""Behavior tests for completed blocks in solve(). Expected values are worked out from the fix description, not from a recorded run."""

from __future__ import annotations

import copy

from backend.models import TimeBlock
from backend.slots import hhmm_to_minutes, overlaps
from backend.solver import solve


def _locked(
    id: str,
    title: str,
    start: str,
    duration_min: int,
    days: list[int],
    energy: str = "medium",
    *,
    completed: bool = False,
) -> TimeBlock:
    return TimeBlock(
        id=id,
        title=title,
        kind="locked",
        duration_min=duration_min,
        days=days,
        start=start,
        priority=1,
        energy=energy,  # type: ignore[arg-type]
        completed=completed,
    )


def _flex(
    id: str,
    title: str,
    duration_min: int,
    days: list[int],
    *,
    priority: int = 3,
    energy: str = "medium",
    latest: str | None = None,
    earliest: str | None = None,
    start: str | None = None,
    completed: bool = False,
) -> TimeBlock:
    return TimeBlock(
        id=id,
        title=title,
        kind="flexible",
        duration_min=duration_min,
        days=days,
        priority=priority,  # type: ignore[arg-type]
        energy=energy,  # type: ignore[arg-type]
        latest=latest,
        earliest=earliest,
        start=start,
        completed=completed,
    )


def _by_id(blocks: list[TimeBlock]) -> dict[str, TimeBlock]:
    return {block.id: block for block in blocks}


def _no_overlaps(placed: list[TimeBlock]) -> bool:
    intervals: list[tuple[int, int, int]] = []
    for block in placed:
        if not block.start:
            continue
        start = hhmm_to_minutes(block.start)
        end = start + block.duration_min
        for day in block.days:
            intervals.append((day, start, end))
    for i, left in enumerate(intervals):
        for right in intervals[i + 1 :]:
            if left[0] == right[0] and overlaps(left[1], left[2], right[1], right[2]):
                return False
    return True


def test_pending_task_wins_the_free_hour_over_a_completed_task_without_start() -> None:
    # Only free hour is Monday 06:00–07:00; the rest is locked 07:00–23:00.
    wind = _locked("wind", "Wind-down", "07:00", 960, [0])
    done = _flex("done", "Finished quiz", 60, [0], priority=1, energy="high", completed=True)
    pending = _flex("pending", "History reading", 60, [0], priority=3, energy="high")
    trace = solve([wind, done, pending])
    assert [block.id for block in trace.placed] == ["wind", "pending"]
    assert _by_id(trace.placed)["pending"].start == "06:00"
    assert trace.unplaced == []
    assert trace.moves == []
    assert trace.complete is True


def test_completed_flexible_without_start_appears_nowhere_in_the_trace() -> None:
    wind = _locked("wind", "Wind-down", "07:00", 960, [0])
    done = _flex("done", "Finished quiz", 60, [0], priority=1, energy="high", completed=True)
    pending = _flex("pending", "History reading", 60, [0], priority=3, energy="high")
    trace = solve([wind, done, pending])
    assert [block.id for block in trace.placed] == ["wind", "pending"]
    assert trace.unplaced == []
    assert trace.moves == []
    assert trace.explanations == []
    assert trace.complete is True


def test_completed_with_start_keeps_its_slot_and_starves_the_pending_task() -> None:
    wind = _locked("wind", "Wind-down", "07:00", 960, [0])
    done = _flex("done", "Finished quiz", 60, [0], priority=1, energy="high", completed=True, start="06:00")
    pending = _flex("pending", "History reading", 60, [0], priority=3, energy="high")
    trace = solve([wind, done, pending])
    placed = _by_id(trace.placed)
    assert [block.id for block in trace.placed] == ["wind", "done"]
    assert placed["done"].start == "06:00"
    assert placed["done"].days == [0]
    assert [block.id for block in trace.unplaced] == ["pending"]
    assert {move.reason for move in trace.moves} == {"NO_SLOT_LEFT"}
    assert "NO_SLOT_LEFT" in trace.failed_constraints
    assert trace.complete is False
    assert _no_overlaps(trace.placed)


def test_completed_locked_block_still_occupies_its_time() -> None:
    rest = _locked("rest", "Evening wind-down", "07:00", 960, [0])
    lesson = _locked("lesson", "Finished lesson", "06:00", 60, [0], completed=True)
    pending = _flex("pending", "History reading", 60, [0], priority=3, energy="high")
    trace = solve([rest, lesson, pending])
    placed = _by_id(trace.placed)
    assert [block.id for block in trace.placed] == ["rest", "lesson"]
    assert placed["lesson"].start == "06:00"
    assert placed["lesson"].days == [0]
    assert [block.id for block in trace.unplaced] == ["pending"]
    assert {move.reason for move in trace.moves} == {"NO_SLOT_LEFT"}
    assert trace.complete is False


def test_missed_day_recovery_leaves_a_completed_flexible_task_alone() -> None:
    # School runs Monday and Tuesday; Monday's occurrence was missed, so Monday
    # is free while Tuesday 08:00–14:30 stays occupied.
    school = _locked("school", "School", "08:00", 390, [0, 1])
    school.missed_days = [0]
    done = _flex("done", "Finished quiz", 60, [1], completed=True, start="10:00")
    pending = _flex("pending", "Makeup reading", 60, [0], energy="high")
    trace = solve([school, done, pending])
    placed = _by_id(trace.placed)
    assert [block.id for block in trace.placed] == ["school", "done", "pending"]
    assert placed["school"].days == [1]
    assert placed["pending"].days == [0]
    assert placed["pending"].start == "06:00"
    assert placed["done"].start == "10:00"
    assert placed["done"].days == [1]
    assert trace.unplaced == []
    assert trace.moves == []
    assert trace.complete is True


def test_solve_leaves_its_input_blocks_unmodified() -> None:
    blocks = [
        _locked("school", "School", "08:00", 390, [0]),
        _flex("spent", "Finished quiz", 60, [1], completed=True, start="10:00"),
        _flex("ghost", "Unstarted finish", 60, [2], completed=True),
        _flex("pending", "Homework", 60, [0], energy="high"),
    ]
    snapshot = copy.deepcopy(blocks)
    trace = solve(blocks)
    assert [block.id for block in trace.placed] == ["school", "spent", "pending"]
    assert [block.completed for block in blocks] == [False, True, True, False]
    assert [block.start for block in blocks] == ["08:00", "10:00", None, None]
    assert [block.days for block in blocks] == [[0], [1], [2], [0]]
    assert blocks == snapshot


def test_a_finished_task_is_not_reported_as_reshuffled_after_a_miss() -> None:
    # The task held 09:00 when the week was last solved. It has since been
    # finished and its time cleared, so it leaves the solver's world entirely.
    # That is not a reshuffle, and reporting it as moved to nowhere would be a
    # lie shown to the student.
    from backend.solver import reschedule_after_miss

    practice = _locked("practice", "Practice", "16:00", 60, [0])
    previously_placed = [_flex("essay", "Essay", 60, [0], start="09:00")]
    now = [practice, _flex("essay", "Essay", 60, [0], completed=True)]
    trace = reschedule_after_miss(now, "practice", 0, previously_placed)
    assert [move.block_id for move in trace.moves] == []
    assert [block.id for block in trace.unplaced] == []
