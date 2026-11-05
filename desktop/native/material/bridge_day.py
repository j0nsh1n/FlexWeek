"""The day screen's bridge. QML reads this. It reads the session and nothing lower."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Protocol

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from desktop.native.calendar import monday_of
from desktop.native.material.bridge_rows import Rows
from desktop.native.material.day_board import (
    DIM_KEYS,
    NUDGE_KEYS,
    DayBoard,
    DayRow,
    board_for,
    read_flag,
)
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

    def __init__(self, window: QObject, parent: QObject, *, today_only: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("dayBridge")
        self._window = window
        self._today_only = today_only
        self._mode = "light"
        self._up = Rows(ROW_ROLES, self)
        self._done = Rows(ROW_ROLES, self)
        self._board = _empty()
        self._iso = ""
        self._year = 2026
        self._month = 1
        self._mini_day = 0
        self._waiting = False
        self._load_error = ""
        self._asked_week = ""
        self._load_started = False
        # Day asked for today while another week was loading; that load lands later and moves the day.
        self._want_today = False
        session = getattr(window, "session", None)
        busy = getattr(session, "busy_changed", None)
        if today_only and busy is not None:
            busy.connect(self._on_busy)
        landed = getattr(session, "week_changed", None)
        if not today_only and landed is not None and hasattr(landed, "connect"):
            landed.connect(self._after_week)
        self._publish(self._board)

    def reload(self, mode: str, *, fetch: bool = False) -> None:
        """Read the session again. Does not consume a Widgets prompt."""
        self._mode = mode if mode in ("light", "dark") else "light"
        session = self._window.session  # type: ignore[attr-defined]
        prefs = getattr(session, "preferences", None) or {}
        set_clock_24h(bool(prefs.get("clock_24h")))
        moment = datetime.fromtimestamp(session.now_ms() / 1000)
        today = moment.date()
        viewed = today if self._today_only else _chosen_day(session, today)
        self._iso = viewed.isoformat()
        self._year = viewed.year
        self._month = viewed.month
        self._mini_day = viewed.day
        items: tuple = ()
        week_start = getattr(session, "week_start", "") or ""
        account = getattr(session, "account", None)
        if self._today_only and account is not None:
            needed = monday_of(viewed.isoformat())
            if week_start != needed:
                self._iso = viewed.isoformat()
                self._year = viewed.year
                self._month = viewed.month
                self._mini_day = viewed.day
                idle = not getattr(session, "busy", False)
                if self._load_started and self._asked_week == needed and idle:
                    self._waiting = False
                    self._load_error = getattr(session, "message", "") or "Couldn't load today."
                    self.changed.emit()
                    return
                self._waiting = True
                self._load_error = ""
                self._asked_week = needed
                want = fetch or self._showing() or self._load_started
                self._load_started = False
                loader = getattr(session, "load_week", None)
                if want and callable(loader) and idle:
                    loader(needed)
                    self._load_started = True
                self.changed.emit()
                return
            self._waiting = False
            self._load_error = ""
            self._asked_week = ""
            self._load_started = False
        if account is not None and week_start:
            start = date.fromisoformat(week_start)
            if start <= viewed <= start + timedelta(days=6):
                on_day = getattr(session.built_week(), "on_day", None)
                if callable(on_day):
                    items = on_day((viewed - start).days)
        when = "today" if viewed == today else ("past" if viewed < today else "future")
        minute = moment.hour * 60 + moment.minute if when == "today" else 0
        self._waiting = False
        self._load_error = ""
        self._publish(
            board_for(
                items,
                minute=minute,
                when=when,
                nudges=read_flag(prefs, NUDGE_KEYS, True),
                dim=read_flag(prefs, DIM_KEYS, True),
                mode=self._mode,
                on=viewed,
                now=moment,
            )
        )

    def _publish(self, board: DayBoard) -> None:
        self._board = board
        self._up.set_rows([_qml_row(row) for row in board.up_next])
        self._done.set_rows([_qml_row(row) for row in board.done])
        self.changed.emit()

    def _say(self, text: str) -> None:
        note = getattr(self.parent(), "note", None)
        if callable(note):
            note(text)

    @Slot(str)
    def finishHomework(self, assignment_id: str) -> None:
        """Mark that homework finished and say so, with Undo on the snackbar."""
        if not assignment_id:
            return
        session = self._window.session  # type: ignore[attr-defined]
        if getattr(session, "busy", False) or getattr(session, "pending_save", None) is not None:
            self._say("Saving your last change… That check will work in a moment.")
            return
        item = (getattr(session, "assignments", None) or {}).get(assignment_id) or {}
        title = item.get("title") or "Homework"
        session.complete_homework(assignment_id, True)
        save = getattr(session, "save", None)
        if callable(save):
            save()
        self._say(f"Finished {title}")
        self.reload(self._mode)

    def ensure_today(self) -> None:
        """Load today's week if looking at a different one, and reset Day to today."""
        session = getattr(self._window, "session", None)
        if session is not None and not self._today_only:
            moment = datetime.fromtimestamp(session.now_ms() / 1000)
            today_iso = moment.date().isoformat()
            opener = getattr(session, "open_day", None)
            if callable(opener):
                opener(today_iso)
            else:
                session.selected_day = today_iso
            self._want_today = bool(getattr(session, "busy", False))
        self._asked_week = ""
        self._load_started = False
        self._load_error = ""
        self.reload(self._mode, fetch=True)

    def _after_week(self) -> None:
        """Open today again once a week load that was already running when Day asked has landed.

        week_changed comes after the week is installed; busy_changed(False) comes before, so it is
        too early. The reopen waits a turn so the landing load finishes its own follow-up requests.
        """
        session = getattr(self._window, "session", None)
        if not self._want_today or session is None or getattr(session, "busy", False):
            return
        self._want_today = False
        if getattr(self.parent(), "_screen", "") != "day":
            return
        today_iso = datetime.fromtimestamp(session.now_ms() / 1000).date().isoformat()
        landed_today = getattr(session, "week_start", "") == monday_of(today_iso)
        if getattr(session, "selected_day", "") != today_iso or not landed_today:
            QTimer.singleShot(0, self, self.ensure_today)

    def _showing(self) -> bool:
        return getattr(self.parent(), "_screen", "") == "myday"

    def _on_busy(self, busy: bool) -> None:
        if busy or not self._today_only:
            return
        if self._load_started or (self._waiting and self._showing()):
            self.reload(self._mode)

    @Slot()
    def previousDay(self) -> None:
        self._shift(-1)

    @Slot()
    def nextDay(self) -> None:
        self._shift(1)

    @Slot(int)
    def pickDay(self, day: int) -> None:
        """Open `day` in the month the side panel is showing."""
        if self._today_only or not 1 <= day <= 31:
            return
        try:
            target = date(self._year, self._month, day)
        except ValueError:
            return
        self._open(target.isoformat())

    @Slot()
    def startFocus(self) -> None:
        """The Focus lane's hook when it has one, otherwise the Widgets Start focus path."""
        window = self._window
        block_id = self._board.focus_block_id
        day = self._board.focus_day
        hook = getattr(window, "start_material_focus", None)
        if callable(hook):
            hook(block_id, day)
            return
        starter = getattr(window, "_start_focus", None)
        if callable(starter):
            starter(block_id, None if day < 0 else day)
            return
        self._window.session.start_focus(block_id or None, None if day < 0 else day)  # type: ignore[attr-defined]

    def _shift(self, days: int) -> None:
        if self._today_only or not self._iso:
            return
        self._open((date.fromisoformat(self._iso) + timedelta(days=days)).isoformat())

    def _open(self, iso: str) -> None:
        self._want_today = False
        session = self._window.session  # type: ignore[attr-defined]
        opener = getattr(session, "open_day", None)
        if callable(opener):
            opener(iso)
        else:
            session.selected_day = iso
        self.reload(self._mode)

    @Property(str, notify=changed)
    def iso(self) -> str:
        return self._iso

    @Property(str, notify=changed)
    def leftLine(self) -> str:
        if self._waiting:
            return "Loading…"
        if self._load_error:
            return self._load_error
        return self._board.left_line

    @Property(bool, notify=changed)
    def waiting(self) -> bool:
        return self._waiting

    @Property(str, notify=changed)
    def loadError(self) -> str:
        return self._load_error

    @Property(int, notify=changed)
    def leftCount(self) -> int:
        return self._board.left_count

    @Property(bool, notify=changed)
    def showNow(self) -> bool:
        return self._board.show_now

    @Property(str, notify=changed)
    def nowTitle(self) -> str:
        return self._board.now_title

    @Property(int, notify=changed)
    def nowMinutes(self) -> int:
        return self._board.now_minutes

    @Property(str, notify=changed)
    def nowLine(self) -> str:
        return self._board.now_line

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

    @Property(int, notify=changed)
    def year(self) -> int:
        return self._year

    @Property(int, notify=changed)
    def month(self) -> int:
        return self._month

    @Property(int, notify=changed)
    def miniDay(self) -> int:
        return self._mini_day

    @Property(str, notify=changed)
    def focusBlockId(self) -> str:
        return self._board.focus_block_id


def _chosen_day(session: object, today: date) -> date:
    selected = getattr(session, "selected_day", "") or ""
    if isinstance(selected, str) and selected:
        try:
            return date.fromisoformat(selected)
        except ValueError:
            return today
    return today


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
