"""One thing: a day screen. The whole window is the thing that is on now, or next if nothing is.

It deliberately cannot plan. Its value is that it shows less, so the only way out is back to planning.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeyEvent, QPainter, QPaintEvent, QResizeEvent
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
    work_left,
)
from desktop.native.weekmodel import Occurrence, clock_label, length_label

DAY_START, DAY_END = 6 * 60, 22 * 60


class DayBar(QWidget):
    """The day as one thin bar: every block a segment, the chosen one in the accent, now as a tick."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("oneDayBar")
        self.setFixedHeight(22)
        self._blocks: tuple[Occurrence, ...] = ()
        self._chosen: Occurrence | None = None
        self._minute: int | None = None
        self._colours = ("#2a2a2a", "#6b6b6b", "#fb923c", "#ffffff")

    def set_day(
        self,
        blocks: tuple[Occurrence, ...],
        chosen: Occurrence | None,
        minute: int | None,
        tokens: dict[str, str],
    ) -> None:
        self._blocks, self._chosen, self._minute = blocks, chosen, minute
        self._colours = (tokens["line"], tokens["bg_muted"], tokens["accent"], tokens["bg_ink"])
        self.setAccessibleName(f"Today from {clock_label(DAY_START)} to {clock_label(DAY_END)}")
        self.update()

    def _x(self, minute: int) -> float:
        share = (min(max(minute, DAY_START), DAY_END) - DAY_START) / (DAY_END - DAY_START)
        return share * self.width()

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
        painter.end()


class OneThingView(LayoutView):
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
            bar = DayBar()
            bar.set_day(scene.week.on_day(scene.today), item, scene.minute, tokens)
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
        return "" if scene.today is None else f"{length_label(work_left(scene))} left today"

    def _empty_title(self, scene: Scene) -> str:
        return "Day screens show today" if scene.today is None else "Nothing else today"

    def _words(
        self, scene: Scene, item: Occurrence | None, is_now: bool, has_current: bool
    ) -> tuple[str, str]:
        if scene.today is None:
            return "Not this week", "Go back to planning and open this week to see today."
        if item is None:
            tomorrow = scene.week.on_day(scene.today + 1)
            if scene.today < 6 and tomorrow:
                return (
                    "Done for today",
                    f"Tomorrow starts with {tomorrow[0].title} at {clock_label(tomorrow[0].start)}",
                )
            return "Done for today", "The rest of the day is yours"
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
