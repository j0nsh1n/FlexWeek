"""Solver fixtures for Phase 2. Expected values come from the spec, not from a recorded run."""

from __future__ import annotations

import json
from pathlib import Path

from backend.models import TimeBlock
from backend.slots import hhmm_to_minutes, overlaps
from backend.solver import SOLVE_BUDGET_MS, solve

DATA = Path(__file__).resolve().parent.parent / "data"


def _locked(
    id: str,
    title: str,
    start: str,
    duration_min: int,
    days: list[int],
    energy: str = "medium",
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
    )


def _by_id(blocks: list[TimeBlock]) -> dict[str, TimeBlock]:
    return {block.id: block for block in blocks}


def _placed_interval(block: TimeBlock) -> tuple[int, int, int]:
    assert block.start is not None
    assert len(block.days) >= 1
    start = hhmm_to_minutes(block.start)
    return block.days[0], start, start + block.duration_min


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


def test_empty_week_is_complete() -> None:
    trace = solve([])
    assert trace.complete is True
    assert trace.placed == []
    assert trace.unplaced == []
    assert trace.moves == []
    assert trace.solve_ms < SOLVE_BUDGET_MS


def test_t1_only_locked_is_identity() -> None:
    school = _locked("school", "School", "08:00", 390, [0, 1, 2, 3, 4])
    trace = solve([school])
    assert trace.complete is True
    assert trace.moves == []
    assert [block.id for block in trace.placed] == ["school"]
    assert trace.unplaced == []
    assert trace.placed[0].start == "08:00"


def test_t2_one_homework_with_room_is_placed() -> None:
    school = _locked("school", "School", "08:00", 390, [0])
    hw = _flex("hw", "Math homework", 60, [0], energy="high")
    trace = solve([school, hw])
    placed = _by_id(trace.placed)
    assert "hw" in placed
    assert placed["hw"].start is not None
    assert trace.unplaced == []
    assert trace.complete is True
    start = hhmm_to_minutes(placed["hw"].start)
    # High-energy window is 06:00–12:00; school occupies 08:00–14:30.
    assert 6 * 60 <= start < 8 * 60


def test_t3_test_beats_reading_for_one_slot() -> None:
    # One free hour Monday 06:00–07:00; everything else locked.
    wind = _locked("wind", "Wind-down", "07:00", 960, [0])  # 07:00–23:00
    test = _flex("test", "Chem test review", 60, [0], priority=1, energy="high")
    reading = _flex("read", "History reading", 60, [0], priority=4, energy="low")
    trace = solve([wind, test, reading])
    placed = _by_id(trace.placed)
    unplaced = _by_id(trace.unplaced)
    assert "test" in placed
    assert placed["test"].start == "06:00"
    assert "read" in unplaced
    assert "PRIORITY_PREEMPT" in {move.reason for move in trace.moves}
    assert "PRIORITY_PREEMPT" in trace.failed_constraints
    assert trace.complete is False


def test_t4_six_hour_task_into_two_hour_gap() -> None:
    school = _locked("school", "School", "08:00", 390, [0])  # 08:00–14:30
    evening = _locked("eve", "Evening", "16:30", 390, [0])  # 16:30–23:00
    # Free: 06:00–08:00 (2h) and 14:30–16:30 (2h). A 6h block cannot split.
    paper = _flex("paper", "Long paper", 360, [0], latest="Monday 23:00")
    trace = solve([school, evening, paper])
    assert "paper" in {block.id for block in trace.unplaced}
    assert "NO_SLOT_LEFT" in trace.failed_constraints
    assert trace.complete is False


def test_t5_deadline_before_any_legal_window() -> None:
    school = _locked("school", "School", "08:00", 390, [0])
    quiz = _flex(
        "quiz",
        "Spanish quiz prep",
        75,
        [0],
        priority=1,
        latest="Monday 07:00",
    )
    trace = solve([school, quiz])
    assert [block.id for block in trace.unplaced] == ["quiz"]
    assert "DEADLINE_MISS" in trace.failed_constraints
    assert trace.complete is False


def test_t6_homework_domain_excludes_sport() -> None:
    sport = _locked("sport", "Soccer", "16:00", 120, [1], energy="high")
    hw = _flex("hw", "Physics set", 60, [1], latest="Tuesday 21:00")
    trace = solve([sport, hw])
    placed = _by_id(trace.placed)
    assert "hw" in placed
    day, start, end = _placed_interval(placed["hw"])
    assert day == 1
    assert not overlaps(start, end, 16 * 60, 18 * 60)


def test_t7_packed_fixture_under_budget() -> None:
    blocks = [
        _locked("school", "School", "08:00", 390, [0, 1, 2, 3, 4]),
        _locked("sleep", "Sleep guard", "22:00", 60, [0, 1, 2, 3, 4, 5, 6]),
    ]
    for i in range(12):
        blocks.append(
            _flex(
                f"t{i}",
                f"Task {i}",
                45,
                [0, 1, 2, 3, 4, 5, 6],
                latest="Sunday 21:00",
            )
        )
    trace = solve(blocks)
    assert trace.solve_ms < SOLVE_BUDGET_MS
    assert "NO_SLOT_LEFT" in trace.failed_constraints or trace.complete
    assert _no_overlaps(trace.placed)


def test_paper_due_tomorrow_is_placed_before_deadline() -> None:
    school = _locked("school", "School", "08:00", 390, [0])
    paper = _flex("paper", "3-hour paper", 180, [0, 1], latest="Tuesday 08:00")
    trace = solve([school, paper])
    placed = _by_id(trace.placed)
    assert "paper" in placed
    day, start, end = _placed_interval(placed["paper"])
    assert (day, end) <= (1, 8 * 60)


def test_impossible_oversize_task_is_unplaced() -> None:
    school = _locked("school", "School", "08:00", 390, [0])
    sleep = _locked("sleep", "Sleep guard", "22:00", 60, [0])
    giant = _flex("giant", "Impossible", 600, [0])  # 10h; no 10h contiguous gap
    trace = solve([school, sleep, giant])
    assert [block.id for block in trace.unplaced] == ["giant"]
    assert "NO_SLOT_LEFT" in trace.failed_constraints
    assert trace.complete is False


def test_two_homeworks_both_placed() -> None:
    school = _locked("school", "School", "08:00", 390, [0])
    a = _flex("a", "Math", 60, [0])
    b = _flex("b", "English", 45, [0])
    trace = solve([school, a, b])
    ids = {block.id for block in trace.placed}
    assert {"school", "a", "b"} <= ids
    assert trace.complete is True
    assert _no_overlaps(trace.placed)


def test_touching_endpoints_do_not_overlap() -> None:
    first = _flex("first", "First", 60, [0], latest="Monday 12:00")
    second = _flex("second", "Second", 60, [0], latest="Monday 12:00")
    trace = solve([first, second])
    assert trace.complete is True
    assert _no_overlaps(trace.placed)
    starts = sorted(hhmm_to_minutes(block.start) for block in trace.placed if block.start)
    assert starts == [6 * 60, 7 * 60]


def test_sleep_guard_rejects_overflow_past_23() -> None:
    late = _flex("late", "Too late", 120, [0], earliest="Monday 22:00")
    trace = solve([late])
    assert [block.id for block in trace.unplaced] == ["late"]
    assert "SLEEP_GUARD" in trace.failed_constraints


def test_block_may_end_at_23() -> None:
    last = _flex("last", "Wind-down homework", 60, [0], earliest="Monday 22:00")
    trace = solve([last])
    placed = _by_id(trace.placed)
    assert placed["last"].start == "22:00"
    assert trace.complete is True


def test_placed_flexible_never_starts_after_deadline() -> None:
    hw = _flex("hw", "Due noon", 60, [0, 1, 2], latest="Monday 12:00")
    trace = solve([hw])
    placed = _by_id(trace.placed)["hw"]
    day, start, _end = _placed_interval(placed)
    assert (day, start) <= (0, 12 * 60)


def test_property_no_output_overlaps_on_demos() -> None:
    for name in ("demo_alex.json", "demo_jordan.json"):
        raw = json.loads((DATA / name).read_text())
        blocks = [TimeBlock.model_validate(item) for item in raw]
        trace = solve(blocks)
        assert _no_overlaps(trace.placed)
        assert trace.solve_ms < SOLVE_BUDGET_MS
        for block in trace.placed:
            if block.kind == "flexible":
                assert block.start is not None


def test_earliest_is_respected() -> None:
    hw = _flex("hw", "Afternoon only", 60, [0], earliest="Monday 15:00")
    trace = solve([hw])
    start = hhmm_to_minutes(_by_id(trace.placed)["hw"].start or "00:00")
    assert start >= 15 * 60


def test_locked_without_start_is_ignored_as_occupancy() -> None:
    broken = TimeBlock(
        id="broken",
        title="Broken lock",
        kind="locked",
        duration_min=60,
        days=[0],
        start=None,
    )
    hw = _flex("hw", "Homework", 30, [0])
    trace = solve([broken, hw])
    assert "hw" in {block.id for block in trace.placed}


def test_unsolvable_week_returns_partial_not_error() -> None:
    school = _locked("school", "School", "06:00", 1020, [0])  # whole Monday
    hw = _flex("hw", "Homework", 60, [0], latest="Monday 21:00")
    other = _flex("sat", "Weekend reading", 30, [5])
    trace = solve([school, hw, other])
    ids_placed = {block.id for block in trace.placed}
    ids_unplaced = {block.id for block in trace.unplaced}
    assert "sat" in ids_placed
    assert "hw" in ids_unplaced
    assert trace.complete is False
    assert trace.failed_constraints


def test_moves_record_unplaced_reasons() -> None:
    quiz = _flex("quiz", "Quiz", 75, [0], latest="Monday 07:00")
    trace = solve([quiz])
    assert any(move.block_id == "quiz" and move.reason == "DEADLINE_MISS" for move in trace.moves)
