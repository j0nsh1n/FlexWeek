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
from pathlib import Path
from typing import Any

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

from backend.models import valid_spotify_url
from backend.slots import hhmm_to_minutes, minutes_to_hhmm
from desktop.native.account_copy import (
    CREATE_HEADING,
    CREATE_NOTE,
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
from desktop.native.calendar import (
    DAY_FULL,
    DAYS,
    SETUP_SCHOOL_ID,
    is_setup_block,
    new_activity_id,
    weekday_order,
)
from desktop.native.client import (
    PASSWORD_LENGTH_HINT,
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
from desktop.native.fields import (
    WEEK_STARTS,
    read_clock,
    save_week_starts_on,
    week_starts_on,
)
from desktop.native.hours.geometry import drag_step
from desktop.native.material.theme import ONE_MODE
from desktop.native.remind import reminder_lead_min
from desktop.native.settings_copy import (
    ALARM_TONE_LABELS,
    DRAG_STEP_CHOICES,
    DRAG_STEP_QUESTION,
    PLANNING_STYLES,
    SPORT_FALLBACK,
    SPOTIFY_TONE_NOTE,
)
from desktop.native.setup_steps import (
    FINISH_LABEL,
    HOMEWORK,
    LOOK_MODE_CARDS,
    MATERIAL_LAST,
    MATERIAL_NOTES,
    MATERIAL_RAIL,
    MATERIAL_TITLES,
    MAX_ACTIVITIES,
    NEXT_LABEL,
    RAIL_STATES,
    REMINDER_LEADS,
    REMINDERS,
    ROW_SIZE_CARDS,
    SCHOOL_CARDS,
    SCHOOL_CUSTOM_NOTE,
    SCHOOL_CUSTOM_TITLE,
    SCHOOL_DAYS_CARD,
    SKIP_ALL_LABEL,
    SKIP_STEP_LABEL,
    SOUND_CARD_TITLE,
    STUDY_CARDS,
    WEEK,
    activity_category_for,
    days_label,
    span_label,
)
from desktop.native.sheet_rules import CUTOFFS
from desktop.native.tones import FALLBACK, RECIPES
from desktop.native.weekmodel import end_after_start_words, hhmm_text, set_clock_24h
from desktop.native.work_windows import MAX_WORK_WINDOWS, PRESETS, PRESETS_NOTE

log = logging.getLogger("flexweek.material")

# Three steps: Material has no style page (Material 3 is the only style) and no first-homework or Done page.
RAIL_STEPS = MATERIAL_RAIL
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


def _hour_label(hour: int) -> str:
    """An hour on the preview's side: 8 AM, or 08:00 on the 24-hour clock."""
    return hhmm_text(f"{hour:02d}:00").replace(":00 ", " ")


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
    "activitiesModel": "activities",
    "workModel": "workWindows",
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
        self._ask: dict = {}
        self._ask_handlers: dict[str, Any] | None = None
        self._edited_done = None
        self._state: Any = None
        self._step = WEEK
        self._furthest = WEEK
        self._clock_24h = False
        self._week_start = "monday"
        self._school_days = [0, 1, 2, 3, 4]
        self._school_start = "08:00"
        self._school_end = "15:00"
        self._school_custom = False
        self._study_custom = False
        self._sound_open = False
        self._settings: Any = None
        self._look_opened: dict[str, str] = {}
        self._look_touched = False
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
        self._problem_text = ""
        self._test_result = ""
        self._skip_open = False
        self._skip_body = ""
        self._skip_confirm = ""
        self._skip_dismiss = ""
        self._skip_dismiss_keeps = False
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
        """Save: the sheet says what the file is first, then the system's file dialog picks where it goes."""
        self.pose_question(
            self._window.recovery_file_question(),  # type: ignore[attr-defined]
            {"choose": lambda: self._write_codes(self._window._pick_recovery_file())},  # type: ignore[attr-defined]
        )

    def _write_codes(self, path: str) -> None:
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
        self._load_fields()
        # A step before School hours is from the removed style pages. One past Look and alerts is from the
        # older five-step setup, which ended on First homework and Done: it resumes on the last step.
        self._step = WEEK if step < WEEK else min(step, MATERIAL_LAST)
        self._furthest = self._step
        self._problem_text = ""
        self._test_result = ""
        self._skip_open = False
        self._look_opened = self._look_choice()
        self._look_touched = False
        self._phase = "setup"
        self._apply_clock()
        self.changed.emit()

    def use_settings(self, settings: Any) -> None:
        """The Settings bridge, which setup's look cards write through, so setup and Settings agree."""
        self._settings = settings

    @Slot(int)
    def toggleSchoolDay(self, day: int) -> None:  # noqa: N802 — QML slot
        days = set(self._school_days)
        if day in days:
            days.discard(day)
        elif 0 <= day <= 6:
            days.add(day)
        self._school_days = sorted(days)
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
        if value in WEEK_STARTS:
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

    # The cards. A card is one answer: it sets the fields the old page's controls set, and the detailed
    # controls (shown while `power` is on) change the same fields.

    @Slot(str)
    def setSchoolPreset(self, key: str) -> None:  # noqa: N802 — QML slot
        if key == "custom":
            self._school_custom = True
        else:
            card = next((item for item in SCHOOL_CARDS if item[0] == key), None)
            if card is None:
                return
            self._school_custom = False
            self._school_days = list(SCHOOL_DAYS_CARD)
            self._school_start, self._school_end = card[1], card[2]
        self.changed.emit()

    @Slot(str)
    def setStudyPreset(self, key: str) -> None:  # noqa: N802 — QML slot
        if key == "custom":
            self._study_custom = True
            self.changed.emit()
            return
        card = next((item for item in STUDY_CARDS if item[0] == key), None)
        if card is None:
            return
        self._study_custom = False
        self._windows = []
        if card[1] is not None:
            for label, days, start, end in PRESETS:
                if label == card[1]:
                    self._windows.append({"days": list(days), "start": start, "end": end})
        self.changed.emit()

    @Slot(str)
    def setReminderChoice(self, value: str) -> None:  # noqa: N802 — QML slot
        if value == "off":
            self._reminders = False
        elif value == "current":
            self._reminders = True
        elif value.isdigit() and int(value) in REMINDER_LEADS:
            self._reminders = True
            self._lead = int(value)
        else:
            return
        self.changed.emit()

    @Slot(bool)
    def setSoundOpen(self, on: bool) -> None:  # noqa: N802 — QML slot
        self._sound_open = bool(on)
        self.changed.emit()

    @Slot()
    def useDefaultSound(self) -> None:  # noqa: N802 — QML slot
        self._tone = FALLBACK
        self._sound_open = False
        self._test_result = ""
        self.changed.emit()

    @Slot(str)
    def setLookPreset(self, name: str) -> None:  # noqa: N802 — QML slot
        self._apply_look(preset=name)

    @Slot(str)
    def setLookMode(self, mode: str) -> None:  # noqa: N802 — QML slot
        self._apply_look(mode=mode)

    @Slot(str)
    def setLookDensity(self, density: str) -> None:  # noqa: N802 — QML slot
        self._apply_look(density=density)

    def _look_choice(self) -> dict[str, str]:
        if self._settings is None:
            return {}
        choice = self._settings._choice
        return {key: choice[key] for key in ("preset", "mode", "density")}

    def _apply_look(self, **parts: str) -> None:
        """A look card applies at once, as in Settings, so the whole window shows the look being picked.
        Skipping the step puts the look it opened with back."""
        if self._settings is None:
            return
        self._look_touched = True
        self._settings.apply_setup_look(**parts)
        self.changed.emit()

    def _restore_look(self) -> None:
        if self._look_touched and self._settings is not None and self._look_opened:
            self._settings.apply_setup_look(**self._look_opened)
        self._look_touched = False

    def pose_edited(self, ask: dict, done) -> None:
        """The edited-weeks question over setup. `done` is called with the answer, or None to cancel."""
        self._edited_done = done
        self._ask = ask
        self.changed.emit()

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def ask(self) -> dict:
        return self._ask

    def pose_question(self, question: dict, handlers: dict[str, Any]) -> None:
        """A question over the account screens (the recovery codes' file). Each answer runs its handler;
        Cancel and Esc run none."""
        self._ask = dict(question)
        self._ask_handlers = handlers
        self.changed.emit()

    @Slot(str)
    def answer(self, choice: str) -> None:
        if self._ask_handlers is not None:
            handlers, self._ask_handlers = self._ask_handlers, None
            self._ask = {}
            self.changed.emit()
            run = handlers.get(choice)
            if run is not None:
                run()
            return
        self._finish_edited(choice if choice in ("keep", "replace", "from_today") else None)

    @Slot()
    def closeSheet(self) -> None:  # noqa: N802 — QML name
        if self._ask_handlers is not None:
            self._ask_handlers = None
            self._ask = {}
            self.changed.emit()
            return
        self._finish_edited(None)

    def _finish_edited(self, choice: str | None) -> None:
        done, self._edited_done = self._edited_done, None
        if not self._ask and done is None:
            return
        self._ask = {}
        self.changed.emit()
        if done is not None:
            done(choice)

    @Slot()
    def setupNext(self) -> None:  # noqa: N802 — QML slot
        if self._step == MATERIAL_LAST:
            self._finish(keep=True)
            return
        self._leave(self._after(), keep=True)

    @Slot()
    def setupBack(self) -> None:  # noqa: N802 — QML slot
        if self._step != WEEK:
            self._leave(self._before(), keep=False)

    @Slot()
    def setupSkip(self) -> None:  # noqa: N802 — QML slot
        if self._step == MATERIAL_LAST:
            self._finish(keep=False)
            return
        if self._step == WEEK:
            names = self._kept_on_week()
            if names:
                self._open_skip(names)
                return
        self._leave(self._after(), keep=False)

    @Slot()
    def setupSkipAll(self) -> None:  # noqa: N802 — QML slot
        if self._step == WEEK:
            self._clock_24h = (self._state.preferences.get("clock_24h") is True) if self._state else False
            self._apply_clock()
        self._restore_look()
        self._window._finish_setup()  # type: ignore[attr-defined]

    @Slot(int)
    def setupJump(self, step: int) -> None:  # noqa: N802 — QML slot
        if step == self._step or step > self._furthest:
            return
        self._leave(step, keep=step > self._step)

    @Slot(int, result=int)
    def stepFor(self, index: int) -> int:  # noqa: N802 — QML slot
        """The first step of the rail's `index`th entry."""
        return RAIL_STEPS[index][1][0] if 0 <= index < len(RAIL_STEPS) else WEEK

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
            return MATERIAL_TITLES[self._step]
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
            return MATERIAL_NOTES[self._step]
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
    def activitiesModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["activitiesModel"]

    @Property(QObject, constant=True)
    def workModel(self) -> QObject:  # noqa: N802 — QML name
        return self._tables["workModel"]

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
        return FINISH_LABEL if self._step == MATERIAL_LAST else NEXT_LABEL

    @Property(bool, notify=changed)
    def backVisible(self) -> bool:  # noqa: N802 — QML name
        return self._phase == "setup" and self._step != WEEK

    @Property(bool, notify=changed)
    def skipVisible(self) -> bool:  # noqa: N802 — QML name
        return self._phase == "setup"

    @Property(bool, notify=changed)
    def skipStepVisible(self) -> bool:  # noqa: N802 — QML name
        """Skip this step needs a next step to go to; on the last one Skip setup does the same."""
        return self._phase == "setup" and self._step != MATERIAL_LAST

    @Property(str, constant=True)
    def skipLabel(self) -> str:  # noqa: N802 — QML name
        return SKIP_STEP_LABEL

    @Property(str, constant=True)
    def skipAllLabel(self) -> str:  # noqa: N802 — QML name
        return SKIP_ALL_LABEL

    @Property(str, constant=True)
    def backLabel(self) -> str:  # noqa: N802 — QML name
        return "Back"

    @Property(str, notify=changed)
    def setupProblem(self) -> str:  # noqa: N802 — QML name
        return self._problem_text

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def rail(self) -> list:
        rows = []
        for index, (name, steps) in enumerate(RAIL_STEPS):
            current = self._step in steps
            done = max(steps) < self._step
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

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def dayNames(self) -> list:  # noqa: N802 — QML name
        """The days in the order shown, from the first day picked on this page."""
        first = WEEK_STARTS.index(self._week_start)
        return [{"day": day, "short": DAYS[day], "full": DAY_FULL[day]} for day in weekday_order(first)]

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

    # What the cards show and the preview draws

    def _school_card_for_fields(self) -> str:
        for key, start, end, _note, _tag in SCHOOL_CARDS:
            if (
                self._school_days == SCHOOL_DAYS_CARD
                and self._school_start == start
                and self._school_end == end
            ):
                return key
        return "custom"

    def _school_card(self) -> str:
        return "custom" if self._school_custom else self._school_card_for_fields()

    def _study_card_for_fields(self) -> str:
        if not self._windows:
            return "anytime"
        if len(self._windows) == 1:
            row = self._windows[0]
            for key, preset, _note, _tag in STUDY_CARDS:
                for label, days, start, end in PRESETS:
                    if (
                        label == preset
                        and not row.get("subject")
                        and list(row.get("days") or []) == list(days)
                        and (row.get("start"), row.get("end")) == (start, end)
                    ):
                        return key
        return "custom"

    def _study_card(self) -> str:
        return "custom" if self._study_custom else self._study_card_for_fields()

    def _power(self) -> bool:
        """The detailed controls show only after a card that means them was picked."""
        return self._school_card() == "custom" or self._study_card() == "custom" or self._sound_open

    def _reminder_card(self) -> str:
        if not self._reminders:
            return "off"
        return str(self._lead) if self._lead in REMINDER_LEADS else "current"

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def schoolCards(self) -> list:  # noqa: N802 — QML name
        picked = self._school_card()
        rows = [
            {
                "value": key,
                "title": f"Mon–Fri · {hhmm_text(start)} to {hhmm_text(end)}",
                "note": note,
                "tag": tag,
                "selected": picked == key,
            }
            for key, start, end, note, tag in SCHOOL_CARDS
        ]
        rows.append(
            {
                "value": "custom",
                "title": SCHOOL_CUSTOM_TITLE,
                "note": SCHOOL_CUSTOM_NOTE,
                "tag": "More options",
                "selected": picked == "custom",
            }
        )
        return rows

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def studyCards(self) -> list:  # noqa: N802 — QML name
        picked = self._study_card()
        titles = {"anytime": "Any open time", "custom": "Custom study hours and drag step…"}
        for label, _days, start, end in PRESETS:
            titles[{"After school": "after_school", "Evenings": "evenings"}.get(label, "")] = (
                f"{label} ({hhmm_text(start)}–{hhmm_text(end)})"
            )
        return [
            {"value": key, "title": titles[key], "note": note, "tag": tag, "selected": picked == key}
            for key, _preset, note, tag in STUDY_CARDS
        ]

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def reminderCards(self) -> list:  # noqa: N802 — QML name
        picked = self._reminder_card()
        rows = [
            {
                "value": str(lead),
                "title": f"{lead} minutes before",
                "note": "",
                "tag": "Default" if lead == reminder_lead_min(None) else "",
            }
            for lead in REMINDER_LEADS
        ]
        if picked == "current":
            words = f"{self._lead} minutes before" if self._lead else "When a block starts"
            rows.insert(0, {"value": "current", "title": words, "note": "", "tag": "Now"})
        rows.append({"value": "off", "title": "No reminders", "note": "I'll check my week myself", "tag": ""})
        return [{**row, "selected": row["value"] == picked} for row in rows]

    @Property(bool, notify=changed)
    def power(self) -> bool:
        return self._power()

    @Property(bool, notify=changed)
    def soundOpen(self) -> bool:  # noqa: N802 — QML name
        return self._sound_open

    @Property(str, constant=True)
    def soundCardTitle(self) -> str:  # noqa: N802 — QML name
        return SOUND_CARD_TITLE

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def lookPresets(self) -> list:  # noqa: N802 — QML name
        return list(self._settings.state.get("swatches") or []) if self._settings is not None else []

    @Property(str, notify=changed)
    def lookPreset(self) -> str:  # noqa: N802 — QML name
        return self._look_choice().get("preset", "")

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def lookModes(self) -> list:  # noqa: N802 — QML name
        choice = self._look_choice()
        one = ONE_MODE.get(choice.get("preset", ""))
        picked = one or choice.get("mode", "system")
        return [
            {
                "value": value,
                "title": title,
                "note": note,
                "selected": picked == value,
                "enabled": not one or one == value,
            }
            for value, title, note in LOOK_MODE_CARDS
        ]

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def rowSizes(self) -> list:  # noqa: N802 — QML name
        picked = self._look_choice().get("density", "comfortable")
        return [
            {"value": value, "title": title, "note": note, "selected": picked == value}
            for value, title, note in ROW_SIZE_CARDS
        ]

    def _fixed_times(self) -> list[dict[str, Any]]:
        """Each school block, sport or job the student entered, as the preview draws it."""
        rows: list[dict[str, Any]] = []
        minutes = _minutes(self._school_start, self._school_end)
        if self._school_days and minutes > 0:
            rows.append(
                {
                    "title": "School",
                    "category": "class",
                    "days": list(self._school_days),
                    "start": self._school_start,
                    "end": self._school_end,
                }
            )
        for row in self._activities:
            if row["days"] and _minutes(row["start"], row["end"]) > 0:
                title = row["title"].strip() or SPORT_FALLBACK
                rows.append(
                    {
                        "title": title,
                        "category": row["category"],
                        "days": list(row["days"]),
                        "start": row["start"],
                        "end": row["end"],
                    }
                )
        return rows

    def _study_times(self) -> list[dict[str, Any]]:
        rows = []
        for row in self._windows:
            start, end = str(row.get("start") or ""), str(row.get("end") or "")
            if row.get("days") and start and end and _minutes(start, end) > 0:
                subject = row.get("subject")
                rows.append(
                    {
                        "title": f"Study: {subject}" if subject else "Study hours",
                        "category": "study",
                        "days": list(row["days"]),
                        "start": start,
                        "end": end,
                    }
                )
        return rows

    def _preview(self) -> dict[str, Any]:
        """The week as far as the student has said it: school and fixed times from the first step, study
        hours from the second. Nothing else is drawn."""
        groups = self._fixed_times()
        if self._step >= HOMEWORK:
            groups += self._study_times()
        used = {day for group in groups for day in group["days"]}
        order = [row["day"] for row in self.dayNames]
        shown = [day for day in order if day in used or day < 5]
        blocks: list[dict[str, Any]] = []
        for group in groups:
            for day in group["days"]:
                begin, finish = hhmm_to_minutes(group["start"]), hhmm_to_minutes(group["end"])
                blocks.append(
                    {
                        "column": shown.index(day),
                        "title": group["title"],
                        "category": group["category"],
                        "detail": span_label(group["start"], finish - begin),
                        "start": begin,
                        "end": finish,
                        "lane": 0,
                        "lanes": 1,
                    }
                )
        self._lanes(blocks)
        if blocks:
            first = min(item["start"] for item in blocks) // 60
            last = -(-max(item["end"] for item in blocks) // 60)
        else:
            first, last = 8, 16
        first = max(0, min(first, 24 - 6))
        last = min(24, max(last, first + 6))
        return {
            "days": [{"day": day, "short": DAYS[day]} for day in shown],
            "blocks": blocks,
            "from": first,
            "to": last,
            "hours": [{"hour": hour, "label": _hour_label(hour)} for hour in range(first, last)],
        }

    @staticmethod
    def _lanes(blocks: list[dict[str, Any]]) -> None:
        """Blocks that overlap on one day sit side by side, each in its own lane."""
        by_column: dict[int, list[dict[str, Any]]] = {}
        for item in blocks:
            by_column.setdefault(item["column"], []).append(item)
        for column in by_column.values():
            column.sort(key=lambda item: (item["start"], item["end"]))
            cluster: list[dict[str, Any]] = []
            ends: list[int] = []
            for item in column:
                if cluster and item["start"] >= max(ends):
                    for member in cluster:
                        member["lanes"] = len(ends)
                    cluster, ends = [], []
                lane = next((at for at, end in enumerate(ends) if end <= item["start"]), len(ends))
                if lane == len(ends):
                    ends.append(item["end"])
                else:
                    ends[lane] = item["end"]
                item["lane"] = lane
                cluster.append(item)
            for member in cluster:
                member["lanes"] = len(ends)

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def preview(self) -> dict:
        return self._preview()

    @Property(str, notify=changed)
    def previewNote(self) -> str:  # noqa: N802 — QML name
        if not self._fixed_times() and not (self._step >= HOMEWORK and self._study_times()):
            return "Nothing to show yet. What you pick appears here."
        words = ["your school hours"] if self._school_days else []
        if any(row["category"] != "class" for row in self._fixed_times()):
            words.append("sports and jobs")
        if self._step >= HOMEWORK and self._study_times():
            words.append("study hours")
        joined = ", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else words[0]
        return f"Showing {joined}"

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def chosenSoFar(self) -> list:  # noqa: N802 — QML name
        """What is picked so far, one line each, for the card under the preview."""
        parts = []
        minutes = _minutes(self._school_start, self._school_end)
        if self._school_days and minutes > 0:
            parts.append(f"{days_label(self._school_days)} {span_label(self._school_start, minutes)}")
        else:
            parts.append("no school")
        count = len(self._fixed_times()) - (1 if self._school_days and minutes > 0 else 0)
        if count:
            parts.append(f"{count} sport, club or job" + ("" if count == 1 else "s"))
        if self._cutoff:
            parts.append(f"no homework after {hhmm_text(self._cutoff)}")
        rows = ["School hours: " + " · ".join(parts)]
        if self._step >= HOMEWORK:
            label = next(
                (text for value, text, _note in PLANNING_STYLES if value == self._planning),
                PLANNING_STYLES[1][1],
            )
            study = (
                "homework at any open time"
                if not self._windows
                else f"{len(self._windows)} study time" + ("" if len(self._windows) == 1 else "s")
            )
            rows.append(f"Homework: {label} · {study}")
        if self._step >= REMINDERS:
            lead = f"{self._lead} min before things start" if self._reminders else "no reminders"
            choice = self._look_choice()
            mode = {"system": "same as this computer", "light": "light", "dark": "dark"}.get(
                ONE_MODE.get(choice.get("preset", "")) or choice.get("mode", "system"), ""
            )
            rows.append(f"Reminders: {lead}")
            rows.append(
                f"Look: {choice.get('preset', '')}, {mode}, {choice.get('density', 'comfortable')} rows"
            )
        return rows

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

    def _apply_clock(self) -> None:
        set_clock_24h(self._clock_24h)

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
            self._school_end = "15:00"
        self._school_custom = self._school_card_for_fields() == "custom"
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
        self._school_custom = self._school_custom or any(row["days"] for row in self._activities)
        self._week_opened = self._week_fingerprint()
        cutoff = prefs.get("day_cutoff")
        self._cutoff = cutoff if isinstance(cutoff, str) else ""
        self._school_custom = self._school_custom or bool(self._cutoff)
        self._saved_cutoff = self._cutoff
        planning = prefs.get("planning_style") or "suggest"
        self._planning = planning if planning in {item[0] for item in PLANNING_STYLES} else "suggest"
        self._drag = drag_step(prefs.get("drag_step_min"))
        self._windows = [dict(row) for row in (prefs.get("work_windows") or [])]
        self._study_custom = self._study_card_for_fields() == "custom"
        self._reminders = prefs.get("reminders_enabled", True) is not False
        self._lead = reminder_lead_min(None if self._state.first_run else prefs)
        tone = str(prefs.get("alarm_tone") or FALLBACK)
        self._tone = tone if tone in RECIPES or tone == "spotify" else FALLBACK
        self._spotify = str(prefs.get("default_spotify_url") or "")
        # The alarm sound stays tucked away while it is the default and no link is saved.
        self._sound_open = self._tone != FALLBACK or bool(self._spotify)
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

    def _absorb(self, answer: dict) -> None:
        if self._state is None:
            return
        if self._step == WEEK:
            kept = [block for block in self._state.blocks if not is_setup_block(block)]
            self._state.blocks = kept + deepcopy(answer["blocks"])
            self._state.preferences["day_cutoff"] = answer["day_cutoff"]
            self._state.preferences["clock_24h"] = answer["clock_24h"]
        elif self._step in (HOMEWORK, REMINDERS):
            self._state.preferences.update(deepcopy(answer))

    def _finish(self, *, keep: bool) -> None:
        """The last step ends setup: kept, its answer is saved and a power reading seeds the Look tier;
        skipped, the look it opened with comes back."""
        answer = None
        if keep:
            problem = self._problem()
            if problem:
                self._problem_text = problem
                self._skip_open = False
                self.changed.emit()
                return
            answer = self._answer()
            self._absorb(answer)
            self._look_touched = False
            if self._power() and self._settings is not None:
                self._settings.seed_look_tier("all")
        else:
            self._restore_look()
        self._window._setup_step_left(self._step, self._step, answer)  # type: ignore[attr-defined]
        self._window._finish_setup()  # type: ignore[attr-defined]

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
            if self._step == WEEK and answer is not None:
                # Cancel stays on this page: nothing typed is kept, and the week-start file is not
                # written, until the student answers.
                choice = self._window.confirm_standing(answer["blocks"])  # type: ignore[attr-defined]
                if choice is None:
                    return
                answer["edited"] = choice
                save_week_starts_on(self._week_start)
        elif self._step == WEEK:
            self._clock_24h = (self._state.preferences.get("clock_24h") is True) if self._state else False
            self._apply_clock()
        if answer is not None:
            self._absorb(answer)
        self._window._setup_step_left(self._step, destination, answer)  # type: ignore[attr-defined]
        self._show(destination)

    def _show(self, step: int) -> None:
        self._step = step
        self._furthest = max(self._furthest, step)
        self._problem_text = ""
        self._skip_open = False
        self._apply_clock()
        self.changed.emit()

    def _after(self) -> int:
        return min(self._step + 1, MATERIAL_LAST)

    def _before(self) -> int:
        return max(self._step - 1, WEEK)

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

    @staticmethod
    def _row(rows: list, index: int) -> dict | None:
        if 0 <= index < len(rows):
            return rows[index]
        return None
