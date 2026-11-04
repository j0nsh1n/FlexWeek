"""The week screen: rows, and every action the Week can take.

The core bridge calls `reload` and re-emits the signals the shell already listens
for. This object does not touch HTTP, SQL, or the engine. It reads and acts only
through NativeSession.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from desktop.native.material.bridge_rows import Labels, Rows
from desktop.native.material.theme import event_category, paint_for_category
from desktop.native.reuse import due_point
from desktop.native.weekmodel import (
    clock_label,
    due_label,
    length_label,
    range_label,
    set_clock_24h,
)

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_ROLES = ("label", "name", "date", "today")
BLOCK_ROLES = (
    "title",
    "day",
    "start",
    "end",
    "fill",
    "ink",
    "category",
    "detail",
    "past",
    "blockId",
    "assignmentId",
    "homework",
    "done",
    "fresh",
)
HOMEWORK_ROLES = ("title", "minutes", "blockId", "assignmentId", "detail", "tag", "tagKind", "reason")
# The solver's own lines: at most an hour of room is "Cutting it close", at most three is "Tight".
DANGER_SLACK_MIN = 60
TIGHT_SLACK_MIN = 3 * 60
SLACK_TAGS = {
    "danger": ("Cutting it close", "cutting"),
    "tight": ("Tight", "tight"),
    "ok": ("Plenty of time", "plenty"),
}
SNACK_MS = 10000
DAY_MIN = 24 * 60
# A status line after Plan my homework counts as its answer for this long.
PLAN_WINDOW_S = 30.0
# A block that just landed keeps its landing motion this long, across the refreshes a save causes.
FRESH_S = 1.0


class _Session(Protocol):
    account: dict | None
    preferences: dict | None
    week_start: str
    blocks: list[dict]
    plan_counts: tuple[int, int]
    busy: bool

    def now_ms(self) -> int: ...

    def homework_time_needed(self) -> list: ...

    def built_week(self) -> Any: ...


class _Window(Protocol):
    session: _Session


def _bool_pref(prefs: dict, key: str, default: bool) -> bool:
    """A preference another lane may not have landed yet. Only an explicit false turns it off."""
    value = prefs.get(key)
    return value if isinstance(value, bool) else default


class WeekBridge(QObject):
    """Blocks, day headers, hour labels, homework that still needs a time, and the week's actions."""

    changed = Signal()
    blocksChanged = Signal()
    homeworkChanged = Signal()
    planFinished = Signal()

    def __init__(self, window: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("weekBridge")
        self._window = window
        self._block_rows: list[dict] = []
        self._homework_rows: list[dict] = []
        self._day_rows: list[dict] = []
        self._hour_labels: list[str] = [clock_label(hour * 60) for hour in range(24)]
        self._blocks = Rows(BLOCK_ROLES, self)
        self._homework = Rows(HOMEWORK_ROLES, self)
        self._days = Rows(DAY_ROLES, self)
        self._hours = Labels(self)
        self._hours.set_rows(self._hour_labels)
        self._now_day = -1
        self._now_minute = 0
        self._columns = 7
        self._week_key = ""
        self._seen: set[tuple[str, int]] = set()
        self._fresh_until: dict[tuple[str, int], float] = {}
        self._done_after_save = ""
        self._said_plan = 0.0
        self._noted = ""
        self._published: dict[str, object] = {}
        self._target_week: str | None = None
        self._loading_week: str | None = None
        self._weekend_save = 0
        self._connect_session()

    def _connect_session(self) -> None:
        session = getattr(self._window, "session", None)
        for name, slot in (
            ("planned", self._on_planned),
            ("save_finished", self._on_save_finished),
            ("status", self._on_status),
            ("busy_changed", self._on_busy_changed),
            ("week_changed", self._on_week_changed),
            ("account_changed", self._on_account_changed),
        ):
            signal = getattr(session, name, None)
            if signal is not None and hasattr(signal, "connect"):
                signal.connect(slot)

    # -- reading the week ------------------------------------------------

    def reload(self, mode: str) -> None:
        """Read the session again. Does not consume a Widgets prompt."""
        session = self._window.session  # type: ignore[attr-defined]
        prefs = session.preferences or {}
        set_clock_24h(bool(prefs.get("clock_24h")))
        self._hour_labels = [clock_label(hour * 60) for hour in range(24)]
        self._columns = 7 if _bool_pref(prefs, "show_weekends", True) else 5
        dim = _bool_pref(prefs, "dim_completed", True)
        block_rows: list[dict] = []
        homework_rows: list[dict] = []
        day_rows: list[dict] = []
        self._now_day = -1
        self._now_minute = 0
        if session.account is None or not session.week_start:
            self._block_rows, self._homework_rows, self._day_rows = [], [], []
            self._seen = set()
            self._publish()
            return
        start = date.fromisoformat(session.week_start)
        moment = datetime.fromtimestamp(session.now_ms() / 1000)
        today = moment.date()
        offset = (today - start).days
        if 0 <= offset <= 6:
            self._now_day = offset
            self._now_minute = moment.hour * 60 + moment.minute
        for index in range(self._columns):
            day = start + timedelta(days=index)
            day_rows.append(
                {
                    "label": f"{DAYS[index]} {day.day}",
                    "name": DAYS[index],
                    "date": str(day.day),
                    "today": index == self._now_day,
                }
            )
        week = session.built_week()
        # A week that ended is all past, a week ahead has nothing past, this week goes by the clock.
        keys: set[tuple[str, int]] = set()
        fresh_ok = self._week_key == session.week_start and bool(self._seen)
        clock = time.monotonic()
        for item in week.occurrences:
            day = int(item.day)
            if day >= self._columns:
                continue
            end = int(item.end)
            if offset > 6:
                gone = True
            elif offset < 0:
                gone = False
            else:
                gone = day < offset or (day == offset and end <= self._now_minute)
            fill, ink = paint_for_category(item.category, mode)
            key = (item.block_id, day)
            keys.add(key)
            if fresh_ok and key not in self._seen:
                self._fresh_until[key] = clock + FRESH_S
            block_rows.append(
                {
                    "title": item.title,
                    "day": day,
                    "start": int(item.start),
                    "end": end,
                    "fill": fill,
                    "ink": ink,
                    "category": event_category(item.category),
                    "detail": range_label(int(item.start), end),
                    "past": dim and (gone or bool(item.done)),
                    "blockId": item.block_id,
                    "assignmentId": item.assignment_id or "",
                    "homework": bool(item.work and item.assignment_id),
                    "done": bool(item.done),
                    "fresh": self._fresh_until.get(key, 0.0) > clock,
                }
            )
        for item in getattr(week, "waiting", ()):
            tag, kind = self._tag_for(item, start, moment)
            parts = []
            if item.due:
                parts.append(f"Due {due_label(item.due, today)}")
            parts.append(length_label(int(item.minutes)))
            homework_rows.append(
                {
                    "title": item.title,
                    "minutes": int(item.minutes),
                    "blockId": item.block_id,
                    "assignmentId": item.assignment_id or "",
                    "detail": " · ".join(parts),
                    "tag": tag,
                    "tagKind": kind,
                    "reason": item.reason,
                }
            )
        self._week_key = session.week_start
        self._seen = keys
        self._fresh_until = {key: until for key, until in self._fresh_until.items() if until > clock}
        self._block_rows, self._homework_rows, self._day_rows = block_rows, homework_rows, day_rows
        self._publish()

    @staticmethod
    def _tag_for(item: Any, start: date, moment: datetime) -> tuple[str, str]:
        """How much room this homework has before it is due. No deadline, no tag."""
        if not item.due:
            return "", "plain"
        point = due_point(item.due, start.isoformat())
        if point is None:
            return SLACK_TAGS["ok"]
        now_at = (moment.date() - start).days * DAY_MIN + moment.hour * 60 + moment.minute
        room = point[0] * DAY_MIN + point[1] - now_at - int(item.minutes)
        if room <= DANGER_SLACK_MIN:
            return SLACK_TAGS["danger"]
        if room <= TIGHT_SLACK_MIN:
            return SLACK_TAGS["tight"]
        return SLACK_TAGS["ok"]

    def _publish(self) -> None:
        # A clock tick reads the same week again. Rebuilding the models would drop hover and focus.
        for name, model, rows in (
            ("blocks", self._blocks, self._block_rows),
            ("homework", self._homework, self._homework_rows),
            ("days", self._days, self._day_rows),
            ("hours", self._hours, self._hour_labels),
        ):
            if self._published.get(name) != rows:
                self._published[name] = list(rows)
                model.set_rows(rows)
        self.blocksChanged.emit()
        self.homeworkChanged.emit()
        self.changed.emit()

    # -- the snackbar ----------------------------------------------------

    def _note(self, text: str, *, action: str = "UNDO") -> None:
        shell = self.parent()
        if shell is None or not hasattr(shell, "note"):
            return
        shell.note(text, action=action)
        self._noted = text

    @Slot()
    def _clear_snack(self) -> None:
        """Take down this bridge's own line. Another screen's line, or none, stays as it is."""
        shell = self.parent()
        if shell is not None and shell.property("snackText") == self._noted:
            self._note("")

    @Slot(str)
    def _on_status(self, message: str) -> None:
        """What a plan the student asked for says when it placed nothing new."""
        if not self._said_plan or not message or message.endswith("…"):
            return
        asked, self._said_plan = self._said_plan, 0.0
        if time.monotonic() - asked < PLAN_WINDOW_S:
            self._note(message)
            self.planFinished.emit()

    @Slot(str)
    def _on_planned(self, _said: str) -> None:
        self._said_plan = 0.0
        self.planFinished.emit()

    @Slot(bool, str)
    def _on_save_finished(self, ok: bool, _message: str) -> None:
        words, self._done_after_save = self._done_after_save, ""
        if ok and words:
            self._note(words)

    # -- actions ---------------------------------------------------------

    @Slot()
    def plan(self) -> None:
        """Plan my homework: the window's own call, so Widgets and Material plan the same way."""
        if not self._homework_rows:
            return
        self._said_plan = time.monotonic()
        self._window._plan_with_left_over()  # type: ignore[attr-defined]

    @Slot(str, int, int)
    def placeHomework(self, block_id: str, day: int, start: int) -> None:
        """A drawer card let go on `day` at minute `start`: the same hand move the Widgets week makes."""
        session = self._window.session  # type: ignore[attr-defined]
        block = next((item for item in session.blocks if item["id"] == block_id), None)
        if block is None or not 0 <= day < self._columns:
            return
        length = int(block.get("duration_min") or 0)
        if length <= 0:
            return
        start = max(0, min(start, DAY_MIN - length))
        session.place_block(block_id, -1, day, start, start + length)

    @Slot(str)
    def planOne(self, identifier: str) -> None:
        """The keyboard's way to give one card a time: plan only that homework, as Find a new time does."""
        session = self._window.session  # type: ignore[attr-defined]
        target = next(
            (
                block["id"]
                for block in session.blocks
                if block["id"] == identifier or block.get("assignment_id") == identifier
            ),
            None,
        )
        if target:
            session.solve(only={target})

    @Slot(str)
    def toggleDone(self, assignment_id: str) -> None:
        """Click homework to mark it finished, or to open it again. Undo takes it back."""
        session = self._window.session  # type: ignore[attr-defined]
        item = session.assignments.get(assignment_id)
        if item is None or session.busy:
            return
        title = item.get("title") or "Homework"
        finished = not bool(item.get("completed"))
        session.complete_homework(assignment_id, finished)
        session.save()
        if session.busy:
            self._done_after_save = f"Finished {title}." if finished else f"{title} is back."

    @Slot()
    def previous(self) -> None:
        self._shift(-7)

    @Slot()
    def next(self) -> None:
        self._shift(7)

    @Slot()
    def toggleWeekends(self) -> None:
        session = self._window.session  # type: ignore[attr-defined]
        previous = dict(session.preferences or {})
        current = _bool_pref(previous, "show_weekends", True)
        wanted = not current
        self._weekend_save += 1
        ticket = self._weekend_save
        session.preferences = {**previous, "show_weekends": wanted}
        self._window._material_page.publish()  # type: ignore[attr-defined]

        def kept(ok: bool) -> None:
            if ok or ticket != self._weekend_save:
                return
            latest = dict(session.preferences or {})
            if "show_weekends" in previous:
                latest["show_weekends"] = previous["show_weekends"]
            else:
                latest.pop("show_weekends", None)
            session.preferences = latest
            self._window._material_page.publish()  # type: ignore[attr-defined]
            self._note("Couldn't save the weekend setting. Try again.", action="")

        if not session.save_preferences({"show_weekends": wanted}, kept):
            kept(False)

    @Slot()
    def today(self) -> None:
        session = self._window.session  # type: ignore[attr-defined]
        moment = datetime.fromtimestamp(session.now_ms() / 1000).date()
        target = (moment - timedelta(days=moment.weekday())).isoformat()
        self._load_target(target)

    def _shift(self, days: int) -> None:
        session = self._window.session  # type: ignore[attr-defined]
        base = self._target_week or session.week_start
        if not base:
            return
        monday = (date.fromisoformat(base) + timedelta(days=days)).isoformat()
        self._load_target(monday)

    def _load_target(self, target: str) -> None:
        session = self._window.session  # type: ignore[attr-defined]
        self._target_week = target
        if not session.busy:
            self._flush_target()

    def _flush_target(self) -> None:
        session = self._window.session  # type: ignore[attr-defined]
        if self._target_week and not session.busy:
            target = self._target_week
            if target == session.week_start:
                self._target_week = None
                return
            self._loading_week = target
            session.load_week(target)
            if not session.busy:
                self._loading_week = None
                self._target_week = None

    def _settle_navigation(self) -> None:
        session = self._window.session  # type: ignore[attr-defined]
        finished, self._loading_week = self._loading_week, None
        if finished is not None and self._target_week == finished:
            self._target_week = None
        if self._target_week == session.week_start:
            self._target_week = None
        if self._target_week and not session.busy:
            QTimer.singleShot(0, self._flush_target)

    @Slot(bool)
    def _on_busy_changed(self, busy: bool) -> None:
        if not busy:
            self._settle_navigation()

    @Slot()
    def _on_week_changed(self) -> None:
        if not self._window.session.busy:  # type: ignore[attr-defined]
            self._settle_navigation()

    @Slot(object)
    def _on_account_changed(self, _account: object) -> None:
        self._target_week = None
        self._loading_week = None

    # -- what QML reads --------------------------------------------------

    @Property(QObject, constant=True)
    def blocks(self) -> QObject:
        return self._blocks

    @Property(QObject, constant=True)
    def homework(self) -> QObject:
        return self._homework

    @Property(QObject, constant=True)
    def days(self) -> QObject:
        return self._days

    @Property(QObject, constant=True)
    def hours(self) -> QObject:
        return self._hours

    @Property("QVariantList", notify=blocksChanged)  # type: ignore[arg-type]
    def blockRows(self) -> list:
        return self._block_rows

    @Property("QVariantList", notify=homeworkChanged)  # type: ignore[arg-type]
    def homeworkRows(self) -> list:
        return self._homework_rows

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def dayHeaders(self) -> list:
        return [row["label"] for row in self._day_rows]

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def hourLabels(self) -> list:
        return self._hour_labels

    @Property(int, notify=changed)
    def columns(self) -> int:
        return self._columns

    @Property(int, notify=changed)
    def nowDay(self) -> int:
        return self._now_day

    @Property(int, notify=changed)
    def nowMinute(self) -> int:
        return self._now_minute

    @Property(int, notify=homeworkChanged)
    def homeworkCount(self) -> int:
        return len(self._homework_rows)
