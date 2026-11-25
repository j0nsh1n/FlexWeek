"""Settings for the Material shell.

QML calls the slots. Preferences go through NativeSession, the same ones the
Widgets settings write. The look file's material object is the preset, the
advanced draft, and the keyboard-shortcut switch. A control with nowhere to
save is not built; the flags below say which those are.
"""

from __future__ import annotations

import copy
from typing import Any

import flexweek_engine  # type: ignore[import-untyped]
from pydantic import ValidationError
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

from backend import clock as wall_clock
from backend.comfort import TIMER_PRESETS, snap_minutes
from backend.models import TimeBlock, WeekRequest, valid_spotify_url
from backend.slots import hhmm_to_minutes, minutes_to_hhmm
from desktop.native import feedback
from desktop.native.calendar import DAY_FULL, DAYS, SETUP_SCHOOL_ID, this_week_line
from desktop.native.fields import (
    WEEK_STARTS,
    save_week_starts_on,
    week_start_day,
    week_start_notice,
    week_starts_on,
)
from desktop.native.hours.geometry import DRAG_STEPS, drag_step
from desktop.native.material.bridge_alarms import MAX_ALARMS, alarm_rows
from desktop.native.material.bridge_hours import SchoolHours, StudyHours
from desktop.native.material.bridge_month import _ROLES, read_cells
from desktop.native.material.bridge_rows import Labels, Rows
from desktop.native.material.theme import (
    ACCENT_LABELS,
    ACCENT_LOCKED,
    ACCENTS,
    BLOCK_STYLES,
    CATEGORY_KEYS,
    CORNER_RANGE,
    DEFAULT_CONTRAST,
    DEFAULT_PRESET,
    FONT_LABELS,
    FONTS,
    HOUR_LINES,
    HOUR_RANGE,
    LOOK_TIERS,
    MOTION_SPEEDS,
    ONE_MODE,
    PAD_RANGE,
    PRESETS,
    SAVED_MODES,
    SCALE_RANGE,
    SETTINGS_NAV_DEFAULT,
    SETTINGS_NAV_RANGE,
    SHADOW_RANGE,
    _float_in,
    _hex,
    accented,
    advanced_default,
    advanced_overrides,
    dress_theme,
    export_document,
    hour_row_px,
    import_document,
    kept_material,
    mode_of,
    pack_material,
    read_accent,
    read_advanced,
    read_font,
    read_letter_keys,
    read_look_tier,
    read_material_choice,
    read_saved_material,
    read_settings_nav_width,
    read_shortcuts,
    reading_problems,
    resolved_mode,
    scheme,
    shown_font,
    store_material,
    theme_object,
)
from desktop.native.remind import reminder_lead_min
from desktop.native.reuse import AVAILABILITY_LIMIT, PROTECTED_KINDS
from desktop.native.settings_copy import (
    ALARM_NOTE,
    ALARM_TONE_LABELS,
    BLOCK_SONG_NOTE,
    DND_NOTE,
    DOT_WORDS,
    FOCUS_AUDIO_NOTE,
    NO_PROTECTED,
    NO_SCHOOL_DAYS,
    NO_SOUND,
    NO_STUDY_HOURS,
    PAIR_CLOSED,
    PAIR_ONCE,
    PLANNING_STYLES,
    PROTECTED_WORDS,
    RELAY_SENTENCE,
    SCHOOL_HOURS_NOTE,
    SPLIT_ROUNDED,
    SPOTIFY_LINK_HINT,
    SPOTIFY_TONE_REST,
    STUDY_HOURS_LINE,
    TRAY_NOTE,
    UNREACHABLE_WORDS,
    clock_warning_words,
    countdown_words,
    pair_problem,
    seen_words,
    sync_state,
    tries_words,
)
from desktop.native.sound import Bell
from desktop.native.spotify import SpotifyPlayer
from desktop.native.tones import FALLBACK, SOUNDS
from desktop.native.update import install_kind, offers_developer_builds
from desktop.native.version import CHANNEL, VERSION
from desktop.native.weekmodel import hhmm_text
from desktop.native.work_windows import PRESETS as WORK_PRESETS

_FIELDS = frozenset(flexweek_engine.preference_fields())
SECTIONS = ("look", "planning", "focus", "alerts", "computer", "sync")
PAIR_TTL_SECONDS = 300
SYNC_STATUS_LABELS: dict[str, tuple[str, str]] = {
    "synced": ("Synced", "ok"),
    "syncing": ("Syncing", "info"),
    "problem": ("Not synced", "error"),
    "idle": ("Not synced", "warn"),
    "off": ("Not linked", "muted"),
}
CUTOFFS = ("20:00", "20:30", "21:00", "21:30", "22:00", "22:30", "23:00")
REMINDERS = ("off", "5", "10", "15")
# Minutes before a block that a reminder may fire: the Widgets spinner's range, one minute a step.
LEAD_MAX = 120
# How often an open pairing code's countdown and tries are read again.
PAIR_TICK_MS = 1000
REMINDER_CHIPS = (
    {"label": "Off", "value": "off"},
    {"label": "5m", "value": "5"},
    {"label": "10m", "value": "10"},
    {"label": "15m", "value": "15"},
)
AUDIO = (
    ("Off", "off"),
    ("Rain", "rain"),
    ("Lo-Fi", "lo-fi"),
    ("White noise", "white-noise"),
    ("Spotify", "spotify"),
)
AUDIO_VALUES = {value for _label, value in AUDIO}
TONES = tuple({"label": ALARM_TONE_LABELS.get(name, name.title()), "value": name} for name in SOUNDS)
# (key, saved field, smallest, largest) of the focus timer's lengths, in minutes. The ranges are the
# backend's (Preferences).
TIMER_LENGTHS = {
    "work": ("timer_work_min", 1, 180),
    "break": ("timer_break_min", 1, 60),
    "long": ("timer_long_break_min", 1, 120),
    "every": ("timer_long_break_every", 2, 12),
}
TIMER_CHOICES = (
    *({"label": item["label"], "value": item["id"]} for item in TIMER_PRESETS),
    {"label": "Custom", "value": "custom"},
)
SAVE_REFUSED = "Could not save that."
# Open on: the four screens FlexWeek can start on. Nothing saved opens on the week.
OPEN_ON = (
    {"label": "Week", "value": "week"},
    {"label": "Day", "value": "day"},
    {"label": "Month", "value": "month"},
    {"label": "My day", "value": "myday"},
)
OPEN_ON_VALUES = {item["value"] for item in OPEN_ON}
ANIMATIONS = (
    {"label": "Off", "value": "off"},
    {"label": "Reduce", "value": "reduce"},
    {"label": "Normal", "value": "normal"},
    {"label": "More", "value": "extra"},
)
ANIMATION_VALUES = {item["value"] for item in ANIMATIONS}
PLANNING_VALUES = {value for value, _label, _note in PLANNING_STYLES}
# The planner lane names these. The first one that exists on Preferences is the one we write.
_WEEKEND_FREE = next(
    (
        name
        for name in (
            "weekend_homework_free",
            "weekends_homework_free",
            "keep_weekends_free",
            "weekend_free",
        )
        if name in _FIELDS
    ),
    None,
)
_BUFFER = next((name for name in ("buffer_min", "smart_buffer_min") if name in _FIELDS), None)
_URGENT = next((name for name in ("urgent_first", "prioritize_urgent") if name in _FIELDS), None)
# auto_split_pomodoro is the focus-timer split, not this planner row.
_SPLIT = "split_long_tasks" if "split_long_tasks" in _FIELDS else None
_SHOW_WEEKENDS = "show_weekends" if "show_weekends" in _FIELDS else None
TEXT_SIZES = {"small": 0.9, "normal": 1.0, "large": 1.3, "larger": 1.6}
# Sharp and pill are the two ends of the corner dial; rounded leaves it on the preset's own radius.
CORNER_SHAPES: dict[str, int | None] = {"sharp": 0, "rounded": None, "pill": CORNER_RANGE[1]}
DENSITY_CHOICES = ("comfortable", "compact")


def _corner_shape(corner: int | None) -> str:
    """The shape card a corner radius matches, or empty when a slider put it between."""
    for name, value in CORNER_SHAPES.items():
        if corner == value:
            return name
    return ""


_GROUPS = {
    "shape": ("corner",),
    "density": ("hour", "padding", "rail"),
    "type": ("scale",),
    "motion": ("motion",),
    "depth": ("shadow",),
    "calendar": ("block", "lines", "now", "today", "times", "lengths", "cat"),
}


def _prefs_of(window: QObject) -> dict[str, Any]:
    raw = getattr(getattr(window, "session", None), "preferences", None)
    return raw if isinstance(raw, dict) else {}


def _reminder_state(prefs: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    """Off/5/10/15 for a new pick. A legal saved lead that is not one of those stays visible."""
    chips = [dict(row) for row in REMINDER_CHIPS]
    try:
        lead = int(prefs["reminder_lead_min"]) if prefs.get("reminder_lead_min") is not None else None
    except TypeError, ValueError:
        lead = None
    if prefs.get("reminders_enabled", True) is False:
        return "off", chips
    if lead in (5, 10, 15):
        return str(lead), chips
    if lead is not None and 0 <= lead <= 120:
        chips.append({"label": f"{lead}m", "value": str(lead)})
        return str(lead), chips
    return "", chips


def _timer_state(prefs: dict[str, Any], custom_open: bool) -> dict[str, Any]:
    """The focus timer as the page shows it: which of Short, Standard and Long the saved lengths are, or
    Custom, and each length with the slider's smallest value and step (15 while splitting)."""
    defaults = {"work": 30, "break": 15, "long": 30, "every": 4}
    values = {key: int(prefs.get(field) or defaults[key]) for key, (field, _lo, _hi) in TIMER_LENGTHS.items()}
    chosen = "custom"
    for item in TIMER_PRESETS:
        if (
            item["timer_work_min"] == values["work"]
            and item["timer_break_min"] == values["break"]
            and item["timer_long_break_min"] == values["long"]
            and item["timer_long_break_every"] == values["every"]
        ):
            chosen = str(item["id"])
            break
    if custom_open:
        chosen = "custom"
    split = prefs.get("auto_split_pomodoro") is True
    return {
        "timerPreset": chosen,
        "timerChoices": list(TIMER_CHOICES),
        "timerWork": values["work"],
        "timerBreak": values["break"],
        "timerLong": values["long"],
        "timerEvery": values["every"],
        "timerStep": 15 if split else 1,
        "timerFrom": 15 if split else 1,
    }


class PassiveWeekBridge(QObject):
    """Passive read-only week projection for the settings preview."""

    changed = Signal()
    homeworkChanged = Signal()

    def __init__(self, live: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("passiveWeekBridge")
        self._live = live
        live.changed.connect(self.changed)
        live.homeworkChanged.connect(self.homeworkChanged)

    @Property(int, notify=changed)
    def columns(self) -> int:
        return int(self._live.columns)  # type: ignore[attr-defined]

    @Property(int, notify=homeworkChanged)
    def homeworkCount(self) -> int:
        return int(self._live.homeworkCount)  # type: ignore[attr-defined]

    @Property(QObject, constant=True)
    def homework(self) -> QObject:
        return self._live.homework  # type: ignore[attr-defined]

    @Slot()
    def toggleWeekends(self) -> None:
        pass

    @Slot(str, int, int)
    def placeHomework(self, block_id: str, day: int, minute: int) -> None:
        pass

    @Slot()
    def plan(self) -> None:
        pass

    @Slot(str)
    def planOne(self, assignment_id: str) -> None:
        pass

    @Slot(str)
    def toggleDone(self, assignment_id: str) -> None:
        pass


class PassiveDayBridge(QObject):
    """Passive read-only day board projection for the settings preview.

    Forwards read-only presentation properties and models from the day screen
    while isolating all action slots (navigation, focus, homework completion)
    so preview interaction cannot mutate live session or planner state.
    """

    changed = Signal()
    dateOpened = Signal()

    def __init__(self, live: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("passiveDayBridge")
        self._live = live
        live.changed.connect(self.changed)
        opened = getattr(live, "dateOpened", None)
        if opened is not None and hasattr(opened, "connect"):
            opened.connect(self.dateOpened)

    @Property(str, notify=changed)
    def leftLine(self) -> str:
        return str(self._live.leftLine)  # type: ignore[attr-defined]

    @Property(bool, notify=changed)
    def waiting(self) -> bool:
        return bool(self._live.waiting)  # type: ignore[attr-defined]

    @Property(str, notify=changed)
    def loadError(self) -> str:
        return str(self._live.loadError)  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def leftCount(self) -> int:
        return int(self._live.leftCount)  # type: ignore[attr-defined]

    @Property(bool, notify=changed)
    def showNow(self) -> bool:
        return bool(self._live.showNow)  # type: ignore[attr-defined]

    @Property(str, notify=changed)
    def nowTitle(self) -> str:
        return str(self._live.nowTitle)  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def nowMinutes(self) -> int:
        return int(self._live.nowMinutes)  # type: ignore[attr-defined]

    @Property(str, notify=changed)
    def nowLine(self) -> str:
        return str(self._live.nowLine)  # type: ignore[attr-defined]

    @Property(bool, notify=changed)
    def nowBusy(self) -> bool:
        return bool(self._live.nowBusy)  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def ringCount(self) -> int:
        return int(self._live.ringCount)  # type: ignore[attr-defined]

    @Property(str, notify=changed)
    def ringCaption(self) -> str:
        return str(self._live.ringCaption)  # type: ignore[attr-defined]

    @Property(float, notify=changed)
    def ringShare(self) -> float:
        return float(self._live.ringShare)  # type: ignore[attr-defined]

    @Property(QObject, constant=True)
    def upNext(self) -> QObject:
        return self._live.upNext  # type: ignore[attr-defined]

    @Property(QObject, constant=True)
    def doneRows(self) -> QObject:
        return self._live.doneRows  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def year(self) -> int:
        return int(self._live.year)  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def month(self) -> int:
        return int(self._live.month)  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def miniDay(self) -> int:
        return int(self._live.miniDay)  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def dayIndex(self) -> int:
        return int(self._live.dayIndex)  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def openingMinute(self) -> int:
        return int(self._live.openingMinute)  # type: ignore[attr-defined]

    @Property(str, notify=changed)
    def iso(self) -> str:
        return str(self._live.iso)  # type: ignore[attr-defined]

    @Property(QObject, constant=True)
    def blocks(self) -> QObject:
        return self._live.blocks  # type: ignore[attr-defined]

    @Slot()
    def previousDay(self) -> None:
        pass

    @Slot()
    def nextDay(self) -> None:
        pass

    @Slot(int)
    def pickDay(self, day: int) -> None:
        pass

    @Slot()
    def startFocus(self) -> None:
        pass

    @Slot(str)
    def finishHomework(self, assignment_id: str) -> None:
        pass


class PassiveMonthBridge(QObject):
    """Passive read-only month projection for the settings preview.

    Forwards read-only calendar models and presentation properties while isolating
    all action slots from mutating the live planner or session navigation.
    On cold entry where no live month has been opened, initializes a passive
    calendar projection so populated dates and headers render without altering
    live session state.
    """

    changed = Signal()

    def __init__(self, live: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("passiveMonthBridge")
        self._live = live
        self._cell_rows: list[dict[str, Any]] = []
        self._weekday_names: list[str] = []
        self._dates = Rows(_ROLES, self)
        self._weekdays = Labels(self)
        self._lines = Labels(self)
        self._selected = ""
        self._heading = ""

        # Lifecycle, account ownership, and request tracking
        self._account_id: str | None = None
        self._snapshot_month: str | None = None
        self._preview_snapshot: dict | None = None
        self._asked_month = ""
        self._failed_month: str | None = None
        self._load_error = ""
        self._loading = False
        self._request_counter = 0
        self._request_token: tuple[str, str, int, int] | None = None

        live.changed.connect(self._on_live_changed)
        session = self._session()
        self._month_gen = getattr(session, "_month_gen", 0) if session is not None else 0
        changed = getattr(session, "week_changed", None)
        if changed is not None and hasattr(changed, "connect"):
            changed.connect(self._on_week_changed)
        acct_changed = getattr(session, "account_changed", None)
        if acct_changed is not None and hasattr(acct_changed, "connect"):
            acct_changed.connect(self._on_account_changed)

        if self._is_preview_active():
            self.reload(fetch=True)
        else:
            self.reload(fetch=False)

    def _session(self) -> Any:
        return getattr(self._live, "_session", lambda: None)()

    def _is_preview_active(self) -> bool:
        parent = self.parent()
        settings = getattr(parent, "_settings", None)
        if settings is None:
            return True
        page = getattr(settings, "_page", "")
        view = getattr(settings, "_preview_view", "")
        # print("IS_ACTIVE_CHECK", "page=", page, "view=", view)
        return bool(page == "advanced" and view == "month")

    def _target_month(self) -> str:
        session = self._session()
        if session is None:
            return ""
        target = getattr(session, "selected_month", None)
        if not target:
            today_iso = getattr(session, "today_iso", lambda: "")()
            target = today_iso[:7] if today_iso else ""
        return target or ""

    def clear(self) -> None:
        """Immediately clear all preview content, snapshots, and in-flight requests."""
        self._account_id = None
        self._snapshot_month = None
        self._preview_snapshot = None
        self._request_counter += 1
        self._request_token = None
        self._loading = False
        self._load_error = ""
        self._failed_month = None
        self._asked_month = ""
        self._selected = ""
        self._heading = ""
        if self._cell_rows:
            self._cell_rows = []
            self._dates.set_rows([])
        if self._weekday_names:
            self._weekday_names = []
            self._weekdays.set_rows([])
        self.changed.emit()

    def _on_live_changed(self) -> None:
        session = self._session()
        if session is None or getattr(session, "account", None) is None:
            self.clear()
            return
        self.reload(fetch=self._is_preview_active())

    def _on_week_changed(self) -> None:
        session = self._session()
        if session is None or getattr(session, "account", None) is None:
            self.clear()
            return
        current_gen = getattr(session, "_month_gen", 0)
        if current_gen != self._month_gen:
            self._month_gen = current_gen
            self._preview_snapshot = None
            self._snapshot_month = None
            self._asked_month = ""
            self._failed_month = None
            self._load_error = ""
            self._request_counter += 1
            self._request_token = (
                self._account_id or "",
                self._target_month(),
                self._request_counter,
                current_gen,
            )
        elif not self._is_preview_active():
            self._preview_snapshot = None
            self._asked_month = ""
        self.reload(fetch=self._is_preview_active())

    def _on_account_changed(self, account: Any = None) -> None:
        if account is None:
            self.clear()
            return
        new_id = str(account.get("id") if isinstance(account, dict) else getattr(account, "id", ""))
        if self._account_id is not None and self._account_id != new_id:
            self.clear()
        self.reload(fetch=self._is_preview_active())

    def activate_preview(self) -> None:
        """Called when Settings opens Advanced Month preview. Resets failed state for bounded retry."""
        self._failed_month = None
        self._load_error = ""
        self._asked_month = ""
        self.reload(fetch=True)

    @Slot()
    def retry(self) -> None:
        """Explicit user retry for failed month load."""
        self.activate_preview()

    def reload(self, fetch: bool = True) -> None:
        session = self._session()
        if session is None:
            self.clear()
            return

        account = getattr(session, "account", None)
        if account is None:
            self.clear()
            return

        account_id = str(account.get("id"))
        if self._account_id is not None and self._account_id != account_id:
            self.clear()
        self._account_id = account_id

        target_month = self._target_month()
        if not target_month:
            self.clear()
            return

        # Drop snapshot if month does not match
        if self._snapshot_month is not None and self._snapshot_month != target_month:
            self._preview_snapshot = None
            self._snapshot_month = None
            self._asked_month = ""
            self._failed_month = None

        snapshot = self._preview_snapshot
        if snapshot is None and getattr(session, "selected_month", None) == target_month:
            live_snapshot = getattr(session, "month_data", None)
            current_gen = getattr(session, "_month_gen", 0)
            live_gen = getattr(session, "_month_data_gen", None)
            gen_ok = live_gen is None or live_gen == current_gen
            if gen_ok and isinstance(live_snapshot, dict) and live_snapshot.get("month") == target_month:
                snapshot = live_snapshot
                self._preview_snapshot = snapshot
                self._snapshot_month = target_month
                self._load_error = ""
                self._failed_month = None

        if snapshot is None:
            cache = getattr(session, "_month_cache", None)
            if isinstance(cache, dict):
                cached = cache.get((account_id, target_month))
                if isinstance(cached, dict) and cached.get("month") == target_month:
                    snapshot = cached
                    self._preview_snapshot = snapshot
                    self._snapshot_month = target_month
                    self._load_error = ""
                    self._failed_month = None

        client = getattr(session, "client", None)
        can_fetch = (
            fetch
            and snapshot is None
            and client is not None
            and hasattr(client, "request")
            and self._is_preview_active()
            and self._asked_month != target_month
            and self._failed_month != target_month
        )

        if can_fetch:
            self._asked_month = target_month
            self._request_counter += 1
            gen = getattr(session, "_month_gen", 0)
            token = (account_id, target_month, self._request_counter, gen)
            self._request_token = token
            self._loading = True
            self._load_error = ""

            def is_stale(current_session: Any) -> bool:
                if token != self._request_token:
                    return True
                return bool(
                    current_session is not None and getattr(current_session, "_month_gen", 0) != token[3]
                )

            def ok(data: dict) -> None:
                current_session = self._session()
                if is_stale(current_session):
                    return
                if current_session is None:
                    self._loading = False
                    self.changed.emit()
                    return
                current_account = getattr(current_session, "account", None)
                if current_account is None or str(current_account.get("id")) != account_id:
                    self._loading = False
                    self.changed.emit()
                    return
                if not isinstance(data, dict) or data.get("month") != target_month:
                    self._loading = False
                    self.changed.emit()
                    return
                self._preview_snapshot = data
                self._snapshot_month = target_month
                self._loading = False
                self._load_error = ""
                self._failed_month = None
                self.reload(fetch=False)

            def err(error: Any) -> None:
                current_session = self._session()
                if is_stale(current_session):
                    return
                if current_session is None:
                    self._loading = False
                    self.changed.emit()
                    return
                current_account = getattr(current_session, "account", None)
                if current_account is None or str(current_account.get("id")) != account_id:
                    self._loading = False
                    self.changed.emit()
                    return
                if self._target_month() != target_month:
                    self._loading = False
                    self.changed.emit()
                    return
                self._loading = False
                self._load_error = getattr(error, "message", "Couldn't load month preview.")
                self._failed_month = target_month
                self.changed.emit()

            # A Monday start asks as it always did; the server's first day is Monday when none is named.
            first = week_start_day()
            asked = f"/api/month?month={target_month}" + (f"&first_day={first}" if first else "")
            client.request("GET", asked, None, ok, err)

        rows, names = read_cells(session, month=target_month, snapshot=snapshot)
        if rows != self._cell_rows:
            self._cell_rows = rows
            self._dates.set_rows([{key: row[key] for key in _ROLES} for row in rows])
        if names != self._weekday_names:
            self._weekday_names = names
            self._weekdays.set_rows(names)
        self.changed.emit()

    @Property(QObject, constant=True)
    def dates(self) -> QObject:
        return self._dates

    @Property(QObject, constant=True)
    def weekdays(self) -> QObject:
        return self._weekdays

    @Property(QObject, constant=True)
    def lines(self) -> QObject:
        return self._lines

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def cellRows(self) -> list:
        return list(self._cell_rows)

    @Property(str, notify=changed)
    def selectedIso(self) -> str:
        return self._selected

    @Property(str, notify=changed)
    def heading(self) -> str:
        return self._heading

    @Property(bool, notify=changed)
    def barOpen(self) -> bool:
        return bool(self._selected)

    @Property(bool, notify=changed)
    def showStudyTime(self) -> bool:
        return bool(getattr(self._live, "showStudyTime", False))

    @Property(str, constant=True)
    def studyLabel(self) -> str:
        return str(getattr(self._live, "studyLabel", "Study time"))

    @Property(bool, notify=changed)
    def loading(self) -> bool:
        return self._loading

    @Property(str, notify=changed)
    def loadError(self) -> str:
        return self._load_error

    @Property(str, notify=changed)
    def error(self) -> str:
        return self._load_error

    @Property(bool, notify=changed)
    def ready(self) -> bool:
        return self._preview_snapshot is not None

    @Slot(str)
    def selectDate(self, iso: str) -> None:
        pass

    @Slot()
    def closeDate(self) -> None:
        pass

    @Slot()
    def openDay(self) -> None:
        pass

    @Slot()
    def previousMonth(self) -> None:
        pass

    @Slot()
    def nextMonth(self) -> None:
        pass

    @Slot(bool)
    def setShowStudyTime(self, on: bool) -> None:
        pass

    @Slot(str)
    def toggleDone(self, block_id: str) -> None:
        pass


class PreviewBridge(QObject):
    """The live week, with the draft's row height and colours, for the advanced page only."""

    changed = Signal()
    blocksChanged = Signal()
    homeworkChanged = Signal()

    def __init__(self, material: QObject, settings: SettingsBridge) -> None:
        super().__init__(settings)
        self.setObjectName("previewBridge")
        self._material = material
        self._settings = settings
        week = material._week  # type: ignore[attr-defined]
        week.changed.connect(self.changed)
        week.blocksChanged.connect(self.blocksChanged)
        week.homeworkChanged.connect(self.homeworkChanged)
        self._passive_week = PassiveWeekBridge(week, self)
        self._passive_day = PassiveDayBridge(material.day, self)  # type: ignore[attr-defined]
        self._passive_month = PassiveMonthBridge(material.month, self)  # type: ignore[attr-defined]

    def _week(self) -> QObject:
        return self._material._week  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def hourRow(self) -> int:
        panel = self._settings
        return hour_row_px(panel._draft_choice["density"], panel._draft)

    @Property(int, notify=changed)
    def dayHourRow(self) -> int:
        return int(self.hourRow)

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def theme(self) -> dict[str, Any]:
        return self._settings._draft_theme

    @Property(QObject, constant=True)
    def week(self) -> QObject:
        return self._passive_week

    @Property(QObject, constant=True)
    def days(self) -> QObject:
        return self._week().days  # type: ignore[attr-defined]

    @Property(QObject, constant=True)
    def hours(self) -> QObject:
        return self._week().hours  # type: ignore[attr-defined]

    @Property(QObject, constant=True)
    def blocks(self) -> QObject:
        return self._week().blocks  # type: ignore[attr-defined]

    @Property(QObject, constant=True)
    def homework(self) -> QObject:
        return self._week().homework  # type: ignore[attr-defined]

    @Property("QVariantList", notify=blocksChanged)  # type: ignore[arg-type]
    def blockRows(self) -> list[Any]:
        return self._week().blockRows  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def nowDay(self) -> int:
        return int(self._week().nowDay)  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def nowColumn(self) -> int:
        return int(self._week().nowColumn)  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def nowMinute(self) -> int:
        return int(self._week().nowMinute)  # type: ignore[attr-defined]

    @Property(int, notify=homeworkChanged)
    def homeworkCount(self) -> int:
        return int(self._week().homeworkCount)  # type: ignore[attr-defined]

    @Property(QObject, constant=True)
    def day(self) -> QObject:
        return self._passive_day

    @Property(QObject, constant=True)
    def month(self) -> QObject:
        return self._passive_month

    @Property(str, notify=changed)
    def density(self) -> str:
        return str(self._settings._draft_choice.get("density", "comfortable"))

    @Property(bool, notify=changed)
    def highContrast(self) -> bool:
        return self._settings._draft_choice.get("contrast") == "high"

    @Property(bool, notify=changed)
    def reduceMotion(self) -> bool:
        return True

    @Property(int, notify=changed)
    def daySideWidth(self) -> int:
        return int(getattr(self._material, "daySideWidth", 312))

    @Slot(int)
    def setDaySideWidth(self, width: int) -> None:
        pass


class SettingsBridge(QObject):
    """The five sections, and the advanced page that stays a draft until Done."""

    changed = Signal()

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("settingsBridge")
        self._bridge = parent
        self._window = parent._window  # type: ignore[attr-defined]
        self._section = "look"
        self._page = "sections"
        self._choice = read_material_choice(None)
        self._advanced = advanced_default()
        self._draft_choice = dict(self._choice)
        self._draft = copy.deepcopy(self._advanced)
        self._shortcuts = True
        self._letter_keys = False
        self._font = ""
        self._tier = ""
        self._nav_width = SETTINGS_NAV_DEFAULT
        self._saved: list[dict[str, Any]] = []
        self._study = StudyHours()
        self._school = SchoolHours()
        self._timer_custom = False
        self._timer_note = ""
        self._bell = Bell(self)
        self._spotify_player = SpotifyPlayer(self)
        self._dirty = False
        self._prompt = ""
        self._notice = ""
        self._spotify_error = ""
        self._import_error = ""
        self._save_error = ""
        self._pair_code = ""
        self._pair_error = ""
        self._pair_open = False
        self._pair_seconds = PAIR_TTL_SECONDS
        self._pair_tries = 3
        self._pair_copied = False
        self._pair_copy_reset = QTimer(self)
        self._pair_copy_reset.setSingleShot(True)
        self._pair_copy_reset.setInterval(2000)
        self._pair_copy_reset.timeout.connect(self._clear_pair_copied)
        # While a code is open: how long it lasts and the tries left, read once a second as the old
        # pairing sheet did.
        self._pair_status = ""
        self._pair_watch = QTimer(self)
        self._pair_watch.setInterval(PAIR_TICK_MS)
        self._pair_watch.timeout.connect(self._pair_tick)
        self._sync_busy = False
        self._clock_warning = ""
        self._sync_problem = ""
        self._remove_ask: dict[str, str] = {}
        self._export_text = ""
        self._ask_preset = False
        self._pending_preset = ""
        # Choices sent to the server and not yet answered. They show at once, so a second arrow key steps on
        # from the first instead of from the old saved value.
        self._unsaved: dict[str, Any] = {}
        self._preview_fit = "Fit"
        self._preview_view = "week"
        self._draft_theme: dict[str, Any] = {}
        self._state: dict[str, Any] = {}
        self._preview = PreviewBridge(parent, self)
        session = getattr(self._window, "session", None)
        signal = getattr(session, "week_changed", None)
        if signal is not None:
            signal.connect(self._on_session)
        week_start_notice().changed.connect(self._on_week_start)
        # The phone list and the sync dot change on the window's own clock, so This computer is read again
        # every few seconds while it is the page on view.
        self._phones_seen: tuple = ()
        self._watch = QTimer(self)
        self._watch.setInterval(2000)
        self._watch.timeout.connect(self._watch_phones)
        self._watch.start()
        self._load_applied(keep_draft=False)

    def _watch_phones(self) -> None:
        if self._section != "sync" or self._bridge.screen != "settings":  # type: ignore[attr-defined]
            return
        seen = (self._phone_rows(), self._sync_words())
        if seen != self._phones_seen:
            self._publish()

    def _clear_pair_copied(self) -> None:
        if self._pair_copied:
            self._pair_copied = False
            self._publish()

    def note_applied(self) -> None:
        """The shell re-read the look file. Keep a draft the student is still editing."""
        self._load_applied(keep_draft=self._dirty)

    def _load_applied(self, *, keep_draft: bool) -> None:
        stored = self._bridge._stored_look()  # type: ignore[attr-defined]
        self._choice = read_material_choice(stored)
        self._advanced = read_advanced(stored)
        self._shortcuts = read_shortcuts(stored)
        self._letter_keys = read_letter_keys(stored)
        self._font = read_font(stored)
        self._tier = read_look_tier(stored)
        self._nav_width = read_settings_nav_width(stored)
        self._saved = read_saved_material(stored)
        if not keep_draft:
            self._draft_choice = dict(self._choice)
            self._draft = copy.deepcopy(self._advanced)
            self._dirty = False
        self._publish()

    def _on_session(self) -> None:
        try:
            self._publish()
        except OSError, KeyError, ValueError:
            return

    def _worn_dark(self) -> bool:
        from desktop.native.material.host import appearance_of

        mode, _contrast = appearance_of(self._window)
        return mode == "dark"

    def _colours(self, choice: dict[str, str]) -> dict[str, str]:
        mode = mode_of(choice, self._worn_dark())
        try:
            colours = scheme(choice["preset"], mode, choice["contrast"])
            return accented(
                colours, read_accent(_prefs_of(self._window)), choice["preset"], mode, choice["contrast"]
            )
        except KeyError, ValueError, OSError:
            try:
                return scheme(DEFAULT_PRESET, "light", DEFAULT_CONTRAST)
            except KeyError, ValueError, OSError:
                return {}

    def _mark_draft(self) -> None:
        self._dirty = True
        self._notice = ""
        self._publish()

    def _publish(self) -> None:
        self._draft_theme = self._make_theme(self._draft_choice, self._draft)
        self._state = self._build()
        self.changed.emit()
        self._preview.changed.emit()

    def _make_theme(self, choice: dict[str, str], advanced: dict[str, Any]) -> dict[str, Any]:
        colours = self._colours(choice)
        if not colours:
            return dict(self._draft_theme or {})
        reduced = advanced.get("motion") == "Off" or bool(self._bridge.reduceMotion)  # type: ignore[attr-defined]
        chips = _prefs_of(self._window).get("accent_chips") is True
        base = theme_object(colours, choice["density"], reduced, choice["contrast"] == "high", chips)
        return dress_theme(base, advanced, choice["preset"], self._font)

    def _build(self) -> dict[str, Any]:
        prefs = {**_prefs_of(self._window), **self._unsaved}
        draft = self._draft
        choice = self._draft_choice
        worn = self._worn_dark()
        swatches = []
        for name in PRESETS:
            try:
                colours = scheme(name, resolved_mode(self._choice["mode"], worn), self._choice["contrast"])
            except KeyError:
                continue
            swatches.append(
                {
                    "name": name,
                    "primary": colours["primary"],
                    "tertiary": colours["tertiary"],
                    "secondaryContainer": colours["secondaryContainer"],
                    "primaryContainer": colours["primaryContainer"],
                }
            )
        reminder, reminder_choices = _reminder_state(prefs)
        if not self._study.dirty:
            self._study.load(prefs)
        if not self._school.dirty:
            self._school.load(self._school_block())
        timer = _timer_state(prefs, self._timer_custom)
        accent = read_accent(prefs)
        preset = self._choice["preset"]
        audio = prefs.get("focus_audio") or "off"
        cutoff = prefs.get("day_cutoff") or ""
        motion = prefs.get("motion")
        open_on = prefs.get("preferred_view")
        phones = self._phone_names()
        phone_rows = self._phone_rows()
        sync_words = self._sync_words()
        sync_key = self._sync_status_key(bool(phone_rows))
        sync_word, sync_tone = SYNC_STATUS_LABELS.get(sync_key, ("Not linked", "muted"))
        self._phones_seen = (phone_rows, sync_words)
        problems = self._problem_rows()
        return {
            "section": self._section,
            "page": self._page,
            "navWidth": self._nav_width,
            "preset": self._choice["preset"],
            "mode": self._choice["mode"],
            "contrast": self._choice["contrast"],
            "density": self._choice["density"],
            "draftPreset": choice["preset"],
            "draftMode": choice["mode"],
            "draftContrast": choice["contrast"],
            "draftDensity": choice["density"],
            "swatches": swatches,
            "clock24": prefs.get("clock_24h") is True,
            "focusAudio": audio if audio in AUDIO_VALUES else "off",
            "spotify": prefs.get("default_spotify_url") or "",
            "spotifyError": self._spotify_error,
            "reminder": reminder,
            "reminderChoices": reminder_choices,
            "reminderLead": reminder_lead_min(prefs),
            "reminderLeadMax": LEAD_MAX,
            **timer,
            "timerNote": self._timer_note,
            "autoSplit": prefs.get("auto_split_pomodoro") is True,
            "autoComplete": prefs.get("focus_auto_complete") is True,
            "autoMute": prefs.get("focus_auto_mute", True) is not False,
            "reminderSound": prefs.get("reminder_sound", True) is not False,
            "tone": prefs.get("alarm_tone") or FALLBACK,
            "alarms": alarm_rows(list(prefs.get("alarms") or [])),
            "alarmsFull": len(prefs.get("alarms") or []) >= MAX_ALARMS,
            "alarmNote": ALARM_NOTE,
            "toneChoices": list(TONES),
            "toneNote": prefs.get("alarm_tone") == "spotify",
            "dnd": prefs.get("reminder_dnd_override") is True,
            "volume": int(prefs.get("alert_volume", 80)),
            "endChime": prefs.get("end_chime") is True,
            "tray": prefs.get("tray_notifications", True) is not False,
            "accent": accent,
            "accentChoices": [{"label": ACCENT_LABELS[name], "value": name} for name in ACCENTS],
            "accentLocked": preset in ACCENT_LOCKED,
            "accentChips": prefs.get("accent_chips") is True,
            "font": shown_font(preset, self._font),
            "fontChoices": [{"label": FONT_LABELS[name], "value": name} for name in FONTS],
            "oneMode": ONE_MODE.get(preset, ""),
            "workWindows": self._study.window_rows(),
            "workPresets": [{"name": name} for name, *_rest in WORK_PRESETS],
            "protectedWindows": self._study.protected_view(),
            "studyDirty": self._study.dirty,
            "studyError": self._study.error,
            "schoolDays": list(self._school.days),
            "schoolStart": hhmm_text(self._school.start),
            "schoolEnd": hhmm_text(self._school.end),
            "schoolDirty": self._school.dirty,
            "schoolError": self._school.error,
            "schoolExists": self._school.exists,
            "thisWeek": self._this_week(),
            "dayNames": [{"day": day, "short": DAYS[day], "full": DAY_FULL[day]} for day in range(7)],
            "protectedKinds": [{"label": PROTECTED_WORDS[kind], "value": kind} for kind in PROTECTED_KINDS],
            "dndNote": DND_NOTE,
            "trayNote": TRAY_NOTE,
            "blockSongNote": BLOCK_SONG_NOTE,
            "reminderLimits": self._reminder_limits(),
            "focusAudioNote": FOCUS_AUDIO_NOTE,
            "spotifyHint": SPOTIFY_LINK_HINT,
            "spotifyRest": SPOTIFY_TONE_REST,
            "studyNote": STUDY_HOURS_LINE,
            "schoolNote": SCHOOL_HOURS_NOTE,
            "noStudyHours": NO_STUDY_HOURS,
            "noProtected": NO_PROTECTED,
            "noSchoolDays": NO_SCHOOL_DAYS,
            "limit": AVAILABILITY_LIMIT,
            "split": bool(prefs.get(_SPLIT)) if _SPLIT else False,
            "cutoff": cutoff,
            "cutoffChoices": [
                {"label": "No limit", "value": ""},
                *(
                    {"label": hhmm_text(item), "value": item}
                    for item in sorted({*CUTOFFS, *([cutoff] if cutoff else [])})
                ),
            ],
            "buffer": (0 if prefs.get(_BUFFER) == 0 else int(prefs.get(_BUFFER) or 15)) if _BUFFER else 15,
            "dragStep": drag_step(prefs.get("drag_step_min")),
            "weekStart": week_starts_on(),
            "urgent": bool(prefs.get(_URGENT, True)) if _URGENT else False,
            "weekendFree": bool(prefs.get(_WEEKEND_FREE)) if _WEEKEND_FREE else False,
            "showWeekends": bool(prefs.get(_SHOW_WEEKENDS, True)) if _SHOW_WEEKENDS else True,
            "startAtLogin": prefs.get("start_at_login") is True,
            "reduceMotion": motion in ("reduce", "off"),
            "animations": motion if motion in ANIMATION_VALUES else "normal",
            "animationChoices": list(ANIMATIONS),
            "openOn": open_on if open_on in OPEN_ON_VALUES else "week",
            "openOnChoices": list(OPEN_ON),
            "showOpenOn": "preferred_view" in _FIELDS,
            "planningStyle": prefs.get("planning_style") or "suggest",
            "planningStyleChoices": [
                {"value": value, "label": label, "note": note} for value, label, note in PLANNING_STYLES
            ],
            "showPlanningStyle": "planning_style" in _FIELDS,
            "shortcuts": self._shortcuts,
            "letters": self._letter_keys,
            "developerBuilds": self._window._updates.get("developer_builds") is True,
            "developerBuildsOffered": offers_developer_builds(install_kind()),
            "feedbackAvailable": feedback.available(),
            "version": (
                f"FlexWeek {VERSION} (developer build)" if CHANNEL == "dev" else f"FlexWeek {VERSION}"
            ),
            "pairCode": self._pair_code,
            "pairStatus": self._pair_status,
            "pairError": self._pair_error,
            "pairOpen": self._pair_open and bool(self._pair_code),
            "pairSeconds": self._pair_seconds,
            "pairFraction": max(0.0, min(1.0, self._pair_seconds / float(PAIR_TTL_SECONDS))),
            "pairTries": self._pair_tries,
            "pairCopied": self._pair_copied,
            "phones": phones,
            "phoneRows": phone_rows,
            "syncWords": sync_words,
            "syncStatusKey": sync_key,
            "syncStatusWord": sync_word,
            "syncStatusTone": sync_tone,
            "syncBusy": self._sync_busy,
            "canSync": self._sync_service() is not None and bool(phone_rows),
            "clockWarning": self._clock_warning,
            "syncProblem": self._sync_problem,
            "relayNote": RELAY_SENTENCE,
            "askRemove": bool(self._remove_ask),
            "removeName": self._remove_ask.get("name", ""),
            "showClock": "clock_24h" in _FIELDS,
            "showAudio": "focus_audio" in _FIELDS,
            "showSpotify": "default_spotify_url" in _FIELDS,
            "showReminder": "reminders_enabled" in _FIELDS and "reminder_lead_min" in _FIELDS,
            "showPomodoro": "timer_work_min" in _FIELDS and "timer_break_min" in _FIELDS,
            "showSplit": _SPLIT is not None,
            "showCutoff": "day_cutoff" in _FIELDS,
            "showBuffer": _BUFFER is not None,
            "showDragStep": "drag_step_min" in _FIELDS,
            "showUrgent": _URGENT is not None,
            "showWeekendFree": _WEEKEND_FREE is not None,
            "showWeekendsRow": _SHOW_WEEKENDS is not None,
            "showLogin": "start_at_login" in _FIELDS,
            "showMotion": "motion" in _FIELDS,
            "corner": 12 if draft["corner"] is None else draft["corner"],
            "hour": hour_row_px(choice["density"], draft),
            "padding": 6 if draft["padding"] is None else draft["padding"],
            "shadow": 0 if draft["shadow"] is None else draft["shadow"],
            "scale": draft["scale"],
            "tier": self._tier or "simple",
            "draftOneMode": ONE_MODE.get(choice["preset"], ""),
            "cornerShape": _corner_shape(draft["corner"]),
            "textSize": (
                "larger"
                if (draft.get("scale") or self._advanced.get("scale") or 1.0) >= 1.5
                else (
                    "large"
                    if (draft.get("scale") or self._advanced.get("scale") or 1.0) >= 1.2
                    else (
                        "small"
                        if (draft.get("scale") or self._advanced.get("scale") or 1.0) <= 0.92
                        else "normal"
                    )
                )
            ),
            "draftMotion": draft["motion"],
            "block": draft["block"],
            "lines": draft["lines"],
            "rail": draft["rail"],
            "today": draft["today"],
            "times": draft["times"],
            "lengths": draft["lengths"],
            "now": draft["now"] or "",
            "catSchool": (draft["cat"] or {}).get("school") or "",
            "catSports": (draft["cat"] or {}).get("sports") or "",
            "catStudy": (draft["cat"] or {}).get("study") or "",
            "catHomework": (draft["cat"] or {}).get("homework") or "",
            "problems": problems,
            "previewFit": self._preview_fit,
            "previewView": self._preview_view,
            "exportText": self._export_text,
            "importError": self._import_error,
            "saveError": self._save_error,
            "notice": self._notice,
            "prompt": self._prompt,
            "askPreset": self._ask_preset,
            "pendingPreset": self._pending_preset,
            "savedNames": [item["name"] for item in self._saved],
            "dirty": self._dirty,
        }

    def _reminder_limits(self) -> str:
        """The server's two reminder-limit sentences, as the Widgets Alerts page showed them."""
        found = getattr(getattr(self._window, "session", None), "reminder_limits", None)
        limits = found if isinstance(found, dict) else {}
        return " ".join(str(limits.get(key, "")) for key in ("spotify", "duplicate")).strip()

    def _problem_rows(self) -> list[dict[str, Any]]:
        mode = mode_of(self._draft_choice, self._worn_dark())
        return [
            {"words": item["words"], "role": item["role"], "ratio": item["ratio"]}
            for item in reading_problems(mode, self._draft)
        ]

    def _phone_names(self) -> list[str]:
        found = getattr(self._window, "_linked_phones", None)
        if not callable(found):
            return []
        try:
            rows = found() or []
        except Exception:
            return []
        names: list[str] = []
        for row in rows:
            if isinstance(row, dict):
                names.append(str(row.get("name") or "Phone"))
        return names

    def _sync_service(self) -> Any:
        host = getattr(self._window, "_sync_host", None)
        return getattr(host, "service", None)

    def _phone_rows(self) -> list[dict[str, str]]:
        """Each linked phone with when it last synced, as the Widgets Devices card said it."""
        found = getattr(self._window, "_linked_phones", None)
        if not callable(found):
            return []
        try:
            rows = found() or []
        except Exception:
            return []
        now_ms = int(self._window.session.now_ms())
        shown: list[dict[str, str]] = []
        for row in rows:
            if isinstance(row, dict):
                shown.append(
                    {
                        "id": str(row.get("device_id") or ""),
                        "name": str(row.get("name") or "Phone"),
                        "seen": seen_words(row.get("last_seen"), now_ms),
                    }
                )
        return shown

    def _sync_words(self) -> str:
        """The status the Widgets dot's tooltip gave: waiting, syncing, synced or could not reach."""
        service = getattr(self._window, "_sync", None)
        if service is None:
            return ""
        try:
            return DOT_WORDS[sync_state(service.status(), bool(self._phone_rows()))]
        except Exception:
            return ""

    def _sync_status_key(self, linked: bool) -> str:
        """Short sync status key for the single colored status word in Phone & sync."""
        if not linked:
            return "off"
        if self._sync_busy:
            return "syncing"
        if self._sync_problem:
            return "problem"
        service = getattr(self._window, "_sync", None)
        if service is None:
            return "idle"
        try:
            return sync_state(service.status(), linked)
        except Exception:
            return "idle"

    @Slot()
    def syncNow(self) -> None:
        if self._sync_service() is None or self._sync_busy:
            return
        self._sync_busy = True
        self._publish()
        self._window.session.sync_linked_phones(self._synced)

    def _synced(self, rows: list | None, problem: Exception | None) -> None:
        self._sync_busy = False
        if problem is not None:
            self._sync_problem = f"Sync failed: {problem}"
            self._clock_warning = ""
            self._publish()
            return
        skewed = sum(
            row[1].get("clock_skewed", 0) for row in rows or [] if row[1] is not None and row[2] is None
        )
        self._clock_warning = clock_warning_words(skewed)
        self._sync_problem = UNREACHABLE_WORDS if any(row[2] is not None for row in rows or []) else ""
        self._publish()

    @Slot(str)
    def askRemovePhone(self, device_id: str) -> None:
        row = next((item for item in self._phone_rows() if item["id"] == device_id), None)
        if row is None:
            return
        self._remove_ask = {"id": device_id, "name": row["name"]}
        self._publish()

    @Slot(str)
    def answerRemovePhone(self, choice: str) -> None:
        ask, self._remove_ask = self._remove_ask, {}
        if choice != "remove" or not ask:
            self._publish()
            return

        def gone(_answer: Any, problem: Exception | None) -> None:
            self._sync_problem = f"Could not remove {ask['name']}: {problem}" if problem is not None else ""
            self._window._sync_tick()  # type: ignore[attr-defined]
            self._publish()

        self._window.session.unlink_phone(ask["id"], gone)
        self._publish()

    def _write(self, updates: dict[str, Any], *, login: bool | None = None) -> None:
        session = self._window.session
        self._unsaved.update(updates)

        def settle() -> None:
            # A newer choice for the same setting is still on its way and keeps showing.
            for name, value in updates.items():
                if name in self._unsaved and self._unsaved[name] == value:
                    del self._unsaved[name]

        def then(ok: bool) -> None:
            settle()
            if ok:
                if login is not None:
                    self._window._apply_start_at_login(login)
                self._bridge.refresh()  # type: ignore[attr-defined]
                self._notice = ""
            else:
                self._notice = "Could not save that."
            self._publish()

        if not session.save_preferences(updates, then):
            settle()
            self._notice = "Could not save that."
        self._publish()

    def _commit(self) -> None:
        path = self._window._look_path()
        material = pack_material(
            self._choice,
            self._advanced,
            self._shortcuts,
            self._letter_keys,
            self._saved,
            self._font,
            self._tier,
            day_side_width=int(getattr(self._bridge, "daySideWidth", 312)),
            settings_nav_width=self._nav_width,
        )
        store_material(path, material)
        self._bridge._shortcuts = self._shortcuts  # type: ignore[attr-defined]
        self._bridge._letter_keys = self._letter_keys  # type: ignore[attr-defined]
        self._bridge.reload_material()  # type: ignore[attr-defined]

    def _set_choice(self, **parts: str) -> None:
        self._choice.update(parts)
        if not self._dirty:
            self._draft_choice.update(parts)
        self._notice = ""
        self._commit()

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def state(self) -> dict[str, Any]:
        return self._state

    @Property(str, notify=changed)
    def page(self) -> str:
        return self._page

    @Property(bool, notify=changed)
    def promptOpen(self) -> bool:
        return bool(self._prompt) or self._ask_preset or bool(self._remove_ask) or (
            self._pair_open and bool(self._pair_code)
        )

    @Slot(int)
    def setNavWidth(self, width: int) -> None:
        low, high = SETTINGS_NAV_RANGE
        clamped = max(low, min(high, int(width)))
        if clamped == self._nav_width:
            return
        self._nav_width = clamped
        path = self._window._look_path()
        kept = kept_material(path)
        if kept is not None:
            store_material(path, {**kept, "settingsNavWidth": clamped})
        else:
            self._commit()
            return
        self._publish()

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def draftTheme(self) -> dict[str, Any]:
        return self._draft_theme

    @Property(QObject, constant=True)
    def preview(self) -> QObject:
        return self._preview

    @Slot(str)
    def setSection(self, name: str) -> None:
        if name not in SECTIONS:
            return
        self._section = name
        self._page = "sections"
        self._prompt = ""
        self._publish()

    @Slot()
    def openAdvanced(self) -> None:
        self._draft_choice = dict(self._choice)
        self._draft = copy.deepcopy(self._advanced)
        self._dirty = False
        self._page = "advanced"
        self._prompt = ""
        self._import_error = ""
        self._save_error = ""
        if self._preview_view == "month" and hasattr(self, "_preview"):
            month_bridge = getattr(self._preview, "_passive_month", None)
            if month_bridge is not None and hasattr(month_bridge, "activate_preview"):
                month_bridge.activate_preview()
        self._publish()

    @Slot()
    def closeAdvanced(self) -> None:
        dropped = self._dirty
        self._page = "sections"
        self._dirty = False
        self._prompt = ""
        self._draft_choice = dict(self._choice)
        self._draft = copy.deepcopy(self._advanced)
        if dropped:
            self._notice = "Advanced changes were not applied. Done applies them."
        self._publish()

    @Slot(str)
    def setPreset(self, name: str) -> None:
        if name not in PRESETS or name == self._choice["preset"]:
            return
        if advanced_overrides(self._advanced):
            self._pending_preset = name
            self._ask_preset = True
            self._publish()
            return
        self._apply_preset(name, keep=True)

    @Slot(str)
    def answerPreset(self, choice: str) -> None:
        name = self._pending_preset
        self._ask_preset = False
        self._pending_preset = ""
        if name and choice in ("keep", "discard"):
            self._apply_preset(name, keep=choice == "keep")
            return
        self._publish()

    def _apply_preset(self, name: str, *, keep: bool) -> None:
        self._choice["preset"] = name
        self._draft_choice["preset"] = name
        if not keep:
            scale = self._advanced.get("scale")
            self._advanced = advanced_default()
            self._draft = advanced_default()
            if scale is not None:
                self._advanced["scale"] = scale
                self._draft["scale"] = scale
            self._dirty = False
        self._commit()

    @Slot(str)
    def setMode(self, mode: str) -> None:
        if mode in SAVED_MODES:
            self._set_choice(mode=mode)

    @Slot(str)
    def setContrast(self, contrast: str) -> None:
        if contrast in ("std", "high"):
            self._set_choice(contrast=contrast)

    @Slot(str)
    def setDensity(self, density: str) -> None:
        if density in ("comfortable", "compact"):
            self._set_choice(density=density)

    @Slot(str)
    def setTextSize(self, size: str) -> None:
        val = TEXT_SIZES.get(size)
        if val is None:
            try:
                val = float(size)
            except ValueError:
                return
        number = _float_in(val, SCALE_RANGE)
        if number is None:
            return
        self._advanced["scale"] = number
        self._draft["scale"] = number
        self._commit()

    # The Advanced page's Simple tier edits the same draft as its other tiers, so Done applies the lot and
    # Back drops it. Its preset, mode and row size are the draft's own choice.
    @Slot(str)
    def setDraftPreset(self, name: str) -> None:
        if name in PRESETS:
            self._draft_choice["preset"] = name
            self._mark_draft()

    @Slot(str)
    def setDraftMode(self, mode: str) -> None:
        if mode in SAVED_MODES:
            self._draft_choice["mode"] = mode
            self._mark_draft()

    @Slot(str)
    def setDraftDensity(self, density: str) -> None:
        if density in ("comfortable", "compact"):
            self._draft_choice["density"] = density
            self._mark_draft()

    @Slot(str)
    def setDraftTextSize(self, size: str) -> None:
        number = _float_in(TEXT_SIZES.get(size), SCALE_RANGE)
        if number is not None:
            self._draft["scale"] = number
            self._mark_draft()

    @Slot(str)
    def setCornerShape(self, shape: str) -> None:
        if shape in CORNER_SHAPES:
            self._draft["corner"] = CORNER_SHAPES[shape]
            self._mark_draft()

    @Slot(str)
    def setLookTier(self, tier: str) -> None:
        """Simple, More or All. It only changes which controls show: no value moves. It is kept on this
        computer in the look file."""
        if tier not in LOOK_TIERS or tier == self._tier:
            return
        self._tier = tier
        self._store_tier()
        self._publish()

    def seed_look_tier(self, tier: str) -> None:
        """Setup read as power: the Advanced page starts on `tier`, unless a tier was already chosen."""
        if tier in LOOK_TIERS and not self._tier:
            self._tier = tier
            self._store_tier()
            self._publish()

    def _store_tier(self) -> None:
        path = self._window._look_path()
        kept = kept_material(path)
        if kept is None:
            self._commit()
            return
        store_material(path, {**kept, "lookTier": self._tier})

    def apply_setup_look(self, **parts: str) -> None:
        """Setup's look cards: applied and kept now, as the Look section does, with no question asked."""
        preset = parts.get("preset")
        if preset in PRESETS and preset != self._choice["preset"]:
            self._apply_preset(preset, keep=True)
        rest = {
            key: value
            for key, value in parts.items()
            if (key == "mode" and value in SAVED_MODES) or (key == "density" and value in DENSITY_CHOICES)
        }
        if rest:
            self._set_choice(**rest)

    @Slot(bool)
    def setClock(self, on: bool) -> None:
        if "clock_24h" in _FIELDS:
            self._write({"clock_24h": bool(on)})

    @Slot(str)
    def setFocusAudio(self, value: str) -> None:
        if value in AUDIO_VALUES and "focus_audio" in _FIELDS:
            self._write({"focus_audio": value})

    @Slot(str)
    def setSpotify(self, text: str) -> None:
        if "default_spotify_url" not in _FIELDS:
            return
        raw = text.strip()
        try:
            link = valid_spotify_url(raw)
        except ValueError:
            self._spotify_error = "Use a link from open.spotify.com."
            self._publish()
            return
        self._spotify_error = ""
        self._write({"default_spotify_url": link})

    @Slot(str)
    def setReminder(self, value: str) -> None:
        if value not in REMINDERS:
            return
        if value == "off":
            self._write({"reminders_enabled": False})
            return
        self._write({"reminders_enabled": True, "reminder_lead_min": int(value)})

    @Slot(int)
    def setReminderLead(self, minutes: int) -> None:
        if isinstance(minutes, bool) or not 0 <= minutes <= LEAD_MAX:
            self._notice = SAVE_REFUSED
            self._publish()
            return
        self._write({"reminder_lead_min": int(minutes)})

    def _round_to_grid(self, updates: dict[str, Any], prefs: dict[str, Any]) -> bool:
        """Splitting needs 15-minute lengths (the backend refuses others). Puts the rounded ones in
        `updates` and says whether any moved."""
        moved = False
        for key in ("work", "break", "long"):
            field, _lo, high = TIMER_LENGTHS[key]
            have = int(updates.get(field) or prefs.get(field) or {"work": 30, "break": 15, "long": 30}[key])
            snapped = snap_minutes(have, 1, high)
            if snapped != have:
                updates[field] = snapped
                moved = True
        return moved

    @Slot(str)
    def setTimerPreset(self, value: str) -> None:
        if "timer_work_min" not in _FIELDS:
            return
        if value == "custom":
            self._timer_custom = True
            self._publish()
            return
        item = next((row for row in TIMER_PRESETS if row["id"] == value), None)
        if item is None:
            return
        self._timer_custom = False
        self._timer_note = ""
        self._write(
            {
                "timer_work_min": item["timer_work_min"],
                "timer_break_min": item["timer_break_min"],
                "timer_long_break_min": item["timer_long_break_min"],
                "timer_long_break_every": item["timer_long_break_every"],
            }
        )

    @Slot(str, int)
    def setTimerLength(self, key: str, value: int) -> None:
        """One length of the Custom timer. A value outside the backend's range, or off the 15-minute
        grid while splitting is on, is refused and what was saved stays."""
        if key not in TIMER_LENGTHS or "timer_work_min" not in _FIELDS:
            return
        field, low, high = TIMER_LENGTHS[key]
        split = _prefs_of(self._window).get("auto_split_pomodoro") is True
        if isinstance(value, bool) or not low <= value <= high or (split and key != "every" and value % 15):
            self._notice = SAVE_REFUSED
            self._publish()
            return
        self._timer_custom = True
        self._timer_note = ""
        self._write({field: int(value)})

    @Slot(bool)
    def setAutoSplit(self, on: bool) -> None:
        if "auto_split_pomodoro" not in _FIELDS:
            return
        updates: dict[str, Any] = {"auto_split_pomodoro": bool(on)}
        self._timer_note = ""
        if on and self._round_to_grid(updates, _prefs_of(self._window)):
            self._timer_note = SPLIT_ROUNDED.format(step=15)
        self._write(updates)

    @Slot(bool)
    def setAutoComplete(self, on: bool) -> None:
        if "focus_auto_complete" in _FIELDS:
            self._write({"focus_auto_complete": bool(on)})

    @Slot(bool)
    def setAutoMute(self, on: bool) -> None:
        if "focus_auto_mute" in _FIELDS:
            self._write({"focus_auto_mute": bool(on)})

    @Slot(bool)
    def setReminderSound(self, on: bool) -> None:
        if "reminder_sound" in _FIELDS:
            self._write({"reminder_sound": bool(on)})

    @Slot(str)
    def setTone(self, value: str) -> None:
        if value in SOUNDS and "alarm_tone" in _FIELDS:
            self._write({"alarm_tone": value})

    @Slot(str)
    def openAlarm(self, alarm_id: str) -> None:
        """Add (an empty id) or edit an alarm. The sheet is the shared one over every screen."""
        self._bridge.sheets.openAlarm(alarm_id)  # type: ignore[attr-defined]

    @Slot()
    def playTone(self) -> None:
        """Test play: the chosen tone at the saved volume. Spotify plays its link, and the built-in
        chime when no link plays. Silent under FLEXWEEK_SILENT, as every Bell is."""
        prefs = _prefs_of(self._window)
        tone = str(prefs.get("alarm_tone") or FALLBACK)
        if tone == "spotify":
            link = prefs.get("default_spotify_url")
            if link and self._spotify_player.play(str(link)):
                return
            tone = FALLBACK
        if not self._bell.once(tone, int(prefs.get("alert_volume", 80))):
            self._notice = NO_SOUND
            self._publish()

    @Slot(bool)
    def setDnd(self, on: bool) -> None:
        if "reminder_dnd_override" in _FIELDS:
            self._write({"reminder_dnd_override": bool(on)})

    @Slot(int)
    def setVolume(self, value: int) -> None:
        if "alert_volume" not in _FIELDS:
            return
        if isinstance(value, bool) or not 0 <= value <= 100:
            self._notice = SAVE_REFUSED
            self._publish()
            return
        self._write({"alert_volume": int(value)})

    @Slot(bool)
    def setEndChime(self, on: bool) -> None:
        if "end_chime" in _FIELDS:
            self._write({"end_chime": bool(on)})

    @Slot(bool)
    def setTray(self, on: bool) -> None:
        if "tray_notifications" in _FIELDS:
            self._write({"tray_notifications": bool(on)})

    @Slot(str)
    def setAccent(self, name: str) -> None:
        if name in ACCENTS and "accent" in _FIELDS:
            self._write({"accent": name})

    @Slot(bool)
    def setAccentChips(self, on: bool) -> None:
        if "accent_chips" in _FIELDS:
            self._write({"accent_chips": bool(on)})

    @Slot(str)
    def setFont(self, name: str) -> None:
        if name in FONTS:
            self._font = name
            self._notice = ""
            self._commit()

    # Study hours and School hours. Each is a draft until its Save, as the Widgets dialogs are.
    def _school_block(self) -> dict[str, Any] | None:
        repeats = getattr(getattr(self._window, "session", None), "repeats", None) or []
        return next((item for item in repeats if item.get("id") == SETUP_SCHOOL_ID), None)

    def _this_week(self) -> str:
        """'This week: no School on Wednesday.' for the usual School, or ''."""
        school = self._school_block()
        session = getattr(self._window, "session", None)
        if school is None or session is None:
            return ""
        clock_24h = (_prefs_of(self._window)).get("clock_24h") is True
        try:
            return this_week_line(session.blocks, [school], clock_24h, session.week_start) or ""
        except KeyError, TypeError, ValueError:
            return ""

    def _redraw_study(self) -> None:
        self._publish()

    @Slot(str)
    def addWorkPreset(self, name: str) -> None:
        for label, days, start, end in WORK_PRESETS:
            if label == name:
                self._study.add_window({"days": list(days), "start": start, "end": end})
                self._redraw_study()
                return

    @Slot()
    def addWorkCustom(self) -> None:
        self._study.add_window()
        self._redraw_study()

    @Slot(int)
    def removeWorkWindow(self, index: int) -> None:
        self._study.remove(self._study.windows, index)
        self._redraw_study()

    @Slot(int, int)
    def toggleWorkDay(self, index: int, day: int) -> None:
        self._study.toggle_day(self._study.windows, index, day)
        self._redraw_study()

    @Slot(int, str)
    def setWorkStart(self, index: int, text: str) -> None:
        self._study.set_time(self._study.windows, index, "start", text)
        self._redraw_study()

    @Slot(int, str)
    def setWorkEnd(self, index: int, text: str) -> None:
        self._study.set_time(self._study.windows, index, "end", text)
        self._redraw_study()

    @Slot(int, str)
    def setWorkSubject(self, index: int, text: str) -> None:
        self._study.set_text(self._study.windows, index, "subject", text)
        self._redraw_study()

    @Slot()
    def addProtected(self) -> None:
        self._study.add_protected()
        self._redraw_study()

    @Slot(int)
    def removeProtected(self, index: int) -> None:
        self._study.remove(self._study.protected_rows, index)
        self._redraw_study()

    @Slot(int, int)
    def toggleProtectedDay(self, index: int, day: int) -> None:
        self._study.toggle_day(self._study.protected_rows, index, day)
        self._redraw_study()

    @Slot(int, str)
    def setProtectedStart(self, index: int, text: str) -> None:
        self._study.set_time(self._study.protected_rows, index, "start", text)
        self._redraw_study()

    @Slot(int, str)
    def setProtectedEnd(self, index: int, text: str) -> None:
        self._study.set_time(self._study.protected_rows, index, "end", text)
        self._redraw_study()

    @Slot(int, str)
    def setProtectedTitle(self, index: int, text: str) -> None:
        self._study.set_text(self._study.protected_rows, index, "title", text)
        self._redraw_study()

    @Slot(int, str)
    def setProtectedKind(self, index: int, kind: str) -> None:
        self._study.set_kind(index, kind)
        self._redraw_study()

    @Slot()
    def saveStudyHours(self) -> None:
        problem = self._study.problem()
        if problem:
            self._study.error = problem
            self._publish()
            return
        session = self._window.session
        cutoff = _prefs_of(self._window).get("day_cutoff") or None
        if session.save_availability(self._study.saved_protected(), cutoff, self._study.saved_windows()):
            self._study.dirty = False
            self._study.error = ""
        self._publish()

    @Slot()
    def discardStudyHours(self) -> None:
        self._study.load(_prefs_of(self._window))
        self._publish()

    @Slot(int)
    def toggleSchoolDay(self, day: int) -> None:
        self._school.toggle_day(day)
        self._publish()

    @Slot(str)
    def setSchoolStart(self, text: str) -> None:
        self._school.set_time("start", text)
        self._publish()

    @Slot(str)
    def setSchoolEnd(self, text: str) -> None:
        self._school.set_time("end", text)
        self._publish()

    @Slot()
    def discardSchoolHours(self) -> None:
        self._school.load(self._school_block())
        self._publish()

    @Slot()
    def saveSchoolHours(self) -> None:
        """School's days and times every week, saved from this week on as the Widgets dialog saves
        them. No day ticked takes School off the calendar."""
        school = self._school
        problem = school.problem()
        if problem:
            school.error = problem
            self._publish()
            return
        window = self._window
        repeats = window.session.repeats
        usual = self._school_block()
        if not school.days:
            if usual is not None:
                after = [item for item in repeats if item.get("id") != SETUP_SCHOOL_ID]
                if window._apply_standing(after, "deleting School"):
                    window.session.save()
                    window._set_notice("Deleted School from this week and every week after.", "", None)
                else:
                    return
            school.dirty = False
            self._publish()
            return
        made = (
            copy.deepcopy(usual)
            if usual is not None
            else {
                "id": SETUP_SCHOOL_ID,
                "kind": "locked",
                "title": "School",
                "category": "class",
            }
        )
        made.update(days=sorted(school.days), start=school.start, duration_min=school.minutes())
        try:
            WeekRequest(blocks=[TimeBlock.model_validate(made)])
        except ValidationError as error:
            from desktop.native.sheet_rules import _block_problem

            school.error = _block_problem(error)
            self._publish()
            return
        after = [made if item.get("id") == SETUP_SCHOOL_ID else item for item in repeats]
        if usual is None:
            after = [made, *repeats]
        start = hhmm_text(made["start"])
        end_minutes = hhmm_to_minutes(made["start"]) + made["duration_min"]
        end = hhmm_text(minutes_to_hhmm(end_minutes) if end_minutes < 1440 else "24:00")
        school.dirty = False
        window._save_standing(
            after,
            "editing School hours",
            lambda: window._set_notice(f"School now {start}–{end} every week", "", None),
        )
        self._publish()

    @Slot(bool)
    def setSplit(self, on: bool) -> None:
        if _SPLIT is None:
            return
        self._write({_SPLIT: bool(on)})

    @Slot(str)
    def setCutoff(self, value: str) -> None:
        if "day_cutoff" not in _FIELDS:
            return
        if value not in CUTOFFS and value != "":
            return
        self._write({"day_cutoff": value or None})

    @Slot(int)
    def setBuffer(self, minutes: int) -> None:
        if _BUFFER is None or minutes not in (0, 15, 30):
            return
        self._write({_BUFFER: minutes})

    @Slot(str)
    def setWeekStart(self, value: str) -> None:  # noqa: N802 — QML slot
        """Kept on this computer, like Widgets Settings' own row; the notice redraws every screen."""
        if value in WEEK_STARTS:
            save_week_starts_on(value)

    def _on_week_start(self, _value: str) -> None:
        self._publish()

    @Slot(int)
    def setDragStep(self, minutes: int) -> None:
        if "drag_step_min" in _FIELDS and minutes in DRAG_STEPS:
            self._write({"drag_step_min": minutes})

    @Slot(bool)
    def setUrgent(self, on: bool) -> None:
        if _URGENT is not None:
            self._write({_URGENT: bool(on)})

    @Slot(bool)
    def setWeekendFree(self, on: bool) -> None:
        if _WEEKEND_FREE is not None:
            self._write({_WEEKEND_FREE: bool(on)})

    @Slot(bool)
    def setShowWeekends(self, on: bool) -> None:
        if _SHOW_WEEKENDS is not None:
            self._write({_SHOW_WEEKENDS: bool(on)})

    @Slot(bool)
    def setStartAtLogin(self, on: bool) -> None:
        if "start_at_login" in _FIELDS:
            self._write({"start_at_login": bool(on)}, login=bool(on))

    @Slot(str)
    def setAnimations(self, value: str) -> None:
        if value in ANIMATION_VALUES and "motion" in _FIELDS:
            self._write({"motion": value})

    @Slot(str)
    def setOpenOn(self, value: str) -> None:
        if value in OPEN_ON_VALUES and "preferred_view" in _FIELDS:
            self._write({"preferred_view": value})

    @Slot(str)
    def setPlanningStyle(self, value: str) -> None:
        if value in PLANNING_VALUES and "planning_style" in _FIELDS:
            self._write({"planning_style": value})

    @Slot(bool)
    def setShortcuts(self, on: bool) -> None:
        self._shortcuts = bool(on)
        self._bridge._shortcuts = self._shortcuts  # type: ignore[attr-defined]
        self._bridge.changed.emit()  # type: ignore[attr-defined]
        self._commit()

    @Slot(bool)
    def setLetterKeys(self, on: bool) -> None:  # noqa: N802 - the name QML calls
        self._letter_keys = bool(on)
        self._bridge._letter_keys = self._letter_keys  # type: ignore[attr-defined]
        self._bridge.changed.emit()  # type: ignore[attr-defined]
        self._commit()

    def _set_optional_int(self, key: str, value: float, bounds: tuple[int, int]) -> None:
        if isinstance(value, bool):
            return
        if value < 0:
            self._draft[key] = None
        else:
            number = int(round(value))
            low, high = bounds
            if not low <= number <= high:
                return
            self._draft[key] = number
        self._mark_draft()

    @Slot(float)
    def setCorner(self, value: float) -> None:
        self._set_optional_int("corner", value, CORNER_RANGE)

    @Slot(float)
    def setHour(self, value: float) -> None:
        self._set_optional_int("hour", value, HOUR_RANGE)

    @Slot(float)
    def setPadding(self, value: float) -> None:
        self._set_optional_int("padding", value, PAD_RANGE)

    @Slot(float)
    def setShadow(self, value: float) -> None:
        self._set_optional_int("shadow", value, SHADOW_RANGE)

    @Slot(float)
    def setScale(self, value: float) -> None:
        number = _float_in(value, SCALE_RANGE)
        if number is None:
            return
        self._draft["scale"] = number
        self._mark_draft()

    @Slot(str)
    def setMotion(self, value: str) -> None:
        if value in MOTION_SPEEDS:
            self._draft["motion"] = value
            self._mark_draft()

    @Slot(str)
    def setBlock(self, value: str) -> None:
        if value in BLOCK_STYLES:
            self._draft["block"] = value
            self._mark_draft()

    @Slot(str)
    def setLines(self, value: str) -> None:
        if value in HOUR_LINES:
            self._draft["lines"] = value
            self._mark_draft()

    @Slot(bool)
    def setRail(self, on: bool) -> None:
        self._draft["rail"] = bool(on)
        self._mark_draft()

    @Slot(bool)
    def setToday(self, on: bool) -> None:
        self._draft["today"] = bool(on)
        self._mark_draft()

    @Slot(bool)
    def setTimes(self, on: bool) -> None:
        self._draft["times"] = bool(on)
        self._mark_draft()

    @Slot(bool)
    def setLengths(self, on: bool) -> None:
        self._draft["lengths"] = bool(on)
        self._mark_draft()

    @Slot(str)
    def setNow(self, text: str) -> None:
        if text.strip() == "":
            self._draft["now"] = None
            self._mark_draft()
            return
        colour = _hex(text.strip())
        if colour is None:
            self._notice = "Use a colour like #1a1c20."
            self._publish()
            return
        self._draft["now"] = colour
        self._mark_draft()

    @Slot(str, str)
    def setCategory(self, key: str, text: str) -> None:
        if key not in CATEGORY_KEYS:
            return
        cats = self._draft["cat"]
        if text.strip() == "":
            cats[key] = None
            self._mark_draft()
            return
        colour = _hex(text.strip())
        if colour is None:
            self._notice = "Use a colour like #1a1c20."
            self._publish()
            return
        cats[key] = colour
        self._mark_draft()

    @Slot(str)
    def resetGroup(self, name: str) -> None:
        keys = _GROUPS.get(name)
        if keys is None:
            return
        fresh = advanced_default()
        for key in keys:
            self._draft[key] = copy.deepcopy(fresh[key])
        self._mark_draft()

    @Slot()
    def resetAdvanced(self) -> None:
        self._draft = advanced_default()
        self._mark_draft()

    @Slot()
    def done(self) -> None:
        self._choice = dict(self._draft_choice)
        self._advanced = copy.deepcopy(self._draft)
        self._dirty = False
        self._page = "sections"
        self._prompt = ""
        self._commit()

    @Slot()
    def exportLook(self) -> None:
        self._export_text = export_document(self._draft_choice, self._draft)
        self._publish()

    @Slot()
    def beginExport(self) -> None:
        self._export_text = export_document(self._draft_choice, self._draft)
        self._prompt = "export"
        self._publish()

    @Slot(str)
    def importText(self, text: str) -> None:
        parsed, error = import_document(text)
        if parsed is None:
            self._import_error = error
            self._prompt = "import"
            self._publish()
            return
        self._draft_choice = dict(parsed["choice"])
        self._draft = copy.deepcopy(parsed["advanced"])
        self._import_error = ""
        self._notice = "Imported. Done applies it."
        self._mark_draft()

    @Slot(str)
    def saveAs(self, name: str) -> None:
        clean = name.strip()
        if not clean:
            self._save_error = "Name the look first."
            self._prompt = "save"
            self._publish()
            return
        self._saved = [
            *self._saved,
            {
                "name": clean,
                "preset": self._draft_choice["preset"],
                "mode": self._draft_choice["mode"],
                "contrast": self._draft_choice["contrast"],
                "density": self._draft_choice["density"],
                "advanced": copy.deepcopy(self._draft),
            },
        ]
        self._save_error = ""
        self._notice = "Saved."
        self._commit()

    @Slot(str)
    def useSaved(self, name: str) -> None:
        """Wear a look kept with Save as new. Applies at once, like the basic dials."""
        for item in self._saved:
            if item["name"] != name:
                continue
            scale = self._advanced.get("scale")
            self._choice = {key: item[key] for key in ("preset", "mode", "contrast", "density")}
            self._advanced = copy.deepcopy(item["advanced"])
            if scale is not None:
                self._advanced["scale"] = scale
            self._draft_choice = dict(self._choice)
            self._draft = copy.deepcopy(self._advanced)
            self._dirty = False
            self._notice = f"Wearing {name}."
            self._commit()
            return

    @Slot(str)
    def forgetSaved(self, name: str) -> None:
        kept = [item for item in self._saved if item["name"] != name]
        if len(kept) == len(self._saved):
            return
        self._saved = kept
        self._notice = "Deleted."
        self._commit()

    @Slot()
    def beginImport(self) -> None:
        self._prompt = "import"
        self._import_error = ""
        self._publish()

    @Slot()
    def beginSave(self) -> None:
        self._prompt = "save"
        self._save_error = ""
        self._publish()

    @Slot()
    def dismissPrompt(self) -> None:
        self._prompt = ""
        self._publish()

    @Slot(str)
    def confirmPrompt(self, text: str) -> None:
        kind = self._prompt
        self._prompt = ""
        if kind == "import":
            self.importText(text)
        elif kind == "save":
            self.saveAs(text)
        else:
            self._publish()

    @Slot(str)
    def setPreviewFit(self, mode: str) -> None:
        if mode in ("Fit", "Actual"):
            self._preview_fit = mode
            self._publish()

    @Slot(str)
    def setPreviewView(self, name: str) -> None:
        if name in ("week", "day", "month"):
            self._preview_view = name
            if name == "month" and hasattr(self, "_preview"):
                month_bridge = getattr(self._preview, "_passive_month", None)
                if month_bridge is not None and hasattr(month_bridge, "activate_preview"):
                    month_bridge.activate_preview()
            self._publish()

    @Slot(str)
    def fixRole(self, role: str) -> None:
        mode = mode_of(self._draft_choice, self._worn_dark())
        for item in reading_problems(mode, self._draft):
            if item["role"] != role:
                continue
            if role == "now":
                self._draft["now"] = item["fixed"]
            elif role in CATEGORY_KEYS:
                self._draft["cat"][role] = item["fixed"]
            self._mark_draft()
            return

    @Slot()
    def fixAll(self) -> None:
        mode = mode_of(self._draft_choice, self._worn_dark())
        for item in reading_problems(mode, self._draft):
            role = item["role"]
            if role == "now":
                self._draft["now"] = item["fixed"]
            elif role in CATEGORY_KEYS:
                self._draft["cat"][role] = item["fixed"]
        self._mark_draft()

    @Slot()
    def pair(self) -> None:
        session = self._window.session

        def finish(offer: Any, error: Exception | None) -> None:
            def apply() -> None:
                if error is not None or not isinstance(offer, dict):
                    self._pair_code = ""
                    self._pair_open = False
                    self._pair_error = str(error) if error is not None else "Pairing did not start."
                else:
                    self._pair_code = str(offer.get("display_code") or "")
                    self._pair_error = ""
                    self._pair_open = bool(self._pair_code)
                    self._pair_copied = False
                    self._pair_seconds = PAIR_TTL_SECONDS
                    self._pair_tries = 3
                    self._pair_watch.start()
                    self._pair_tick()
                    return
                self._publish()

            # Owned by this bridge: a bridge dropped before the turn ends takes the timer with it.
            QTimer.singleShot(0, self, apply)

        if not session.begin_pairing(finish):
            self._pair_code = ""
            self._pair_open = False
            self._pair_error = "Pairing needs an account on this computer."
            self._publish()

    @Slot()
    def copyPairCode(self) -> None:
        if not self._pair_code:
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._pair_code)
        self._pair_copied = True
        self._pair_copy_reset.start()
        self._publish()

    @Slot()
    def closePairing(self) -> None:
        if not self._pair_open:
            return
        self._pair_open = False
        self._publish()

    def _pair_tick(self) -> None:
        """The open code's words: its countdown and tries while it waits, else why it closed."""
        status = self._window.session.pairing_status()
        state = status.get("state") if isinstance(status, dict) else None
        if state == "waiting":
            left = max(0, (int(status["expires_at_ms"]) - wall_clock.now_ms()) // 1000)
            self._pair_seconds = left
            self._pair_tries = int(status["tries_left"])
            tries = tries_words(self._pair_tries)
            self._pair_status = f"{countdown_words(left)}. {tries}. {PAIR_ONCE}"
        else:
            self._pair_watch.stop()
            self._pair_status = ""
            self._pair_seconds = 0
            if state is not None:
                self._pair_code = ""
                self._pair_open = False
                if state != "paired":
                    self._pair_error = pair_problem(state) or PAIR_CLOSED
        self._publish()

    @Slot()
    def openAccount(self) -> None:
        self._window._open_account()

    @Slot()
    def runSetup(self) -> None:
        self._window._run_setup_again()

    @Slot(bool)
    def setDeveloperBuilds(self, on: bool) -> None:
        self._window._updates["developer_builds"] = bool(on)
        self._window._save_look()
        self._publish()

    @Slot()
    def checkUpdates(self) -> None:
        self._window._check_updates(asked=True)

    @Slot()
    def reportProblem(self) -> None:
        feedback.open_form()
