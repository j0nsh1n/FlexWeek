"""What a month's dates hold: the cells, their chips and the study load, with no drawing."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

import flexweek_engine  # type: ignore[import-untyped]

from desktop.native.fields import week_start_day
from desktop.native.weekmodel import HOMEWORK as SESSION_CATEGORY  # noqa: F401
from desktop.native.weekmodel import WeekModel

LOAD_CAP = int(flexweek_engine.VIEWS_MONTH_LOAD_CAP)
LOAD_WORDS = str(flexweek_engine.VIEWS_MONTH_LOAD_WORDS)

HOMEWORK = frozenset(flexweek_engine.VIEWS_MONTH_HOMEWORK_CATEGORIES)


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
        return bool(flexweek_engine.views_month_chip_carried(self.block_id, self.start, self.due))

    @property
    def flag(self) -> str:
        """The state word shown before a deadline or a carried block."""
        return str(flexweek_engine.views_month_chip_flag(self.history, self.due, self.late, self.due_time))

    @property
    def words(self) -> str:
        return str(
            flexweek_engine.views_month_chip_words(
                self.title, self.start, self.due, self.late, self.due_time, self.history
            )
        )


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
        return int(flexweek_engine.views_month_day_number(self.iso))


def month_cells(
    snapshot: dict | None, weeks: Mapping[str, WeekModel], today_iso: str, month: str | None = None
) -> list[MonthCell]:
    """The dates of a month reply, each with its chips. `weeks` are the weeks the student has now,
    saved or not, by their Monday: a date in one of them is read from it; any other date from what
    the reply says is on it."""
    raw = json.loads(
        flexweek_engine.views_month_cells(json.dumps(snapshot), weeks, today_iso, month, week_start_day())
    )
    return [
        MonthCell(
            cell["iso"],
            cell["in_month"],
            cell["today"],
            tuple(MonthChip(**chip) for chip in cell["chips"]),
            cell["planned_min"],
            cell["completed_min"],
        )
        for cell in raw
    ]
