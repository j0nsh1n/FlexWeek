"""The only way the Material shell reads the week: through NativeSession.

QML calls the slots. It does not touch HTTP, SQL, or the engine. Prompts that
belong to the Widgets week (the one-shot plan review and the unfinished list)
are not taken here. A refresh of this surface must not consume them.

Each screen has its own bridge module. This file is the core: navigation, the
theme object, and the slots every screen shares. Week rows live in bridge_week.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, cast

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from desktop.native.material.bridge_day import DayBridge
from desktop.native.material.bridge_month import MonthBridge
from desktop.native.material.bridge_myday import MyDayBridge
from desktop.native.material.bridge_settings import SettingsBridge
from desktop.native.material.bridge_week import WeekBridge
from desktop.native.material.theme import (
    DEFAULT_CONTRAST,
    DEFAULT_DENSITY,
    DEFAULT_PRESET,
    DENSITY,
    read_material_choice,
    resolved_mode,
    scheme,
    stroke_for,
    theme_object,
)
from desktop.native.reuse import planner_title
from desktop.native.weekmodel import clock_label

# Keys 1–5, and the StackLayout order. Week is the screen a new shell opens on.
SCREENS = ("day", "week", "month", "myday", "settings")
SNACK_MS = 6000


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

    def _add_homework(self) -> None: ...

    def _look_path(self) -> Path: ...

    def open_material_more(self) -> None: ...


class MaterialBridge(QObject):
    """Navigation, the theme object, and the few actions the shell can take."""

    changed = Signal()
    blocksChanged = Signal()
    homeworkChanged = Signal()
    widgetsRequested = Signal()

    def __init__(self, window: QObject) -> None:
        super().__init__(window)
        self.setObjectName("materialBridge")
        self._window = cast(_Window, window)
        self._screen = "week"
        self._snack = ""
        self._preset = DEFAULT_PRESET
        self._mode = "light"
        self._contrast = DEFAULT_CONTRAST
        self._density = DEFAULT_DENSITY
        self._reduce_motion = False
        self._colours = scheme(DEFAULT_PRESET, "light", DEFAULT_CONTRAST)
        self._theme = theme_object(self._colours, self._density, False, False)
        self._week = WeekBridge(window, self)
        self._day = DayBridge(window, self)
        self._month = MonthBridge(self)
        self._myday = MyDayBridge(window, self)
        self._settings_bridge = SettingsBridge(self)
        self._following = False
        # Save finishes on this signal. The day lists and the Undo button read it then,
        # rather than waiting for the 20s clock tick.
        changed = getattr(self._window.session, "week_changed", None)
        if changed is not None and hasattr(changed, "connect"):
            changed.connect(self._follow_week)

    def set_appearance(self, mode: str, _worn_contrast: str) -> None:
        """Apply the saved Material look. `mode` is the worn light or dark axis.

        Follow system uses that axis. An explicit saved light or dark wins. The worn
        contrast is not Material's contrast: this shell stays standard unless its own
        saved contrast says high.
        """
        choice = read_material_choice(self._stored_look())
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

    def refresh(self) -> None:
        """Read the session again. Does not consume a Widgets prompt."""
        self._publish_theme()
        self._week.reload(self._mode)
        self._day.reload(self._mode)
        self._myday.reload(self._mode)
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

    def _publish_theme(self) -> None:
        self._reduce_motion = self._motion_reduced()
        self._theme = theme_object(
            self._colours, self._density, self._reduce_motion, self._contrast == "high"
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

    @Property(int, notify=changed)
    def hourRow(self) -> int:
        return int(DENSITY[self._density]["hour_row"])

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
    def settingsBridge(self) -> QObject:
        return self._settings_bridge

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

    def note(self, text: str) -> None:
        """One snackbar line. Day uses it after a homework check."""
        self._snack = text
        self.changed.emit()
        QTimer.singleShot(SNACK_MS, self, lambda: self._clear_snack(text))

    def _clear_snack(self, text: str) -> None:
        # A newer line, or Undo, has already replaced this one.
        if self._snack == text:
            self._snack = ""
            self.changed.emit()

    @Slot()
    def undo(self) -> None:
        if self._snack:
            self._snack = ""
        self._window.session.undo()
        self.refresh()

    @Slot()
    def redo(self) -> None:
        self._window.session.redo()

    @Slot()
    def openMore(self) -> None:
        self._window.open_material_more()

    @Slot()
    def addHomework(self) -> None:
        self._window._add_homework()

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
        if name not in SCREENS or name == self._screen:
            return
        self._screen = name
        self.changed.emit()
