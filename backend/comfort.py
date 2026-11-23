"""Stage 5 timer presets, grid rounding and reminder-limit copy. No HTTP, no database."""

from __future__ import annotations

import json

import flexweek_engine  # type: ignore[import-untyped]

TIMER_PRESETS: tuple[dict, ...] = tuple(json.loads(flexweek_engine.timer_presets()))


def snap_minutes(value: int, minimum: int, maximum: int) -> int:
    return flexweek_engine.snap_minutes_wide(value, minimum, maximum)


def split_plan(
    duration_min: int,
    work_min: int,
    break_min: int,
    long_break_min: int,
    cadence: int,
) -> dict[str, object]:
    return json.loads(
        flexweek_engine.split_plan(duration_min, work_min, break_min, long_break_min, cadence)
    )
