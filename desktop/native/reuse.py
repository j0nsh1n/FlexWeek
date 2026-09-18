"""Clipboard, collision previews and Stage 3/4 planning helpers. No Qt."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta

from backend.slots import DAY_END_MIN, DAY_START_MIN, SLOT_MIN, hhmm_to_minutes, minutes_to_hhmm
from desktop.native.calendar import DAY_FULL

MAX_WEEK_BLOCKS = 100
AVAILABILITY_LIMIT = 21
LATE_MINUTES = (15, 30, 60)
PROTECTED_KINDS = ("downtime", "commute", "meal")
ROUTINE_FIELDS = (
    "title",
    "days",
    "start",
    "duration_min",
    "category",
    "course",
    "priority",
    "energy",
    "spotify_url",
)


def restore_point_label(text: str) -> str:
    characters = list(text)
    if len(characters) <= 80:
        return text
    return "".join(characters[:79]) + "…"


def format_duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def week_label(week_start: str) -> str:
    return "Week of " + week_start


def floor_slot(minutes: int) -> int:
    return max(0, minutes) // SLOT_MIN * SLOT_MIN


def is_homework_session(block: dict) -> bool:
    return bool(block.get("assignment_id"))


def occurrence_days(block: dict) -> list[int]:
    if block and block.get("kind") == "flexible" and block.get("completed"):
        completed_day = block.get("completed_day")
        if isinstance(completed_day, int):
            return [completed_day]
        if isinstance(block.get("days"), list) and len(block["days"]) > 1:
            return []
    return list((block or {}).get("days") or [])


def session_minutes(blocks: list[dict], assignment_id: str) -> int:
    total = 0
    for block in blocks:
        if block.get("assignment_id") == assignment_id and not block.get("completed"):
            total += int(block["duration_min"])
    return total


def available_homework_minutes(
    assignment: dict | None,
    blocks: list[dict],
    committed_blocks: list[dict] | None = None,
) -> int:
    if not assignment or assignment.get("completed"):
        return 0
    here = session_minutes(blocks, assignment["id"])
    committed = session_minutes(committed_blocks or [], assignment["id"])
    server = assignment.get("unplanned_min")
    if server is None:
        remaining = max(0, int(assignment["estimate_min"]) - int(assignment.get("focus_minutes") or 0))
        return floor_slot(remaining - here)
    return floor_slot(int(server) + committed - here)


def copied_fixed_block(source: dict, days: list[int], block_id: str) -> dict:
    copy = deepcopy(source)
    copy["id"] = block_id
    copy["kind"] = "locked"
    copy["days"] = list(days)
    copy["completed"] = False
    copy["completed_day"] = None
    copy["missed_days"] = []
    copy["focus_minutes"] = 0
    copy["focus_sessions"] = 0
    for key in ("assignment_id", "pomodoro_parent_id", "pomodoro_role", "pomodoro_index", "template_id"):
        copy.pop(key, None)
    return copy


def copied_homework_block(assignment: dict, day: int, duration: int, block_id: str) -> dict:
    return {
        "id": block_id,
        "kind": "flexible",
        "title": assignment["title"],
        "duration_min": duration,
        "days": [day],
        "start": None,
        "earliest": None,
        "latest": None,
        "priority": assignment.get("priority") or 3,
        "energy": assignment.get("energy") or "medium",
        "course": assignment.get("course"),
        "category": assignment.get("category"),
        "spotify_url": assignment.get("spotify_url"),
        "completed": False,
        "completed_day": None,
        "missed_days": [],
        "assignment_id": assignment["id"],
    }


def clipboard_item(block: dict, source_day: int, scope: str, group_id: str) -> dict:
    return {
        "block": deepcopy(block),
        "source_day": source_day,
        "scope": scope,
        "group_id": group_id,
    }


def clipboard_fingerprint(items: list[dict]) -> str:
    payload = [
        {"block": item["block"], "source_day": item["source_day"], "scope": item["scope"]}
        for item in items
    ]
    return json.dumps(payload, sort_keys=True, default=str)


def block_occurs_on_day(block: dict, day: int, placed: list[dict] | None = None) -> bool:
    if is_homework_session(block) or block.get("kind") == "flexible":
        source = block if block.get("start") else None
        if source is None and placed:
            source = next(
                (
                    item
                    for item in placed
                    if item.get("id") == block.get("id") and day in occurrence_days(item)
                ),
                None,
            )
        return bool(source and source.get("start") and day in occurrence_days(source))
    return day in occurrence_days(block)


def intervals_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a


def row_conflict(row: dict, rows: list[dict], existing: list[dict]) -> str | None:
    if not row.get("fixed") or not row["block"].get("start"):
        return None
    start = hhmm_to_minutes(row["block"]["start"])
    end = start + int(row["block"]["duration_min"])
    for block in existing:
        if not block.get("start") or row["day"] not in occurrence_days(block):
            continue
        other = hhmm_to_minutes(block["start"])
        if intervals_overlap(start, end, other, other + int(block["duration_min"])):
            return block["title"]
    for candidate in rows:
        if (
            candidate is row
            or not candidate.get("checked")
            or not candidate.get("fixed")
            or candidate["day"] != row["day"]
            or candidate.get("week_start") != row.get("week_start")
            or not candidate["block"].get("start")
        ):
            continue
        other = hhmm_to_minutes(candidate["block"]["start"])
        if intervals_overlap(start, end, other, other + int(candidate["block"]["duration_min"])):
            return candidate["block"]["title"]
    return None


def proposals_from_clipboard(
    items: list[dict],
    *,
    kind: str,
    week_start: str,
    target_day: int,
    target_start: str | None,
    assignments: dict[str, dict],
    available: dict[str, int],
) -> list[dict]:
    rows: list[dict] = []
    left = dict(available)
    for item_index, item in enumerate(items):
        source = item["block"]
        if is_homework_session(source):
            assignment = assignments.get(source["assignment_id"])
            remaining = left.get(source["assignment_id"], 0)
            duration = min(int(source["duration_min"]), remaining)
            usable = bool(assignment and duration >= SLOT_MIN)
            if usable:
                left[source["assignment_id"]] = remaining - duration
            if usable and assignment is not None:
                block = copied_homework_block(assignment, target_day, duration, item["group_id"])
                invalid = ""
            else:
                block = deepcopy(source)
                invalid = (
                    "No unplanned time remains for this homework."
                    if assignment
                    else "This homework did not load."
                )
            rows.append(
                {
                    "week_start": week_start,
                    "day": target_day,
                    "fixed": False,
                    "block": block,
                    "group_id": item["group_id"],
                    "checked": usable,
                    "invalid": invalid,
                    "original_duration": int(source["duration_min"]),
                }
            )
            continue
        days = list(source["days"]) if item["scope"] == "series" else [target_day]
        for day_index, day in enumerate(days):
            start = (
                target_start
                if target_start and kind == "block" and item["scope"] != "series"
                else source.get("start")
            )
            block = copied_fixed_block(source, [day], item["group_id"])
            block["start"] = start
            group_id = (
                item["group_id"]
                if item["scope"] == "series"
                else f"{item['group_id']}-{item_index}-{day_index}"
            )
            rows.append(
                {
                    "week_start": week_start,
                    "day": day,
                    "fixed": True,
                    "block": block,
                    "group_id": group_id,
                    "original_duration": int(source["duration_min"]),
                    "checked": True,
                    "invalid": "" if start else "Choose a start time.",
                }
            )
    return rows


def merge_preview_rows(rows: list[dict], operation_id: str) -> list[dict]:
    groups: dict[tuple, dict] = {}
    order: list[tuple] = []
    for row in rows:
        if not row.get("checked"):
            continue
        block = deepcopy(row["block"])
        if row.get("fixed"):
            block["days"] = [row["day"]]
        shape = {key: value for key, value in block.items() if key not in {"id", "days"}}
        key = (row["week_start"], row["group_id"], json.dumps(shape, sort_keys=True, default=str))
        if key not in groups:
            groups[key] = {"week_start": row["week_start"], "block": block, "days": []}
            order.append(key)
        groups[key]["days"].append(row["day"])
    stem = operation_id.replace("-", "")[:24]
    result = []
    for index, key in enumerate(order):
        group = groups[key]
        group["block"]["id"] = f"b-stage3-{stem}-{index:x}"
        group["block"]["days"] = sorted(set(group["days"]))
        result.append({"week_start": group["week_start"], "block": group["block"]})
    return result


def capacity_problem(existing_count: int, added_count: int, label: str) -> str:
    if existing_count + added_count > MAX_WEEK_BLOCKS:
        return f"{label} would exceed 100 blocks. Uncheck an item or remove a block first."
    return ""


def preview_conflict_message(row: dict, rows: list[dict], existing: list[dict]) -> str:
    if row.get("invalid"):
        return row["invalid"]
    conflict = row_conflict(row, rows, existing)
    if conflict:
        return f"Conflicts with {conflict}. Choose another time."
    if row.get("fixed"):
        return format_duration(int(row["block"]["duration_min"])) + " · Only this week"
    return format_duration(int(row["block"]["duration_min"])) + " · Time chosen when you plan"


def routine_source_blocks(blocks: list[dict]) -> list[dict]:
    return [
        block
        for block in blocks
        if block.get("kind") == "locked"
        and not block.get("assignment_id")
        and not block.get("pomodoro_role")
    ]


def routine_template(block: dict, template_id: str) -> dict:
    body: dict = {"template_id": template_id, "title": block["title"], "days": list(block["days"])}
    body["start"] = block["start"]
    body["duration_min"] = block["duration_min"]
    for field in ROUTINE_FIELDS:
        if field in {"template_id", "title", "days", "start", "duration_min"}:
            continue
        value = block.get(field)
        if value is not None:
            body[field] = value
    return body


def routine_rows(routine: dict, week_start: str, allowed_days: list[int]) -> list[dict]:
    rows: list[dict] = []
    allowed = set(allowed_days)
    for template in routine.get("blocks") or []:
        group_id = template["template_id"]
        for day in template.get("days") or []:
            if day not in allowed:
                continue
            block = copied_fixed_block({**template, "kind": "locked"}, [day], group_id)
            block.pop("template_id", None)
            rows.append(
                {
                    "week_start": week_start,
                    "day": day,
                    "fixed": True,
                    "block": block,
                    "group_id": group_id,
                    "original_duration": int(template["duration_min"]),
                    "checked": True,
                    "invalid": "",
                }
            )
    return rows


def unfinished_items(
    assignments: dict[str, dict],
    saved_weeks: list[str],
    week_start: str,
    blocks: list[dict],
    committed_blocks: list[dict],
) -> list[dict]:
    if not any(saved < week_start for saved in saved_weeks):
        return []
    items = []
    for item in assignments.values():
        minutes = available_homework_minutes(item, blocks, committed_blocks)
        if item.get("completed") or minutes < SLOT_MIN:
            continue
        items.append({**item, "remaining_min": minutes})
    return sorted(items, key=lambda item: (item.get("due") or "", item["id"]))


def late_from_start(minute: int) -> str:
    snapped = minute // SLOT_MIN * SLOT_MIN
    snapped = max(DAY_START_MIN, min(DAY_END_MIN - SLOT_MIN, snapped))
    return minutes_to_hhmm(snapped)


def running_late_block(day: int, from_start: str, minutes: int, block_id: str) -> dict:
    start = hhmm_to_minutes(from_start)
    duration = min(minutes, DAY_END_MIN - start)
    return {
        "id": block_id,
        "kind": "locked",
        "title": "Running late",
        "duration_min": duration,
        "days": [day],
        "start": from_start,
        "priority": 1,
        "energy": "medium",
        "category": "downtime",
        "completed": False,
        "missed_days": [],
    }


def running_late_refusal(
    *,
    week_start: str,
    now: datetime,
    dirty: bool,
    conflict: bool,
    block_count: int,
) -> str | None:
    today = now.date()
    this_week = (today - timedelta(days=today.weekday())).isoformat()
    minute = now.hour * 60 + now.minute
    if week_start != this_week:
        return "Open this week before using Running late."
    if minute < DAY_START_MIN or minute >= DAY_END_MIN:
        return "Running late is available between 06:00 and 23:00."
    if dirty or conflict:
        return "Save or reload this week before previewing a late start."
    if block_count >= MAX_WEEK_BLOCKS:
        return "This week already has 100 blocks. Remove one before recording a late start."
    return None


def late_id(operation_id: str) -> str:
    return "b-late-" + operation_id.replace("-", "")[:24]


def copy_label(block: dict, source_day: int, scope: str) -> str:
    title = block["title"]
    series = block.get("kind") == "locked" and len(block.get("days") or []) > 1
    if scope == "series":
        return f"{title} (all days)"
    if series:
        return f"{title} ({DAY_FULL[source_day]} only)"
    return title
