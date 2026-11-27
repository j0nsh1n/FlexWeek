"""Account, week drafts and solver results for the native desktop window."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import QObject, QTimer, Signal

from backend import clock as wall_clock
from backend.weeks import current_week_start
from desktop.native.calendar import (
    hand_move,
    local_stamp,
    repeat_changes,
    stored_weeks_of,
    week_start_on,
)
from desktop.native.client import SESSION_ENDED, ApiError, NativeClient
from desktop.native.files import (
    export_day_payload,
    export_week_payload,
    parse_import_payload,
)
from desktop.native.focus import (
    add_focus_time_plan,
    advance_begin,
    advance_plan,
    apply_auto_complete_blocks,
    apply_credit_blocks,
    auto_complete_plan,
    begin_state,
    credit_enqueue_decision,
    credit_plan,
    drop_missing,
    elapsed_minutes,
    end_early_decision,
    finish_after_load,
    finish_focused_plan,
    finish_intent_on_request,
    focus_candidates,
    focus_spotify_decision,
    focus_spotify_open_failed,
    mutes_alerts,
    now_and_next,
    now_next_line,
    persist_payload,
    quick_focus_homework,
    rebase_state,
    release_held,
    restart_finished_plan,
    restore_decision,
    scheduled_blocks_of,
    split_held,
    start_allowed,
    start_decision,
    start_target,
    take_break_plan,
    tick_step,
    toggle_pause_decision,
)
from desktop.native.hours.geometry import drag_step
from desktop.native.kept import KeptSession
from desktop.native.kept_alerts import KeptReminders
from desktop.native.look import sanitize_look
from desktop.native.remind import clock_parts
from desktop.native.reuse import (
    clear_stale_pins,
    settle_placements,
    week_label,
)
from desktop.native.weekmodel import (
    WeekModel,
    build_week,
    homework_time_sentence,
)

WEEK_OVER = str(flexweek_engine.PLAN_WEEK_OVER)


def _plan_clock(moment: datetime) -> dict[str, object]:
    return {
        "today_iso": moment.date().isoformat(),
        "hour": moment.hour,
        "minute": moment.minute,
        "second": moment.second,
        "microsecond": moment.microsecond,
    }


def first_placed(trace: dict, targets: object) -> tuple[int, int] | None:
    """Where the first homework a plan gave a time is, by day and then minute."""
    return flexweek_engine.session_plan_first_placed(json.dumps(trace), targets)


LEFT_NAMED = 2


def left_sentence(left: object) -> str:
    """Homework with minutes the plan could not give a time, each named with its minutes: "History essay
    still has 10 min with no time." Nothing for no homework, so a plan that left nothing says nothing."""
    return str(flexweek_engine.session_plan_left_sentence(left))


def plan_sentence(placed: int, waiting: int, left: object = ()) -> str:
    """How many targeted sessions a plan placed. `waiting` is homework whose sessions found no room;
    `left` is homework with minutes no session holds, by title and minutes."""
    return str(flexweek_engine.session_plan_sentence(placed, waiting, left))


def spread_ready_sentence(title: str, minutes: int, due: str, today: str) -> str:
    """Spread preview: names the homework and how much is ready before it is due."""
    return str(flexweek_engine.session_spread_ready_sentence(title, minutes, due, today))


HOURS_REFUSED = "Check the days and times in Study hours and Protected time."


# Blocks and homework are checked and written as the engine does it (engine/service/src/blocks.rs and
# homework_saves.rs, matched to the old pydantic models on 2,500 blocks and 2,000 homework saves); one it
# refuses raises ValueError.
HOMEWORK_FIELDS = frozenset(flexweek_engine.homework_fields())


def _checked_block(block: dict) -> dict:
    return json.loads(flexweek_engine.checked_block(json.dumps(block)))


def _checked_homework(item: dict) -> dict:
    return json.loads(flexweek_engine.checked_homework(json.dumps(item)))


def _week_write(week_start: str, blocks: list[dict], revision: int | list[int]) -> dict:
    return json.loads(flexweek_engine.save_week_write(week_start, json.dumps(blocks), json.dumps(revision)))


# What the status line says when a save or a week load goes as expected. A reminder on the status line
# outranks these, so they are not allowed to replace it.
ROUTINE_STATUS = frozenset(
    ("Saving…", "Saved.", "Saving preferences…", "Saved preferences.", "Loading…", "This week.")
)


def _late_summary(moved: int) -> str:
    return str(flexweek_engine.session_late_summary(moved))


def _draft_field(name: str, *, writable: bool = False) -> property:
    def read(session: NativeSession) -> Any:
        return session._draft_view(name)

    def write(session: NativeSession, value: Any) -> None:
        session._draft_command("set", fields={name: value})

    return property(read, write if writable else None)


class _MonthCache(dict):
    """clear() and item writes reach the Rust cache: sign-out and the month tests call them on the
    object this property returns, and the settings preview reads it as a dict."""

    def __init__(self, session: NativeSession) -> None:
        self._session = session
        dict.__init__(self, session._views.cache_mapping())

    def clear(self) -> None:
        dict.clear(self)
        self._session._views.clear_cache()

    def __setitem__(self, key: tuple, value: dict) -> None:
        dict.__setitem__(self, key, value)
        self._session._views.insert_cache(str(key[0]), str(key[1]), value)

    def __delitem__(self, key: tuple) -> None:
        dict.__delitem__(self, key)
        self._session._views.remove_cache(str(key[0]), str(key[1]))


class _MonthPrefetch(set):
    """clear(), add and discard reach the in-flight set: a save's tests call clear() on it."""

    def __init__(self, session: NativeSession) -> None:
        self._session = session
        set.__init__(self, session._views.prefetch_members())

    def clear(self) -> None:
        set.clear(self)
        self._session._views.clear_prefetch()

    def add(self, key: tuple) -> None:
        set.add(self, key)
        self._session._views.add_prefetch(str(key[0]), str(key[1]))

    def discard(self, key: tuple) -> None:
        set.discard(self, key)
        self._session._views.discard_prefetch(str(key[0]), str(key[1]))


class NativeSession(QObject):
    account_changed = Signal(object)
    recovery_codes = Signal(list)
    week_changed = Signal()
    busy_changed = Signal(bool)
    status = Signal(str)
    # The session kept at the last sign-in no longer works: the launch goes to sign-in.
    resume_failed = Signal()
    # Each save's outcome, for words that must wait for it: (stored, what the status line says).
    save_finished = Signal(bool, str)
    # Toast words for a hand move that has just been saved, including one that waited out a save.
    hand_placed = Signal(str)
    # A change to School or an activity from this week on reached later weeks that kept a change of
    # their own: the server's words for which and what, to show without blocking.
    repeats_kept = Signal(str)
    # A save that made a restore point first, or made a weekly time that doubles a hand-made copy in
    # later weeks: the point's id ("" for none) and the weeks' starts, oldest first.
    save_answered = Signal(str, list)
    plan_conflicts = Signal(list)
    planned = Signal(str)
    focus_changed = Signal()
    focus_replace_needed = Signal(str, str)
    alerts = Signal(list)
    alarm_due = Signal(object)

    def __init__(
        self, database: str | Path, parent: QObject | None = None, kept: KeptSession | None = None
    ) -> None:
        super().__init__(parent)
        self.client = NativeClient(database, self)
        self.client.expired.connect(self._on_expired)
        self.client.told.connect(self._told)
        self.account: dict | None = None
        # Keep me signed in: where this database's kept session lives, and the choice on the sign-in
        # card at the last sign-in. A session resumed at launch was kept, so it stays kept.
        self.kept = kept
        self.keep_signed_in = True
        self._resuming = False
        self._draft_views: dict[str, Any] = {}
        self._fixture_draft_values: dict[str, Any] = {}
        self._draft_versions: dict[str, int] = {}
        self._draft_command("clear", week_start=current_week_start())
        self._views = flexweek_engine.ViewState(wall_clock.today().isoformat())
        # New homework to give a time once its save lands, when the student plans as they add.
        self._plan_after_save: set[str] = set()
        # Sessions to plan once the open week is read again: a save wrote them through the stored
        # Mondays of a week on screen from another day.
        self._plan_after_load: set[str] = set()
        # Sessions Allow splitting made: a plan that includes them places them all this week, with no fair
        # share, until one such plan is saved. `_split_planned` are those in the plan now being saved.
        self._split_whole: set[str] = set()
        self._split_planned: set[str] = set()
        self._replan_after_save = False
        # Replan all asked during a save that ended by reading another week: run once that week is in place.
        self._replan_after_load = False
        self._spread_after_save: tuple[str, int, str] | None = None
        self._allow_split_pending: str | None = None
        self.clipboard: dict | None = None
        self.routines: dict[str, dict] = {}
        self.saved_weeks: list[str] = []
        self.preferences: dict | None = None
        self.late_preview: dict | None = None
        self.spread_preview: dict | None = None
        self._seen_unfinished: set[str] = set()
        self._weeks_ticket = 0
        self._routines_ticket = 0
        self._prefs_ticket = 0
        self.focus: dict | None = None
        self._fresh_plan = False
        # The last plan's homework given a time and still without one: what its toast and its bar say.
        self.plan_counts: tuple[int, int] = (0, 0)
        # Homework with a session the last plan left waiting for a time: Material's "Placed N of M".
        self.plan_open = 0
        self.plan_remainders: list[tuple[str, int]] = []
        # The day and minute of the first homework the last plan gave a time, to scroll to.
        self.plan_first: tuple[int, int] | None = None
        # Place now's answer once it placed the block: "Placed Math worksheet on Thu 5:45 PM."
        self.placed_where = ""
        self.needs_time: dict[str, str] = {}
        # Registered in this sitting, so setup can open before the account's preferences arrive.
        self.new_account = False
        self.focus_store: dict[int, dict | None] = {}
        self.look: dict = sanitize_look(None)
        self.now_ms = wall_clock.now_ms
        self._focus_busy = False
        self._pending_focus: dict | None = None
        # Mark finished can wait for the timer's week. The week itself may be null, so null is not
        # "nothing is waiting".
        self._finish_focus_waiting = False
        self._finish_focus_week: str | None = None
        # Material 3's focus rules (mute reminders, finish the block) apply only while Material is the
        # surface in use. The window hands in the question; the Widgets styles never set it.
        self.material_owns: Callable[[], bool] | None = None
        self._held_alerts: list[dict] = []
        # Finished focus sessions, with their length, not yet added to their homework.
        self._credits_waiting: list[tuple[dict, int, bool]] = []
        self.fired_reminders: set[str] = set()
        # Reminders kept on screen as cards; they follow the clock and any edit to today's blocks.
        self.reminder_cards = KeptReminders(
            self.todays_reminder_blocks, lambda: self._clock()["minute"], self.fired_reminders.discard, self
        )
        self.week_changed.connect(self.reminder_cards.sync)
        self.fired_alarms: set[str] = set()
        self.snoozed_alarms: dict[str, int] = {}
        self.last_alarm_check: int | None = None
        self._alarms = flexweek_engine.AlarmQueue()
        self.played_songs: set[str] = set()
        self._focus_after_restore = False
        self.restore_points: list[dict] = []
        self.restore_preview: dict | None = None
        self.storage_info: dict | None = None
        self.transfer_preview: dict | None = None
        self.timer_presets: list[dict] = []
        self.reminder_limits: dict = {}
        self.recovery_remaining: int | None = None
        self.split_preview: dict | None = None
        # The week Plan was last asked for in: its answer may show homework left in an earlier week.
        self.plan_asked_week: str | None = None
        # One block let go while a save is in flight. The save's reply replaces the week, so the move
        # is applied on the next turn after that reply, not during it. A later let-go replaces it.
        self._hand_waiting: tuple[str, int, int, int, int] | None = None
        # What setup has kept and not yet written, one request at a time: preferences, then study
        # hours, then the week. A second request would replace the first on this session.
        self._setup = flexweek_engine.SetupQueue()
        # The app's one sync host. Pairing, removal and Sync now use it; this session does not start
        # another.
        self._sync_host: QObject | None = None
        self.busy_changed.connect(self._resume_pending)
        self._reminder_ticket = 0
        self._reminder_fetching: str | None = None
        self._reminder_week: str | None = None
        self._reminder_blocks: list[dict] = []
        self._reminder_trace: dict | None = None

    week_start = _draft_field("week_start", writable=True)
    blocks = _draft_field("blocks", writable=True)
    revision = _draft_field("revision", writable=True)
    assignments = _draft_field("assignments")
    dirty_assignments = _draft_field("dirty_assignments")
    trace = _draft_field("trace", writable=True)
    dirty = _draft_field("dirty", writable=True)
    conflict = _draft_field("conflict", writable=True)
    pending_save = _draft_field("pending_save", writable=True)
    repeats = _draft_field("repeats")
    last_save_refused = _draft_field("last_save_refused")
    _stored_parts = _draft_field("stored_parts", writable=True)
    _undo = _draft_field("undo")
    _assignments_basis = _draft_field("assignments_basis")
    _repeat_send = _draft_field("repeat_send")
    _saved_repeats = _draft_field("saved_repeats")

    def _draft_view(self, name: str) -> Any:
        if name not in self._draft_views:
            value: Any = self.client.view(f"drafts.{name}")
            if name == "dirty_assignments":
                value = set(value)
            self._draft_views[name] = value
            if name in {"blocks", "assignments", "dirty_assignments"}:
                self._fixture_draft_values[name] = deepcopy(value)
        return self._draft_views[name]

    def _accept_draft_versions(self, answer: dict) -> None:
        versions = answer["versions"]
        for name, version in versions.items():
            if version != self._draft_versions.get(name):
                self._draft_views.pop(name, None)
                self._fixture_draft_values.pop(name, None)
        self._draft_versions = versions

    def _flush_fixture_drafts(self) -> None:
        # Older desktop fixtures edit projected blocks or homework in place.
        changes = {
            field: self._draft_views[field]
            for field, previous in self._fixture_draft_values.items()
            if self._draft_views[field] != previous
        }
        if "dirty_assignments" in changes:
            changes["dirty_assignments"] = sorted(changes["dirty_assignments"])
        if changes:
            self._accept_draft_versions(self.client.command({"cmd": "drafts_set", "fields": changes}))

    def _draft_command(self, name: str, **payload: Any) -> dict:
        self._flush_fixture_drafts()
        answer = self.client.command({"cmd": f"drafts_{name}", **payload})
        self._accept_draft_versions(answer)
        return answer

    def _selection(self) -> dict:
        return {
            "selected_day": self.selected_day,
            "selected_block_id": self.selected_block_id,
            "selected_occurrence_day": self.selected_occurrence_day,
        }

    def _send_week_effect(self, effect: dict, done: Callable[[dict], None]) -> None:
        def replied(data: dict | None, error: ApiError | None) -> None:
            answer = self._draft_command(
                "reply",
                effect_id=effect["id"],
                data=data,
                error=None if error is None else {"status": error.status, "message": error.message},
                selection=self._selection(),
                shifted_week=bool(self.first_weekday),
                now=(
                    datetime.fromtimestamp(self.now_ms() / 1000).strftime("%Y-%m-%dT%H:%M")
                    if error is None and effect.get("clock") else None
                ),
                ids=[str(uuid4()) for _ in range(effect.get("ids", 0))],
            )
            if answer["action"] != "ignore":
                done(answer)

        self.client.request(
            effect["method"], effect["path"], effect["body"],
            lambda data: replied(data, None), lambda error: replied(None, error),
        )

    # Which request is the latest, whether the session is busy, and the status line live in the session in
    # Rust (engine/app/src/session/status.rs); the signals stay here.
    def _status(self) -> dict:
        return self.client.view("status")

    @property
    def busy(self) -> bool:
        return bool(self._status()["busy"])

    @busy.setter
    def busy(self, value: bool) -> None:
        self.client.command({"cmd": "set_busy", "busy": bool(value)})

    @property
    def message(self) -> str:
        return str(self._status()["message"])

    @message.setter
    def message(self, text: str) -> None:
        self.client.command({"cmd": "say", "text": text})

    @property
    def _ticket(self) -> int:
        return int(self._status()["ticket"])

    def _say(self, text: str) -> None:
        self.message = text
        self.status.emit(text)

    def _begin(self, planning: bool = False) -> int:
        ticket = int(self.client.command({"cmd": "begin", "planning": bool(planning)})["ticket"])
        self.busy_changed.emit(True)
        return ticket

    @property
    def planning(self) -> bool:
        """A plan was asked for and its result is not back yet."""
        return bool(self._status()["planning"])

    def _alive(self, ticket: int) -> bool:
        return ticket == self._ticket

    def _idle(self, ticket: int) -> bool:
        if not self.client.command({"cmd": "idle", "ticket": ticket})["idle"]:
            return False
        self._went_idle()
        return True

    def _went_idle(self) -> None:
        """The session has just stopped being busy with the latest request."""
        self.busy_changed.emit(False)
        if self._credits_waiting:
            # After the reply that made this call has been put in place.
            QTimer.singleShot(0, self, self._credit_when_free)
        if self._refollow_week:
            # A first day of the week picked while this request ran: its week once the reply is in place.
            QTimer.singleShot(0, self, self._follow_week)

    def _credit_when_free(self) -> None:
        if self._credits_waiting and not self.busy:
            self._credit_waiting_sessions()

    def _fail(self, ticket: int, error: ApiError) -> None:
        planning = self.planning
        if self._idle(ticket):
            if planning and error.status == 0:
                self._say("Can't reach FlexWeek, so nothing was planned. Try again.")
            else:
                self._say(error.message)

    def _drop_setup(self) -> None:
        """Unsent setup answers belong to the account that gave them."""
        self._setup.clear()

    @property
    def setup_prefs(self) -> dict:
        return json.loads(self._setup.prefs())

    @setup_prefs.setter
    def setup_prefs(self, value: dict) -> None:
        self._setup.set_prefs(json.dumps(value))

    @property
    def setup_work_windows(self) -> list[dict] | None:
        windows = self._setup.windows()
        return None if windows is None else json.loads(windows)

    @setup_work_windows.setter
    def setup_work_windows(self, value: list[dict] | None) -> None:
        self._setup.set_windows(None if value is None else json.dumps(value))

    @property
    def setup_week(self) -> bool:
        return self._setup.week()

    @setup_week.setter
    def setup_week(self, value: bool) -> None:
        self._setup.set_week(value)

    def _drop_other_setup(self, account_id: object) -> None:
        """A different account does not keep the previous one's unsent setup answers."""
        if self.account is None or self.account["id"] != account_id:
            self._drop_setup()

    def _clear_local(self) -> None:
        if self.account is not None:
            self.focus_store.pop(self.account["id"], None)
        self._credits_waiting.clear()
        self.account = None
        self._drop_setup()
        self._refollow_week = False
        self._draft_views.clear()
        self._fixture_draft_values.clear()
        self._draft_command("clear", week_start=self.shown_week_of(wall_clock.today().isoformat()))
        self._split_whole = set()
        self._split_planned = set()
        self.planner_view = "week"
        self.selected_day = wall_clock.today().isoformat()
        self.day_data = None
        self.selected_month = None
        self.month_data = None
        self._month_data_gen = 0
        self._month_cache.clear()
        self._month_gen += 1
        self._month_prefetching.clear()
        self.armed_category = None
        self.selected_block_id = None
        self.selected_occurrence_day = None
        self._day_ticket += 1
        self._month_ticket += 1
        self._replan_after_save = False
        self._plan_after_load = set()
        self._replan_after_load = False
        self.clipboard = None
        self.routines = {}
        self.saved_weeks = []
        self.preferences = None
        self.new_account = False
        self.late_preview = None
        self.spread_preview = None
        self._seen_unfinished.clear()
        self.needs_time = {}
        self._reset_focus(persist=False)
        self._held_alerts.clear()
        self.fired_reminders.clear()
        self.reminder_cards.clear()
        self.fired_alarms.clear()
        self.snoozed_alarms.clear()
        self.last_alarm_check = None
        self._alarms.clear()
        self.played_songs.clear()
        self._focus_after_restore = False
        self.restore_points = []
        self.restore_preview = None
        self.storage_info = None
        self.transfer_preview = None
        self.timer_presets = []
        self.reminder_limits = {}
        self.recovery_remaining = None
        self.split_preview = None
        self._reminder_ticket += 1
        self._reminder_fetching = None
        self._reminder_week = None
        self._reminder_blocks = []
        self._reminder_trace = None

    @property
    def planner_view(self) -> str:
        return self._views.planner_view()

    @planner_view.setter
    def planner_view(self, value: str) -> None:
        self._views.set_planner_view(value)

    @property
    def selected_day(self) -> str:
        return self._views.selected_day()

    @selected_day.setter
    def selected_day(self, value: str) -> None:
        self._views.set_selected_day(value)

    @property
    def day_data(self) -> dict | None:
        return self._views.day_data()

    @day_data.setter
    def day_data(self, value: dict | None) -> None:
        self._views.set_day_data(value)

    @property
    def selected_month(self) -> str | None:
        return self._views.selected_month()

    @selected_month.setter
    def selected_month(self, value: str | None) -> None:
        self._views.set_selected_month(value)

    @property
    def month_data(self) -> dict | None:
        return self._views.month_data()

    @month_data.setter
    def month_data(self, value: dict | None) -> None:
        self._views.set_month_data(value)

    @property
    def first_weekday(self) -> int:
        return self._views.first_weekday()

    @first_weekday.setter
    def first_weekday(self, value: int) -> None:
        self._views.set_first_weekday(value)

    @property
    def _refollow_week(self) -> bool:
        return self._views.refollow_week()

    @_refollow_week.setter
    def _refollow_week(self, value: bool) -> None:
        self._views.set_refollow_week(value)

    @property
    def armed_category(self) -> str | None:
        return self._views.armed_category()

    @armed_category.setter
    def armed_category(self, value: str | None) -> None:
        self._views.set_armed_category(value)

    @property
    def selected_block_id(self) -> str | None:
        return self._views.selected_block_id()

    @selected_block_id.setter
    def selected_block_id(self, value: str | None) -> None:
        self._views.set_selected_block_id(value)

    @property
    def selected_occurrence_day(self) -> int | None:
        return self._views.selected_occurrence_day()

    @selected_occurrence_day.setter
    def selected_occurrence_day(self, value: int | None) -> None:
        self._views.set_selected_occurrence_day(value)

    @property
    def _day_ticket(self) -> int:
        return self._views.day_ticket()

    @_day_ticket.setter
    def _day_ticket(self, value: int) -> None:
        self._views.set_day_ticket(value)

    @property
    def _month_ticket(self) -> int:
        return self._views.month_ticket()

    @_month_ticket.setter
    def _month_ticket(self, value: int) -> None:
        self._views.set_month_ticket(value)

    @property
    def _month_gen(self) -> int:
        return self._views.month_gen()

    @_month_gen.setter
    def _month_gen(self, value: int) -> None:
        self._views.set_month_gen(value)

    @property
    def _month_data_gen(self) -> int:
        return self._views.month_data_gen()

    @_month_data_gen.setter
    def _month_data_gen(self, value: int) -> None:
        self._views.set_month_data_gen(value)

    @property
    def _month_cache(self) -> dict:
        return _MonthCache(self)

    @_month_cache.setter
    def _month_cache(self, value: dict) -> None:
        self._views.replace_cache(value)

    @property
    def _month_prefetching(self) -> set:
        return _MonthPrefetch(self)

    def arm_category(self, category: str) -> None:
        self.armed_category = category

    def select_block(self, block_id: str | None, day: int | None) -> None:
        self.selected_block_id = block_id
        self.selected_occurrence_day = day

    def shown_week_of(self, iso_day: str) -> str:
        """The first date of the week on screen that holds `iso_day`, from the week's first day."""
        return week_start_on(iso_day, self.first_weekday)

    def today_column(self, iso_day: str) -> int | None:
        """Which day of the open week `iso_day` is (0 its first day), or None when it is not in it."""
        return self._views.column_of(iso_day, self.week_start)

    def _ensure_selected_day(self) -> None:
        # A day of the open week stays, also when that week still starts on the day weeks started on
        # before the first day changed: the new week is opened from it.
        self._views.ensure_selected_day(self.week_start)

    def _held(self) -> bool:
        return self._draft_command("meta")["held"]

    def parked_unsaved_week(self) -> str | None:
        return self._draft_command("parked_held")["week"]

    def autosave_due(self) -> bool:
        return self._draft_command("autosave", signed_in=self.account is not None)["save"]

    def start_leaving(self, limit_ms: int, again: str) -> bool:
        if self.account is None:
            return False
        return self._draft_command("leaving_start", limit_ms=limit_ms, again=again)["waiting"]

    def poll_leaving(self, poll_ms: int) -> dict:
        return self._draft_command("leaving_poll", poll_ms=poll_ms)

    def _refresh_view(self) -> None:
        self._view_act(self._views.refresh(self._view_world()))

    def set_view(self, view: str) -> None:
        self._view_act(self._views.set_view(view, self._view_world()))

    def open_day(self, iso_day: str) -> None:
        self._view_act(self._views.open_day(iso_day, self._view_world()))

    def today_iso(self) -> str:
        return datetime.fromtimestamp(self.now_ms() / 1000).date().isoformat()

    def open_month(self, month: str | None = None) -> None:
        self._view_act(self._views.open_month(month, self._view_world()))

    def shift_month(self, amount: int) -> None:
        self._view_act(self._views.shift_month(amount, self._view_world()))

    def follow_first_weekday(self, first_weekday: int) -> None:
        """A new first day of the week: the month's rows change, so what was kept is asked for again,
        and the open week becomes the one from that day holding the selected day. Changes not yet
        saved are saved first, in the week they were made in."""
        self._view_act(self._views.follow_first_weekday(first_weekday, self._view_world()))

    def _rebase_focus(self) -> None:
        """The focus timer names its week and day: keep its date, in the week from the new first day."""
        moved = rebase_state(self.focus, self.first_weekday)
        if moved is None:
            return
        self.focus = moved
        self._persist_focus()

    def _follow_week(self) -> None:
        """Open the week from the chosen first day once nothing is held; a save still going on calls
        this again when it lands."""
        self._view_act(self._views.follow_week(self._view_world()))

    def _fetch_day(self) -> None:
        self._view_act(self._views.fetch_day(self._view_world()))

    def _fetch_month(self) -> None:
        self._view_act(self._views.fetch_month(self._view_world()))

    def _month_path(self, month: str) -> str:
        return str(self._views.month_path(month))

    def _prefetch_open_week_month(self) -> None:
        """Warm the month most likely to be opened without holding up the week."""
        self._view_act(self._views.prefetch(self._view_world()))

    def _invalidate_months(self) -> None:
        self._views.invalidate_months()

    def _view_world(self) -> str:
        account = self.account
        return json.dumps(
            {
                "signed_in": account is not None,
                "account_id": None if account is None else str(account["id"]),
                "week_start": self.week_start,
                "today": self.today_iso(),
                "busy": self.busy,
                "held": self._held(),
                "parked": bool(self.parked_unsaved_week()),
            }
        )

    def _view_act(self, effect: str) -> None:
        decided = json.loads(effect)
        if decided["set_week_start"] is not None:
            self._draft_command("set_week_start", week_start=decided["set_week_start"])
        if decided["rebase_focus"]:
            self._rebase_focus()
        if decided["load_week"] is not None:
            self.load_week(decided["load_week"])
        if decided["emit_before_request"]:
            self.week_changed.emit()
        if decided["request"] is not None:
            self._view_request(decided["request"])
        if decided["emit"]:
            self.week_changed.emit()

    def _view_request(self, request: dict) -> None:
        kind = str(request["kind"])
        token = int(request["token"])
        asked = str(request["asked"])
        generation = int(request["gen"])
        owner = str(request["owner"])

        def ok(data: dict) -> None:
            self._view_answered(kind, token, asked, generation, owner, data, None)

        def err(error: ApiError) -> None:
            self._view_answered(kind, token, asked, generation, owner, None, error.message)

        self.client.request(request["method"], request["path"], None, ok, err)

    def _view_answered(
        self,
        kind: str,
        token: int,
        asked: str,
        generation: int,
        owner: str,
        data: dict | None,
        error: str | None,
    ) -> None:
        account = self.account
        answer = json.loads(
            self._views.view_reply(
                json.dumps(
                    {
                        "kind": kind,
                        "token": token,
                        "asked": asked,
                        "gen": generation,
                        "owner": owner,
                        "account_id": None if account is None else str(account["id"]),
                        "data": data,
                        "error": error,
                    }
                )
            )
        )
        if answer["say"] is not None:
            self._say(answer["say"])
        if answer["emit"]:
            self.week_changed.emit()

    def _keep_session(self) -> None:
        if self.kept is None:
            return
        self.kept.note_sign_in()
        token = self.client.session_token() if self.keep_signed_in else None
        if token:
            self.kept.keep(token)
        else:
            self.kept.forget()

    def _forget_session(self) -> None:
        if self.kept is not None:
            self.kept.forget()

    def resume(self) -> None:
        """Open the week with the session kept at the last sign-in, when there is one and it still
        works. One that the server has ended, by expiry or by signing out elsewhere, is forgotten."""
        token = self.kept.token() if self.kept is not None else None
        if token is None or self.account is not None or self.busy:
            return
        self._start_flow({"cmd": "resume", "token": token})
        self._resuming = True

    # Signing in, up and out, and the account's own changes, run in the session
    # (engine/app/src/session/account.rs): it sends the request,
    # reads the answer, and says what happened; what follows here is the window's own part.
    def _start_flow(self, command: dict) -> dict:
        answer = self.client.command(command)
        self.busy_changed.emit(True)
        # The words it began with, even when it finished at once (a sign-out with no one signed in).
        self.status.emit(answer["said"])
        return answer

    def _told(self, event: dict) -> None:
        kind = event["kind"]
        if kind == "signed_in":
            self._resuming = False
            data = event["account"]
            self._drop_other_setup(data["id"])
            self._went_idle()
            self.account = {"id": data["id"], "username": data["username"]}
            if event["how"] == "resume":
                self.keep_signed_in = True
            else:
                self._keep_session()
            self.account_changed.emit(self.account)
            # Sign-in does not clear the window the way sign-out does. Drop a finish that belonged
            # to the previous account before this account's week opens.
            self._clear_finish_intent()
            self.load_week(self.week_start, discard=True)
        elif kind == "registered":
            data = event["account"]
            self._drop_other_setup(data["id"])
            self.account = {"id": data["id"], "username": data["username"]}
            self.new_account = True
            # Registration does not clear the window the way sign-out does. Drop a finish that
            # belonged to the previous account, as sign-in does.
            self._clear_finish_intent()
            self.busy_changed.emit(False)
            self.account_changed.emit(self.account)
            self.recovery_codes.emit(list(event["codes"] or []))
            self.status.emit(self.message)
        elif kind == "auth_failed":
            if event["forget"]:
                self._forget_session()
            if self._resuming:
                # Before the words, so the sign-in card is there to show them.
                self._resuming = False
                self.resume_failed.emit()
            if event["idle"]:
                self._went_idle()
                self.status.emit(self.message)
        elif kind == "password_replaced":
            self._went_idle()
            if event["account"] is not None:
                data = event["account"]
                self.account = {"id": data["id"], "username": data["username"]}
                # The new password came with a new session, and the kept one no longer works.
                self._keep_session()
            self.status.emit(self.message)
            self.week_changed.emit()
        elif kind == "codes_replaced":
            self._went_idle()
            self.recovery_remaining = int(event["remaining"])
            self.recovery_codes.emit(list(event["codes"]))
            self.status.emit(self.message)
        elif kind == "account_deleted":
            self._forget_session()
            if self.kept is not None and event["owner"] is not None:
                self.kept.forget_look(event["owner"])
            self._clear_local()
            self.busy_changed.emit(False)
            self.account_changed.emit(None)
            self.week_changed.emit()
            self.status.emit(self.message)
        elif kind == "signed_out":
            if event["account_id"] is not None:
                self.focus_store.pop(event["account_id"], None)
            self._clear_local()
            self.busy_changed.emit(False)
            self.account_changed.emit(None)
            self.week_changed.emit()
            self.focus_changed.emit()
            self.status.emit(self.message)

    def _on_expired(self) -> None:
        self._forget_session()
        self.client.command({"cmd": "cancel"})
        self.busy_changed.emit(False)
        self.client.reset()
        self._clear_local()
        self.account_changed.emit(None)
        self.week_changed.emit()
        self._say(SESSION_ENDED)

    def register(self, username: str, password: str) -> None:
        self._start_flow(
            {"cmd": "register", "username": username, "password": password, "keep": bool(self.keep_signed_in)}
        )

    def login(self, username: str, password: str) -> None:
        self._start_flow(
            {"cmd": "login", "username": username, "password": password, "keep": bool(self.keep_signed_in)}
        )

    def finish_recovery(self) -> None:
        if self.account is None:
            return
        # Kept only now. Kept at registration, quitting before this page would open the week at the
        # next launch and the recovery codes would never be shown again.
        self._keep_session()
        self.selected_day = self.today_iso()
        self.load_week(self.shown_week_of(self.selected_day))

    def logout(self) -> None:
        # Forgotten first, so a sign-out that fails to reach the server still leaves nothing to resume.
        self._forget_session()
        account_id = None if self.account is None else self.account["id"]
        finished = self._start_flow({"cmd": "logout", "account_id": account_id})["finished"]
        if finished is not None:
            self._told(finished)

    def load_week(
        self, week_start: str | None = None, *, discard: bool = False, said: str | None = None
    ) -> None:
        """Load a week from the server. `said` is what the status line says once it is loaded."""
        if self.account is None:
            return
        if self.busy:
            return
        # A finish waiting for its own week is dropped when the student asks for a different one.
        # The press itself asks for the timer's week, which keeps the wait. A request for another
        # week while a load is in flight never reaches this check: the busy guard above ignores it.
        if finish_intent_on_request(
            waiting=self._finish_focus_waiting,
            pending=self._finish_focus_week,
            requested=week_start,
        ) == "drop":
            self._clear_finish_intent()
        route = self._draft_command(
            "load", requested=week_start or self.shown_week_of(wall_clock.today().isoformat()),
            first_weekday=self.first_weekday, discard=discard, selection=self._selection(),
        )
        if route["action"] == "keep":
            # Nothing was loaded, so a finish waiting on this request would stay set.
            self._clear_finish_intent()
            return
        if route["action"] == "restore":
            selection = route["selection"]
            self.selected_day = selection["selected_day"]
            self.selected_block_id = selection["selected_block_id"]
            self.selected_occurrence_day = selection["selected_occurrence_day"]
            self._say(route["words"])
            self._refresh_view()
            self.week_changed.emit()
            self._restore_focus()
            self._drop_missing_focus()
            self._finish_loaded_focus(loaded=True)
            return
        ticket = self._begin()
        self._say("Loading…")
        reply = self._draft_command("fetch", ticket=ticket, start=route["start"], said=said)

        def received(answer: dict) -> None:
            if answer["action"] == "request":
                self._send_week_effect(answer["effect"], received)
                return
            if answer["action"] == "load_failed":
                self._week_read_failed(ticket, answer["message"], assignments=answer["assignments"])
                return
            if not self._idle(ticket):
                return
            self._split_planned = set()
            self._ensure_selected_day()
            self._say(answer["words"])
            self._refresh_view()
            self.week_changed.emit()
            self._restore_focus()
            self._drop_missing_focus()
            self._finish_loaded_focus(loaded=True)
            self._fetch_weeks()
            self._fetch_routines()
            self._fetch_preferences()
            self._fetch_restore_points()
            self._fetch_recovery_status()
            self._prefetch_open_week_month()
            self._plan_waiting_for_load()

        self._send_week_effect(reply["effect"], received)

    def _week_read_failed(self, ticket: int, message: str, *, assignments: bool) -> None:
        if not self._alive(ticket):
            return
        clear_plan, refresh_day = flexweek_engine.week_load_failed(
            self.week_start, assignments, self.selected_day, self.first_weekday,
        )
        if clear_plan:
            self._plan_after_load = set()
            self._replan_after_load = False
        if refresh_day:
            self._ensure_selected_day()
            self._refresh_view()
        if self._idle(ticket):
            self._say(message)
        self.week_changed.emit()
        self._finish_loaded_focus(loaded=False)

    def _plan_waiting_for_load(self) -> None:
        planned, self._plan_after_load = self._plan_after_load, set()
        if planned:
            QTimer.singleShot(0, lambda: self.solve(only=planned, join=True))
        replan, self._replan_after_load = self._replan_after_load, False
        if replan:
            QTimer.singleShot(0, lambda: self.solve(everything=True))

    def reload(self) -> None:
        self._draft_command("reload")
        self.load_week(self.week_start, discard=True, said=flexweek_engine.week_reload_words())

    def use_sync_host(self, host: QObject | None) -> None:
        """Use the sync host the app already started. This session does not start a second one."""
        self._sync_host = host

    def _sync_service(self) -> tuple[QObject, Any, int] | None:
        host = self._sync_host
        account = self.account
        service = getattr(host, "service", None) if host is not None else None
        if host is None or service is None or account is None:
            return None
        return host, service, int(account["id"])

    def begin_pairing(self, done: Callable[[Any, Exception | None], None]) -> bool:
        """Ask for a pairing code on the app's sync host. A host that is not running yet is started
        first, as Pair a phone does. False with no host or account, and then `done` is not called."""
        host = self._sync_host
        account = self.account
        if host is None or account is None:
            return False
        user_id = int(account["id"])

        def pair(service: Any) -> None:
            from desktop.native.devices import begin_pairing as start

            start(host, service, user_id, done)

        service = getattr(host, "service", None)
        if service is not None:
            pair(service)
            return True
        ensure = getattr(host, "ensure", None)
        if not callable(ensure):
            return False

        def ready(started: Any) -> None:
            if started is None:
                from desktop.native.devices import NO_SYNC_WORDS

                done(None, RuntimeError(NO_SYNC_WORDS))
                return
            pair(started)

        ensure(ready)
        return True

    def pairing_status(self) -> dict | None:
        """The open pairing code's state, tries left and expiry, or None with no running service."""
        found = self._sync_service()
        if found is None:
            return None
        _host, service, _user_id = found
        return service.pair_status()

    def end_pairing(self, done: Callable[[Any, Exception | None], None]) -> bool:
        """Close the open pairing code. False with no host, service or account."""
        found = self._sync_service()
        if found is None:
            return False
        host, service, _user_id = found
        from desktop.native.devices import end_pairing

        end_pairing(host, service, done)
        return True

    def unlink_phone(self, device_id: str, done: Callable[[Any, Exception | None], None]) -> bool:
        """Remove a linked phone. False with no host, service or account."""
        found = self._sync_service()
        if found is None:
            return False
        host, service, user_id = found
        from desktop.native.devices import unlink_phone

        unlink_phone(host, service, user_id, device_id, done)
        return True

    def sync_linked_phones(self, done: Callable[[Any, Exception | None], None]) -> bool:
        """Sync every linked phone. False with no host, service or account."""
        found = self._sync_service()
        if found is None:
            return False
        host, service, _user_id = found
        from desktop.native.devices import sync_linked_phones

        sync_linked_phones(host, service, done)
        return True

    def stored_weeks(self) -> list[tuple[str, int]]:
        """The stored (Monday) weeks the open week is read from, with the revisions this window holds:
        the week itself from Monday, both stored weeks it covers from any other day."""
        if self._stored_parts:
            return [(str(part["week_start"]), int(part["revision"])) for part in self._stored_parts]
        if isinstance(self.revision, list):
            return list(zip(stored_weeks_of(self.week_start), map(int, self.revision), strict=True))
        return [(self.week_start, int(self.revision))]

    def accept_remote_week(self, who: str) -> bool:
        """A linked phone's edits arrived. Unsaved edits here are kept and marked as a conflict, and
        the week is not reloaded. False while a request is in flight, so the caller can ask again."""
        answer = self._draft_command("remote_change", signed_in=self.account is not None, who=who)
        if answer["conflict"]:
            self.week_changed.emit()
        if answer["words"] is not None:
            self.load_week(self.week_start, discard=True, said=answer["words"])
        return answer["accepted"]

    def _touch(
        self,
        label: str | None = None,
        keep: set[str] | frozenset[str] = frozenset(),
        *,
        blocks: list[dict] | None = None,
        homework: tuple[dict, ...] | list[dict] = (),
        repeats: list[dict] | None = None,
        intents: list[dict] | None = None,
    ) -> None:
        blocks = self.blocks if blocks is None else blocks
        assignments = {**self.assignments, **{item["id"]: item for item in homework}}
        overdue = self._overdue_assignment_ids(assignments)
        after_deadline = {
            block["id"] for block in blocks
            if block.get("start") and block.get("assignment_id") in overdue
        }
        blocks, lost = settle_placements(
            blocks, assignments, self.week_start, keep, after_deadline=after_deadline
        )
        blocks = clear_stale_pins(blocks)
        self._draft_command(
            "touch", label=label, blocks=blocks, put_homework=homework,
            repeats=repeats, hold_repeats=intents,
        )
        if self.selected_block_id not in {item["id"] for item in blocks}:
            self.select_block(None, None)
        for note in lost:
            self.needs_time[note["block_id"]] = note["message"]
        self._forget_settled_notes()
        self.week_changed.emit()
        if lost:
            self.plan_conflicts.emit(lost)

    def _forget_settled_notes(self) -> None:
        waiting = {
            block["id"]
            for block in self.blocks
            if block.get("kind") == "flexible" and not block.get("completed") and not block.get("start")
        }
        self.needs_time = {key: value for key, value in self.needs_time.items() if key in waiting}

    def plan_notes(self) -> dict | None:
        """The last plan's explanations, or after an edit the reason each session lost its time."""
        if self.trace is not None:
            return self.trace
        if not self.needs_time:
            return None
        return {
            "placed": [],
            "explanations": [{"block_id": key, "message": value} for key, value in self.needs_time.items()],
        }

    def check_block(self, block: dict) -> dict:
        return _checked_block(block)

    def add_block(self, block: dict, *, scope: str = "series", day: int | None = None) -> None:
        edit = json.loads(
            flexweek_engine.block_edit_json(
                json.dumps(self.blocks), json.dumps(block), scope, day, str(uuid4())
            )
        )
        self._touch(edit["label"], blocks=edit["blocks"], keep={edit["block_id"]})

    def add_homework(
        self, assignment: dict, *, days: list[int] | None = None, spread: bool = False
    ) -> None:
        """Save `assignment` and keep its sessions in step. `spread` drops every open time it has and
        makes no new one, for `spread_after_save` to write the sessions that replace them."""
        edit = json.loads(
            flexweek_engine.homework_edit_json(
                json.dumps(self.blocks),
                json.dumps(self.assignments),
                json.dumps(self._assignments_basis),
                json.dumps(assignment),
                self.week_start,
                json.dumps(days),
                spread,
                str(uuid4()),
            )
        )
        for block_id in edit["pinned"]:
            self.needs_time.pop(block_id, None)
        body = edit["assignment"]
        self._touch(edit["label"], keep=set(edit["changed"]), blocks=edit["blocks"], homework=[body])

    def _time_step(self) -> int:
        """The student's time step, 5 or 15 minutes."""
        return drag_step((self.preferences or {}).get("drag_step_min"))

    def judge_hand_move(self, block_id: str, from_day: int, day: int, start: int, end: int) -> dict:
        """The hand-move rule's answer for letting `block_id` go here now, with nothing applied."""
        clock = clock_parts(self.now_ms())
        return hand_move(
            self.blocks,
            self.assignments,
            block_id,
            (self.week_start, clock["iso"], int(clock["minute"]), self._time_step()),
            (from_day, day, start, end),
        )

    def hand_move(self, block_id: str, from_day: int, day: int, start: int, end: int) -> bool:
        """Let a block go where the student dropped or picked it, by the one rule the phone shares.
        Homework moved this way is pinned, so no plan moves it back, and it is one Undo step."""
        answer = self.judge_hand_move(block_id, from_day, day, start, end)
        decision = json.loads(
            flexweek_engine.block_hand_json(
                json.dumps(self.blocks), json.dumps(answer), block_id
            )
        )
        if not decision["moved"]:
            self._say(decision["problem"])
            return False
        self.needs_time.pop(block_id, None)
        self._touch(decision["label"], blocks=decision["blocks"], keep={decision["block_id"]})
        return True

    def place_block(self, block_id: str, from_day: int, day: int, start: int, end: int) -> None:
        """Let a block go at a time. A save already on its way keeps this move and applies it once
        that save has landed, so the reply cannot put the block back where it was."""
        if self.busy:
            self._hand_waiting = (block_id, from_day, day, start, end)
            return
        before = json.dumps(self.blocks)
        if not flexweek_engine.has_block_json(before, block_id):
            return
        if not self.hand_move(block_id, from_day, day, start, end):
            return
        words = flexweek_engine.place_block_words_json(
            before, block_id, from_day, day, start, end, self.week_start
        )
        self.save()
        self.hand_placed.emit(words)

    def _resume_pending(self, busy: bool) -> None:
        plan = json.loads(
            flexweek_engine.resume_pending_json(
                busy,
                json.dumps(self._hand_waiting),
                bool(self.setup_prefs),
                self.setup_work_windows is not None,
                bool(self.setup_week),
            )
        )
        if plan["place"] is not None:
            self._hand_waiting = None
            waiting = tuple(plan["place"])
            QTimer.singleShot(0, lambda waiting=waiting: self.place_block(*waiting))
        if plan["flush_setup"]:
            # After this turn, so a save that just landed finishes putting its week in place first.
            QTimer.singleShot(0, self, self.flush_setup)

    def keep_setup(
        self,
        updates: dict,
        *,
        work_windows: list[dict] | None = None,
        save_week: bool = False,
    ) -> None:
        """Remember what a setup page answered. The write goes out one request at a time."""
        self._setup.keep(
            json.dumps(updates),
            None if work_windows is None else json.dumps(work_windows),
            save_week,
        )
        if self.preferences is not None:
            # Seen at once, as Settings does: the save that follows stores them.
            self.preferences = {**self.preferences, **self.setup_prefs}
        self.flush_setup()

    def flush_setup(self) -> None:
        """Write what setup kept. Preferences go first: the week's save can start a plan. While a
        request is out, this waits, and the next idle turn sends whatever is still kept."""
        step = json.loads(
            self._setup.next(self.account is not None, self.busy, self.preferences is not None)
        )
        if step["step"] == "preferences":
            self.save_preferences(step["updates"])
        elif step["step"] == "windows":
            prefs = self.preferences or {}
            self.save_availability(
                prefs.get("protected") or [], prefs.get("day_cutoff"), step["windows"]
            )
        elif step["step"] == "week":
            self.save()

    def set_setup_blocks(self, blocks: list[dict], edited: str = "keep") -> None:
        """School and activities as Setup now has them, from this week on, as one Undo step for this
        week. Setup showed the repeats, so a block it leaves out stops and what this week changed
        itself stays this week's. Anything the student added another way stays where it is.
        `edited` is keep (later weeks keep their own edits), replace, or from_today."""
        self.change_repeats(self.setup_repeats(blocks), "setting up your week", edited=edited)

    def setup_repeats(self, blocks: list[dict]) -> list[dict]:
        """The repeats after Setup: School and the activities as its page has them, and every weekly fixed
        time the student made as it stands. Setup does not list those, so leaving them out would stop them."""
        return json.loads(
            flexweek_engine.setup_standing_json(
                json.dumps(self.repeats), json.dumps(blocks)
            )
        )

    def change_repeats(self, after: list[dict], label: str, edited: str = "keep") -> None:
        """The repeats become `after` from this week on: the open week changes now by the rule the
        store applies to later weeks, and the next save sends the changes. `edited` is how a later
        week that has its own edit is treated."""
        raw = flexweek_engine.repeat_edit_json(
            json.dumps(self.blocks),
            json.dumps(self.repeats),
            json.dumps(after),
            json.dumps(self._saved_repeats),
            json.dumps(self._repeat_send),
            self.week_start,
            edited,
            self.today_iso(),
            self.first_weekday,
        )
        if raw is None:
            return
        edit = json.loads(raw)
        if edit["leaves_week"]:
            self._touch(label, intents=edit["stamped"])
            return
        self._touch(label, blocks=edit["blocks"], repeats=edit["repeats"], intents=edit["stamped"])

    def repeat_diff(self, after: list[dict]) -> list[dict]:
        """The repeat changes from what stands now to `after`, as the save would send them."""
        return repeat_changes(self.repeats, after, self.week_start)

    def preview_repeats(
        self,
        changes: list[dict],
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        """Ask which later weeks `changes` would reach that have their own edit. Nothing is saved."""
        self.client.request("POST", "/api/repeat-edits", {"repeats": changes}, on_success, on_error)

    def plan_after_save(self, assignment_id: str) -> None:
        """Give this homework's sessions that need a time one once the save now under way lands."""
        waiting = {
            block["id"]
            for block in self.blocks
            if block.get("assignment_id") == assignment_id
            and not block.get("start")
            and not block.get("completed")
        }
        self._plan_after_save |= waiting

    def allow_splitting(self, assignment_id: str) -> bool:
        plan = json.loads(
            flexweek_engine.session_prepare_allow_splitting(
                json.dumps(self.assignments.get(assignment_id)),
                self.done_minutes_for(assignment_id),
                self.week_start,
                self.today_iso(),
                self.selected_day,
            )
        )
        if plan is None:
            return False
        self.add_homework(plan["assignment"], spread=True)
        self._allow_split_pending = assignment_id
        self.spread_after_save(assignment_id, plan["session_min"], plan["from_date"])
        self.save()
        return True

    def spread_after_save(self, assignment_id: str, session_min: int, from_date: str) -> None:
        """Once the save now under way lands, spread this homework into sessions of `session_min` from
        `from_date` and add them, with no preview to answer: the editor already said what they would be."""
        self._spread_after_save = (assignment_id, session_min, from_date)

    def _fixed_copy_rows(self, source: dict | None) -> list[dict] | None:
        offer = json.loads(
            flexweek_engine.fixed_copy_rows_json(
                json.dumps(source),
                self.week_start,
                [str(uuid4()) for _ in (source or {}).get("blocks") or []],
            )
        )
        return offer["rows"]

    def copy_last_week_fixed_rows(self, done: Callable[[list[dict] | None], None]) -> None:
        """Fixed times from last week for the empty-week copy sheet. Never parks a draft."""
        decision = json.loads(
            flexweek_engine.session_previous_week_for_copy(
                self.account is not None, self.week_start, self.first_weekday
            )
        )
        if decision["kind"] == "absent":
            done(None)
            return
        if decision["kind"] == "say":
            self._say(decision["say"])
            done(None)
            return
        previous = decision["week_start"]

        def offer(source: dict) -> None:
            rows = self._fixed_copy_rows(source)
            if not rows:
                self._say(json.loads(flexweek_engine.copy_empty_words_json(json.dumps(source))))
            done(rows)

        local = self._week_local(previous)
        if local is not None:
            offer(local)
            return
        ticket = self._begin()

        def ok(data: dict) -> None:
            if self._idle(ticket):
                offer(data)

        def fail(error: ApiError) -> None:
            if self._idle(ticket):
                self._say(error.message)
                done(None)

        self.client.request("GET", decision["path"], None, ok, fail)

    def date_problem(
        self,
        block_id: str,
        from_iso: str,
        to_iso: str,
        start: str | None = None,
        duration_min: int | None = None,
        assignment_id: str | None = None,
    ) -> str | None:
        """Why this block cannot go on `to_iso`, in the same words as a hours drag, or None."""
        raw = flexweek_engine.session_resolve_date_span(from_iso, to_iso, self.first_weekday)
        if raw is None:
            return None
        span = json.loads(raw)
        clock_now = clock_parts(self.now_ms())
        return flexweek_engine.date_problem_json(
            block_id,
            from_iso,
            to_iso,
            span["from_week"],
            span["to_week"],
            span["from_day"],
            span["to_day"],
            json.dumps(self._block_on_week(block_id, span["from_week"])),
            start,
            duration_min,
            assignment_id,
            json.dumps(self.assignments),
            clock_now["iso"],
            int(clock_now["minute"]),
            self._time_step(),
        )

    def move_to_date(self, block_id: str, from_iso: str, to_iso: str) -> bool:
        """Move a block to another calendar date. Same week keeps its time; another week is one save
        of both documents. A repeating block moves only the day it was dragged from. The open week
        does not change until the server accepts the write."""
        account_id = None if self.account is None else self.account["id"]
        plan = json.loads(
            flexweek_engine.session_prepare_move_to_date(
                json.dumps(
                    {
                        "account_id": account_id,
                        "conflict": self.conflict,
                        "busy": self.busy,
                        "pending_save": self.pending_save is not None,
                        "block_id": block_id,
                        "from_iso": from_iso,
                        "to_iso": to_iso,
                        "first_weekday": self.first_weekday,
                    }
                )
            )
        )
        if plan["kind"] == "stop":
            return bool(plan["result"])
        problem = self.date_problem(block_id, from_iso, to_iso)
        if problem:
            self._say(problem)
            return False
        from_week = plan["from_week"]
        to_week = plan["to_week"]
        key = plan["key"]
        operation_id = self._operation(key)
        source = self._week_local(from_week)
        dest = self._week_local(to_week)
        needed = json.loads(
            flexweek_engine.session_move_to_date_needed(
                from_week, to_week, source is not None, dest is not None
            )
        )
        if not needed:
            return self._commit_move_to_date(
                block_id, from_iso, to_iso, from_week, to_week, source, dest, operation_id, key
            )
        ticket = self._begin()
        fetched: dict[str, dict] = {}

        def fail(error: ApiError) -> None:
            if self._idle(ticket):
                self._say(error.message)
                self.save_finished.emit(False, self.message)

        def proceed() -> None:
            if not self._alive(ticket):
                return
            launched = self._commit_move_to_date(
                block_id,
                from_iso,
                to_iso,
                from_week,
                to_week,
                self._week_local(from_week),
                self._week_local(to_week),
                operation_id,
                key,
                ticket=ticket,
                fetched=fetched,
            )
            if not launched and self._alive(ticket) and self.busy:
                self._idle(ticket)
                self.save_finished.emit(False, self.message)

        def fetch_next() -> None:
            if not needed:
                proceed()
                return
            week = needed.pop(0)

            def ok(data: dict) -> None:
                if not self._alive(ticket):
                    return
                fetched[week] = data
                fetch_next()

            self.client.request("GET", f"/api/week?week_start={week}", None, ok, fail)

        fetch_next()
        return True

    def _wrote_open_weeks(self, written: list[str]) -> bool:
        return self._draft_command("wrote_open", written=written)["wrote"]

    def _week_local(self, week_start: str) -> dict | None:
        return self._draft_command("local", week_start=week_start)["week"]

    def unsaved_weeks(self) -> dict[str, WeekModel]:
        """Weeks other than the open one that the student changed and left without saving."""
        return {
            start: build_week(start, parked["blocks"], parked["assignments"], parked["trace"])
            for start, parked in self._draft_command("unsaved")["weeks"]
        }

    def _block_on_week(self, block_id: str, week_start: str) -> dict | None:
        raw = flexweek_engine.session_block_on_week(json.dumps(self._week_local(week_start)), block_id)
        return None if raw is None else json.loads(raw)

    def _commit_move_to_date(
        self,
        block_id: str,
        from_iso: str,
        to_iso: str,
        from_week: str,
        to_week: str,
        source: dict | None,
        dest: dict | None,
        operation_id: str,
        attempt_key: str,
        ticket: int | None = None,
        fetched: dict[str, dict] | None = None,
    ) -> bool:
        decision = json.loads(
            flexweek_engine.session_build_move_to_date_batch(
                json.dumps(
                    {
                        "block_id": block_id,
                        "from_iso": from_iso,
                        "to_iso": to_iso,
                        "from_week": from_week,
                        "to_week": to_week,
                        "source_local": source,
                        "dest_local": dest,
                        "fetched": {} if fetched is None else fetched,
                        "assignments": self.assignments,
                        "today_iso": self.today_iso(),
                        "operation_id": operation_id,
                        "attempt_key": attempt_key,
                    }
                )
            )
        )
        if decision["kind"] == "say":
            self._say(decision["say"])
            return False
        self._draft_command(
            "submit_batch",
            pending_step=decision["pending_step"],
            history_label=decision["history_label"],
            move_attempt=decision["move_attempt"],
            pending_save=decision["pending_save"],
        )
        self._post_pending(ticket)
        return True

    def delete_homework(self, assignment_id: str) -> bool:
        """Delete homework and its sessions in every week as one undoable change."""
        item = self.assignments.get(assignment_id)
        if item is None or self.account is None or self.conflict:
            return False
        if self.busy or self.dirty or self.pending_save is not None:
            self._say("Saving your last change… Try Delete again in a moment.")
            return False
        key = f"delete-homework|{self.account['id']}|{assignment_id}|{int(item.get('revision') or 0)}"
        operation_id = self._operation(key)
        ticket = self._begin()
        first = self._draft_command(
            "delete_start", assignment_id=assignment_id, operation_id=operation_id,
            key=key, ticket=ticket,
        )
        self._say("Deleting " + first["title"] + "…")

        def received(answer: dict) -> None:
            if answer.get("deleted") and self.first_weekday:
                self._reminder_week = None
            if answer["action"] == "request":
                self._send_week_effect(answer["effect"], received)
                return
            if not self._idle(ticket):
                return
            self._say(answer["words"])
            success = answer["action"] == "deleted"
            self.save_finished.emit(success, self.message)
            if success:
                self._refresh_view()
                self.week_changed.emit()
                self._fetch_weeks()
                self._refresh_assignments()

        self._send_week_effect(first["effect"], received)
        return True

    def unpin_assignment(self, assignment_id: str) -> bool:
        """Let FlexWeek move this homework's sessions again."""
        unpinned = flexweek_engine.homework_unpin_json(json.dumps(self.blocks), assignment_id)
        if unpinned is None:
            return False
        label = flexweek_engine.unpin_label_json(json.dumps(self.assignments), assignment_id)
        self._touch(label, blocks=json.loads(unpinned))
        return True

    def delete_block(
        self,
        block_id: str,
        *,
        scope: str = "series",
        day: int | None = None,
        every_week: bool = False,
        label: str | None = None,
    ) -> None:
        """Delete a block. School or an activity from Setup stands in every week, so taking it out of
        this week alone keeps a saved copy with the removed days so it doesn't repeat into this week;
        `every_week` takes it out of the standing week too. `label` names the Undo step when the delete
        is part of a larger change."""
        raw = flexweek_engine.block_delete_json(
            json.dumps(self.blocks),
            json.dumps(self.repeats),
            block_id,
            scope,
            day,
            every_week,
            self.selected_block_id,
            label,
        )
        if raw is None:
            return
        decision = json.loads(raw)
        if decision["clear_selection"]:
            self.select_block(None, None)
        self._touch(decision["label"], blocks=decision["blocks"], repeats=decision["repeats"])

    def delete_selected(self) -> bool:
        raw = flexweek_engine.delete_selected_plan_json(
            json.dumps(self.blocks), self.selected_block_id, self.selected_occurrence_day
        )
        if raw is None:
            return False
        plan = json.loads(raw)
        self.delete_block(plan["block_id"], scope=plan["scope"], day=plan["day"])
        return True

    def complete_homework(self, assignment_id: str, completed: bool = True) -> None:
        item = self.assignments.get(assignment_id)
        if item is None:
            return
        body = json.loads(flexweek_engine.homework_completed_json(json.dumps(item), completed, local_stamp()))
        self.add_homework(body)

    def last_step(self) -> dict | None:
        return self.client.view("drafts.last_step")["step"]

    def last_step_token(self) -> int | None:
        return self.client.view("drafts.last_step")["token"]

    def can_undo(self) -> bool:
        return self._draft_command("can", redo=False)["can"]

    def can_redo(self) -> bool:
        return self._draft_command("can", redo=True)["can"]

    def _travel(self, redo: bool) -> None:
        answer = self._draft_command("travel", redo=redo)
        if answer.get("words") is not None:
            self._say(answer["words"])
        if answer["go"]:
            self._touch(answer["label"])
            self.save()

    def undo(self) -> None:
        self._travel(False)

    def redo(self) -> None:
        self._travel(True)

    def save(
        self,
        snapshot_label: str | None = None,
        operation_id: str | None = None,
        record_history: bool = True,
        status: str | None = None,
        join: bool = False,
        plan: bool = False,
    ) -> None:
        if self.account is None or self.conflict:
            return
        if self.busy:
            return
        self._draft_command(
            "save", snapshot_label=snapshot_label, operation_id=operation_id,
            record_history=record_history, status=status, join=join, plan=plan,
            ids=[str(uuid4()), str(uuid4())],
        )
        self._post_pending()

    def _post_pending(self, ticket: int | None = None) -> None:
        if self.pending_save is None:
            return
        if ticket is None:
            ticket = self._begin()
        # The existing adapter selects a destination in the host's set iteration order.
        written_order = list({week["week_start"] for week in self.pending_save.get("weeks") or []})
        post = self._draft_command(
            "post", ticket=ticket, shifted_week=bool(self.first_weekday), written_order=written_order,
        )
        if post["held_status"] is None:
            self._say("Saving…")

        def ok(answer: dict) -> None:
            if not self._idle(ticket):
                return
            current = answer["open_week"]
            destination = answer["destination"]
            written = answer["written"]
            planned = answer["planned"]
            if planned:
                # `planned` says it, with Undo.
                self.message = answer["words"]
            else:
                self._say(answer["words"])
            self._invalidate_months()
            spread_next, self._spread_after_save = self._spread_after_save, None
            if spread_next is not None:
                QTimer.singleShot(0, lambda: self.preview_spread(*spread_next, then=self.confirm_spread))
            self._split_whole -= self._split_planned
            self._split_planned = set()
            planned_next, self._plan_after_save = self._plan_after_save, set()
            reread = (
                destination is None
                and not self._refollow_week
                and not current
                and self._wrote_open_weeks(written)
            )
            # A new first day of the week opens its week next; a plan started before that read lands
            # would take its place and leave the old week on screen.
            following = destination is None and self._refollow_week
            if planned_next and (reread or following):
                self._plan_after_load = planned_next
            elif planned_next:
                # Plan it for me as I add it: the new homework's time, joined to the add in one step.
                QTimer.singleShot(0, lambda: self.solve(only=planned_next, join=True))
            replan_next, self._replan_after_save = self._replan_after_save, False
            if replan_next and following:
                self._replan_after_load = True
            elif replan_next:
                QTimer.singleShot(0, lambda: self.solve(everything=True))
            self.save_finished.emit(True, self.message)
            kept = answer["repeat_notice"]
            if kept:
                self.repeats_kept.emit(kept)
            point_id = answer["point_id"]
            doubled = answer["doubled"]
            if point_id or doubled:
                self.save_answered.emit(point_id, doubled)
            if planned:
                self.planned.emit(self.message)
            if self.first_weekday:
                # Reminders read today's stored week from the server when the open week starts on another
                # day; what this save changed is read again.
                self._reminder_week = None
            if destination is not None:
                self.load_week(destination)
                return
            if self._refollow_week:
                self._follow_week()
                if self.busy:
                    return
            if not current and self._wrote_open_weeks(written):
                # Stored weeks the open week shows changed through their Mondays: show them again.
                self.load_week(self.week_start, discard=True, said=self.message)
                return
            # No read followed after all: what waited for one runs now.
            self._plan_waiting_for_load()
            self._refresh_view()
            self.week_changed.emit()
            self._fetch_weeks()
            self._refresh_assignments()

        def err(refusal: dict) -> None:
            if not self._idle(ticket):
                return
            # A plan waiting on this save must not fire after some later, unrelated one.
            self._plan_after_save = set()
            # A plan that was not saved ends no promise; Allow splitting's sessions stay to be saved by Retry.
            self._split_planned = set()
            self._replan_after_save = False
            self._spread_after_save = None
            self._allow_split_pending = None
            self._say(refusal["words"])
            self.save_finished.emit(False, self.message)
            self.week_changed.emit()
            if refusal["reload_words"] is not None:
                # The week on screen is the undone one, which the server never stored. Showing it
                # would leave Undo greyed over a week that is not the saved one.
                self._draft_command("reload")
                self.load_week(self.week_start, discard=True, said=refusal["reload_words"])

        def received(answer: dict) -> None:
            if answer["action"] == "saved":
                ok(answer)
            else:
                err(answer)

        self._send_week_effect(post["effect"], received)

    def retry_save(self) -> None:
        if self.pending_save is not None and not self.conflict:
            self.save()

    def drop_refused_save(self) -> None:
        """A save the server refused (the repeat limit, say) is taken back: nothing of it is sent again, and
        the open week is read again as it is saved."""
        if self._draft_command("drop_refused")["dropped"]:
            self.load_week(self.week_start, discard=True)

    def solve(
        self,
        *,
        everything: bool = False,
        only: set[str] | None = None,
        join: bool = False,
        earliest_first: bool = False,
        _prepared_weeks: dict[str, dict] | None = None,
        _overdue: set[str] | None = None,
        _new_left: set[str] | None = None,
        _dirty_before: bool | None = None,
    ) -> None:
        """Plan my homework. Homework that already has a time keeps it, except a session of this week whose
        time has passed unfinished.

        `everything` is Replan all my homework. `only` finds new times for named work. Nothing is
        placed before now. `earliest_first` (Place now) puts each named block at the first gap that
        fits all of it, instead of the planner's usual order, and says where it went in `placed_where`.
        """
        clock = datetime.fromtimestamp(self.now_ms() / 1000)
        prepared = json.loads(
            flexweek_engine.session_prepare_plan(
                json.dumps(
                    {
                        "planning": self.planning,
                        "conflict": self.conflict,
                        "pending_save": self.pending_save is not None,
                        "week_start": self.week_start,
                        "blocks": self.blocks,
                        "assignments": self.assignments,
                        "assignments_basis": self._assignments_basis,
                        "preferences": self.preferences,
                        "saved_weeks": self.saved_weeks,
                        "split_whole": list(self._split_whole),
                        "clock": _plan_clock(clock),
                        "everything": everything,
                        "only": None if only is None else list(only),
                        "earliest_first": earliest_first,
                        "prepared_weeks": _prepared_weeks,
                        "overdue": None if _overdue is None else list(_overdue),
                    }
                )
            )
        )
        if prepared["kind"] == "blocked":
            if prepared["replan_after_save"]:
                self._replan_after_save = True
            self._say(prepared["message"])
            return
        self.plan_asked_week = self.week_start
        self.placed_where = ""
        # Plan can move the block the outline is on, so the outline does not stay on it.
        self.select_block(None, None)
        if prepared["kind"] == "week_over":
            self._say(prepared["message"])
            return
        if _prepared_weeks is None:
            earlier = prepared["weeks"] if prepared["kind"] == "fetch_earlier" else []
            if earlier:
                ticket = self._begin(planning=True)
                fetched: dict[str, dict] = {}
                self._say("Gathering homework from earlier weeks…")

                def fail(error: ApiError) -> None:
                    self._fail(ticket, error)

                def fetch_next() -> None:
                    if not self._alive(ticket):
                        return
                    if not earlier:
                        if self._idle(ticket):
                            self.solve(
                                everything=everything,
                                only=only,
                                join=join,
                                earliest_first=earliest_first,
                                _prepared_weeks=fetched,
                            )
                        return
                    week_start = earlier.pop(0)

                    def got(data: dict) -> None:
                        if self._alive(ticket):
                            fetched[week_start] = data
                            fetch_next()

                    self.client.request("GET", f"/api/week?week_start={week_start}", None, got, fail)

                fetch_next()
                return
            _prepared_weeks = {}

        if prepared["kind"] == "empty":
            # The window keeps a visible Undo toast when this is only Plan finding nothing new.
            self._plan_idle = True
            try:
                needed = self.homework_time_needed()
                self._say(homework_time_sentence(self.unfinished(), needed))
            finally:
                self._plan_idle = False
            # Homework left in an earlier week is not this plan's to move; the window offers it.
            self.week_changed.emit()
            return
        body = prepared["body"]
        targets = set(prepared["targets"])
        prior_updates = prepared["prior_updates"]
        shares = prepared["shares"]
        week = prepared["week"]
        ticket = self._begin(planning=True)
        self._say("Planning…")

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            answer_clock = datetime.fromtimestamp(self.now_ms() / 1000)
            answer = json.loads(
                flexweek_engine.session_apply_plan_answer(
                    json.dumps(
                        {
                            "original_blocks": self.blocks,
                            "source_week": week,
                            "trace": data,
                            "targets": prepared["targets"],
                            "assignments": self.assignments,
                            "assignments_basis": self._assignments_basis,
                            "week_start": self.week_start,
                            "preferences": self.preferences,
                            "shares": shares,
                            "needs_time": self.needs_time,
                            "clock": _plan_clock(answer_clock),
                            "earliest_first": earliest_first,
                            "overdue": None if _overdue is None else list(_overdue),
                            "new_left": None if _new_left is None else list(_new_left),
                        }
                    )
                )
            )
            self.needs_time = answer["needs_time"]
            self._fresh_plan = True
            self.plan_remainders = [tuple(item) for item in answer["plan_remainders"]]
            self.plan_counts = tuple(answer["plan_counts"])
            self.plan_open = answer["plan_open"]
            self.plan_first = None if answer["plan_first"] is None else tuple(answer["plan_first"])
            split_note = answer["split_note"]
            changed = answer["changed"]
            dirty = self.dirty or changed or bool(split_note)
            self._draft_command(
                "apply_plan",
                blocks=answer["blocks"],
                trace=answer["trace"],
                history_label="the focus split" if split_note else "planning the week" if changed else None,
                dirty=dirty,
                prior_updates=prior_updates if changed else None,
                step_id=str(uuid4()) if changed and prior_updates else None,
                clear_plan_step_id=dirty or bool(self.dirty_assignments),
            )
            placed_note = answer["placed_note"]
            if answer["placed_where"]:
                self.placed_where = answer["placed_where"]
            if not changed and not self.dirty and not self.dirty_assignments:
                self._say(placed_note)
                self.week_changed.emit()
                return
            # Said once its save lands, by `planned`, with Undo. Said now as well, the toast showed it
            # without Undo and then rewrapped it (Grok Bot's 0.17.0 audit, T7).
            self.message = placed_note
            self.week_changed.emit()
            self._split_planned = targets & self._split_whole
            self.save(status=placed_note, join=join, plan=changed and not (join and only is not None))

        def err(error: ApiError) -> None:
            if self._alive(ticket) and _new_left:
                self._draft_command(
                    "apply_plan",
                    blocks=[block for block in self.blocks if block["id"] not in _new_left],
                    dirty=_dirty_before,
                )
                self._forget_settled_notes()
                self.week_changed.emit()
            self._fail(ticket, error)

        self.client.request(
            "POST",
            "/api/solve",
            body,
            ok,
            err,
        )

    def _place_now_sentence(self, block: dict) -> str:
        """Where Place now put one block, or that it found no room this week."""
        return str(flexweek_engine.session_place_now_sentence(json.dumps(block), self.week_start))

    def _apply_auto_split(self, trace: dict, sources: list[dict] | None = None) -> str:
        """Turn each placed homework block into focus chunks and breaks, when the student asked for
        it. The solver was given room for the breaks before it ran, so the chunks fit where it put
        the block rather than landing on whatever came next. `sources` is the week as planned (work
        minutes), not the inflated duration the solver reserved for breaks. Starts, pins, days and
        overdue rewrites stay the week after apply_plan."""
        result = json.loads(
            flexweek_engine.session_apply_auto_split(
                json.dumps(self.blocks),
                json.dumps(trace),
                json.dumps(sources),
                json.dumps(self.preferences),
            )
        )
        if not result["count"]:
            return ""
        self._draft_command(
            "apply_plan",
            blocks=result["blocks"],
            history_label="the focus split",
            dirty=True,
        )
        return str(result["note"])

    def _operation(self, key: str) -> str:
        return self._draft_command("attempt", key=key, new=str(uuid4()))["id"]

    def _dump_blocks(self, blocks: list[dict] | None = None) -> list[dict]:
        return [_checked_block(block) for block in (blocks if blocks is not None else self.blocks)]

    def _fetch_weeks(self) -> None:
        if self.account is None:
            return
        self._weeks_ticket += 1
        token = self._weeks_ticket

        def ok(data: dict) -> None:
            if token != self._weeks_ticket or self.account is None:
                return
            self.saved_weeks = list(data.get("weeks") or [])
            self.week_changed.emit()

        self.client.request("GET", "/api/weeks", None, ok, lambda _error: None)

    def _fetch_routines(self) -> None:
        if self.account is None:
            return
        self._routines_ticket += 1
        token = self._routines_ticket

        def ok(data: dict) -> None:
            if token != self._routines_ticket or self.account is None:
                return
            self.routines = json.loads(
                flexweek_engine.session_routines_from_reply(json.dumps(data))
            )
            self.week_changed.emit()

        self.client.request("GET", "/api/routines", None, ok, lambda _error: None)

    def _fetch_preferences(self) -> None:
        if self.account is None:
            return
        self._prefs_ticket += 1
        token = self._prefs_ticket

        def ok(data: dict) -> None:
            if token != self._prefs_ticket or self.account is None:
                return
            self.preferences = data
            self.week_changed.emit()
            # The window resumes a setup queue from week_changed. A surface with no window cannot,
            # so the answers kept while preferences were absent go out from here.
            self.flush_setup()
            self._fetch_timer_tools()

        self.client.request("GET", "/api/preferences", None, ok, lambda _error: None)

    def _refresh_assignments(self) -> None:
        if self.account is None:
            return
        answer = self._draft_command("refresh")
        self._send_week_effect(answer["effect"], lambda _answer: self.week_changed.emit())

    def consume_plan_review(self) -> dict | None:
        """The solver's trace, once, for the review panel. Reading a week again must not reopen it."""
        if not self._fresh_plan:
            return None
        self._fresh_plan = False
        return self.trace

    def _clock_now(self) -> dict[str, Any]:
        clock = datetime.fromtimestamp(self.now_ms() / 1000)
        return {
            "today": clock.date().isoformat(),
            "hour": clock.hour,
            "minute": clock.minute,
            "second": clock.second,
            "microsecond": clock.microsecond,
        }

    def _homework_counts(
        self,
        blocks: list[dict] | None = None,
        assignments: dict[str, dict] | None = None,
    ) -> dict[str, Any]:
        return json.loads(
            flexweek_engine.session_homework_counts(
                json.dumps(
                    {
                        "week_start": self.week_start,
                        "first_weekday": self.first_weekday,
                        "blocks": self.blocks if blocks is None else blocks,
                        "assignments": self.assignments if assignments is None else assignments,
                        "assignments_basis": self._assignments_basis,
                        "now": self._clock_now(),
                    }
                )
            )
        )

    def done_minutes_for(self, assignment_id: str | None) -> int:
        """Minutes of this homework's sessions ticked done, in every saved week and this week as it stands:
        with its focus minutes, the larger of the two is its done time."""
        # A homework not saved yet has done nothing.
        return int(
            self._homework_counts()["per_assignment"]
            .get(assignment_id or "", {})
            .get("done_sessions_min", 0)
        )

    def homework_counts(self) -> dict[str, Any]:
        """One engine count, for a caller that reads several of its parts at the same clock reading."""
        return self._homework_counts()

    def homework_minutes(self) -> dict[str, dict[str, Any]]:
        """Every homework's counts from one engine call, for lists that would otherwise ask once per row."""
        return self._homework_counts()["per_assignment"]

    def remaining_for(self, assignment_id: str) -> int:
        return int(
            self._homework_counts()["per_assignment"]
            .get(assignment_id, {})
            .get("remaining_min", 0)
        )

    def homework_time_needed(self) -> list[dict]:
        """Homework that needs a time. A session whose time has passed unfinished needs one again. In a week
        that is over, the minutes of its missed sessions are also given as `missed_min`, and those of its
        pinned sessions that passed unfinished as `pinned_min`."""
        return self._homework_counts()["needed"]

    def _open_week(self, blocks: list[dict] | None = None) -> list[dict]:
        """The week every count of minutes still needed reads: each missed session as one with no time."""
        return self._homework_counts(blocks=blocks)["open_week"]

    def missed_block_ids(self) -> frozenset[str]:
        """The sessions every look calls missed: the planner's own answer, read at the clock now."""
        return frozenset(self._homework_counts()["missed_block_ids"])

    def _time_split(self, blocks: list[dict] | None = None) -> list[dict]:
        return self._homework_counts(blocks=blocks)["parts"]

    def plan_can_place(self) -> bool:
        """Whether pressing Plan has something to place: a session waiting for a time (a missed one is read
        as waiting), or minutes no session holds that make a whole quarter hour."""
        return bool(self._homework_counts()["plan_can_place"])

    def homework_remainders(self) -> list[tuple[str, int, str]]:
        """Homework with minutes that no session holds, by title, those minutes alone and its id: the drawer
        lists them under the cards, which already show the sessions that wait. In a week that is over a
        pinned session that passed is said as such, not as minutes with no time."""
        return [tuple(row) for row in self._homework_counts()["remainders"]]

    def minutes_left_for(self, assignment_id: str) -> int:
        """Minutes of this homework that no session holds. `remaining_for` is what Plan can place of them."""
        return int(
            self._homework_counts()["per_assignment"]
            .get(assignment_id, {})
            .get("uncovered_min", 0)
        )

    def built_week(self) -> WeekModel:
        """The week Material draws. The shell asks the session, not the builder."""
        return build_week(self.week_start, self.blocks, self.assignments, self.trace)

    def paste_destination(self, today: date | None = None) -> tuple[int, str | None] | None:
        today = today or wall_clock.today()
        raw = flexweek_engine.paste_destination_json(
            json.dumps(self.blocks),
            json.dumps(self.trace),
            self.selected_block_id,
            self.selected_occurrence_day,
            self.planner_view,
            self.first_weekday,
            self.selected_day,
            today.isoformat(),
            self.week_start,
        )
        if raw is None:
            return None
        destination = json.loads(raw)
        return (destination["day"], destination["start"])

    def copy_block(self, block_id: str, day: int | None, scope: str = "auto", *, say: bool = True) -> bool:
        if self.account is None:
            return False
        decision = json.loads(
            flexweek_engine.clipboard_block_json(
                json.dumps(self.blocks), block_id, day, scope, str(uuid4())
            )
        )
        if decision["clipboard"] is None:
            return False
        self.clipboard = decision["clipboard"]
        if say:
            self._say(decision["words"])
        self.week_changed.emit()
        return True

    def copy_selected(self, scope: str = "auto") -> bool:
        decision = json.loads(
            flexweek_engine.session_copy_selected(
                self.account is not None,
                json.dumps(self.blocks),
                self.selected_block_id,
                self.selected_occurrence_day,
                scope,
                str(uuid4()),
            )
        )
        if decision["kind"] == "say":
            self._say(decision["say"])
            return False
        if decision["kind"] != "copied":
            return False
        self.clipboard = decision["clipboard"]
        self._say(decision["say"])
        self.week_changed.emit()
        return True

    def copy_day(self, day: int | None = None) -> bool:
        decision = json.loads(
            flexweek_engine.session_copy_day(
                json.dumps(
                    {
                        "signed_in": self.account is not None,
                        "blocks": self.blocks,
                        "trace": self.trace,
                        "day": day,
                        "selected_block_id": self.selected_block_id,
                        "selected_occurrence_day": self.selected_occurrence_day,
                        "planner_view": self.planner_view,
                        "first_weekday": self.first_weekday,
                        "selected_day": self.selected_day,
                        "today_iso": wall_clock.today().isoformat(),
                        "week_start": self.week_start,
                    }
                )
            )
        )
        if decision["kind"] == "say":
            self._say(decision["say"])
            return False
        if decision["kind"] != "copied":
            return False
        self.clipboard = decision["clipboard"]
        self._say(decision["say"])
        self.week_changed.emit()
        return True

    def paste_proposals(
        self,
        target_day: int | None = None,
        target_start: str | None = None,
        *,
        today: date | None = None,
    ) -> list[dict] | None:
        today_iso = wall_clock.today().isoformat() if today is None else today.isoformat()
        prep = json.loads(
            flexweek_engine.session_paste_proposals_prepare(
                json.dumps(
                    {
                        "signed_in": self.account is not None,
                        "clipboard": self.clipboard,
                        "target_day": target_day,
                        "target_start": target_start,
                        "blocks": self.blocks,
                        "trace": self.trace,
                        "selected_block_id": self.selected_block_id,
                        "selected_occurrence_day": self.selected_occurrence_day,
                        "planner_view": self.planner_view,
                        "first_weekday": self.first_weekday,
                        "selected_day": self.selected_day,
                        "today_iso": today_iso,
                        "week_start": self.week_start,
                        "has_assignments": bool(self.assignments),
                    }
                )
            )
        )
        if prep["kind"] == "say":
            self._say(prep["say"])
            return None
        if prep["kind"] != "ready":
            return None
        minutes = self.homework_minutes() if prep["needs_minutes"] else {}
        return json.loads(
            flexweek_engine.session_paste_proposals_build(
                json.dumps(self.clipboard),
                self.week_start,
                prep["day"],
                prep["start"],
                json.dumps(self.assignments),
                json.dumps(minutes),
            )
        )

    def duplicate_selected(self, scope: str = "auto") -> list[dict] | None:
        prep = json.loads(
            flexweek_engine.session_duplicate_selected_prepare(
                self.account is not None,
                json.dumps(self.blocks),
                self.selected_block_id,
                self.selected_occurrence_day,
                scope,
                str(uuid4()),
                bool(self.assignments),
            )
        )
        if prep["kind"] == "say":
            self._say(prep["say"])
            return None
        if prep["kind"] != "ready":
            return None
        if prep["announce"] is not None:
            self._say(prep["announce"])
        minutes = self.homework_minutes() if prep["needs_minutes"] else {}
        rows = json.loads(
            flexweek_engine.session_paste_proposals_build(
                json.dumps(prep["clipboard"]),
                self.week_start,
                prep["target_day"],
                None,
                json.dumps(self.assignments),
                json.dumps(minutes),
            )
        )
        self.week_changed.emit()
        return rows

    def confirm_preview(
        self,
        rows: list[dict],
        *,
        label: str,
        snapshot_label: str | None = None,
        operation_id: str | None = None,
        attempt_key: str | None = None,
        existing: list[dict] | None = None,
        destination: str | None = None,
        said: str | None = None,
    ) -> bool:
        """Add the checked rows. `said` is what the status line says once they are saved."""
        decision = json.loads(
            flexweek_engine.session_confirm_preview_plan(
                json.dumps(
                    {
                        "signed_in": self.account is not None,
                        "conflict": self.conflict,
                        "rows": rows,
                        "week_start": self.week_start,
                        "blocks": self.blocks,
                        "today_iso": self.today_iso(),
                        "operation_id": operation_id,
                        "attempt_key": attempt_key,
                        "attempts": self.client.view("drafts.attempts"),
                        "fresh_operation_id": str(uuid4()),
                    }
                )
            )
        )
        if decision["kind"] == "absent":
            return False
        if decision["record_attempt"]:
            self._draft_command("attempt", key=attempt_key, new=decision["op_id"])
            self._draft_command("preview_attempt", key=attempt_key)
        if decision["kind"] == "say":
            self._say(decision["say"])
            return False
        if decision["kind"] == "single_week":
            self._touch(label, blocks=decision["blocks"])
            self.save(snapshot_label=snapshot_label, operation_id=decision["op_id"], status=said)
            return True
        self._commit_groups(
            decision["by_week"],
            label=label,
            snapshot_label=snapshot_label,
            operation_id=decision["op_id"],
            said=said,
            fetch_order=decision["fetch_order"],
        )
        return True

    def _commit_groups(
        self,
        by_week: dict[str, list[dict]],
        *,
        label: str,
        snapshot_label: str | None,
        operation_id: str,
        said: str | None = None,
        fetch_order: list[str] | None = None,
    ) -> None:
        pending = (
            list(fetch_order)
            if fetch_order is not None
            else json.loads(flexweek_engine.session_commit_groups_order(json.dumps(by_week), self.week_start))
        )
        ticket = self._begin()
        fetched: dict[str, dict] = {}

        def fail(error: ApiError) -> None:
            self._fail(ticket, error)

        def proceed() -> None:
            if not self._alive(ticket):
                return
            decision = json.loads(
                flexweek_engine.session_commit_groups_batch(
                    json.dumps(
                        {
                            "by_week": by_week,
                            "week_start": self.week_start,
                            "current_blocks": self.blocks,
                            "current_revision": self.revision,
                            "fetched": fetched,
                            "today_iso": self.today_iso(),
                            "label": label,
                            "snapshot_label": snapshot_label,
                            "operation_id": operation_id,
                            "said": said,
                        }
                    )
                )
            )
            if decision["kind"] == "say":
                if self._idle(ticket):
                    self._say(decision["say"])
                return
            self._draft_command(
                "submit_batch",
                pending_save=decision["pending_save"],
                blocks=decision["blocks"],
                history_label=decision["history_label"],
                capture_step=decision["capture_step"],
                save_status=decision["save_status"],
            )
            self._post_pending(ticket)

        def fetch_next() -> None:
            if not pending:
                proceed()
                return
            week = pending.pop(0)

            def ok(data: dict) -> None:
                if not self._alive(ticket):
                    return
                fetched[week] = data
                fetch_next()

            self.client.request("GET", f"/api/week?week_start={week}", None, ok, fail)

        fetch_next()

    def save_routine(self, name: str, block_ids: list[str] | None = None) -> bool:
        account_id = None if self.account is None else self.account["id"]
        decision = json.loads(
            flexweek_engine.session_prepare_save_routine(
                json.dumps(
                    {
                        "account_id": account_id,
                        "week_start": self.week_start,
                        "blocks": self.blocks,
                        "name": name,
                        "block_ids": block_ids,
                    }
                )
            )
        )
        if decision["kind"] == "absent":
            return False
        if decision["kind"] == "say":
            self._say(decision["say"])
            return False
        operation_id = self._operation(decision["key"])
        request = json.loads(
            flexweek_engine.session_save_routine_request(
                operation_id, decision["title"], json.dumps(decision["templates"])
            )
        )
        ticket = self._begin()
        self._say(request["progress"])

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            saved = json.loads(flexweek_engine.session_save_routine_reply(json.dumps(data)))
            self.routines[saved["id"]] = saved["routine"]
            self._draft_command("forget_attempt", key=decision["key"])
            self._say(saved["say"])
            self.week_changed.emit()

        self.client.request(
            request["method"],
            request["path"],
            request["body"],
            ok,
            lambda error: self._fail(ticket, error),
        )
        return True

    def delete_routine(self, routine_id: str) -> None:
        account_id = None if self.account is None else self.account["id"]
        decision = json.loads(
            flexweek_engine.session_prepare_delete_routine(
                json.dumps(
                    {
                        "account_id": account_id,
                        "routines": self.routines,
                        "routine_id": routine_id,
                    }
                )
            )
        )
        if decision["kind"] == "absent":
            return
        operation_id = self._operation(decision["key"])
        ticket = self._begin()
        path = flexweek_engine.session_delete_routine_path(
            routine_id, json.dumps(decision["revision"]), operation_id
        )

        def ok(_data: dict) -> None:
            if not self._idle(ticket):
                return
            self.routines.pop(routine_id, None)
            self._draft_command("forget_attempt", key=decision["key"])
            self._say(decision["say"])
            self.week_changed.emit()

        self.client.request("DELETE", path, None, ok, lambda error: self._fail(ticket, error))

    def week_blocks(self, week_start: str, then: Callable[[list[dict]], None]) -> None:
        """The blocks on screen for this week, or the saved blocks of another week. A failed load is
        said here, and `then` is not called, so a preview cannot treat that week as empty."""
        if week_start == self.week_start:
            then(self.blocks)
            return

        def ok(data: dict) -> None:
            then(list(data.get("blocks") or []))

        def err(error: ApiError) -> None:
            self._say(error.message)

        self.client.request("GET", f"/api/week?week_start={week_start}", None, ok, err)

    def apply_routine_rows(self, routine_id: str, week_start: str, days: list[int]) -> list[dict] | None:
        decision = json.loads(
            flexweek_engine.session_apply_routine_rows(
                json.dumps(
                    {
                        "routines": self.routines,
                        "routine_id": routine_id,
                        "week_start": week_start,
                        "days": days,
                    }
                )
            )
        )
        if decision["kind"] == "say":
            self._say(decision["say"])
            return None
        return decision["rows"]

    def apply_routine(
        self,
        routine_id: str,
        week_start: str,
        days: list[int],
        rows: list[dict] | None = None,
        existing: list[dict] | None = None,
    ) -> bool:
        account_id = None if self.account is None else self.account["id"]
        decision = json.loads(
            flexweek_engine.session_prepare_apply_routine(
                json.dumps(
                    {
                        "account_id": account_id,
                        "routines": self.routines,
                        "routine_id": routine_id,
                        "week_start": week_start,
                        "days": days,
                        "rows": rows,
                    }
                )
            )
        )
        if decision["kind"] == "absent":
            return False
        if decision["kind"] == "say":
            for words in decision["say"]:
                self._say(words)
            return False
        return self.confirm_preview(
            decision["proposals"],
            label=decision["label"],
            snapshot_label=decision["snapshot_label"],
            operation_id=self._operation(decision["key"]),
            attempt_key=decision["key"],
            existing=existing,
            destination=week_start,
        )

    def _unfinished_args(self, *, only_left_from_last_week: bool = False) -> str:
        return json.dumps(
            {
                "week_start": self.week_start,
                "first_weekday": self.first_weekday,
                "blocks": self.blocks,
                "assignments": self.assignments,
                "assignments_basis": self._assignments_basis,
                "saved_weeks": self.saved_weeks,
                "stored_parts": self._stored_parts,
                "now": self._clock_now(),
                "only_left_from_last_week": only_left_from_last_week,
            }
        )

    def unfinished(self) -> list[dict]:
        return json.loads(flexweek_engine.session_unfinished_items(self._unfinished_args()))

    def _overdue_assignment_ids(self, assignments: dict[str, dict] | None = None) -> set[str]:
        chosen = self.assignments
        if assignments is not None:
            chosen = assignments
        return set(
            json.loads(
                flexweek_engine.session_overdue_assignment_ids(
                    json.dumps({"assignments": chosen, "now": self._clock_now()})
                )
            )
        )

    def consume_unfinished(self) -> list[dict]:
        items = self.unfinished()
        if not items or self.week_start in self._seen_unfinished:
            return []
        self._seen_unfinished.add(self.week_start)
        return items

    def plan_unfinished(self, assignment_id: str) -> list[dict] | None:
        result = json.loads(
            flexweek_engine.session_unfinished_preview(
                json.dumps(
                    {
                        "week_start": self.week_start,
                        "blocks": self.blocks,
                        "assignments": self.assignments,
                        "assignments_basis": self._assignments_basis,
                        "assignment_id": assignment_id,
                        "now": self._clock_now(),
                        "plannable_today": wall_clock.today().isoformat(),
                        "block_id": str(uuid4()),
                    }
                )
            )
        )
        if "say" in result:
            self._say(result["say"])
            return None
        return result["rows"]

    def left_unfinished(self) -> list[dict]:
        """Homework whose deadline passed or whose saved session was left in an earlier week."""
        return json.loads(
            flexweek_engine.session_unfinished_items(
                self._unfinished_args(only_left_from_last_week=True)
            )
        )

    def plan_left(self, assignment_ids: list[str]) -> None:
        """"Plan into this week": each one gets a session in this week for the time it has left, and Plan
        finds those times as it does any homework's. The time left in the earlier week stays where it was."""
        if self.busy or self.conflict or self.pending_save is not None:
            return
        ids = list(assignment_ids)
        plan = json.loads(
            flexweek_engine.session_plan_unfinished(
                json.dumps(
                    {
                        "week_start": self.week_start,
                        "blocks": self.blocks,
                        "assignments": self.assignments,
                        "assignments_basis": self._assignments_basis,
                        "assignment_ids": ids,
                        "now": self._clock_now(),
                        "new_ids": [str(uuid4()) for _ in ids],
                    }
                )
            )
        )
        if "say" in plan:
            self._say(plan["say"])
            return
        dirty_before = self.dirty
        made = set(plan["made"])
        if made:
            self._touch("planning unfinished homework", blocks=plan["blocks"])
        self.solve(
            only=set(plan["targets"]),
            _overdue=set(plan["overdue_targets"]),
            _new_left=made,
            _dirty_before=dirty_before,
        )

    def did_these(self, assignment_ids: list[str]) -> None:
        """"Mark as finished": the student finished them after all, as one Undo step."""
        for assignment_id in assignment_ids:
            if assignment_id in self.assignments:
                self.complete_homework(assignment_id)
        self.save()

    def recover_missed(self, block_id: str, day: int) -> None:
        prep = json.loads(
            flexweek_engine.session_recover_request(
                self.week_start,
                json.dumps(self.blocks),
                None if self.trace is None else json.dumps(self.trace),
                block_id,
                day,
            )
        )
        if prep["kind"] == "ignore":
            return
        if prep["kind"] == "save_only":
            self.save()
            return
        ticket = self._begin()
        self._say(prep["status"])

        def send_recover(payload: dict) -> None:
            def ok(trace: dict) -> None:
                if not self._idle(ticket):
                    return
                applied = json.loads(
                    flexweek_engine.session_recover_answer(
                        self.week_start,
                        json.dumps(self.blocks),
                        json.dumps(self.assignments),
                        block_id,
                        day,
                        json.dumps(trace),
                    )
                )
                if applied is None:
                    return
                self._touch(applied["label"], blocks=applied["blocks"])
                self._draft_command("apply_plan", trace=trace)
                self.save()

            self.client.request(
                "POST",
                "/api/solve",
                payload,
                ok,
                lambda error: self._fail(ticket, error),
            )

        if prep["kind"] == "ready":
            send_recover(prep["payload"])
            return

        def base_ok(trace: dict) -> None:
            if not self._alive(ticket):
                return
            payload = json.loads(
                flexweek_engine.session_recover_payload_from_base(
                    self.week_start,
                    json.dumps(self.blocks),
                    block_id,
                    day,
                    json.dumps(trace),
                )
            )
            send_recover(payload)

        self.client.request(
            "POST",
            "/api/solve",
            prep["base_payload"],
            base_ok,
            lambda error: self._fail(ticket, error),
        )

    def preview_running_late(self, minutes: int, now: datetime | None = None) -> None:
        moment = now or wall_clock.now()
        prep = json.loads(
            flexweek_engine.session_prepare_late(
                self.week_start,
                moment.date().isoformat(),
                moment.hour,
                moment.minute,
                minutes,
                self.dirty,
                self.conflict,
                json.dumps(self.blocks),
                None if self.trace is None else json.dumps(self.trace),
            )
        )
        if prep["kind"] == "refused":
            self._say(prep["message"])
            return
        day = prep["day"]
        from_start = prep["from_start"]
        ticket = self._begin()
        self._say(prep["status"])

        def send_late(payload: dict) -> None:
            def ok(trace: dict) -> None:
                if not self._idle(ticket):
                    return
                operation_id = str(uuid4())
                answered = json.loads(
                    flexweek_engine.session_late_answer(
                        self.week_start,
                        day,
                        from_start,
                        minutes,
                        operation_id,
                        json.dumps(trace),
                    )
                )
                self.late_preview = answered["preview"]
                self._say(answered["summary"])
                self.week_changed.emit()

            self.client.request(
                "POST",
                "/api/solve",
                payload,
                ok,
                lambda error: self._fail(ticket, error),
            )

        if prep["kind"] == "ready":
            send_late(prep["payload"])
            return

        def base_ok(trace: dict) -> None:
            if not self._alive(ticket):
                return
            payload = json.loads(
                flexweek_engine.session_late_payload_from_base(
                    self.week_start,
                    json.dumps(self.blocks),
                    day,
                    from_start,
                    minutes,
                    json.dumps(trace),
                )
            )
            send_late(payload)

        self.client.request(
            "POST",
            "/api/solve",
            prep["base_payload"],
            base_ok,
            lambda error: self._fail(ticket, error),
        )

    def _late_blocks(self) -> list[dict]:
        """The week as Running late replans it. Homework still waiting for a time stays out, so a late
        start never places it: Plan places that homework."""
        blocks: list[dict] = json.loads(flexweek_engine.session_late_blocks(json.dumps(self.blocks)))
        return blocks

    def accept_running_late(self) -> bool:
        decision = json.loads(
            flexweek_engine.session_accept_late(
                None if self.late_preview is None else json.dumps(self.late_preview),
                self.week_start,
                json.dumps(self.blocks),
                json.dumps(self.assignments),
            )
        )
        if decision["kind"] == "ignore":
            return False
        if decision["kind"] == "refused":
            self._say(decision["message"])
            return False
        self._touch(decision["label"], blocks=decision["blocks"])
        self._draft_command("apply_plan", trace=decision["trace"])
        self.save(operation_id=decision["operation_id"])
        self.late_preview = None
        return True

    def preview_spread(
        self,
        assignment_id: str,
        session_min: int,
        from_date: str,
        then: Callable[[], object] | None = None,
    ) -> None:
        item = self.assignments.get(assignment_id)
        if item is None or item.get("completed"):
            self._allow_split_pending = None
            return
        ticket = self._begin()
        self._say("Working out sessions…")

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            answered = json.loads(
                flexweek_engine.session_spread_answer(
                    assignment_id,
                    json.dumps(item),
                    json.dumps(data),
                    from_date,
                    session_min,
                    self.today_iso(),
                    str(uuid4()),
                )
            )
            if answered["kind"] == "empty":
                self._say(answered["message"])
                self.spread_preview = None
                # Allow splitting made nothing, so a later Spread of this homework is an ordinary one.
                self._allow_split_pending = None
                return
            self.spread_preview = answered["preview"]
            self._say(answered["summary"])
            self.week_changed.emit()
            if then is not None:
                then()

        def failed(error: ApiError) -> None:
            if self._alive(ticket):
                # Allow splitting made nothing, so a later Spread of this homework is an ordinary one.
                self._allow_split_pending = None
            self._fail(ticket, error)

        self.client.request(
            "POST",
            f"/api/assignments/{quote(assignment_id, safe='')}/spread",
            {"session_min": session_min, "from_date": from_date},
            ok,
            failed,
        )

    def confirm_spread(self) -> bool:
        preview = self.spread_preview
        if preview is None or self.account is None:
            return False
        key = flexweek_engine.session_spread_operation_key(
            int(self.account["id"]),
            preview["assignment_id"],
            preview["from_date"],
            int(preview["session_min"]),
        )
        operation_id = self._operation(key)
        selection = json.loads(
            flexweek_engine.session_spread_selection(
                json.dumps(preview),
                json.dumps(self.assignments),
                self.week_start,
                self.first_weekday,
                operation_id,
                self._allow_split_pending,
            )
        )
        made = set(selection["made_ids"])
        plan_ids = set(selection["plan_ids"])
        self._plan_after_save |= plan_ids
        # A Spread by hand of the same homework and length makes the same ids as discarded Allow splitting
        # sessions (one operation per attempt); its sessions are not promised a place.
        self._split_whole = (self._split_whole - made) | plan_ids
        ok = self.confirm_preview(
            preview["rows"],
            label=selection["label"],
            operation_id=operation_id,
            attempt_key=key,
        )
        if ok:
            self.spread_preview = None
            self._allow_split_pending = None
        else:
            self._plan_after_save.difference_update(plan_ids)
            # Refused (a full week): the sessions were never made.
            self._split_whole -= plan_ids
            self._allow_split_pending = None
        return ok

    def save_availability(
        self,
        protected: list[dict],
        day_cutoff: str | None,
        work_windows: list[dict] | None = None,
    ) -> bool:
        if self.account is None or self.preferences is None:
            return False
        try:
            flexweek_engine.check_hours_windows(
                json.dumps(protected), None if work_windows is None else json.dumps(work_windows)
            )
        except ValueError:
            # The engine's reason names fields, not what the student sees; the Study hours sheet checks
            # its own rows first, so this is rarely reached.
            self._say(HOURS_REFUSED)
            return False
        body = json.loads(
            flexweek_engine.session_availability_body(
                json.dumps(self.preferences),
                json.dumps(protected),
                json.dumps(day_cutoff),
                None if work_windows is None else json.dumps(work_windows),
            )
        )
        ticket = self._begin()
        self._say("Saving availability…")

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            self.preferences = data
            self._say("Saved availability.")
            self.week_changed.emit()

        self.client.request(
            "PUT",
            "/api/preferences",
            body,
            ok,
            lambda error: self._fail(ticket, error),
        )
        return True

    def _clock(self) -> dict:
        return clock_parts(self.now_ms())

    def scheduled_blocks(self) -> list[dict]:
        return scheduled_blocks_of(self.blocks, self.trace)

    def now_next_text(self) -> str:
        clock = self._clock()
        column = self.today_column(clock["iso"])
        if column is None:
            return ""
        return now_next_line(
            now_and_next(self.scheduled_blocks(), column, clock["minute"]),
            clock["minute"],
        )

    def focus_tasks(self) -> list[dict]:
        now = datetime.fromtimestamp(self.now_ms() / 1000)
        return focus_candidates(
            self.blocks,
            self.assignments,
            self.trace,
            self.week_start,
            now.isoformat(timespec="minutes"),
        )

    def _drop_missing_focus(self) -> None:
        announce = self._focus_after_restore
        self._focus_after_restore = False
        decision = drop_missing(self.focus, self.week_start, self.blocks, announce)
        if not decision["drop"]:
            return
        self._reset_focus()
        if decision["say"]:
            self._say(decision["say"])

    def _persist_focus(self) -> None:
        if self.account is None:
            return
        payload = persist_payload(self.focus)
        if payload is None:
            self.focus_store.pop(self.account["id"], None)
        else:
            self.focus_store[self.account["id"]] = payload

    def _clear_finish_intent(self) -> None:
        self._finish_focus_waiting = False
        self._finish_focus_week = None

    def _reset_focus(self, persist: bool = True) -> None:
        self.focus = None
        self._focus_busy = False
        self._pending_focus = None
        self._clear_finish_intent()
        if persist:
            self._persist_focus()
        self.focus_changed.emit()

    def _restore_focus(self) -> None:
        if self.account is None or self.focus is not None:
            return
        saved = self.focus_store.get(self.account["id"])
        decision = restore_decision(
            saved,
            assignments=self.assignments,
            blocks=self.blocks,
            prefs=self.preferences,
            now_ms=self.now_ms(),
        )
        if decision["action"] == "drop":
            self.focus_store.pop(self.account["id"], None)
            return
        # Persist and tell, then either finish the work phase or replace it with the paused one.
        self.focus = decision["state"]
        self._persist_focus()
        self.focus_changed.emit()
        if decision["action"] == "advance_work":
            self.advance_focus(completed=True)
        elif decision["action"] == "paused_work":
            self.focus = decision["paused"]
            self._say(decision["say"])
            self._persist_focus()
            self.focus_changed.emit()

    def start_quick_focus(self, *, replace: bool = False) -> bool:
        return self.start_focus(None, None, replace=replace, quick=True)

    def quick_focus_offer(self) -> dict | None:
        """The homework session the Quick focus screen offers: the one on now, or the next one today."""
        if self.account is None or not self.week_start:
            return None
        now = datetime.fromtimestamp(self.now_ms() / 1000)
        return quick_focus_homework(
            self.blocks, self.assignments, self.trace, self.week_start, now.isoformat(timespec="minutes")
        )

    def start_focus_on_offer(self) -> bool:
        """Start from the Quick focus screen: on the homework it names, counted toward it as when Day
        starts focus on that block; a plain timer when nothing is offered."""
        offer = self.quick_focus_offer()
        if offer is None:
            return self.start_quick_focus()
        return self.start_focus(offer["id"], offer["day"])

    def start_focus(
        self,
        block_id: str | None,
        day: int | None = None,
        *,
        replace: bool = False,
        quick: bool = False,
    ) -> bool:
        if not start_allowed(self.account is not None, self.busy, self._focus_busy):
            return False
        # Only a homework's title says whether it is overdue, so the clock is read only for one.
        names_homework = not quick and day is None and block_id in self.assignments
        planned = start_target(
            block_id=block_id,
            day=day,
            quick=quick,
            week_start=self.week_start,
            assignments=self.assignments,
            blocks=self.blocks,
            trace=self.trace,
            overdue=sorted(self._overdue_assignment_ids()) if names_homework else [],
        )
        if "refuse" in planned:
            self._say(planned["refuse"])
            return False
        target = planned["target"]
        decision = start_decision(self.focus, target, replace)
        if decision == "same":
            return True
        if decision == "ask":
            self._pending_focus = {**target, "quick": quick, "block_id": block_id, "day": day}
            self.focus_replace_needed.emit(self.focus["title"], target["title"])
            return False
        self.focus = begin_state(target, self.preferences, self.now_ms())
        self._pending_focus = None
        self._persist_focus()
        self.focus_changed.emit()
        self._open_focus_spotify()
        return True

    def _open_focus_spotify(self) -> None:
        """Spotify, when that is the focus sound: open the Settings link. Anything else stays quiet.
        A missing link or an app that will not open is said once, and focus carries on."""
        decision = focus_spotify_decision(self.preferences, self.spotify_url())
        if decision["action"] == "skip":
            return
        if decision["action"] == "say":
            self._say(decision["say"])
            return
        from desktop.native.spotify import open_in_app

        if not open_in_app(decision["link"]):
            self._say(focus_spotify_open_failed())

    def confirm_replace_focus(self) -> bool:
        pending = self._pending_focus
        if pending is None:
            return False
        return self.start_focus(
            pending.get("block_id"),
            pending.get("day"),
            replace=True,
            quick=bool(pending.get("quick")),
        )

    def toggle_focus_pause(self) -> None:
        decision = toggle_pause_decision(
            self.focus, focus_busy=self._focus_busy, busy=self.busy, now_ms=self.now_ms()
        )
        if decision["action"] == "ignore":
            return
        self.focus = decision["state"]
        self._persist_focus()
        self.focus_changed.emit()

    def reset_focus(self) -> None:
        self._reset_focus()

    def end_focus_early(self) -> None:
        """End a session on the student's word: the whole minutes already worked count toward the
        homework or block, as the End question says, but nothing is finished by it."""
        decision = end_early_decision(self.focus, self.week_start, self.preferences, self.now_ms())
        if decision["credit"]:
            self.credit_focus_session(decision["minutes"], finished=False)
        self._reset_focus()

    def focus_elapsed_min(self) -> int:
        """Whole minutes of the work session running or paused, which are credited to the homework only
        when it ends. A homework is credited whichever week is open; a block, only from its own week."""
        return elapsed_minutes(self.focus, self.week_start, self.preferences, self.now_ms())

    def tick_focus(self) -> None:
        step = tick_step(
            self.focus, credits_waiting=bool(self._credits_waiting), busy=self.busy, now_ms=self.now_ms()
        )
        if step["credit"]:
            self._credit_waiting_sessions()
            # Crediting can save, which can change or end the timer: decide again on what is left.
            step = tick_step(self.focus, credits_waiting=False, busy=self.busy, now_ms=self.now_ms())
        if step["action"] == "ended" and self.focus is not None:
            self.focus["running"] = False
            self.focus["remainingMs"] = 0
            self.advance_focus(completed=True)
        elif step["action"] == "changed":
            self.focus_changed.emit()

    def advance_focus(self, completed: bool) -> None:
        begin = advance_begin(self.focus, focus_busy=self._focus_busy, completed=completed)
        if not begin["go"]:
            return
        self._focus_busy = True
        try:
            if begin["credit"]:
                self.credit_focus_session()
            # Crediting can save, and a save's reply can drop the timer.
            if self.focus is None:
                return
            plan = advance_plan(
                self.focus,
                completed=completed,
                assignment_known=self.focus.get("assignmentId") in self.assignments,
                prefs=self.preferences,
                now_ms=self.now_ms(),
            )
            if "cycles" in plan:
                self.focus["cycles"] = plan["cycles"]
            if plan["alert_first"]:
                self.alerts.emit([plan["alert"]])
            self.focus = plan["state"]
            self._persist_focus()
            self.focus_changed.emit()
            if not plan["alert_first"]:
                self.alerts.emit([plan["alert"]])
        finally:
            self._focus_busy = False

    def credit_focus_session(self, minutes: int | None = None, *, finished: bool = True) -> None:
        decision = credit_enqueue_decision(
            self.focus, prefs=self.preferences, minutes=minutes, finished=finished, busy=self.busy
        )
        if decision["action"] == "ignore":
            return
        credit = decision["credit"]
        held = (credit["state"], credit["work_min"], credit["finished"])
        if decision["action"] == "enqueue":
            # A save is under way and its reply replaces the homework, which would wipe the minutes
            # added now. They are added once it is done.
            self._credits_waiting.append(held)
            return
        self._credit_session(*held)

    def _credit_waiting_sessions(self) -> None:
        waiting, self._credits_waiting = self._credits_waiting, []
        for credit in waiting:
            self._credit_session(*credit)

    def _credit_session(self, state: dict, work_min: int, finished: bool = True) -> None:
        plan = credit_plan(
            state,
            week_start=self.week_start,
            assignments=self.assignments,
            blocks=self.blocks,
            work_min=work_min,
        )
        if "say" in plan:
            self._say(plan["say"])
            return
        if "skip" in plan:
            return
        applied = apply_credit_blocks(self.blocks, plan["to"], plan["updated"])
        self._draft_command(
            "credit_focus", homework=applied["homework"], blocks=applied["blocks"], mark_dirty=True
        )
        if finished:
            self._auto_complete_session(state)
        self.save(record_history=False)

    def _material_focus_rules(self) -> bool:
        return self.material_owns is not None and bool(self.material_owns())

    def focus_mutes_alerts(self) -> bool:
        """Auto-mute: reminders wait while a focus work phase is under way, running or paused."""
        return mutes_alerts(self.focus, self.preferences, self._material_focus_rules())

    def hold_alerts(self, notices: list[dict]) -> list[dict]:
        """The notices to show now. Focus's own are always shown; reminders are kept until focus
        leaves its work phase. Alarms the student set do not come through here and still ring."""
        split = split_held(notices, self.focus, self.preferences, self._material_focus_rules())
        if not split["hold"]:
            return notices
        self._held_alerts.extend(split["hold"])
        return split["show"]

    def release_held_alerts(self) -> list[dict]:
        if not release_held(self._held_alerts, self.focus, self.preferences, self._material_focus_rules()):
            return []
        held, self._held_alerts = self._held_alerts, []
        return held

    def _auto_complete_session(self, state: dict) -> None:
        """Auto-complete: the block this session worked on goes to Done and nothing else does. Its
        homework is finished too only when that was its last session; with sessions left it stays open."""
        plan = auto_complete_plan(
            state,
            prefs=self.preferences,
            material_owns=self._material_focus_rules(),
            week_start=self.week_start,
            assignments=self.assignments,
            blocks=self.blocks,
        )
        applied = apply_auto_complete_blocks(self.blocks, plan["block"])
        if applied["changed"]:
            self._draft_command("credit_focus", blocks=applied["blocks"])
        if plan["complete_homework"]:
            self.complete_homework(plan["complete_homework"], True)

    def _apply_focused_finish(self, plan: dict) -> bool:
        self._draft_command("credit_focus", blocks=plan["blocks"])
        self.complete_homework(plan["assignment_id"], True)
        self._reset_focus()
        self.save()
        return True

    def finish_focused_homework(self) -> str | bool:
        """Return finished, queued, or False. Queued waits for the other week's load."""
        plan = finish_focused_plan(
            self.focus,
            busy=self.busy,
            focus_busy=self._focus_busy,
            week_start=self.week_start,
            blocks=self.blocks,
            assignments=self.assignments,
        )
        if plan["action"] == "ignore":
            return False
        if plan["action"] == "load_then_finish":
            self._finish_focus_waiting = True
            self._finish_focus_week = plan["week"]
            self.load_week(plan["week"])
            if self.account is None:
                self._clear_finish_intent()
            # A synchronous restore finishes before this returns. A fetch is still in flight.
            # A load that stayed on the open week has already cleared the wait.
            if self.focus is None:
                return "finished"
            if self._finish_focus_waiting:
                return "queued"
            return False
        self._apply_focused_finish(plan)
        return "finished"

    def _finish_loaded_focus(self, *, loaded: bool) -> None:
        plan = finish_after_load(
            waiting=self._finish_focus_waiting,
            pending=self._finish_focus_week,
            load_ok=loaded,
            state=self.focus,
            busy=self.busy,
            focus_busy=self._focus_busy,
            week_start=self.week_start,
            blocks=self.blocks,
            assignments=self.assignments,
        )
        if plan["action"] == "none":
            return
        self._clear_finish_intent()
        if plan["action"] != "finish":
            return
        self._apply_focused_finish(plan)

    def restart_finished_focus(self) -> bool:
        """Start again on a timer that has run out: a new session on the same homework (or a quick
        one), taking the place of the finished timer without asking to replace it."""
        plan = restart_finished_plan(
            self.focus,
            busy=self.busy,
            focus_busy=self._focus_busy,
            prefs=self.preferences,
            now_ms=self.now_ms(),
        )
        if plan["action"] == "ignore":
            return False
        self.focus = plan["state"]
        self._pending_focus = None
        self._persist_focus()
        self.focus_changed.emit()
        self._open_focus_spotify()
        return True

    def add_focus_time(self, minutes: int) -> bool:
        plan = add_focus_time_plan(
            self.focus,
            busy=self.busy,
            focus_busy=self._focus_busy,
            assignments=self.assignments,
            minutes=minutes,
            prefs=self.preferences,
            now_ms=self.now_ms(),
        )
        if plan["action"] == "ignore":
            return False
        if plan["action"] == "refuse":
            self._say(plan["say"])
            return False
        self.alerts.emit([plan["alert"]])
        self.focus = plan["state"]
        self._draft_command(
            "add_focus_time", homework=plan["homework"], history_label=plan["history_label"]
        )
        self._persist_focus()
        self.focus_changed.emit()
        self.save()
        return True

    def take_focus_break(self) -> bool:
        plan = take_break_plan(
            self.focus, focus_busy=self._focus_busy, prefs=self.preferences, now_ms=self.now_ms()
        )
        if plan["action"] == "ignore":
            return False
        self.alerts.emit([plan["alert"]])
        self.focus = plan["state"]
        self._persist_focus()
        self.focus_changed.emit()
        return True

    def _today_reminder_source(self, today_monday: str) -> dict | None:
        # A parked lookup writes drafts, so it runs only when the open week is not today.
        opened = json.loads(
            flexweek_engine.session_open_reminder_source(
                json.dumps(self.week_start), json.dumps(self.blocks), json.dumps(self.trace), today_monday
            )
        )
        if opened is not None:
            return opened
        parked = self._draft_command("parked", week_start=today_monday)["week"]
        return json.loads(
            flexweek_engine.session_parked_or_cached_source(
                json.dumps(parked),
                json.dumps(self._reminder_week),
                json.dumps(self._reminder_blocks),
                json.dumps(self._reminder_trace),
                today_monday,
            )
        )

    def todays_reminder_blocks(self) -> dict[str, dict] | None:
        """Today's blocks by reminder key, or None while today's week is not known here."""
        clock = self._clock()
        today_monday = flexweek_engine.calendar_monday_of(clock["iso"])
        source = self._today_reminder_source(today_monday)
        if source is None:
            return None
        return json.loads(
            flexweek_engine.session_todays_reminder_blocks(
                json.dumps(source["blocks"]), json.dumps(source["trace"]), clock["iso"]
            )
        )

    def _due_block_alerts(
        self, blocks: list[dict], trace: dict | None, clock: dict
    ) -> tuple[list[dict], list[dict]]:
        due = json.loads(
            flexweek_engine.session_due_block_alerts(
                json.dumps(blocks, default=str),
                json.dumps(trace, default=str),
                clock["iso"],
                clock["minute"],
                json.dumps(self.preferences),
                self.fired_reminders,
                self.played_songs,
            )
        )
        return due["notices"], due["songs"]

    def _request_today_reminders(self, today_monday: str) -> None:
        begun = json.loads(
            flexweek_engine.session_reminder_fetch_begin(
                json.dumps(self._reminder_fetching), self._reminder_ticket, today_monday
            )
        )
        self._reminder_fetching = begun["fetching"]
        self._reminder_ticket = begun["ticket"]
        if not begun["send"]:
            return
        token = begun["ticket"]

        def ok(data: dict) -> None:
            gate = json.loads(
                flexweek_engine.session_reminder_fetch_gate(
                    token,
                    self._reminder_ticket,
                    json.dumps(self.account),
                    json.dumps(self.week_start),
                    today_monday,
                )
            )
            if gate["kind"] == "ignore":
                return
            self._reminder_fetching = None
            parked = None
            if gate["need_parked"]:
                parked = self._draft_command("parked", week_start=today_monday)["week"]
            reply = json.loads(
                flexweek_engine.session_reminder_fetch_apply(
                    gate["need_parked"], json.dumps(parked), json.dumps(data), today_monday
                )
            )
            if reply["kind"] == "cache":
                self._reminder_week = reply["week"]
                self._reminder_blocks = reply["blocks"]
                self._reminder_trace = None
            self._emit_cached_today_reminders(today_monday)

        def failed(_error: ApiError) -> None:
            if flexweek_engine.session_reminder_fetch_failed(token, self._reminder_ticket):
                self._reminder_fetching = None

        self.client.request("GET", f"/api/week?week_start={today_monday}", None, ok, failed)

    def _emit_cached_today_reminders(self, today_monday: str) -> None:
        clock = self._clock()
        if not flexweek_engine.session_cached_reminders_due(
            json.dumps(self.preferences), clock["iso"], today_monday
        ):
            return
        source = self._today_reminder_source(today_monday)
        if source is None:
            return
        notices, songs = self._due_block_alerts(source["blocks"], source["trace"], clock)
        if notices:
            self.alerts.emit(notices)
        for song in songs:
            self._enqueue_alarm(song)

    def check_alerts(self) -> None:
        if self.account is None:
            return
        clock = self._clock()
        # Before the due check: a card whose block starts now frees its key, so "starts now" comes this tick.
        self.reminder_cards.sync()
        begun = json.loads(
            flexweek_engine.session_check_alerts_begin(json.dumps(self.preferences), clock["iso"])
        )
        notices: list[dict] = []
        songs: list[dict] = []
        if begun["today_monday"] is not None:
            source = self._today_reminder_source(begun["today_monday"])
            if source is None:
                self._request_today_reminders(begun["today_monday"])
            else:
                notices, songs = self._due_block_alerts(source["blocks"], source["trace"], clock)
        alarms = json.loads(
            flexweek_engine.session_due_alarm_plan(
                json.dumps(self.preferences),
                self._alarms.songs(),
                clock["iso"],
                clock["day"],
                clock["now_ms"],
                self.last_alarm_check,
                self.fired_alarms,
                json.dumps(self.snoozed_alarms),
                datetime.fromisoformat,
            )
        )
        self.snoozed_alarms = alarms["snoozed_alarms"]
        self.last_alarm_check = alarms["last_alarm_check"]
        if notices:
            self.alerts.emit(notices)
        for song in songs:
            self._enqueue_alarm(song)
        for alarm in alarms["queued"]:
            self._enqueue_alarm(alarm)

    @property
    def active_alarm(self) -> dict | None:
        """The alarm ringing now (the engine holds it; this is a copy)."""
        return json.loads(self._alarms.active())

    @property
    def alarm_queue(self) -> list[dict]:
        """The alarms waiting their turn, in order (a copy)."""
        return json.loads(self._alarms.waiting())

    @property
    def _snoozed_songs(self) -> dict[str, dict]:
        """Block songs a snooze keeps to ring again, by alarm id (a copy)."""
        return json.loads(self._alarms.songs())

    def _enqueue_alarm(self, alarm: dict) -> None:
        if self._alarms.enqueue(json.dumps(alarm, default=str)):
            self.alarm_due.emit(alarm)

    def finish_alarm(self, snooze: bool = False) -> None:
        answer = json.loads(self._alarms.finish(snooze, self.now_ms() if snooze else 0))
        if answer["snoozed"] is not None:
            self.snoozed_alarms[answer["snoozed"]["id"]] = answer["snoozed"]["until_ms"]
        self.alarm_due.emit(answer["next"])

    def spotify_url(self, value: str | None = None) -> str:
        """A link handed in, checked, or the Settings link when nothing was handed in.

        Alarms pass their own link. More and a block start pass nothing and get the Settings link.
        A link stored on a block is not read.
        """
        return flexweek_engine.session_resolve_spotify_url(json.dumps(self.preferences), json.dumps(value))

    def save_preferences(self, updates: dict, then: Callable[[bool], None] | None = None) -> bool:
        """Send the changes. `then` is told whether the server kept them, once it has answered."""
        if self.account is None or self.preferences is None:
            return False
        body = json.loads(
            flexweek_engine.session_preferences_body(
                json.dumps(self.preferences), json.dumps(updates)
            )
        )
        ticket = self._begin()
        self._say("Saving preferences…")

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            self.preferences = data
            self._say("Saved preferences.")
            self.week_changed.emit()
            if then is not None:
                then(True)

        def failed(error: ApiError) -> None:
            current = self._alive(ticket)
            self._fail(ticket, error)
            if current and then is not None:
                then(False)

        self.client.request("PUT", "/api/preferences", body, ok, failed)
        return True

    def preview_timer_split(self, duration_min: int) -> None:
        if self.account is None or self.preferences is None:
            return
        ticket = self._begin()

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            self.split_preview = data
            self.week_changed.emit()

        self.client.request(
            "POST",
            "/api/timer-split-preview",
            {
                "duration_min": duration_min,
                "timer_work_min": self.preferences.get("timer_work_min"),
                "timer_break_min": self.preferences.get("timer_break_min"),
                "timer_long_break_min": self.preferences.get("timer_long_break_min"),
                "timer_long_break_every": self.preferences.get("timer_long_break_every"),
            },
            ok,
            lambda error: self._fail(ticket, error),
        )

    def _fetch_timer_tools(self) -> None:
        if self.account is None:
            return

        def presets(data: dict) -> None:
            self.timer_presets = list(data.get("presets") or [])

        def limits(data: dict) -> None:
            self.reminder_limits = dict(data)
            self.week_changed.emit()

        self.client.request("GET", "/api/timer-presets", None, presets, lambda _error: None)
        self.client.request("GET", "/api/reminder-limits", None, limits, lambda _error: None)

    def _fetch_recovery_status(self) -> None:
        if self.account is None:
            return

        def ok(data: dict) -> None:
            self.recovery_remaining = int(data.get("remaining") or 0)
            self.week_changed.emit()

        def storage(data: dict) -> None:
            self.storage_info = data

        self.client.request("GET", "/api/auth/recovery-status", None, ok, lambda _error: None)
        self.client.request("GET", "/api/storage-info", None, storage, lambda _error: None)

    def recover(self, username: str, code: str, password: str) -> None:
        self._start_flow(
            {
                "cmd": "recover",
                "username": username,
                "code": code,
                "password": password,
                "keep": bool(self.keep_signed_in),
            }
        )

    def change_password(self, current_password: str, new_password: str) -> None:
        self._start_flow(
            {"cmd": "change_password", "current_password": current_password, "new_password": new_password}
        )

    def replace_recovery_codes(self, password: str) -> None:
        self._start_flow({"cmd": "replace_recovery_codes", "password": password})

    def delete_account(self, password: str) -> None:
        owner = str(self.account["id"]) if self.account else None
        self._start_flow({"cmd": "delete_account", "password": password, "owner": owner})

    def _fetch_restore_points(self) -> None:
        if self.account is None:
            return

        def ok(data: dict) -> None:
            self.restore_points = list(data.get("restore_points") or data.get("points") or [])
            self.week_changed.emit()

        self.client.request("GET", "/api/restore-points", None, ok, lambda _error: None)

    def create_restore_point(self, label: str) -> None:
        if self.account is None or not label.strip():
            self._say("Name the saved copy.")
            return
        key = flexweek_engine.create_restore_operation_key(self.account["id"], label.strip())
        ticket = self._begin()
        self._say("Saving a copy…")

        def ok(data: dict) -> None:
            # The point exists now. The same name asked for again is a new backup, not a retry.
            self._draft_command("forget_attempt", key=key)
            if not self._idle(ticket):
                return
            point = data.get("restore_point") or data
            self.restore_points = json.loads(
                flexweek_engine.restore_points_after_create_json(
                    json.dumps(self.restore_points), json.dumps(point)
                )
            )
            self._say("Saved copy " + point.get("label", label) + ".")
            self.week_changed.emit()

        self.client.request(
            "POST",
            "/api/restore-points",
            {"label": label.strip(), "operation_id": self._operation(key)},
            ok,
            lambda error: self._fail(ticket, error),
        )

    def preview_restore_point(self, point_id: str, on_preview=None) -> None:
        if self.account is None:
            return
        ticket = self._begin()

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            self.restore_preview = data
            self.week_changed.emit()
            if on_preview is not None:
                on_preview()

        def err(error: ApiError) -> None:
            if self._alive(ticket):
                self.restore_preview = None
            self._fail(ticket, error)

        self.client.request(
            "GET",
            f"/api/restore-points/{quote(point_id, safe='')}/preview",
            None,
            ok,
            err,
        )

    def undo_to_restore_point(self, point_id: str) -> None:
        """A notice's Undo for a change from this week on: read the point, then put it back."""
        self.preview_restore_point(point_id, lambda: self.apply_restore_point(point_id))

    def apply_restore_point(self, point_id: str) -> None:
        preview = self.restore_preview
        words = flexweek_engine.restore_guard_words(
            self.account is not None, None if preview is None else json.dumps(preview), point_id
        )
        if words is not None:
            self._say(words)
            return
        assert self.account is not None and preview is not None
        key = flexweek_engine.restore_operation_key(self.account["id"], point_id)
        ticket = self._begin()
        self._say("Restoring…")

        def ok(_data: dict) -> None:
            if not self._idle(ticket):
                return
            self.restore_preview = None
            self._draft_command("history_clear")
            self._focus_after_restore = True
            self._say("Restored.")
            self.load_week(self.week_start, said="Restored.")
            self._fetch_restore_points()

        def err(error: ApiError) -> None:
            if self._alive(ticket) and error.status == 409:
                self.restore_preview = None
            self._fail(ticket, error)

        self.client.request(
            "POST",
            f"/api/restore-points/{quote(point_id, safe='')}/restore",
            {"state_token": preview["state_token"], "operation_id": self._operation(key)},
            ok,
            err,
        )

    def export_account(self, password: str, on_snapshot) -> None:
        words = flexweek_engine.transfer_blocked_words(
            self.account is None or self.dirty, len(self.dirty_assignments), "export"
        )
        if words is not None:
            self._say(words)
            return
        ticket = self._begin()

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            on_snapshot(data)

        self.client.request(
            "POST",
            "/api/account-export",
            {"password": password},
            ok,
            lambda error: self._fail(ticket, error),
        )

    def preview_account_import(self, snapshot: dict, on_preview=None) -> None:
        words = flexweek_engine.transfer_blocked_words(
            self.account is None or self.dirty, len(self.dirty_assignments), "import"
        )
        if words is not None:
            self._say(words)
            return
        ticket = self._begin()

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            self.transfer_preview = {"snapshot": snapshot, **data}
            self.week_changed.emit()
            if on_preview is not None:
                on_preview()

        def err(error: ApiError) -> None:
            if self._alive(ticket):
                self.transfer_preview = None
            self._fail(ticket, error)

        self.client.request(
            "POST",
            "/api/account-import/preview",
            {"snapshot": snapshot},
            ok,
            err,
        )

    def apply_account_import(self) -> None:
        preview = self.transfer_preview
        if self.account is None or preview is None:
            return
        words = flexweek_engine.transfer_blocked_words(self.dirty, len(self.dirty_assignments), "import")
        if words is not None:
            self._say(words)
            return
        key = flexweek_engine.import_operation_key(
            self.account["id"], json.dumps(preview.get("state_token"))
        )
        ticket = self._begin()

        def ok(_data: dict) -> None:
            if not self._idle(ticket):
                return
            self.transfer_preview = None
            self._draft_command("history_clear")
            self._say("Imported account data.")
            self.load_week(self.week_start, discard=True)
            self._fetch_restore_points()

        def err(error: ApiError) -> None:
            if self._alive(ticket) and error.status == 409:
                self.transfer_preview = None
            self._fail(ticket, error)

        self.client.request(
            "POST",
            "/api/account-import",
            {
                "snapshot": preview["snapshot"],
                "state_token": preview["state_token"],
                "operation_id": self._operation(key),
            },
            ok,
            err,
        )

    def week_file(self) -> dict:
        return export_week_payload(self.week_start, self.blocks, self.assignments)

    def day_file(self, day: int) -> dict:
        return export_day_payload(self.week_start, day, self.blocks, self.assignments)

    def import_week_file(self, raw: str, *, replace: bool | None = None) -> bool:
        parsed = parse_import_payload(raw)
        target = parsed.get("week_start") or self.week_start
        decision = json.loads(
            flexweek_engine.import_week_decision_json(
                json.dumps(parsed),
                self.week_start,
                week_label(self.week_start, self.today_iso()),
                week_label(target, self.today_iso()),
                json.dumps(self.blocks),
                json.dumps(self.assignments),
                replace,
            )
        )
        if "say" in decision:
            self._say(decision["say"])
            return False
        self._touch("the import", blocks=decision["blocks"], homework=decision["create"])
        self.save()
        return True
