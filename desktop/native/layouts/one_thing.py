"""One thing: a day screen. The whole window is the thing that is on now, or next if nothing is.

It deliberately cannot plan. Its value is that it shows less, so the only way out is back to planning.
It can move the day's own blocks, though: drag one along the day bar, or drag the thing itself onto
it, to put it later, as Running late does.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QProgressBar, QVBoxLayout, QWidget

from desktop.native.calendar import DAY_FULL
from desktop.native.layouts.base import (
    LayoutView,
    Scene,
    base_sheet,
    day_buttons,
    empty,
    label,
    rules,
)
from desktop.native.layouts.drag import Carried, Mark, Pickup, Spot, Verdict, Zone, liftable, snap
from desktop.native.weekmodel import Occurrence, clock_label, length_label

DAY_START, DAY_END = 6 * 60, 22 * 60


class DayBar(QWidget):
    """The day as one thin bar: every block a segment, the chosen one in the accent, now as a tick.
    A segment can be dragged along it to a new time, and a block dropped on it goes at that time."""

    block_clicked = Signal(str)

    def __init__(self, day: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("oneDayBar")
        self.setFixedHeight(22)
        self._day = day
        self._blocks: tuple[Occurrence, ...] = ()
        self._chosen: Occurrence | None = None
        self._minute: int | None = None
        self._colours = ("#2a2a2a", "#6b6b6b", "#fb923c", "#ffffff")
        self._ghost_colours = ("#fb923c", "#ef4444")
        self._drop: Verdict | None = None
        self._pickup = Pickup(self, self.block_at, self.block_clicked.emit, self.minute_at)

    def set_day(
        self,
        blocks: tuple[Occurrence, ...],
        chosen: Occurrence | None,
        minute: int | None,
        tokens: dict[str, str],
    ) -> None:
        self._blocks, self._chosen, self._minute = blocks, chosen, minute
        self._colours = (tokens["line"], tokens["bg_muted"], tokens["accent"], tokens["bg_ink"])
        self._ghost_colours = (tokens["accent"], tokens["danger"])
        self.setAccessibleName(f"Today from {clock_label(DAY_START)} to {clock_label(DAY_END)}")
        self.update()

    def _x(self, minute: int) -> float:
        share = (min(max(minute, DAY_START), DAY_END) - DAY_START) / (DAY_END - DAY_START)
        return share * self.width()

    def minute_at(self, spot: QPointF) -> int:
        share = min(max(spot.x() / max(self.width(), 1), 0.0), 1.0)
        return round(DAY_START + share * (DAY_END - DAY_START))

    def block_at(self, spot: QPointF) -> Occurrence | None:
        return next(
            (item for item in self._blocks if self._x(item.start) <= spot.x() <= self._x(item.end)), None
        )

    def set_drop(self, verdict: Verdict | None) -> None:
        self._drop = verdict
        self.update()

    def where(self, point: QPoint, thing: Carried) -> tuple[Spot, Mark]:
        return Spot(self._day, snap(self.minute_at(QPointF(point)) - thing.grab)), Mark(paint=self.set_drop)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._pickup.press(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._pickup.move(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._pickup.release(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        track, other, chosen, tick = (QColor(colour) for colour in self._colours)
        painter = QPainter(self)
        painter.fillRect(QRectF(0, 6, self.width(), 10), track)
        for item in self._blocks:
            left, right = self._x(item.start), self._x(item.end)
            painter.fillRect(
                QRectF(left, 6, max(right - left, 2), 10), chosen if item == self._chosen else other
            )
        if self._minute is not None:
            painter.fillRect(QRectF(self._x(self._minute) - 1.5, 0, 3, 22), tick)
        drop = self._drop
        if drop is not None and drop.start is not None and drop.end is not None:
            colour = QColor(self._ghost_colours[0 if drop.ok else 1])
            left, right = self._x(drop.start), self._x(drop.end)
            painter.setPen(QPen(colour, 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(left, 2, max(right - left, 4), 18))
        painter.end()


class OneThingView(LayoutView):
    # The day bar is the day's hours, so a block is dropped on it rather than in a drawer.
    uses_drawer = False
    layout_id = "one"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._skip = 0
        self._title = label("", "oneTitle", wrap=True)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(30, 22, 30, 22)

    def _queue(self, scene: Scene) -> tuple[tuple[Occurrence, ...], Occurrence | None]:
        if scene.today is None:
            return (), None
        found = scene.week.day_queue(scene.today, scene.minute)
        if scene.options.get("lead") == "next" and found.current is not None:
            return found.queue[1:], None
        return found.queue, found.current

    def render(self, scene: Scene, week_changed: bool) -> None:
        if week_changed:
            self._skip = 0
        tokens = scene.tokens
        queue, current = self._queue(scene)
        self._skip = min(self._skip, max(len(queue) - 1, 0))
        item = queue[self._skip] if queue else None
        is_now = item is not None and item == current
        self.setStyleSheet(
            base_sheet(self.objectName(), tokens)
            + rules(
                self.objectName(),
                {
                    "#oneDate, #oneLeft, #oneThen, #oneHint": f"color: {tokens['bg_muted']};"
                    f" font-size: {scene.px(15)}px; letter-spacing: 2px;",
                    "#oneLabel": f"color: {tokens['accent']}; font-size: {scene.px(26)}px;"
                    " font-weight: 700; letter-spacing: 5px;",
                    "#oneTitle": f"color: {tokens['bg_ink']}; font-weight: 800;",
                    "#oneLine": f"color: {tokens['accent']}; font-size: {scene.px(40)}px; font-weight: 700;",
                    "#oneProgress": f"background: {tokens['line']}; border: none; border-radius: 0;"
                    f" max-height: {scene.px(6)}px; min-height: {scene.px(6)}px; padding: 0;",
                    "#oneProgress::chunk": f"background: {tokens['accent']};",
                    "QPushButton": f"background: {tokens['bg']}; color: {tokens['bg_ink']};"
                    f" border: 2px solid {tokens['bg_ink']}; border-radius: 0; padding: 0 {scene.px(22)}px;"
                    f" min-height: {scene.px(48)}px; font-size: {scene.px(15)}px; font-weight: 600;"
                    " letter-spacing: 2px;",
                    'QPushButton[kind="main"]': f"background: {tokens['accent']};"
                    f" color: {tokens['accent_ink']}; border-color: {tokens['accent']};",
                    "QPushButton:focus": f"border: 3px solid {tokens['accent']};",
                },
            )
        )
        empty(self._root)
        self._title = label("", "oneTitle", wrap=True)
        top = QHBoxLayout()
        when = (
            "Another week"
            if scene.today is None
            else f"{DAY_FULL[scene.today]} {scene.week.date_of(scene.today).day}"
        )
        top.addWidget(label(f"{when} · {clock_label(scene.minute)}".upper(), "oneDate"))
        top.addStretch()
        top.addWidget(label(self._left_text(scene).upper(), "oneLeft"))
        self._root.addLayout(top)
        self._root.addStretch(1)
        heading, line = self._words(scene, item, is_now, current is not None)
        self._root.addWidget(label(heading.upper(), "oneLabel"))
        self._title.setText((item.title if item else self._empty_title(scene)).upper())
        if item is not None:
            self._title.setAccessibleDescription("Press Enter to open it")
            # The thing itself can be dragged onto the day bar, to a later time.
            liftable(self._title, item.block_id)
        self._root.addWidget(self._title)
        self._root.addWidget(label(line.upper(), "oneLine", wrap=True))
        if is_now and item is not None:
            progress = QProgressBar()
            progress.setObjectName("oneProgress")
            progress.setTextVisible(False)
            progress.setRange(0, max(item.minutes, 1))
            progress.setValue(scene.minute - item.start)
            progress.setMaximumWidth(scene.px(720))
            progress.setAccessibleName(
                f"{round((scene.minute - item.start) / max(item.minutes, 1) * 100)} percent through"
            )
            self._root.addSpacing(scene.px(14))
            self._root.addWidget(progress)
        self._root.addSpacing(scene.px(24))
        self._root.addLayout(self._actions(scene, item))
        self._root.addStretch(1)
        if scene.options.get("daybar") != "hide" and scene.today is not None:
            bar = DayBar(scene.today)
            bar.set_day(scene.week.on_day(scene.today), item, scene.minute, tokens)
            bar.block_clicked.connect(self.block_activated.emit)
            Zone(self, bar, bar.where)
            self._root.addWidget(bar)
        foot = QHBoxLayout()
        then = queue[self._skip + 1 : self._skip + 3]
        said = ", ".join(f"{entry.title} {clock_label(entry.start)}" for entry in then)
        foot.addWidget(label(("Then: " + (said or "nothing")).upper(), "oneThen"))
        foot.addStretch()
        foot.addWidget(label("SPACE: WHAT COMES AFTER · B: BACK TO PLANNING", "oneHint"))
        self._root.addLayout(foot)
        self._fit_title()

    def _left_text(self, scene: Scene) -> str:
        if scene.today is None:
            return ""
        return f"{length_label(scene.week.minutes_left_today(scene.today, scene.minute))} left today"

    def _empty_title(self, scene: Scene) -> str:
        if scene.today is None:
            return "Day screens show today"
        return scene.week.leftover_parts(scene.today)[1]

    def _words(
        self, scene: Scene, item: Occurrence | None, is_now: bool, has_current: bool
    ) -> tuple[str, str]:
        if scene.today is None:
            return "Not this week", "Go back to planning and open this week to see today."
        if item is None:
            heading, _title, line = scene.week.leftover_parts(scene.today)
            tomorrow = scene.week.on_day(scene.today + 1)
            if (
                scene.week.leftover_kind(scene.today) == "calendar_only"
                and scene.today < 6
                and tomorrow
            ):
                line = f"Tomorrow starts with {tomorrow[0].title} at {clock_label(tomorrow[0].start)}"
            return heading, line or heading
        if is_now:
            return "Now", f"until {clock_label(item.end)} · {length_label(item.end - scene.minute)} left"
        first_upcoming = 1 if has_current else 0
        heading = "Up next" if self._skip == first_upcoming else "Later today"
        return heading, f"{clock_label(item.start)} · in {length_label(item.start - scene.minute)}"

    def _actions(self, scene: Scene, item: Occurrence | None) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(scene.px(10))
        for entry in day_buttons(self, scene, item, "one", upper=True):
            row.addWidget(entry)
        row.addStretch()
        return row

    def _fit_title(self) -> None:
        """As large as the window allows, and never so large that a wrapped line is cut off.

        The room is measured, not guessed: a word-wrapped label asks for one line as its minimum, so the
        layout squeezed the title rather than anything else and its second line vanished.
        """
        scale = self._scene.scale if self._scene else 1.0
        size = round(min(max(self.width() * 0.085, 44), 124) * scale)
        self._title.setMinimumHeight(0)
        self._title.ensurePolished()
        self._root.invalidate()
        others = self._root.totalMinimumSize().height() - self._title.minimumSizeHint().height()
        font = QFont(self._title.font())
        font.setWeight(QFont.Weight.ExtraBold)
        margins = self._root.contentsMargins()
        width = max(self.width() - margins.left() - margins.right(), 200)
        room = max(self.height() - others - 8, 40)
        needed = room
        while True:
            font.setPixelSize(size)
            needed = (
                QFontMetrics(font)
                .boundingRect(QRect(0, 0, width, 10_000), int(Qt.TextFlag.TextWordWrap), self._title.text())
                .height()
            )
            if needed <= room or size <= 22:
                break
            size -= 4
        self._title.setStyleSheet(f"font-size: {size}px;")
        self._title.setMinimumHeight(needed)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_title()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        scene = self._scene
        if scene is not None and event.key() == Qt.Key.Key_Space:
            queue, _ = self._queue(scene)
            self._skip = 0 if self._skip + 1 >= len(queue) else self._skip + 1
            self.render(scene, False)
            event.accept()
            return
        if scene is not None and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            queue, _ = self._queue(scene)
            if queue:
                self.block_activated.emit(queue[self._skip].block_id)
                event.accept()
                return
        super().keyPressEvent(event)
