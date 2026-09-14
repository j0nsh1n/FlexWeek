"""Stage 4 occupancy, running-late reshape, spread and cluster copy."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.availability import occupancy_from_windows, spread_sessions
from backend.models import Assignment, GridWindow, ProtectedWindow, TimeBlock
from backend.slots import hhmm_to_minutes
from backend.solver import SOLVE_BUDGET_MS, reschedule_running_late, solve

CLUSTER_MESSAGE = (
    "Several tasks are short on time. Shorten a session, pick another day, "
    "or free some protected hours. Work that cannot fit stays unplaced."
)
LATE_MESSAGE = "Moved after you ran late so the rest of the day still fits."


def _locked(block_id: str, start: str, duration_min: int, days: list[int]) -> TimeBlock:
    return TimeBlock(
        id=block_id,
        title=block_id,
        kind="locked",
        duration_min=duration_min,
        days=days,
        start=start,
        priority=1,
        energy="medium",
    )


def _flex(
    block_id: str,
    duration_min: int,
    days: list[int],
    *,
    priority: int = 3,
    energy: str = "medium",
    latest: str | None = None,
    start: str | None = None,
) -> TimeBlock:
    return TimeBlock(
        id=block_id,
        title=block_id,
        kind="flexible",
        duration_min=duration_min,
        days=days,
        priority=priority,  # type: ignore[arg-type]
        energy=energy,  # type: ignore[arg-type]
        latest=latest,
        start=start,
    )


def test_protected_hours_leave_locked_blocks_and_unplace_overflow() -> None:
    wind = _locked("wind", "07:00", 960, [0])
    homework = _flex("hw", 60, [0], energy="high")
    open_trace = solve([wind, homework])
    assert {block.id: block.start for block in open_trace.placed}["hw"] == "06:00"
    occ = occupancy_from_windows(
        [ProtectedWindow(kind="downtime", days=[0], start="06:00", duration_min=60)],
        None,
    )
    trace = solve([wind, homework], extra_occ=occ)
    placed = {block.id: block for block in trace.placed}
    assert placed["wind"].start == "07:00"
    assert placed["wind"].days == [0]
    assert [block.id for block in trace.unplaced] == ["hw"]
    assert trace.complete is False


def test_running_late_keeps_sleep_and_reports_overflow_unplaced() -> None:
    wind = _locked("wind", "07:00", 960, [0])
    sleep = _locked("sleep", "22:00", 60, [0, 1, 2, 3, 4, 5, 6])
    homework = _flex("hw", 60, [0], energy="high")
    before = solve([wind, sleep, homework])
    placed = {block.id: block for block in before.placed}
    assert placed["hw"].start == "06:00"
    after = reschedule_running_late([wind, sleep, homework], 0, 60, "06:00", before.placed)
    kept = {block.id: block for block in after.placed}
    assert kept["wind"].start == "07:00"
    assert kept["sleep"].start == "22:00"
    assert kept["sleep"].days == [0, 1, 2, 3, 4, 5, 6]
    assert [block.id for block in after.unplaced] == ["hw"]
    assert "hw" in {block.id for block in after.unplaced}
    assert after.complete is False


def test_running_late_move_uses_late_copy_not_the_missed_class_sentence() -> None:
    school = _locked("school", "08:00", 390, [0])
    homework = _flex("hw", 60, [0, 1], energy="high")
    before = solve([school, homework])
    placed = {block.id: block for block in before.placed}
    assert placed["hw"].days == [0]
    assert placed["hw"].start == "06:00"
    after = reschedule_running_late([school, homework], 0, 30, "06:00", before.placed)
    moved = {block.id: block for block in after.placed}
    assert moved["school"].start == "08:00"
    assert moved["hw"].days == [0]
    assert moved["hw"].start == "06:30"
    explanation = next(
        item for item in after.explanations if item.block_id == "hw" and item.reason == "RESHUFFLE_AFTER_MISS"
    )
    assert explanation.message == LATE_MESSAGE


def test_packed_fixture_stays_under_budget_with_protected_hours() -> None:
    blocks = [
        _locked("school", "08:00", 390, [0, 1, 2, 3, 4]),
        _locked("sleep", "22:00", 60, [0, 1, 2, 3, 4, 5, 6]),
    ]
    for i in range(12):
        blocks.append(_flex(f"t{i}", 45, [0, 1, 2, 3, 4, 5, 6], latest="Sunday 21:00"))
    occ = occupancy_from_windows(
        [ProtectedWindow(kind="meal", days=[0, 1, 2, 3, 4, 5, 6], start="18:00", duration_min=60)],
        "21:00",
    )
    windows = [GridWindow(days=[0, 1, 2, 3, 4], start="15:00", duration_min=120)]
    trace = solve(blocks, extra_occ=occ, study_windows=windows)
    assert trace.solve_ms < SOLVE_BUDGET_MS


def test_spread_chunks_remaining_minutes_before_the_due_date() -> None:
    sessions, remaining = spread_sessions(
        estimate_min=120,
        focus_minutes=0,
        planned_min=0,
        due="2026-09-15T23:59",
        session_min=60,
        from_date="2026-09-14",
    )
    assert remaining == 0
    assert sessions == [
        {"week_start": "2026-09-14", "date": "2026-09-14", "days": [0], "duration_min": 60},
        {"week_start": "2026-09-14", "date": "2026-09-15", "days": [1], "duration_min": 60},
    ]


def test_spread_keeps_unplaced_remaining_when_the_start_is_after_the_due_date() -> None:
    sessions, remaining = spread_sessions(
        estimate_min=90,
        focus_minutes=0,
        planned_min=0,
        due="2026-09-15T23:59",
        session_min=45,
        from_date="2026-09-16",
    )
    assert sessions == []
    assert remaining == 90


def test_spread_snaps_a_focus_remainder_down_to_the_grid() -> None:
    sessions, remaining = spread_sessions(
        estimate_min=120,
        focus_minutes=7,
        planned_min=0,
        due="2026-09-15T23:59",
        session_min=60,
        from_date="2026-09-14",
    )
    # 113 unplanned minutes place 105 on the grid; 8 minutes cannot fit a slot.
    assert remaining == 8
    assert [item["duration_min"] for item in sessions] == [60, 45]


def test_spread_reports_a_remainder_that_fits_no_grid_session() -> None:
    sessions, remaining = spread_sessions(
        estimate_min=60,
        focus_minutes=53,
        planned_min=0,
        due="2026-09-15T23:59",
        session_min=60,
        from_date="2026-09-14",
    )
    assert sessions == []
    assert remaining == 7


def test_study_windows_are_preferred_before_energy() -> None:
    homework = _flex("hw", 60, [0], energy="high")
    windows = [GridWindow(days=[0], start="18:00", duration_min=120)]
    trace = solve([homework], study_windows=windows)
    placed = {block.id: block for block in trace.placed}["hw"]
    assert placed.start == "18:00"
    assert hhmm_to_minutes(placed.start) >= 18 * 60


def test_a_short_study_window_does_not_claim_a_longer_session() -> None:
    homework = _flex("hw", 60, [0], energy="high")
    windows = [GridWindow(days=[0], start="21:00", duration_min=30)]
    trace = solve([homework], study_windows=windows)
    placed = {block.id: block for block in trace.placed}["hw"]
    # A 60-minute session cannot fit a 30-minute window, so the energy-matched
    # morning slot keeps its usual first place.
    assert placed.start == "06:00"


def test_cutoff_occupancy_blocks_starts_that_would_finish_after_it() -> None:
    homework = _flex("hw", 60, [0], energy="high")
    occ = occupancy_from_windows([], "06:15")
    trace = solve([homework], extra_occ=occ)
    assert [block.id for block in trace.unplaced] == ["hw"]


def test_cluster_explanation_only_when_two_tasks_are_in_trouble() -> None:
    wind = _locked("wind", "08:00", 900, [0])
    one = _flex("one", 360, [0], latest="Monday 23:00")
    two = _flex("two", 360, [0], latest="Monday 23:00")
    crowded = solve([wind, one, two])
    cluster = [item for item in crowded.explanations if item.message == CLUSTER_MESSAGE]
    assert len(cluster) == 1
    assert cluster[0].reason is None
    assert cluster[0].block_id in {"one", "two"}
    lonely = solve([wind, one])
    assert CLUSTER_MESSAGE not in {item.message for item in lonely.explanations}


def test_assignment_notes_links_and_checklist_round_trip_and_omit_empties() -> None:
    empty = Assignment.model_validate(
        {
            "id": "hw-essay",
            "title": "Essay",
            "due": "2026-09-15T23:59",
            "estimate_min": 120,
            "revision": 0,
        }
    )
    dumped = empty.model_dump()
    assert "notes" not in dumped
    assert "links" not in dumped
    assert "checklist" not in dumped
    filled = Assignment.model_validate(
        {
            "id": "hw-essay",
            "title": "Essay",
            "due": "2026-09-15T23:59",
            "estimate_min": 120,
            "revision": 1,
            "notes": "Use the primary sources from week 3.",
            "links": [{"label": "Prompt", "url": "https://example.edu/prompt"}],
            "checklist": [{"id": "outline", "text": "Outline", "done": False}],
        }
    )
    assert filled.model_dump()["notes"] == "Use the primary sources from week 3."
    assert filled.model_dump()["links"] == [{"label": "Prompt", "url": "https://example.edu/prompt"}]
    assert filled.model_dump()["checklist"] == [{"id": "outline", "text": "Outline", "done": False}]


def test_assignment_rejects_javascript_urls_and_duplicate_checklist_ids() -> None:
    base = {
        "id": "hw-essay",
        "title": "Essay",
        "due": "2026-09-15T23:59",
        "estimate_min": 120,
        "revision": 0,
    }
    with pytest.raises(ValidationError):
        Assignment.model_validate({**base, "links": [{"label": "Bad", "url": "javascript:alert(1)"}]})
    with pytest.raises(ValidationError):
        Assignment.model_validate(
            {
                **base,
                "checklist": [
                    {"id": "one", "text": "First"},
                    {"id": "one", "text": "Again"},
                ],
            }
        )
