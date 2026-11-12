"""Material sign-in, recovery, and first-run setup.

QML calls these slots. The slots call NativeSession (login, register, resume,
recover, logout, keep_setup, flush_setup) and the window methods that already
turn a setup answer into those calls. This module does not touch HTTP or SQL.

The widgets pages keep their own controls. This bridge is shown only while the
saved surface is Material.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QApplication

from backend import clock as wall_clock
from backend.models import valid_spotify_url
from backend.slots import hhmm_to_minutes, minutes_to_hhmm
from desktop.native.calendar import (
    DAY_FULL,
    DAYS,
    SETUP_SCHOOL_ID,
    is_setup_block,
    new_activity_id,
)
from desktop.native.client import (
    SESSION_ENDED,
    SIGN_IN_AGAIN,
    SIGN_IN_WHY,
    SIGN_IN_WHY_LINK,
    TOO_MANY_TRIES,
    TYPE_RECOVERY_CODE,
    USERNAME_ERROR,
    USERNAME_HINT,
    short_password_needed,
    sign_in_problem,
    sign_up_problem,
)
from desktop.native.fields import QUICK_LENGTHS, read_clock, save_week_starts_on, week_starts_on
from desktop.native.hours.geometry import drag_step
from desktop.native.layouts.registry import (
    DESIGN_LOOKS,
    LAYOUTS,
    layouts_for,
    options_for,
    sanitize_layout,
)
from desktop.native.look import (
    KNOB_VALUE_LABELS,
    LOOK_KNOBS,
    effective_look,
    parse_look_menu_token,
    sanitize_look,
)
from desktop.native.remind import reminder_lead_min
from desktop.native.settings import (
    ALARM_TONE_LABELS,
    DRAG_STEP_CHOICES,
    DRAG_STEP_QUESTION,
    PLANNING_STYLES,
    SPORT_FALLBACK,
    SPOTIFY_TONE_NOTE,
)
from desktop.native.setup import (
    COLOURS,
    DONE,
    FINISH_LABEL,
    FIRST,
    HOMEWORK,
    LOOK,
    LOOK_STEPS,
    MAX_ACTIVITIES,
    MAX_FIRST_HOMEWORK,
    NEXT_LABEL,
    NOTES,
    OWN_LOOK_LABEL,
    RAIL,
    RAIL_STATES,
    REMINDERS,
    SKIP_ALL_LABEL,
    SKIP_STEP_LABEL,
    STYLE,
    STYLES,
    TITLES,
    WEEK,
    Style,
    activity_category_for,
    days_label,
    next_school_day,
    span_label,
    style_layout,
    style_look,
)
from desktop.native.tones import FALLBACK, RECIPES
from desktop.native.weekmodel import end_after_start_words, hhmm_text, set_clock_24h
from desktop.native.widgets import CUTOFFS, DUE_BY_HINT
from desktop.native.window import (
    CREATE_HEADING,
    CREATE_NOTE,
    PASSWORD_LENGTH_HINT,
    RECOVERY_COPY,
    RECOVERY_FILE,
    RECOVERY_KEEP,
    RECOVERY_SAID_MS,
    RECOVERY_SAVE,
    RECOVERY_WAIT,
    RESET_HEADING,
    RESET_NOTE,
    SIGN_IN_HEADING,
)
from desktop.native.work_windows import MAX_WORK_WINDOWS, PRESETS, PRESETS_NOTE

log = logging.getLogger("flexweek.material")

# The four shipped styles, plus Material 3. The widgets list is unchanged.
# Material 3 uses the classic light pack, so Next keeps a light week and the
# saved surface stays Material.
MATERIAL_STYLE = Style(
    "material",
    "Material 3",
    "The Material week",
    "classic",
    "pack:light-frost",
    "light-frost",
)
MATERIAL_STYLES = (MATERIAL_STYLE, *STYLES)
RECOVERY_HEADING = "Save these recovery codes"
RECOVERY_NOTE = (
    "They are the only way to reset your password. FlexWeek can't email you. "
    "Copy them somewhere you will still have if this computer is gone."
)
RECOVERY_ACK = "I have saved these codes"
RECOVERY_CONTINUE = "Continue to my week"
WHY_TITLE = "Why it doesn't say which"
SPOTIFY_PLACEHOLDER = "Paste a link from Spotify: open.spotify.com/track/… or /playlist/…"
SPOTIFY_PROBLEM = "Paste a link that starts with https://open.spotify.com, or pick another sound."
AUTH_PHASES = ("sign-in", "create", "reset")
PHASES = (*AUTH_PHASES, "recovery", "setup", "app")


def _minutes(start: str, end: str) -> int:
    try:
        return hhmm_to_minutes(end) - hhmm_to_minutes(start)
    except (TypeError, ValueError):
        return 0


def _clock(text: str, *, end: bool = False) -> str | None:
    """HH:MM for a time the student typed ("4 pm", "16:00", "8:30"), or None when it is not a time."""
    minute = read_clock(str(text), end=end, whole=False)
    if minute is None:
        return None
    return minutes_to_hhmm(minute) if minute < 1440 else "23:59"


def _blank_activity() -> dict[str, Any]:
    return {
        # Kept for the life of the row, so removing another activity never renumbers this one.
        "id": new_activity_id(),
        "title": "",
        "days": [],
        "start": "15:30",
        "end": "17:00",
        "category": "extra",
        "touched": False,
    }


def _blank_homework(due: str) -> dict[str, Any]:
    return {
        "title": "",
        "minutes": 60,
        "due": due,
        "due_touched": False,
        "timed": False,
        "time": "09:00",
    }


class Table(QAbstractListModel):
    """Rows a repeater keeps its items for: a row that changes is updated in place, not rebuilt.

    A plain list would rebuild every item on each change, and a text field being typed in would lose
    the keyboard on its first letter. Each item reads the whole row as `row`.
    """

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._rows: list[Any] = []

    def sync(self, rows: list[Any]) -> None:
        rows = list(rows)
        old, new = self._rows, rows
        common = min(len(old), len(new))
        changed = [index for index in range(common) if old[index] != new[index]]
        if len(new) > len(old):
            self.beginInsertRows(QModelIndex(), len(old), len(new) - 1)
            self._rows = new
            self.endInsertRows()
        elif len(new) < len(old):
            self.beginRemoveRows(QModelIndex(), len(new), len(old) - 1)
            self._rows = new
            self.endRemoveRows()
        else:
            self._rows = new
        for index in changed:
            at = self.index(index)
            self.dataChanged.emit(at, at)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if role != Qt.ItemDataRole.UserRole + 1 or not index.isValid() or index.row() >= len(self._rows):
            return None
        return self._rows[index.row()]

    def roleNames(self) -> dict[int, QByteArray]:
        return {Qt.ItemDataRole.UserRole + 1: QByteArray(b"row")}


# model name -> the list property it follows
TABLES = {
    "stylesModel": "styles",
    "mainsModel": "mains",
    "knobsModel": "knobRows",
    "dayLayoutsModel": "dayLayouts",
    "activitiesModel": "activities",
    "workModel": "workWindows",
    "homeworkModel": "homeworkRows",
    "summaryModel": "summaryRows",
    "railModel": "rail",
}


class AccountBridge(QObject):
    """The account and setup screens. `phase` is app once the week is the page."""

    changed = Signal()

    def __init__(self, window: QObject) -> None:
        super().__init__(window)
        self._window = window
        session = window.session  # type: ignore[attr-defined]
        self._phase = "app" if session.account is not None else "sign-in"
        self._username = ""
        self._password = ""
        self._keep = bool(session.keep_signed_in)
        self._code = ""
        self._new_password = ""
        self._problems = {"username": "", "password": "", "recovery": "", "new": ""}
        self._status = ""
        self._why_open = False
        self._codes: list[str] = []
        self._ack = False
        self._copy_label = RECOVERY_COPY
        self._save_label = RECOVERY_SAVE
        self._recovery_status = ""
        self._said = QTimer(self)
        self._said.setSingleShot(True)
        self._said.setInterval(RECOVERY_SAID_MS)
        self._said.timeout.connect(self._reset_recovery_labels)
        self._state: Any = None
        self._step = STYLE
        self._furthest = STYLE
        self._own_look = False
        self._style_key = "material"
        self._style_tokens: dict[str, str] = {}
        self._pack = "system"
        self._look = sanitize_look(None)
        self._layout = sanitize_layout(None)
        self._entered = (self._pack, deepcopy(self._look), deepcopy(self._layout))
        self._clock_24h = False
        self._week_start = "monday"
        self._school_days = [0, 1, 2, 3, 4]
        self._school_start = "08:00"
        self._school_end = "14:30"
        self._activities: list[dict[str, Any]] = [_blank_activity()]
        self._week_opened: tuple = ()
        self._cutoff = ""
        self._saved_cutoff = ""
        self._planning = "suggest"
        self._drag = 5
        self._windows: list[dict[str, Any]] = []
        self._reminders = True
        self._lead = reminder_lead_min(None)
        self._tone = FALLBACK
        self._spotify = ""
        self._homework: list[dict[str, Any]] = [_blank_homework(next_school_day([0, 1, 2, 3, 4]))]
        self._made: dict[str, str] = {}
        self._problem_text = ""
        self._test_result = ""
        self._skip_open = False
        self._skip_body = ""
        self._skip_confirm = ""
        self._skip_dismiss = ""
        self._skip_dismiss_keeps = False
        self._summary: list[dict[str, str]] = []
        # The surface the student picked on the style page, written when setup ends.
        self._surface_pick: str | None = None
        self._tables = {name: Table(self) for name in TABLES}
        # Before QML's own handlers, so a binding that reads a table sees the new rows.
        self.changed.connect(self._sync_tables)
        self._sync_tables()
        session.status.connect(self._on_status)
        session.busy_changed.connect(self._on_busy)

    @property
    def codes(self) -> list[str]:
        """The recovery codes on screen, for the window to hand to the Widgets page if Material fails."""
        return list(self._codes)

    @property
    def setup_step(self) -> int:
        return self._step

    def apply_surface(self) -> None:
        """Make the style picked in setup the window's surface. Material stays unless a standard style won."""
        pick = self._surface_pick
        self._surface_pick = None
        window = self._window
        if pick is None or pick == window._surface:  # type: ignore[attr-defined]
            return
        window._surface = pick  # type: ignore[attr-defined]
        window._save_look()  # type: ignore[attr-defined]
        if pick == "widgets":
            window._week_keys(True)  # type: ignore[attr-defined]

    # Sign-in

    def show_sign_in(self, *, clear: bool = False) -> None:
        """The sign-in card. `clear` drops what the previous student typed."""
        if clear:
            self._username = ""
            self._password = ""
            self._code = ""
            self._new_password = ""
        self._phase = "sign-in"
        self._clear_problems()
        self._status = ""
        self._why_open = False
        self.changed.emit()

    @Slot()
    def showSignIn(self) -> None:  # noqa: N802 — QML slot
        self.show_sign_in()

    @Slot()
    def showCreate(self) -> None:  # noqa: N802 — QML slot
        self._phase = "create"
        self._clear_problems()
        self._status = ""
        self._why_open = False
        self.changed.emit()

    @Slot()
    def showReset(self) -> None:  # noqa: N802 — QML slot
        self._phase = "reset"
        self._clear_problems()
        self._status = ""
        self._why_open = False
        self.changed.emit()

    @Slot(str)
    def setUsername(self, value: str) -> None:  # noqa: N802 — QML slot
        self._username = value
        self._problems["username"] = ""
        self.changed.emit()

    @Slot(str)
    def setPassword(self, value: str) -> None:  # noqa: N802 — QML slot
        self._password = value
        self._problems["password"] = ""
        self._why_open = False
        self.changed.emit()

    @Slot(str)
    def setRecoveryCode(self, value: str) -> None:  # noqa: N802 — QML slot
        self._code = value
        self._problems["recovery"] = ""
        self.changed.emit()

    @Slot(str)
    def setNewPassword(self, value: str) -> None:  # noqa: N802 — QML slot
        self._new_password = value
        self._problems["new"] = ""
        self.changed.emit()

    @Slot(bool)
    def setKeepSignedIn(self, on: bool) -> None:  # noqa: N802 — QML slot
        self._keep = bool(on)
        self._window.session.keep_signed_in = self._keep  # type: ignore[attr-defined]
        self.changed.emit()

    @Slot()
    def submit(self) -> None:
        phase = self._phase
        name = self._username.strip()
        if phase == "sign-in":
            problem = sign_in_problem(name, self._password)
            action = self._window.session.login  # type: ignore[attr-defined]
            values: tuple = (name, self._password)
        elif phase == "create":
            problem = sign_up_problem(name, self._password)
            action = self._window.session.register  # type: ignore[attr-defined]
            values = (name, self._password)
        elif phase == "reset":
            problem = self._recovery_problem()
            action = self._window.session.recover  # type: ignore[attr-defined]
            values = (name, self._code.strip(), self._new_password)
        else:
            return
        if problem:
            self._show_problem(problem)
            return
        self._window.session.keep_signed_in = self._keep  # type: ignore[attr-defined]
        action(*values)

    @Slot()
    def explainWhy(self) -> None:  # noqa: N802 — QML slot
        if self.whyVisible:
            self._why_open = True
            self.changed.emit()

    @Slot()
    def dismissWhy(self) -> None:  # noqa: N802 — QML slot
        self._why_open = False
        self.changed.emit()

    def show_recovery(self, codes: list) -> None:
        self._codes = [str(code) for code in codes]
        self._ack = False
        self._copy_label = RECOVERY_COPY
        self._save_label = RECOVERY_SAVE
        self._recovery_status = ""
        self._phase = "recovery"
        self.changed.emit()

    @Slot(bool)
    def setRecoveryAck(self, on: bool) -> None:  # noqa: N802 — QML slot
        self._ack = bool(on)
        self.changed.emit()

    @Slot()
    def copyCodes(self) -> None:  # noqa: N802 — QML slot
        QApplication.clipboard().setText(self.recoveryCodes + "\n")
        self._copy_label = "Copied"
        self._said.start()
        self.changed.emit()

    @Slot()
    def saveCodes(self) -> None:  # noqa: N802 — QML slot
        path = self._window._choose_recovery_file()  # type: ignore[attr-defined]
        if not path:
            return
        try:
            Path(path).write_text(self.recoveryCodes + "\n")
        except OSError:
            self._recovery_status = "FlexWeek could not save the codes there. Try another folder."
            self.changed.emit()
            return
        self._recovery_status = ""
        self._save_label = "Saved"
        self._said.start()
        self.changed.emit()

    @Slot()
    def finishRecovery(self) -> None:  # noqa: N802 — QML slot
        if not self._ack:
            self._recovery_status = RECOVERY_WAIT
            self.changed.emit()
            return
        self._window._finish_recovery()  # type: ignore[attr-defined]

    def show_app(self) -> None:
        if self._phase == "app":
            return
        self._phase = "app"
        self._why_open = False
        self._skip_open = False
        self.changed.emit()

    # Setup

    def open_setup(self, state: Any, step: int) -> None:
        """Fill setup from this account's own state. A previous account's rows are not kept."""
        self._state = deepcopy(state)
        self._pack = str(state.pack)
        self._look = sanitize_look(state.look)
        self._layout = sanitize_layout(state.layout)
        self._entered = (self._pack, deepcopy(self._look), deepcopy(self._layout))
        self._own_look = step in (LOOK, COLOURS)
        self._style_tokens = {}
        self._load_fields()
        self._step = step if step in range(DONE + 1) else STYLE
        self._furthest = self._step
        self._problem_text = ""
        self._test_result = ""
        self._skip_open = False
        self._made = {}
        if self._step == STYLE and state.first_run:
            self._style_key = MATERIAL_STYLE.key
        else:
            matched = self._matching_style()
            self._style_key = matched or (MATERIAL_STYLE.key if state.first_run else "plain")
        self._phase = "setup"
        if self._step == STYLE:
            self._apply_style(self._style_key, preview=True)
        else:
            self._apply_clock()
        if self._step == DONE:
            self._summary = self._build_summary()
        self.changed.emit()

    @Slot(str)
    def chooseStyle(self, key: str) -> None:  # noqa: N802 — QML slot
        if self._style(key) is None:
            return
        self._apply_style(key, preview=True)
        self.changed.emit()

    @Slot()
    def chooseOwnLook(self) -> None:  # noqa: N802 — QML slot
        self._own_look = True
        self._surface_pick = "widgets"
        self._leave(LOOK, keep=False)

    @Slot(str)
    def chooseMain(self, layout_id: str) -> None:  # noqa: N802 — QML slot
        if layout_id not in DESIGN_LOOKS:
            return
        options = deepcopy(self._layout["options"])
        if "look" not in options.get(layout_id, {}):
            options[layout_id] = {**options.get(layout_id, {}), "look": DESIGN_LOOKS[layout_id][0][0]}
        self._layout = sanitize_layout({**self._layout, "main": layout_id, "options": options})
        self._preview()
        self.changed.emit()

    @Slot(str)
    def chooseColour(self, token: str) -> None:  # noqa: N802 — QML slot
        main = self._layout["main"]
        options = deepcopy(self._layout["options"])
        options[main] = {**options.get(main, {}), "look": token}
        parsed = parse_look_menu_token(token)
        if parsed is not None and parsed[0] == "pack":
            self._pack = parsed[1]
        self._layout = sanitize_layout({**self._layout, "options": options})
        self._preview()
        self.changed.emit()

    @Slot(str, str)
    def chooseKnob(self, knob: str, value: str) -> None:  # noqa: N802 — QML slot
        if knob not in {"text", "density", "font", "depth"} or value not in LOOK_KNOBS[knob]:
            return
        knobs = dict(sanitize_look(self._look)["knobs"])
        knobs[knob] = value
        if knob == "density" and self._layout["main"] == "timeline":
            options = deepcopy(self._layout["options"])
            options.setdefault("timeline", {})["density"] = value or "comfortable"
            self._layout = sanitize_layout({**self._layout, "options": options})
        self._look = sanitize_look({"preset": "default", "knobs": knobs})
        self._preview()
        self.changed.emit()

    @Slot(str)
    def chooseDay(self, layout_id: str) -> None:  # noqa: N802 — QML slot
        self._layout = sanitize_layout({**self._layout, "day": layout_id})
        self._preview()
        self.changed.emit()

    @Slot(int)
    def toggleSchoolDay(self, day: int) -> None:  # noqa: N802 — QML slot
        previous = next_school_day(self._school_days)
        days = set(self._school_days)
        if day in days:
            days.discard(day)
        elif 0 <= day <= 6:
            days.add(day)
        self._school_days = sorted(days)
        nxt = next_school_day(self._school_days)
        for row in self._homework:
            if not row["due_touched"] and row["due"] == previous:
                row["due"] = nxt
        self.changed.emit()

    @Slot(str)
    def setSchoolStart(self, value: str) -> None:  # noqa: N802 — QML slot
        self._school_start = _clock(value) or self._school_start
        self.changed.emit()

    @Slot(str)
    def setSchoolEnd(self, value: str) -> None:  # noqa: N802 — QML slot
        self._school_end = _clock(value, end=True) or self._school_end
        self.changed.emit()

    @Slot()
    def addActivity(self) -> None:  # noqa: N802 — QML slot
        if len(self._activities) >= MAX_ACTIVITIES:
            return
        self._activities.append(_blank_activity())
        self.changed.emit()

    @Slot(int)
    def removeActivity(self, index: int) -> None:  # noqa: N802 — QML slot
        if 0 <= index < len(self._activities):
            self._activities.pop(index)
            if not self._activities:
                self._activities.append(_blank_activity())
            self.changed.emit()

    @Slot(int, str)
    def setActivityTitle(self, index: int, value: str) -> None:  # noqa: N802 — QML slot
        row = self._row(self._activities, index)
        if row is None:
            return
        row["title"] = value
        if not row["touched"]:
            row["category"] = activity_category_for(value)
        self.changed.emit()

    @Slot(int, int)
    def toggleActivityDay(self, index: int, day: int) -> None:  # noqa: N802 — QML slot
        row = self._row(self._activities, index)
        if row is None or not 0 <= day <= 6:
            return
        days = set(row["days"])
        if day in days:
            days.discard(day)
        else:
            days.add(day)
        row["days"] = sorted(days)
        self.changed.emit()

    @Slot(int, str)
    def setActivityStart(self, index: int, value: str) -> None:  # noqa: N802 — QML slot
        row = self._row(self._activities, index)
        if row is not None:
            row["start"] = _clock(value) or row["start"]
            self.changed.emit()

    @Slot(int, str)
    def setActivityEnd(self, index: int, value: str) -> None:  # noqa: N802 — QML slot
        row = self._row(self._activities, index)
        if row is not None:
            row["end"] = _clock(value, end=True) or row["end"]
            self.changed.emit()

    @Slot(int, str)
    def setActivityCategory(self, index: int, value: str) -> None:  # noqa: N802 — QML slot
        row = self._row(self._activities, index)
        if row is None or value not in ("extra", "exercise"):
            return
        row["category"] = value
        row["touched"] = True
        self.changed.emit()

    @Slot(bool)
    def setClock24(self, on: bool) -> None:  # noqa: N802 — QML slot
        self._clock_24h = bool(on)
        self._apply_clock()
        self.changed.emit()

    @Slot(str)
    def setWeekStart(self, value: str) -> None:  # noqa: N802 — QML slot
        if value in ("monday", "sunday"):
            self._week_start = value
            self.changed.emit()

    @Slot(str)
    def setCutoff(self, value: str) -> None:  # noqa: N802 — QML slot
        self._cutoff = value if value in CUTOFFS or (value and value == self._saved_cutoff) else ""
        self.changed.emit()

    @Slot(str)
    def setPlanning(self, value: str) -> None:  # noqa: N802 — QML slot
        if value in {item[0] for item in PLANNING_STYLES}:
            self._planning = value
            self.changed.emit()

    @Slot(int)
    def setDragStep(self, minutes: int) -> None:  # noqa: N802 — QML slot
        self._drag = drag_step(minutes)
        self.changed.emit()

    @Slot(str)
    def addWorkPreset(self, name: str) -> None:  # noqa: N802 — QML slot
        for label, days, start, end in PRESETS:
            if label == name:
                self._add_window({"days": list(days), "start": start, "end": end})
                return

    @Slot()
    def addWorkCustom(self) -> None:
        self._add_window({"days": [0, 1, 2, 3, 4], "start": "16:00", "end": "18:00"})

    @Slot(int)
    def removeWorkWindow(self, index: int) -> None:  # noqa: N802 — QML slot
        if 0 <= index < len(self._windows):
            self._windows.pop(index)
            self.changed.emit()

    @Slot(int, str)
    def setWorkSubject(self, index: int, value: str) -> None:  # noqa: N802 — QML slot
        row = self._row(self._windows, index)
        if row is None:
            return
        text = value.strip()
        if text:
            row["subject"] = text
        else:
            row.pop("subject", None)
        self.changed.emit()

    @Slot(int, int)
    def toggleWorkDay(self, index: int, day: int) -> None:  # noqa: N802 — QML slot
        row = self._row(self._windows, index)
        if row is None or not 0 <= day <= 6:
            return
        days = set(row.get("days") or [])
        days.symmetric_difference_update({day})
        row["days"] = sorted(days)
        self.changed.emit()

    @Slot(int, str)
    def setWorkStart(self, index: int, value: str) -> None:  # noqa: N802 — QML slot
        row = self._row(self._windows, index)
        if row is not None:
            row["start"] = _clock(value) or row.get("start") or "16:00"
            self.changed.emit()

    @Slot(int, str)
    def setWorkEnd(self, index: int, value: str) -> None:  # noqa: N802 — QML slot
        row = self._row(self._windows, index)
        if row is not None:
            row["end"] = _clock(value, end=True) or row.get("end") or "18:00"
            self.changed.emit()

    @Slot(bool)
    def setReminders(self, on: bool) -> None:  # noqa: N802 — QML slot
        self._reminders = bool(on)
        self.changed.emit()

    @Slot(int)
    def setLead(self, minutes: int) -> None:  # noqa: N802 — QML slot
        self._lead = max(0, min(120, int(minutes)))
        self.changed.emit()

    @Slot(str)
    def setTone(self, tone: str) -> None:  # noqa: N802 — QML slot
        if tone in RECIPES or tone == "spotify":
            self._tone = tone
            self.changed.emit()

    @Slot(str)
    def setSpotify(self, value: str) -> None:  # noqa: N802 — QML slot
        self._spotify = value
        self.changed.emit()

    @Slot(str)
    def playTone(self, tone: str) -> None:  # noqa: N802 — QML slot
        if tone not in RECIPES:
            return
        volume = int((self._window.session.preferences or {}).get("alert_volume", 80))  # type: ignore[attr-defined]
        self._window._bell.once(tone, volume)  # type: ignore[attr-defined]

    @Slot()
    def sendTest(self) -> None:
        link = self._spotify_link()
        if self._tone == "spotify" and link is None:
            self._test_result = "Paste a Spotify link first."
            self.changed.emit()
            return
        window = self._window
        volume = int((window.session.preferences or {}).get("alert_volume", 80))  # type: ignore[attr-defined]
        opened = self._tone == "spotify" and bool(link) and bool(window._spotify.play(link))  # type: ignore[attr-defined]
        window._bell.once(FALLBACK if self._tone == "spotify" else self._tone, volume)  # type: ignore[attr-defined]
        if window._tray_icon is not None and window._tray_icon.supportsMessages():  # type: ignore[attr-defined]
            said = "Sent. It shows in the corner of your screen."
        else:
            said = "Sent. This computer shows no notifications, so reminders appear in FlexWeek instead."
        if opened:
            said += (
                " Alarms and block starts play your Spotify link in the Spotify app,"
                " which it has just been given."
            )
        self._test_result = said
        self.changed.emit()

    @Slot()
    def addHomeworkRow(self) -> None:  # noqa: N802 — QML slot
        if len(self._homework) >= MAX_FIRST_HOMEWORK:
            return
        self._homework.append(_blank_homework(next_school_day(self._school_days)))
        self.changed.emit()

    @Slot(int)
    def removeHomeworkRow(self, index: int) -> None:  # noqa: N802 — QML slot
        if not 0 <= index < len(self._homework):
            return
        self._homework.pop(index)
        if not self._homework:
            self._homework.append(_blank_homework(next_school_day(self._school_days)))
        self.changed.emit()

    @Slot(int, str)
    def setHomeworkTitle(self, index: int, value: str) -> None:  # noqa: N802 — QML slot
        row = self._row(self._homework, index)
        if row is not None:
            row["title"] = value
            self.changed.emit()

    @Slot(int, int)
    def setHomeworkMinutes(self, index: int, minutes: int) -> None:  # noqa: N802 — QML slot
        row = self._row(self._homework, index)
        if row is not None:
            row["minutes"] = max(15, min(600, int(minutes)))
            self.changed.emit()

    @Slot(int, str)
    def setHomeworkDue(self, index: int, value: str) -> None:  # noqa: N802 — QML slot
        row = self._row(self._homework, index)
        if row is not None:
            row["due"] = value
            row["due_touched"] = True
            self.changed.emit()

    @Slot(int, bool)
    def setHomeworkTimed(self, index: int, on: bool) -> None:  # noqa: N802 — QML slot
        row = self._row(self._homework, index)
        if row is not None:
            row["timed"] = bool(on)
            self.changed.emit()

    @Slot(int, str)
    def setHomeworkTime(self, index: int, value: str) -> None:  # noqa: N802 — QML slot
        row = self._row(self._homework, index)
        if row is not None:
            row["time"] = _clock(value) or row["time"]
            self.changed.emit()

    @Slot()
    def setupNext(self) -> None:  # noqa: N802 — QML slot
        if self._step == DONE:
            self._window._finish_setup()  # type: ignore[attr-defined]
            return
        self._leave(self._after(), keep=True)

    @Slot()
    def setupBack(self) -> None:  # noqa: N802 — QML slot
        if self._step != STYLE:
            self._leave(self._before(), keep=False)

    @Slot()
    def setupSkip(self) -> None:  # noqa: N802 — QML slot
        if self._step == DONE:
            return
        if self._step == WEEK:
            names = self._kept_on_week()
            if names:
                self._open_skip(names)
                return
        self._leave(self._after(), keep=False)

    @Slot()
    def setupSkipAll(self) -> None:  # noqa: N802 — QML slot
        if self._step in LOOK_STEPS:
            self._restore_entered()
            self._preview()
        elif self._step == WEEK:
            self._clock_24h = (self._state.preferences.get("clock_24h") is True) if self._state else False
            self._apply_clock()
        self._window._finish_setup()  # type: ignore[attr-defined]

    @Slot(int)
    def setupJump(self, step: int) -> None:  # noqa: N802 — QML slot
        if step == self._step:
            return
        if step > self._furthest and step != DONE:
            return
        if step == DONE and self._furthest < DONE:
            return
        self._leave(step, keep=step > self._step)

    @Slot(int, result=int)
    def stepFor(self, index: int) -> int:  # noqa: N802 — QML slot
        """The first step of the rail's `index`th entry."""
        return RAIL[index][1][0] if 0 <= index < len(RAIL) else STYLE

    @Slot(str)
    def answerSkip(self, choice: str) -> None:  # noqa: N802 — QML slot
        self._skip_open = False
        if choice == "skip":
            self._leave(self._after(), keep=False)
        elif choice == "keep":
            self._leave(self._after(), keep=True)
        else:
            self.changed.emit()

    # Properties

    @Property(str, notify=changed)
    def phase(self) -> str:
        return self._phase

    @Property(str, notify=changed)
    def heading(self) -> str:
        if self._phase == "recovery":
            return RECOVERY_HEADING
        if self._phase == "setup":
            return TITLES[self._step]
        return {
            "sign-in": SIGN_IN_HEADING,
            "create": CREATE_HEADING,
            "reset": RESET_HEADING,
        }.get(self._phase, "")

    @Property(str, notify=changed)
    def note(self) -> str:
        if self._phase == "recovery":
            return RECOVERY_NOTE
        if self._phase == "create":
            return CREATE_NOTE
        if self._phase == "reset":
            return RESET_NOTE
        if self._phase == "setup":
            return NOTES[self._step]
        return ""

    @Property(str, notify=changed)
    def username(self) -> str:
        return self._username

    @Property(str, notify=changed)
    def password(self) -> str:
        return self._password

    @Property(bool, notify=changed)
    def keepSignedIn(self) -> bool:  # noqa: N802 — QML name
        return self._keep

    @Property(str, notify=changed)
    def usernameHint(self) -> str:  # noqa: N802 — QML name
        return USERNAME_HINT if self._phase == "create" else ""

    @Property(str, notify=changed)
    def passwordHint(self) -> str:  # noqa: N802 — QML name
        return PASSWORD_LENGTH_HINT if self._phase == "create" else ""

    @Property(str, notify=changed)
    def usernameProblem(self) -> str:  # noqa: N802 — QML name
        return self._problems["username"]

    @Property(str, notify=changed)
    def passwordProblem(self) -> str:  # noqa: N802 — QML name
        return self._problems["password"]

    @Property(str, notify=changed)
    def recoveryProblem(self) -> str:  # noqa: N802 — QML name
        return self._problems["recovery"]

    @Property(str, notify=changed)
    def newPasswordProblem(self) -> str:  # noqa: N802 — QML name
        return self._problems["new"]

    @Property(str, notify=changed)
    def statusLine(self) -> str:  # noqa: N802 — QML name
        return self._status

    @Property(QObject, constant=True)
    def stylesModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["stylesModel"]

    @Property(QObject, constant=True)
    def mainsModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["mainsModel"]

    @Property(QObject, constant=True)
    def knobsModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["knobsModel"]

    @Property(QObject, constant=True)
    def dayLayoutsModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["dayLayoutsModel"]

    @Property(QObject, constant=True)
    def activitiesModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["activitiesModel"]

    @Property(QObject, constant=True)
    def workModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["workModel"]

    @Property(QObject, constant=True)
    def homeworkModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["homeworkModel"]

    @Property(QObject, constant=True)
    def summaryModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["summaryModel"]

    @Property(QObject, constant=True)
    def railModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["railModel"]

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return bool(self._window.session.busy)  # type: ignore[attr-defined]

    @Property(bool, notify=changed)
    def whyVisible(self) -> bool:  # noqa: N802 — QML name
        return self._problems["password"].startswith("Wrong username or password")

    @Property(bool, notify=changed)
    def whyOpen(self) -> bool:  # noqa: N802 — QML name
        return self._why_open

    @Property(str, constant=True)
    def whyLink(self) -> str:  # noqa: N802 — QML name
        return SIGN_IN_WHY_LINK

    @Property(str, constant=True)
    def whyTitle(self) -> str:  # noqa: N802 — QML name
        return WHY_TITLE

    @Property(str, constant=True)
    def whyBody(self) -> str:  # noqa: N802 — QML name
        return SIGN_IN_WHY

    @Property(str, notify=changed)
    def recoveryCode(self) -> str:  # noqa: N802 — QML name
        return self._code

    @Property(str, notify=changed)
    def newPassword(self) -> str:  # noqa: N802 — QML name
        return self._new_password

    @Property(str, notify=changed)
    def recoveryCodes(self) -> str:  # noqa: N802 — QML name
        return "\n".join(self._codes)

    @Property(bool, notify=changed)
    def recoveryAck(self) -> bool:  # noqa: N802 — QML name
        return self._ack

    @Property(bool, notify=changed)
    def recoveryReady(self) -> bool:  # noqa: N802 — QML name
        return self._ack and not self._window.session.busy  # type: ignore[attr-defined]

    @Property(str, notify=changed)
    def copyLabel(self) -> str:  # noqa: N802 — QML name
        return self._copy_label

    @Property(str, notify=changed)
    def saveLabel(self) -> str:  # noqa: N802 — QML name
        return self._save_label

    @Property(str, notify=changed)
    def recoveryStatus(self) -> str:  # noqa: N802 — QML name
        return self._recovery_status

    @Property(str, constant=True)
    def recoveryAckLabel(self) -> str:  # noqa: N802 — QML name
        return RECOVERY_ACK

    @Property(str, constant=True)
    def recoveryContinueLabel(self) -> str:  # noqa: N802 — QML name
        return RECOVERY_CONTINUE

    @Property(str, constant=True)
    def recoveryWait(self) -> str:  # noqa: N802 — QML name
        return RECOVERY_WAIT

    @Property(str, constant=True)
    def recoveryKeep(self) -> str:  # noqa: N802 — QML name
        return RECOVERY_KEEP

    @Property(int, notify=changed)
    def setupStep(self) -> int:  # noqa: N802 — QML name
        return self._step

    @Property(str, notify=changed)
    def nextLabel(self) -> str:  # noqa: N802 — QML name
        return FINISH_LABEL if self._step == DONE else NEXT_LABEL

    @Property(bool, notify=changed)
    def backVisible(self) -> bool:  # noqa: N802 — QML name
        return self._phase == "setup" and self._step != STYLE

    @Property(bool, notify=changed)
    def skipVisible(self) -> bool:  # noqa: N802 — QML name
        return self._phase == "setup" and self._step != DONE

    @Property(str, constant=True)
    def skipLabel(self) -> str:  # noqa: N802 — QML name
        return SKIP_STEP_LABEL

    @Property(str, constant=True)
    def skipAllLabel(self) -> str:  # noqa: N802 — QML name
        return SKIP_ALL_LABEL

    @Property(str, constant=True)
    def backLabel(self) -> str:  # noqa: N802 — QML name
        return "Back"

    @Property(str, constant=True)
    def ownLookLabel(self) -> str:  # noqa: N802 — QML name
        return OWN_LOOK_LABEL

    @Property(str, notify=changed)
    def setupProblem(self) -> str:  # noqa: N802 — QML name
        return self._problem_text

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def rail(self) -> list:
        rows = []
        for index, (name, steps) in enumerate(RAIL):
            current = self._step in steps
            done = max(steps) < self._step or (self._furthest >= DONE and steps[0] != DONE)
            state = "current" if current else "finished" if done else "pending"
            where = RAIL_STATES[{"current": "current", "finished": "finished", "pending": "pending"}[state]]
            rows.append(
                {
                    "name": name,
                    "step": steps[0],
                    "state": state,
                    "accessName": f"Step {index + 1}: {name}" + (f", {where.lower()}" if where else ""),
                }
            )
        return rows

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def styles(self) -> list:
        return [
            {
                "key": style.key,
                "name": style.name,
                "note": style.note,
                "selected": style.key == self._style_key and not self._own_look,
            }
            for style in MATERIAL_STYLES
        ]

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def mains(self) -> list:
        return [
            {
                "id": spec.id,
                "label": spec.label,
                "note": spec.summary,
                "selected": spec.id == self._layout["main"],
            }
            for spec in layouts_for("plan")
        ]

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def colours(self) -> list:
        main = self._layout["main"]
        current = options_for(self._layout, main).get("look")
        rows = [
            {"value": value, "label": label, "selected": value == current}
            for value, label in (*DESIGN_LOOKS[main], ("your", "Your look"))
        ]
        return rows

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def knobRows(self) -> list:  # noqa: N802 — QML name
        knobs = effective_look(self._look)
        labels = (("text", "Text size"), ("density", "Spacing"), ("font", "Font"), ("depth", "Shadows"))
        rows = []
        for key, label in labels:
            rows.append(
                {
                    "key": key,
                    "label": label,
                    "choices": [
                        {
                            "value": value,
                            "label": KNOB_VALUE_LABELS.get(value, value.title()),
                            "selected": knobs.get(key) == value,
                        }
                        for value in LOOK_KNOBS[key]
                    ],
                }
            )
        return rows

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def dayLayouts(self) -> list:  # noqa: N802 — QML name
        return [
            {
                "id": spec.id,
                "label": spec.label,
                "note": spec.summary,
                "selected": spec.id == self._layout["day"],
            }
            for spec in layouts_for("day")
        ]

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def schoolDays(self) -> list:  # noqa: N802 — QML name
        return list(self._school_days)

    @Property(str, notify=changed)
    def schoolStart(self) -> str:  # noqa: N802 — QML name
        return hhmm_text(self._school_start)

    @Property(str, notify=changed)
    def schoolEnd(self) -> str:  # noqa: N802 — QML name
        return hhmm_text(self._school_end)

    @Property(bool, notify=changed)
    def schoolHint(self) -> bool:  # noqa: N802 — QML name
        return not self._school_days

    @Property(str, notify=changed)
    def thisWeek(self) -> str:  # noqa: N802 — QML name
        """The page shows the usual week; "This week: no School on Wednesday." says what the open week
        does differently."""
        return (self._state.this_week if self._state is not None else None) or ""

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def activities(self) -> list:
        return [
            {
                "title": row["title"],
                "days": list(row["days"]),
                "start": hhmm_text(row["start"]),
                "end": hhmm_text(row["end"]),
                "category": row["category"],
            }
            for row in self._activities
        ]

    @Property(bool, notify=changed)
    def canAddActivity(self) -> bool:  # noqa: N802 — QML name
        return len(self._activities) < MAX_ACTIVITIES

    @Property(bool, notify=changed)
    def clock24(self) -> bool:
        return self._clock_24h

    @Property(str, notify=changed)
    def weekStart(self) -> str:  # noqa: N802 — QML name
        return self._week_start

    @Property(str, notify=changed)
    def cutoff(self) -> str:
        return self._cutoff

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def cutoffChoices(self) -> list:  # noqa: N802 — QML name
        # A time saved before the list was shortened stays on it, as in Widgets' fill_cutoff.
        kept = [self._saved_cutoff] if self._saved_cutoff else []
        times = ({"value": item, "label": hhmm_text(item)} for item in sorted({*CUTOFFS, *kept}))
        return [{"value": "", "label": "No limit"}, *times]

    @Property("QVariantList", constant=True)  # type: ignore[arg-type]
    def dayNames(self) -> list:  # noqa: N802 — QML name
        return [{"short": short, "full": full} for short, full in zip(DAYS, DAY_FULL, strict=True)]

    @Property(str, notify=changed)
    def planning(self) -> str:
        return self._planning

    @Property(int, notify=changed)
    def dragStep(self) -> int:  # noqa: N802 — QML name
        return self._drag

    @Property("QVariantList", constant=True)  # type: ignore[arg-type]
    def planningChoices(self) -> list:  # noqa: N802 — QML name
        return [{"value": value, "label": text, "note": note} for value, text, note in PLANNING_STYLES]

    @Property("QVariantList", constant=True)  # type: ignore[arg-type]
    def dragChoices(self) -> list:  # noqa: N802 — QML name
        return [{"value": minutes, "label": text} for minutes, text in DRAG_STEP_CHOICES]

    @Property(str, constant=True)
    def dragQuestion(self) -> str:  # noqa: N802 — QML name
        return DRAG_STEP_QUESTION

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def workWindows(self) -> list:  # noqa: N802 — QML name
        return [
            {
                "days": list(row.get("days") or []),
                "start": hhmm_text(row["start"]) if row.get("start") else "",
                "end": hhmm_text(row["end"]) if row.get("end") else "",
                "subject": row.get("subject") or "",
            }
            for row in self._windows
        ]

    @Property(bool, notify=changed)
    def canAddWindow(self) -> bool:  # noqa: N802 — QML name
        return len(self._windows) < MAX_WORK_WINDOWS

    @Property(str, notify=changed)
    def workMessage(self) -> str:  # noqa: N802 — QML name
        if self._windows:
            return "Homework is only planned between these times."
        return "Homework can be planned at any time of day."

    @Property(str, constant=True)
    def workPresetsNote(self) -> str:  # noqa: N802 — QML name
        return PRESETS_NOTE

    @Property(str, notify=changed)
    def workLimit(self) -> str:  # noqa: N802 — QML name
        if len(self._windows) >= MAX_WORK_WINDOWS:
            return f"{MAX_WORK_WINDOWS} is the most you can add."
        return ""

    @Property("QVariantList", constant=True)  # type: ignore[arg-type]
    def workPresets(self) -> list:  # noqa: N802 — QML name
        return [
            {"name": name, "objectName": "workWindowPreset" + name.replace(" ", "")}
            for name, *_rest in PRESETS
        ]

    @Property(bool, notify=changed)
    def remindersOn(self) -> bool:  # noqa: N802 — QML name
        return self._reminders

    @Property(int, notify=changed)
    def lead(self) -> int:
        return self._lead

    @Property(str, notify=changed)
    def tone(self) -> str:
        return self._tone

    @Property(str, notify=changed)
    def spotify(self) -> str:
        return self._spotify

    @Property(bool, notify=changed)
    def spotifyOn(self) -> bool:  # noqa: N802 — QML name
        return self._tone == "spotify"

    @Property(str, notify=changed)
    def testResult(self) -> str:  # noqa: N802 — QML name
        return self._test_result

    @Property("QVariantList", constant=True)  # type: ignore[arg-type]
    def tones(self) -> list:
        rows = [{"value": tone, "label": tone.title()} for tone in RECIPES]
        rows.append({"value": "spotify", "label": ALARM_TONE_LABELS["spotify"]})
        return rows

    @Property(str, constant=True)
    def spotifyNote(self) -> str:  # noqa: N802 — QML name
        return SPOTIFY_TONE_NOTE

    @Property(str, constant=True)
    def spotifyPlaceholder(self) -> str:  # noqa: N802 — QML name
        return SPOTIFY_PLACEHOLDER

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def homeworkRows(self) -> list:  # noqa: N802 — QML name
        return [
            {
                "title": row["title"],
                "minutes": row["minutes"],
                "due": row["due"],
                "timed": row["timed"],
                "time": hhmm_text(row["time"]),
            }
            for row in self._homework
        ]

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def dueChoices(self) -> list:  # noqa: N802 — QML name
        """The next two weeks as buttons, and any later date a row already holds."""
        today = wall_clock.today()
        days = [today + timedelta(days=ahead) for ahead in range(0, 14)]
        known = {day.isoformat() for day in days}
        extra = sorted({row["due"] for row in self._homework} - known)
        rows = [{"value": day.isoformat(), "label": day.strftime("%a %-d %b")} for day in days]
        for iso in extra:
            try:
                rows.append({"value": iso, "label": date.fromisoformat(iso).strftime("%a %-d %b")})
            except ValueError:
                continue
        return rows

    @Property("QVariantList", constant=True)  # type: ignore[arg-type]
    def lengthChoices(self) -> list:  # noqa: N802 — QML name
        return [{"value": minutes, "label": f"{minutes} min"} for minutes in QUICK_LENGTHS]

    @Property(bool, notify=changed)
    def canAddHomework(self) -> bool:  # noqa: N802 — QML name
        return len(self._homework) < MAX_FIRST_HOMEWORK

    @Property(str, constant=True)
    def dueHint(self) -> str:  # noqa: N802 — QML name
        return DUE_BY_HINT

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def summaryRows(self) -> list:  # noqa: N802 — QML name
        return list(self._summary)

    @Property(bool, notify=changed)
    def skipOpen(self) -> bool:  # noqa: N802 — QML name
        return self._skip_open

    @Property(str, notify=changed)
    def skipBody(self) -> str:  # noqa: N802 — QML name
        return self._skip_body

    @Property(str, notify=changed)
    def skipConfirm(self) -> str:  # noqa: N802 — QML name
        return self._skip_confirm

    @Property(str, notify=changed)
    def skipDismiss(self) -> str:  # noqa: N802 — QML name
        return self._skip_dismiss

    @Property(bool, notify=changed)
    def skipDismissKeeps(self) -> bool:  # noqa: N802 — QML name
        return self._skip_dismiss_keeps

    @Property(str, constant=True)
    def recoveryFile(self) -> str:  # noqa: N802 — QML name
        return RECOVERY_FILE

    def table(self, name: str) -> Table:
        return self._tables[name]

    def _sync_tables(self) -> None:
        for name, attribute in TABLES.items():
            self._tables[name].sync(getattr(self, attribute))

    # Internals

    def _on_busy(self, _busy: bool) -> None:
        self.changed.emit()

    def _on_status(self, message: str) -> None:
        if self._phase not in AUTH_PHASES:
            return
        if not message:
            self._clear_problems()
            self._status = ""
            self.changed.emit()
            return
        if message.endswith("…"):
            self._status = message
            self.changed.emit()
            return
        field = self._field_for(message)
        if field:
            self._clear_problems()
            self._problems[field] = message
            self._status = ""
        else:
            self._status = message
        self.changed.emit()

    def _field_for(self, message: str) -> str:
        words = message.lower()
        if message in {SIGN_IN_AGAIN, SESSION_ENDED}:
            return ""
        if message == TOO_MANY_TRIES:
            return "recovery" if self._phase == "reset" else "password"
        if message == USERNAME_ERROR:
            return "username"
        if message.startswith("Wrong username or password"):
            return "password"
        if "recovery code" in words or "each code" in words:
            return "recovery"
        if "username" in words:
            return "username"
        if "password" in words:
            return "new" if self._phase == "reset" else "password"
        return ""

    def _show_problem(self, message: str) -> None:
        self._clear_problems()
        field = self._field_for(message)
        if field:
            self._problems[field] = message
            self._status = ""
        else:
            self._status = message
        self.changed.emit()

    def _clear_problems(self) -> None:
        self._problems = {"username": "", "password": "", "recovery": "", "new": ""}
        self._why_open = False

    def _recovery_problem(self) -> str:
        password = self._new_password
        if not self._username.strip():
            return "Type your username."
        if not self._code.strip():
            return TYPE_RECOVERY_CODE
        if not password:
            return "Choose a password with at least 12 characters."
        if len(password) < 12:
            return short_password_needed(12 - len(password))
        return ""

    def _reset_recovery_labels(self) -> None:
        self._copy_label = RECOVERY_COPY
        self._save_label = RECOVERY_SAVE
        self.changed.emit()

    def _style(self, key: str) -> Style | None:
        return next((style for style in MATERIAL_STYLES if style.key == key), None)

    def _matching_style(self) -> str | None:
        from desktop.native.setup import matching_style

        return matching_style(self._pack, self._look, self._layout)

    def _apply_style(self, key: str, *, preview: bool) -> None:
        style = self._style(key)
        if style is None:
            return
        self._style_key = style.key
        self._own_look = False
        self._pack = style.pack
        self._look = style_look(style)
        self._layout = style_layout(style, self._layout)
        token = self._style_tokens.get(style.main) or style.colour or DESIGN_LOOKS[style.main][0][0]
        self._style_tokens[style.main] = token
        self._layout["options"][style.main]["look"] = token
        self._layout = sanitize_layout(self._layout)
        if preview:
            self._preview()

    def _preview(self) -> None:
        """Dress the window in the look being tried, then republish Material.

        The saved surface is not changed. A standard style still stores its own
        pack for the day the student switches back to the widgets styles.
        """
        self._window._preview_setup_look(  # type: ignore[attr-defined]
            {"pack": self._pack, "look": deepcopy(self._look), "layout": deepcopy(self._layout)}
        )
        page = getattr(self._window, "_material_page", None)
        if page is None or not getattr(page, "_ready", False):
            return
        try:
            page.publish()
        except Exception as error:
            log.warning("Material 3 could not be re-dressed: %s", error)

    def _apply_clock(self) -> None:
        set_clock_24h(self._clock_24h)

    def _restore_entered(self) -> None:
        pack, look, layout = self._entered
        self._pack = pack
        self._look = deepcopy(look)
        self._layout = deepcopy(layout)

    def _load_fields(self) -> None:
        prefs = dict(self._state.preferences)
        self._clock_24h = prefs.get("clock_24h") is True
        self._apply_clock()
        self._week_start = week_starts_on()
        blocks = list(self._state.blocks)
        school = next((block for block in blocks if block.get("id") == SETUP_SCHOOL_ID), None)
        if school is not None and school.get("start"):
            self._school_days = [int(day) for day in school.get("days") or []]
            self._school_start = str(school["start"])
            self._school_end = minutes_to_hhmm(
                hhmm_to_minutes(self._school_start) + int(school["duration_min"])
            )
        else:
            self._school_days = [0, 1, 2, 3, 4]
            self._school_start = "08:00"
            self._school_end = "14:30"
        self._activities = []
        for block in blocks:
            if is_setup_block(block) and block.get("id") != SETUP_SCHOOL_ID and block.get("start"):
                start = str(block["start"])
                end = minutes_to_hhmm(hhmm_to_minutes(start) + int(block["duration_min"]))
                self._activities.append(
                    {
                        "id": str(block["id"]),
                        "title": str(block.get("title") or ""),
                        "days": [int(day) for day in block.get("days") or []],
                        "start": start,
                        "end": end,
                        "category": str(block.get("category") or "extra"),
                        "touched": True,
                    }
                )
        if not self._activities:
            self._activities.append(_blank_activity())
        self._week_opened = self._week_fingerprint()
        cutoff = prefs.get("day_cutoff")
        self._cutoff = cutoff if isinstance(cutoff, str) else ""
        self._saved_cutoff = self._cutoff
        planning = prefs.get("planning_style") or "suggest"
        self._planning = planning if planning in {item[0] for item in PLANNING_STYLES} else "suggest"
        self._drag = drag_step(prefs.get("drag_step_min"))
        self._windows = [dict(row) for row in (prefs.get("work_windows") or [])]
        self._reminders = prefs.get("reminders_enabled", True) is not False
        self._lead = reminder_lead_min(None if self._state.first_run else prefs)
        tone = str(prefs.get("alarm_tone") or FALLBACK)
        self._tone = tone if tone in RECIPES or tone == "spotify" else FALLBACK
        self._spotify = str(prefs.get("default_spotify_url") or "")
        self._homework = [_blank_homework(next_school_day(self._school_days))]
        self._apply_clock()

    def _week_fingerprint(self) -> tuple:
        rows = tuple(
            (row["title"], tuple(row["days"]), (row["start"], _minutes(row["start"], row["end"])))
            for row in self._activities
        )
        school = (self._school_start, _minutes(self._school_start, self._school_end))
        return (tuple(self._school_days), school, rows)

    def _kept_on_week(self) -> list[str]:
        if self._week_fingerprint() == self._week_opened:
            return []
        names = ["School"] if self._school_days else []
        names += [row["title"].strip() or SPORT_FALLBACK for row in self._activities if row["days"]]
        return names

    def _problem(self) -> str:
        if self._step == WEEK:
            if self._school_days and _minutes(self._school_start, self._school_end) <= 0:
                return "School has to end after it starts."
            for row in self._activities:
                if row["days"] and _minutes(row["start"], row["end"]) <= 0:
                    name = row["title"].strip() or "An activity"
                    return f"{name} has to end after it starts."
        if self._step == REMINDERS and self._tone == "spotify" and self._spotify_link() is None:
            return SPOTIFY_PROBLEM
        if self._step == HOMEWORK:
            for row in self._windows:
                if row.get("end", "") <= row.get("start", ""):
                    return end_after_start_words(hhmm_text(str(row.get("start") or "")))
        return ""

    def _spotify_link(self) -> str | None:
        typed = self._spotify.strip()
        if not typed:
            return None
        try:
            return valid_spotify_url(typed) or None
        except ValueError:
            return None

    def _answer(self) -> dict | None:
        if self._step == STYLE:
            self._apply_style(self._style_key, preview=False)
        if self._step in LOOK_STEPS:
            return {"pack": self._pack, "look": deepcopy(self._look), "layout": deepcopy(self._layout)}
        if self._step == WEEK:
            return {
                "blocks": self._week_blocks(),
                "day_cutoff": self._cutoff or None,
                "clock_24h": self._clock_24h,
            }
        if self._step == HOMEWORK:
            return {
                "planning_style": self._planning,
                "drag_step_min": self._drag,
                "work_windows": deepcopy(self._windows),
            }
        if self._step == REMINDERS:
            prefs = self._state.preferences if self._state is not None else {}
            return {
                "reminders_enabled": self._reminders,
                "reminder_lead_min": self._lead,
                "alarm_tone": self._tone,
                "default_spotify_url": self._spotify_link() or prefs.get("default_spotify_url"),
            }
        if self._step == FIRST:
            homework = self._first_homework()
            return {"homework": homework} if homework else None
        return None

    def _week_blocks(self) -> list[dict]:
        blocks: list[dict] = []
        minutes = _minutes(self._school_start, self._school_end)
        if self._school_days and minutes > 0:
            blocks.append(
                {
                    "id": SETUP_SCHOOL_ID,
                    "title": "School",
                    "kind": "locked",
                    "category": "class",
                    "start": self._school_start,
                    "duration_min": minutes,
                    "days": list(self._school_days),
                }
            )
        for row in self._activities:
            span = _minutes(row["start"], row["end"])
            if not row["days"] or span <= 0:
                continue
            blocks.append(
                {
                    "id": row["id"],
                    "title": row["title"].strip() or SPORT_FALLBACK,
                    "kind": "locked",
                    "category": row["category"],
                    "start": row["start"],
                    "duration_min": span,
                    "days": list(row["days"]),
                }
            )
        return blocks

    def _first_homework(self) -> list[dict]:
        made = []
        for row in self._homework:
            title = row["title"].strip()
            if not title:
                continue
            due = f"{row['due']}T{row['time']}" if row["timed"] else row["due"]
            item = {
                "id": self._made.get(title) or str(uuid4()),
                "title": title,
                "estimate_min": int(row["minutes"]),
                "due": due,
                "revision": 0,
            }
            self._made[title] = item["id"]
            made.append(item)
        return made

    def _absorb(self, answer: dict) -> None:
        if self._state is None:
            return
        if self._step in LOOK_STEPS:
            self._state.pack = answer["pack"]
            self._state.look = deepcopy(answer["look"])
            self._state.layout = deepcopy(answer["layout"])
            self._entered = (self._pack, deepcopy(self._look), deepcopy(self._layout))
        elif self._step == WEEK:
            kept = [block for block in self._state.blocks if not is_setup_block(block)]
            self._state.blocks = kept + deepcopy(answer["blocks"])
            self._state.preferences["day_cutoff"] = answer["day_cutoff"]
            self._state.preferences["clock_24h"] = answer["clock_24h"]
        elif self._step in (HOMEWORK, REMINDERS):
            self._state.preferences.update(deepcopy(answer))
        elif self._step == FIRST:
            for item in answer["homework"]:
                if item["title"] not in self._state.homework:
                    self._state.homework.append(item["title"])

    def _leave(self, destination: int, *, keep: bool) -> None:
        answer = None
        if keep:
            problem = self._problem()
            if problem:
                self._problem_text = problem
                self._skip_open = False
                self.changed.emit()
                return
            answer = self._answer()
            if self._step == STYLE and not self._own_look:
                self._surface_pick = "material" if self._style_key == MATERIAL_STYLE.key else "widgets"
            if self._step == WEEK:
                save_week_starts_on(self._week_start)
        elif self._step in LOOK_STEPS and destination not in LOOK_STEPS:
            self._restore_entered()
            self._preview()
        elif self._step == WEEK:
            self._clock_24h = (self._state.preferences.get("clock_24h") is True) if self._state else False
            self._apply_clock()
        if answer is not None:
            self._absorb(answer)
        self._window._setup_step_left(self._step, destination, answer)  # type: ignore[attr-defined]
        self._show(destination)

    def _show(self, step: int) -> None:
        if step in LOOK_STEPS and self._step not in LOOK_STEPS:
            self._entered = (self._pack, deepcopy(self._look), deepcopy(self._layout))
        self._step = step
        self._furthest = max(self._furthest, step)
        self._problem_text = ""
        self._skip_open = False
        if step == STYLE and self._style_key:
            self._apply_style(self._style_key, preview=True)
        self._apply_clock()
        if step == DONE:
            self._summary = self._build_summary()
        self.changed.emit()

    def _after(self) -> int:
        if self._step == STYLE:
            return WEEK
        return min(self._step + 1, DONE)

    def _before(self) -> int:
        if self._step == WEEK:
            return COLOURS if self._own_look else STYLE
        return max(self._step - 1, STYLE)

    def _open_skip(self, names: list[str]) -> None:
        what = " and ".join(names)
        problem = self._problem()
        if problem:
            named = names[0]
            self._skip_body = f"{named}'s times don't work ({problem}). Fix them, or skip without {what}?"
            self._skip_dismiss = "Fix them"
            self._skip_dismiss_keeps = False
        else:
            self._skip_body = f"Keep {what} and go on, or skip without {what}?"
            self._skip_dismiss = f"Keep {what} and go on"
            self._skip_dismiss_keeps = True
        self._skip_confirm = f"Skip without {what}"
        self._skip_open = True
        self.changed.emit()

    def _add_window(self, window: dict) -> None:
        if len(self._windows) >= MAX_WORK_WINDOWS:
            return
        self._windows.append(window)
        self.changed.emit()

    def _build_summary(self) -> list[dict[str, str]]:
        if self._state is None:
            return []
        state = self._state
        if self._style_key == MATERIAL_STYLE.key and not self._own_look:
            look = MATERIAL_STYLE.name
        else:
            main = state.layout["main"]
            spec = LAYOUTS[main]
            selected = options_for(state.layout, main).get("look")
            colour_name = next(
                (label for value, label in DESIGN_LOOKS[main] if value == selected), "Your look"
            )
            text = effective_look(state.look)["text"]
            look = f"{spec.label} in {colour_name}"
            if text != "normal":
                look += f", {text} text"
        week_parts = []
        for block in state.blocks:
            if is_setup_block(block) and block.get("start"):
                when = span_label(block["start"], block["duration_min"])
                week_parts.append(f"{block['title']} {days_label(block['days'])} {when}")
        cutoff = state.preferences.get("day_cutoff")
        if cutoff:
            week_parts.append(f"no homework after {hhmm_text(cutoff)}")
        prefs = state.preferences
        chosen = prefs.get("planning_style") or "suggest"
        planning = next(
            (label for value, label, _note in PLANNING_STYLES if value == chosen),
            PLANNING_STYLES[1][1],
        )
        windows = prefs.get("work_windows") or []
        if windows:
            shown = [
                f"{days_label(item['days'])} {hhmm_text(item['start'])}–{hhmm_text(item['end'])}"
                for item in windows[:2]
            ]
            planning += " · homework only " + ", ".join(shown)
            if len(windows) > 2:
                planning += f" and {len(windows) - 2} more"
        else:
            planning += " · homework can be planned at any time of day"
        planning += f" · a drag moves {drag_step(prefs.get('drag_step_min'))} minutes at a time"
        tone = str(prefs.get("alarm_tone") or FALLBACK)
        sound = "Spotify" if tone == "spotify" else tone.title()
        if prefs.get("reminders_enabled", True) is not False:
            reminders = f"{reminder_lead_min(prefs)} min before things start · {sound}"
        else:
            reminders = f"Off · alarms ring {sound}"
        homework = " · ".join(state.homework) or "None yet"
        values = (look, " · ".join(week_parts) or "Nothing fixed yet", planning, reminders, homework)
        names = [name for name, _steps in RAIL[:-1]]
        return [{"name": name, "value": value} for name, value in zip(names, values, strict=True)]

    @staticmethod
    def _row(rows: list, index: int) -> dict | None:
        if 0 <= index < len(rows):
            return rows[index]
        return None
