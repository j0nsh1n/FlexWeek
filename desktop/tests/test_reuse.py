"""Clipboard, collision and unfinished helpers. Expected values match Stage 3."""

from __future__ import annotations

from datetime import datetime

from backend.slots import SLOT_MIN
from desktop.native.calendar import days_through, due_day_in_week, first_plannable_day
from desktop.native.reuse import (
    MAX_WEEK_BLOCKS,
    available_homework_minutes,
    capacity_problem,
    clipboard_fingerprint,
    copied_fixed_block,
    copied_homework_block,
    merge_preview_rows,
    occurrence_days,
    proposals_from_clipboard,
    restore_point_label,
    routine_rows,
    routine_source_blocks,
    routine_template,
    row_conflict,
    running_late_block,
    running_late_refusal,
    unfinished_items,
)


def soccer() -> dict:
    return {
        "id": "soccer",
        "title": "Soccer",
        "kind": "locked",
        "duration_min": 60,
        "days": [0, 2],
        "start": "16:00",
        "category": "exercise",
    }


def essay() -> dict:
    return {
        "id": "essay",
        "title": "Essay",
        "estimate_min": 90,
        "focus_minutes": 0,
        "unplanned_min": 90,
        "completed": False,
        "due": "2026-09-11T21:00",
    }


def test_completed_flexible_pins_to_completed_day_only() -> None:
    done = {
        "id": "sess",
        "kind": "flexible",
        "days": [1, 3],
        "completed": True,
        "completed_day": 3,
        "start": "16:00",
    }
    assert occurrence_days(done) == [3]
    open_work = {**done, "completed": False, "completed_day": None}
    assert occurrence_days(open_work) == [1, 3]
    unpinned = {**done, "completed_day": None}
    assert occurrence_days(unpinned) == []


def test_copied_fixed_block_drops_homework_and_timer_state() -> None:
    source = {
        **soccer(),
        "assignment_id": "essay",
        "completed": True,
        "missed_days": [0],
        "focus_minutes": 15,
        "pomodoro_role": "work",
    }
    copy = copied_fixed_block(source, [1], "copy-1")
    assert copy["id"] == "copy-1"
    assert copy["kind"] == "locked"
    assert copy["days"] == [1]
    assert copy["completed"] is False
    assert copy["missed_days"] == []
    assert copy["focus_minutes"] == 0
    assert "assignment_id" not in copy
    assert "pomodoro_role" not in copy


def test_homework_paste_keeps_assignment_identity_and_shares_remaining_time() -> None:
    assignment = essay()
    session = {
        "id": "sess",
        "assignment_id": "essay",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [1],
    }
    items = [
        {"block": session, "source_day": 1, "scope": "occurrence", "group_id": "g1"},
        {"block": session, "source_day": 1, "scope": "occurrence", "group_id": "g2"},
    ]
    rows = proposals_from_clipboard(
        items,
        kind="day",
        week_start="2026-09-07",
        target_day=3,
        target_start=None,
        assignments={"essay": assignment},
        available={"essay": 90},
    )
    assert rows[0]["checked"] is True
    assert rows[0]["block"]["assignment_id"] == "essay"
    assert rows[0]["block"]["duration_min"] == 60
    assert rows[0]["block"]["kind"] == "flexible"
    assert rows[0]["block"].get("start") in {None, ""}
    assert rows[1]["checked"] is True
    assert rows[1]["block"]["duration_min"] == 30


def test_a_second_homework_paste_is_invalid_when_nothing_remains() -> None:
    assignment = essay()
    session = {
        "id": "sess",
        "assignment_id": "essay",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 90,
        "days": [1],
    }
    items = [
        {"block": session, "source_day": 1, "scope": "occurrence", "group_id": "g1"},
        {"block": session, "source_day": 1, "scope": "occurrence", "group_id": "g2"},
    ]
    rows = proposals_from_clipboard(
        items,
        kind="block",
        week_start="2026-09-07",
        target_day=2,
        target_start=None,
        assignments={"essay": assignment},
        available={"essay": 90},
    )
    assert rows[1]["checked"] is False
    assert rows[1]["invalid"] == "No unplanned time remains for this homework."


def test_paste_of_a_fixed_block_onto_the_same_slot_conflicts() -> None:
    source = soccer()
    items = [{"block": source, "source_day": 0, "scope": "occurrence", "group_id": "g1"}]
    rows = proposals_from_clipboard(
        items,
        kind="block",
        week_start="2026-09-07",
        target_day=0,
        target_start="16:00",
        assignments={},
        available={},
    )
    assert row_conflict(rows[0], rows, [source]) == "Soccer"
    rows[0]["block"]["start"] = "18:00"
    assert row_conflict(rows[0], rows, [source]) is None


def test_adjacent_blocks_do_not_conflict() -> None:
    existing = [soccer()]
    row = {
        "week_start": "2026-09-07",
        "day": 0,
        "fixed": True,
        "checked": True,
        "block": {"title": "Piano", "start": "17:00", "duration_min": 30, "days": [0]},
    }
    assert row_conflict(row, [row], existing) is None


def test_capacity_problem_uses_merged_block_count() -> None:
    rows = proposals_from_clipboard(
        [{"block": soccer(), "source_day": 0, "scope": "series", "group_id": "g1"}],
        kind="block",
        week_start="2026-09-07",
        target_day=1,
        target_start=None,
        assignments={},
        available={},
    )
    groups = merge_preview_rows(rows, "00000000-0000-4000-8000-000000000001")
    assert len(groups) == 1
    assert groups[0]["block"]["days"] == [0, 2]
    assert groups[0]["block"]["id"].startswith("b-stage3-")
    assert capacity_problem(100, 1, "This week")
    assert not capacity_problem(99, 1, "This week")
    assert MAX_WEEK_BLOCKS == 100


def test_available_minutes_follow_dirty_sessions_on_the_open_week() -> None:
    assignment = essay()
    assert available_homework_minutes(assignment, [], []) == 90
    assignment["unplanned_min"] = 60
    committed = [copied_homework_block(assignment, 1, 30, "here")]
    assert available_homework_minutes(assignment, committed, committed) == 60
    draft = committed + [copied_homework_block(assignment, 2, 30, "extra")]
    assert available_homework_minutes(assignment, draft, committed) == 30


def test_unfinished_needs_an_earlier_saved_week_and_a_slot_of_remaining_time() -> None:
    assignment = essay()
    items = unfinished_items({"essay": assignment}, ["2026-08-31"], "2026-09-07", [], [])
    assert items[0]["id"] == "essay"
    assert items[0]["remaining_min"] == 90
    assert unfinished_items({"essay": assignment}, ["2026-09-07"], "2026-09-07", [], []) == []
    assignment["unplanned_min"] = 10
    assert unfinished_items({"essay": assignment}, ["2026-08-31"], "2026-09-07", [], []) == []


def test_days_through_due_matches_the_web_planner() -> None:
    assert due_day_in_week("2026-09-11T08:10", "2026-09-07") == 4
    assert days_through(4, 2) == [2, 3, 4]
    assert days_through(1, 3) == [1]
    assert first_plannable_day("2026-09-07") in range(7)


def test_routines_are_locked_times_without_homework_or_pomodoro() -> None:
    blocks = [
        soccer(),
        copied_homework_block(essay(), 1, 60, "hw"),
        {**soccer(), "id": "chunk", "pomodoro_role": "work"},
    ]
    sources = routine_source_blocks(blocks)
    assert [block["id"] for block in sources] == ["soccer"]
    template = routine_template(soccer(), "t1")
    assert template["template_id"] == "t1"
    assert "assignment_id" not in template
    routine = {"name": "Sports", "blocks": [template]}
    rows = routine_rows(routine, "2026-09-14", [0, 1, 2, 3, 4])
    assert [row["day"] for row in rows] == [0, 2]
    assert all(row["fixed"] for row in rows)


def test_running_late_occupies_from_a_snapped_start_until_the_day_end() -> None:
    block = running_late_block(0, "22:30", 60, "b-late-1")
    assert block["title"] == "Running late"
    assert block["kind"] == "locked"
    assert block["start"] == "22:30"
    assert block["duration_min"] == 30
    assert block["category"] == "downtime"
    now = datetime(2026, 9, 14, 14, 7)
    assert (
        running_late_refusal(week_start="2026-09-14", now=now, dirty=False, conflict=False, block_count=0)
        is None
    )
    assert (
        "this week"
        in (
            running_late_refusal(week_start="2026-09-07", now=now, dirty=False, conflict=False, block_count=0)
            or ""
        ).lower()
    )
    assert running_late_refusal(week_start="2026-09-14", now=now, dirty=True, conflict=False, block_count=0)


def test_restore_point_labels_fit_eighty_characters() -> None:
    label = restore_point_label("Before applying " + ("A" * 80) + " to 2026-09-14")
    assert len(label) == 80
    assert label.endswith("…")


def test_clipboard_fingerprint_ignores_group_ids() -> None:
    left = [{"block": soccer(), "source_day": 0, "scope": "occurrence", "group_id": "a"}]
    right = [{"block": soccer(), "source_day": 0, "scope": "occurrence", "group_id": "b"}]
    assert clipboard_fingerprint(left) == clipboard_fingerprint(right)
    assert SLOT_MIN == 15
