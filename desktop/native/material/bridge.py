"""The only way the Material shell reads the week: through NativeSession.

QML calls the slots. It does not touch HTTP, SQL, or the engine. Prompts that
belong to the Widgets week (the one-shot plan review and the unfinished list)
are not taken here. A refresh of this surface must not consume them.

Each screen has its own bridge module. This file is the core: navigation, the
theme object, and the slots every screen shares. Week rows live in bridge_week.
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, cast

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from desktop.native.fields import announce
from desktop.native.hours.zoom import Scale
from desktop.native.material.bridge_account import AccountBridge
from desktop.native.material.bridge_day import DayBridge
from desktop.native.material.bridge_focus import FocusBridge
from desktop.native.material.bridge_month import MonthBridge
from desktop.native.material.bridge_myday import MyDayBridge
from desktop.native.material.bridge_settings import SettingsBridge
from desktop.native.material.bridge_sheets import SheetsBridge
from desktop.native.material.bridge_week import WeekBridge
from desktop.native.material.theme import (
    DEFAULT_CONTRAST,
    DEFAULT_DENSITY,
    DEFAULT_PRESET,
    advanced_default,
    dress_theme,
    hour_row_px,
    read_advanced,
    read_letter_keys,
    read_material_choice,
    read_shortcuts,
    resolved_mode,
    scheme,
    stroke_for,
    theme_object,
)
from desktop.native.reuse import planner_title
from desktop.native.weekmodel import clock_label

# Keys 1–5, and the StackLayout order. Week is the screen a new shell opens on.
SCREENS = ("day", "week", "month", "myday", "settings")
SNACK_MS = 10000
WEEK_ZOOM = Scale("material.week", (32, 44, 56, 72, 96, 128), 56)
DAY_ZOOM = Scale("material.day", (32, 44, 56, 72, 96, 128), 56)


class _Session(Protocol):
    account: dict | None
    preferences: dict | None
    week_start: str

    def now_ms(self) -> int: ...

    def can_undo(self) -> bool: ...

    def can_redo(self) -> bool: ...

    def undo(self) -> None: ...

    def redo(self) -> None: ...


class _Window(Protocol):
    session: _Session
    _motion: str

    def _look_path(self) -> Path: ...


class MaterialBridge(QObject):
    """Navigation, the theme object, and the few actions the shell can take."""

    changed = Signal()
    blocksChanged = Signal()
    homeworkChanged = Signal()
    widgetsRequested = Signal()

    def __init__(self, window: QObject) -> None:
        super().__init__(window)
        self.setObjectName("materialBridge")
        # Set before scheme() so a failed build can still dispose() this half-made bridge.
        self._week_follow = None
        self._window = cast(_Window, window)
        self._screen = "week"
        self._snack = ""
        self._snack_action = "UNDO"
        self._snack_target = ""
        self._snack_paused = False
        self._snack_held = False
        self._snack_remaining_ms = SNACK_MS
        self._snack_timer = QTimer(self)
        self._snack_timer.setSingleShot(True)
        self._snack_timer.setInterval(SNACK_MS)
        self._snack_timer.timeout.connect(self._on_snack_timeout)
        self._preset = DEFAULT_PRESET
        self._mode = "light"
        self._contrast = DEFAULT_CONTRAST
        self._density = DEFAULT_DENSITY
        self._reduce_motion = False
        self._advanced = advanced_default()
        self._shortcuts = True
        self._letter_keys = False
        self._colours = scheme(DEFAULT_PRESET, "light", DEFAULT_CONTRAST)
        self._theme = theme_object(self._colours, self._density, False, False)
        self._week = WeekBridge(window, self)
        self._day = DayBridge(window, self)
        self._month = MonthBridge(window, self)
        self._myday = MyDayBridge(window, self)
        self._settings_bridge = SettingsBridge(self)
        self._account = AccountBridge(window)
        self._account.setParent(self)
        self._focus = FocusBridge(window, self)
        self._sheets = SheetsBridge(window, self)
        self._following = False
        # Save finishes on this signal. The day lists and the Undo button read it then,
        # rather than waiting for the 20s clock tick.
        changed = getattr(self._window.session, "week_changed", None)
        if changed is not None and hasattr(changed, "connect"):
            changed.connect(self._follow_week)
            self._week_follow = changed
        # Reminders the session keeps on screen when there is no notification service.
        self._announced_reminders: set[str] = set()
        stay = getattr(self._window.session, "stay_changed", None)
        self._stay_follow = None
        if stay is not None and hasattr(stay, "connect"):
            stay.connect(self._follow_reminders)
            self._stay_follow = stay

    def set_appearance(self, mode: str, _worn_contrast: str) -> None:
        """Apply the saved Material look. `mode` is the worn light or dark axis.

        Follow system uses that axis. An explicit saved light or dark wins. The worn
        contrast is not Material's contrast: this shell stays standard unless its own
        saved contrast says high.
        """
        stored = self._stored_look()
        choice = read_material_choice(stored)
        self._advanced = read_advanced(stored)
        self._shortcuts = read_shortcuts(stored)
        self._letter_keys = read_letter_keys(stored)
        worn_dark = mode == "dark"
        resolved = resolved_mode(choice["mode"], worn_dark)
        try:
            colours = scheme(choice["preset"], resolved, choice["contrast"])
        except KeyError:
            resolved = "light"
            choice["preset"] = DEFAULT_PRESET
            choice["contrast"] = DEFAULT_CONTRAST
            colours = scheme(DEFAULT_PRESET, "light", DEFAULT_CONTRAST)
        self._preset = choice["preset"]
        self._mode = resolved
        self._contrast = choice["contrast"]
        self._density = choice["density"]
        self._colours = colours
        self._publish_theme()
        self._settings_bridge.note_applied()

    def refresh(self) -> None:
        """Read the session again. Does not consume a Widgets prompt."""
        self._publish_theme()
        self._week.reload(self._mode)
        self._day.reload(self._mode)
        self._month.reload()
        self._myday.reload(self._mode)
        self._sheets.refresh()
        self.blocksChanged.emit()
        self.homeworkChanged.emit()
        self.changed.emit()

    @Slot()
    def _follow_week(self) -> None:
        if self._following:
            return
        self._following = True
        try:
            self.refresh()
        finally:
            self._following = False

    def dispose(self) -> None:
        """Cut the session signals this bridge joined before its deleteLater runs. Between the drop
        and the next turn of the event loop a week change would still reach a half-made bridge."""
        changed = getattr(self, "_week_follow", None)
        self._week_follow = None
        if changed is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                changed.disconnect(self._follow_week)
        stay = getattr(self, "_stay_follow", None)
        self._stay_follow = None
        if stay is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                stay.disconnect(self._follow_reminders)

    def _publish_theme(self) -> None:
        self._reduce_motion = self._motion_reduced() or self._advanced.get("motion") == "Off"
        self._theme = dress_theme(
            theme_object(self._colours, self._density, self._reduce_motion, self._contrast == "high"),
            self._advanced,
        )

    def _motion_reduced(self) -> bool:
        prefs = self._window.session.preferences or {}
        chosen = prefs.get("motion")
        level = getattr(self._window, "_motion", "normal")
        return chosen in ("reduce", "off") or level in ("reduce", "off")

    def _stored_look(self) -> object:
        try:
            text = self._window._look_path().read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def _colour(self, role: str) -> str:
        return self._colours[role]

    @Property(bool, notify=changed)
    def dark(self) -> bool:
        return self._mode == "dark"

    @Property(str, notify=changed)
    def primary(self) -> str:
        return self._colour("primary")

    @Property(str, notify=changed)
    def onPrimary(self) -> str:
        return self._colour("onPrimary")

    @Property(str, notify=changed)
    def surface(self) -> str:
        return self._colour("surface")

    @Property(str, notify=changed)
    def onSurface(self) -> str:
        return self._colour("onSurface")

    @Property(str, notify=changed)
    def surfaceContainer(self) -> str:
        return self._colour("surfaceContainer")

    @Property(str, notify=changed)
    def outline(self) -> str:
        return self._colour("outline")

    @Property(str, notify=changed)
    def outlineVariant(self) -> str:
        return self._colour("outlineVariant")

    @Property(float, notify=changed)
    def stroke(self) -> float:
        return stroke_for(self._contrast)

    def _px_for(self, scale: Scale, key: str) -> int:
        """The zoom level, before the text size: what the zoom buttons step through."""
        zoom = getattr(self._window, "_zoom", None)
        if isinstance(zoom, dict) and key in zoom:
            return scale.nearest(zoom[key])
        return hour_row_px(self._density, {**self._advanced, "scale": None})

    def _drawn_px(self, scale: Scale, key: str) -> int:
        """The row as drawn: the zoom level grown by the text size, so a zoomed row grows too."""
        factor = self._advanced.get("scale")
        grow = factor if isinstance(factor, (int, float)) and factor > 0 else 1.0
        zoom = getattr(self._window, "_zoom", None)
        if isinstance(zoom, dict) and key in zoom:
            return int(round(scale.nearest(zoom[key]) * grow))
        return hour_row_px(self._density, self._advanced)

    def _hour_row(self) -> int:
        return self._drawn_px(WEEK_ZOOM, "material.week")

    def _day_hour_row(self) -> int:
        return self._drawn_px(DAY_ZOOM, "material.day")

    def _screen_zoom(self) -> tuple[Scale, str] | None:
        if self._screen == "week":
            return WEEK_ZOOM, "material.week"
        if self._screen == "day":
            return DAY_ZOOM, "material.day"
        return None

    @Property(int, notify=changed)
    def hourRow(self) -> int:
        return self._hour_row()

    @Property(int, notify=changed)
    def dayHourRow(self) -> int:
        return self._day_hour_row()

    @Property(bool, notify=changed)
    def canZoomIn(self) -> bool:
        pair = self._screen_zoom()
        if pair is None:
            return False
        scale, key = pair
        return self._px_for(scale, key) < scale.levels[-1]

    @Property(bool, notify=changed)
    def canZoomOut(self) -> bool:
        pair = self._screen_zoom()
        if pair is None:
            return False
        scale, key = pair
        return self._px_for(scale, key) > scale.levels[0]

    @Slot(int)
    def zoomBy(self, steps: int) -> None:
        pair = self._screen_zoom()
        if pair is None:
            return
        scale, key = pair
        current = self._px_for(scale, key)
        px = scale.step(current, steps)
        if px == current:
            return
        remember = getattr(self._window, "_remember_zoom", None)
        if callable(remember):
            remember(key, px)
        else:
            zoom = getattr(self._window, "_zoom", None)
            if isinstance(zoom, dict):
                zoom[key] = px
        self.changed.emit()

    @Slot()
    def zoomReset(self) -> None:
        pair = self._screen_zoom()
        if pair is None:
            return
        _scale, key = pair
        zoom = getattr(self._window, "_zoom", None)
        if not isinstance(zoom, dict) or key not in zoom:
            return
        del zoom[key]
        save = getattr(self._window, "_save_look", None)
        if callable(save):
            save()
        self.changed.emit()

    @Property(bool, notify=changed)
    def shortcuts(self) -> bool:
        """The number keys 1–5 switch screens, unless Settings turned that off."""
        return self._shortcuts

    @Property(bool, notify=changed)
    def letterKeys(self) -> bool:  # noqa: N802 - the name QML reads
        """P plans, Z undoes and F opens Focus, only when Settings turned that on. It starts off."""
        return self._letter_keys

    @Property(bool, constant=True)
    def later(self) -> bool:
        """Day, Month, and My day are part of this shell. The flag stays for older readers."""
        return True

    @Property(str, notify=changed)
    def screen(self) -> str:
        return self._screen

    @Property(int, notify=changed)
    def pageIndex(self) -> int:
        return SCREENS.index(self._screen)

    @Property(str, notify=changed)
    def density(self) -> str:
        return self._density

    @Property(bool, notify=changed)
    def reduceMotion(self) -> bool:
        return self._reduce_motion

    @Property(bool, notify=changed)
    def highContrast(self) -> bool:
        return self._contrast == "high"

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def theme(self) -> dict[str, Any]:
        return self._theme

    @Property(str, notify=changed)
    def snackText(self) -> str:
        return self._snack

    @Property(str, notify=changed)
    def snackAction(self) -> str:
        return self._snack_action

    def _kept_reminders(self) -> list[dict]:
        return list(getattr(self._window.session, "visible_reminders", lambda: [])())

    @Property(str, notify=changed)
    def reminderKey(self) -> str:
        """The reminder the card shows (the first one the session keeps), or "" when there is none."""
        kept = self._kept_reminders()
        return str(kept[0].get("key")) if kept else ""

    @Property(str, notify=changed)
    def reminderText(self) -> str:
        kept = self._kept_reminders()
        if not kept:
            return ""
        first = kept[0]
        body = first.get("body") or ""
        words = f"{first.get('title') or 'FlexWeek'}{' — ' + body if body else ''}"
        return words + (f"  (+{len(kept) - 1} more)" if len(kept) > 1 else "")

    @Slot()
    def _follow_reminders(self) -> None:
        kept = self._kept_reminders()
        keys = {str(item.get("key")) for item in kept}
        spoken = getattr(self._window, "_toast_reads", "")
        fresh = [
            words
            for words in (
                f"{item.get('title') or 'FlexWeek'}{' — ' + item['body'] if item.get('body') else ''}"
                for item in kept
                if str(item.get("key")) not in self._announced_reminders
            )
            if words not in spoken
        ]
        self._announced_reminders = keys
        self.changed.emit()
        if fresh and getattr(self._window, "_surface", "") == "material":
            # Said once, politely, without moving the keyboard. The toast reads a new reminder itself.
            announce(cast("Any", self._window), "; ".join(fresh))

    @Slot(str)
    def snoozeReminder(self, key: str) -> None:
        self._window.session.snooze_reminder(key)

    @Slot(str)
    def closeReminder(self, key: str) -> None:
        self._window.session.close_reminder(key)

    @Property(str, notify=changed)
    def title(self) -> str:
        if self._screen == "myday":
            return "My day"
        if self._screen == "settings":
            return "Settings"
        session = self._window.session
        if session.account is None or not session.week_start:
            return "FlexWeek"
        view = self._screen if self._screen in ("day", "week", "month") else "week"
        return planner_title(session, view)

    @Property(str, notify=changed)
    def clockText(self) -> str:
        session = self._window.session
        moment = datetime.fromtimestamp(session.now_ms() / 1000)
        return clock_label(moment.hour * 60 + moment.minute)

    @Property(bool, notify=changed)
    def canUndo(self) -> bool:
        return bool(self._window.session.can_undo())

    @Property(bool, notify=changed)
    def canRedo(self) -> bool:
        return bool(self._window.session.can_redo())

    @Property(int, notify=homeworkChanged)
    def homeworkCount(self) -> int:
        return self._week.homeworkCount

    @Property(QObject, constant=True)
    def week(self) -> QObject:
        return self._week

    @Property(QObject, constant=True)
    def day(self) -> QObject:
        return self._day

    @Property(QObject, constant=True)
    def month(self) -> QObject:
        return self._month

    @Property(QObject, constant=True)
    def myday(self) -> QObject:
        return self._myday

    @Property(QObject, constant=True)
    def account(self) -> QObject:
        return self._account

    @Property(QObject, constant=True)
    def sheets(self) -> QObject:
        return self._sheets

    @Property(QObject, constant=True)
    def settingsBridge(self) -> QObject:
        return self._settings_bridge

    @Property(QObject, constant=True)
    def focus(self) -> QObject:
        return self._focus

    @Property(QObject, constant=True)
    def blocks(self) -> QObject:
        return self._week.blocks

    @Property(QObject, constant=True)
    def homework(self) -> QObject:
        return self._week.homework

    @Property(QObject, constant=True)
    def days(self) -> QObject:
        return self._week.days

    @Property(QObject, constant=True)
    def hours(self) -> QObject:
        return self._week.hours

    @Property("QVariantList", notify=blocksChanged)  # type: ignore[arg-type]
    def blockRows(self) -> list:
        return self._week.blockRows

    @Property("QVariantList", notify=homeworkChanged)  # type: ignore[arg-type]
    def homeworkRows(self) -> list:
        return self._week.homeworkRows

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def dayHeaders(self) -> list:
        return self._week.dayHeaders

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def hourLabels(self) -> list:
        return self._week.hourLabels

    @Property(int, notify=changed)
    def nowDay(self) -> int:
        return self._week.nowDay

    @Property(int, notify=changed)
    def nowMinute(self) -> int:
        return self._week.nowMinute

    def note(self, text: str, *, action: str = "UNDO") -> None:
        """One snackbar line. Day uses it after a homework check."""
        self._snack = text
        self._snack_action = action
        self._snack_target = text
        self._snack_remaining_ms = SNACK_MS
        if not text:
            self._snack_timer.stop()
            self._snack_paused = False
        else:
            if self._snack_held:
                self._snack_paused = True
                self._snack_timer.stop()
            else:
                self._snack_paused = False
                self._snack_timer.start(SNACK_MS)
        self.changed.emit()

    def _on_snack_timeout(self) -> None:
        self._clear_snack(self._snack_target)

    def _clear_snack(self, text: str) -> None:
        # A newer line, or Undo, has already replaced this one.
        if self._snack == text:
            self._snack = ""
            self._snack_timer.stop()
            self._snack_paused = False
            self._snack_held = False
            self.changed.emit()

    @Slot()
    def pauseSnack(self) -> None:
        self._snack_held = True
        self._snack_paused = True
        if self._snack_timer.isActive():
            self._snack_remaining_ms = max(0, self._snack_timer.remainingTime())
            self._snack_timer.stop()

    @Slot()
    def resumeSnack(self) -> None:
        self._snack_held = False
        if self._snack_paused:
            self._snack_paused = False
            if self._snack:
                self._snack_timer.start(max(1000, self._snack_remaining_ms))

    @Slot()
    def undo(self) -> None:
        if self._snack:
            self._snack = ""
            self._snack_timer.stop()
            self._snack_paused = False
            self._snack_held = False
        self._window.session.undo()
        self.refresh()

    @Slot()
    def plan(self) -> None:
        """P in the shell. The same plan the week button runs."""
        self._window._plan_with_left_over()

    def reload_material(self) -> None:
        """Read the look file again and publish it. Settings calls this after it writes."""
        from desktop.native.material.host import appearance_of

        mode, contrast_name = appearance_of(self._window)
        self.set_appearance(mode, contrast_name)
        self.refresh()

    @Slot()
    def redo(self) -> None:
        self._window.session.redo()

    @Slot()
    def openMore(self) -> None:
        self._sheets.openMore()

    @Slot()
    def addHomework(self) -> None:
        self._sheets.openHomework()

    @Slot()
    def useWidgets(self) -> None:
        self.widgetsRequested.emit()

    @Slot()
    def showWeek(self) -> None:
        self.showPage("week")

    @Slot()
    def showSettings(self) -> None:
        self.showPage("settings")

    @Slot(str)
    def showPage(self, name: str) -> None:
        self.open_page(name)

    def open_page(self, name: str, today: bool = True) -> None:
        """Change screen. Day from the rail opens on today; Month's Open Day passes today=False."""
        if name not in SCREENS or name == self._screen:
            return
        session = self._window.session
        to_today = today and name == "day"
        if name == "month":
            self._month.activate()
        elif not to_today and getattr(session, "planner_view", None) == "month" and name == "week":
            # Week leaves the month through the session. Day opens today's week itself: leaving
            # through the month anchor first would load that month's week and win the race.
            session.set_view(name)
        self._screen = name
        if name == "myday":
            self._myday.ensure_today()
        elif to_today:
            self._day.ensure_today()
        self.changed.emit()
