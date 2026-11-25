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
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, cast

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from desktop.native import fields
from desktop.native.fields import week_start_day, week_start_notice
from desktop.native.hours.scale import Scale
from desktop.native.material.bridge_account import AccountBridge
from desktop.native.material.bridge_alarms import RingBridge
from desktop.native.material.bridge_day import DayBridge
from desktop.native.material.bridge_focus import FocusBridge
from desktop.native.material.bridge_month import MonthBridge
from desktop.native.material.bridge_myday import MyDayBridge
from desktop.native.material.bridge_settings import SettingsBridge
from desktop.native.material.bridge_sheets import SheetsBridge
from desktop.native.material.bridge_week import WeekBridge
from desktop.native.material.theme import (
    DAY_SIDE_DEFAULT,
    DAY_SIDE_RANGE,
    DEFAULT_CONTRAST,
    DEFAULT_DENSITY,
    DEFAULT_PRESET,
    MOTION_SPEED_PACE,
    accented,
    advanced_default,
    dress_theme,
    hour_row_px,
    kept_material,
    mode_of,
    pack_material,
    read_accent,
    read_advanced,
    read_day_side_width,
    read_font,
    read_letter_keys,
    read_look_tier,
    read_material_choice,
    read_saved_material,
    read_settings_nav_width,
    read_shortcuts,
    scheme,
    store_material,
    stroke_for,
    theme_object,
)
from desktop.native.motion_level import LEVELS, moves
from desktop.native.reuse import planner_title
from desktop.native.weekmodel import clock_label

# Keys 1–5, and the StackLayout order. Week is the screen a new shell opens on.
SCREENS = ("day", "week", "month", "myday", "settings")
OPEN_ON = ("week", "day", "month", "myday")
SNACK_MS = 10000
# How often the seconds on Undo and the shrinking line are read, and the window's presence checked.
SNACK_TICK_MS = 100
WEEK_ZOOM = Scale("material.week", (32, 44, 56, 72, 96, 128, 192, 256), 56)
DAY_ZOOM = Scale("material.day", (32, 44, 56, 72, 96, 128, 192, 256), 56)


class _Session(Protocol):
    account: dict | None
    preferences: dict | None
    week_start: str

    def now_ms(self) -> int: ...

    def can_undo(self) -> bool: ...

    def can_redo(self) -> bool: ...

    pending_save: dict | None
    conflict: bool
    busy: bool

    def retry_save(self) -> None: ...

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
    snackClockChanged = Signal()
    homeworkChanged = Signal()

    def __init__(self, window: QObject) -> None:
        super().__init__(window)
        self.setObjectName("materialBridge")
        # Set before scheme() so a failed build can still dispose() this half-made bridge.
        self._week_follow = None
        self._window = cast(_Window, window)
        self._screen = "week"
        self._opened_for: str | None = None
        self._snack = ""
        self._snack_action = "UNDO"
        self._snack_target = ""
        self._snack_paused = False
        self._snack_held = False
        self._snack_remaining_ms = SNACK_MS
        self._snack_callback: Callable[[], None] | None = None
        # The notice's clock follows the session's clock, so the seconds on Undo and the shrinking line
        # agree with it; the wall timer below still ends the notice.
        self._snack_deadline = 0
        self._snack_away = False
        self._snack_timer = QTimer(self)
        self._snack_timer.setSingleShot(True)
        self._snack_timer.setInterval(SNACK_MS)
        self._snack_timer.timeout.connect(self._on_snack_timeout)
        self._snack_tick = QTimer(self)
        self._snack_tick.setInterval(SNACK_TICK_MS)
        self._snack_tick.timeout.connect(self._on_snack_tick)
        self._preset = DEFAULT_PRESET
        self._mode = "light"
        self._contrast = DEFAULT_CONTRAST
        self._density = DEFAULT_DENSITY
        self._reduce_motion = False
        self._motion_pace = 1.0
        self._motion_reach = 1.0
        self._advanced = advanced_default()
        self._shortcuts = True
        self._letter_keys = False
        self._font = ""
        self._day_side_width = DAY_SIDE_DEFAULT
        self._colours = scheme(DEFAULT_PRESET, "light", DEFAULT_CONTRAST)
        self._theme = theme_object(self._colours, self._density, False, False)
        self._week = WeekBridge(window, self)
        self._day = DayBridge(window, self)
        self._month = MonthBridge(window, self)
        self._myday = MyDayBridge(window, self)
        self._settings_bridge = SettingsBridge(self)
        self._account = AccountBridge(window)
        self._account.setParent(self)
        self._account.use_settings(self._settings_bridge)
        self._focus = FocusBridge(window, self)
        self._sheets = SheetsBridge(window, self)
        self._ring = RingBridge(self)
        self._following = False
        strip = getattr(window, "alert_strip", None)
        if strip is not None:
            strip.changed.connect(self.changed)
        cards = getattr(window.session, "reminder_cards", None)
        if cards is not None:
            cards.changed.connect(self.changed)
            cards.shown.connect(lambda words: fields.announce(self._window, words))
        week_start_notice().changed.connect(self._on_week_start)
        # Save finishes on this signal. The day lists and the Undo button read it then,
        # rather than waiting for the 20s clock tick.
        changed = getattr(self._window.session, "week_changed", None)
        if changed is not None and hasattr(changed, "connect"):
            changed.connect(self._follow_week)
            self._week_follow = changed
        finished = getattr(self._window.session, "save_finished", None)
        self._save_follow = None
        if finished is not None and hasattr(finished, "connect"):
            finished.connect(self._on_save_finished)
            self._save_follow = finished

    def set_appearance(self, mode: str, _worn_contrast: str) -> None:
        """Apply the saved Material look. `mode` is the light or dark the device or Material's own
        choice gives (appearance_of). Material's contrast is its own saved one."""
        stored = self._stored_look()
        choice = read_material_choice(stored)
        self._advanced = read_advanced(stored)
        self._shortcuts = read_shortcuts(stored)
        self._letter_keys = read_letter_keys(stored)
        self._day_side_width = read_day_side_width(stored)
        worn_dark = mode == "dark"
        resolved = mode_of(choice, worn_dark)
        self._font = read_font(stored)
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

    def _open_on_saved_screen(self) -> None:
        """Open on the screen "Open on" names, once per sign-in. A later change in Settings waits for the
        next sign-in, so it never moves a student who is already somewhere."""
        session = self._window.session
        account = session.account
        if account is None:
            self._opened_for = None
            return
        prefs = session.preferences
        if prefs is None or self._opened_for == str(account["id"]):
            return
        self._opened_for = str(account["id"])
        wanted = prefs.get("preferred_view")
        if wanted in OPEN_ON:
            self.open_page(wanted)

    def refresh(self) -> None:
        """Read the session again. Does not consume a Widgets prompt."""
        self._open_on_saved_screen()
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
        finished = getattr(self, "_save_follow", None)
        self._save_follow = None
        if finished is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                finished.disconnect(self._on_save_finished)

    def _on_save_finished(self, ok: bool, message: str) -> None:
        """A save that failed says so in the snackbar with a Retry button, and the top bar keeps a
        Retry save button for as long as the changes wait. A save that worked takes the Retry away."""
        if not ok:
            if self._window.session.pending_save is not None:
                self.note(message, action="RETRY")
            return
        if self._snack_action == "RETRY":
            self._clear_snack(self._snack)
        self.changed.emit()

    def _publish_theme(self) -> None:
        level = self._motion_level()
        self._reduce_motion = not moves(level)
        self._motion_pace = LEVELS[level].pace * MOTION_SPEED_PACE.get(self._advanced.get("motion"), 1.0)
        self._motion_reach = LEVELS[level].reach
        prefs = self._window.session.preferences or {}
        accent = read_accent(prefs)
        colours = accented(self._colours, accent, self._preset, self._mode, self._contrast)
        self._theme = dress_theme(
            theme_object(
                colours,
                self._density,
                self._reduce_motion,
                self._contrast == "high",
                prefs.get("accent_chips") is True,
            ),
            self._advanced,
            self._preset,
            self._font,
        )

    def _motion_level(self) -> str:
        """The Animations level in force: the student's choice, else the window's (the look's own). The
        advanced page's Motion speed Off is the Off level."""
        if self._advanced.get("motion") == "Off":
            return "off"
        chosen = (self._window.session.preferences or {}).get("motion")
        if chosen in LEVELS:
            return str(chosen)
        level = getattr(self._window, "_motion", "normal")
        return str(level) if level in LEVELS else "normal"

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

    def _on_week_start(self, _value: str) -> None:
        self.changed.emit()

    @Property(int, notify=changed)
    def firstWeekday(self) -> int:  # noqa: N802 — QML name
        """The day weeks start on, 0 Monday to 6 Sunday: the small months start their rows on it."""
        return week_start_day()

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
        """T, D, W, M, J, K, C, P, Z and F, only when Settings turned that on. It starts off."""
        return self._letter_keys

    @Property(int, notify=changed)
    def daySideWidth(self) -> int:  # noqa: N802 - the name QML reads
        """Remembered width of the Day right sidebar (Now card + mini month)."""
        return self._day_side_width

    @Slot(int)
    def setDaySideWidth(self, width: int) -> None:  # noqa: N802 - the name QML calls
        low, high = DAY_SIDE_RANGE
        clamped = max(low, min(high, int(width)))
        if clamped == self._day_side_width:
            return
        self._day_side_width = clamped
        path = self._window._look_path()
        stored = self._stored_look()
        kept = kept_material(path)
        if kept is not None:
            store_material(path, {**kept, "daySideWidth": clamped})
        else:
            material = pack_material(
                read_material_choice(stored),
                read_advanced(stored),
                read_shortcuts(stored),
                read_letter_keys(stored),
                read_saved_material(stored),
                read_font(stored),
                read_look_tier(stored),
                day_side_width=clamped,
                settings_nav_width=read_settings_nav_width(stored),
            )
            store_material(path, material)
        self.changed.emit()

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

    @Property(float, notify=changed)
    def motionPace(self) -> float:
        return self._motion_pace

    @Property(float, notify=changed)
    def motionReach(self) -> float:
        return self._motion_reach

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

    @Property(str, notify=changed)
    def alertText(self) -> str:
        """A reminder the student asked to keep on screen until they deal with it, from the window's strip."""
        strip = getattr(self._window, "alert_strip", None)
        return strip.text() if strip is not None and strip.pending() else ""

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def reminderCards(self) -> list[dict[str, str]]:  # noqa: N802 - the name QML reads
        """Reminders kept on screen, newest first, each with its title, body and key."""
        cards = getattr(self._window.session, "reminder_cards", None)
        return cards.cards() if cards is not None else []

    @Slot(str)
    def snoozeReminder(self, key: str) -> None:  # noqa: N802
        """Snooze: the card hides and comes back later, never after its block starts."""
        self._window.session.reminder_cards.snooze(key)

    @Slot(str)
    def closeReminder(self, key: str) -> None:  # noqa: N802
        self._window.session.reminder_cards.close(key)

    @Slot()
    def dismissAlert(self) -> None:
        """Got it: the strip's own button, so one reminder goes at a time and its snackbar line with it."""
        strip = getattr(self._window, "alert_strip", None)
        if strip is not None:
            strip.drop()

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
    def retryShown(self) -> bool:
        """Changes are waiting after a failed save and Retry save can send them."""
        session = self._window.session
        return session.pending_save is not None and not session.conflict

    @Property(bool, notify=changed)
    def retryEnabled(self) -> bool:
        return self.retryShown and not self._window.session.busy

    @Slot()
    def retrySave(self) -> None:
        """Retry save: the same call as the Widgets button. Ctrl+S flushes the same waiting changes."""
        if self._snack_action == "RETRY":
            self._clear_snack(self._snack)
        self._window.session.retry_save()
        self.changed.emit()

    @Slot()
    def snackActed(self) -> None:
        if self._snack_action == "RETRY":
            self.retrySave()
        elif self._snack_callback is not None:
            act = self._snack_callback
            self._clear_snack(self._snack)
            act()
        else:
            self.undo()

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
    def ring(self) -> QObject:
        return self._ring

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
    def nowColumn(self) -> int:
        return self._week.nowColumn

    @Property(int, notify=changed)
    def nowMinute(self) -> int:
        return self._week.nowMinute

    def note(self, text: str, *, action: str = "UNDO", on_action: Callable[[], None] | None = None) -> None:
        """One snackbar line. `on_action` is what its button does; Undo and Retry need none."""
        said_before = self._snack
        self._snack = text
        self._snack_action = action
        self._snack_callback = on_action
        self._snack_target = text
        self._snack_remaining_ms = SNACK_MS
        self._snack_away = self._window_away()
        if not text:
            self._snack_timer.stop()
            self._snack_tick.stop()
            self._snack_paused = False
        else:
            if self._snack_held or self._snack_away:
                self._snack_paused = True
                self._snack_timer.stop()
            else:
                self._snack_paused = False
                self._snack_deadline = self._now() + SNACK_MS
                self._snack_timer.start(SNACK_MS)
            self._snack_tick.start()
            if text != said_before:
                # Said once, politely, when it appears; a screen reader does not repeat it as the
                # seconds on Undo count down.
                fields.announce(self._window, text)
        self.changed.emit()
        self.snackClockChanged.emit()

    def bump_snack(self) -> None:
        """The same notice said again: its time starts over, nothing is announced."""
        if not self._snack:
            return
        self._snack_remaining_ms = SNACK_MS
        if self._snack_paused:
            self.snackClockChanged.emit()
            return
        self._snack_deadline = self._now() + SNACK_MS
        self._snack_timer.start(SNACK_MS)
        self.snackClockChanged.emit()

    def _now(self) -> int:
        return int(self._window.session.now_ms())

    def _window_away(self) -> bool:
        """The window is hidden, minimised or not the one in front: the notice waits for the student."""
        window = self._window
        return (
            not window.isVisible()  # type: ignore[attr-defined]
            or window.isMinimized()  # type: ignore[attr-defined]
            or not window.isActiveWindow()  # type: ignore[attr-defined]
        )

    def _snack_left_ms(self) -> int:
        if not self._snack:
            return 0
        if self._snack_paused:
            return max(0, self._snack_remaining_ms)
        left = min(SNACK_MS, self._snack_deadline - self._now())
        if self._snack_timer.isActive():
            # The wall timer can be shorter than the session's clock says (a notice resumed late).
            left = min(left, self._snack_timer.remainingTime())
        return max(0, left)

    def _on_snack_tick(self) -> None:
        if not self._snack:
            self._snack_tick.stop()
            return
        away = self._window_away()
        if away != self._snack_away:
            self._snack_away = away
            self._apply_snack_hold()
        elif not self._snack_paused and self._snack_left_ms() <= 0:
            self._clear_snack(self._snack_target)
            return
        self.snackClockChanged.emit()

    def _apply_snack_hold(self) -> None:
        """The clock waits while the pointer or keyboard is on the notice or the window is away, and
        starts again, with at least a second left, when none of them is."""
        hold = self._snack_held or self._snack_away
        if hold and not self._snack_paused:
            self._snack_remaining_ms = self._snack_left_ms()
            self._snack_timer.stop()
            self._snack_paused = True
        elif not hold and self._snack_paused and self._snack:
            self._snack_paused = False
            self._snack_remaining_ms = max(1000, self._snack_remaining_ms)
            self._snack_deadline = self._now() + self._snack_remaining_ms
            self._snack_timer.start(self._snack_remaining_ms)

    @Property(int, notify=snackClockChanged)
    def snackSeconds(self) -> int:
        """Whole seconds left, as the Undo button shows them."""
        return (self._snack_left_ms() + 999) // 1000

    @Property(float, notify=snackClockChanged)
    def snackFraction(self) -> float:
        """How much of the notice's time is left, for the line along its bottom."""
        return self._snack_left_ms() / SNACK_MS

    def _on_snack_timeout(self) -> None:
        self._clear_snack(self._snack_target)

    def _clear_snack(self, text: str) -> None:
        # A newer line, or Undo, has already replaced this one.
        if self._snack == text:
            self._snack = ""
            self._snack_callback = None
            self._snack_timer.stop()
            self._snack_tick.stop()
            self._snack_paused = False
            self._snack_held = False
            self.changed.emit()
            self.snackClockChanged.emit()

    @Slot()
    def pauseSnack(self) -> None:
        self._snack_held = True
        self._apply_snack_hold()

    @Slot()
    def resumeSnack(self) -> None:
        self._snack_held = False
        self._apply_snack_hold()

    @Slot()
    def undo(self) -> None:
        if self._snack:
            self._clear_snack(self._snack)
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
    def openHelp(self) -> None:
        self._window._open_help()  # type: ignore[attr-defined]

    @Slot()
    def addFixedTime(self) -> None:
        self._sheets.openBlock()

    @Slot()
    def openWeekList(self) -> None:
        """Ctrl+Shift+L: the same sheet as More's Week as a list."""
        self._sheets.openWeekList()

    @Slot()
    def addHomework(self) -> None:
        self._sheets.openHomework()

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
        if self._screen == "settings" and name != "settings":
            self._settings_bridge.leave_settings()
        self._screen = name
        if name == "myday":
            self._myday.ensure_today()
        elif to_today:
            self._day.ensure_today()
        self.changed.emit()
