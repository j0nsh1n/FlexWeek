"""What the reuse wrapper still decides in Python: `row_conflict` finds the row's own place in the
preview rows by object identity before asking the engine, so a row never conflicts with itself."""

from __future__ import annotations

from desktop.native.reuse import (
    move_earlier_homework,
    open_rest_sessions,
    proposals_from_clipboard,
    row_conflict,
    time_still_needed,
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


def test_remaining_time_wrappers_call_the_engine_and_return_decoded_values() -> None:
    assignment = {
        "id": "history",
        "title": "History",
        "due": "2026-10-14T23:59",
        "unplanned_min": 45,
        "estimate_min": 60,
    }
    blocks = open_rest_sessions([], {"history": assignment}, "2026-10-05")
    assert blocks[0]["duration_min"] == 45
    assert time_still_needed({"history": assignment}, blocks, "2026-10-05") == [
        {
            "assignment_id": "history",
            "title": "History",
            "minutes": 45,
            "period": "later",
        }
    ]


def test_earlier_homework_wrapper_returns_both_weeks_for_one_save() -> None:
    source = {
        "id": "session",
        "title": "History",
        "kind": "flexible",
        "assignment_id": "history",
        "duration_min": 60,
        "days": [0, 1, 2, 3, 4, 5, 6],
    }
    assignment = {"id": "history", "title": "History", "due": "2026-10-21T23:59"}
    blocks, moved, updates = move_earlier_homework(
        [],
        [{"week_start": "2026-10-05", "revision": 3, "blocks": [source]}],
        {"history": assignment},
        "2026-10-12",
    )
    assert blocks[0]["id"] == "session"
    assert blocks[0]["duration_min"] == 60
    assert moved[0]["duration_min"] == 60
    assert updates[0]["before"] == [source]
    assert updates[0]["after"] == []
