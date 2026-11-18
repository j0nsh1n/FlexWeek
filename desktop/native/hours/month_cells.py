"""What a month's dates hold: the cells, their chips and the study load, with no drawing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from backend.models import due_is_timed
from desktop.native.calendar import month_rows
from desktop.native.fields import week_start_day
from desktop.native.weekmodel import HOMEWORK as SESSION_CATEGORY
from desktop.native.weekmodel import WeekModel, clock_label, hhmm_text

LOAD_CAP = 180
LOAD_WORDS = "Show study time per date"

HOMEWORK = frozenset({"homework", "assignments"})


@dataclass(frozen=True)
class MonthChip:
    """One line in a date: a block at its time, or homework due that day."""

    key: str
    title: str
    category: str
    block_id: str | None = None
    start: int | None = None
    minutes: int = 0
    due: bool = False
    due_time: str | None = None
    done: bool = False
    # Due on a date already gone and not finished.
    late: bool = False
    history: str = ""

    @property
    def carried(self) -> bool:
        """A block with a time can be carried to another date. A deadline cannot."""
        return self.block_id is not None and self.start is not None and not self.due

    @property
    def flag(self) -> str:
        """The state word shown before a deadline or a carried block."""
        if self.history:
            return self.history
        if not self.due:
            return ""
        if self.late:
            return "Overdue"
        return f"Due {hhmm_text(self.due_time)}" if self.due_time else "Due"

    @property
    def words(self) -> str:
        if self.due or self.history:
            if self.history and not self.due:
                return f"{self.flag} {clock_label(self.start or 0)} {self.title}"
            return f"{self.flag} {self.title}"
        return f"{clock_label(self.start or 0)} {self.title}"


@dataclass(frozen=True)
class MonthCell:
    iso: str
    in_month: bool
    today: bool
    chips: tuple[MonthChip, ...]
    planned_min: int = 0
    completed_min: int = 0

    @property
    def day_number(self) -> int:
        return int(self.iso[8:])


def month_cells(
    snapshot: dict | None, weeks: Mapping[str, WeekModel], today_iso: str, month: str | None = None
) -> list[MonthCell]:
    """The dates of a month reply, each with its chips. `weeks` are the weeks the student has now,
    saved or not, by their Monday: a date in one of them is read from it; any other date from what
    the reply says is on it."""
    snapshot = snapshot or {"month": month, "days": []}
    deadlines: dict[str, dict] = {}
    for item in list(snapshot.get("deadlines") or []) + list(snapshot.get("overdue") or []):
        if item.get("id"):
            deadlines[str(item["id"])] = item
    open_days: dict[str, tuple] = {}
    for week_start, week in weeks.items():
        monday = date.fromisoformat(week_start)
        for offset in range(7):
            day_iso = (monday + timedelta(days=offset)).isoformat()
            open_days[day_iso] = tuple(item for item in week.occurrences if item.day == offset)
    days = {str(day["date"]): day for day in snapshot.get("days") or []}
    month = str(snapshot.get("month") or month or "")
    if not month and days:
        month = next((iso[:7] for iso, day in days.items() if day.get("in_month")), next(iter(days))[:7])
    if month:
        first = date.fromisoformat(month + "-01")
        next_month = date(first.year + (first.month == 12), 1 if first.month == 12 else first.month + 1, 1)
        last = next_month - timedelta(days=1)
        display_start, display_end = month_rows(first, last, week_start_day())
        ordered_days = []
        current = display_start
        while current <= display_end:
            iso = current.isoformat()
            ordered_days.append(days.get(iso, {"date": iso, "in_month": current.month == first.month}))
            current += timedelta(days=1)
    else:
        ordered_days = list(days.values())
    cells = []
    for day in ordered_days:
        iso = str(day["date"])
        chips: list[MonthChip] = []
        for aid in day.get("due_ids") or []:
            item = deadlines.get(str(aid), {"id": aid, "title": aid})
            due = str(item.get("due") or "")
            chips.append(
                MonthChip(
                    f"due:{aid}",
                    str(item.get("title") or aid),
                    str(item.get("category") or "assignments"),
                    due=True,
                    due_time=due[11:16] if due and due_is_timed(due) else None,
                    done=bool(item.get("completed")),
                    late=iso < today_iso and not item.get("completed"),
                )
            )
        blocks: list[MonthChip] = []
        if iso in open_days:
            for item in open_days[iso]:
                blocks.append(
                    MonthChip(
                        f"block:{item.block_id}",
                        item.title,
                        item.category,
                        block_id=item.block_id,
                        start=item.start,
                        minutes=item.end - item.start,
                        done=item.done,
                        history=item.history,
                    )
                )
        else:
            for item in day.get("blocks") or []:
                start = str(item.get("start") or "")
                if len(start) != 5:
                    continue
                blocks.append(
                    MonthChip(
                        f"block:{item['id']}",
                        str(item.get("title") or "Untitled"),
                        # A homework session is saved with no category unless the student picked one.
                        str(item.get("category") or (SESSION_CATEGORY if item.get("assignment_id") else "")),
                        block_id=str(item["id"]),
                        start=int(start[:2]) * 60 + int(start[3:]),
                        minutes=int(item.get("duration_min") or 0),
                        done=bool(item.get("completed")),
                        history=str(item.get("history") or ""),
                    )
                )
        blocks.sort(key=lambda chip: (chip.start or 0, chip.title))
        sessions = [block for block in blocks if block.category in HOMEWORK]
        planned = sum(block.minutes for block in sessions)
        completed = sum(block.minutes for block in sessions if block.done)
        cells.append(
            MonthCell(
                iso,
                bool(day.get("in_month")),
                iso == today_iso,
                tuple(chips + blocks),
                planned,
                completed,
            )
        )
    return cells
