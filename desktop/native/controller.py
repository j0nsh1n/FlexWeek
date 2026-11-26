"""Account, week drafts and solver results for the native desktop window."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import QObject, QTimer, Signal

from backend import clock as wall_clock
from backend.assignments import unplanned_minutes
from backend.models import parse_due
from backend.slots import hhmm_to_minutes
from backend.weeks import current_week_start
from desktop.native.calendar import (
    apply_block_edit,
    apply_repeat_changes,
    block_family,
    blocks_by_weekday,
    date_for_day,
    day_in_week,
    day_names,
    days_through,
    delete_occurrence,
    due_day_in_week,
    first_plannable_day,
    hand_move,
    is_series,
    is_standing_block,
    local_stamp,
    monday_of,
    month_anchor_date,
    month_for_view,
    one_day_note,
    repeat_changes,
    repeat_leaves_week,
    replaced_repeat_on_shown_week,
    routine_on_week,
    shifted_month,
    stored_weeks_of,
    week_start_on,
    windows_on_week,
)
from desktop.native.client import SESSION_ENDED, ApiError, NativeClient
from desktop.native.files import (
    export_day_payload,
    export_week_payload,
    parse_import_payload,
)
from desktop.native.focus import (
    advance_begin,
    advance_plan,
    alerts_held,
    auto_complete_plan,
    begin_state,
    break_phase,
    credit_plan,
    drop_missing,
    elapsed_minutes,
    enter_phase,
    focus_candidates,
    more_time_choices,
    mutes_alerts,
    now_and_next,
    now_next_line,
    pause_state,
    persist_payload,
    quick_focus_homework,
    rebase_state,
    remaining_ms,
    restore_state,
    set_phase,
    start_decision,
    start_target,
    tick_step,
    work_minutes,
)
from desktop.native.hours.geometry import drag_step
from desktop.native.kept import KeptSession
from desktop.native.kept_alerts import KeptReminders
from desktop.native.look import sanitize_look
from desktop.native.pomodoro import inflate_for_solve, split_solved
from desktop.native.remind import (
    clock_parts,
    due_alarms,
    due_reminders,
    due_songs,
    reminder_lead_min,
    todays_starts,
)
from desktop.native.reuse import (
    MAX_WEEK_BLOCKS,
    apply_plan,
    available_homework_minutes,
    capacity_problem,
    clear_stale_pins,
    clipboard_fingerprint,
    copied_homework_block,
    done_minutes,
    fair_share,
    is_planned,
    late_from_start,
    late_id,
    left_over_items,
    merge_preview_rows,
    missed_session_ids,
    move_earlier_homework,
    open_rest_sessions,
    plan_open_counts,
    plan_start,
    proposals_from_clipboard,
    restore_point_label,
    routine_rows,
    routine_source_blocks,
    routine_template,
    running_late_block,
    running_late_refusal,
    settle_placements,
    solve_request,
    time_still_needed,
    time_still_needed_parts,
    uncovered_homework_minutes,
    week_label,
    without_missed_times,
)
from desktop.native.weekmodel import (
    WeekModel,
    build_week,
    due_label,
    hhmm_text,
    homework_time_sentence,
    length_label,
    minute_of,
    moved_words,
)

WEEK_OVER = "This week is over, so nothing was planned. Plan this week or a later one."


def first_placed(trace: dict, targets: object) -> tuple[int, int] | None:
    """Where the first homework a plan gave a time is, by day and then minute."""
    spots = [
        (day, minute_of(item["start"]))
        for item in trace.get("placed") or []
        if item["id"] in targets and item.get("start")
        for day in (item.get("days") or [])[:1]
    ]
    return min(spots, default=None)


LEFT_NAMED = 2


def left_sentence(left: object) -> str:
    """Homework with minutes the plan could not give a time, each named with its minutes: "History essay
    still has 10 min with no time." Nothing for no homework, so a plan that left nothing says nothing."""
    items = list(left or [])
    said = "".join(
        f" {title} still has {length_label(minutes)} with no time." for title, minutes in items[:LEFT_NAMED]
    )
    if len(items) > LEFT_NAMED:
        said += f" And {len(items) - LEFT_NAMED} more."
    return said


def plan_sentence(placed: int, waiting: int, left: object = ()) -> str:
    """How much homework a plan placed, counting homework only. `waiting` is homework whose sessions
    found no room; `left` is homework with minutes no session holds, by title and minutes."""
    if placed == 0:
        said = "Nothing placed."
    else:
        said = f"Placed {placed} homework block{'s' if placed != 1 else ''}."
    if waiting:
        said += f" {waiting} with no time yet."
    return said + left_sentence(left)


def spread_ready_sentence(title: str, minutes: int, due: str, today: str) -> str:
    """Spread preview: names the homework and how much is ready before it is due."""
    return f"{title}: {length_label(minutes)} ready to add before {due_label(due, today)}."


HOURS_REFUSED = "Check the days and times of your study hours and protected time."


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


def _stamp_edited(changes: list[dict], edited: str, today: str, first_weekday: int) -> list[dict]:
    """The changes as the save sends them. `keep` stays as the form built it."""
    if edited == "keep":
        return changes
    stamped = []
    for change in changes:
        item = {**change, "edited": edited}
        if edited == "from_today":
            item["today"] = today
            item["first_weekday"] = first_weekday
        stamped.append(item)
    return stamped


def _late_summary(moved: int) -> str:
    if not moved:
        return "Nothing needs to move."
    return f"{moved} task{'s' if moved != 1 else ''} {'moves' if moved == 1 else 'move'}"


def _draft_field(name: str, *, writable: bool = False) -> property:
    def read(session: NativeSession) -> Any:
        return session._draft_view(name)

    def write(session: NativeSession, value: Any) -> None:
        session._draft_command("set", fields={name: value})

    return property(read, write if writable else None)


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
        self.planner_view = "week"
        self.selected_day = wall_clock.today().isoformat()
        self.day_data: dict | None = None
        self.selected_month: str | None = None
        self.month_data: dict | None = None
        # The day weeks start on, on screen (0 Monday to 6 Sunday). It is kept on this computer, so the
        # window tells the session; stored weeks stay keyed by their Monday whatever it is.
        self.first_weekday = 0
        # The first day changed while a change was being saved: the week from it opens once it lands.
        self._refollow_week = False
        # The type a drag on the hours makes, once one is picked under Add. Until then a block made by
        # dragging has none: it used to be School, and an hour of Club counted as school.
        self.armed_category: str | None = None
        self.selected_block_id: str | None = None
        self.selected_occurrence_day: int | None = None
        self._day_ticket = 0
        self._month_ticket = 0
        self._month_cache: dict[tuple[str, str], dict] = {}
        self._month_gen = 0
        self._month_data_gen = 0
        self._month_prefetching: set[tuple[str, str]] = set()
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
        try:
            day = day_in_week(iso_day, self.week_start)
        except ValueError:
            return None
        return day if 0 <= day <= 6 else None

    def _ensure_selected_day(self) -> None:
        # A day of the open week stays, also when that week still starts on the day weeks started on
        # before the first day changed: the new week is opened from it.
        if self.today_column(self.selected_day) is not None:
            return
        try:
            # The same weekday in the open week.
            weekday = day_in_week(self.selected_day, self.shown_week_of(self.selected_day))
        except ValueError:
            self.selected_day = self.week_start
            return
        self.selected_day = date_for_day(self.week_start, weekday)

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
        if self.planner_view == "day":
            self._ensure_selected_day()
            self._fetch_day()
        elif self.planner_view == "month" and self.selected_month:
            self._fetch_month()

    def set_view(self, view: str) -> None:
        if view not in {"day", "week", "month"} or self.account is None:
            return
        if view == "month":
            self.open_month()
            return
        if self.planner_view == "month":
            self._leave_month(view)
            return
        self.planner_view = view
        self._refresh_view()
        self.week_changed.emit()

    def open_day(self, iso_day: str) -> None:
        if self.account is None:
            return
        try:
            date.fromisoformat(iso_day)
        except ValueError:
            return
        shown = self.shown_week_of(iso_day)
        self.selected_day = iso_day
        self.planner_view = "day"
        self.day_data = None
        if shown != self.week_start:
            self.load_week(shown)
            return
        self._fetch_day()
        self.week_changed.emit()

    def today_iso(self) -> str:
        return datetime.fromtimestamp(self.now_ms() / 1000).date().isoformat()

    def open_month(self, month: str | None = None) -> None:
        if self.account is None:
            return
        today = datetime.fromtimestamp(self.now_ms() / 1000).date().isoformat()
        anchor = self.selected_day if self.planner_view == "day" else (
            today if self.today_column(today) is not None else date_for_day(self.week_start, 3)
        )
        self.selected_day = anchor
        self.selected_month = month or month_for_view(anchor)
        self.planner_view = "month"
        self.month_data = None
        self._fetch_month()
        self.week_changed.emit()

    def shift_month(self, amount: int) -> None:
        if self.planner_view != "month" or not self.selected_month:
            return
        nxt = shifted_month(self.selected_month, amount)
        if nxt is None:
            return
        self.selected_month = nxt
        self.month_data = None
        self._fetch_month()
        self.week_changed.emit()

    def _leave_month(self, view: str) -> None:
        if not self.selected_month:
            self.planner_view = view
            self.week_changed.emit()
            return
        today = datetime.fromtimestamp(self.now_ms() / 1000).date().isoformat()
        anchor = self.selected_day if self.selected_day[:7] == self.selected_month else (
            month_anchor_date(self.selected_month, today)
        )
        shown = self.shown_week_of(anchor)
        self.selected_day = anchor
        self.planner_view = view
        if shown != self.week_start:
            self.load_week(shown)
            return
        self._refresh_view()
        self.week_changed.emit()

    def follow_first_weekday(self, first_weekday: int) -> None:
        """A new first day of the week: the month's rows change, so what was kept is asked for again,
        and the open week becomes the one from that day holding the selected day. Changes not yet
        saved are saved first, in the week they were made in."""
        follow = json.loads(
            flexweek_engine.session_follow_first_weekday(
                self.first_weekday, first_weekday, self.account is not None
            )
        )
        self.first_weekday = first_weekday
        self._month_cache.clear()
        self._month_gen += 1
        if self.account is None:
            self._draft_command("set_week_start", week_start=self.shown_week_of(self.selected_day))
        elif follow["refollow"]:
            if follow["rebase_focus"]:
                self._rebase_focus()
            self._refollow_week = True
            self._follow_week()
        if self.planner_view == "month":
            self._fetch_month()
        self.week_changed.emit()

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
        if not self._refollow_week or self.account is None or self.busy or self._held():
            return
        self._refollow_week = False
        anchor = self.selected_day if self.today_column(self.selected_day) is not None else self.week_start
        target = self.shown_week_of(anchor)
        if target != self.week_start:
            self.selected_day = anchor
            self.load_week(target)

    def _fetch_day(self) -> None:
        if self.account is None or self.planner_view != "day":
            return
        asked = self.selected_day
        self._day_ticket += 1
        token = self._day_ticket

        def ok(data: dict) -> None:
            if token != self._day_ticket or self.planner_view != "day" or self.selected_day != asked:
                return
            self.day_data = data
            self.week_changed.emit()

        def err(_error: ApiError) -> None:
            if token != self._day_ticket:
                return
            self.week_changed.emit()

        self.client.request("GET", f"/api/day?date={asked}", None, ok, err)

    def _fetch_month(self) -> None:
        if self.account is None or self.planner_view != "month" or not self.selected_month:
            return
        asked = self.selected_month
        self._month_ticket += 1
        token = self._month_ticket
        gen = self._month_gen
        key = (str(self.account["id"]), asked)
        cached = None if self._held() or self.parked_unsaved_week() else self._month_cache.get(key)
        if cached is not None:
            # Shown at once, then asked for again: another week may have changed since it was kept.
            self.month_data = cached
            self._month_data_gen = gen
            self.week_changed.emit()

        def ok(data: dict) -> None:
            if (
                token != self._month_ticket
                or self.planner_view != "month"
                or self.selected_month != asked
                or gen != self._month_gen
            ):
                return
            self.month_data = data
            self._month_data_gen = gen
            self._month_cache[key] = data
            self.week_changed.emit()

        def err(error: ApiError) -> None:
            if token != self._month_ticket or gen != self._month_gen:
                return
            self._say(error.message)
            self.week_changed.emit()

        self.client.request("GET", self._month_path(asked), None, ok, err)

    def _month_path(self, month: str) -> str:
        # A Monday start asks as it always did; the server's first day is Monday when none is named.
        first = f"&first_day={self.first_weekday}" if self.first_weekday else ""
        return f"/api/month?month={month}{first}"

    def _prefetch_open_week_month(self) -> None:
        """Warm the month most likely to be opened without holding up the week."""
        if self.account is None:
            return
        owner = str(self.account["id"])
        asked = month_for_view(date_for_day(self.week_start, 3))
        key = (owner, asked)
        if key in self._month_cache or key in self._month_prefetching:
            return
        self._month_prefetching.add(key)
        gen = self._month_gen

        def ok(data: dict) -> None:
            self._month_prefetching.discard(key)
            if (
                self.account is not None
                and str(self.account["id"]) == owner
                and data.get("month") == asked
                and gen == self._month_gen
            ):
                self._month_cache[key] = data

        def err(_error: ApiError) -> None:
            self._month_prefetching.discard(key)

        self.client.request("GET", self._month_path(asked), None, ok, err)

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
            self.load_week(self.week_start, discard=True)
        elif kind == "registered":
            data = event["account"]
            self._drop_other_setup(data["id"])
            self.account = {"id": data["id"], "username": data["username"]}
            self.new_account = True
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
        route = self._draft_command(
            "load", requested=week_start or self.shown_week_of(wall_clock.today().isoformat()),
            first_weekday=self.first_weekday, discard=discard, selection=self._selection(),
        )
        if route["action"] == "keep":
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

    def add_block(self, block: dict, *, scope: str = "series", day: int | None = None) -> None:
        validated = _checked_block(block)
        verb = "editing " if any(item["id"] == validated["id"] for item in self.blocks) else "adding "
        blocks = apply_block_edit(self.blocks, validated, scope=scope, day=day)
        self._touch(verb + validated["title"], blocks=blocks, keep={validated["id"]})

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
        if not answer["moved"]:
            self._say(answer["problem"])
            return False
        block = next((item for item in self.blocks if item["id"] == block_id), None)
        if block is not None and not block.get("start"):
            label = "placing " + block["title"]
        elif block is not None and is_series(block):
            label = "moving " + block["title"] + " on one day"
        elif block is not None:
            label = "editing " + block["title"]
        else:
            label = None
        self.needs_time.pop(block_id, None)
        self._touch(label, blocks=answer["blocks"], keep={answer["block_id"]})
        return True

    def place_block(self, block_id: str, from_day: int, day: int, start: int, end: int) -> None:
        """Let a block go at a time. A save already on its way keeps this move and applies it once
        that save has landed, so the reply cannot put the block back where it was."""
        if self.busy:
            self._hand_waiting = (block_id, from_day, day, start, end)
            return
        block = next((item for item in self.blocks if item["id"] == block_id), None)
        if block is None:
            return
        if not self.hand_move(block_id, from_day, day, start, end):
            return
        origin = from_day if from_day in block["days"] else day
        words = moved_words(block, origin, day, start, end, self.week_start)
        # Material has no School hours, so its note points to Setup.
        material = self.material_owns is not None and self.material_owns()
        note = one_day_note(block, origin, not material, self.week_start)
        if note:
            words = f"{words} {note}"
        self.save()
        self.hand_placed.emit(words)

    def _resume_pending(self, busy: bool) -> None:
        if busy:
            return
        if self._hand_waiting is not None:
            waiting, self._hand_waiting = self._hand_waiting, None
            QTimer.singleShot(0, lambda waiting=waiting: self.place_block(*waiting))
        if self.setup_prefs or self.setup_work_windows is not None or self.setup_week:
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
        made = [_checked_block(block) for block in blocks]
        weekly = [deepcopy(item) for item in self.repeats if str(item.get("id", "")).startswith("weekly-")]
        return made + weekly

    def change_repeats(self, after: list[dict], label: str, edited: str = "keep") -> None:
        """The repeats become `after` from this week on: the open week changes now by the rule the
        store applies to later weeks, and the next save sends the changes. `edited` is how a later
        week that has its own edit is treated."""
        changes = repeat_changes(self.repeats, after, self.week_start)
        if not changes:
            return
        stamped = _stamp_edited(changes, edited, self.today_iso(), self.first_weekday)
        send = self._against_saved(changes, after)
        intents = _stamp_edited(send, edited, self.today_iso(), self.first_weekday)
        # From today on, this week and every earlier week stay exactly as they are.
        if stamped and repeat_leaves_week(stamped[0], self.week_start):
            self._touch(label, intents=intents)
            return
        if edited in ("replace", "from_today"):
            # Days on `after` count from Monday. The open week counts from its first day, so the
            # engine turns them. A stop has no body and comes off the week.
            by_id = {item["id"]: item for item in after}
            blocks = self.blocks
            for block_id in {item["id"] for item in changes}:
                blocks = replaced_repeat_on_shown_week(
                    blocks, self.week_start, block_id, by_id.get(block_id)
                )
            repeats = list(after)
        else:
            blocks, repeats = apply_repeat_changes(self.blocks, self.repeats, changes, self.week_start)
        self._touch(label, blocks=blocks, repeats=repeats, intents=intents)

    def _against_saved(self, changes: list[dict], after: list[dict]) -> list[dict]:
        """A repeat that already has a held intent changes again before the server took the first:
        its intent is measured from what the server last said, so it carries both changes."""
        held = {item["id"] for item in self._repeat_send or []}
        if not held & {item["id"] for item in changes}:
            return changes
        from_saved = {
            item["id"]: item for item in repeat_changes(self._saved_repeats, after, self.week_start)
        }
        return [from_saved.get(item["id"], item) if item["id"] in held else item for item in changes]

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
        assignment = self.assignments.get(assignment_id)
        if assignment is None or assignment.get("completed"):
            return False
        updated = deepcopy(assignment)
        updated["spread"] = "spread"
        remaining = unplanned_minutes(
            int(updated.get("estimate_min") or 0),
            int(updated.get("focus_minutes") or 0),
            self.done_minutes_for(assignment_id),
            0,
        )
        session_min = max(15, min(60, remaining - remaining % 15))
        due = str(updated.get("due") or self.week_start)[:10]
        from_date = min(max(self.today_iso(), self.selected_day or self.week_start), due)
        self.add_homework(updated, spread=True)
        self._allow_split_pending = assignment_id
        self.spread_after_save(assignment_id, session_min, from_date)
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
        nothing = "There's nothing to copy from last week yet."
        if self.account is None:
            done(None)
            return
        try:
            before = date.fromisoformat(self.week_start) - timedelta(days=7)
            previous = self.shown_week_of(before.isoformat())
        except ValueError:
            self._say(nothing)
            done(None)
            return
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

        self.client.request("GET", f"/api/week?week_start={previous}", None, ok, fail)

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
        try:
            to_week = self.shown_week_of(to_iso)
            from_week = self.shown_week_of(from_iso)
            from_day = day_in_week(from_iso, from_week)
            to_day = day_in_week(to_iso, to_week)
        except ValueError:
            return None
        clock_now = clock_parts(self.now_ms())
        return flexweek_engine.date_problem_json(
            block_id,
            from_iso,
            to_iso,
            from_week,
            to_week,
            from_day,
            to_day,
            json.dumps(self._block_on_week(block_id, from_week)),
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
        if self.account is None or self.conflict or self.busy or self.pending_save is not None:
            return False
        try:
            from_week = self.shown_week_of(from_iso)
            to_week = self.shown_week_of(to_iso)
        except ValueError:
            return False
        if from_iso == to_iso:
            return True
        problem = self.date_problem(block_id, from_iso, to_iso)
        if problem:
            self._say(problem)
            return False
        key = f"move-to-date|{self.account['id']}|{block_id}|{from_iso}|{to_iso}"
        operation_id = self._operation(key)
        source = self._week_local(from_week)
        dest = source if to_week == from_week else self._week_local(to_week)
        if source is not None and dest is not None:
            return self._commit_move_to_date(
                block_id, from_iso, to_iso, from_week, to_week, source, dest, operation_id, key
            )
        ticket = self._begin()
        needed = [week for week in dict.fromkeys((from_week, to_week)) if self._week_local(week) is None]
        fetched: dict[str, dict] = {}

        def fail(error: ApiError) -> None:
            if self._idle(ticket):
                self._say(error.message)
                self.save_finished.emit(False, self.message)

        def proceed() -> None:
            if not self._alive(ticket):
                return
            source_state = self._week_local(from_week) or fetched[from_week]
            dest_state = (
                source_state if to_week == from_week else (self._week_local(to_week) or fetched[to_week])
            )
            launched = self._commit_move_to_date(
                block_id,
                from_iso,
                to_iso,
                from_week,
                to_week,
                source_state,
                dest_state,
                operation_id,
                key,
                ticket=ticket,
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
        state = self._week_local(week_start)
        if state is None:
            return None
        blocks = state["blocks"]
        index = flexweek_engine.week_block_index([item["id"] for item in blocks], block_id)
        return None if index is None else blocks[index]

    def _commit_move_to_date(
        self,
        block_id: str,
        from_iso: str,
        to_iso: str,
        from_week: str,
        to_week: str,
        source: dict,
        dest: dict,
        operation_id: str,
        attempt_key: str,
        ticket: int | None = None,
    ) -> bool:
        from_day = day_in_week(from_iso, from_week)
        to_day = day_in_week(to_iso, to_week)
        decision = json.loads(
            flexweek_engine.relocate_json(
                block_id,
                from_day,
                to_day,
                from_week,
                to_week,
                json.dumps(source),
                json.dumps(dest),
                json.dumps(self.assignments),
                week_label(to_week, self.today_iso()),
                str(uuid4()),
            )
        )
        if decision["say"] is not None:
            self._say(decision["say"])
            return False
        source_after = decision["source_after"]
        dest_after = decision["dest_after"]
        writes = [_week_write(from_week, source_after, source["revision"])]
        step_weeks = [
            {
                "week_start": from_week,
                "before": deepcopy(source["blocks"]),
                "after": deepcopy(source_after),
            }
        ]
        if dest_after is not None:
            writes.append(_week_write(to_week, dest_after, dest["revision"]))
            step_weeks.append(
                {
                    "week_start": to_week,
                    "before": deepcopy(dest["blocks"]),
                    "after": deepcopy(dest_after),
                }
            )
        title = decision["title"]
        label = "moving " + title + " to another date"
        self._draft_command(
            "submit_batch",
            pending_step={"label": label, "weeks": step_weeks, "assignments": [], "stale": False},
            history_label=label,
            move_attempt=attempt_key,
            pending_save={"weeks": writes, "assignments": [], "operation_id": operation_id, "stay": True},
        )
        self._post_pending(ticket)
        return True

    def delete_homework(self, assignment_id: str) -> bool:
        """Delete homework and its sessions in every week as one undoable change."""
        item = self.assignments.get(assignment_id)
        if item is None or self.account is None or self.conflict:
            return False
        if self.busy or self.dirty or self.pending_save is not None:
            self._say("Saving your last change… Delete will work in a moment.")
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
        blocks = json.loads(unpinned)
        title = (self.assignments.get(assignment_id) or {}).get("title") or "homework"
        self._touch("unpinning " + title, blocks=blocks)
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
        this week alone keeps it here missed on every day, or the standing week would bring it back;
        `every_week` takes it out of the standing week too. `label` names the Undo step when the delete
        is part of a larger change."""
        block = next((item for item in self.blocks if item["id"] == block_id), None)
        if block is None:
            return
        setup = is_standing_block(block)
        family = block_family(block_id)
        if block.get("assignment_id") or scope != "occurrence":
            # School split at a week's seam is School on each side: all of it goes together.
            going = {
                item["id"] for item in self.blocks
                if item["id"] == block_id or (setup and block_family(item["id"]) == family)
            }
            gone = [item for item in self.blocks if item["id"] in going]
            blocks = [item for item in self.blocks if item["id"] not in going]
        else:
            blocks = delete_occurrence(self.blocks, block_id, day)
            gone = [] if any(item["id"] == block_id for item in blocks) else [block]
        repeats = None
        if setup and gone:
            if every_week:
                repeats = [item for item in self.repeats if item["id"] != family]
            else:
                missed = [{**item, "missed_days": list(item.get("days") or [])} for item in gone]
                blocks = [*blocks, *missed]
        if self.selected_block_id == block_id:
            self.select_block(None, None)
        self._touch(label or "deleting " + block["title"], blocks=blocks, repeats=repeats)

    def delete_selected(self) -> bool:
        if self.selected_block_id is None:
            return False
        block = next((item for item in self.blocks if item["id"] == self.selected_block_id), None)
        if block is None:
            return False
        scope = "occurrence" if is_series(block) else "series"
        self.delete_block(block["id"], scope=scope, day=self.selected_occurrence_day)
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
            self._month_cache.clear()
            self._month_gen += 1
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
        if self.planning:
            self._say("Planning… one moment.")
            return
        if self.conflict:
            self._say("This week changed in another window. Choose More > Reload this week, then try again.")
            return
        if self.pending_save is not None:
            if everything:
                self._replan_after_save = True
                self._say("Saving your last change… Plan will work in a moment.")
                return
            self._say("Saving your last change… Plan will work in a moment.")
            return
        self.plan_asked_week = self.week_start
        self.placed_where = ""
        # Plan can move the block the outline is on, so the outline does not stay on it.
        self.select_block(None, None)
        clock = datetime.fromtimestamp(self.now_ms() / 1000)
        start = plan_start(self.week_start, clock)
        if start is not None and start[0] > 6:
            self._say(WEEK_OVER)
            return
        if _prepared_weeks is None:
            earlier = [week for week in self.saved_weeks if week < self.week_start] if only is None else []
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

        prior_input = [
            {"week_start": week_start, **saved}
            for week_start, saved in (_prepared_weeks or {}).items()
        ]
        planning_blocks, _moved, prior_updates = (
            move_earlier_homework(self.blocks, prior_input, self.assignments, self.week_start)
            if only is None
            else (deepcopy(self.blocks), [], [])
        )
        earlier_blocks = [
            block
            for week in prior_input
            for block in week.get("blocks", [])
            if block.get("start") and not block.get("completed")
        ]
        open_blocks = planning_blocks if only is not None else open_rest_sessions(
            planning_blocks, self.assignments, self.week_start, earlier_blocks, self._assignments_basis, clock
        )
        payload, targets = solve_request(
            open_blocks,
            self.assignments,
            self.week_start,
            everything=everything,
            only=only,
            not_before=start,
            now=clock,
            saved_week=self._assignments_basis,
        )
        # Work due after Sunday gets its fair share of this week; the rest waits for next week's Plan.
        first_day = start[0] if start else 0
        first_minute = start[1] if start else 0
        week, shares = fair_share(
            open_blocks,
            self.assignments,
            self._assignments_basis,
            self.week_start,
            first_day,
            first_minute,
            windows_on_week(self.week_start, self.preferences.get("work_windows") or []),
            targets - self._split_whole,
        )
        if shares:
            kept = {block["id"] for block in week}
            payload, targets = solve_request(
                week,
                self.assignments,
                self.week_start,
                only=targets & kept,
                not_before=start,
                now=clock,
                saved_week=self._assignments_basis,
            )
        if earliest_first:
            payload = [
                {**block, "prefer_earliest": True} if block["id"] in targets else block for block in payload
            ]
        if not targets:
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
        if _overdue:
            # Only the solve copy loses its deadline link. Saved sessions keep their homework ID
            # and the homework keeps its missed deadline.
            payload = [
                {**block, "assignment_id": None, "latest": None, "earliest": None, "pinned": False,
                 "prefer_earliest": True,
                 "days": list(range(first_day, 7))}
                if block["id"] in _overdue else block
                for block in payload
            ]
        ticket = self._begin(planning=True)
        self._say("Planning…")

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            original_blocks = self.blocks
            before = self._dump_blocks()
            blocks = apply_plan(
                week, data, targets=targets, assignments=self.assignments, week_start=self.week_start
            )
            if _overdue:
                placed_ids = {item["id"] for item in data["placed"] if item.get("start")}
                failed = _overdue - placed_ids
                originals = {block["id"]: block for block in original_blocks}
                blocks = [
                    dict(originals[block["id"]]) if block["id"] in failed else block
                    for block in blocks
                    if block["id"] not in (failed & (_new_left or set()))
                ]
                for block in blocks:
                    block.pop("prefer_earliest", None)
            sources = {block["id"]: block for block in blocks}
            for share in shares:
                assigned = [
                    item
                    for item in data.get("placed") or []
                    if item.get("assignment_id") == share["assignment_id"]
                    and item.get("start")
                ]
                placed_min = sum(int(item.get("duration_min") or 0) for item in assigned)
                total_min = share["this_week_min"] + share["left_min"]
                share["this_week_min"] = placed_min
                share["left_min"] = max(0, total_min - placed_min)
                share["placed_days"] = sorted(
                    {
                        int(item["days"][0])
                        for item in assigned
                        if item.get("days")
                    }
                )
            data = {
                **data,
                "week_start": self.week_start,
                "shares": shares,
                "placed": [
                    sources.get(item["id"], item)
                    if (item.get("kind") == "locked" or item["id"] in (_overdue or set()))
                    and item["id"] in sources
                    else item
                    for item in data.get("placed") or []
                ],
            }
            placed = sum(1 for item in data["placed"] if item["id"] in targets and item.get("start"))
            # Why each target still has no time is what this plan found, not what the edit that first
            # took its time said: kept, that sentence came back after the next edit and was wrong.
            reasons = {
                item["block_id"]: item["message"]
                for item in data.get("explanations") or []
                if item.get("reason") and item.get("message")
            }
            for block_id in targets:
                if sources.get(block_id, {}).get("start"):
                    self.needs_time.pop(block_id, None)
                elif block_id in reasons:
                    self.needs_time[block_id] = reasons[block_id]
            self._fresh_plan = True
            # Counted on the week as this plan left it, not on the server's number from before it: the
            # sessions just given a time are already out of what is still needed.
            counts = plan_open_counts(
                self.assignments, self._open_week(blocks), self.week_start, self._assignments_basis
            )
            # A homework with minutes in no session is named with all it still needs, a session still waiting
            # included, so it is left out of the plain "with no time yet" count.
            self.plan_remainders = [
                (item["title"], item["minutes"]) for item in self._time_split(blocks) if item["uncovered_min"]
            ]
            self.plan_counts = (placed, counts["waiting_only"])
            self.plan_open = counts["open"]
            self.plan_first = first_placed(data, targets)
            blocks, split_note = self._split_plan(blocks, data, week)
            changed = self._dump_blocks(blocks) != before
            dirty = self.dirty or changed or bool(split_note)
            self._draft_command(
                "apply_plan",
                blocks=blocks if changed else original_blocks,
                trace=data,
                history_label="the focus split" if split_note else "planning the week" if changed else None,
                dirty=dirty,
                prior_updates=prior_updates if changed else None,
                step_id=str(uuid4()) if changed and prior_updates else None,
                clear_plan_step_id=dirty or bool(self.dirty_assignments),
            )
            placed_note = plan_sentence(placed, self.plan_counts[1], self.plan_remainders)
            if earliest_first and len(targets) == 1:
                only_block = sources.get(next(iter(targets)), {})
                placed_note = self._place_now_sentence(only_block)
                if only_block.get("start"):
                    self.placed_where = placed_note
            if split_note:
                placed_note += split_note
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
            {
                "blocks": inflate_for_solve(payload, self.preferences),
                "week_start": self.week_start,
                "now_floor": list(start) if start is not None else None,
            },
            ok,
            err,
        )

    def _place_now_sentence(self, block: dict) -> str:
        """Where Place now put one block, or that it found no room this week."""
        title = block.get("title") or "this homework"
        if not (block.get("start") and block.get("days")):
            return f"No free time this week for {title}."
        day = day_names(self.week_start)[block["days"][0]]
        return f"Placed {title} on {day} {hhmm_text(block['start'])}."

    def _apply_auto_split(self, trace: dict, sources: list[dict] | None = None) -> str:
        blocks, note = self._split_plan(self.blocks, trace, sources)
        if note:
            self._draft_command("apply_plan", blocks=blocks, history_label="the focus split", dirty=True)
        return note

    def _split_plan(
        self, blocks: list[dict], trace: dict, sources: list[dict] | None,
    ) -> tuple[list[dict], str]:
        # The solver reserves room for breaks. Split the placements using the original work lengths.
        planned = blocks if sources is None else sources
        work_minutes = {block["id"]: block.get("duration_min") for block in planned}
        week = [
            {**block, "duration_min": work_minutes[block["id"]]}
            if block["id"] in work_minutes
            else dict(block)
            for block in blocks
        ]
        split, count = split_solved(week, trace, self.preferences)
        return (split, f" Split {count} into focus chunks.") if count else (blocks, "")

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
            self.routines = {item["id"]: item for item in data.get("routines") or []}
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

    def done_minutes_for(self, assignment_id: str | None) -> int:
        """Minutes of this homework's sessions ticked done, in every saved week and this week as it stands:
        with its focus minutes, the larger of the two is its done time."""
        known = self.assignments.get(assignment_id or "")
        # A homework not saved yet has done nothing.
        return done_minutes(known, self._open_week(), self._assignments_basis) if known is not None else 0

    def remaining_for(self, assignment_id: str) -> int:
        return available_homework_minutes(
            self.assignments.get(assignment_id),
            self._open_week(),
            self._assignments_basis,
        )

    def homework_time_needed(self) -> list[dict]:
        """Homework that needs a time. A session whose time has passed unfinished needs one again. In a week
        that is over, the minutes of its missed sessions are also given as `missed_min`, and those of its
        pinned sessions that passed unfinished as `pinned_min`."""
        week = self._open_week()
        needed = time_still_needed(self.assignments, week, self.week_start, self._assignments_basis)
        missed = self._missed_minutes(week)
        pinned = self._pinned_past_minutes(week)
        for item in needed:
            if missed.get(item["assignment_id"]):
                item["missed_min"] = missed[item["assignment_id"]]
            if pinned.get(item["assignment_id"]):
                item["pinned_min"] = min(
                    pinned[item["assignment_id"]], item["minutes"] - item.get("missed_min", 0)
                )
        return needed

    def _pinned_past_minutes(self, week: list[dict]) -> dict[str, int]:
        """Each homework's minutes in pinned sessions that passed unfinished, in a week that is over: the
        open week leaves them out, and no plan moves them, so they are said as pinned in the past."""
        today = datetime.fromtimestamp(self.now_ms() / 1000).date().isoformat()
        if not self.week_start or self.shown_week_of(today) <= self.week_start:
            return {}
        kept = {block["id"] for block in week}
        pinned: dict[str, int] = {}
        for block in self.blocks:
            homework = block.get("assignment_id")
            if homework and block.get("start") and block["id"] not in kept:
                pinned[homework] = pinned.get(homework, 0) + int(block.get("duration_min") or 0)
        return pinned

    def _missed_minutes(self, week: list[dict]) -> dict[str, int]:
        """Each homework's minutes in missed sessions, by homework, in a week that is over and in no other:
        their make-up time is planned from this week, so the week that is over says them as missed rather
        than as still needing a time there. `week` is `_open_week()`, where a missed session has no time."""
        today = datetime.fromtimestamp(self.now_ms() / 1000).date().isoformat()
        if not self.week_start or self.shown_week_of(today) <= self.week_start:
            return {}
        had_time = {block["id"] for block in self.blocks if block.get("start")}
        missed: dict[str, int] = {}
        for block in week:
            homework = block.get("assignment_id")
            if homework and block["id"] in had_time and not block.get("start"):
                missed[homework] = missed.get(homework, 0) + int(block.get("duration_min") or 0)
        return missed

    def _open_week(self, blocks: list[dict] | None = None) -> list[dict]:
        """The week every count of minutes still needed reads: each missed session as one with no time."""
        clock = datetime.fromtimestamp(self.now_ms() / 1000)
        return without_missed_times(
            self.blocks if blocks is None else blocks,
            self.assignments, self.week_start, self._assignments_basis, clock,
        )

    def missed_block_ids(self) -> frozenset[str]:
        """The sessions every look calls missed: the planner's own answer, read at the clock now."""
        clock = datetime.fromtimestamp(self.now_ms() / 1000)
        return missed_session_ids(
            self.blocks, self.assignments, self.week_start, self._assignments_basis, clock
        )

    def _time_split(self, blocks: list[dict] | None = None) -> list[dict]:
        return time_still_needed_parts(
            self.assignments, self._open_week(blocks), self.week_start, self._assignments_basis
        )

    def plan_can_place(self) -> bool:
        """Whether pressing Plan has something to place: a session waiting for a time (a missed one is read
        as waiting), or minutes no session holds that make a whole quarter hour."""
        return any(
            item["waiting_min"] or self.remaining_for(item["assignment_id"]) > 0
            for item in self._time_split()
        )

    def homework_remainders(self) -> list[tuple[str, int, str]]:
        """Homework with minutes that no session holds, by title, those minutes alone and its id: the drawer
        lists them under the cards, which already show the sessions that wait. In a week that is over a
        pinned session that passed is said as such, not as minutes with no time."""
        pinned = self._pinned_past_minutes(self._open_week())
        return [
            (item["title"], item["uncovered_min"] - held, item["assignment_id"])
            for item in self._time_split()
            if item["uncovered_min"] > (held := pinned.get(item["assignment_id"], 0))
        ]

    def minutes_left_for(self, assignment_id: str) -> int:
        """Minutes of this homework that no session holds. `remaining_for` is what Plan can place of them."""
        return uncovered_homework_minutes(
            self.assignments.get(assignment_id), self._open_week(), self._assignments_basis
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
        if not self.selected_block_id:
            self._say("Select a block before copying it.")
            return False
        return self.copy_block(self.selected_block_id, self.selected_occurrence_day, scope)

    def copy_day(self, day: int | None = None) -> bool:
        if self.account is None:
            return False
        if day is None:
            destination = self.paste_destination()
            if destination is None:
                self._say("Select a block or open Day view before copying a day from this week.")
                return False
            day = destination[0]
        decision = json.loads(
            flexweek_engine.clipboard_day_json(
                json.dumps(self.blocks),
                json.dumps(self.trace),
                day,
                self.week_start,
                [str(uuid4()) for _ in self.blocks],
            )
        )
        if decision["clipboard"] is None:
            self._say(decision["words"])
            return False
        self.clipboard = decision["clipboard"]
        self._say(decision["words"])
        self.week_changed.emit()
        return True

    def paste_proposals(
        self,
        target_day: int | None = None,
        target_start: str | None = None,
        *,
        today: date | None = None,
    ) -> list[dict] | None:
        if self.account is None:
            if self.clipboard is None:
                self._say("Copy a block or day before pasting.")
            return None
        ready = json.loads(
            flexweek_engine.paste_ready_json(
                json.dumps(self.clipboard),
                target_day,
                target_start,
                json.dumps(self.blocks),
                json.dumps(self.trace),
                self.selected_block_id,
                self.selected_occurrence_day,
                self.planner_view,
                self.first_weekday,
                self.selected_day,
                (today or wall_clock.today()).isoformat(),
                self.week_start,
            )
        )
        if ready["words"] is not None:
            self._say(ready["words"])
            return None
        available = {item_id: self.minutes_left_for(item_id) for item_id in self.assignments}
        return proposals_from_clipboard(
            self.clipboard["items"],
            kind=self.clipboard["kind"],
            week_start=self.week_start,
            target_day=ready["day"],
            target_start=ready["start"],
            assignments=self.assignments,
            available=available,
        )

    def duplicate_selected(self, scope: str = "auto") -> list[dict] | None:
        source_id = self.selected_block_id
        day = self.selected_occurrence_day
        if source_id is None:
            self._say("Select a block before duplicating it.")
            return None
        prior = deepcopy(self.clipboard)
        # Nothing is left copied, so nothing says so.
        if not self.copy_block(source_id, day, scope, say=False):
            return None
        rows = self.paste_proposals(day if day is not None else 0, None)
        self.clipboard = prior
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
        if self.account is None or self.conflict:
            return False
        # A refused selection must not reserve an attempt: the id is only kept once the rows are accepted.
        held = self._draft_command("attempt", key=attempt_key)["id"] if attempt_key else None
        op_id = operation_id or held or str(uuid4())
        decision = json.loads(flexweek_engine.preview_groups_json(json.dumps(rows), op_id))
        if decision["say"] is not None:
            self._say(decision["say"])
            return False
        by_week = decision["by_week"]
        if attempt_key:
            self._draft_command("attempt", key=attempt_key, new=op_id)
            self._draft_command("preview_attempt", key=attempt_key)
        if list(by_week) == [self.week_start]:
            added = by_week[self.week_start]
            week_words = week_label(self.week_start, self.today_iso())
            problem = capacity_problem(len(self.blocks), len(added), week_words)
            if problem:
                self._say(problem)
                return False
            self._touch(label, blocks=[*self.blocks, *added])
            self.save(snapshot_label=snapshot_label, operation_id=op_id, status=said)
            return True
        self._commit_groups(
            by_week,
            label=label,
            snapshot_label=snapshot_label,
            operation_id=op_id,
            said=said,
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
    ) -> None:
        needed = [week for week in by_week if week != self.week_start]
        ticket = self._begin()
        fetched: dict[str, dict] = {}

        def fail(error: ApiError) -> None:
            self._fail(ticket, error)

        def proceed() -> None:
            if not self._alive(ticket):
                return
            writes = []
            current_after = None
            for week, added in by_week.items():
                if week == self.week_start:
                    blocks = list(self.blocks) + added
                    revision = self.revision
                    current_after = blocks
                else:
                    data = fetched[week]
                    blocks = list(data["blocks"]) + added
                    revision = data["revision"]
                if len(blocks) > MAX_WEEK_BLOCKS:
                    if self._idle(ticket):
                        week_words = week_label(week, self.today_iso())
                        self._say(capacity_problem(len(blocks) - len(added), len(added), week_words))
                    return
                writes.append(_week_write(week, blocks, revision))
            payload: dict = {"weeks": writes, "assignments": [], "operation_id": operation_id}
            if snapshot_label:
                payload["snapshot_label"] = snapshot_label
            self._draft_command(
                "submit_batch", pending_save=payload, blocks=current_after,
                history_label=label if current_after is not None else None,
                capture_step=current_after is not None, save_status=said,
            )
            self._post_pending(ticket)

        def fetch_next() -> None:
            if not needed:
                proceed()
                return
            week = needed.pop()

            def ok(data: dict) -> None:
                if not self._alive(ticket):
                    return
                fetched[week] = data
                fetch_next()

            self.client.request("GET", f"/api/week?week_start={week}", None, ok, fail)

        fetch_next()

    def save_routine(self, name: str, block_ids: list[str] | None = None) -> bool:
        if self.account is None:
            return False
        # A routine keeps weekdays, so it copies the same way whichever day a week starts on.
        sources = routine_source_blocks(blocks_by_weekday(self.week_start, self.blocks))
        if block_ids is not None:
            allowed = set(block_ids)
            sources = [block for block in sources if block["id"] in allowed]
        title = name.strip()
        if not title or not sources:
            self._say("Name the routine and select at least one fixed commitment.")
            return False
        templates = [routine_template(block, str(uuid4())) for block in sources]
        fingerprint = clipboard_fingerprint(
            [{"block": block, "source_day": 0, "scope": "block"} for block in sources]
        )
        key = f"create-routine|{self.account['id']}|{title}|{fingerprint}"
        routine_id = "r-" + self._operation(key)
        ticket = self._begin()
        self._say("Saving routine…")
        body = {"id": routine_id, "name": title, "blocks": templates, "revision": 0}

        def ok(data: dict) -> None:
            if not self._idle(ticket):
                return
            saved = data.get("routine") or data
            self.routines[saved["id"]] = saved
            self._draft_command("forget_attempt", key=key)
            self._say("Saved " + saved["name"] + ".")
            self.week_changed.emit()

        self.client.request(
            "PUT",
            f"/api/routines/{quote(routine_id, safe='')}",
            body,
            ok,
            lambda error: self._fail(ticket, error),
        )
        return True

    def delete_routine(self, routine_id: str) -> None:
        routine = self.routines.get(routine_id)
        if self.account is None or routine is None:
            return
        key = f"delete-routine|{self.account['id']}|{routine_id}|{routine['revision']}"
        operation_id = self._operation(key)
        ticket = self._begin()
        path = (
            f"/api/routines/{quote(routine_id, safe='')}?revision={int(routine['revision'])}"
            f"&operation_id={quote(operation_id, safe='')}"
        )

        def ok(_data: dict) -> None:
            if not self._idle(ticket):
                return
            self.routines.pop(routine_id, None)
            self._draft_command("forget_attempt", key=key)
            self._say("Deleted " + routine["name"] + ".")
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
        routine = self.routines.get(routine_id)
        if routine is None or not days:
            self._say("Choose at least one weekday to copy.")
            return None
        return routine_rows(routine_on_week(week_start, routine), week_start, days)

    def apply_routine(
        self,
        routine_id: str,
        week_start: str,
        days: list[int],
        rows: list[dict] | None = None,
        existing: list[dict] | None = None,
    ) -> bool:
        routine = self.routines.get(routine_id)
        if self.account is None or routine is None:
            return False
        proposals = rows if rows is not None else self.apply_routine_rows(routine_id, week_start, days)
        if not proposals:
            self._say("There's nothing available to add.")
            return False
        key = (
            f"routine|{self.account['id']}|{routine_id}|{routine['revision']}|"
            f"{week_start}|{','.join(str(day) for day in days)}"
        )
        return self.confirm_preview(
            proposals,
            label="the " + routine["name"] + " routine",
            snapshot_label=restore_point_label("Before applying " + routine["name"] + " to " + week_start),
            operation_id=self._operation(key),
            attempt_key=key,
            existing=existing,
            destination=week_start,
        )

    def unfinished(self) -> list[dict]:
        moment = datetime.fromtimestamp(self.now_ms() / 1000)
        today_week = self.shown_week_of(moment.date().isoformat())
        # Left from last week shows on the week on screen that holds today.
        here = self.week_start == today_week
        # The stored week holding that week's first days, as saved, to tell its earlier days apart.
        first_part = self._stored_parts[0]["blocks"] if here and len(self._stored_parts) == 2 else []
        items = left_over_items(
            self.assignments,
            self.saved_weeks,
            today_week,
            moment.isoformat(timespec="minutes"),
            self._open_week(),
            self._assignments_basis,
            first_part,
        )
        return [item for item in items if here or item.get("left_over_state") == "overdue"]

    def _overdue_assignment_ids(self, assignments: dict[str, dict] | None = None) -> set[str]:
        now = datetime.fromtimestamp(self.now_ms() / 1000)
        moment = (now.date(), now.hour * 60 + now.minute)
        return {
            key for key, item in (self.assignments if assignments is None else assignments).items()
            if item.get("due") and not item.get("completed") and parse_due(item["due"]) <= moment
        }

    def consume_unfinished(self) -> list[dict]:
        items = self.unfinished()
        if not items or self.week_start in self._seen_unfinished:
            return []
        self._seen_unfinished.add(self.week_start)
        return items

    def _too_short_to_plan(self, item: dict | None, assignment_id: str) -> str:
        """Said when Plan has nothing to place because what is left does not fill a quarter hour."""
        left = self.minutes_left_for(assignment_id)
        if item is None or left <= 0:
            return ""
        title = item.get("title") or "This homework"
        return f"{title} has {length_label(left)} left, less than the 15 minutes Plan places."

    def plan_unfinished(self, assignment_id: str) -> list[dict] | None:
        item = self.assignments.get(assignment_id)
        minutes = self.remaining_for(assignment_id)
        if item is None or minutes < 15:
            short = self._too_short_to_plan(item, assignment_id)
            self._say(short or "That homework is already fully planned.")
            return None
        due_day = due_day_in_week(item.get("due"), self.week_start)
        days = days_through(due_day, first_plannable_day(self.week_start))
        block = copied_homework_block(item, days[0] if days else 0, minutes, str(uuid4()))
        block["days"] = days or [0]
        return [
            {
                "week_start": self.week_start,
                "day": block["days"][0],
                "fixed": False,
                "block": block,
                "group_id": block["id"],
                "checked": True,
                "invalid": "",
                "original_duration": minutes,
            }
        ]

    def left_unfinished(self) -> list[dict]:
        """Homework whose deadline passed or whose saved session was left in an earlier week."""
        return [item for item in self.unfinished() if item.get("left_over_state") == "left_from_last_week"]

    def plan_left(self, assignment_ids: list[str]) -> None:
        """"Plan into this week": each one gets a session in this week for the time it has left, and Plan
        finds those times as it does any homework's. The time left in the earlier week stays where it was."""
        if self.busy or self.conflict or self.pending_save is not None:
            return
        now = datetime.fromtimestamp(self.now_ms() / 1000)
        start = plan_start(self.week_start, now)
        if start is not None and start[0] > 6:
            self._say(WEEK_OVER)
            return
        first_day = start[0] if start else 0
        overdue = self._overdue_assignment_ids()
        # The line counts a missed session as time with no time, so Plan takes it as it takes a waiting
        # one. The same engine answer the counts read: a pinned session never reads as missed here.
        timeless = {block["id"] for block in self._open_week() if not block.get("start")}
        missed = {block["id"] for block in self.blocks if block.get("start") and block["id"] in timeless}
        # A pinned session that passed stays where the student put it: its minutes get a new session.
        pinned_past = {block["id"] for block in self.blocks if block.get("pinned")} & self.missed_block_ids()
        made: set[str] = set()
        targets: set[str] = set()
        late_targets: set[str] = set()
        short = ""
        added: list[dict] = []
        for assignment_id in assignment_ids:
            item = self.assignments.get(assignment_id)
            if item is None or item.get("completed"):
                continue
            late = assignment_id in overdue
            for block in self.blocks:
                if (
                    block.get("assignment_id") != assignment_id
                    or block.get("completed")
                    or block["id"] in pinned_past
                ):
                    continue
                if block.get("start") and not late and block["id"] not in missed:
                    continue
                targets.add(block["id"])
                if late:
                    late_targets.add(block["id"])
            minutes = self.remaining_for(assignment_id)
            if minutes < 15:
                short = short or self._too_short_to_plan(item, assignment_id)
                continue
            days = list(range(first_day, 7)) if late else days_through(
                due_day_in_week(item.get("due"), self.week_start), first_day
            )
            block = copied_homework_block(item, days[0] if days else 0, minutes, str(uuid4()))
            block["days"] = days or [0]
            added.append(block)
            made.add(block["id"])
            targets.add(block["id"])
            if late:
                late_targets.add(block["id"])
        if not targets:
            self._say(short or "That homework already has a time.")
            return
        dirty_before = self.dirty
        if made:
            self._touch("planning unfinished homework", blocks=[*self.blocks, *added])
        self.solve(only=targets, _overdue=late_targets, _new_left=made, _dirty_before=dirty_before)

    def did_these(self, assignment_ids: list[str]) -> None:
        """"Mark as finished": the student finished them after all, as one Undo step."""
        for assignment_id in assignment_ids:
            if assignment_id in self.assignments:
                self.complete_homework(assignment_id)
        self.save()

    def recover_missed(self, block_id: str, day: int) -> None:
        block = next((item for item in self.blocks if item["id"] == block_id), None)
        if block is None or block.get("kind") != "locked" or day not in (block.get("days") or []):
            return
        if day in (block.get("missed_days") or []):
            self.save()
            return
        ticket = self._begin()
        self._say("Replanning after the miss…")

        def run(previous: list[dict]) -> None:
            payload = {
                "week_start": self.week_start,
                "blocks": self._dump_blocks(),
                "recover": {
                    "missed_block_id": block_id,
                    "missed_day": day,
                    "previous_placed": previous,
                },
            }

            def ok(trace: dict) -> None:
                if not self._idle(ticket):
                    return
                blocks = deepcopy(self.blocks)
                target = next((item for item in blocks if item["id"] == block_id), None)
                if target is None:
                    return
                target["missed_days"] = sorted(set(target.get("missed_days") or []) | {day})
                applied = apply_plan(blocks, trace, assignments=self.assignments, week_start=self.week_start)
                self._touch("the replan", blocks=applied)
                self._draft_command("apply_plan", trace=trace)
                self.save()

            self.client.request(
                "POST",
                "/api/solve",
                payload,
                ok,
                lambda error: self._fail(ticket, error),
            )

        if self.trace and self.trace.get("placed"):
            run(self._dump_blocks(self.trace["placed"]))
            return
        if any(is_planned(block) for block in self.blocks):
            run(self._dump_blocks(self.scheduled_blocks()))
            return

        def base_ok(trace: dict) -> None:
            if not self._alive(ticket):
                return
            run(self._dump_blocks(trace.get("placed") or []))

        self.client.request(
            "POST",
            "/api/solve",
            {"week_start": self.week_start, "blocks": self._dump_blocks()},
            base_ok,
            lambda error: self._fail(ticket, error),
        )

    def preview_running_late(self, minutes: int, now: datetime | None = None) -> None:
        moment = now or wall_clock.now()
        refusal = running_late_refusal(
            week_start=self.week_start,
            now=moment,
            dirty=self.dirty,
            conflict=self.conflict,
            block_count=len(self.blocks),
        )
        if refusal:
            self._say(refusal)
            return
        if minutes not in (15, 30, 60):
            self._say("Choose 15, 30 or 60 minutes.")
            return
        from_start = late_from_start(moment.hour * 60 + moment.minute)
        day = day_in_week(moment.date().isoformat(), self.week_start)
        ticket = self._begin()
        self._say("Replanning…")

        def run(previous: list[dict]) -> None:
            payload = {
                "week_start": self.week_start,
                "blocks": self._dump_blocks(self._late_blocks()),
                "running_late": {
                    "day": day,
                    "minutes": minutes,
                    "from_start": from_start,
                    "now_floor": [day, hhmm_to_minutes(from_start)],
                    "previous_placed": previous,
                },
            }

            def ok(trace: dict) -> None:
                if not self._idle(ticket):
                    return
                operation_id = str(uuid4())
                self.late_preview = {
                    "trace": trace,
                    "operation_id": operation_id,
                    "week_start": self.week_start,
                    "block": running_late_block(day, from_start, minutes, late_id(operation_id)),
                    "stale": False,
                }
                self._say(_late_summary(len(trace.get("moves") or [])))
                self.week_changed.emit()

            self.client.request(
                "POST",
                "/api/solve",
                payload,
                ok,
                lambda error: self._fail(ticket, error),
            )

        if self.trace and self.trace.get("placed"):
            run(self._dump_blocks(self.trace["placed"]))
            return
        if any(is_planned(block) for block in self.blocks):
            run(self._dump_blocks(self.scheduled_blocks()))
            return

        def base_ok(trace: dict) -> None:
            if not self._alive(ticket):
                return
            run(self._dump_blocks(trace.get("placed") or []))

        self.client.request(
            "POST",
            "/api/solve",
            {"week_start": self.week_start, "blocks": self._dump_blocks(self._late_blocks())},
            base_ok,
            lambda error: self._fail(ticket, error),
        )

    def _late_blocks(self) -> list[dict]:
        """The week as Running late replans it. Homework still waiting for a time stays out, so a late
        start never places it: Plan places that homework."""
        return [
            block
            for block in self.blocks
            if not (block.get("kind") == "flexible" and block.get("assignment_id") and not block.get("start"))
        ]

    def accept_running_late(self) -> bool:
        preview = self.late_preview
        if preview is None or preview.get("stale") or preview.get("week_start") != self.week_start:
            return False
        if len(self.blocks) >= MAX_WEEK_BLOCKS:
            self._say("This week already has 100 blocks. Remove one before recording a late start.")
            return False
        blocks = apply_plan(
            [*self.blocks, preview["block"]],
            preview["trace"],
            assignments=self.assignments,
            week_start=self.week_start,
        )
        self._touch("running late", blocks=blocks)
        self._draft_command("apply_plan", trace=preview["trace"])
        self.save(operation_id=preview["operation_id"])
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
            sessions = data.get("sessions") or []
            remaining = int(data.get("remaining_min") or 0)
            if not sessions:
                if remaining:
                    self._say(
                        f"{length_label(remaining)} remains, but it doesn't fit the 15-minute planning grid."
                    )
                else:
                    self._say("All of this homework is already focused or planned.")
                self.spread_preview = None
                # Allow splitting made nothing, so a later Spread of this homework is an ordinary one.
                self._allow_split_pending = None
                return
            rows = []
            total = 0
            for index, session in enumerate(sessions):
                duration = int(session["duration_min"])
                total += duration
                group_id = f"spread-{uuid4()}-{index:x}"
                block = copied_homework_block(item, session["days"][0], duration, group_id)
                rows.append(
                    {
                        "week_start": session["week_start"],
                        "day": session["days"][0],
                        "fixed": False,
                        "block": block,
                        "group_id": group_id,
                        "checked": True,
                        "invalid": "",
                    }
                )
            # Time, not a count of sessions, and the deadline as a student says it: this read
            # "3 sessions · 180 minutes ready to add before 2026-09-27T23:59."
            summary = spread_ready_sentence(item["title"], total, item["due"], self.today_iso())
            if remaining:
                summary += (
                    f" {length_label(remaining)} can't fit the 15-minute grid and has not been "
                    "dropped from the homework total."
                )
            self.spread_preview = {
                "assignment_id": assignment_id,
                "rows": rows,
                "summary": summary,
                "from_date": from_date,
                "session_min": session_min,
            }
            self._say(summary)
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
        item = self.assignments.get(preview["assignment_id"])
        title = item["title"] if item else "homework"
        key = (
            f"spread|{self.account['id']}|{preview['assignment_id']}|"
            f"{preview['from_date']}|{preview['session_min']}"
        )
        operation_id = self._operation(key)
        groups = merge_preview_rows(preview["rows"], operation_id)

        def in_open_week(group: dict) -> bool:
            # A group is keyed by its stored Monday; the week on screen is the one holding its date.
            day = date_for_day(group["week_start"], group["block"]["days"][0])
            return self.shown_week_of(day) == self.week_start

        made = {
            group["block"]["id"]
            for group in groups
            if in_open_week(group) and group["block"].get("assignment_id") == preview["assignment_id"]
        }
        plan_ids = made if self._allow_split_pending == preview["assignment_id"] else set()
        self._plan_after_save |= plan_ids
        # A Spread by hand of the same homework and length makes the same ids as discarded Allow splitting
        # sessions (one operation per attempt); its sessions are not promised a place.
        self._split_whole = (self._split_whole - made) | plan_ids
        ok = self.confirm_preview(
            preview["rows"],
            label="spreading " + title,
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
        if not self.trace:
            return [
                block
                for block in self.blocks
                if block.get("kind") == "locked" or (block.get("kind") == "flexible" and block.get("start"))
            ]
        sources = {block["id"]: block for block in self.blocks}
        merged = []
        for placed in self.trace.get("placed") or []:
            source = sources.get(placed["id"])
            if source is None:
                merged.append(placed)
                continue
            item = dict(source)
            item["days"] = list(placed.get("days") or source.get("days") or [])
            item["start"] = placed.get("start")
            merged.append(item)
        return merged

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

    def _reset_focus(self, persist: bool = True) -> None:
        self.focus = None
        self._focus_busy = False
        self._pending_focus = None
        if persist:
            self._persist_focus()
        self.focus_changed.emit()

    def _restore_focus(self) -> None:
        if self.account is None or self.focus is not None:
            return
        saved = self.focus_store.get(self.account["id"])
        state = restore_state(saved, assignments=self.assignments, blocks=self.blocks, now_ms=self.now_ms())
        if state is None:
            self.focus_store.pop(self.account["id"], None)
            return
        expired = state.pop("expired", False)
        self.focus = state
        self._persist_focus()
        self.focus_changed.emit()
        if expired and state["phase"] == "work":
            self.advance_focus(completed=True)
        elif expired:
            self.focus = set_phase(state, "work", self.preferences, self.now_ms())
            self.focus["running"] = False
            self.focus["remainingMs"] = remaining_ms(self.focus, self.now_ms())
            self._say("The break ended while FlexWeek was closed. Press Resume to focus again.")
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
        if self.account is None or self.busy or self._focus_busy:
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
        if (self.preferences or {}).get("focus_audio") != "spotify":
            return
        link = self.spotify_url()
        if not link:
            self._say("Add a Spotify link in Settings, under Alerts. Focus has started.")
            return
        from desktop.native.spotify import open_in_app

        if not open_in_app(link):
            self._say("Spotify didn't open. Focus has started.")

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
        if self.focus is None or self._focus_busy or self.busy or self.focus.get("phase") == "ended":
            return
        self.focus = pause_state(self.focus, self.now_ms())
        self._persist_focus()
        self.focus_changed.emit()

    def reset_focus(self) -> None:
        self._reset_focus()

    def end_focus_early(self) -> None:
        """End a session on the student's word: the whole minutes already worked count toward the
        homework or block, as the End question says, but nothing is finished by it."""
        minutes = self.focus_elapsed_min()
        if minutes > 0:
            self.credit_focus_session(minutes, finished=False)
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

    def _enter_phase(self, state: dict, phase: str) -> dict:
        """Move to a phase and announce it, which is what the web's setFocusPhase does."""
        entered = enter_phase(state, phase, self.preferences, self.now_ms())
        self.alerts.emit([entered["alert"]])
        moved: dict = entered["state"]
        return moved

    def credit_focus_session(self, minutes: int | None = None, *, finished: bool = True) -> None:
        state = self.focus
        if state is None or not (state.get("blockId") or state.get("assignmentId")):
            return
        worked = work_minutes(state, self.preferences) if minutes is None else minutes
        credit = (dict(state), worked, finished)
        if self.busy:
            # A save is under way and its reply replaces the homework, which would wipe the minutes
            # added now. They are added once it is done.
            self._credits_waiting.append(credit)
            return
        self._credit_session(*credit)

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
        updated = plan["updated"]
        homework = updated if plan["to"] == "assignment" else None
        blocks = None if homework is not None else [
            updated if item["id"] == updated["id"] else item for item in self.blocks
        ]
        self._draft_command("credit_focus", homework=homework, blocks=blocks, mark_dirty=True)
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
        held = alerts_held(
            [item.get("kind") for item in notices],
            self.focus,
            self.preferences,
            self._material_focus_rules(),
        )
        if not any(held):
            return notices
        self._held_alerts.extend(item for item, keep in zip(notices, held, strict=True) if keep)
        return [item for item, keep in zip(notices, held, strict=True) if not keep]

    def release_held_alerts(self) -> list[dict]:
        if not self._held_alerts or self.focus_mutes_alerts():
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
        done = plan["block"]
        if done is not None:
            blocks = [
                {**block, "start": done["start"], "completed": True, "completed_day": done["completed_day"]}
                if block["id"] == done["id"] else block
                for block in self.blocks
            ]
            self._draft_command("credit_focus", blocks=blocks)
        if plan["complete_homework"]:
            self.complete_homework(plan["complete_homework"], True)

    def finish_focused_homework(self) -> bool:
        state = self.focus
        if state is None or state.get("phase") != "ended" or self.busy or self._focus_busy:
            return False
        assignment_id = state.get("assignmentId")
        if not assignment_id or assignment_id not in self.assignments:
            return False
        if state.get("weekStart") != self.week_start:
            self.load_week(state["weekStart"])
            return False
        blocks = deepcopy(self.blocks)
        block = next((item for item in blocks if item["id"] == state.get("blockId")), None)
        if block is not None and block.get("kind") == "flexible":
            if (
                state.get("start")
                and isinstance(state.get("day"), int)
                and state["day"] in (block.get("days") or [])
            ):
                block["start"] = state["start"]
                # A finished day is only valid on a finished block, and finishing the homework below
                # checks every session it has before marking any of them.
                block["completed"] = True
                block["completed_day"] = state["day"]
            elif not isinstance(block.get("completed_day"), int):
                block["start"] = None
        self._draft_command("credit_focus", blocks=blocks)
        self.complete_homework(assignment_id, True)
        self._reset_focus()
        self.save()
        return True

    def restart_finished_focus(self) -> bool:
        """Start again on a timer that has run out: a new session on the same homework (or a quick
        one), taking the place of the finished timer without asking to replace it."""
        state = self.focus
        if state is None or state.get("phase") != "ended" or self.busy or self._focus_busy:
            return False
        target = {
            key: state.get(key) for key in ("weekStart", "blockId", "assignmentId", "day", "start", "title")
        }
        self.focus = begin_state(target, self.preferences, self.now_ms())
        self._pending_focus = None
        self._persist_focus()
        self.focus_changed.emit()
        self._open_focus_spotify()
        return True

    def add_focus_time(self, minutes: int) -> bool:
        state = self.focus
        if state is None or state.get("phase") != "ended" or self.busy or self._focus_busy:
            return False
        assignment = self.assignments.get(state.get("assignmentId"))
        if assignment is None or minutes not in more_time_choices(int(assignment.get("estimate_min") or 0)):
            self._say("Choose how much more time it needs.")
            return False
        homework = {**assignment, "estimate_min": int(assignment["estimate_min"]) + minutes}
        self.focus = self._enter_phase(state, break_phase(int(state.get("cycles") or 0), self.preferences))
        self._draft_command(
            "add_focus_time", homework=homework, history_label="adding time to " + assignment["title"],
        )
        self._persist_focus()
        self.focus_changed.emit()
        self.save()
        return True

    def take_focus_break(self) -> bool:
        state = self.focus
        if state is None or state.get("phase") != "ended" or self._focus_busy:
            return False
        self.focus = self._enter_phase(state, break_phase(int(state.get("cycles") or 0), self.preferences))
        self._persist_focus()
        self.focus_changed.emit()
        return True

    def _today_reminder_source(self, today_monday: str) -> tuple[list[dict], dict | None] | None:
        if self.week_start == today_monday:
            return self.blocks, self.trace
        parked = self._draft_command("parked", week_start=today_monday)["week"]
        if parked is not None:
            return parked["blocks"], parked.get("trace")
        if self._reminder_week == today_monday:
            return self._reminder_blocks, self._reminder_trace
        return None

    def todays_reminder_blocks(self) -> dict[str, dict] | None:
        """Today's blocks by reminder key, or None while today's week is not known here."""
        clock = self._clock()
        source = self._today_reminder_source(monday_of(clock["iso"]))
        if source is None:
            return None
        return {key: block for block, _day, _start, key in todays_starts(source[0], source[1], clock["iso"])}

    def _due_block_alerts(
        self, blocks: list[dict], trace: dict | None, clock: dict, prefs: dict
    ) -> tuple[list[dict], list[dict]]:
        """Today's reminders, and the song for blocks that are starting.

        A link stored on a block is left in the week. The copies handed to the engine have that field
        cleared, so a block start uses the Settings link. It plays only when the alarm sound is
        Spotify. A link saved for Focus does not start a song on its own.
        """
        notices: list[dict] = []
        lead = reminder_lead_min(prefs)

        def quiet(item: dict) -> dict:
            if item.get("spotify_url"):
                return {**item, "spotify_url": None}
            return item

        blocks = [quiet(block) for block in blocks]
        if isinstance(trace, dict):
            placed = trace.get("placed")
            if isinstance(placed, list):
                trace = {
                    **trace,
                    "placed": [quiet(item) if isinstance(item, dict) else item for item in placed],
                }
        # A bad saved link is left out here, as it is when the alarm rings.
        default_link = self.spotify_url(prefs.get("default_spotify_url") or "") or None
        sound_is_spotify = prefs.get("alarm_tone") == "spotify"
        due = due_reminders(
            blocks=blocks,
            trace=trace,
            today_iso=clock["iso"],
            now_min=clock["minute"],
            lead_min=lead,
            fired=self.fired_reminders,
            default_link=default_link,
            sound_is_spotify=sound_is_spotify,
        )
        for item in due:
            self.fired_reminders.add(item["key"])
            notices.append(
                {"title": item["title"], "body": item["body"], "kind": "reminder", "key": item["key"]}
            )
        songs = due_songs(
            blocks=blocks,
            trace=trace,
            today_iso=clock["iso"],
            now_min=clock["minute"],
            lead_min=lead,
            played=self.played_songs,
            default_link=default_link,
            sound_is_spotify=sound_is_spotify,
        )
        self.played_songs.update(song["id"] for song in songs)
        return notices, songs

    def _request_today_reminders(self, today_monday: str) -> None:
        if self._reminder_fetching == today_monday:
            return
        self._reminder_fetching = today_monday
        self._reminder_ticket += 1
        token = self._reminder_ticket

        def ok(data: dict) -> None:
            if token != self._reminder_ticket or self.account is None:
                return
            self._reminder_fetching = None
            if self.week_start == today_monday or self._draft_command(
                "parked", week_start=today_monday
            )["week"] is not None:
                self._emit_cached_today_reminders(today_monday)
                return
            self._reminder_week = data.get("week_start") or today_monday
            self._reminder_blocks = list(data.get("blocks") or [])
            self._reminder_trace = None
            self._emit_cached_today_reminders(today_monday)

        def failed(_error: ApiError) -> None:
            if token != self._reminder_ticket:
                return
            self._reminder_fetching = None

        self.client.request("GET", f"/api/week?week_start={today_monday}", None, ok, failed)

    def _emit_cached_today_reminders(self, today_monday: str) -> None:
        prefs = self.preferences or {}
        if not prefs.get("reminders_enabled"):
            return
        clock = self._clock()
        if monday_of(clock["iso"]) != today_monday:
            return
        source = self._today_reminder_source(today_monday)
        if source is None:
            return
        notices, songs = self._due_block_alerts(source[0], source[1], clock, prefs)
        if notices:
            self.alerts.emit(notices)
        for song in songs:
            self._enqueue_alarm(song)

    def check_alerts(self) -> None:
        if self.account is None:
            return
        clock = self._clock()
        notices: list[dict] = []
        songs: list[dict] = []
        prefs = self.preferences or {}
        # Before the due check: a card whose block starts now frees its key, so "starts now" comes this tick.
        self.reminder_cards.sync()
        if prefs.get("reminders_enabled"):
            today_monday = monday_of(clock["iso"])
            source = self._today_reminder_source(today_monday)
            if source is None:
                self._request_today_reminders(today_monday)
            else:
                notices, songs = self._due_block_alerts(source[0], source[1], clock, prefs)
        queued, self.snoozed_alarms, self.last_alarm_check = due_alarms(
            alarms=[*(prefs.get("alarms") or []), *self._snoozed_songs.values()],
            today_iso=clock["iso"],
            weekday=clock["day"],
            now_ms=clock["now_ms"],
            midnight_ms=clock["midnight_ms"],
            last_check_ms=self.last_alarm_check,
            fired=self.fired_alarms,
            snoozed=self.snoozed_alarms,
        )
        if notices:
            self.alerts.emit(notices)
        for alarm in (*songs, *queued):
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
        from backend.models import valid_spotify_url

        raw = (self.preferences or {}).get("default_spotify_url") if value is None else value
        try:
            return valid_spotify_url(raw) or ""
        except ValueError:
            return ""

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
            self._say("Give the restore point a name.")
            return
        key = flexweek_engine.create_restore_operation_key(self.account["id"], label.strip())
        ticket = self._begin()
        self._say("Saving restore point…")

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
            self._say("Saved restore point " + point.get("label", label) + ".")
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
