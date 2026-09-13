"""Assignment helpers. No HTTP, no database."""

from __future__ import annotations

import copy
import hashlib
from datetime import date, timedelta

from backend.slots import hhmm_to_minutes, minutes_to_hhmm, parse_deadline


def migrated_assignment_id(week_start: str, source_id: str) -> str:
    return "a-" + hashlib.sha256(f"{week_start}:{source_id}".encode()).hexdigest()[:32]


def due_from_latest(week_start: str, latest: str | None, days: list[int]) -> str:
    monday = date.fromisoformat(week_start)
    parsed = parse_deadline(latest, days)
    if parsed is None:
        return f"{(monday + timedelta(days=6)).isoformat()}T23:59"
    day_index, minutes = parsed
    return f"{(monday + timedelta(days=day_index)).isoformat()}T{minutes_to_hhmm(minutes)}"


def completed_at_for_block(week_start: str, block: dict) -> str:
    monday = date.fromisoformat(week_start)
    start = block.get("start")
    days = list(block.get("days") or [])
    day = block.get("completed_day")
    if start:
        if day is None and len(days) == 1:
            day = days[0]
        if day is not None:
            end = hhmm_to_minutes(start) + int(block["duration_min"])
            return f"{(monday + timedelta(days=int(day))).isoformat()}T{minutes_to_hhmm(end)}"
    return f"{(monday + timedelta(days=6)).isoformat()}T23:59"


def _assignment_body(
    assignment_id: str,
    block: dict,
    *,
    due: str,
    estimate_min: int,
    focus_minutes: int,
    focus_sessions: int,
    completed: bool,
    completed_at: str | None,
) -> dict:
    return {
        "id": assignment_id,
        "title": block.get("title") or assignment_id,
        "course": block.get("course"),
        "category": block.get("category"),
        "priority": block.get("priority", 3),
        "energy": block.get("energy", "medium"),
        "spotify_url": block.get("spotify_url"),
        "due": due,
        "estimate_min": estimate_min,
        "focus_minutes": focus_minutes,
        "focus_sessions": focus_sessions,
        "completed": completed,
        "completed_at": completed_at,
    }


def _as_session(block: dict, assignment_id: str) -> None:
    block["assignment_id"] = assignment_id
    block.pop("latest", None)
    block.pop("focus_minutes", None)
    block.pop("focus_sessions", None)


def migrate_blocks(week_start: str, blocks: list[dict]) -> tuple[list[dict], list[dict]]:
    updated = copy.deepcopy(blocks)
    created: list[dict] = []
    grouped: dict[str, list[int]] = {}
    for index, block in enumerate(updated):
        parent = block.get("pomodoro_parent_id")
        if block.get("kind") == "locked" and parent:
            grouped.setdefault(str(parent), []).append(index)
    claimed: set[int] = set()
    sunday_due = f"{(date.fromisoformat(week_start) + timedelta(days=6)).isoformat()}T23:59"
    for parent, indices in grouped.items():
        work_indices = [index for index in indices if updated[index].get("pomodoro_role") == "work"]
        if not work_indices or any(updated[index].get("assignment_id") for index in work_indices):
            continue
        work = [updated[index] for index in work_indices]
        aid = migrated_assignment_id(week_start, parent)
        completed = all(bool(block.get("completed")) for block in work)
        completed_at = None
        if completed:
            ends = [completed_at_for_block(week_start, block) for block in work if block.get("start")]
            completed_at = max(ends) if ends else sunday_due
        created.append(
            _assignment_body(
                aid,
                work[0],
                due=sunday_due,
                estimate_min=sum(int(block["duration_min"]) for block in work),
                focus_minutes=sum(int(block.get("focus_minutes") or 0) for block in work),
                focus_sessions=sum(int(block.get("focus_sessions") or 0) for block in work),
                completed=completed,
                completed_at=completed_at,
            )
        )
        for index in work_indices:
            _as_session(updated[index], aid)
            claimed.add(index)
    for index, block in enumerate(updated):
        if index in claimed or block.get("assignment_id") or block.get("kind") != "flexible":
            continue
        aid = migrated_assignment_id(week_start, str(block["id"]))
        completed = bool(block.get("completed"))
        created.append(
            _assignment_body(
                aid,
                block,
                due=due_from_latest(week_start, block.get("latest"), list(block.get("days") or [])),
                estimate_min=int(block["duration_min"]),
                focus_minutes=int(block.get("focus_minutes") or 0),
                focus_sessions=int(block.get("focus_sessions") or 0),
                completed=completed,
                completed_at=completed_at_for_block(week_start, block) if completed else None,
            )
        )
        _as_session(block, aid)
    return updated, created
