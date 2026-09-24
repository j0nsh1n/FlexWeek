"""One thing: a day screen. The whole window is the thing that is on now, or next if nothing is.

It deliberately cannot plan. Its value is that it shows less, so the only way out is back to planning.
It can move the day's own blocks, though, through the window's hand: drag one along the day bar, or
drag the thing itself onto it, to put it later, as Running late does.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from desktop.native.calendar import DAY_FULL
from desktop.native.hours.canvas import BlockPainter, Drawn, HoursCanvas
from desktop.native.hours.geometry import Axis, LinearTrack, Span
from desktop.native.hours.hand import Gesture, Hand, Held
from desktop.native.layouts.base import (
    LayoutView,
    Scene,
    base_sheet,
    day_buttons,
    empty,
    label,
    rules,
)
from desktop.native.weekmodel import Occurrence, Waiting, clock_label, length_label

DAY_START, DAY_END = 6 * 60, 22 * 60
BAR_TALL = 22


def _small(font: QFont) -> QFont:
    """The words on the carried block's pill, a little under the bar's own font."""
    made = QFont(font)
    made.setPointSizeF(max(made.pointSizeF() * 0.86, 7))
    return made


class BarPainter(BlockPainter):
    """The day as one thin bar: every block a segment, the thing on screen in the accent, now as a
    tick. A carried block is drawn where it would land, outlined, with its words on a pill above."""

    def __init__(self, tokens: dict[str, str], chosen: str | None) -> None:
        super().__init__(
            {
                "track": tokens["line"],
                "other": tokens["bg_muted"],
                "accent": tokens["accent"],
                "accent_ink": tokens["accent_ink"],
                "error": tokens["danger"],
                "tick": tokens["bg_ink"],
            }
        )
        self.chosen = chosen
        self._middle = 0.0

    def background(self, painter: QPainter, rect: QRectF) -> None:
        pass

    def track(self, painter: QPainter, track: LinearTrack, today: bool) -> None:
        area = track.area
        self._middle = area.center().y()
        painter.fillRect(QRectF(area.left(), self._middle - 5, area.width(), 10), self.c("track"))

    def hour_labels(self, painter: QPainter, track: LinearTrack, room: float, every: int = 60) -> None:
        pass

    def block(self, painter: QPainter, rect: QRectF, drawn: Drawn, visible: QRectF) -> None:
        tall = min(10.0, rect.height())
        # On the bar, or in its share of the bar's height where blocks overlap.
        middle = self._middle if drawn.columns == 1 else rect.center().y()
        segment = QRectF(rect.left(), middle - tall / 2, max(rect.width(), 2), tall)
        if drawn.held:
            ok = drawn.verdict is None or drawn.verdict.ok
            colour = self.c("accent" if ok else "error")
            painter.fillRect(segment, colour)
            painter.setPen(QPen(colour, 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(segment.left(), segment.top() - 4, max(segment.width(), 4), tall + 8))
            return
        painter.fillRect(segment, self.c("accent" if drawn.block_id == self.chosen else "other"))

    def hint(self, painter: QPainter, rect: QRectF, big: bool) -> None:
        pass

    def now(self, painter: QPainter, track: LinearTrack, minute: int) -> None:
        area = track.area
        painter.fillRect(
            QRectF(area.left() + track.offset(minute) - 1.5, area.top(), 3, area.height()), self.c("tick")
        )

    def label(self, painter: QPainter, beside: QRectF, words: str, ok: bool, room: QRectF) -> None:
        """Above the carried segment, in the room left over the bar for it."""
        plain = _small(painter.font())
        metrics = QFontMetrics(plain)
        width, height = metrics.horizontalAdvance(words) + 20, metrics.height() + 10
        left = min(max(beside.center().x() - width / 2, room.left()), room.right() - width)
        pill = QRectF(left, max(beside.top() - 8 - height, room.top()), width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.c("accent" if ok else "error"))
        painter.drawRoundedRect(pill, height / 2, height / 2)
        painter.setPen(self.c("accent_ink"))
        painter.setFont(plain)
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, words)


class DayBar(HoursCanvas):
    """Today from 06:00 to 22:00 as one track across. A segment can be carried along it to a new
    time, and a tap on one opens it. Free time makes nothing: this screen does not plan."""

    block_clicked = Signal(str)

    def __init__(self, hand: Hand, day: int, tokens: dict[str, str], chosen: str | None) -> None:
        super().__init__(
            hand,
            BarPainter(tokens, chosen),
            lambda area: [LinearTrack(day, area, Axis.ACROSS, DAY_START, DAY_END)],
        )
        self.setObjectName("oneDayBar")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName(f"Today from {clock_label(DAY_START)} to {clock_label(DAY_END)}")
        self.setAccessibleDescription("Drag a block along the bar to move it, or click it to open it.")
        # Room over the bar for the carried block's words.
        self.header = QFontMetrics(_small(self.font())).height() + 18
        self.setFixedHeight(round(self.header) + BAR_TALL)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self._block_at(event.position())
        if hit is None:
            return
        drawn, _rect, track = hit
        span = drawn.span
        held = Held(
            Gesture.MOVE,
            drawn.title,
            span.minutes,
            drawn.block_id,
            span.day,
            span,
            round(track.minute_at(event.position()) - span.start),
        )
        self.hand.press(
            self,
            held,
            event.globalPosition().toPoint(),
            tap=lambda: self.block_clicked.emit(drawn.block_id),
            home=(self, track),
        )

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # The first click of the two has opened it already.
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self.hand.busy:
            over = self._block_at(event.position()) is not None
            self.setCursor(Qt.CursorShape.OpenHandCursor if over else Qt.CursorShape.ArrowCursor)


class Thing(QLabel):
    """The thing itself, as large as the window allows. Like a tray chip, it can be picked up and
    let go on the day bar: a block with a time moves there, homework with none is given that time."""

    def __init__(self, hand: Hand) -> None:
        super().__init__("")
        self.hand = hand
        self.held: Held | None = None
        self.setObjectName("oneTitle")
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)

    def carry(self, thing: Occurrence | Waiting | None) -> None:
        if isinstance(thing, Occurrence):
            span = Span(thing.day, thing.start, thing.end)
            self.held = Held(Gesture.MOVE, thing.title, thing.minutes, thing.block_id, thing.day, span)
        elif isinstance(thing, Waiting):
            self.held = Held(Gesture.PLACE, thing.title, thing.minutes, thing.block_id)
        else:
            self.held = None
        self.setProperty("block_id", self.held.block_id if self.held is not None else None)
        self.setCursor(Qt.CursorShape.OpenHandCursor if self.held is not None else Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.held is not None:
            self.hand.press(self, self.held, event.globalPosition().toPoint())
            return
        super().mousePressEvent(event)


class OneThingView(LayoutView):
    layout_id = "one"

    def __init__(self, parent: QWidget | None = None, *, hand: Hand | None = None) -> None:
        super().__init__(parent, hand=hand)
        self._skip = 0
        self._title = Thing(self.hand)
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
        self._title = Thing(self.hand)
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
        # The thing itself can be carried onto the day bar, to a later time.
        needs_time = scene.today is not None and scene.week.leftover_kind(scene.today) == "needs_time"
        self._title.carry(item or (scene.week.due_today_unplaced(scene.today)[0] if needs_time else None))
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
            bar = DayBar(self.hand, scene.today, tokens, item.block_id if item is not None else None)
            bar.set_week(scene.week.on_day(scene.today), scene.today, scene.minute)
            bar.block_clicked.connect(self.block_activated.emit)
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
