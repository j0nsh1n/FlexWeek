"""The week screen's rows. Later week work stays in this file.

The core bridge calls `reload` and re-emits the signals the shell already listens
for. This object does not touch HTTP, SQL, or the engine. It reads NativeSession.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Protocol

from PySide6.QtCore import Property, QObject, Signal

from desktop.native.material.bridge_rows import Labels, Rows
from desktop.native.material.theme import event_category, paint_for_category
from desktop.native.weekmodel import clock_label, range_label, set_clock_24h

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
BLOCK_ROLES = ("title", "day", "start", "end", "fill", "ink", "category", "detail", "past")
HOMEWORK_ROLES = ("title", "minutes")


class _Session(Protocol):
    account: dict | None
    preferences: dict | None
    week_start: str

    def now_ms(self) -> int: ...

    def homework_time_needed(self) -> list: ...

    def built_week(self) -> Any: ...


class _Window(Protocol):
    session: _Session


class WeekBridge(QObject):
    """Blocks, day headers, hour labels, and homework that still needs a time."""

    changed = Signal()
    blocksChanged = Signal()
    homeworkChanged = Signal()

    def __init__(self, window: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("weekBridge")
        self._window = window
        self._block_rows: list[dict] = []
        self._homework_rows: list[dict] = []
        self._day_headers: list[str] = []
        self._hour_labels: list[str] = [clock_label(hour * 60) for hour in range(24)]
        self._blocks = Rows(BLOCK_ROLES, self)
        self._homework = Rows(HOMEWORK_ROLES, self)
        self._days = Labels(self)
        self._hours = Labels(self)
        self._hours.set_rows(self._hour_labels)
        self._now_day = -1
        self._now_minute = 0

    def reload(self, mode: str) -> None:
        """Read the session again. Does not consume a Widgets prompt."""
        session = self._window.session  # type: ignore[attr-defined]
        prefs = session.preferences or {}
        set_clock_24h(bool(prefs.get("clock_24h")))
        self._hour_labels = [clock_label(hour * 60) for hour in range(24)]
        self._block_rows = []
        self._homework_rows = []
        self._day_headers = []
        self._now_day = -1
        self._now_minute = 0
        if session.account is None or not session.week_start:
            self._publish()
            return
        start = date.fromisoformat(session.week_start)
        self._day_headers = [f"{DAYS[index]} {(start + timedelta(days=index)).day}" for index in range(7)]
        moment = datetime.fromtimestamp(session.now_ms() / 1000)
        today = moment.date()
        if start <= today <= start + timedelta(days=6):
            self._now_day = (today - start).days
            self._now_minute = moment.hour * 60 + moment.minute
        for item in session.built_week().occurrences:
            fill, ink = paint_for_category(item.category, mode)
            day = int(item.day)
            end = int(item.end)
            past = self._now_day >= 0 and (
                day < self._now_day or (day == self._now_day and end <= self._now_minute)
            )
            self._block_rows.append(
                {
                    "title": item.title,
                    "day": day,
                    "start": int(item.start),
                    "end": end,
                    "fill": fill,
                    "ink": ink,
                    "category": event_category(item.category),
                    "detail": range_label(int(item.start), end),
                    "past": past,
                }
            )
        for item in session.homework_time_needed():
            title = item.get("title")
            if isinstance(title, str) and title:
                self._homework_rows.append({"title": title, "minutes": int(item.get("minutes") or 0)})
        self._publish()

    def _publish(self) -> None:
        self._blocks.set_rows(self._block_rows)
        self._homework.set_rows(self._homework_rows)
        self._days.set_rows(self._day_headers)
        self._hours.set_rows(self._hour_labels)
        self.blocksChanged.emit()
        self.homeworkChanged.emit()
        self.changed.emit()

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

    @Property(int, notify=homeworkChanged)
    def homeworkCount(self) -> int:
        return len(self._homework_rows)
