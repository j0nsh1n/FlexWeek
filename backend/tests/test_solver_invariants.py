"""Check solver output with independent minute arithmetic and reproducible inputs."""

from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from backend import solver
from backend.models import TimeBlock, WeekRequest
from backend.solver import solve


@pytest.mark.parametrize("seed", range(20))
def test_generated_weeks_preserve_grid_bounds_occupancy_and_input(seed: int) -> None:
    rng = random.Random(seed)
    blocks = [
        TimeBlock(id="school", title="School", kind="locked", days=[0, 1],
                  start="08:00", duration_min=180, missed_days=[0]),
        TimeBlock(id="spent", title="Finished work", kind="flexible", days=[1],
                  start="12:00", duration_min=60, completed=True),
        TimeBlock(id="done", title="Done without placement", kind="flexible", days=[0],
                  duration_min=60, completed=True),
    ]
    for i in range(6):
        day = rng.randrange(2)
        days = sorted(rng.sample([0, 1], rng.randint(1, 2)))
        earliest = rng.randrange(6, 10)
        latest = rng.randrange(11, 18)
        blocks.append(TimeBlock(
            id=f"task-{i}", title=f"Task {i}", kind="flexible", days=days,
            duration_min=rng.choice([15, 30, 60, 90]),
            earliest=f"{['Monday', 'Tuesday'][day]} {earliest:02}:00",
            latest=f"{['Monday', 'Tuesday'][day]} {latest:02}:00",
        ))
    WeekRequest(blocks=blocks)
    before = [block.model_dump() for block in blocks]
    trace = solve(blocks)
    assert [block.model_dump() for block in blocks] == before
    placed = {block.id: block for block in trace.placed}
    assert placed["school"].days == [1]
    assert placed["spent"].start == "12:00"
    assert placed["spent"].days == [1]
    pending = {block.id for block in blocks if block.kind == "flexible" and not block.completed}
    assert set(placed) - {"school", "spent"} | {b.id for b in trace.unplaced} == pending
    assert set(placed).isdisjoint(b.id for b in trace.unplaced)
    assert trace.complete == (len(trace.unplaced) == 0)
    occupied: set[tuple[int, int]] = set()
    originals = {block.id: block for block in blocks}
    for block in trace.placed:
        assert block.start is not None
        hour, minute = map(int, block.start.split(":"))
        start = hour * 60 + minute
        assert start % 15 == 0
        assert 360 <= start < start + block.duration_min <= 1380
        for day in block.days:
            slots = {(day, t) for t in range(start, start + block.duration_min, 15)}
            assert occupied.isdisjoint(slots), (seed, block.id, occupied & slots)
            occupied |= slots
        if block.id not in pending:
            continue
        original = originals[block.id]
        assert len(block.days) == 1 and block.days[0] in original.days
        assert original.earliest is not None and original.latest is not None
        first_day, first_time = original.earliest.split()
        last_day, last_time = original.latest.split()
        first = (["Monday", "Tuesday"].index(first_day), int(first_time[:2]) * 60)
        last = (["Monday", "Tuesday"].index(last_day), int(last_time[:2]) * 60)
        assert first <= (block.days[0], start)
        assert (block.days[0], start + block.duration_min) <= last
    reasons = {item.block_id for item in trace.explanations if item.reason is not None}
    assert {block.id for block in trace.unplaced} <= reasons


def test_priority_wins_even_when_reading_has_fewer_candidate_slots() -> None:
    blocks = [
        TimeBlock(id="rest", title="Rest", kind="locked", days=[0], start="07:15", duration_min=945),
        TimeBlock(id="exam", title="Exam prep", kind="flexible", days=[0], duration_min=60, priority=1),
        TimeBlock(id="reading", title="Reading", kind="flexible", days=[0], duration_min=75, priority=4),
    ]
    trace = solve(blocks)
    assert {block.id for block in trace.placed} == {"rest", "exam"}
    assert [block.id for block in trace.unplaced] == ["reading"]
    assert next(move.reason for move in trace.moves if move.block_id == "reading") == "PRIORITY_PREEMPT"


def test_one_exam_block_wins_capacity_over_two_reading_blocks() -> None:
    blocks = [
        TimeBlock(id="rest", title="Rest", kind="locked", days=[0], start="07:00", duration_min=960),
        TimeBlock(id="exam", title="Exam prep", kind="flexible", days=[0], duration_min=60,
                  priority=1, energy="high"),
        TimeBlock(id="read-1", title="Read one", kind="flexible", days=[0], duration_min=30,
                  priority=4, energy="high"),
        TimeBlock(id="read-2", title="Read two", kind="flexible", days=[0], duration_min=30,
                  priority=4, energy="high"),
    ]
    trace = solve(blocks)
    assert {block.id for block in trace.placed} == {"rest", "exam"}
    assert {block.id for block in trace.unplaced} == {"read-1", "read-2"}
    assert {move.reason for move in trace.moves} == {"PRIORITY_PREEMPT"}


def test_budget_expiry_returns_the_best_partial_placement(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter([0.0, 0.0, 0.0, 0.0, 0.151])
    monkeypatch.setattr(solver, "time", SimpleNamespace(perf_counter=lambda: next(ticks, 0.151)))
    blocks = [
        TimeBlock(id="exam", title="Exam", kind="flexible", days=[0], duration_min=60,
                  priority=1, energy="high"),
        TimeBlock(id="reading", title="Reading", kind="flexible", days=[0], duration_min=60, priority=4),
    ]
    trace = solve(blocks)
    assert [(block.id, block.start, block.days) for block in trace.placed] == [("exam", "06:00", [0])]
    assert [block.id for block in trace.unplaced] == ["reading"]
    assert trace.complete is False
    assert [item.block_id for item in trace.explanations if item.reason] == ["reading"]
    assert blocks[0].start is None and blocks[1].start is None


def test_feasible_mixed_priorities_finish_within_budget() -> None:
    # The last two columns are a hand-built feasible schedule, not solver output.
    cases = [
        (180, 3, [0, 1, 2, 3, 4], 4, 870),
        (60, 4, [0], 0, 360),
        (60, 1, [1, 2, 3, 4], 1, 360),
        (180, 2, [1, 4], 1, 870),
        (180, 1, [0, 2, 4], 2, 870),
        (90, 2, [0, 2, 3], 0, 1050),
        (90, 1, [0, 1, 2, 4], 2, 1050),
        (180, 1, [0, 1, 3], 0, 870),
        (60, 3, [0, 1, 2, 3], 2, 1140),
        (60, 3, [2], 2, 360),
        (90, 3, [1, 4], 1, 1050),
        (60, 3, [1, 2, 3], 3, 360),
        (60, 4, [0, 1, 4], 0, 1140),
        (60, 3, [0, 2, 3], 0, 1200),
        (180, 2, [0, 3, 4], 3, 870),
        (90, 2, [0, 2, 3, 4], 3, 1050),
    ]
    occupied = {(day, minute) for day in range(5) for minute in range(480, 870, 15)}
    blocks = [{"id": "school", "title": "School", "kind": "locked", "days": [0, 1, 2, 3, 4],
               "start": "08:00", "duration_min": 390}]
    for i, (duration, priority, days, day, start) in enumerate(cases):
        assert day in days and 360 <= start < start + duration <= 1260
        slots = {(day, minute) for minute in range(start, start + duration, 15)}
        assert occupied.isdisjoint(slots)
        occupied |= slots
        blocks.append({"id": f"t{i}", "title": f"Task {i}", "kind": "flexible", "days": days,
                       "duration_min": duration, "priority": priority, "latest": "Friday 21:00"})
    trace = solve(WeekRequest.model_validate({"blocks": blocks}).blocks)
    assert trace.complete is True
    assert {block.id for block in trace.placed} == {"school", *(f"t{i}" for i in range(16))}
    assert trace.solve_ms < 150


def test_feasible_energy_ordering_does_not_spend_budget_on_optional_skips() -> None:
    blocks: list[TimeBlock] = []
    for day in range(3):
        blocks.extend([
            TimeBlock(id=f"am{day}", title="AM", kind="locked", days=[day],
                      start="06:00", duration_min=510),
            TimeBlock(id=f"pm{day}", title="PM", kind="locked", days=[day],
                      start="18:30", duration_min=270),
        ])
    cases = [
        ("t0", 150, [0], 4, "medium"), ("t1", 30, [0], 2, "low"),
        ("t2", 60, [0, 1, 2], 1, "medium"), ("t3", 120, [1], 4, "low"),
        ("t4", 30, [1], 3, "low"), ("t5", 90, [0, 1, 2], 3, "high"),
        ("t6", 90, [1, 2], 4, "low"), ("t7", 30, [2], 3, "high"),
        ("t8", 30, [0, 1, 2], 4, "high"), ("t9", 90, [0, 1, 2], 2, "low"),
    ]
    blocks.extend(
        TimeBlock(
            id=block_id,
            title=block_id,
            kind="flexible",
            days=days,
            duration_min=duration,
            priority=priority,  # type: ignore[arg-type]
            energy=energy,  # type: ignore[arg-type]
            latest="Wednesday 18:30",
        )
        for block_id, duration, days, priority, energy in cases
    )
    trace = solve(blocks)
    assert trace.complete is True
    assert {block.id for block in trace.placed if block.kind == "flexible"} == {
        f"t{i}" for i in range(10)
    }
    assert trace.solve_ms < 150
