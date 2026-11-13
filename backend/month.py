"""Month calendar assembly. No HTTP, no database."""

from __future__ import annotations

import json

import flexweek_engine  # type: ignore[import-untyped]


def build_month(
    month: str,
    assignment_rows: list[tuple[dict, int]],
    weeks: list[tuple[str, list[dict]]],
    first_weekday: int = 0,
) -> dict:
    """`first_weekday` is the day the month's rows start on, 0 Monday to 6 Sunday."""
    return json.loads(
        flexweek_engine.build_month(
            month,
            json.dumps([[body, revision] for body, revision in assignment_rows]),
            json.dumps([[start, blocks] for start, blocks in weeks]),
            first_weekday,
        )
    )
