"""Mission control: a main view. Time runs sideways, days are lanes, and the risks sit beside them.

The lanes are painted, so a keyboard cannot walk them. The day row under the lanes is their twin: pick
a day and every block on it is a button that opens the same block.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from desktop.native.calendar import DAY_FULL, DAYS
from desktop.native.layouts.base import (
    LayoutView,
    Scene,
    base_sheet,
    block_button,
    button,
    css,
    empty,
    label,
    mark_of,
    plan_buttons,
    rules,
    scrolling,
)
from desktop.native.look import readable_ink
from desktop.native.weekmodel import Occurrence, WeekModel, clock_label, due_label

HOURS = {"day": (6 * 60, 22 * 60), "full": (0, 24 * 60)}
GUTTER, AXIS = 74, 20


class Lanes(QWidget):
    block_clicked = Signal(str)
    day_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("missionLanes")
        self.setMinimumHeight(230)
        self._week: WeekModel | None = None
        self._today: int | None = None
        self._minute = 0
        self._span = HOURS["day"]
        self._tokens: dict[str, str] = {}
        self._chosen = 0

    def set_week(
        self,
        week: WeekModel,
        today: int | None,
        minute: int,
        span: tuple[int, int],
        tokens: dict[str, str],
        chosen: int,
    ) -> None:
        self._week, self._today, self._minute, self._span, self._tokens, self._chosen = (
            week,
            today,
            minute,
            span,
            tokens,
            chosen,
        )
        self.setAccessibleName("The week as seven lanes. The day row below lists the same blocks as buttons.")
        self.update()

    def _x(self, minute: int) -> float:
        start, end = self._span
        share = (min(max(minute, start), end) - start) / (end - start)
        return GUTTER + share * (self.width() - GUTTER - 4)

    def _lane(self, day: int) -> QRectF:
        height = (self.height() - AXIS) / 7
        return QRectF(GUTTER, AXIS + day * height + 2, self.width() - GUTTER - 4, height - 4)

    def bar_rect(self, item: Occurrence) -> QRectF:
        lane = self._lane(item.day)
        left, right = self._x(item.start), self._x(item.end)
        return QRectF(left, lane.top() + 2, max(right - left, 3), lane.height() - 4)

    def _in_view(self, item: Occurrence) -> bool:
        """Clamped to the span, a block at 05:00 became a sliver at 06:00 that could be clicked: a lie
        about when it happens. What falls outside the hours shown is not drawn at all."""
        return item.end > self._span[0] and item.start < self._span[1]

    def block_at(self, spot: QPointF) -> Occurrence | None:
        if self._week is None:
            return None
        under = [
            item
            for item in self._week.occurrences
            if self._in_view(item) and self.bar_rect(item).contains(spot)
        ]
        under.sort(key=lambda item: not item.work)
        return under[0] if under else None

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        if self._week is None or not self._tokens:
            return
        tokens = self._tokens
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        small = QFont(self.font())
        small.setPixelSize(11)
        painter.setFont(small)
        metrics = QFontMetrics(small)
        step = 120 if self._span == HOURS["day"] else 180
        painter.setPen(QColor(tokens["bg_muted"]))
        for minute in range(self._span[0], self._span[1] + 1, step):
            # The last label is pulled in from the edge, where half of it was cut off.
            left = min(self._x(minute) - 20, self.width() - 42)
            painter.drawText(QRectF(left, 0, 40, AXIS), Qt.AlignmentFlag.AlignCenter, clock_label(minute))
        for day in range(7):
            lane = self._lane(day)
            painter.fillRect(lane, QColor(tokens["surface"]))
            painter.setPen(QColor(tokens["accent"] if day == self._today else tokens["bg_muted"]))
            name = f"{DAYS[day].upper()} {self._week.date_of(day).day}"
            mark = "› " if day == self._chosen else ""
            painter.drawText(
                QRectF(0, lane.top(), GUTTER - 8, lane.height()), Qt.AlignmentFlag.AlignVCenter, mark + name
            )
        for item in self._week.occurrences:
            if not self._in_view(item):
                continue
            box = self.bar_rect(item)
            fill = QColor(mark_of(item.category))
            if not item.live:
                painter.setPen(QPen(QColor(tokens["line"]), 1, Qt.PenStyle.DashLine))
                painter.setBrush(QColor(tokens["bg"]))
                ink = QColor(tokens["bg_muted"])
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(fill)
                ink = QColor(readable_ink(fill.name()))
            painter.drawRoundedRect(box, 3, 3)
            if box.width() > 34:
                painter.setPen(ink)
                words = metrics.elidedText(item.title, Qt.TextElideMode.ElideRight, int(box.width()) - 8)
                painter.drawText(box.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, words)
        if self._today is not None and self._span[0] <= self._minute <= self._span[1]:
            lane = self._lane(self._today)
            painter.setPen(QPen(QColor(tokens["danger"]), 2))
            painter.drawLine(
                QPointF(self._x(self._minute), lane.top() - 2),
                QPointF(self._x(self._minute), lane.bottom() + 2),
            )
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        found = self.block_at(event.position())
        if found is not None:
            self.block_clicked.emit(found.block_id)
        elif event.position().x() < GUTTER and event.position().y() > AXIS:
            self.day_clicked.emit(min(int((event.position().y() - AXIS) / ((self.height() - AXIS) / 7)), 6))


class MissionView(LayoutView):
    layout_id = "mission"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day: int | None = None
        # A view's minimum height must not become the window's: three designs pushed it past a 768 pixel
        # laptop screen. Inside a scroll area, what does not fit scrolls and the window keeps its size.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._page = QWidget()
        self._page.setObjectName("missionPage")
        self._root = QVBoxLayout(self._page)
        self._root.setContentsMargins(14, 10, 14, 10)
        outer.addWidget(scrolling(self._page, "missionScroll"))

    def shown_day(self, scene: Scene) -> int:
        return self._day if self._day is not None else (scene.today if scene.today is not None else 0)

    def _show_day(self, day: int) -> None:
        if self._scene is not None:
            self._day = None if day == self._scene.today else day
            self.render(self._scene, False)

    def render(self, scene: Scene, week_changed: bool) -> None:
        if week_changed:
            self._day = None
        tokens, name = scene.tokens, self.objectName()
        mono = "DejaVu Sans Mono, Noto Sans Mono, monospace"
        self.setStyleSheet(
            base_sheet(name, tokens)
            + rules(
                name,
                {
                    "#missionScroll, #missionPage": css(background=tokens["bg"]),
                    "QLabel": css(
                        font_size=f"{scene.px(12)}px", letter_spacing="1px", color=tokens["bg_muted"]
                    ),
                    "#missionTitle": css(
                        color=tokens["bg_ink"], font_size=f"{scene.px(15)}px", font_weight=800
                    ),
                    "#missionClock, #missionPlaced": css(
                        color=tokens["accent"], font_family=mono, font_weight=700
                    ),
                    "#missionSide": css(background=tokens["surface"], border=f"1px solid {tokens['line']}"),
                    "QPushButton": css(
                        background=tokens["surface"],
                        color=tokens["accent"],
                        border=f"1px solid {tokens['accent']}",
                        border_radius="0",
                        padding=f"0 {scene.px(12)}px",
                        min_height=f"{scene.px(34)}px",
                        font_family=mono,
                        font_size=f"{scene.px(12)}px",
                        font_weight=700,
                    ),
                    'QPushButton[kind="main"]': css(background=tokens["accent"], color=tokens["accent_ink"]),
                    'QPushButton[kind="row"], QPushButton[kind="chip"], QPushButton[kind="day"]': css(
                        color=tokens["text"],
                        border=f"1px solid {tokens['line']}",
                        text_align="left",
                        font_family="inherit",
                        font_weight=500,
                    ),
                    'QPushButton[kind="row"][risk="danger"]': css(
                        border_left=f"4px solid {tokens['danger']}"
                    ),
                    'QPushButton[kind="row"][risk="tight"]': css(border_left=f"4px solid {tokens['accent']}"),
                    'QPushButton[kind="day"][chosen="true"]': css(
                        border=f"1px solid {tokens['accent']}", color=tokens["accent"], font_weight=800
                    ),
                    'QPushButton[kind="chip"][state="past"]': css(
                        color=tokens["muted"], text_decoration="line-through"
                    ),
                    "QPushButton:focus": css(border=f"2px solid {tokens['bg_ink']}"),
                    'QFrame[role="load"]': css(background=tokens["accent"]),
                },
            )
        )
        empty(self._root)
        self._root.setSpacing(scene.px(8))
        week, day = scene.week, self.shown_day(scene)
        span = HOURS.get(scene.options.get("hours", "day"), HOURS["day"])
        placed = len({item.block_id for item in week.occurrences if item.work})
        head = QHBoxLayout()
        head.setSpacing(scene.px(16))
        head.addWidget(label(f"FLEXWEEK / WEEK {week.date_of(0).isocalendar().week}", "missionTitle"))
        head.addWidget(label(f"LOCAL {clock_label(scene.minute)}", "missionClock"))
        head.addWidget(label(f"PLAN {placed}/{placed + len(week.waiting)} PLACED", "missionPlaced"))
        head.addStretch(1)
        for made in plan_buttons(self, "mission", ("+ ADD", "RUN PLAN", "MY DAY")):
            head.addWidget(made)
        self._root.addLayout(head)
        if week.waiting:
            strip = QHBoxLayout()
            strip.addWidget(label("UNPLACED", "missionUnplaced"))
            for index, item in enumerate(week.waiting):
                made = block_button(
                    self, f"{item.title} · {item.reason}", f"missionWaiting{index}", item.block_id
                )
                made.setProperty("risk", "danger")
                strip.addWidget(made)
            strip.addStretch(1)
            self._root.addLayout(strip)
        body = QHBoxLayout()
        body.setSpacing(scene.px(12))
        left = QVBoxLayout()
        lanes = Lanes()
        lanes.set_week(week, scene.today, scene.minute, span, tokens, day)
        lanes.block_clicked.connect(self.block_activated.emit)
        lanes.day_clicked.connect(self._show_day)
        left.addWidget(lanes, 1)
        left.addLayout(self._day_row(scene, day))
        body.addLayout(left, 1)
        if scene.options.get("side") != "hide":
            body.addWidget(self._side(scene))
        self._root.addLayout(body, 1)

    def _day_row(self, scene: Scene, day: int) -> QVBoxLayout:
        holder = QVBoxLayout()
        picker = QHBoxLayout()
        picker.addWidget(label("DAY", "missionDayLabel"))
        for target, name in enumerate(DAYS):
            pick = button(f"{name.upper()} {scene.week.date_of(target).day}", f"missionDay{target}", "day")
            pick.setProperty("chosen", "true" if target == day else "false")
            pick.setProperty("day_target", target)
            pick.setAccessibleName(f"Show {DAY_FULL[target]}")
            pick.clicked.connect(lambda _=False, chosen=target: self._show_day(chosen))
            picker.addWidget(pick)
        picker.addStretch(1)
        holder.addLayout(picker)
        chips = QHBoxLayout()
        for index, item in enumerate(scene.week.on_day(day)):
            chip = block_button(
                self, f"{clock_label(item.start)} {item.title}", f"missionChip{index}", item.block_id, "chip"
            )
            over = (
                item.end <= scene.minute
                if day == scene.today
                else (scene.today is not None and day < scene.today)
            )
            chip.setProperty("state", "past" if over or not item.live else "")
            chips.addWidget(chip)
        if not scene.week.on_day(day):
            chips.addWidget(label("NOTHING ON THIS DAY", "missionDayEmpty"))
        chips.addStretch(1)
        holder.addLayout(chips)
        return holder

    def _side(self, scene: Scene) -> QFrame:
        side = QFrame()
        side.setObjectName("missionSide")
        side.setFixedWidth(scene.px(290))
        inner = QVBoxLayout(side)
        inner.setContentsMargins(scene.px(10), scene.px(10), scene.px(10), scene.px(10))
        inner.addWidget(label("DEADLINE RADAR", "missionRadarTitle"))
        work = scene.week.open_work()
        for index, item in enumerate(work):
            words = f"{item.title}\n{due_label(item.due, scene.week.week_start)}"
            if item.slack_words:
                words += f" · {item.slack_words.upper()}"
            row = block_button(self, words, f"missionRadar{index}", item.block_id)
            row.setProperty("risk", item.slack or "")
            row.setStyleSheet(f"min-height: {scene.px(40)}px;")
            inner.addWidget(row)
        if not work:
            inner.addWidget(label("ALL CLEAR", "missionRadarEmpty"))
        inner.addSpacing(scene.px(10))
        inner.addWidget(label("HOMEWORK LOAD / DAY", "missionLoadTitle"))
        bars = QHBoxLayout()
        most = max([scene.week.load_min(day) for day in range(7)] + [1])
        for day, name in enumerate(DAYS):
            column = QVBoxLayout()
            column.addStretch(1)
            bar = QFrame()
            bar.setProperty("role", "load")
            bar.setFixedHeight(max(round(scene.px(54) * scene.week.load_min(day) / most), 2))
            column.addWidget(bar)
            column.addWidget(label(name[0], f"missionLoad{day}"), 0, Qt.AlignmentFlag.AlignHCenter)
            bars.addLayout(column)
        inner.addLayout(bars)
        inner.addStretch(1)
        return side
