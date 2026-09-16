"""Month calendar assembly. No HTTP, no database."""

from __future__ import annotations

from datetime import date, timedelta

from backend.assignments import planned_minutes_by_id, unplanned_minutes
from backend.day import is_work_session
from backend.models import parse_naive_stamp
from backend.weeks import monday_of, month_grid, parse_month


def _dates_between(start: date, end: date) -> list[date]:
    days: list[date] = []
    day = start
    while day <= end:
        days.append(day)
        day += timedelta(days=1)
    return days


def _on_day(block: dict, day_index: int) -> bool:
    return day_index in list(block.get("days") or [])


def _placed_on_day(block: dict, day_index: int) -> bool:
    return bool(block.get("start")) and _on_day(block, day_index)


def _session_pinned_on_day(block: dict, day_index: int) -> bool:
    # A completed session keeps its candidate list; completed_day names the slot it
    # held (solver.py spent-time rule). Without it, only a single candidate pins.
    if not block.get("start"):
        return False
    pinned = block.get("completed_day")
    if pinned is None:
        days = list(block.get("days") or [])
        if len(days) != 1:
            return False
        pinned = days[0]
    return int(pinned) == day_index


def _details(body: dict) -> tuple[bool, bool, int, int]:
    checklist = list(body.get("checklist") or [])
    has_notes = bool(body.get("notes"))
    has_links = bool(body.get("links"))
    done = sum(1 for item in checklist if item.get("done"))
    return has_notes, has_links, len(checklist), done


def _unplanned(body: dict, planned: dict[str, int]) -> int:
    return unplanned_minutes(
        int(body["estimate_min"]), int(body["focus_minutes"]), planned.get(body["id"], 0)
    )


def _deadline_item(body: dict, revision: int, due_day: date, planned: dict[str, int]) -> dict:
    return {
        "id": body["id"],
        "title": body["title"],
        "due": body["due"],
        "date": due_day.isoformat(),
        "completed": bool(body.get("completed")),
        "estimate_min": int(body["estimate_min"]),
        "unplanned_min": _unplanned(body, planned),
        "revision": revision,
    }


def build_month(
    month: str,
    assignment_rows: list[tuple[dict, int]],
    weeks: list[tuple[str, list[dict]]],
) -> dict:
    start, end = parse_month(month)
    grid_start, grid_end = month_grid(start, end)
    grid_days = _dates_between(grid_start, grid_end)
    weeks_by_start = dict(weeks)
    from_week = monday_of(start.isoformat())
    planned = planned_minutes_by_id(weeks, from_week)

    due_by_date: dict[str, list[dict]] = {day.isoformat(): [] for day in grid_days}
    overdue: list[dict] = []
    assignment_due: dict[str, date] = {}
    for body, revision in assignment_rows:
        due_day, _minutes = parse_naive_stamp(body["due"])
        assignment_due[body["id"]] = due_day
        item = _deadline_item(body, revision, due_day, planned)
        key = due_day.isoformat()
        if key in due_by_date:
            due_by_date[key].append(item)
        elif due_day < grid_start and not body.get("completed"):
            overdue.append(item)
    for items in due_by_date.values():
        items.sort(key=lambda item: (item["due"], item["id"]))
    overdue.sort(key=lambda item: (item["due"], item["id"]))

    session_dates: dict[str, list[str]] = {}
    days_out: list[dict] = []
    for day in grid_days:
        label = day.isoformat()
        week_start = monday_of(label)
        day_index = day.weekday()
        blocks = weeks_by_start.get(week_start, [])
        sessions = [
            block
            for block in blocks
            if is_work_session(block)
            and (
                _placed_on_day(block, day_index)
                if block.get("kind") == "locked"
                else _session_pinned_on_day(block, day_index)
            )
        ]
        locked = [
            block
            for block in blocks
            if block.get("kind") == "locked"
            and not is_work_session(block)
            and _placed_on_day(block, day_index)
        ]
        for block in sessions:
            aid = block["assignment_id"]
            seen = session_dates.setdefault(aid, [])
            if label not in seen:
                seen.append(label)
        due_items = due_by_date[label]
        days_out.append(
            {
                "date": label,
                "week_start": week_start,
                "in_month": start <= day <= end,
                "due_ids": [item["id"] for item in due_items],
                "session_count": len(sessions),
                "locked_count": len(locked),
                "scheduled_min": sum(int(block["duration_min"]) for block in sessions + locked),
            }
        )

    deadlines = [item for day in grid_days for item in due_by_date[day.isoformat()]]
    visible_ids = {item["id"] for item in deadlines + overdue}
    visible_ids.update(session_dates)
    by_id = {body["id"]: (body, revision) for body, revision in assignment_rows}
    projects: list[dict] = []
    for assignment_id in visible_ids:
        row = by_id.get(assignment_id)
        if row is None:
            continue
        body, revision = row
        if body.get("completed"):
            continue
        has_notes, has_links, checklist_total, checklist_done = _details(body)
        dates = session_dates.get(assignment_id, [])
        if not (has_notes or has_links or checklist_total or len(dates) >= 2):
            continue
        item = _deadline_item(body, revision, assignment_due[assignment_id], planned)
        item["session_dates"] = dates
        item["has_notes"] = has_notes
        item["has_links"] = has_links
        item["checklist_total"] = checklist_total
        item["checklist_done"] = checklist_done
        projects.append(item)
    projects.sort(key=lambda item: (item["due"], item["id"]))

    return {
        "month": month,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "grid_start": grid_start.isoformat(),
        "grid_end": grid_end.isoformat(),
        "days": days_out,
        "deadlines": deadlines,
        "projects": projects,
        "overdue": overdue,
    }
