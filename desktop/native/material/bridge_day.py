"""The day screen's bridge. QML reads this. It reads the session and nothing lower.

Decisions and view state live in `flexweek_engine.DayView`; this object reads the session, hands
the facts over, and forwards what comes back into Qt models, properties, signals and slots.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Any, Protocol

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from desktop.native.calendar import monday_of
from desktop.native.material.bridge_rows import Rows
from desktop.native.material.bridge_week import BLOCK_ROLES
from desktop.native.material.day_board import DayBoard, DayRow, board_for, board_from
from desktop.native.weekmodel import set_clock_24h

ROW_ROLES = (
    "title",
    "subtitle",
    "icon",
    "bar",
    "fill",
    "ink",
    "tag",
    "tagKind",
    "canFinish",
    "assignmentId",
    "dim",
)


def _week_holding(session: object, iso_day: str) -> str:
    """The first day of the week on screen that holds `iso_day`: it starts on the student's chosen day."""
    holder = getattr(session, "shown_week_of", None)
    if holder is None:
        return monday_of(iso_day)
    return str(holder(iso_day))


def _moment(session: Any) -> datetime:
    return datetime.fromtimestamp(session.now_ms() / 1000)


class _Session(Protocol):
    preferences: dict | None
    week_start: str
    selected_day: str
    assignments: dict

    def now_ms(self) -> int: ...

    def built_week(self) -> Any: ...

    def complete_homework(self, assignment_id: str, completed: bool = True) -> None: ...

    def save(self) -> None: ...

    def start_focus(self, block_id: str | None, day: int | None = None) -> bool: ...


class _Window(Protocol):
    session: _Session

    def _start_focus(self, block_id: str, day: object) -> None: ...


def _empty() -> DayBoard:
    return board_for((), minute=0, when="today", nudges=True, dim=True, mode="light", on=date(2026, 1, 1))


class DayBridge(QObject):
    """One day's lists, the free-time card, and the actions those rows take."""

    changed = Signal()
    dateOpened = Signal()

    def __init__(self, window: QObject, parent: QObject, *, today_only: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("dayBridge")
        self._window = window
        self._view = flexweek_engine.DayView(today_only)
        self._up = Rows(ROW_ROLES, self)
        self._done = Rows(ROW_ROLES, self)
        self._blocks = Rows(BLOCK_ROLES, self)
        self._block_rows: list[dict] = []
        self._board = _empty()
        self._apply_snapshot()
        self._connect_session(today_only)
        self._publish(self._board)

    def _connect_session(self, today_only: bool) -> None:
        session = getattr(self._window, "session", None)
        timer = getattr(session, "focus_changed", None)
        if timer is not None and hasattr(timer, "connect"):
            timer.connect(self._on_timer)
        busy = getattr(session, "busy_changed", None)
        if today_only and busy is not None:
            busy.connect(self._on_busy)
        landed = getattr(session, "week_changed", None)
        if not today_only and landed is not None and hasattr(landed, "connect"):
            landed.connect(self._after_week)

    @property
    def _mode(self) -> str:
        return str(self._view.mode())

    def _apply_snapshot(self) -> None:
        self._snap: dict = json.loads(self._view.snapshot_json())

    def _announce(self) -> None:
        self._apply_snapshot()
        self.changed.emit()

    def reload(self, mode: str, *, fetch: bool = False) -> None:
        """Read the session again. Does not consume a Widgets prompt."""
        session = self._window.session  # type: ignore[attr-defined]
        moment = _moment(session)
        today_iso = moment.date().isoformat()
        prefs = getattr(session, "preferences", None)
        clock, proceed, load, day, read_week = self._view.begin_reload(
            mode,
            prefs,
            today_iso,
            moment.hour,
            moment.minute,
            getattr(session, "selected_day", None),
            getattr(session, "account", None) is not None,
            getattr(session, "week_start", None),
            _week_holding(session, today_iso),
            bool(getattr(session, "busy", False)),
            getattr(session, "message", None),
            fetch,
            getattr(self.parent(), "_screen", ""),
            getattr(session, "load_week", None) is not None,
        )
        set_clock_24h(clock)
        if proceed is None:
            self._ask_for_week(session, load)
            self._announce()
            return
        week = None
        missed: Iterable[str] = ()
        if read_week is not None:
            week = session.built_week()
            missed = session.missed_block_ids()
        items: Sequence = ()
        if day is not None:
            on_day = getattr(week, "on_day", None)
            if on_day is not None:
                items = on_day(day)
        answer = json.loads(
            self._view.finish_reload(
                week,
                items,
                missed,
                prefs,
                json.dumps(getattr(session, "focus", None)),
                getattr(session, "assignments", None),
                session.now_ms(),
                moment,
            )
        )
        self._publish(board_from(answer["board"]), answer["block_rows"])

    def _ask_for_week(self, session: Any, week: str | None) -> None:
        if week is not None:
            session.load_week(week)
            self._view.mark_load_started()

    def _publish(self, board: DayBoard, block_rows: list[dict] | None = None) -> None:
        self._board = board
        self._up.set_rows([_qml_row(row) for row in board.up_next])
        self._done.set_rows([_qml_row(row) for row in board.done])
        rows = block_rows if block_rows is not None else []
        if self._block_rows != rows:
            self._block_rows = list(rows)
            self._blocks.set_rows(rows)
        self._announce()

    def _on_timer(self) -> None:
        """The timer ticks twice a second; the card changes only when its words do."""
        session = self._window.session  # type: ignore[attr-defined]
        changed = self._view.refresh_timer(
            json.dumps(getattr(session, "focus", None)),
            session.now_ms(),
            getattr(session, "assignments", None),
        )
        if changed is not None:
            self._announce()

    def _say(self, text: str) -> None:
        note = getattr(self.parent(), "note", None)
        if note is not None:
            note(text)

    @Slot(str)
    def finishHomework(self, assignment_id: str) -> None:
        """Mark that homework finished and say so, with Undo on the snackbar."""
        session = self._window.session  # type: ignore[attr-defined]
        first, finished = flexweek_engine.views_day_finish_plan(
            assignment_id,
            bool(getattr(session, "busy", False)),
            getattr(session, "pending_save", None) is not None,
            getattr(session, "assignments", None),
        )
        if first is not None:
            self._say(first)
        if finished is not None:
            session.complete_homework(assignment_id, True)
            save = getattr(session, "save", None)
            if save is not None:
                save()
            self._say(finished)
            self.reload(self._mode)

    def _open_day(self, session: Any, iso: str) -> None:
        opener = getattr(session, "open_day", None)
        if opener is not None:
            opener(iso)
        else:
            session.selected_day = iso

    def ensure_today(self) -> None:
        """Load today's week if looking at a different one, and reset Day to today."""
        session = getattr(self._window, "session", None)
        if self._view.today_requested(session is not None) is not None:
            self._open_day(session, _moment(session).date().isoformat())
            self._view.set_want_today(bool(getattr(session, "busy", False)))
        self._view.reset_load()
        self.reload(self._mode, fetch=True)
        self.dateOpened.emit()

    def _after_week(self) -> None:
        """Open today again once a week load that was already running when Day asked has landed.

        week_changed comes after the week is installed; busy_changed(False) comes before, so it is
        too early. The reopen waits a turn so the landing load finishes its own follow-up requests.
        """
        session = getattr(self._window, "session", None)
        landed = self._view.after_week(session is not None, bool(getattr(session, "busy", False)))
        if landed is None:
            return
        today_iso = _moment(session).date().isoformat()
        again = self._view.reopen_today(
            getattr(self.parent(), "_screen", ""),
            getattr(session, "selected_day", None),
            getattr(session, "week_start", None),
            _week_holding(session, today_iso),
            today_iso,
        )
        if again is not None:
            QTimer.singleShot(0, self, self.ensure_today)

    def _on_busy(self, busy: bool) -> None:
        if self._view.on_busy(busy, getattr(self.parent(), "_screen", "")) is not None:
            self.reload(self._mode)

    @Slot()
    def today(self) -> None:
        """Day's T key: show today again, as the rail's Day does."""
        if self._view.today_requested(True) is not None:
            self.ensure_today()

    @Slot()
    def previousDay(self) -> None:
        self._shift(-1)

    @Slot()
    def nextDay(self) -> None:
        self._shift(1)

    @Slot(int)
    def pickDay(self, day: int) -> None:
        """Open `day` in the month the side panel is showing."""
        target = self._view.pick_target(day)
        if target is not None:
            self._open(target)

    @Slot()
    def markFinished(self) -> None:
        """The Now card's Mark finished: done now, or queued until the timer's week loads."""
        outcome = self._window.session.finish_focused_homework()  # type: ignore[attr-defined]
        if flexweek_engine.views_day_finish_refreshes(outcome) is not None:
            self._on_timer()

    @Slot()
    def startAgain(self) -> None:
        """The Now card's Start again: a new timer on the same homework, never asking to replace."""
        window = self._window
        restarted = window.session.restart_finished_focus()  # type: ignore[attr-defined]
        if flexweek_engine.views_day_when_true(restarted) is not None:
            opener = getattr(window, "_open_focus_screen", None)
            if opener is not None:
                opener()

    @Slot()
    def dismissFinished(self) -> None:
        """The Now card's OK on a finished session whose homework is already done: clear the timer."""
        session = self._window.session  # type: ignore[attr-defined]
        if flexweek_engine.views_day_focus_ended(getattr(session, "focus", None)) is not None:
            session.reset_focus()

    @Slot()
    def startFocus(self) -> None:
        """Back to a running timer; else the Focus lane's hook, otherwise the Widgets Start focus path."""
        window: Any = self._window
        call, block_id, day = self._view.start_focus_plan(
            getattr(window, "_open_focus_screen", None) is not None,
            getattr(window, "start_material_focus", None) is not None,
            getattr(window, "_start_focus", None) is not None,
            self._board.focus_block_id,
            self._board.focus_day,
        )
        calls = {
            "open_focus": lambda: window._open_focus_screen(),
            "hook": lambda: window.start_material_focus(block_id, day),
            "widgets": lambda: window._start_focus(block_id, day),
            "session": lambda: window.session.start_focus(block_id, day),
        }
        calls[call]()

    def _shift(self, days: int) -> None:
        target = self._view.shift_target(days)
        if target is not None:
            self._open(target)

    def _open(self, iso: str) -> None:
        self._view.set_want_today(False)
        self._open_day(self._window.session, iso)  # type: ignore[attr-defined]
        self.reload(self._mode)
        self.dateOpened.emit()

    @Property(str, notify=changed)
    def iso(self) -> str:
        return self._snap["iso"]

    @Property(str, notify=changed)
    def leftLine(self) -> str:
        return str(self._view.left_line(self._board.left_line))

    @Property(bool, notify=changed)
    def waiting(self) -> bool:
        return self._snap["waiting"]

    @Property(str, notify=changed)
    def loadError(self) -> str:
        return self._snap["loadError"]

    @Property(int, notify=changed)
    def leftCount(self) -> int:
        return self._board.left_count

    @Property(bool, notify=changed)
    def showNow(self) -> bool:
        return bool(self._view.show_now(self._board.show_now))

    @Property(str, notify=changed)
    def nowTitle(self) -> str:
        return self._board.now_title

    @Property(str, notify=changed)
    def focusTitle(self) -> str:
        return self._board.focus_title

    @Property(int, notify=changed)
    def nowMinutes(self) -> int:
        return self._board.now_minutes

    @Property(str, notify=changed)
    def nowLine(self) -> str:
        return self._board.now_line

    @Property(bool, notify=changed)
    def nowBusy(self) -> bool:
        return self._board.now_busy

    @Property(int, notify=changed)
    def ringCount(self) -> int:
        return self._board.ring_count

    @Property(str, notify=changed)
    def ringCaption(self) -> str:
        return self._board.ring_caption

    @Property(float, notify=changed)
    def ringShare(self) -> float:
        return self._board.ring_share

    @Property(QObject, constant=True)
    def upNext(self) -> QObject:
        return self._up

    @Property(QObject, constant=True)
    def doneRows(self) -> QObject:
        return self._done

    @Property(QObject, constant=True)
    def blocks(self) -> QObject:
        return self._blocks

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def blockRows(self) -> list:
        """The blocks as a list, in the model's order, so the hours can place each against the others."""
        return self._block_rows

    @Property(int, notify=changed)
    def year(self) -> int:
        return self._snap["year"]

    @Property(int, notify=changed)
    def month(self) -> int:
        return self._snap["month"]

    @Property(int, notify=changed)
    def miniDay(self) -> int:
        return self._snap["miniDay"]

    @Property(int, notify=changed)
    def dayIndex(self) -> int:
        return self._snap["dayIndex"]

    @Property(int, notify=changed)
    def openingMinute(self) -> int:
        return self._snap["openingMinute"]

    @Property(str, notify=changed)
    def focusBlockId(self) -> str:
        return self._board.focus_block_id

    @Property(str, notify=changed)
    def timerTitle(self) -> str:
        return self._snap["timerTitle"]

    @Property(str, notify=changed)
    def timerLine(self) -> str:
        return self._snap["timerLine"]

    @Property(bool, notify=changed)
    def timerEnded(self) -> bool:
        return self._snap["timerEnded"]

    @Property(bool, notify=changed)
    def timerDone(self) -> bool:
        """Time is up on homework that is already done: only OK is left to offer."""
        return self._snap["timerDone"]

    @Property(bool, notify=changed)
    def timerCanFinish(self) -> bool:
        """Time is up on homework that is still open, which a quick focus never has."""
        return self._snap["timerCanFinish"]


def _qml_row(row: DayRow) -> dict:
    return {
        "title": row.title,
        "subtitle": row.subtitle,
        "icon": row.icon,
        "bar": row.bar,
        "fill": row.fill,
        "ink": row.ink,
        "tag": row.tag,
        "tagKind": row.tag_kind,
        "canFinish": row.can_finish,
        "assignmentId": row.assignment_id,
        "dim": row.dim,
    }
