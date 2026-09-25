"""Grid math for the native calendar. Expected values match the web calendar tests."""

from __future__ import annotations

from desktop.native.calendar import (
    apply_block_edit,
    apply_block_times,
    create_click_range,
    days_through,
    due_day_in_week,
    due_soon_for,
    is_series,
    span_clash,
    span_problem,
    split_occurrence,
    sunday_due,
)
from desktop.native.reuse import due_point


def test_a_click_makes_up_to_an_hour_and_stops_at_the_next_block() -> None:
    assert create_click_range(900, [(930, 960)]) == (900, 930)
    assert create_click_range(900, []) == (900, 960)
    assert create_click_range(1425, [(1430, 1440)]) == (1425, 1430)
    assert create_click_range(1430, [(1430, 1440)]) is None


def test_a_repeating_locked_block_cannot_be_retimed_from_one_day() -> None:
    school = {
        "id": "school",
        "kind": "locked",
        "title": "School",
        "duration_min": 60,
        "days": [0, 1, 2],
        "start": "10:00",
    }
    assert is_series(school)
    assert apply_block_times(school, 630, 705) is None


def test_a_one_day_block_can_still_be_moved_and_resized() -> None:
    school = {
        "id": "school",
        "kind": "locked",
        "title": "School",
        "duration_min": 60,
        "days": [0],
        "start": "10:00",
    }
    moved = apply_block_times(school, 630, 705)
    assert moved is not None
    assert moved["start"] == "10:30"
    assert moved["duration_min"] == 75
    assert moved["days"] == [0]


def test_a_flexible_task_with_several_candidate_days_is_not_a_series() -> None:
    essay = {
        "id": "essay",
        "kind": "flexible",
        "title": "Essay",
        "duration_min": 60,
        "days": [1, 3],
        "start": "10:00",
    }
    assert not is_series(essay)
    moved = apply_block_times(essay, 630, 690)
    assert moved is not None
    assert moved["start"] == "10:30"
    assert moved["days"] == [1, 3]


def test_editing_one_occurrence_splits_a_new_one_day_block() -> None:
    school = {
        "id": "school",
        "kind": "locked",
        "title": "School",
        "duration_min": 60,
        "days": [0, 1, 2],
        "start": "10:00",
    }
    edited = dict(school)
    edited["start"] = "11:00"
    result = apply_block_edit([school], edited, scope="occurrence", day=1)
    days = {tuple(block["days"]): block["start"] for block in result}
    assert days[(0, 2)] == "10:00"
    assert days[(1,)] == "11:00"
    assert len({block["id"] for block in result}) == 2


def test_split_occurrence_leaves_a_single_day_block_alone() -> None:
    block = {
        "id": "once",
        "kind": "locked",
        "title": "Piano",
        "duration_min": 60,
        "days": [1],
        "start": "17:00",
    }
    result, new_id = split_occurrence([block], "once", 1)
    assert new_id is None
    assert result[0]["days"] == [1]


def test_homework_dragged_on_a_day_is_due_at_the_end_of_that_week() -> None:
    assert sunday_due("2026-09-07") == "2026-09-13T23:59"


def test_days_through_a_due_date_start_at_the_first_plannable_day() -> None:
    assert due_day_in_week("2026-09-11T08:10", "2026-09-07") == 4
    assert days_through(4, 2) == [2, 3, 4]
    assert days_through(1, 3) == [1]


def test_a_time_on_another_block_is_allowed_and_named_but_not_outside_the_day_or_past_due() -> None:
    """As in Daily Scheduler: two blocks may share a time. What cannot stand is time FlexWeek does not
    plan in, and homework ending after it is due."""
    school = {"id": "school", "title": "School", "start": "08:00", "duration_min": 390, "days": [0, 1, 2]}
    missed = {
        **school,
        "id": "club",
        "title": "Club",
        "start": "16:00",
        "duration_min": 60,
        "missed_days": [1],
    }
    done = {
        **school,
        "id": "done",
        "title": "Done work",
        "start": "17:00",
        "days": [1, 2],
        "completed": True,
        "completed_day": 2,
    }
    blocks = [school, missed, done]
    assert span_problem(blocks, "essay", 1, 10 * 60, 11 * 60, None) is None
    assert span_clash(blocks, "essay", 1, 10 * 60, 11 * 60) == "School"
    assert span_clash(blocks, "school", 1, 10 * 60, 11 * 60) is None, "never beside itself"
    assert span_clash(blocks, "essay", 1, 14 * 60 + 30, 15 * 60) is None, "touching is not sharing"
    assert span_clash(blocks, "essay", 1, 16 * 60, 17 * 60) is None, "not on a day it was missed"
    assert span_clash(blocks, "essay", 1, 17 * 60, 18 * 60) is None, (
        "finished work sits on the day it was done"
    )
    assert span_clash(blocks, "essay", 2, 17 * 60, 18 * 60) == "Done work"
    assert span_problem(blocks, "essay", 1, 3 * 60, 4 * 60, None) is None
    assert span_problem(blocks, "essay", 1, 22 * 60 + 30, 23 * 60 + 30, None) is None
    assert span_problem(blocks, "essay", 1, 23 * 60 + 30, 24 * 60 + 30, None) == (
        "That is outside the hours FlexWeek plans in, so it stayed where it was."
    )
    assert span_problem(blocks, "essay", 3, 19 * 60, 20 * 60, (3, 19 * 60 + 30)) == (
        "That ends after it is due, so it stayed where it was."
    )
    assert span_problem(blocks, "essay", 3, 18 * 60, 19 * 60 + 30, (3, 19 * 60 + 30)) is None


def test_due_point_and_span_problem_cover_date_only_and_timed_dues() -> None:
    week = "2026-09-14"
    date_only = due_point("2026-09-15", week)
    legacy = due_point("2026-09-15T23:59", week)
    timed = due_point("2026-09-15T09:00", week)
    assert date_only == (1, 24 * 60)
    assert legacy == (1, 24 * 60)
    assert timed == (1, 9 * 60)
    assert due_day_in_week("2026-09-15", week) == 1
    after_due = "That ends after it is due, so it stayed where it was."
    assert span_problem([], "essay", 1, 23 * 60, 23 * 60 + 45, date_only) is None
    assert span_problem([], "essay", 1, 23 * 60, 23 * 60 + 45, legacy) is None
    assert span_problem([], "essay", 1, 9 * 60, 9 * 60 + 15, timed) == after_due
    assert span_problem([], "essay", 1, 8 * 60, 9 * 60, timed) is None
    ordered = due_soon_for(
        "2026-09-15",
        {
            "allday": {"id": "allday", "title": "All day", "due": "2026-09-15", "completed": False},
            "morning": {"id": "morning", "title": "Morning", "due": "2026-09-15T09:00", "completed": False},
        },
    )
    assert [item["id"] for item in ordered] == ["morning", "allday"]
