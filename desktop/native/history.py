"""Undo and redo snapshots for the native week on screen. No Qt."""

from __future__ import annotations

import json
from copy import deepcopy

HISTORY_LIMIT = 50


def same_value(left: object, right: object) -> bool:
    return json.dumps(left, sort_keys=True, default=str) == json.dumps(right, sort_keys=True, default=str)


def capture_step(
    label: str,
    week_start: str,
    before_blocks: list[dict],
    after_blocks: list[dict],
    before_assignments: dict[str, dict],
    after_assignments: dict[str, dict],
    changed_ids: set[str],
) -> dict | None:
    step: dict = {"label": label, "weeks": [], "assignments": [], "stale": False}
    if not same_value(before_blocks, after_blocks):
        step["weeks"].append(
            {
                "week_start": week_start,
                "before": deepcopy(before_blocks),
                "after": deepcopy(after_blocks),
            }
        )
    for item_id in sorted(changed_ids):
        prior = before_assignments.get(item_id)
        after = after_assignments.get(item_id)
        if same_value(prior, after):
            continue
        step["assignments"].append(
            {
                "id": item_id,
                "before": deepcopy(prior) if prior is not None else None,
                "after": deepcopy(after) if after is not None else None,
            }
        )
    if not step["weeks"] and not step["assignments"]:
        return None
    return step


def push_step(stack: list[dict], step: dict) -> None:
    stack.append(step)
    if len(stack) > HISTORY_LIMIT:
        del stack[0]


def mark_stale(steps: list[dict], week_start: str) -> None:
    for step in steps:
        if any(entry["week_start"] == week_start for entry in step.get("weeks") or []):
            step["stale"] = True
