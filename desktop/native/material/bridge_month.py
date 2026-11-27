"""The month screen's bridge.

Decisions and view state live in `flexweek_engine.MonthView` and `views_month_*`;
this object only reads NativeSession and hands QML rows. It does not call HTTP,
SQL, or the solver.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import Property, QObject, Signal, Slot

from desktop.native.fields import week_start_day, week_start_notice
from desktop.native.hours.month_cells import LOAD_WORDS, MonthCell
from desktop.native.material.bridge_rows import Labels, Rows
from desktop.native.weekmodel import set_clock_24h

_WEEKDAYS = tuple(flexweek_engine.VIEWS_MONTH_WEEKDAYS)
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
    """The week's days from the computer's first day of the week."""
    return list(flexweek_engine.views_month_weekday_names(week_start_day()))


def pane_line(chip: Any) -> str:
    """One row of the date bar, the same line the Widgets date pane shows."""
    return str(flexweek_engine.views_month_pane_line(chip))


def _share(minutes: int) -> float:
    return float(flexweek_engine.views_month_share(minutes))


def _kind(chip: Any) -> str:
    return str(flexweek_engine.views_month_chip_kind(bool(chip.due), bool(chip.late)))


def _heading(iso: str) -> str:
    return str(flexweek_engine.views_month_heading(iso))


def _access(cell: MonthCell) -> str:
    return str(flexweek_engine.views_month_access_name(cell.iso, cell.today, cell.in_month))


def _row(cell: MonthCell) -> dict[str, Any]:
    return json.loads(flexweek_engine.views_month_cell_row(cell))


def read_cells(
    session: _Session,
    month: str | None = None,
    snapshot: dict | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """The dates to draw, and the weekday headings. Empty until a month is open."""
    first_weekday = week_start_day()
    clock_24h, ready, chosen_month, chosen_snapshot_json, include_built, names = (
        flexweek_engine.views_month_prepare_read(
            session.account is not None,
            session.preferences,
            month,
            session.selected_month,
            json.dumps(snapshot),
            json.dumps(session.month_data),
            session.week_start,
            first_weekday,
        )
    )
    if clock_24h is not None:
        set_clock_24h(clock_24h)
    if ready is None:
        return [], list(names)
    built_week = None
    if include_built is not None:
        built_week = session.built_week()
    rows = json.loads(
        flexweek_engine.views_month_build_rows(
            chosen_snapshot_json,
            session.unsaved_weeks(),
            session.week_start,
            built_week,
            session.today_iso(),
            chosen_month,
            first_weekday,
        )
    )
    return rows, list(names)


class MonthBridge(QObject):
    """Dates, chips, and the actions on the month screen."""

    changed = Signal()

    def __init__(self, window: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("monthBridge")
        self._window = window
        self._view = flexweek_engine.MonthView()
        self._dates = Rows(_ROLES, self)
        self._weekdays = Labels(self)
        self._lines = Labels(self)
        self._published: dict[str, list[Any]] = {"dates": [], "weekdays": [], "lines": []}
        self._apply_snapshot()
        changed = getattr(self._session(), "week_changed", None)
        if changed is not None:
            changed.connect(self.reload)
        week_start_notice().changed.connect(self._on_week_start)

    def _session(self) -> _Session:
        return self._window.session  # type: ignore[attr-defined]

    def _on_week_start(self, _value: str) -> None:
        self.reload()

    def _note(self) -> None:
        self.changed.emit()
        parent = self.parent()
        signal = getattr(parent, "changed", None)
        if signal is not None and signal is not self.changed:
            signal.emit()

    def _apply_snapshot(self) -> None:
        snap = json.loads(self._view.snapshot_json())
        self._cell_rows: list[dict[str, Any]] = snap["cellRows"]
        self._date_rows: list[dict[str, Any]] = snap["dateRows"]
        self._weekday_names: list[str] = snap["weekdayNames"]
        self._selected: str = snap["selectedIso"]
        self._heading: str = snap["heading"]
        self._bar_open: bool = snap["barOpen"]
        self._line_rows: list[str] = snap["lines"]
        self._show_study: bool = snap["showStudyTime"]

    def _publish(self) -> None:
        for name, model, rows in (
            ("dates", self._dates, self._date_rows),
            ("weekdays", self._weekdays, self._weekday_names),
            ("lines", self._lines, self._line_rows),
        ):
            if self._published.get(name) != rows:
                self._published[name] = list(rows)
                model.set_rows(rows)
        self._note()

    def reload(self) -> None:
        """Read the session's month again. A date that left the grid is closed."""
        session = self._session()
        clock_24h, ready, include_built = self._view.prepare_reload(
            session.account is not None,
            session.preferences,
            session.selected_month,
            json.dumps(session.month_data),
            session.week_start,
            week_start_day(),
        )
        if clock_24h is not None:
            set_clock_24h(clock_24h)
        if ready is not None:
            built_week = None
            if include_built is not None:
                built_week = session.built_week()
            self._view.finish_reload(
                session.unsaved_weeks(),
                session.week_start,
                built_week,
                session.today_iso(),
            )
        self._apply_snapshot()
        self._publish()

    def activate(self) -> None:
        """Ask the session for the month when the shell opens this screen."""
        session = self._session()
        open_month, should_reload = self._view.activate_plan(
            session.account is not None, session.planner_view
        )
        if open_month is not None:
            session.open_month()
        if should_reload is not None:
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
        return self._bar_open

    @Property(bool, notify=changed)
    def showStudyTime(self) -> bool:
        return self._show_study

    @Property(str, constant=True)
    def studyLabel(self) -> str:
        return LOAD_WORDS

    @Slot(str)
    def selectDate(self, iso: str) -> None:
        """Open that date's bar. The same date again closes it, as the mock-up does."""
        if self._view.select_date(iso) is None:
            return
        self._apply_snapshot()
        self._publish()

    @Slot()
    def closeDate(self) -> None:
        if self._view.close_date() is None:
            return
        self._apply_snapshot()
        self._publish()

    @Slot()
    def openDay(self) -> None:
        """Open that date on Day, through the shell's page change."""
        iso = self._view.open_day_target()
        if iso is None:
            return
        self._session().open_day(iso)
        show = getattr(self.parent(), "open_page", None)
        if show is not None:
            show("day", today=False)

    @Slot(result=str)
    def pickerAnchor(self) -> str:
        """The first day of the month on view: the month the Go to date picker opens on."""
        session = self._session()
        return str(self._view.picker_anchor(session.selected_month, session.today_iso()))

    @Slot(result=str)
    def todayIso(self) -> str:
        return self._session().today_iso()

    @Slot(str)
    def goToDate(self, iso: str) -> None:
        """A day picked in the Go to date month: that month."""
        session = self._session()
        month = self._view.go_to_date_month(iso, session.account is not None)
        if month is not None:
            session.open_month(month)

    @Slot()
    def today(self) -> None:
        """Month's T key: this month, through the same open the shell uses."""
        session = self._session()
        month = self._view.today_month(session.account is not None, session.today_iso())
        if month is not None:
            session.open_month(month)

    @Slot()
    def previousMonth(self) -> None:
        self._shift(-1)

    @Slot()
    def nextMonth(self) -> None:
        self._shift(1)

    def _shift(self, amount: int) -> None:
        session = self._session()
        plan = self._view.shift_plan(session.account is not None, session.planner_view, amount)
        if plan is None:
            return
        open_month, step = plan
        if open_month is not None:
            session.open_month()
        session.shift_month(step)

    @Slot(bool)
    def setShowStudyTime(self, on: bool) -> None:
        """The Widgets switch. It is not saved: that screen keeps it for this visit too."""
        if self._view.set_show_study_time(on) is None:
            return
        self._apply_snapshot()
        self.changed.emit()
