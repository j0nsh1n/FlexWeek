"""The only way the Material shell reads the week: through NativeSession.

QML calls the slots. It does not touch HTTP, SQL, or the engine. Prompts that
belong to the Widgets week (the one-shot plan review and the unfinished list)
are not taken here. A refresh of this surface must not consume them.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any, Protocol, cast

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    Signal,
    Slot,
)

from desktop.native.material.theme import DENSITY, paint_for_category, scheme, stroke_for
from desktop.native.reuse import planner_title
from desktop.native.weekmodel import clock_label, set_clock_24h


class _Session(Protocol):
    account: dict | None
    preferences: dict | None
    week_start: str
    blocks: list
    assignments: Any
    trace: Any

    def now_ms(self) -> int: ...

    def can_undo(self) -> bool: ...

    def can_redo(self) -> bool: ...

    def undo(self) -> None: ...

    def redo(self) -> None: ...

    def homework_time_needed(self) -> list: ...

    def built_week(self) -> Any: ...


class _Window(Protocol):
    session: _Session

    def _add_homework(self) -> None: ...

    def _look_inputs(self) -> tuple: ...

    def _worn_look(self) -> dict: ...

    def open_material_more(self) -> None: ...


DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_LATER_PAGES = {"day": 2, "month": 3, "myday": 4}
_BLOCK_ROLES = ("title", "day", "start", "end", "fill", "ink")
_HOMEWORK_ROLES = ("title", "minutes")


class _Rows(QAbstractListModel):
    """Rows the shell's repeaters can read. A Python list of dicts is not a model Qt Quick will build."""

    def __init__(self, roles: tuple[str, ...], parent: QObject) -> None:
        super().__init__(parent)
        self._names = {
            Qt.ItemDataRole.UserRole + 1 + index: name for index, name in enumerate(roles)
        }
        self._roles = {role: QByteArray(name.encode("ascii")) for role, name in self._names.items()}
        self._rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        name = self._names.get(role)
        if name is None or not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()].get(name)

    def roleNames(self) -> dict[int, QByteArray]:
        return self._roles


class _Labels(QAbstractListModel):
    """One string a row, as the role `label`."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._rows: list[str] = []

    def set_rows(self, rows: list[str]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if role != Qt.ItemDataRole.UserRole + 1 or not index.isValid():
            return None
        if not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()]

    def roleNames(self) -> dict[int, QByteArray]:
        return {Qt.ItemDataRole.UserRole + 1: QByteArray(b"label")}


class MaterialBridge(QObject):
    """Week rows, the clock, and the few actions the shell can take."""

    changed = Signal()
    blocksChanged = Signal()
    homeworkChanged = Signal()
    widgetsRequested = Signal()

    def __init__(self, window: QObject) -> None:
        super().__init__(window)
        self.setObjectName("materialBridge")
        self._window = cast(_Window, window)
        self._mode = "light"
        self._contrast = "std"
        self._colours: dict[str, str] = scheme("Blue", "light", "std")
        self._page = 0
        self._block_rows: list[dict] = []
        self._homework_rows: list[dict] = []
        self._day_headers: list[str] = []
        self._hour_labels: list[str] = [clock_label(hour * 60) for hour in range(24)]
        self._blocks = _Rows(_BLOCK_ROLES, self)
        self._homework = _Rows(_HOMEWORK_ROLES, self)
        self._days = _Labels(self)
        self._hours = _Labels(self)
        self._hours.set_rows(self._hour_labels)
        self._now_day = -1
        self._now_minute = 0
        self._later = os.environ.get("FLEXWEEK_MATERIAL_LATER") == "1"

    def set_appearance(self, mode: str, contrast_name: str) -> None:
        self._mode = mode if mode in ("light", "dark") else "light"
        self._contrast = contrast_name if contrast_name in ("std", "high") else "std"
        self._colours = scheme("Blue", self._mode, self._contrast)

    def refresh(self) -> None:
        """Read the session again. Does not consume a Widgets prompt."""
        session = self._window.session
        prefs = session.preferences or {}
        set_clock_24h(bool(prefs.get("clock_24h")))
        self._hour_labels = [clock_label(hour * 60) for hour in range(24)]
        self._block_rows = []
        self._homework_rows = []
        self._day_headers = []
        self._now_day = -1
        self._now_minute = 0
        if session.account is None or not session.week_start:
            self._publish_rows()
            return
        start = date.fromisoformat(session.week_start)
        self._day_headers = [
            f"{DAYS[index]} {(start + timedelta(days=index)).day}" for index in range(7)
        ]
        model = session.built_week()
        for item in model.occurrences:
            fill, ink = paint_for_category(item.category, self._mode)
            self._block_rows.append(
                {
                    "title": item.title,
                    "day": int(item.day),
                    "start": int(item.start),
                    "end": int(item.end),
                    "fill": fill,
                    "ink": ink,
                }
            )
        for item in session.homework_time_needed():
            title = item.get("title")
            if isinstance(title, str) and title:
                self._homework_rows.append({"title": title, "minutes": int(item.get("minutes") or 0)})
        moment = datetime.fromtimestamp(session.now_ms() / 1000)
        today = moment.date()
        if start <= today <= start + timedelta(days=6):
            self._now_day = (today - start).days
            self._now_minute = moment.hour * 60 + moment.minute
        self._publish_rows()

    def _publish_rows(self) -> None:
        self._blocks.set_rows(self._block_rows)
        self._homework.set_rows(self._homework_rows)
        self._days.set_rows(self._day_headers)
        self._hours.set_rows(self._hour_labels)
        self.blocksChanged.emit()
        self.homeworkChanged.emit()
        self.changed.emit()

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

    @Property(int, constant=True)
    def hourRow(self) -> int:
        return int(DENSITY["comfortable"]["hour_row"])

    @Property(bool, constant=True)
    def later(self) -> bool:
        return self._later

    @Property(int, notify=changed)
    def pageIndex(self) -> int:
        return self._page

    @Property(str, notify=changed)
    def title(self) -> str:
        session = self._window.session
        if session.account is None:
            return "FlexWeek"
        return planner_title(session, "week")

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
        return len(self._homework_rows)

    @Property(QObject, constant=True)
    def blocks(self) -> QObject:
        return self._blocks

    @Property(QObject, constant=True)
    def homework(self) -> QObject:
        return self._homework

    @Property(QObject, constant=True)
    def days(self) -> QObject:
        return self._days

    @Property(QObject, constant=True)
    def hours(self) -> QObject:
        return self._hours

    @Property("QVariantList", notify=blocksChanged)  # type: ignore[arg-type]
    def blockRows(self) -> list:
        return self._block_rows

    @Property("QVariantList", notify=homeworkChanged)  # type: ignore[arg-type]
    def homeworkRows(self) -> list:
        return self._homework_rows

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def dayHeaders(self) -> list:
        return self._day_headers

    @Property("QVariantList", notify=changed)  # type: ignore[arg-type]
    def hourLabels(self) -> list:
        return self._hour_labels

    @Property(int, notify=changed)
    def nowDay(self) -> int:
        return self._now_day

    @Property(int, notify=changed)
    def nowMinute(self) -> int:
        return self._now_minute

    @Slot()
    def undo(self) -> None:
        self._window.session.undo()

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
        self._page = 0
        self.changed.emit()

    @Slot()
    def showSettings(self) -> None:
        self._page = 1
        self.changed.emit()

    @Slot(str)
    def showPage(self, name: str) -> None:
        """Day, Month and My day stay unreachable unless FLEXWEEK_MATERIAL_LATER=1."""
        if not self._later:
            return
        page = _LATER_PAGES.get(name)
        if page is None:
            return
        self._page = page
        self.changed.emit()
