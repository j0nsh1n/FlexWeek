"""A session stand-in and snapshots for the Material month bridge tests. Dates are worked out from the
calendar (1 November 2026 is a Sunday), not read off the code."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal

from desktop.native import fields
from desktop.native.material.bridge_month import MonthBridge


class Shell(QObject):
    """The part of the bridge above the month: a changed signal and the page change."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.pages: list[str] = []

    def open_page(self, name: str, today: bool = True) -> None:
        self.pages.append(name if today else name + " keeping the date")


class FakeSession:
    def __init__(self, month: str, snapshot: dict | None, clock_24h: bool = False) -> None:
        self.account = {"id": "a"}
        self.preferences = {"clock_24h": clock_24h}
        self.week_start = ""
        self.planner_view = "month"
        self.selected_month: str | None = month
        self.month_data = snapshot
        self.today = "2026-11-02"
        self.calls: list[tuple] = []

    def now_ms(self) -> int:
        return 0

    def today_iso(self) -> str:
        return self.today

    def open_month(self, month: str | None = None) -> None:
        self.calls.append(("open_month", month))
        self.planner_view = "month"

    def shift_month(self, amount: int) -> None:
        self.calls.append(("shift_month", amount))

    def open_day(self, iso_day: str) -> None:
        self.calls.append(("open_day", iso_day))
        self.planner_view = "day"

    def built_week(self) -> None:
        return None

    def unsaved_weeks(self) -> dict:
        return {}


def snapshot(month: str, days: dict[str, dict] | None = None, **extra: list) -> dict:
    return {"month": month, "days": [{"date": iso, **body} for iso, body in (days or {}).items()], **extra}


def isos(rows: list[dict]) -> list[str]:
    return [row["iso"] for row in rows]


def bridge_for(session: FakeSession) -> tuple[MonthBridge, Shell]:
    shell = Shell()
    month = MonthBridge(SimpleNamespace(session=session), shell)
    month.reload()
    return month, shell


def deadlines() -> dict:
    return snapshot(
        "2026-11",
        {
            "2026-11-05": {"in_month": True, "due_ids": ["essay", "oral"]},
            "2026-11-03": {"in_month": True, "due_ids": ["late"]},
            "2026-11-06": {
                "in_month": True,
                "blocks": [{"id": "school", "title": "School", "start": "08:00", "duration_min": 390}],
            },
        },
        deadlines=[
            {"id": "essay", "title": "History essay", "category": "assignments", "due": "2026-11-05T19:00"},
            {"id": "oral", "title": "French oral", "category": "assignments", "due": "2026-11-05"},
        ],
        overdue=[{"id": "late", "title": "Reading", "category": "assignments", "due": "2026-11-03"}],
    )


def chips(rows: list[dict], iso: str) -> list[dict]:
    row = next(item for item in rows if item["iso"] == iso)
    return json.loads(row["chipsJson"])


@pytest.fixture
def week_start():
    """Choose which day the week starts on, for the grid and the weekday names alike."""

    def choose(value: str) -> None:
        # Written as a pick writes it; the test folder is cleared between tests.
        path = fields._week_starts_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"week_starts_on": value}), encoding="utf-8")

    choose("monday")
    return choose
