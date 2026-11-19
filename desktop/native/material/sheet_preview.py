"""The preview sheet: what Paste, Duplicate and the other copies propose, row by row, before saving.

The rows and their conflict rules are the Widgets dialog's own (reuse.row_conflict and its message); this
holds the state and the words for Material's sheet."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from backend.slots import (
    DAY_END_MIN,
    DAY_START_MIN,
    SLOT_MIN,
    hhmm_to_minutes,
    minutes_to_hhmm,
)
from desktop.native.calendar import DAYS
from desktop.native.reuse import preview_conflict_message, row_conflict
from desktop.native.weekmodel import hhmm_text

NONE_CHOSEN = "Select at least one item before saving."


def beside_words(clash: str) -> str:
    """What a time says when another block is already there: it is allowed, and both are drawn."""
    return f"{clash} is at that time too. Both will show, side by side."


class PreviewDraft:
    """Rows the student can untick, and for a fixed time move to another day, start or length."""

    def __init__(
        self,
        title: str,
        summary: str,
        rows: list[dict],
        existing: list[dict],
        save: Callable[[list[dict]], None],
        confirm: str = "Save preview",
    ) -> None:
        self.confirm = confirm
        self.title = title
        self.summary = summary
        self.rows = deepcopy(rows)
        self.existing = existing
        self.save = save
        self._first = True
        self._settle()

    def _settle(self) -> None:
        if self._first:
            for row in self.rows:
                if row.get("invalid"):
                    row["checked"] = False
        self._first = False

    def can_save(self) -> bool:
        return any(row.get("checked") for row in self.rows)

    def check(self, index: int, checked: bool) -> None:
        if 0 <= index < len(self.rows) and not self.rows[index].get("invalid"):
            self.rows[index]["checked"] = checked

    def _touched(self, index: int) -> None:
        if not row_conflict(self.rows[index], self.rows, self.existing):
            self.rows[index]["checked"] = True

    def set_day(self, index: int, day: int) -> None:
        if not 0 <= index < len(self.rows) or not 0 <= day < len(DAYS):
            return
        self.rows[index]["day"] = day
        self.rows[index]["block"]["days"] = [day]
        self._touched(index)

    def set_start(self, index: int, start: str) -> None:
        if not 0 <= index < len(self.rows):
            return
        self.rows[index]["block"]["start"] = start
        self.rows[index]["invalid"] = ""
        self._touched(index)

    def set_duration(self, index: int, minutes: int) -> None:
        if not 0 <= index < len(self.rows):
            return
        self.rows[index]["block"]["duration_min"] = int(minutes)
        self._touched(index)

    def _row_form(self, index: int, row: dict) -> dict[str, Any]:
        conflict = row_conflict(row, self.rows, self.existing)
        beside = conflict and not row.get("invalid")
        detail = (
            beside_words(conflict) if beside else preview_conflict_message(row, self.rows, self.existing)
        )
        form: dict[str, Any] = {
            "index": index,
            "title": row["block"]["title"],
            "checked": bool(row.get("checked")),
            "invalid": bool(row.get("invalid")),
            "detail": detail,
            "fixed": bool(row.get("fixed")),
        }
        if row.get("fixed"):
            block = row["block"]
            duration = int(block["duration_min"])
            current = block.get("start") or minutes_to_hhmm(DAY_START_MIN)
            last = DAY_END_MIN - duration
            offered = {minutes_to_hhmm(minute) for minute in range(DAY_START_MIN, last + 1, SLOT_MIN)}
            starts = sorted(offered | {current})
            block["start"] = current
            room = DAY_END_MIN - hhmm_to_minutes(current)
            maximum = min(room, int(row.get("original_duration") or duration))
            lengths = set(range(SLOT_MIN, maximum + 1, SLOT_MIN))
            if duration <= maximum:
                lengths.add(duration)
            form.update(
                {
                    "day": row["day"],
                    "dayOptions": [{"value": number, "label": name} for number, name in enumerate(DAYS)],
                    "start": current,
                    "startOptions": [{"value": value, "label": hhmm_text(value)} for value in starts],
                    "duration": min(duration, maximum),
                    "durationOptions": [
                        {"value": minutes, "label": str(minutes)} for minutes in sorted(lengths)
                    ],
                }
            )
        return form

    def form(self) -> dict[str, Any]:
        rows = [self._row_form(index, row) for index, row in enumerate(self.rows)]
        return {
            "kind": "preview",
            "heading": self.title,
            "intro": self.summary,
            "confirm": self.confirm,
            "rows": rows,
            "canSave": self.can_save(),
            "whyOff": "" if self.can_save() else NONE_CHOSEN,
        }
