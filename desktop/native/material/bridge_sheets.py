"""The Material sheets and the More menu: Add homework, Add fixed time, Running late,
Unfinished, Week as a list, Routines.

QML shows `form` and calls the slots. Every change goes through NativeSession, with the words
and checks the Widgets sheets use. This module does not touch HTTP, SQL, or the engine.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QAbstractButton

from backend.slots import DAY_END_MIN, SLOT_MIN, hhmm_to_minutes
from desktop.native.calendar import DAY_FULL, DAYS, FLEX_CATEGORIES, monday_of, sunday_due
from desktop.native.controller import twin_alert_words
from desktop.native.hours.geometry import next_slot
from desktop.native.material.sheet_block import BlockDraft
from desktop.native.material.sheet_homework import HomeworkDraft
from desktop.native.reuse import (
    LATE_MINUTES,
    late_from_start,
    late_locked_line,
    running_late_refusal,
)
from desktop.native.weekmodel import added_words, hhmm_text, length_label, range_label
from desktop.native.widgets import LATE_WAIT, _late_move, _late_summary

NOTHING_UNFINISHED = "None left"
NOTICE_MS = 10000
WAIT_SAVE = "Saving your last change… Save will work in a moment."
WAIT_DELETE = "Saving your last change… Delete will work in a moment."
DISCARD = {
    "id": "discard",
    "title": "Discard your changes?",
    "body": "Your changes will be lost.",
    "answers": [
        {"id": "keep", "label": "Keep editing", "kind": "text"},
        {"id": "discard", "label": "Discard", "kind": "tonal"},
    ],
}
# The More menu, in one place. A row names the Widgets button it presses, when it has one.
MORE_ROWS = (
    ("heading", "Planning"),
    ("runningLate", "Running late", "schedule", "runningLate"),
    ("unfinishedOpen", "Unfinished", "event_busy", ""),
    ("weekListRow", "Week as a list", "list", ""),
    ("routinesButton", "Routines", "repeat", ""),
    ("quickFocusAction", "Quick focus", "timer", "quickFocusAction"),
    ("replanAll", "Replan all my homework", "autorenew", "replanAll"),
    ("heading", "Help and info"),
    ("helpButton", "Help", "help", "helpButton"),
    ("aboutButton", "About FlexWeek", "info", "aboutButton"),
    ("heading", "Account"),
    ("signOut", "Sign out", "logout", "signOut"),
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
        # Notes that must be answered, waiting for the prompt that is up to be.
        self._queued_asks: list[dict] = []
        self._more = False
        self._drag_range_active = False
        self._notice = ""
        self._notice_undo = False
        self._homework: HomeworkDraft | None = None
        self._block: BlockDraft | None = None
        self._late_minutes = 30
        self._late_from: datetime | None = None
        self._late_from_start = ""
        self._pending_delete = ""
        self._late_running: dict | None = None
        self._late_error = ""
        self._late_waiting: tuple[str, str] | None = None
        self._routine_id = ""
        self._routine_days: list[int] = []
        self._routine_error = ""
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
            twins = getattr(session, "standing_twins", None)
            if twins is not None:
                twins.connect(self._on_twins)
            busy = getattr(session, "busy_changed", None)
            if busy is not None:
                busy.connect(self._on_busy)

    def _on_twins(self, title: str, week_starts: list) -> None:
        """A new weekly fixed time shows twice in weeks the student copied it into by hand: a prompt with
        one OK, which stays until answered. Over a prompt that is already up it waits, so it never
        replaces a question, and over a sheet it leaves the typing as it is."""
        owns = getattr(self._window, "_material_owns", None)
        if owns is not None and not owns():
            return
        today = self._session.today_iso()
        heading, words = twin_alert_words(title, week_starts, int(today[:4]))
        ask = {
            "id": "twin-weeks",
            "title": heading,
            "body": words,
            "answers": [{"id": "ok", "label": "OK", "kind": "filled"}],
        }
        if self._ask:
            self._queued_asks.append(ask)
            return
        self._ask = ask
        self._publish()

    def _next_queued_ask(self) -> None:
        if not self._ask and self._queued_asks:
            self._ask = self._queued_asks.pop(0)
            self._publish()

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

    def _drop_ask(self) -> None:
        """A sheet opening or closing takes its own question with it, never the note that has to be
        answered."""
        if self._ask.get("id") != "twin-weeks":
            self._ask = {}

    def _open(self, kind: str) -> None:
        self._kind = kind
        self._more = False
        self._drop_ask()
        self._publish()

    def _close(self) -> None:
        late = self._kind == "late"
        self._kind = ""
        self._drop_ask()
        self._drag_range_active = False
        self._homework = None
        self._block = None
        session = self._session
        if late and session is not None and session.late_preview is not None:
            session.late_preview = None
            session._say("")
        self._publish()

    @Slot()
    def openHomework(self) -> None:
        session = self._session
        if session is None or session.account is None:
            return
        category = session.armed_category
        if category not in FLEX_CATEGORIES:
            category = "assignments"
        self._homework = HomeworkDraft(session, category=category)
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
        self._block = BlockDraft(
            session, day=day, start=start, category=None if category in FLEX_CATEGORIES else category
        )
        self._open("block")

    @Slot(int, int, int)
    def openBlockAt(self, day: int, start_min: int, end_min: int) -> None:
        """Add fixed time for a time picked on the grid: that day, that start, that length."""
        session = self._session
        if session is None or session.account is None:
            return
        start_min, end_min = sorted((start_min, end_min))
        if end_min - start_min < 15:
            return
        category = session.armed_category
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
        if monday_of(now.date().isoformat()) != session.week_start:
            return 0, "16:00"
        ahead, slot = next_slot(now.hour * 60 + now.minute)
        if now.weekday() + ahead > 6:
            return 0, "16:00"
        return now.weekday() + ahead, f"{slot // 60:02d}:{slot % 60:02d}"

    @Slot()
    def closeSheet(self) -> None:
        """Esc, Cancel and a tap on the scrim. A sheet with typed work asks before dropping it."""
        if self._drag_range_active:
            self._drag_range_active = False
            self.dragRangeCanceled.emit()
            self.changed.emit()
            return
        if self._ask:
            self._ask = {}
            self._publish()
            self._next_queued_ask()
            return
        draft = self._homework if self._kind == "homework" else self._block if self._kind == "block" else None
        if draft is not None and draft.dirty():
            self._ask = dict(DISCARD)
            self._publish()
            return
        self._close()

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

    def _save_block(self, every_week: bool | None = None) -> None:
        """`every_week` is the answer to the which-weeks question: None while it has not been asked."""
        draft, session = self._block, self._session
        if draft is None or session is None:
            return
        if self._hold_for_save():
            return
        made = draft.candidate()
        if made is None:
            self._publish()
            return
        if every_week is None and session.edit_asks_which_weeks(
            made, scope=draft.scope, weekly=draft.weekly_arg(), until=draft.until
        ):
            self._ask = draft.edit_question()
            self._publish()
            return
        before = {item["id"] for item in session.blocks}
        session.add_block(
            made,
            scope=draft.scope,
            day=draft.occurrence_day,
            weekly=draft.weekly_arg(),
            until=draft.until,
            every_week=bool(every_week),
        )
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
        # Later weeks change with no Undo (as for School's hours), so the notice offers none.
        self._say(
            f"Saved {made['title']}" if existed else added_words(made),
            undo=not (draft.repeat_changed() or every_week),
        )

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
                    {"id": "delete", "label": "Delete", "kind": "filled"},
                ],
            }
        elif self._block is not None and self._block.existing and session is not None:
            self._ask = self._block.delete_question()
        else:
            return
        self._publish()

    @Slot(str)
    def answer(self, choice: str) -> None:
        """A button on the prompt that is up."""
        self._answer(choice)
        self._next_queued_ask()

    def _answer(self, choice: str) -> None:
        asked = self._ask.get("id", "") if self._ask else ""
        self._ask = {}
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
        elif asked == "edit-block" and choice in ("week", "every"):
            self._save_block(every_week=choice == "every")
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
        session.delete_block(block["id"], scope=scope, day=day, every_week=every_week)
        session.save()
        self._close()
        if every_week:
            self._say(f"Deleted {title} from this week and every week after.")
        elif scope == "occurrence" and day is not None:
            self._say(f"Deleted {title} on {DAY_FULL[day]} from this week.", undo=True)
        else:
            self._say(f"Deleted {title} from this week.", undo=True)

    # Running late -----------------------------------------------------------------------

    def _late_other_week(self) -> bool:
        session = self._session
        now = datetime.fromtimestamp(session.now_ms() / 1000)
        return monday_of(now.date().isoformat()) != session.week_start

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
                and now.weekday() in (block.get("days") or [])
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
                changes.append(_late_move(move, block, titles.get(move["block_id"], move["block_id"])))
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

    def _on_saved(self, stored: bool, _said: str) -> None:
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
                }
            )
        return {
            "kind": "unfinished",
            "heading": "Unfinished",
            "intro": "Overdue and left from last week, then homework that still needs a time.",
            "rows": rows,
            "empty": "Nothing is left over." if not rows else "",
        }

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
                {"id": "delete", "label": "Delete", "kind": "filled"},
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
        for day in range(7):
            stamp = DAY_FULL[day]
            if monday:
                moment = date.fromordinal(monday.toordinal() + day)
                stamp = f"{DAY_FULL[day]} {moment.day} {moment.strftime('%b')}"
            rows.append({"type": "heading", "text": stamp})
            items = sorted(week.on_day(day), key=lambda item: (item.start, item.end, item.title))
            if not items:
                rows.append({"type": "none", "text": "Nothing planned"})
            for occurrence in items:
                detail = range_label(int(occurrence.start), int(occurrence.end))
                if not occurrence.work:
                    detail += " · Fixed time"
                rows.append(
                    {
                        "type": "item",
                        "title": occurrence.title,
                        "detail": detail,
                        "blockId": occurrence.block_id,
                        "day": day,
                        "words": f"{DAY_FULL[day]}: {occurrence.title}, {detail}",
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

    def _routine_form(self) -> dict:
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
        days = [
            {
                "value": index,
                "label": DAYS[index],
                "date": date.fromordinal(monday.toordinal() + index).day if monday else 0,
                "on": index in self._routine_days,
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
            "error": self._routine_error,
        }

    @Slot()
    def openRoutines(self) -> None:
        if self._session is None or self._session.account is None:
            return
        self._routine_id = ""
        self._routine_days = []
        self._routine_error = ""
        self._open("routines")

    @Slot(str)
    def selectRoutine(self, routine_id: str) -> None:
        routine = self._session.routines.get(routine_id)
        if routine is None:
            return
        self._routine_id = routine_id
        days: set[int] = set()
        for block in routine.get("blocks") or []:
            days.update(int(day) for day in block.get("days") or [])
        self._routine_days = sorted(days)
        self._routine_error = ""
        self._publish()

    @Slot(int)
    def toggleRoutineDay(self, day: int) -> None:
        days = set(self._routine_days)
        days.symmetric_difference_update({day})
        self._routine_days = sorted(days)
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
            self._close()
            self._say(f"Added the {name} routine.", undo=True)
            return
        self._publish()

    # The More menu ----------------------------------------------------------------------

    def _button(self, name: str) -> QAbstractButton | None:
        return self._window.findChild(QAbstractButton, name)

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
            name, label, icon, button_name = row
            button = self._button(button_name) if button_name else None
            enabled = True
            detail = ""
            if button is not None:
                enabled = button.isEnabled()
                label = button.text() or label
            if name == "runningLate":
                enabled = enabled and not session.busy and not self._late_other_week()
            elif name == "unfinishedOpen":
                enabled = bool(left)
                detail = f"{left} left" if left else NOTHING_UNFINISHED
            elif name in ("weekListRow", "routinesButton"):
                enabled = session.account is not None
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
        self._drop_ask()
        self._more = True
        self._publish()

    @Slot()
    def closeMore(self) -> None:
        if self._more:
            self._more = False
            self._publish()

    @Slot(str)
    def moreAction(self, name: str) -> None:
        """A row of More. Each opens a sheet, or presses the button the Widgets menu presses."""
        entry = next((item for item in self._more_entries() if item["id"] == name), None)
        if entry is None or not entry["enabled"]:
            return
        self._more = False
        opening = {
            "runningLate": self.openLate,
            "unfinishedOpen": self.openUnfinished,
            "weekListRow": self.openWeekList,
            "routinesButton": self.openRoutines,
        }.get(name)
        if opening is not None:
            opening()
            return
        row = next(item for item in MORE_ROWS if item[0] == name)
        button = self._button(row[3])
        self._publish()
        if button is not None:
            button.click()

    # Notice -----------------------------------------------------------------------------

    def _say(self, text: str, *, undo: bool = False) -> None:
        self._notice = text
        self._notice_undo = undo
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
            self._timer.stop()
            self._paused = False
            self._held = False
            self.changed.emit()

    @Slot()
    def undoNotice(self) -> None:
        if self._notice_undo and self._session is not None:
            self._session.undo()
        self.dismissNotice()

    # The form ---------------------------------------------------------------------------

    def refresh(self) -> None:
        """The session changed. A sheet that reads it, such as a late preview, shows what it has now."""
        if self._kind in ("late", "unfinished", "weekList", "routines"):
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
        elif kind == "routines":
            self._form = self._routine_form()
        else:
            self._form = {}
        self.changed.emit()
