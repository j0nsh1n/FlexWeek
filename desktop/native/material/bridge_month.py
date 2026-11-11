"""The month screen's bridge.

The grid, the chip words, and the study-time minutes are the Widgets month's.
This object only reads NativeSession and hands QML rows. It does not call
HTTP, SQL, or the engine.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Protocol

from PySide6.QtCore import Property, QObject, Signal, Slot

from desktop.native.fields import week_starts_on
from desktop.native.hours.month import HOMEWORK, LOAD_CAP, LOAD_WORDS, MonthCell, month_cells
from desktop.native.material.bridge_rows import Labels, Rows
from desktop.native.material.theme import event_category
from desktop.native.weekmodel import clock_label, length_label, set_clock_24h

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_ROLES = (
    "iso",
    "day",
    "inMonth",
    "today",
    "chipsJson",
    "plannedShare",
    "completedShare",
    "accessName",
)


class _Session(Protocol):
    account: dict | None
    preferences: dict | None
    week_start: str
    planner_view: str
    selected_month: str | None
    month_data: dict | None

    def now_ms(self) -> int: ...

    def today_iso(self) -> str: ...

    def open_month(self, month: str | None = None) -> None: ...

    def shift_month(self, amount: int) -> None: ...

    def open_day(self, iso_day: str) -> None: ...

    def built_week(self) -> Any: ...

    def unsaved_weeks(self) -> dict: ...


class _Window(Protocol):
    session: _Session


def weekday_names() -> list[str]:
    """The account's week, Monday unless this computer starts on Sunday."""
    if week_starts_on() == "sunday":
        return ["Sun", *_WEEKDAYS[:6]]
    return list(_WEEKDAYS)


def pane_line(chip: Any) -> str:
    """One row of the date bar, the same line the Widgets date pane shows."""
    if chip.due or chip.history:
        return str(chip.words)
    when = clock_label(chip.start or 0)
    length = f" · {length_label(chip.minutes)}" if chip.minutes else ""
    mark = "✓ " if chip.category in HOMEWORK and chip.done else ""
    return f"{mark}{when} {chip.title}{length}"


def _share(minutes: int) -> float:
    if minutes <= 0:
        return 0.0
    return min(minutes / LOAD_CAP, 1.0)


def _kind(chip: Any) -> str:
    if chip.late:
        return "overdue"
    if chip.due:
        return "due"
    return "plain"


def _heading(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day.strftime('%A')} {day.day} {day.strftime('%B')}"


def _access(cell: MonthCell) -> str:
    words = _heading(cell.iso)
    if cell.today:
        words += ", today"
    if not cell.in_month:
        words += ", not in this month"
    return words


def _row(cell: MonthCell) -> dict[str, Any]:
    chips = [
        {"text": chip.words, "kind": _kind(chip), "category": event_category(chip.category)}
        for chip in cell.chips
    ]
    lines = [pane_line(chip) for chip in cell.chips] or ["Nothing planned"]
    if cell.planned_min or cell.completed_min:
        planned = length_label(cell.planned_min) if cell.planned_min else "0"
        done = length_label(cell.completed_min) if cell.completed_min else "0"
        lines.append(f"{planned} homework planned · {done} completed")
    return {
        "iso": cell.iso,
        "day": cell.day_number,
        "inMonth": cell.in_month,
        "today": cell.today,
        "chipsJson": json.dumps(chips),
        "chipTexts": [chip.words for chip in cell.chips],
        "lines": lines,
        "heading": _heading(cell.iso),
        "plannedMin": cell.planned_min,
        "completedMin": cell.completed_min,
        "plannedShare": _share(cell.planned_min),
        "completedShare": _share(cell.completed_min),
        "accessName": _access(cell),
    }


def read_cells(
    session: _Session,
    month: str | None = None,
    snapshot: dict | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """The dates to draw, and the weekday headings. Empty until a month is open."""
    names = weekday_names()
    if session.account is None:
        return [], names
    set_clock_24h(bool((session.preferences or {}).get("clock_24h")))
    chosen_month = month or session.selected_month
    chosen_snapshot = snapshot if snapshot is not None else session.month_data
    if chosen_snapshot is not None and chosen_month and chosen_snapshot.get("month") != chosen_month:
        chosen_snapshot = None
    if chosen_snapshot is None and not chosen_month:
        return [], names
    weeks: dict[str, Any] = {}
    weeks.update(session.unsaved_weeks())
    if session.week_start:
        weeks[session.week_start] = session.built_week()
    cells = month_cells(chosen_snapshot, weeks, session.today_iso(), chosen_month)
    return [_row(cell) for cell in cells], names


class MonthBridge(QObject):
    """Dates, chips, and the actions on the month screen."""

    changed = Signal()

    def __init__(self, window: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("monthBridge")
        self._window = window
        self._cell_rows: list[dict[str, Any]] = []
        self._weekday_names: list[str] = []
        self._selected = ""
        self._heading = ""
        self._show_study = False
        self._dates = Rows(_ROLES, self)
        self._weekdays = Labels(self)
        self._lines = Labels(self)
        changed = getattr(self._session(), "week_changed", None)
        if changed is not None:
            changed.connect(self.reload)

    def _session(self) -> _Session:
        return self._window.session  # type: ignore[attr-defined]

    def _note(self) -> None:
        self.changed.emit()
        parent = self.parent()
        signal = getattr(parent, "changed", None)
        if signal is not None and signal is not self.changed:
            signal.emit()

    def reload(self) -> None:
        """Read the session's month again. A date that left the grid is closed."""
        session = self._session()
        rows, names = read_cells(session)
        if rows != self._cell_rows:
            self._cell_rows = rows
            self._dates.set_rows([{key: row[key] for key in _ROLES} for row in rows])
        if names != self._weekday_names:
            self._weekday_names = names
            self._weekdays.set_rows(names)
        if self._selected and not any(row["iso"] == self._selected for row in rows):
            self._selected = ""
        self._fill_bar()
        self._note()

    def _fill_bar(self) -> None:
        row = next((item for item in self._cell_rows if item["iso"] == self._selected), None)
        if row is None:
            self._heading = ""
            self._lines.set_rows([])
            return
        self._heading = str(row["heading"])
        self._lines.set_rows(list(row["lines"]))

    def activate(self) -> None:
        """Ask the session for the month when the shell opens this screen."""
        session = self._session()
        if session.account is None:
            return
        if session.planner_view != "month":
            session.open_month()
            return
        self.reload()

    @Property(QObject, constant=True)
    def dates(self) -> QObject:
        return self._dates

    @Property(QObject, constant=True)
    def weekdays(self) -> QObject:
        return self._weekdays

    @Property(QObject, constant=True)
    def lines(self) -> QObject:
        return self._lines

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def cellRows(self) -> list:
        return self._cell_rows

    @Property(str, notify=changed)
    def selectedIso(self) -> str:
        return self._selected

    @Property(str, notify=changed)
    def heading(self) -> str:
        return self._heading

    @Property(bool, notify=changed)
    def barOpen(self) -> bool:
        return self._selected != ""

    @Property(bool, notify=changed)
    def showStudyTime(self) -> bool:
        return self._show_study

    @Property(str, constant=True)
    def studyLabel(self) -> str:
        return LOAD_WORDS

    @Slot(str)
    def selectDate(self, iso: str) -> None:
        """Open that date's bar. The same date again closes it, as the mock-up does."""
        if iso == self._selected:
            self._selected = ""
        elif any(row["iso"] == iso for row in self._cell_rows):
            self._selected = iso
        else:
            return
        self._fill_bar()
        self._note()

    @Slot()
    def closeDate(self) -> None:
        if not self._selected:
            return
        self._selected = ""
        self._fill_bar()
        self._note()

    @Slot()
    def openDay(self) -> None:
        """Open that date on Day, through the shell's page change."""
        iso = self._selected
        if not iso:
            return
        self._session().open_day(iso)
        show = getattr(self.parent(), "open_page", None)
        if show is not None:
            show("day", today=False)

    @Slot()
    def previousMonth(self) -> None:
        self._shift(-1)

    @Slot()
    def nextMonth(self) -> None:
        self._shift(1)

    def _shift(self, amount: int) -> None:
        session = self._session()
        if session.account is None:
            return
        if session.planner_view != "month":
            session.open_month()
        session.shift_month(amount)

    @Slot(bool)
    def setShowStudyTime(self, on: bool) -> None:
        """The Widgets switch. It is not saved: that screen keeps it for this visit too."""
        if self._show_study == on:
            return
        self._show_study = on
        self.changed.emit()
