"""Settings for the Material shell.

QML calls the slots. Preferences go through NativeSession, the same ones the
Widgets settings write. The look file's material object is the preset, the
advanced draft, and the keyboard-shortcut switch. A control with nowhere to
save is not built; the flags below say which those are.
"""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from backend.app import Preferences
from backend.models import valid_spotify_url
from desktop.native.material.theme import (
    BLOCK_STYLES,
    CATEGORY_KEYS,
    CORNER_RANGE,
    DEFAULT_CONTRAST,
    DEFAULT_PRESET,
    HOUR_LINES,
    HOUR_RANGE,
    MOTION_SPEEDS,
    PAD_RANGE,
    PRESETS,
    SAVED_MODES,
    SCALE_RANGE,
    SHADOW_RANGE,
    _float_in,
    _hex,
    advanced_default,
    advanced_overrides,
    dress_theme,
    export_document,
    hour_row_px,
    import_document,
    pack_material,
    read_advanced,
    read_material_choice,
    read_saved_material,
    read_shortcuts,
    reading_problems,
    resolved_mode,
    scheme,
    store_material,
    theme_object,
)
from desktop.native.version import VERSION

_FIELDS = frozenset(Preferences.model_fields)
SECTIONS = ("look", "planning", "focus", "alerts", "computer")
CUTOFFS = ("20:00", "21:00", "22:00")
REMINDERS = ("off", "5", "10", "15")
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
    except (TypeError, ValueError):
        lead = None
    if prefs.get("reminders_enabled", True) is False:
        return "off", chips
    if lead in (5, 10, 15):
        return str(lead), chips
    if lead is not None and 0 <= lead <= 120:
        chips.append({"label": f"{lead}m", "value": str(lead)})
        return str(lead), chips
    return "", chips


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

    def _week(self) -> QObject:
        return self._material._week  # type: ignore[attr-defined]

    @Property(int, notify=changed)
    def hourRow(self) -> int:
        panel = self._settings
        return hour_row_px(panel._draft_choice["density"], panel._draft)

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def theme(self) -> dict[str, Any]:
        return self._settings._draft_theme

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
    def nowMinute(self) -> int:
        return int(self._week().nowMinute)  # type: ignore[attr-defined]

    @Property(int, notify=homeworkChanged)
    def homeworkCount(self) -> int:
        return int(self._week().homeworkCount)  # type: ignore[attr-defined]


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
        self._saved: list[dict[str, Any]] = []
        self._dirty = False
        self._prompt = ""
        self._notice = ""
        self._spotify_error = ""
        self._import_error = ""
        self._save_error = ""
        self._pair_code = ""
        self._pair_error = ""
        self._export_text = ""
        self._ask_preset = False
        self._pending_preset = ""
        self._preview_fit = "Fit"
        self._preview_view = "week"
        self._draft_theme: dict[str, Any] = {}
        self._state: dict[str, Any] = {}
        self._preview = PreviewBridge(parent, self)
        session = getattr(self._window, "session", None)
        signal = getattr(session, "week_changed", None)
        if signal is not None:
            signal.connect(self._on_session)
        self._load_applied(keep_draft=False)

    def note_applied(self) -> None:
        """The shell re-read the look file. Keep a draft the student is still editing."""
        self._load_applied(keep_draft=self._dirty)

    def _load_applied(self, *, keep_draft: bool) -> None:
        stored = self._bridge._stored_look()  # type: ignore[attr-defined]
        self._choice = read_material_choice(stored)
        self._advanced = read_advanced(stored)
        self._shortcuts = read_shortcuts(stored)
        self._saved = read_saved_material(stored)
        if not keep_draft:
            self._draft_choice = dict(self._choice)
            self._draft = copy.deepcopy(self._advanced)
            self._dirty = False
        self._publish()

    def _on_session(self) -> None:
        try:
            self._publish()
        except (OSError, KeyError, ValueError):
            return

    def _worn_dark(self) -> bool:
        from desktop.native.material.host import appearance_of

        mode, _contrast = appearance_of(self._window)
        return mode == "dark"

    def _colours(self, choice: dict[str, str]) -> dict[str, str]:
        mode = resolved_mode(choice["mode"], self._worn_dark())
        try:
            return scheme(choice["preset"], mode, choice["contrast"])
        except (KeyError, ValueError, OSError):
            try:
                return scheme(DEFAULT_PRESET, "light", DEFAULT_CONTRAST)
            except (KeyError, ValueError, OSError):
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
        base = theme_object(colours, choice["density"], reduced, choice["contrast"] == "high")
        return dress_theme(base, advanced)

    def _build(self) -> dict[str, Any]:
        prefs = _prefs_of(self._window)
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
        work = int(prefs.get("timer_work_min") or 30)
        rest = int(prefs.get("timer_break_min") or 15)
        audio = prefs.get("focus_audio") or "off"
        cutoff = prefs.get("day_cutoff") or ""
        motion = prefs.get("motion")
        phones = self._phone_names()
        problems = self._problem_rows()
        return {
            "section": self._section,
            "page": self._page,
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
            "pomodoro": work == 25 and rest == 5,
            "split": bool(prefs.get(_SPLIT)) if _SPLIT else False,
            "cutoff": cutoff if cutoff in CUTOFFS else "",
            "buffer": int(prefs.get(_BUFFER) or 0) if _BUFFER else 0,
            "urgent": bool(prefs.get(_URGENT, True)) if _URGENT else False,
            "weekendFree": bool(prefs.get(_WEEKEND_FREE)) if _WEEKEND_FREE else False,
            "showWeekends": bool(prefs.get(_SHOW_WEEKENDS, True)) if _SHOW_WEEKENDS else True,
            "startAtLogin": prefs.get("start_at_login") is True,
            "reduceMotion": motion in ("reduce", "off"),
            "shortcuts": self._shortcuts,
            "version": f"FlexWeek {VERSION}",
            "pairCode": self._pair_code,
            "pairError": self._pair_error,
            "phones": phones,
            "showClock": "clock_24h" in _FIELDS,
            "showAudio": "focus_audio" in _FIELDS,
            "showSpotify": "default_spotify_url" in _FIELDS,
            "showReminder": "reminders_enabled" in _FIELDS and "reminder_lead_min" in _FIELDS,
            "showPomodoro": "timer_work_min" in _FIELDS and "timer_break_min" in _FIELDS,
            "showSplit": _SPLIT is not None,
            "showCutoff": "day_cutoff" in _FIELDS,
            "showBuffer": _BUFFER is not None,
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

    def _problem_rows(self) -> list[dict[str, Any]]:
        mode = resolved_mode(self._draft_choice["mode"], self._worn_dark())
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

    def _write(self, updates: dict[str, Any], *, login: bool | None = None) -> None:
        session = self._window.session

        def then(ok: bool) -> None:
            if ok:
                if login is not None:
                    self._window._apply_start_at_login(login)
                self._bridge.refresh()  # type: ignore[attr-defined]
                self._notice = ""
            else:
                self._notice = "Could not save that."
            self._publish()

        if not session.save_preferences(updates, then):
            self._notice = "Could not save that."
            self._publish()

    def _commit(self) -> None:
        path = self._window._look_path()
        material = pack_material(self._choice, self._advanced, self._shortcuts, self._saved)
        store_material(path, material)
        self._bridge._shortcuts = self._shortcuts  # type: ignore[attr-defined]
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

    @Property(bool, notify=changed)
    def promptOpen(self) -> bool:
        return bool(self._prompt) or self._ask_preset

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
            self._advanced = advanced_default()
            self._draft = advanced_default()
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

    @Slot(bool)
    def setPomodoro(self, on: bool) -> None:
        if "timer_work_min" not in _FIELDS:
            return
        if on:
            updates: dict[str, Any] = {"timer_work_min": 25, "timer_break_min": 5}
            if _prefs_of(self._window).get("auto_split_pomodoro"):
                updates["auto_split_pomodoro"] = False
            self._write(updates)
            return
        self._write({"timer_work_min": 30, "timer_break_min": 15})

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

    @Slot(bool)
    def setReduceMotion(self, on: bool) -> None:
        if "motion" in _FIELDS:
            self._write({"motion": "reduce" if on else "normal"})

    @Slot(bool)
    def setShortcuts(self, on: bool) -> None:
        self._shortcuts = bool(on)
        self._bridge._shortcuts = self._shortcuts  # type: ignore[attr-defined]
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
            self._choice = {key: item[key] for key in ("preset", "mode", "contrast", "density")}
            self._advanced = copy.deepcopy(item["advanced"])
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
            self._publish()

    @Slot(str)
    def fixRole(self, role: str) -> None:
        mode = resolved_mode(self._draft_choice["mode"], self._worn_dark())
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
        mode = resolved_mode(self._draft_choice["mode"], self._worn_dark())
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
                    self._pair_error = str(error) if error is not None else "Pairing did not start."
                else:
                    self._pair_code = str(offer.get("display_code") or "")
                    self._pair_error = ""
                self._publish()

            QTimer.singleShot(0, apply)

        if not session.begin_pairing(finish):
            self._pair_code = ""
            self._pair_error = "Pairing needs an account on this computer."
            self._publish()

    @Slot()
    def openAccount(self) -> None:
        self._window._open_account()

    @Slot()
    def runSetup(self) -> None:
        self._window._run_setup_again()

    @Slot()
    def checkUpdates(self) -> None:
        self._window._check_updates(asked=True)
