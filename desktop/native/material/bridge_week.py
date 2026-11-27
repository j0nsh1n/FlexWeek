"""The week screen: rows, and every action the Week can take.

The core bridge calls `reload` and re-emits the signals the shell already listens
for. Decisions and view state live in `flexweek_engine.WeekView`; this object
forwards values into Qt models, properties, signals and slots.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from typing import Any, Protocol

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from desktop.native.material.bridge_rows import Labels, Rows
from desktop.native.weekmodel import set_clock_24h

EVERYTHING_TIMED = str(flexweek_engine.VIEWS_WEEK_EVERYTHING_TIMED)
DAY_ROLES = ("label", "name", "date", "today", "day")
BLOCK_ROLES = (
    "title",
    "day",
    "column",
    "start",
    "end",
    "fill",
    "ink",
    "category",
    "detail",
    "detailStart",
    "past",
    "blockId",
    "assignmentId",
    "homework",
    "done",
    "fresh",
    "indent",
    "under",
)


def occurrence_row(item: Any, mode: str, *, dim: bool, gone: bool, fresh: bool, missed: bool = False) -> dict:
    """One QML block row from a week occurrence. Day and Week share this shape."""
    return json.loads(flexweek_engine.views_week_occurrence_row(item, mode, dim, gone, fresh, missed))


def overlapped(rows: list[dict]) -> list[dict]:
    """Items that share time overlap instead of splitting the lane (Jonathan, 2026-11-08)."""
    rows[:] = json.loads(flexweek_engine.views_week_overlapped(json.dumps(rows)))
    return rows


# "1 h" and "30 min": a number keeps its unit on one line, so a wrapped card never leaves the unit alone.
LENGTH_GAP = re.compile(r"(\d) (h|min)\b")
HOMEWORK_ROLES = ("title", "minutes", "blockId", "assignmentId", "detail", "tag", "tagKind", "reason")
# The solver's own lines: at most an hour of room is "Cutting it close", at most three is "Tight".
DANGER_SLACK_MIN = int(flexweek_engine.VIEWS_WEEK_DANGER_SLACK_MIN)
TIGHT_SLACK_MIN = int(flexweek_engine.VIEWS_WEEK_TIGHT_SLACK_MIN)
SLACK_TAGS = {
    "danger": ("Cutting it close", "cutting"),
    "tight": ("Tight", "tight"),
    "ok": ("Plenty of time", "plenty"),
}
DAY_MIN = int(flexweek_engine.VIEWS_WEEK_DAY_MIN)
# A status line after Plan my homework counts as its answer for this long.
PLAN_WINDOW_S = float(flexweek_engine.VIEWS_WEEK_PLAN_WINDOW_S)
# A block that just landed keeps its landing motion this long, across the refreshes a save causes.
FRESH_S = float(flexweek_engine.VIEWS_WEEK_FRESH_S)


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
    return bool(flexweek_engine.views_week_bool_pref(prefs, key, default))


def _steady_ms() -> int:
    return int(time.monotonic() * 1000)


def _moment(session: Any) -> datetime:
    return datetime.fromtimestamp(session.now_ms() / 1000)


def _call_optional(owner: Any, name: str, default: Any) -> Any:
    fn = getattr(owner, name, None)
    if fn is None:
        return default
    return fn()


class WeekBridge(QObject):
    """Blocks, day headers, hour labels, homework that still needs a time, and the week's actions."""

    changed = Signal()
    blocksChanged = Signal()
    homeworkChanged = Signal()
    planFinished = Signal()
    # Today was pressed, even when this week is already the one shown: the grid shows the line again.
    todayAsked = Signal()

    def __init__(self, window: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("weekBridge")
        self._window = window
        self._view = flexweek_engine.WeekView()
        self._blocks = Rows(BLOCK_ROLES, self)
        self._homework = Rows(HOMEWORK_ROLES, self)
        self._days = Rows(DAY_ROLES, self)
        self._hours = Labels(self)
        self._published: dict[str, object] = {}
        self._apply_snapshot()
        self._hours.set_rows(self._hour_labels)
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

    @property
    def _target_week(self) -> str | None:
        return self._view.target_week()

    @_target_week.setter
    def _target_week(self, value: str | None) -> None:
        self._view.set_target_week(value)

    @property
    def _loading_week(self) -> str | None:
        return self._view.loading_week()

    @_loading_week.setter
    def _loading_week(self, value: str | None) -> None:
        self._view.set_loading_week(value)

    def _apply_snapshot(self) -> None:
        snap = json.loads(self._view.snapshot_json())
        self._block_rows: list[dict] = snap["blockRows"]
        self._homework_rows: list[dict] = snap["homeworkRows"]
        self._day_rows: list[dict] = snap["dayRows"]
        self._day_headers: list[str] = snap["dayHeaders"]
        self._hour_labels: list[str] = snap["hourLabels"]
        self._time_words: str = snap["timeWords"]
        self._all_timed: bool = snap["allTimed"]
        self._can_plan: bool = snap["canPlan"]
        self._listed_count: int = snap["listedCount"]
        self._leftover_words: str = snap["leftoverWords"]
        self._left_words: str = snap["leftWords"]
        self._now_day: int = snap["nowDay"]
        self._now_column: int = snap["nowColumn"]
        self._now_minute: int = snap["nowMinute"]
        self._columns: int = snap["columns"]
        self._shown_days: list[int] = snap["shownDays"]
        self._drag_step: int = snap["dragStep"]

    # -- reading the week ------------------------------------------------

    def reload(self, mode: str) -> None:
        """Read the session again. Does not consume a Widgets prompt."""
        session = self._window.session  # type: ignore[attr-defined]
        ready = self._view.prepare_reload(
            session.preferences, session.week_start, session.account is not None
        )
        set_clock_24h(self._view.clock_24h())
        if ready is None:
            self._apply_snapshot()
            self._publish()
            return
        moment = _moment(session)
        self._view.finish_reload(
            mode,
            session.built_week(),
            session.missed_block_ids(),
            json.dumps(session.homework_time_needed()),
            bool(_call_optional(session, "plan_can_place", False)),
            _call_optional(session, "homework_remainders", ()),
            json.dumps(self._window._unfinished_items()),  # type: ignore[attr-defined]
            moment.date().isoformat(),
            moment.hour,
            moment.minute,
            _steady_ms(),
            FRESH_S,
        )
        self._apply_snapshot()
        self._publish()

    def _left_line(self) -> str:
        """The Widgets line above the week: "N overdue · N left from last week", from the same list."""
        return str(flexweek_engine.views_week_left_line(json.dumps(self._window._unfinished_items())))  # type: ignore[attr-defined]

    @staticmethod
    def _tag_for(item: Any, start: date, moment: datetime) -> tuple[str, str]:
        """How much room this homework has before it is due. No deadline, no tag."""
        del start
        return tuple(
            flexweek_engine.views_week_tag_for(
                item.due, int(item.minutes), moment.date().isoformat(), moment.hour, moment.minute
            )
        )

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
        note = getattr(self.parent(), "note", None)
        if note is not None:
            note(text, action=action)

    @Slot(str)
    def _on_status(self, message: str) -> None:
        """What a plan the student asked for says when it placed nothing new."""
        if self._view.on_status(message, _steady_ms(), PLAN_WINDOW_S) is not None:
            # The window puts the words on the snackbar, with no Undo and keeping an Undo already there.
            self.planFinished.emit()

    @Slot(str)
    def _on_planned(self, _said: str) -> None:
        self._view.on_planned()
        self.planFinished.emit()

    @Slot(bool, str)
    def _on_save_finished(self, ok: bool, _message: str) -> None:
        words = self._view.on_save_finished(ok)
        if words is not None:
            self._note(words)

    # -- actions ---------------------------------------------------------

    @Slot()
    def plan(self) -> None:
        """Plan my homework: the window's own call, so Widgets and Material plan the same way."""
        if self._view.begin_plan(_steady_ms()) is not None:
            self._window._plan_with_left_over()  # type: ignore[attr-defined]

    @Slot()
    def planLeft(self) -> None:
        """Plan into this week: the Widgets button's own call."""
        self._window._plan_left()  # type: ignore[attr-defined]

    @Slot()
    def didLeft(self) -> None:
        """Mark as finished: the Widgets button's own call."""
        self._window._did_left()  # type: ignore[attr-defined]

    @Slot(str, int, int)
    def placeHomework(self, block_id: str, day: int, start: int) -> None:
        """A drawer card let go on `day` at minute `start`: the same hand move the Widgets week makes,
        on the student's drag step."""
        session = self._window.session  # type: ignore[attr-defined]
        plan = self._view.place_homework_plan(
            json.dumps(session.blocks), block_id, day, start, bool(session.busy)
        )
        if plan is None:
            return
        snapped, end, judge = plan
        if judge is not None:
            problem = flexweek_engine.views_week_hand_move_problem(
                json.dumps(session.judge_hand_move(block_id, -1, day, snapped, end))
            )
            if problem is not None:
                # Nothing is changed, so there is nothing for UNDO to take back.
                self._note(problem, action="")
                return
        session.place_block(block_id, -1, day, snapped, end)

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def dayRows(self) -> list:
        """The shown days as the headers name them, for Move to day...'s list."""
        return self._day_rows

    @Slot(str, int, int, int, int)
    def moveBlock(self, block_id: str, from_day: int, day: int, start: int, end: int) -> None:
        """A block let go by the mouse, or sent by Move to day..., on `day` from `start` to `end`: the one
        hand-move rule the plain look uses, one Undo step, and the same words in the notice."""
        session = self._window.session  # type: ignore[attr-defined]
        plan = self._view.move_block_plan(
            json.dumps(session.blocks), block_id, day, start, end, bool(session.busy)
        )
        if plan is None:
            return
        move_start, move_end, judge = plan
        if judge is not None:
            problem = flexweek_engine.views_week_hand_move_problem(
                json.dumps(session.judge_hand_move(block_id, from_day, day, move_start, move_end))
            )
            if problem is not None:
                # Nothing is changed, so there is nothing for UNDO to take back.
                self._note(problem, action="")
                return
        session.place_block(block_id, from_day, day, move_start, move_end)

    @Slot(str, int)
    def duplicateBlock(self, block_id: str, day: int) -> None:
        """The plain look's Duplicate for this block: its preview, then the copy saved as one Undo step."""
        window = self._window
        session = window.session  # type: ignore[attr-defined]
        kept = (session.selected_block_id, session.selected_occurrence_day)
        session.selected_block_id = block_id
        session.selected_occurrence_day = flexweek_engine.views_week_optional_day(day)
        try:
            window._duplicate_selected()  # type: ignore[attr-defined]
        finally:
            session.selected_block_id, session.selected_occurrence_day = kept

    @Slot(str, int)
    def copyBlock(self, block_id: str, day: int) -> None:
        """The plain look's Copy: the block goes on the clipboard, for Ctrl+V."""
        self._window.session.copy_block(block_id, flexweek_engine.views_week_optional_day(day))  # type: ignore[attr-defined]

    @Slot()
    def pasteCopied(self) -> None:
        """Ctrl+V: the plain look's Paste, into the day on view (Day) or today (Week)."""
        self._window._paste_clipboard()  # type: ignore[attr-defined]

    @Slot(result=bool)
    def hasCopied(self) -> bool:
        """Something is on the clipboard and no save is under way (the plain look greys Paste then), so
        the free-time menu offers Paste here."""
        session = self._window.session  # type: ignore[attr-defined]
        return bool(flexweek_engine.views_week_has_copied(session.clipboard, bool(session.busy)))

    @Slot(int, int)
    def pasteHere(self, day: int, start_min: int) -> None:
        """Paste here: the plain look's Paste, onto that day from that minute, through its preview."""
        self._window._paste_at(day, start_min)  # type: ignore[attr-defined]

    @Slot(str)
    def planOne(self, identifier: str) -> None:
        """Place now, and Enter on a card: that homework at the first free gap from now that fits it."""
        session = self._window.session  # type: ignore[attr-defined]
        target = self._view.plan_one_target(json.dumps(session.blocks), identifier, _steady_ms())
        if target is not None:
            session.solve(only={target}, earliest_first=True)

    @Slot(str)
    def toggleDone(self, assignment_id: str) -> None:
        """Click homework to mark it finished, or to open it again. Undo takes it back."""
        session = self._window.session  # type: ignore[attr-defined]
        plan = self._view.toggle_done_plan(json.dumps(session.assignments), assignment_id, bool(session.busy))
        if plan is None:
            return
        finished, words = plan
        session.complete_homework(assignment_id, finished)
        session.save()
        self._view.record_done_after_save(words, bool(session.busy))

    @Slot()
    def previous(self) -> None:
        self._shift(-7)

    @Slot()
    def next(self) -> None:
        self._shift(7)

    @Slot(result=str)
    def pickerAnchor(self) -> str:
        """The Monday of the week on view: the month the Go to date picker opens on."""
        return str(self._view.picker_anchor(self._window.session.week_start))  # type: ignore[attr-defined]

    @Slot(result=str)
    def todayIso(self) -> str:
        return str(self._window.session.today_iso())  # type: ignore[attr-defined]

    @Slot(str)
    def goToDate(self, iso: str) -> None:
        """A day picked in the Go to date month: the week that holds it."""
        picked = flexweek_engine.views_week_parse_date(iso)
        if picked is not None:
            self._load_target(self._window.session.shown_week_of(picked))  # type: ignore[attr-defined]

    @Slot()
    def toggleWeekends(self) -> None:
        session = self._window.session  # type: ignore[attr-defined]
        ticket, wanted, updated_json = self._view.toggle_weekends_start(json.dumps(session.preferences))
        session.preferences = json.loads(updated_json)
        self._window._material_page.publish()  # type: ignore[attr-defined]

        def kept(ok: bool) -> None:
            rollback = self._view.toggle_weekends_finish(ticket, ok, json.dumps(session.preferences))
            if rollback is None:
                return
            restored_json, message = rollback
            session.preferences = json.loads(restored_json)
            self._window._material_page.publish()  # type: ignore[attr-defined]
            self._note(message, action="")

        kept(bool(session.save_preferences({"show_weekends": wanted}, kept)))

    @Slot()
    def today(self) -> None:
        session = self._window.session  # type: ignore[attr-defined]
        target = session.shown_week_of(_moment(session).date().isoformat())
        self._load_target(target)
        self.todayAsked.emit()

    def _shift(self, days: int) -> None:
        moved = self._view.shift_target(days, self._window.session.week_start)  # type: ignore[attr-defined]
        if moved is not None:
            self._load_target(moved)

    def _load_target(self, target: str) -> None:
        if self._view.load_target(target, bool(self._window.session.busy)) is not None:  # type: ignore[attr-defined]
            self._flush_target()

    def _flush_target(self) -> None:
        session = self._window.session  # type: ignore[attr-defined]
        target = self._view.begin_flush(session.week_start, bool(session.busy))
        if target is None:
            return
        session.load_week(target)
        self._view.finish_flush(bool(session.busy))

    def _settle_navigation(self) -> None:
        session = self._window.session  # type: ignore[attr-defined]
        if self._view.settle_navigation(session.week_start, bool(session.busy)) is not None:
            # Owned by this bridge: a bridge dropped before the turn ends takes the timer with it.
            QTimer.singleShot(0, self, self._flush_target)

    @Slot(bool)
    def _on_busy_changed(self, busy: bool) -> None:
        if flexweek_engine.views_week_when_idle(bool(busy)) is not None:
            self._settle_navigation()

    @Slot()
    def _on_week_changed(self) -> None:
        if flexweek_engine.views_week_when_idle(bool(self._window.session.busy)) is not None:  # type: ignore[attr-defined]
            self._settle_navigation()

    @Slot(object)
    def _on_account_changed(self, _account: object) -> None:
        self._view.on_account_changed()

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
        return self._day_headers

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def hourLabels(self) -> list:
        return self._hour_labels

    @Property(int, notify=changed)
    def columns(self) -> int:
        return self._columns

    @Property(int, notify=changed)
    def dragStep(self) -> int:
        return self._drag_step

    @Property(int, notify=changed)
    def nowDay(self) -> int:
        return self._now_day

    @Property(int, notify=changed)
    def nowColumn(self) -> int:
        """Today's column on the week grid, or -1 when today is not shown."""
        return self._now_column

    @Property(int, notify=changed)
    def nowMinute(self) -> int:
        return self._now_minute

    @Property(int, notify=homeworkChanged)
    def homeworkCount(self) -> int:
        return len(self._homework_rows)

    @Property(str, notify=homeworkChanged)
    def leftWords(self) -> str:
        """ "N overdue · N left from last week", or nothing when no homework is left over."""
        return self._left_words

    @Property(int, notify=homeworkChanged)
    def listedCount(self) -> int:
        """How many homework the drawer lists, each once: a homework with a card and a "with no time" line
        is one."""
        return self._listed_count

    @Property(str, notify=homeworkChanged)
    def timeWords(self) -> str:
        """What the drawer says when no card is listed: whether any homework still needs a time."""
        return self._time_words

    @Property(bool, notify=homeworkChanged)
    def canPlan(self) -> bool:
        """Whether Plan my homework has anything to place, listed as a card or not."""
        return self._can_plan

    @Property(str, notify=homeworkChanged)
    def planLabel(self) -> str:
        """The plan button's words: a student who places homework by hand asks for ideas, so Suggest times."""
        return str(flexweek_engine.views_week_plan_label(self._window.session.preferences))  # type: ignore[attr-defined]

    @Property(bool, notify=homeworkChanged)
    def allTimed(self) -> bool:
        return self._all_timed

    @Property(str, notify=homeworkChanged)
    def leftoverWords(self) -> str:
        """Homework with minutes no session holds, one line each: they have no card to drag."""
        return self._leftover_words
