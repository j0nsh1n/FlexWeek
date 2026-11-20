"""The Material sheets and the More menu: Add homework, Add fixed time, Running late,
Unfinished, Week as a list, Routines.

QML shows `form` and calls the slots. Every change goes through NativeSession, with the words
and checks the Widgets sheets use. This module does not touch HTTP, SQL, or the engine.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from backend import clock as wall_clock
from backend.slots import DAY_END_MIN, SLOT_MIN, hhmm_to_minutes
from desktop.native.calendar import (
    DAY_FULL,
    DAYS,
    FLEX_CATEGORIES,
    block_family,
    day_full_names,
    day_names,
    is_standing_block,
    routine_on_week,
    sunday_due,
)
from desktop.native.fields import announce
from desktop.native.hours.geometry import drag_step, next_slot
from desktop.native.hours.words import detail_words, plan_placed
from desktop.native.material.bridge_alarms import FULL, MAX_ALARMS, NOT_SAVED, AlarmDraft, with_alarm
from desktop.native.material.bridge_info import SIGN_OUT, about_form, help_form, update_form
from desktop.native.material.bridge_manage import (
    RESTORE_FIRST,
    RESTORE_QUESTION,
    AccountActions,
    account_form,
    restore_form,
)
from desktop.native.material.sheet_block import BlockDraft
from desktop.native.material.sheet_homework import HomeworkDraft
from desktop.native.material.sheet_preview import PreviewDraft
from desktop.native.reuse import (
    LATE_MINUTES,
    late_from_start,
    late_locked_line,
    restore_point_label,
    running_late_refusal,
)
from desktop.native.sheet_rules import (
    LATE_WAIT,
    _late_move,
    _late_summary,
    moved_across_months,
    moved_day_names,
    moved_days_note,
    same_weekday,
    turn_days_keeping_weekdays,
)
from desktop.native.weekmodel import added_words, hhmm_text, length_label

NOTHING_UNFINISHED = "None left"
NOTICE_MS = 10000
WAIT_SAVE = "Saving your last change… Save will work in a moment."
WAIT_DELETE = "Saving your last change… Delete will work in a moment."
UNDO_ALSO = "Undo also takes back anything changed after it."
MAX_NAMED_WEEKS = 3
DISCARD = {
    "id": "discard",
    "title": "Discard your changes?",
    "body": "Your changes will be lost.",
    "answers": [
        {"id": "keep", "label": "Keep editing", "kind": "text"},
        {"id": "discard", "label": "Discard", "kind": "danger"},
    ],
}


def doubled_words(name: str, weeks: list[str], today: date) -> str:
    """Where a new weekly time sits twice: at most three weeks named, then "and N more"."""

    def label(week: str) -> str:
        day = date.fromisoformat(week)
        text = f"{day.day} {day.strftime('%b')}"
        return text if day.year == today.year else f"{text} {day.year}"

    named = [label(week) for week in weeks[:MAX_NAMED_WEEKS]]
    more = len(weeks) - MAX_NAMED_WEEKS
    if more > 0:
        listed = ", ".join(named) + f" and {more} more"
    elif len(named) > 1:
        listed = ", ".join(named[:-1]) + f" and {named[-1]}"
    else:
        listed = named[0]
    one = len(weeks) == 1
    return (
        f"{name} also sits on its own in the {'week' if one else 'weeks'} of {listed}, so it shows twice "
        f"there. Delete the extra one in {'that week' if one else 'those weeks'} if you don't want both."
    )


# The More menu, in one place: id, words, icon.
MORE_ROWS = (
    ("heading", "Planning"),
    ("runningLate", "Running late", "schedule"),
    ("unfinishedOpen", "Unfinished", "event_busy"),
    ("weekListRow", "Week as a list", "list"),
    ("routinesButton", "Routines", "repeat"),
    ("quickFocusAction", "Quick focus", "timer"),
    ("replanAll", "Replan all my homework", "autorenew"),
    ("copyDay", "Copy day", "calendar_view_day"),
    ("copyLastWeek", "Copy last week's fixed times", "content_copy"),
    ("restoreButton", "Copies of this week", "save"),
    ("reloadWeek", "Reload this week", "refresh"),
    ("openSpotify", "Open Spotify link", "link"),
    ("heading", "Help and info"),
    ("helpButton", "Help", "help"),
    ("aboutButton", "About FlexWeek", "info"),
    ("heading", "Account"),
    ("accountButton", "Account", "user"),
    ("signOut", "Sign out", "logout"),
)


class SheetsBridge(QObject):
    """The sheet that is open, if any, and the notice a finished sheet leaves behind."""

    changed = Signal()
    dragRangeCanceled = Signal()

    def __init__(self, window: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("sheetsBridge")
        self._window: Any = window
        self._kind = ""
        self._form: dict = {}
        self._ask: dict = {}
        self._edited_done = None
        self._more = False
        self._drag_range_active = False
        self._notice = ""
        self._notice_undo = False
        # A change from this week on: the notice waits for the restore point the save makes, which its Undo
        # puts back. `_saving_repeat` is the words while the save is in flight (the sheet stays open until
        # it answers), `_restore_words` the words of a notice still waiting for its point.
        self._notice_restore = ""
        self._saving_repeat = ""
        self._restore_words = ""
        self._doubled_name = ""
        self._doubled_waiting: list[str] | None = None
        self._homework: HomeworkDraft | None = None
        self._block: BlockDraft | None = None
        self._alarm: AlarmDraft | None = None
        # The update sheet: what was found, the window's answers to it, and how the download is going.
        self._update: dict | None = None
        self._update_current = ""
        self._update_install: Any = None
        self._update_finished: Any = None
        self._update_skip = False
        self._update_state: dict = {}
        # An update found while another sheet is open waits for it to close, so no typing is lost.
        self._update_waiting: tuple | None = None
        self._sign_out_done: Any = None
        # The Account and Restore points sheets: the answer to a prompt that is up, what the student picked
        # in the list, the name typed for a new copy, and the last thing the session said.
        self._ask_handlers: dict[str, Any] | None = None
        self._preview: PreviewDraft | None = None
        self._restore_selected = ""
        self._restore_label = ""
        self._manage_note = ""
        self._account_actions = AccountActions(window, self._ask_then, self._close)
        # What was typed into a new Add sheet that Esc closed, kept for the next Add of that kind.
        self._kept_homework: HomeworkDraft | None = None
        self._kept_block: BlockDraft | None = None
        self._late_minutes = 30
        self._late_from: datetime | None = None
        self._late_from_start = ""
        self._pending_delete = ""
        self._late_running: dict | None = None
        self._late_error = ""
        self._late_waiting: tuple[str, str] | None = None
        self._routine_id = ""
        self._routine_days: list[int] = []
        # The open week the numbers in _routine_days count from.
        self._routine_week = ""
        # The ticks the last turn moved, as new day to the old (day, week) it came from, until the
        # student touches the row, the sheet is applied, or it closes.
        self._routine_moved: dict[int, tuple[int, str]] = {}
        # Whether the student ticked or unticked a day since the routine was picked: the ticks the
        # routine put there carry no mark when the week start changes.
        self._routine_touched = False
        self._routine_error = ""
        # The moved-day note the open sheet last showed; None until the sheet's first showing.
        self._noted: str | None = None
        self._paused = False
        self._held = False
        self._remaining_ms = NOTICE_MS
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(NOTICE_MS)
        self._timer.timeout.connect(self.dismissNotice)
        session = self._session
        if session is not None:
            session.status.connect(self._on_status)
            session.save_finished.connect(self._on_saved)
            answered = getattr(session, "save_answered", None)
            if answered is not None:
                answered.connect(self._on_save_answered)
            busy = getattr(session, "busy_changed", None)
            if busy is not None:
                busy.connect(self._on_busy)
            account = getattr(session, "account_changed", None)
            if account is not None:
                account.connect(self._drop_kept)

    def _drop_kept(self, _account: object = None) -> None:
        """Typing kept after Esc belongs to the account that typed it."""
        self._kept_homework = None
        self._kept_block = None

    @property
    def _session(self) -> Any:
        return getattr(self._window, "session", None)

    # What QML reads ---------------------------------------------------------------------

    @Property(str, notify=changed)
    def kind(self) -> str:
        return self._kind

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def form(self) -> dict:
        return self._form

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def ask(self) -> dict:
        return self._ask

    @Property(bool, notify=changed)
    def moreOpen(self) -> bool:
        return self._more

    @Property(bool, notify=changed)
    def active(self) -> bool:
        return bool(self._kind) or self._more or bool(self._ask) or self._drag_range_active

    @Slot(bool)
    def setDragRangeActive(self, active: bool) -> None:
        if self._drag_range_active != active:
            self._drag_range_active = active
            self.changed.emit()

    @Property(bool, notify=changed)
    def canSave(self) -> bool:
        session = self._session
        return (
            session is not None and not session.busy and session.pending_save is None and not session.conflict
        )

    def _hold_for_save(self, words: str = WAIT_SAVE) -> bool:
        """True when a write is still in flight. The draft stays; Save stays off."""
        if self.canSave:
            return False
        self._say(words)
        self._publish()
        return True

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def moreEntries(self) -> list:
        return self._more_entries() if self._more else []

    @Property(str, notify=changed)
    def notice(self) -> str:
        return self._notice

    @Property(bool, notify=changed)
    def noticeUndo(self) -> bool:
        return self._notice_undo

    # Opening and closing ----------------------------------------------------------------

    def _open(self, kind: str) -> None:
        self._kind = kind
        self._more = False
        self._ask = {}
        self._ask_handlers = None
        self._manage_note = ""
        self._noted = None
        self._publish()

    def _close(self) -> None:
        late = self._kind == "late"
        done, self._edited_done = self._edited_done, None
        update_done = self._finish_update() if self._kind == "update" else None
        self._kind = ""
        self._ask = {}
        self._ask_handlers = None
        self._restore_label = ""
        self._drag_range_active = False
        self._homework = None
        self._block = None
        self._alarm = None
        self._preview = None
        session = self._session
        if late and session is not None and session.late_preview is not None:
            session.late_preview = None
            session._say("")
        self._publish()
        if done is not None:
            done(None)
        if update_done is not None:
            update_done()

    @Slot()
    def openHomework(self) -> None:
        session = self._session
        if session is None or session.account is None:
            return
        category = session.armed_category
        if category not in FLEX_CATEGORIES:
            category = "assignments"
        kept, self._kept_homework = self._kept_homework, None
        if kept is not None:
            kept.read_clock()
            kept.follow_week(HomeworkDraft(session, category=category).when_day)
        self._homework = kept or HomeworkDraft(session, category=category)
        self._open("homework")

    @Slot(int, int, int)
    def openHomeworkAt(self, day: int, start_min: int, end_min: int) -> None:
        session = self._session
        if session is None or session.account is None:
            return
        if start_min > end_min:
            start_min, end_min = end_min, start_min
        duration = end_min - start_min
        if duration < 15:
            return
        category = session.armed_category
        if category not in FLEX_CATEGORIES:
            category = "assignments"
        due = sunday_due(session.week_start) if session.week_start else None
        start_hhmm = f"{start_min // 60:02d}:{start_min % 60:02d}"
        kept, self._kept_homework = self._kept_homework, None
        if kept is not None:
            kept.read_clock()
            kept.follow_week(HomeworkDraft(session, category=category).when_day)
            kept.use_picked(day, start_hhmm)
            self._homework = kept
            self._open("homework")
            return
        self._homework = HomeworkDraft(
            session,
            category=category,
            due=due,
            when="fixed",
            when_day=day,
            when_time=start_hhmm,
            estimate_min=duration,
        )
        self._open("homework")

    @Slot(str)
    def editHomework(self, assignment_id: str) -> None:
        session = self._session
        assignment = None if session is None else session.assignments.get(assignment_id)
        if assignment is None:
            return
        self._homework = HomeworkDraft(session, assignment)
        self._open("homework")

    @Slot()
    def openBlock(self) -> None:
        session = self._session
        if session is None or session.account is None:
            return
        day, start = self._new_event_values()
        category = session.armed_category
        kept, self._kept_block = self._kept_block, None
        fresh = BlockDraft(
            session, day=day, start=start, category=None if category in FLEX_CATEGORIES else category
        )
        if kept is not None:
            kept.follow_week(fresh.days)
        self._block = kept or fresh
        self._open("block")

    @Slot(int, int, int)
    def openBlockAt(self, day: int, start_min: int, end_min: int) -> None:
        """Add fixed time for a time picked on the grid: that day, that start, that length."""
        session = self._session
        if session is None or session.account is None:
            return
        start_min, end_min = sorted((start_min, end_min))
        # One step is the shortest block a draw makes, as in the Widgets grid.
        if end_min - start_min < drag_step((session.preferences or {}).get("drag_step_min")):
            return
        category = session.armed_category
        kept, self._kept_block = self._kept_block, None
        if kept is not None:
            kept.follow_week(BlockDraft(session, day=day).days)
            kept.use_picked(day, f"{start_min // 60:02d}:{start_min % 60:02d}", end_min - start_min)
            self._block = kept
            self._open("block")
            return
        self._block = BlockDraft(
            session,
            day=day,
            start=f"{start_min // 60:02d}:{start_min % 60:02d}",
            length=end_min - start_min,
            category=None if category in FLEX_CATEGORIES else category,
        )
        self._open("block")

    @Slot(str, int)
    def editBlock(self, block_id: str, day: int) -> None:
        """A block on the week: homework opens Edit homework, a fixed time opens Edit fixed time."""
        session = self._session
        block = next((item for item in session.blocks if item["id"] == block_id), None) if session else None
        if block is None:
            return
        assignment_id = block.get("assignment_id")
        if assignment_id and assignment_id in session.assignments:
            self.editHomework(assignment_id)
            return
        if block.get("kind") != "locked":
            return
        self._block = BlockDraft(session, block, occurrence_day=day if day >= 0 else None)
        self._open("block")

    @Slot(str, int)
    def askDeleteBlock(self, block_id: str, day: int) -> None:
        """Delete from a fixed time's menu: the Edit sheet's own question, with no sheet behind it."""
        session = self._session
        block = next((item for item in session.blocks if item["id"] == block_id), None) if session else None
        if block is None or block.get("kind") != "locked" or block.get("assignment_id"):
            return
        self._block = BlockDraft(session, block, occurrence_day=day if day >= 0 else None)
        self._ask = self._block.delete_question()
        self._publish()

    def _new_event_values(self) -> tuple[int, str]:
        """The next quarter hour still ahead today, or the usual 16:00 on another week."""
        session = self._session
        now = datetime.fromtimestamp(session.now_ms() / 1000)
        today = session.today_column(now.date().isoformat())
        if today is None:
            return 0, "16:00"
        ahead, slot = next_slot(now.hour * 60 + now.minute)
        if today + ahead > 6:
            return 0, "16:00"
        return today + ahead, f"{slot // 60:02d}:{slot % 60:02d}"

    @Slot()
    def closeSheet(self) -> None:
        """Esc, Cancel and a tap on the scrim. A sheet with typed work asks before dropping it."""
        if self._drag_range_active:
            self._drag_range_active = False
            self.dragRangeCanceled.emit()
            self.changed.emit()
            return
        if self._ask:
            edited = self._ask.get("id") == "edited-weeks"
            done, self._edited_done = self._edited_done, None
            self._sign_out_done = None
            handlers, self._ask_handlers = self._ask_handlers, None
            self._ask = {}
            self._publish()
            if edited and done is not None:
                done(None)
            elif handlers is not None and "dismiss" in handlers:
                handlers["dismiss"]()
            return
        draft = self._homework if self._kind == "homework" else self._block if self._kind == "block" else None
        if draft is not None and draft.dirty():
            self._ask = dict(DISCARD)
            self._publish()
            return
        if self._kind == "alarm" and self._alarm is not None and self._alarm.dirty():
            self._ask = dict(DISCARD)
            self._publish()
            return
        self._close()

    @Slot()
    def escapeSheet(self) -> None:
        """Esc. A new Add sheet with typed work closes at once and keeps it for the next Add of its kind;
        anything else (Cancel, a tap on the scrim, an Edit sheet) goes through closeSheet."""
        draft = self._draft()
        if (
            draft is not None
            and not draft.existing
            and draft.dirty()
            and not self._drag_range_active
            and not self._ask
        ):
            if self._kind == "homework":
                self._kept_homework = self._homework
            else:
                self._kept_block = self._block
            self._close()
            return
        self.closeSheet()

    @Slot()
    def forceClose(self) -> None:
        self._close()

    # Add and edit -----------------------------------------------------------------------

    def _draft(self) -> HomeworkDraft | BlockDraft | None:
        return self._homework if self._kind == "homework" else self._block if self._kind == "block" else None

    def _set(self, name: str, value: Any) -> None:
        draft = self._draft()
        if draft is None:
            return
        draft.set(name, value)
        self._publish()

    @Slot(str, str)
    def setText(self, name: str, value: str) -> None:
        self._set(name, value)

    @Slot(str, int)
    def setNumber(self, name: str, value: int) -> None:
        self._set(name, value)

    @Slot(str, bool)
    def setFlag(self, name: str, value: bool) -> None:
        self._set(name, value)

    @Slot(int)
    def toggleDay(self, day: int) -> None:
        if self._block is not None:
            self._block.toggle_day(day)
            self._publish()

    @Slot()
    def next(self) -> None:
        draft = self._draft()
        if draft is None:
            return
        if draft.advance():
            self.save()
            return
        self._publish()

    @Slot()
    def back(self) -> None:
        draft = self._draft()
        if draft is not None:
            draft.back()
            self._publish()

    @Slot(int)
    def goto(self, index: int) -> None:
        draft = self._draft()
        if draft is not None:
            draft.goto(index)
            self._publish()

    @Slot()
    def addLink(self) -> None:
        if self._homework is not None:
            self._homework.add_link()
            self._publish()

    @Slot(int)
    def removeLink(self, index: int) -> None:
        if self._homework is not None:
            self._homework.remove_link(index)
            self._publish()

    @Slot()
    def addCheck(self) -> None:
        if self._homework is not None:
            self._homework.add_check()
            self._publish()

    @Slot(int)
    def toggleCheck(self, index: int) -> None:
        if self._homework is not None:
            self._homework.toggle_check(index)
            self._publish()

    @Slot(int)
    def removeCheck(self, index: int) -> None:
        if self._homework is not None:
            self._homework.remove_check(index)
            self._publish()

    @Slot()
    def save(self) -> None:
        """Add or Save: the sheet's answer, through the session."""
        if self._kind == "homework":
            self._save_homework()
        elif self._kind == "block":
            self._save_block()

    def _save_homework(self) -> None:
        draft, session = self._homework, self._session
        if draft is None or session is None:
            return
        if self._hold_for_save():
            return
        made = draft.candidate()
        if made is None:
            self._publish()
            return
        known = session.assignments.get(made["id"])
        title = made.get("title") or "Homework"
        if draft.spread_requested():
            plan = draft.spread_plan()
            session.add_homework(made, spread=True)
            session.spread_after_save(made["id"], plan["session_min"], plan["from_date"])
            session.save()
        else:
            session.add_homework(made)
            style = (session.preferences or {}).get("planning_style")
            if style == "auto" and known is None and not made.get("completed"):
                # Plan it for me as I add it: new homework gets its time once it is saved.
                session.plan_after_save(made["id"])
            session.save()
        if made.get("completed") and not (known or {}).get("completed"):
            words = f"Finished {title}."
        else:
            words = f"Added {title}" if known is None else f"Saved {title}"
        self._close()
        self._say(words, undo=True)

    def _save_block(self) -> None:
        draft, session = self._block, self._session
        if draft is None or session is None:
            return
        if self._hold_for_save():
            return
        made = draft.candidate()
        if made is None:
            self._publish()
            return
        plan = draft.save_plan(made)
        if plan["kind"] == "ask":
            self._ask = draft.save_question()
            self._publish()
            return
        if plan["kind"] != "plain":
            self._save_repeat(draft, made, plan)
            return
        self._save_week_copy(draft, made)

    def _answer_save(self, choice: str) -> None:
        """The answer to "Change <name>?": this week's copy alone, or the repeat from this week on."""
        draft = self._block
        if draft is None or self._session is None:
            return
        made = draft.candidate()
        if made is None:
            self._publish()
            return
        if choice == "later":
            self._save_repeat(draft, made, draft.save_plan(made))
        else:
            self._save_week_copy(draft, made)

    def _save_repeat(self, draft: BlockDraft, made: dict, plan: dict) -> None:
        """A change to a weekly fixed time from this week on, through the repeats the session holds. The
        save makes a restore point first; the sheet stays until the store has answered, so a refusal (the
        200 limit) shows on it."""
        session = self._session
        kind, body, name = plan["kind"], plan.get("repeat"), made["title"]
        repeats = session.repeats
        if kind in ("add", "make"):
            after = [*repeats, body]
        elif kind in ("later", "ask"):
            after = [body if item["id"] == body["id"] else item for item in repeats]
        else:
            after = [item for item in repeats if item["id"] != draft.family]
        if not self._window._apply_standing(after, f"changing {name}"):  # type: ignore[attr-defined]
            return
        if kind == "make":
            # The one-off is now the repeat: one Undo step, named for the change.
            session.delete_block(draft.original["id"], scope="series", label=f"changing {name}")
        elif kind == "stop":
            alone = {key: value for key, value in made.items() if key != "until"}
            alone["id"] = draft.family[len("weekly-") :]
            session.add_block(alone, scope="series")
        said = {
            "add": f"{name} repeats every week from this week on.",
            "make": f"{name} repeats every week from this week on.",
            "stop": f"{name} stops repeating after this week.",
        }.get(kind, f"Changed {name} from this week on.")
        self._saving_repeat = f"{said} {UNDO_ALSO}"
        self._doubled_name = name
        session.save(snapshot_label=restore_point_label(f"Before changing {name}"))

    def _save_week_copy(self, draft: BlockDraft, made: dict) -> None:
        session = self._session
        before = {item["id"] for item in session.blocks}
        session.add_block(made, scope=draft.scope, day=draft.occurrence_day)
        day = draft.occurrence_day
        if draft.recover_missed() and day is not None:
            # "This day only" splits the series and gives that day a new id.
            ids = {made["id"]} | ({item["id"] for item in session.blocks} - before)
            holder = next(
                (item for item in session.blocks if item["id"] in ids and day in item["days"]), None
            )
            if holder is not None:
                session.recover_missed(holder["id"], day)
                self._close()
                self._say(f"Saved {made['title']}", undo=True)
                return
        session.save()
        existed = made["id"] in before
        self._close()
        self._say(f"Saved {made['title']}" if existed else added_words(made, session.week_start), undo=True)

    @Slot()
    def unpin(self) -> None:
        draft, session = self._homework, self._session
        if draft is None or session is None or not draft.existing:
            return
        if self._hold_for_save():
            return
        if session.unpin_assignment(draft.original["id"]):
            session.save()
        self._close()
        self._say("FlexWeek can move it again.", undo=True)

    @Slot()
    def remove(self) -> None:
        """Delete, on a sheet that is editing something. It asks first."""
        session = self._session
        if self._homework is not None and self._homework.existing:
            title = self._homework.original.get("title") or "this homework"
            self._ask = {
                "id": "delete-homework",
                "title": "Delete homework",
                "body": (
                    f"Delete {title}? Its times on the calendar go too, in every week. You can undo this."
                ),
                "answers": [
                    {"id": "stay", "label": "Cancel", "kind": "text"},
                    {"id": "delete", "label": "Delete", "kind": "danger"},
                ],
            }
        elif self._block is not None and self._block.existing and session is not None:
            self._ask = self._block.delete_question()
        else:
            return
        self._publish()

    def pose_edited(self, ask: dict, done) -> None:
        """The edited-weeks question on the week. `done` is called with the answer, or None to cancel."""
        self._edited_done = done
        self._ask = ask
        self._publish()

    @Slot(str)
    def answer(self, choice: str) -> None:
        """A button on the prompt that is up."""
        asked = self._ask.get("id", "") if self._ask else ""
        if asked == "edited-weeks":
            done, self._edited_done = self._edited_done, None
            self._ask = {}
            self._publish()
            if done is not None:
                done(choice if choice in ("keep", "replace", "from_today") else None)
            return
        self._ask = {}
        handlers, self._ask_handlers = self._ask_handlers, None
        if handlers is not None:
            self._publish()
            run = handlers.get(choice)
            if run is not None:
                run()
            return
        if asked == "sign-out":
            signing_out, self._sign_out_done = self._sign_out_done, None
            self._publish()
            if choice == "yes" and signing_out is not None:
                signing_out()
            return
        if asked == "discard":
            if choice == "discard":
                self._close()
                return
        elif asked == "delete-homework" and choice == "delete":
            self._delete_homework()
            return
        elif asked == "delete-block" and choice in ("delete", "day", "week", "every"):
            self._delete_block(choice)
            return
        elif asked == "block-save" and choice in ("week", "later"):
            self._answer_save(choice)
            return
        elif asked == "delete-alarm" and choice == "delete":
            self._delete_alarm()
            return
        elif asked == "delete-unfinished" and choice == "delete":
            self._delete_unfinished(self._pending_delete)
            return
        self._publish()

    def _delete_homework(self) -> None:
        draft, session = self._homework, self._session
        if draft is None or session is None:
            return
        title = draft.original.get("title") or "this homework"
        if not session.delete_homework(draft.original["id"]):
            # Saving, or another window changed the week: the sheet stays so nothing typed is lost.
            self._say(session.message)
            self._publish()
            return
        self._close()
        self._say(f"Deleted {title}.", undo=True)

    def _delete_block(self, choice: str) -> None:
        draft, session = self._block, self._session
        if draft is None or session is None:
            return
        if self._hold_for_save(WAIT_DELETE):
            return
        block = draft.original
        title = block.get("title") or "this fixed time"
        scope = draft.scope
        if choice == "day":
            scope = "occurrence"
        elif choice in ("week", "every"):
            scope = "series"
        every_week = choice == "every"
        day = draft.occurrence_day
        if every_week and is_standing_block(block):
            family = block_family(block["id"])
            after = [item for item in session.repeats if item["id"] != family]
            if not self._window._apply_standing(after, f"deleting {title}"):  # type: ignore[attr-defined]
                return
            session.save(snapshot_label=restore_point_label(f"Before deleting {title}"))
            self._close()
            words = f"Deleted {title} from this week and every week after. {UNDO_ALSO}"
            self._say(words)
            self._restore_words = words
            return
        session.delete_block(block["id"], scope=scope, day=day, every_week=every_week)
        session.save()
        self._close()
        if every_week:
            self._say(f"Deleted {title} from this week and every week after.")
        elif scope == "occurrence" and day is not None:
            name = day_full_names(session.week_start)[day]
            self._say(f"Deleted {title} on {name} from this week.", undo=True)
        else:
            self._say(f"Deleted {title} from this week.", undo=True)

    # Alarms -----------------------------------------------------------------------------

    def _alarms_now(self) -> list[dict]:
        session = self._session
        return list((getattr(session, "preferences", None) or {}).get("alarms") or [])

    @Slot(str)
    def openAlarm(self, alarm_id: str) -> None:
        """Add (an empty id) or edit an alarm of Settings > Alerts."""
        session = self._session
        if session is None or session.account is None or session.preferences is None:
            return
        alarms = self._alarms_now()
        found = next((item for item in alarms if item.get("id") == alarm_id), None) if alarm_id else None
        if alarm_id and found is None:
            return
        if found is None and len(alarms) >= MAX_ALARMS:
            self._say(FULL)
            return
        self._alarm = AlarmDraft(
            found,
            str(session.preferences.get("alarm_tone") or "chime"),
            session.preferences.get("clock_24h") is True,
        )
        self._open("alarm")

    @Slot(str, str)
    def setAlarmText(self, name: str, value: str) -> None:
        if self._alarm is not None:
            self._alarm.set_text(name, value)
            self._publish()

    @Slot(str, int)
    def setAlarmNumber(self, name: str, value: int) -> None:
        if self._alarm is not None:
            self._alarm.set_number(name, value)
            self._publish()

    @Slot(bool)
    def setAlarmEnabled(self, on: bool) -> None:
        if self._alarm is not None:
            self._alarm.set_enabled(on)
            self._publish()

    @Slot(int)
    def toggleAlarmDay(self, day: int) -> None:
        if self._alarm is not None:
            self._alarm.toggle_day(day)
            self._publish()

    def _write_alarms(self, alarms: list[dict], said: str) -> None:
        session = self._session

        def then(ok: bool) -> None:
            if ok:
                self._close()
                self._say(said)
            elif self._alarm is not None:
                self._alarm.error = NOT_SAVED
                self._publish()

        if not session.save_preferences({"alarms": alarms}, then):
            if self._alarm is not None:
                self._alarm.error = NOT_SAVED
            self._publish()

    @Slot()
    def saveAlarm(self) -> None:
        draft, session = self._alarm, self._session
        if draft is None or session is None or self._kind != "alarm":
            return
        if self._hold_for_save():
            return
        alarms = self._alarms_now()
        if not draft.existing and len(alarms) >= MAX_ALARMS:
            draft.error = FULL
            self._publish()
            return
        made = draft.candidate()
        if made is None:
            self._publish()
            return
        self._write_alarms(with_alarm(alarms, made), "Saved the alarm.")

    @Slot()
    def removeAlarm(self) -> None:
        """Delete, on the edit sheet. It asks first."""
        draft = self._alarm
        if draft is None or not draft.existing:
            return
        name = draft.name.strip() or "this alarm"
        self._ask = {
            "id": "delete-alarm",
            "title": "Delete alarm",
            "body": f"Delete {name}? It will not ring again.",
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text"},
                {"id": "delete", "label": "Delete", "kind": "danger"},
            ],
        }
        self._publish()

    def _delete_alarm(self) -> None:
        draft = self._alarm
        if draft is None or self._hold_for_save():
            return
        left = [item for item in self._alarms_now() if item.get("id") != draft.id]
        self._write_alarms(left, "Deleted the alarm.")

    # Running late -----------------------------------------------------------------------

    def _late_other_week(self) -> bool:
        session = self._session
        now = datetime.fromtimestamp(session.now_ms() / 1000)
        return session.today_column(now.date().isoformat()) is None

    @Slot()
    def openLate(self) -> None:
        session = self._session
        if session is None or session.account is None or self._late_other_week():
            return
        now = datetime.fromtimestamp(session.now_ms() / 1000)
        refusal = running_late_refusal(
            week_start=session.week_start,
            now=now,
            dirty=session.dirty,
            conflict=session.conflict,
            block_count=len(session.blocks),
        )
        if refusal:
            self._more = False
            self._say(refusal)
            self._publish()
            return
        # Rounded up: a start in the quarter hour that has already begun was a time gone by.
        ahead, minute = next_slot(now.hour * 60 + now.minute)
        if ahead:
            minute = DAY_END_MIN - SLOT_MIN
        self._late_from = now.replace(hour=minute // 60, minute=minute % 60, second=0, microsecond=0)
        now_minute = now.hour * 60 + now.minute
        self._late_running = next(
            (
                block
                for block in session.blocks
                if block.get("kind") == "flexible"
                and not block.get("completed")
                and block.get("start")
                and session.today_column(now.date().isoformat()) in (block.get("days") or [])
                and hhmm_to_minutes(block["start"])
                <= now_minute
                < hhmm_to_minutes(block["start"]) + int(block.get("duration_min") or 0)
            ),
            None,
        )
        self._late_from_start = late_from_start(minute)
        self._late_minutes = 30
        self._late_error = ""
        session.late_preview = None
        self._open("late")

    def _late_form(self) -> dict:
        session = self._session
        running = self._late_running
        if running is not None:
            context = (
                f"{running['title']}, {hhmm_text(running['start'])}, moves {self._late_minutes} min later"
            )
        else:
            now = datetime.fromtimestamp(session.now_ms() / 1000)
            context = f"Starting from {hhmm_text(self._late_from_start)} today ({DAY_FULL[now.weekday()]})."
        preview = session.late_preview
        changes: list[str] = []
        summary = ""
        if preview is not None:
            trace = preview.get("trace") or {}
            titles = {block["id"]: block["title"] for block in session.blocks}
            details = {
                block["id"]: block for block in [*(trace.get("placed") or []), *(trace.get("unplaced") or [])]
            }
            for move in trace.get("moves") or []:
                block = details.get(move["block_id"], {})
                title = titles.get(move["block_id"], move["block_id"])
                changes.append(_late_move(move, block, title, session.week_start))
            changes.extend(
                block["title"] + " no longer fits and will stay on the task list."
                for block in trace.get("unplaced") or []
            )
            if not changes:
                changes.append("No homework needs to move.")
            summary = _late_summary(len(trace.get("moves") or []))
        return {
            "kind": "late",
            "heading": "Running late",
            "intro": "Say how late you are and preview what moves. Nothing changes until you accept it.",
            "context": context,
            "minutes": self._late_minutes,
            "choices": [{"value": value, "label": f"{value} minutes"} for value in LATE_MINUTES],
            "previewed": preview is not None,
            "summary": summary,
            "changes": changes,
            "error": self._late_error,
            "wait": LATE_WAIT,
            "busy": bool(session.busy),
        }

    @Slot(int)
    def setLate(self, minutes: int) -> None:
        if self._kind != "late" or self._session.late_preview is not None:
            return
        self._late_minutes = minutes if minutes in LATE_MINUTES else 30
        self._publish()

    @Slot()
    def preview(self) -> None:
        session = self._session
        if self._kind != "late" or session is None or self._late_from is None:
            return
        self._late_error = ""
        session.preview_running_late(self._late_minutes, self._late_from)
        self._publish()

    @Slot()
    def acceptLate(self) -> None:
        session = self._session
        if self._kind != "late" or session is None:
            return
        preview = session.late_preview
        block = None if preview is None else preview.get("block")
        moved = len(((preview or {}).get("trace") or {}).get("moves") or [])
        if not session.accept_running_late() or not isinstance(block, dict):
            self._publish()
            return
        session.select_block(block["id"], (block.get("days") or [0])[0])
        # "Is now locked" waits for the save that stores it.
        self._late_waiting = (block["id"], late_locked_line(block, moved))
        self._kind = ""
        self._publish()

    def _on_status(self, text: str) -> None:
        """The session says "Replanning…" and the preview's count through the same signal. The sheet
        shows the count itself, so only a real problem goes under it."""
        if self._kind == "restore":
            self._manage_note = text
            self._publish()
            return
        if self._kind != "late":
            return
        session = self._session
        preview = session.late_preview or {}
        summary = _late_summary(len((preview.get("trace") or {}).get("moves") or []))
        self._late_error = "" if text == "Replanning…" or (preview and text == summary) else text
        self._publish()

    def _on_busy(self, _busy: bool) -> None:
        if self._kind in ("homework", "block"):
            self._publish()

    def _on_saved(self, stored: bool, said: str) -> None:
        words, self._saving_repeat = self._saving_repeat, ""
        if words:
            if stored:
                self._close()
                self._say(words)
                self._restore_words = words
            elif self._block is not None:
                # The sheet keeps what was typed and the store's sentence; a refused change is taken back, so
                # the week shows what is saved and Save sends a corrected one.
                self._session.drop_refused_save()
                self._block.error = said
                self._publish()
        if self._kind in ("homework", "block"):
            self._publish()
        waiting = self._late_waiting
        if waiting is None:
            return
        block_id, message = waiting
        if not stored:
            self._late_waiting = None
        elif any(item["id"] == block_id for item in self._session.blocks):
            self._late_waiting = None
            self._say(message, undo=True)

    # Unfinished -------------------------------------------------------------------------

    def _unfinished_items(self) -> list[dict]:
        """Overdue and carried homework, then homework that still needs a time and is not already listed."""
        session = self._session
        left = session.unfinished()
        seen = {item["id"] for item in left}
        counted = [
            {
                "id": item["assignment_id"],
                "title": item["title"],
                "remaining_min": item["minutes"],
                "plannable": session.remaining_for(item["assignment_id"]) >= 15,
            }
            for item in session.homework_time_needed()
        ]
        return left + [item for item in counted if item["id"] not in seen]

    def _unfinished_form(self) -> dict:
        rows = []
        for item in self._unfinished_items():
            state = item.get("left_over_state")
            words = {"overdue": "Overdue", "left_from_last_week": "Left from last week"}.get(state or "", "")
            due = item.get("due")
            due_words = ""
            if isinstance(due, str) and due:
                try:
                    day = date.fromisoformat(due[:10])
                    due_words = f" · due {DAYS[day.weekday()]} {day.day} {day.strftime('%b')}"
                except ValueError:
                    due_words = ""
            line = f"{length_label(int(item['remaining_min']))} left{due_words}"
            rows.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "detail": f"{line} · {words}" if words else line,
                    "plannable": bool(item.get("plannable", True)),
                    "overdue": state == "overdue",
                    # Homework with no time left over to place has nothing to start a timer on yet.
                    "focusable": state in ("overdue", "left_from_last_week"),
                }
            )
        return {
            "kind": "unfinished",
            "heading": "Unfinished",
            "intro": "Overdue and left from last week, then homework that still needs a time.",
            "rows": rows,
            "empty": "Nothing is left over." if not rows else "",
        }

    def open_preview(self, draft: PreviewDraft) -> None:
        """What a paste or a copy proposes, as a sheet. Save hands the rows back; Cancel and Esc drop them."""
        self._preview = draft
        self._open("preview")

    @Slot(int, bool)
    def previewCheck(self, index: int, checked: bool) -> None:
        if self._kind == "preview" and self._preview is not None:
            self._preview.check(index, checked)
            self._publish()

    @Slot(int, int)
    def previewDay(self, index: int, day: int) -> None:
        if self._kind == "preview" and self._preview is not None:
            self._preview.set_day(index, day)
            self._publish()

    @Slot(int, str)
    def previewStart(self, index: int, start: str) -> None:
        if self._kind == "preview" and self._preview is not None:
            self._preview.set_start(index, start)
            self._publish()

    @Slot(int, int)
    def previewLength(self, index: int, minutes: int) -> None:
        if self._kind == "preview" and self._preview is not None:
            self._preview.set_duration(index, minutes)
            self._publish()

    @Slot()
    def savePreview(self) -> None:
        draft = self._preview
        if self._kind != "preview" or draft is None or not draft.can_save():
            return
        rows = draft.rows
        save = draft.save
        self._close()
        save(rows)

    @Slot()
    def openUnfinished(self) -> None:
        if self._session is None or self._session.account is None:
            return
        self._open("unfinished")

    @Slot(str)
    def findTime(self, assignment_id: str) -> None:
        """Find a time for one homework: the Widgets row's own two paths."""
        session = self._session
        if session is None or session.assignments.get(assignment_id) is None:
            return
        self._window._plan_unfinished(assignment_id)
        self._publish()

    @Slot(str)
    def startFocusOn(self, assignment_id: str) -> None:
        """Start focus on one unfinished homework, as the Widgets row did. The sheet closes first,
        so the Focus screen opens on the page and not under the sheet."""
        session = self._session
        if session is None or session.assignments.get(assignment_id) is None:
            return
        self._close()
        self._window._start_focus(assignment_id, None)

    @Slot(str)
    def askDeleteUnfinished(self, assignment_id: str) -> None:
        item = self._session.assignments.get(assignment_id)
        if item is None:
            return
        self._pending_delete = assignment_id
        self._ask = {
            "id": "delete-unfinished",
            "title": "Delete homework",
            "body": (
                f"Delete {item.get('title') or 'this homework'}? Its times on the calendar go too, "
                "in every week. You can undo this."
            ),
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text"},
                {"id": "delete", "label": "Delete", "kind": "danger"},
            ],
        }
        self.changed.emit()

    @Slot(str)
    def askDeleteHomework(self, assignment_id: str) -> None:
        """Ask whether to delete homework when triggered outside a sheet (e.g. from Week or Day)."""
        self.askDeleteUnfinished(assignment_id)

    def _delete_unfinished(self, assignment_id: str) -> None:
        session = self._session
        item = session.assignments.get(assignment_id)
        if item is not None and session.delete_homework(assignment_id):
            self._say(f"Deleted {item.get('title') or 'this homework'}.", undo=True)
        self._publish()

    # Week as a list ---------------------------------------------------------------------

    def _week_list_form(self) -> dict:
        session = self._session
        week = session.built_week()
        monday = date.fromisoformat(session.week_start) if session.week_start else None
        rows: list[dict] = []
        # What became of each homework that was not finished in time, as the Widgets week list put it.
        states = {
            item["id"]: "Overdue" if item.get("left_over_state") == "overdue" else "Left from last week"
            for item in session.unfinished()
        }
        for day in range(7):
            stamp = week.day_full(day)
            if monday:
                moment = date.fromordinal(monday.toordinal() + day)
                stamp = f"{week.day_full(day)} {moment.day} {moment.strftime('%b')}"
            rows.append({"type": "heading", "text": stamp})
            items = sorted(week.on_day(day), key=lambda item: (item.start, item.end, item.title))
            if not items:
                rows.append({"type": "none", "text": "Nothing planned"})
            for occurrence in items:
                detail = detail_words(
                    int(occurrence.start),
                    int(occurrence.end),
                    done=occurrence.done,
                    missed=occurrence.missed,
                    pinned=occurrence.pinned,
                    history=states.get(occurrence.assignment_id or "", ""),
                    history_due=str(occurrence.due) if occurrence.due else None,
                    placed_by_plan=plan_placed(occurrence),
                )
                if not occurrence.work:
                    detail += " · Fixed time"
                rows.append(
                    {
                        "type": "item",
                        "title": occurrence.title,
                        "detail": detail,
                        "blockId": occurrence.block_id,
                        "day": day,
                        "words": f"{week.day_full(day)}: {occurrence.title}, {detail}",
                    }
                )
        return {"kind": "weekList", "heading": "Week as a list", "rows": rows}

    @Slot()
    def openWeekList(self) -> None:
        if self._session is None or self._session.account is None:
            return
        self._open("weekList")

    @Slot(str, int)
    def openFromList(self, block_id: str, day: int) -> None:
        self._kind = ""
        self.editBlock(block_id, day)
        if not self._kind:
            self._publish()

    # Routines ---------------------------------------------------------------------------

    def _keep_routine_days(self) -> None:
        """Ticked days keep their weekdays when the open week now starts on another day. The ticks
        whose date changed are remembered, so the row can mark them until the student touches it."""
        week = self._session.week_start or ""
        if week != self._routine_week:
            turned, moved = turn_days_keeping_weekdays(
                self._routine_days, self._routine_week, week
            )
            self._routine_days = turned
            if not self._routine_touched:
                # The routine's own days follow its weekdays into the new week, as picking it again would.
                self._routine_moved = {}
                self._routine_week = week
                return
            # A mark the student has not touched yet stays through another first-day switch; another
            # week from the same first day is a different week, so its marks no longer apply.
            same_start = (
                bool(week)
                and bool(self._routine_week)
                and date.fromisoformat(week).weekday()
                == date.fromisoformat(self._routine_week).weekday()
            )
            kept = (
                {}
                if same_start
                else {
                    same_weekday(day, self._routine_week, week): origin
                    for day, origin in self._routine_moved.items()
                }
            )
            self._routine_moved = {
                **kept,
                **{new: (old, self._routine_week) for old, new in moved},
            }
            self._routine_week = week

    def _routine_form(self) -> dict:
        self._keep_routine_days()
        session = self._session
        routines = sorted(session.routines.values(), key=lambda item: str(item.get("name", "")).lower())
        monday = date.fromisoformat(session.week_start) if session.week_start else None
        rows = []
        for item in routines:
            count = len(item.get("blocks") or [])
            rows.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "detail": f"{count} fixed times",
                    "on": item["id"] == self._routine_id,
                }
            )
        moved_names = {
            new: moved_day_names(old, old_week, new, self._routine_week)
            for new, (old, old_week) in sorted(self._routine_moved.items())
        }
        moved_origin = dict(self._routine_moved)

        def spoken_to(index: int) -> str:
            """The new name when the tick moved into another month, for its chip's spoken name."""
            crossed = index in moved_names and moved_across_months(
                *moved_origin[index], index, self._routine_week
            )
            return moved_names[index][1] if crossed else ""

        moved_note = moved_days_note(list(moved_names.values()))
        days = [
            {
                "value": index,
                "label": day_names(session.week_start)[index] if monday else DAYS[index],
                "date": date.fromordinal(monday.toordinal() + index).day if monday else 0,
                "on": index in self._routine_days,
                "moved": index in self._routine_moved,
                "movedFrom": moved_names[index][0] if index in moved_names else "",
                "movedTo": spoken_to(index),
            }
            for index in range(7)
        ]
        return {
            "kind": "routines",
            "heading": "Routines",
            "intro": "Pick a routine, the week to copy it into and the days to copy.",
            "rows": rows,
            "empty": "No routines saved yet." if not rows else "",
            "days": days,
            "selected": self._routine_id,
            "movedNote": moved_note,
            "error": self._routine_error,
        }

    @Slot()
    def openRoutines(self) -> None:
        if self._session is None or self._session.account is None:
            return
        self._routine_id = ""
        self._routine_days = []
        self._routine_moved = {}
        self._routine_touched = False
        self._routine_error = ""
        self._open("routines")

    @Slot(str)
    def selectRoutine(self, routine_id: str) -> None:
        routine = self._session.routines.get(routine_id)
        if routine is None:
            return
        self._routine_id = routine_id
        if self._session.week_start:
            # A routine keeps weekdays (0 Monday); the day buttons are the open week's days.
            routine = routine_on_week(self._session.week_start, routine)
        days: set[int] = set()
        for block in routine.get("blocks") or []:
            days.update(int(day) for day in block.get("days") or [])
        self._routine_days = sorted(days)
        self._routine_moved = {}
        self._routine_touched = False
        self._routine_error = ""
        self._publish()

    @Slot(int)
    def toggleRoutineDay(self, day: int) -> None:
        days = set(self._routine_days)
        days.symmetric_difference_update({day})
        self._routine_days = sorted(days)
        self._routine_moved = {}
        self._routine_touched = True
        self._routine_error = ""
        self._publish()

    @Slot()
    def applyRoutine(self) -> None:
        session = self._session
        routine = session.routines.get(self._routine_id)
        if routine is None:
            self._routine_error = "Choose a saved routine."
            self._publish()
            return
        if not self._routine_days:
            self._routine_error = "Choose at least one weekday to copy."
            self._publish()
            return
        week = session.week_start
        rows = session.apply_routine_rows(self._routine_id, week, self._routine_days)
        if not rows:
            self._publish()
            return
        for row in rows:
            if row.get("invalid"):
                row["checked"] = False
        if not any(row.get("checked") for row in rows):
            self._routine_error = "There's nothing available to add."
            self._publish()
            return
        name = routine["name"]
        done = session.apply_routine(
            self._routine_id, week, self._routine_days, rows, existing=list(session.blocks)
        )
        if done:
            self._routine_moved = {}
            self._close()
            self._say(f"Added the {name} routine.", undo=True)
            return
        self._publish()

    # The More menu ----------------------------------------------------------------------

    def _more_entries(self) -> list[dict]:
        session = self._session
        rows: list[dict] = []
        left = len(self._unfinished_items()) if session.account is not None else 0
        for row in MORE_ROWS:
            if row[0] == "heading":
                rows.append(
                    {"heading": row[1], "id": "", "label": row[1], "icon": "", "detail": "", "enabled": False}
                )
                continue
            name, label, icon = row
            enabled = True
            detail = ""
            if name == "runningLate":
                enabled = not session.busy and not self._late_other_week()
            elif name == "signOut":
                enabled = not session.busy
            elif name in ("restoreButton", "accountButton"):
                enabled = session.account is not None
            elif name == "unfinishedOpen":
                enabled = bool(left)
                detail = f"{left} left" if left else NOTHING_UNFINISHED
            elif name in ("weekListRow", "routinesButton"):
                enabled = session.account is not None
            elif name == "openSpotify":
                # Only with a link set in Settings, as the plain look's More shows it.
                if not session.spotify_url():
                    continue
                enabled = not session.busy
            elif name in ("copyDay", "copyLastWeek", "reloadWeek"):
                enabled = session.account is not None and not session.busy
                if name == "copyDay":
                    destination = session.paste_destination()
                    if destination is not None:
                        detail = day_full_names(session.week_start)[destination[0]]
            rows.append(
                {
                    "heading": "",
                    "id": name,
                    "label": label,
                    "icon": icon,
                    "enabled": bool(enabled),
                    "detail": detail,
                }
            )
        return rows

    @Slot()
    def openMore(self) -> None:
        if self._session is None:
            return
        self._kind = ""
        self._ask = {}
        self._ask_handlers = None
        self._more = True
        self._publish()

    @Slot()
    def closeMore(self) -> None:
        if self._more:
            self._more = False
            self._publish()

    @Slot(str)
    def moreAction(self, name: str) -> None:
        """A row of More. Each opens a sheet or runs the same window action the Widgets menu runs."""
        entry = next((item for item in self._more_entries() if item["id"] == name), None)
        if entry is None or not entry["enabled"]:
            return
        self._more = False
        opening = {
            "runningLate": self.openLate,
            "unfinishedOpen": self.openUnfinished,
            "weekListRow": self.openWeekList,
            "routinesButton": self.openRoutines,
            "restoreButton": self.openRestore,
            "accountButton": self.openAccount,
        }.get(name)
        if opening is not None:
            opening()
            return
        self._publish()
        window = self._window
        session = self._session
        {
            "quickFocusAction": window._quick_focus,
            "copyDay": window._copy_day,
            "copyLastWeek": window._copy_last_week_fixed,
            "reloadWeek": session.reload,
            "openSpotify": window._open_spotify,
            "replanAll": lambda: window._plan_with_left_over(everything=True),
            "helpButton": window._open_help,
            "aboutButton": window._open_about,
            "signOut": window._log_out,
        }[name]()

    # Help, About, Update and the Sign out question ---------------------------------------

    @Slot()
    def openHelp(self) -> None:
        self._open("help")

    @Slot()
    def openAbout(self) -> None:
        self._open("about")

    @Slot()
    def openAboutFolder(self) -> None:
        folder = str(self._window._look_path().parent)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def ask_sign_out(self, question: str, done: Any) -> None:
        """The Sign out question. `done()` runs when the student answers Sign out; Cancel and Esc leave
        everything as it was."""
        self._more = False
        self._sign_out_done = done
        self._ask = {**SIGN_OUT, "body": question}
        self._publish()

    def open_update(self, update: dict, current: str, install: Any, finished: Any) -> None:
        """A newer FlexWeek exists. `install()` starts the download; `finished(skip)` runs when the sheet
        closes, with whether the student chose Skip this version. Another sheet that is open keeps the
        screen: the update waits for it."""
        self._update_waiting = (update, current, install, finished)
        self._show_waiting_update()

    def _show_waiting_update(self) -> None:
        if self._update_waiting is None or self.active:
            return
        update, current, install, finished = self._update_waiting
        self._update_waiting = None
        self._update = update
        self._update_current = current
        self._update_install = install
        self._update_finished = finished
        self._update_skip = False
        self._update_state = {"status": "", "problem": False, "busy": False, "progress": -1}
        self._open("update")

    def _finish_update(self) -> Any:
        """The sheet closes: what to tell the window once the sheet is gone."""
        finished, skip = self._update_finished, self._update_skip
        self._update = None
        self._update_install = None
        self._update_finished = None
        self._update_skip = False
        if finished is None:
            return None
        return lambda: finished(skip)

    @Slot()
    def updateInstall(self) -> None:
        if self._kind != "update" or self._update_state.get("busy"):
            return
        self._update_state = {"status": "Downloading…", "problem": False, "busy": True, "progress": 0.0}
        self._publish()
        if self._update_install is not None:
            self._update_install()

    @Slot()
    def updateSkip(self) -> None:
        if self._kind == "update":
            self._update_skip = True
            self._close()

    def update_progress(self, got: int, total: int) -> None:
        if self._kind != "update":
            return
        self._update_state = {**self._update_state, "progress": min(1.0, got / total) if total > 0 else -1}
        self._publish()

    def update_problem(self, why: str) -> None:
        if self._kind != "update":
            return
        self._update_state = {"status": why, "problem": True, "busy": False, "progress": -1}
        self._publish()

    def update_open(self) -> bool:
        return self._kind == "update"

    def update_done(self) -> None:
        """The download is in place: the sheet goes without the student pressing anything."""
        if self._kind == "update":
            self._close()

    # Account and Restore points ----------------------------------------------------------

    def pose_question(self, question: dict, handlers: dict[str, Any]) -> None:
        """A prompt from the window. Each answer runs its handler; Esc runs "dismiss" when there is one."""
        self._ask_then(question, handlers)

    def _ask_then(self, question: dict, handlers: dict[str, Any]) -> None:
        """A prompt whose answers run `handlers`; Cancel and Esc run none, unless "dismiss" is given."""
        self._more = False
        self._ask = dict(question)
        self._ask_handlers = handlers
        self._publish()

    @Slot()
    def openAccount(self) -> None:
        if self._session is None or self._session.account is None:
            return
        self._open("account")

    @Slot(str, str, str)
    def accountAct(self, action: str, password: str, new_password: str) -> None:
        """A button of the Account sheet. It closes, then does what the Widgets dialog did once it had
        closed. Delete stays open under its question, so Cancel finds the fields as they were."""
        if self._kind != "account":
            return
        acts = self._account_actions
        if action == "delete":
            acts.delete(password)
            return
        run = {
            "password": lambda: acts.change_password(password, new_password),
            "codes": lambda: acts.replace_codes(password),
            "export": lambda: acts.export_account(password),
            "import": acts.import_account,
            "week": acts.export_week,
            "day": acts.export_day,
            "import-week": acts.import_file,
        }.get(action)
        if run is None:
            return
        self._close()
        run()

    @Slot()
    def openRestore(self) -> None:
        session = self._session
        if session is None or session.account is None:
            return
        preview = session.restore_preview or {}
        self._restore_selected = str(preview.get("id") or "")
        self._restore_label = ""
        self._open("restore")

    @Slot(str)
    def selectRestore(self, point_id: str) -> None:
        if self._kind == "restore" and any(
            str(point.get("id")) == point_id for point in self._session.restore_points
        ):
            self._restore_selected = point_id
            self._manage_note = ""
            self._publish()

    @Slot(str)
    def setRestoreLabel(self, value: str) -> None:
        if self._kind == "restore":
            self._restore_label = value

    @Slot()
    def createRestore(self) -> None:
        if self._kind != "restore":
            return
        label = self._restore_label
        self._session.create_restore_point(label.strip())
        if label.strip():
            self._restore_label = ""
            self._publish()

    @Slot()
    def previewRestore(self) -> None:
        if self._kind != "restore":
            return
        if not self._restore_selected:
            self._manage_note = RESTORE_FIRST
            self._publish()
            return
        self._manage_note = ""
        self._session.preview_restore_point(self._restore_selected, self._publish)

    @Slot()
    def restoreSelected(self) -> None:
        """Restore asks first. Yes closes the sheet, then FlexWeek saves its own "Before restore" copy and
        goes back."""
        if self._kind != "restore":
            return
        chosen = self._restore_selected
        if not chosen:
            self._manage_note = RESTORE_FIRST
            self._publish()
            return
        self._ask_then(RESTORE_QUESTION, {"restore": lambda: self._restored(chosen)})

    def _restored(self, point_id: str) -> None:
        self._close()
        self._session.apply_restore_point(point_id)

    # Notice -----------------------------------------------------------------------------

    def _on_save_answered(self, point_id: str, doubled: list) -> None:
        """The store's answer to a save: the restore point it made, which gives the notice its Undo, and the
        weeks where the new weekly time doubles one made by hand."""
        words = self._restore_words
        if point_id and words and self._notice == words:
            self._notice_restore = point_id
            self._notice_undo = True
            self._restore_words = ""
            self.changed.emit()
        if doubled:
            self._doubled_waiting = [str(week) for week in doubled]
            self._show_doubled()

    def _show_doubled(self) -> None:
        """The doubled-weeks prompt, once no other question is up; it never replaces one."""
        weeks = self._doubled_waiting
        if weeks is None or self._ask:
            return
        self._doubled_waiting = None
        name = self._doubled_name or "This fixed time"
        self._ask = {
            "id": "doubled-weeks",
            "title": f"{name} is already in {'a later week' if len(weeks) == 1 else 'later weeks'}",
            "body": doubled_words(name, weeks, wall_clock.today()),
            "answers": [{"id": "ok", "label": "OK", "kind": "tonal"}],
        }
        self.changed.emit()

    def _say(self, text: str, *, undo: bool = False) -> None:
        self._notice = text
        self._notice_undo = undo
        self._notice_restore = ""
        self._restore_words = ""
        self._remaining_ms = NOTICE_MS
        if not text:
            self._timer.stop()
            self._paused = False
        else:
            if getattr(self, "_held", False):
                self._paused = True
                self._timer.stop()
            else:
                self._paused = False
                self._timer.start(NOTICE_MS)
        self.changed.emit()

    @Slot()
    def pauseNotice(self) -> None:
        self._held = True
        self._paused = True
        if self._timer.isActive():
            self._remaining_ms = max(0, self._timer.remainingTime())
            self._timer.stop()

    @Slot()
    def resumeNotice(self) -> None:
        self._held = False
        if self._paused:
            self._paused = False
            if self._notice:
                self._timer.start(max(1000, getattr(self, "_remaining_ms", NOTICE_MS)))

    @Slot()
    def dismissNotice(self) -> None:
        if self._notice:
            self._notice = ""
            self._notice_undo = False
            self._notice_restore = ""
            self._restore_words = ""
            self._timer.stop()
            self._paused = False
            self._held = False
            self.changed.emit()

    @Slot()
    def undoNotice(self) -> None:
        if self._notice_undo and self._session is not None:
            if self._notice_restore:
                self._session.undo_to_restore_point(self._notice_restore)
            else:
                self._session.undo()
        self.dismissNotice()

    # The form ---------------------------------------------------------------------------

    def refresh(self) -> None:
        """The session changed. A sheet that reads it, such as a late preview, shows what it has now."""
        if self._kind in ("late", "unfinished", "weekList", "routines", "account", "restore", "preview"):
            self._publish()

    def _publish(self) -> None:
        kind = self._kind
        if kind == "homework" and self._homework is not None:
            self._form = {**self._homework.form(), "canSave": self.canSave}
        elif kind == "block" and self._block is not None:
            self._form = {**self._block.form(), "canSave": self.canSave}
        elif kind == "late":
            self._form = self._late_form()
        elif kind == "unfinished":
            self._form = self._unfinished_form()
        elif kind == "weekList":
            self._form = self._week_list_form()
        elif kind == "preview" and self._preview is not None:
            self._form = self._preview.form()
        elif kind == "routines":
            self._form = self._routine_form()
        elif kind == "alarm" and self._alarm is not None:
            self._form = {**self._alarm.form(), "canSave": self.canSave}
        elif kind == "help":
            owner = self.parent()
            self._form = help_form(
                bool(getattr(owner, "shortcuts", True)), bool(getattr(owner, "letterKeys", False))
            )
        elif kind == "about":
            self._form = about_form(getattr(self._session, "storage_info", None))
        elif kind == "update" and self._update is not None:
            self._form = update_form(self._update, self._update_current, self._update_state)
        elif kind == "account":
            self._form = account_form(self._session.storage_info, self._session.recovery_remaining)
        elif kind == "restore":
            session = self._session
            self._form = restore_form(
                session.restore_points,
                session.restore_preview,
                session.storage_info,
                self._restore_selected,
                self._restore_label,
                self._manage_note,
            )
        else:
            self._form = {}
        # The moved-day note is said aloud when it appears or changes in a sheet that is already open. A
        # sheet that opens with it is read with the note, and one that clears it says nothing.
        note = str(self._form.get("movedNote") or self._form.get("whenMovedNote") or "")
        if self._noted is not None and note and note != self._noted:
            announce(self._window, note)
        self._noted = note
        self.changed.emit()
        self._show_waiting_update()
        self._show_doubled()
