"""Today's app's Day and Week, as Daily Scheduler draws them.

Day is one full-width day at 96 pixels an hour that scrolls, with the homework still waiting for a
time and a summary of the day beside it. Week is seven columns at 48 pixels an hour that scroll,
with the day's name kept at the top so it still opens that day. Both are painted hours on the one
`Hand`, so every gesture works the same on each.
"""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from desktop.native.calendar import CATEGORIES, DAYS
from desktop.native.hours.canvas import BlockPainter, HoursCanvas
from desktop.native.hours.chips import TrayChip
from desktop.native.hours.geometry import FIRST, LAST, LinearTrack
from desktop.native.hours.hand import Hand
from desktop.native.weekmodel import WeekModel, length_label

DAY_HOUR_PX = 96
WEEK_HOUR_PX = 48
PAD = 8
NAME_H = 30
GUTTER = 52


def _hours_height(px_per_hour: int) -> int:
    return round((LAST - FIRST) / 60 * px_per_hour) + 2 * PAD


class DayName(QLabel):
    """A day's name above the week. Kept out of the scroll so it stays reachable."""

    clicked = Signal(int)

    def __init__(self, day: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day = day
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._day)
            event.accept()
            return
        super().mousePressEvent(event)


def _seven_columns(area: QRectF) -> list[LinearTrack]:
    width = area.width() / 7
    return [
        LinearTrack(day, QRectF(area.left() + day * width, area.top() + PAD, width, area.height() - 2 * PAD))
        for day in range(7)
    ]


class ClassicWeek(QWidget):
    """The week as a scrollable overview, names fixed at the top, still drags."""

    day_opened = Signal(int)

    def __init__(self, hand: Hand, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("weekTable")
        self.week_start = ""
        self._revealed: str | None = None
        self._now_min: int | None = None
        self._needs_scroll = False
        self.hours = HoursCanvas(
            hand, BlockPainter({}), _seven_columns, gutter=GUTTER, header=0, names=self._name
        )
        self.hours.setObjectName("weekHours")
        self.hours.setFixedHeight(_hours_height(WEEK_HOUR_PX))
        self.hours.day_opened.connect(self.day_opened.emit)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("weekScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.hours)
        self.names = QWidget()
        self.names.setObjectName("weekDayNames")
        self.names.setFixedHeight(NAME_H)
        row = QHBoxLayout(self.names)
        row.setContentsMargins(GUTTER, 0, 0, 0)
        row.setSpacing(0)
        self._name_btns: list[DayName] = []
        for day in range(7):
            name = DayName(day)
            name.setObjectName(f"weekDayName{day}")
            name.setText(DAYS[day])
            name.clicked.connect(self.day_opened.emit)
            row.addWidget(name)
            self._name_btns.append(name)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        box.addWidget(self.names)
        box.addWidget(self.scroll, 1)

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)
        if self._needs_scroll:
            self._needs_scroll = False
            self._scroll_toward_now()

    def _name(self, day: int) -> str:
        if not self.week_start:
            return DAYS[day]
        return f"{DAYS[day]} {(date.fromisoformat(self.week_start) + timedelta(days=day)).day}"

    def _scroll_toward_now(self) -> None:
        minute = self._now_min if self._now_min is not None else 8 * 60
        top = max(minute - 90, FIRST)
        self.scroll.verticalScrollBar().setValue(round((top - FIRST) / 60 * WEEK_HOUR_PX))

    def set_look(self, look: dict | None, palette: dict) -> None:
        self.hours.set_painter(BlockPainter(palette, look))

    def set_week(self, week: WeekModel, today: int | None, now_min: int | None) -> None:
        self.week_start = week.week_start
        self._now_min = now_min
        self.hours.set_week(week.occurrences, today, now_min)
        for day, btn in enumerate(self._name_btns):
            btn.setText(self._name(day))
        if week.week_start != self._revealed:
            self._revealed = week.week_start
            self._needs_scroll = True
            self._scroll_toward_now()

    def hours_surfaces(self) -> list[HoursCanvas]:
        return [self.hours]


class ClassicDay(QWidget):
    """One day, full width, with what still needs a time and what the day holds beside it."""

    def __init__(self, hand: Hand, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dayView")
        self.hand = hand
        self.day = 0
        self._revealed: tuple[str, int] | None = None
        self.hours = HoursCanvas(hand, BlockPainter({}), self._one_column, gutter=56)
        self.hours.setObjectName("dayHours")
        self.hours.setFixedHeight(_hours_height(DAY_HOUR_PX))
        self.scroll = QScrollArea()
        self.scroll.setObjectName("dayScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.hours)
        self.side = QFrame()
        self.side.setObjectName("daySide")
        self.side.setFixedWidth(250)
        side = QVBoxLayout(self.side)
        side.setContentsMargins(12, 12, 12, 12)
        side.setSpacing(6)
        waiting = QLabel("Not placed yet")
        waiting.setObjectName("dayWaitingLabel")
        side.addWidget(waiting)
        self.tray = QVBoxLayout()
        self.tray.setSpacing(6)
        side.addLayout(self.tray)
        self.tray_hint = QLabel(
            "Drag one onto the day to give it that time, or drag on empty time to add something."
        )
        self.tray_hint.setObjectName("dayWaitingHint")
        self.tray_hint.setWordWrap(True)
        side.addWidget(self.tray_hint)
        summary = QLabel("Summary")
        summary.setObjectName("daySummaryLabel")
        side.addWidget(summary)
        self.summary = QLabel()
        self.summary.setObjectName("daySummary")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        side.addWidget(self.summary)
        side.addStretch(1)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.scroll, 1)
        row.addWidget(self.side)

    def _one_column(self, area: QRectF) -> list[LinearTrack]:
        return [LinearTrack(self.day, area.adjusted(0, PAD, -PAD, -PAD))]

    def set_look(self, look: dict | None, palette: dict) -> None:
        self.hours.set_painter(BlockPainter(palette, look))

    def set_day(self, week: WeekModel, day: int, today: int | None, now_min: int | None) -> None:
        changed_day = day != self.day
        self.day = day
        if changed_day:
            self.hours.relayout()
        self.hours.set_week([item for item in week.occurrences if item.day == day], today, now_min)
        self._fill_tray(week)
        self._fill_summary(week, day)
        key = (week.week_start, day)
        if key != self._revealed:
            self._revealed = key
            items = week.on_day(day)
            minute = (
                now_min
                if today == day and now_min is not None
                else min((item.start for item in items), default=8 * 60)
            )
            top = max(minute - 90, FIRST)
            self.scroll.verticalScrollBar().setValue(round((top - FIRST) / 60 * DAY_HOUR_PX))

    def _fill_tray(self, week: WeekModel) -> None:
        if self.hand.busy:
            # Rebuilding would delete the chip the pointer is holding. The release refreshes.
            return
        while self.tray.count():
            widget = self.tray.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for index, waiting in enumerate(week.waiting):
            chip = TrayChip(self.hand, waiting)
            chip.setObjectName(f"dayWaiting{index}")
            chip.clicked.connect(lambda _=False, key=waiting.block_id: self.hand.open(key))
            self.tray.addWidget(chip)
        self.tray_hint.setVisible(bool(week.waiting))

    def _fill_summary(self, week: WeekModel, day: int) -> None:
        totals: dict[str, int] = {}
        for item in week.on_day(day):
            name = CATEGORIES.get(item.category, {}).get("label") or ("Homework" if item.work else "Other")
            totals[name] = totals.get(name, 0) + item.minutes
        lines = [f"{name}: {length_label(minutes)}" for name, minutes in totals.items()]
        self.summary.setText("\n".join(lines) if lines else "Nothing planned.")

    def hours_surfaces(self) -> list[HoursCanvas]:
        return [self.hours]
