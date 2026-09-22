"""Clipboard, collision and unfinished helpers. Expected values match Stage 3."""

from __future__ import annotations

from datetime import datetime

from backend.slots import SLOT_MIN
from desktop.native.calendar import days_through, due_day_in_week, first_plannable_day
from desktop.native.reuse import (
    MAX_WEEK_BLOCKS,
    apply_plan,
    available_homework_minutes,
    capacity_problem,
    clipboard_fingerprint,
    copied_fixed_block,
    copied_homework_block,
    late_locked_line,
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
    settle_placements,
    solve_request,
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
    dirty = running_late_refusal(
        week_start="2026-09-14", now=now, dirty=True, conflict=False, block_count=0
    )
    assert dirty == "Your last change is still saving. Try again in a moment."
    conflict = running_late_refusal(
        week_start="2026-09-14", now=now, dirty=False, conflict=True, block_count=0
    )
    assert conflict == "This week was changed somewhere else. Reload it first."


def test_late_locked_line_names_the_interval_and_what_moved() -> None:
    block = running_late_block(0, "19:00", 30, "b-late-1")
    assert late_locked_line(block, 2) == "Running late: 19:00–19:30 is now locked. 2 moved."
    assert late_locked_line(block, 0) == "Running late: 19:00–19:30 is now locked. Nothing had to move."


def test_restore_point_labels_fit_eighty_characters() -> None:
    label = restore_point_label("Before applying " + ("A" * 80) + " to 2026-09-14")
    assert len(label) == 80
    assert label.endswith("…")


def test_clipboard_fingerprint_ignores_group_ids() -> None:
    left = [{"block": soccer(), "source_day": 0, "scope": "occurrence", "group_id": "a"}]
    right = [{"block": soccer(), "source_day": 0, "scope": "occurrence", "group_id": "b"}]
    assert clipboard_fingerprint(left) == clipboard_fingerprint(right)
    assert SLOT_MIN == 15


def test_apply_plan_writes_solver_starts_onto_the_week() -> None:
    blocks = [
        {"id": "essay", "title": "Essay", "kind": "flexible", "days": [0, 1, 2], "duration_min": 60},
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "days": [0],
            "start": "08:00",
            "duration_min": 390,
        },
    ]
    trace = {
        "placed": [
            {
                "id": "essay",
                "title": "Essay",
                "kind": "flexible",
                "days": [1],
                "start": "16:00",
                "duration_min": 60,
            },
            {
                "id": "school",
                "title": "School",
                "kind": "locked",
                "days": [0],
                "start": "08:00",
                "duration_min": 390,
            },
        ],
        "unplaced": [],
    }
    essay = next(item for item in apply_plan(blocks, trace) if item["id"] == "essay")
    assert essay["start"] == "16:00"
    assert essay["days"] == [1]


def test_apply_plan_clears_a_start_the_solver_could_not_keep() -> None:
    blocks = [{"id": "essay", "kind": "flexible", "days": [0], "start": "16:00", "duration_min": 60}]
    out = apply_plan(blocks, {"placed": [], "unplaced": [{"id": "essay"}]})
    assert "start" not in out[0]


# A planned week to change: school Monday to Friday until 15:15, Math and English after it on
# Monday, Reading on Saturday. The week of 2026-09-28 starts on a Monday.
PLAN_WEEK = "2026-09-28"
PLAN_HOMEWORK = {
    "math": {"id": "math", "title": "Math worksheet", "due": "2026-09-28T21:00"},
    "eng": {"id": "eng", "title": "English essay", "due": "2026-09-29T21:00"},
    "read": {"id": "read", "title": "Reading", "due": "2026-10-04T21:00"},
}


def planned_week() -> list[dict]:
    def session(block_id: str, title: str, minutes: int, day: int, start: str) -> dict:
        return {
            "id": "s-" + block_id,
            "title": title,
            "kind": "flexible",
            "duration_min": minutes,
            "days": [day],
            "start": start,
            "assignment_id": block_id,
        }

    school = {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "duration_min": 435,
        "days": [0, 1, 2, 3, 4],
        "start": "08:00",
    }
    return [
        school,
        session("math", "Math worksheet", 30, 0, "15:15"),
        session("eng", "English essay", 90, 0, "15:45"),
        session("read", "Reading", 60, 5, "12:00"),
    ]


def game(start: str) -> dict:
    return {"id": "game", "title": "Game", "kind": "locked", "duration_min": 120, "days": [5], "start": start}


def times(blocks: list[dict]) -> dict[str, tuple[list[int], str | None]]:
    return {block["id"]: (block["days"], block.get("start")) for block in blocks}


def test_a_saturday_event_elsewhere_moves_no_homework() -> None:
    week = [*planned_week(), game("15:00")]
    settled, lost = settle_placements(week, PLAN_HOMEWORK, PLAN_WEEK)
    assert lost == []
    assert times(settled) == times(week)


def test_a_saturday_event_over_reading_takes_only_readings_time() -> None:
    settled, lost = settle_placements([*planned_week(), game("11:30")], PLAN_HOMEWORK, PLAN_WEEK)
    assert [note["message"] for note in lost] == [
        "Reading no longer fits Saturday at 12:00: Game is there now."
    ]
    after = times(settled)
    # Every day up to Sunday's deadline is open to it again; Monday's homework has not moved.
    assert after["s-read"] == ([0, 1, 2, 3, 4, 5, 6], None)
    assert after["s-math"] == ([0], "15:15")
    assert after["s-eng"] == ([0], "15:45")


def test_a_deadline_moved_earlier_takes_the_time_away_and_says_why() -> None:
    homework = {**PLAN_HOMEWORK, "eng": {**PLAN_HOMEWORK["eng"], "due": "2026-09-28T16:00"}}
    settled, lost = settle_placements(planned_week(), homework, PLAN_WEEK)
    assert [note["message"] for note in lost] == [
        "English essay no longer fits Monday at 15:45: that is after it is due."
    ]
    assert times(settled)["s-eng"] == ([0], None)
    assert times(settled)["s-math"] == ([0], "15:15")


def test_homework_moved_onto_other_homework_pushes_the_other_one_out() -> None:
    week = planned_week()
    week[1] = {**week[1], "start": "16:00"}
    settled, lost = settle_placements(week, PLAN_HOMEWORK, PLAN_WEEK, keep={"s-math"})
    assert [note["message"] for note in lost] == [
        "English essay no longer fits Monday at 15:45: Math worksheet is there now."
    ]
    assert times(settled)["s-math"] == ([0], "16:00")


def test_a_missed_school_day_frees_time_rather_than_taking_any() -> None:
    week = planned_week()
    week[0] = {**week[0], "missed_days": [0]}
    week[1] = {**week[1], "start": "09:00"}
    _settled, lost = settle_placements(week, PLAN_HOMEWORK, PLAN_WEEK)
    assert lost == []


def test_planning_holds_planned_homework_in_place_and_places_the_rest() -> None:
    week = planned_week()
    week[3] = {**week[3], "days": [5, 6]}
    week[3].pop("start")
    payload, targets = solve_request(week, PLAN_HOMEWORK, PLAN_WEEK)
    assert targets == {"s-read"}
    held = {block["id"]: block for block in payload}
    assert held["s-math"] == {
        "id": "s-math",
        "title": "Math worksheet",
        "kind": "locked",
        "duration_min": 30,
        "days": [0],
        "start": "15:15",
    }
    assert held["s-read"]["kind"] == "flexible"
    assert held["s-read"]["days"] == [5, 6]


def test_replanning_everything_reopens_every_day_up_to_each_deadline() -> None:
    payload, targets = solve_request(planned_week(), PLAN_HOMEWORK, PLAN_WEEK, everything=True)
    assert targets == {"s-math", "s-eng", "s-read"}
    sent = {block["id"]: block for block in payload}
    english = sent["s-eng"]
    assert (english["kind"], english["days"], "start" in english) == ("flexible", [0, 1], False)
    assert sent["s-math"]["days"] == [0]


def test_finding_a_new_time_places_only_the_named_work() -> None:
    week = planned_week()
    week.append({"id": "s-new", "title": "Lab report", "kind": "flexible", "duration_min": 60, "days": [2]})
    payload, targets = solve_request(week, PLAN_HOMEWORK, PLAN_WEEK, only={"s-eng"})
    assert targets == {"s-eng"}
    sent = {block["id"]: block for block in payload}
    assert "s-new" not in sent
    assert sent["s-math"]["kind"] == "locked"


def test_a_plan_for_part_of_the_week_changes_only_that_part() -> None:
    trace = {
        "placed": [{"id": "s-eng", "kind": "flexible", "days": [1], "start": "15:15"}],
        "unplaced": [{"id": "s-read"}],
    }
    out = apply_plan(
        planned_week(), trace, targets={"s-eng", "s-read"}, assignments=PLAN_HOMEWORK, week_start=PLAN_WEEK
    )
    assert times(out)["s-eng"] == ([1], "15:15")
    assert times(out)["s-read"] == ([0, 1, 2, 3, 4, 5, 6], None)
    assert times(out)["s-math"] == ([0], "15:15")


def test_a_plan_never_rewrites_a_fixed_block() -> None:
    """The solver lists a fixed block with its missed days left out. Copying that list back made
    Monday a missed day of a block that no longer ran on Monday, and the week stopped saving."""
    school = {**planned_week()[0], "missed_days": [0]}
    trace = {"placed": [{**school, "days": [1, 2, 3, 4], "missed_days": []}], "unplaced": []}
    assert apply_plan([school], trace) == [school]
