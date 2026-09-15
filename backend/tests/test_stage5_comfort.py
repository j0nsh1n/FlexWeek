"""Stage 5 timer rounding, presets and reminder-limit copy."""

from __future__ import annotations

from backend.comfort import preview_split, snap_minutes, split_plan


def test_snap_sends_25_to_30_and_5_to_15() -> None:
    assert snap_minutes(25, 1, 180) == 30
    assert snap_minutes(5, 1, 60) == 15
    assert snap_minutes(1, 1, 180) == 15
    assert snap_minutes(30, 1, 180) == 30


def test_split_plan_matches_a_90_minute_task_after_grid_snap() -> None:
    plan = split_plan(90, 30, 15, 15, 4)
    assert plan == {
        "segments": [
            {"role": "work", "duration_min": 30, "index": 1},
            {"role": "break", "duration_min": 15, "index": 1},
            {"role": "work", "duration_min": 30, "index": 2},
            {"role": "break", "duration_min": 15, "index": 2},
            {"role": "work", "duration_min": 30, "index": 3},
        ],
        "total_min": 120,
    }


def test_preview_reports_each_rounded_length() -> None:
    body = preview_split(
        duration_min=90,
        timer_work_min=25,
        timer_break_min=5,
        timer_long_break_min=15,
        timer_long_break_every=4,
    )
    assert body["timer_work_min"] == 30
    assert body["timer_break_min"] == 15
    assert body["timer_long_break_min"] == 15
    assert body["rounded"] is True
    assert body["message"] == (
        "Work length 25 minutes becomes 30 on the 15-minute grid. "
        "Break length 5 minutes becomes 15 on the 15-minute grid."
    )
    assert body["total_min"] == 120
    segments = body["segments"]
    assert isinstance(segments, list)
    assert segments[0] == {"role": "work", "duration_min": 30, "index": 1}


def test_preview_without_duration_has_empty_segments() -> None:
    body = preview_split(
        duration_min=None,
        timer_work_min=30,
        timer_break_min=15,
        timer_long_break_min=30,
        timer_long_break_every=4,
    )
    assert body == {
        "timer_work_min": 30,
        "timer_break_min": 15,
        "timer_long_break_min": 30,
        "timer_long_break_every": 4,
        "rounded": False,
        "message": "",
        "segments": [],
        "total_min": 0,
    }
