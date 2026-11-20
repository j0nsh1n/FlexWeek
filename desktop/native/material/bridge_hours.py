"""Study hours and School hours as Material Settings edits them.

The rules and messages are the Widgets dialogs' (AvailabilityDialog and SchoolHoursDialog): hours sit on
the 15-minute grid, an end must be later than its start, protected times may not overlap on a shared
day, and at most 21 of each. The drafts are plain data, so they are checked without Qt; the
SettingsBridge shows them, and Save sends them the way the Widgets dialogs do.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.slots import SLOT_MIN, hhmm_to_minutes, minutes_to_hhmm
from desktop.native.calendar import DAY_FULL
from desktop.native.fields import read_clock
from desktop.native.reuse import AVAILABILITY_LIMIT, PROTECTED_KINDS
from desktop.native.settings_copy import PROTECTED_WORDS
from desktop.native.weekmodel import end_after_start_words, hhmm_text

NEW_WINDOW = {"days": [0, 1, 2, 3, 4], "start": "16:00", "end": "18:00"}
NEW_PROTECTED = {"days": [0, 1, 2, 3, 4], "kind": "downtime", "start": "17:00", "end": "18:00", "title": ""}


def grid_clock(text: str, *, end: bool = False) -> str | None:
    """HH:MM on the 15-minute grid for a time the student typed, or None when it is not a time. An end
    of the day is 24:00."""
    minute = read_clock(str(text), end=end, whole=False)
    if minute is None:
        return None
    if minute >= 1440:
        return "24:00"
    return minutes_to_hhmm(minute - minute % SLOT_MIN)


def _minutes(clock: str) -> int:
    return 1440 if clock == "24:00" else hhmm_to_minutes(clock)


def _days(row: dict[str, Any], day: int) -> list[int]:
    days = set(row.get("days") or [])
    days.symmetric_difference_update({day})
    return sorted(days)


class StudyHours:
    """The study windows and protected times being edited. Nothing is saved until `problem()` is empty
    and the bridge sends `windows()`, `protected()` and the cutoff."""

    def __init__(self) -> None:
        self.windows: list[dict[str, Any]] = []
        self.protected_rows: list[dict[str, Any]] = []
        self.dirty = False
        self.error = ""

    def load(self, prefs: dict[str, Any]) -> None:
        self.windows = [
            {
                "days": sorted(row.get("days") or []),
                "start": row["start"],
                "end": row["end"],
                "subject": row.get("subject") or "",
            }
            for row in prefs.get("work_windows") or []
        ]
        self.protected_rows = [
            {
                "days": sorted(row.get("days") or []),
                "kind": row["kind"],
                "start": row["start"],
                "end": minutes_to_hhmm(hhmm_to_minutes(row["start"]) + int(row["duration_min"]))
                if hhmm_to_minutes(row["start"]) + int(row["duration_min"]) < 1440
                else "24:00",
                "title": row.get("title") or "",
            }
            for row in prefs.get("protected") or []
        ]
        self.dirty = False
        self.error = ""

    def _touch(self) -> None:
        self.dirty = True
        self.error = ""

    def add_window(self, row: dict[str, Any] | None = None) -> None:
        if len(self.windows) >= AVAILABILITY_LIMIT:
            self.error = f"Up to {AVAILABILITY_LIMIT} sets of study hours."
            return
        self.windows.append({**deepcopy(row or NEW_WINDOW), "subject": ""})
        self._touch()

    def add_protected(self) -> None:
        if len(self.protected_rows) >= AVAILABILITY_LIMIT:
            self.error = f"Up to {AVAILABILITY_LIMIT} protected times."
            return
        self.protected_rows.append(deepcopy(NEW_PROTECTED))
        self._touch()

    def remove(self, rows: list[dict[str, Any]], index: int) -> None:
        if 0 <= index < len(rows):
            rows.pop(index)
            self._touch()

    def toggle_day(self, rows: list[dict[str, Any]], index: int, day: int) -> None:
        if 0 <= index < len(rows) and 0 <= day <= 6:
            rows[index]["days"] = _days(rows[index], day)
            self._touch()

    def set_time(self, rows: list[dict[str, Any]], index: int, field: str, text: str) -> None:
        if not 0 <= index < len(rows) or field not in ("start", "end"):
            return
        clock = grid_clock(text, end=field == "end")
        if clock is None:
            self.error = "Type a time such as 4 pm or 16:00."
            return
        if field == "start" and clock == "24:00":
            self.error = "Type a time such as 4 pm or 16:00."
            return
        rows[index][field] = clock
        self._touch()

    def set_text(self, rows: list[dict[str, Any]], index: int, field: str, text: str) -> None:
        if 0 <= index < len(rows) and field in ("subject", "title"):
            rows[index][field] = text.strip()[:40]
            self._touch()

    def set_kind(self, index: int, kind: str) -> None:
        if 0 <= index < len(self.protected_rows) and kind in PROTECTED_KINDS:
            self.protected_rows[index]["kind"] = kind
            self._touch()

    def problem(self) -> str:
        """The first thing wrong with the draft, in the Widgets dialogs' words, or ''."""
        for row in (*self.windows, *self.protected_rows):
            if not row["days"]:
                return "Pick at least one day."
            if _minutes(row["end"]) <= _minutes(row["start"]):
                return end_after_start_words(hhmm_text(row["start"]))
        for day in range(7):
            spans = sorted(
                (_minutes(row["start"]), _minutes(row["end"]))
                for row in self.protected_rows
                if day in row["days"]
            )
            for (_s1, end1), (start2, _e2) in zip(spans, spans[1:], strict=False):
                if start2 < end1:
                    return f"That overlaps protected time already on {DAY_FULL[day]}."
        return ""

    def saved_windows(self) -> list[dict[str, Any]]:
        saved = []
        for row in self.windows:
            window = {"days": sorted(row["days"]), "start": row["start"], "end": row["end"]}
            if row.get("subject"):
                window["subject"] = row["subject"]
            saved.append(window)
        return saved

    def saved_protected(self) -> list[dict[str, Any]]:
        saved = []
        for row in self.protected_rows:
            window = {
                "days": sorted(row["days"]),
                "kind": row["kind"],
                "start": row["start"],
                "duration_min": _minutes(row["end"]) - _minutes(row["start"]),
            }
            if row.get("title"):
                window["title"] = row["title"]
            saved.append(window)
        return saved

    def window_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "days": list(row["days"]),
                "start": hhmm_text(row["start"]),
                "end": hhmm_text(row["end"]),
                "subject": row.get("subject") or "",
            }
            for row in self.windows
        ]

    def protected_view(self) -> list[dict[str, Any]]:
        return [
            {
                "days": list(row["days"]),
                "kind": row["kind"],
                "kindLabel": PROTECTED_WORDS.get(row["kind"], row["kind"]),
                "start": hhmm_text(row["start"]),
                "end": hhmm_text(row["end"]),
                "title": row.get("title") or "",
            }
            for row in self.protected_rows
        ]


class SchoolHours:
    """The usual School: its days and times, as the Widgets School hours dialog asks them."""

    def __init__(self) -> None:
        self.days: list[int] = [0, 1, 2, 3, 4]
        self.start = "08:00"
        self.end = "15:00"
        self.exists = False
        self.dirty = False
        self.error = ""

    def load(self, school: dict[str, Any] | None) -> None:
        self.exists = school is not None
        if school is not None:
            self.days = sorted(int(day) for day in school.get("days") or [])
            self.start = str(school.get("start") or "08:00")
            end = hhmm_to_minutes(self.start) + int(school.get("duration_min") or 390)
            self.end = minutes_to_hhmm(end) if end < 1440 else "24:00"
        else:
            self.days, self.start, self.end = [0, 1, 2, 3, 4], "08:00", "15:00"
        self.dirty = False
        self.error = ""

    def toggle_day(self, day: int) -> None:
        if 0 <= day <= 6:
            self.days = _days({"days": self.days}, day)
            self.dirty = True
            self.error = ""

    def set_time(self, field: str, text: str) -> None:
        clock = grid_clock(text, end=field == "end")
        if clock is None or (field == "start" and clock == "24:00") or field not in ("start", "end"):
            self.error = "Type a time such as 8 am or 08:00."
            return
        setattr(self, field, clock)
        self.dirty = True
        self.error = ""

    def minutes(self) -> int:
        return _minutes(self.end) - _minutes(self.start)

    def problem(self) -> str:
        if self.days and self.minutes() <= 0:
            return end_after_start_words(hhmm_text(self.start))
        return ""
