"""Retro desktop: live hours in movable windows, with deadlines in a notepad."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from desktop.native.calendar import DAY_FULL, DAYS
from desktop.native.hours.canvas import BlockPainter, Drawn, HoursCanvas
from desktop.native.hours.chips import TrayChip
from desktop.native.hours.geometry import FIRST, LAST, LinearTrack
from desktop.native.hours.hand import Hand
from desktop.native.hours.zoom import HoursScroll, Scale, opening_minute
from desktop.native.layouts.base import (
    LayoutView,
    Scene,
    base_sheet,
    button,
    css,
    empty,
    label,
    mark_of,
    plan_buttons,
    rules,
    scrolling,
)
from desktop.native.weekmodel import clock_label, due_label, length_label

DAY_SCALE = Scale("retro.day", (96, 128, 160, 192), 96)
WEEK_SCALE = Scale("retro.week", (48, 64, 80, 96), 64)
GUTTER = 56
PAD = 8
WINDOWS = (
    ("week", "Week.exe", QPoint(14, 6)),
    ("notes", "deadlines.txt", QPoint(850, 40)),
    ("next", "Up next", QPoint(850, 300)),
)


def _height(px: int) -> int:
    return round((LAST - FIRST) / 60 * px) + 2 * PAD


def _columns(area: QRectF) -> list[LinearTrack]:
    width = area.width() / 7
    return [
        LinearTrack(day, QRectF(area.left() + day * width, area.top() + PAD, width, area.height() - 2 * PAD))
        for day in range(7)
    ]


class RetroPainter(BlockPainter):
    """Square grid and bevelled bars, with shared block words and hour labels."""

    def __init__(self, tokens: dict[str, str]) -> None:
        super().__init__(
            {
                "window": tokens["surface"],
                "grid": tokens["line"],
                "hairline": tokens["line"],
                "accent": tokens["accent"],
                "accent_ink": tokens["accent_ink"],
                "error": tokens["danger"],
                "text": tokens["text"],
                "muted": tokens["muted"],
            }
        )
        self.tokens = tokens

    def track(self, painter: QPainter, track: LinearTrack, today: bool) -> None:
        painter.fillRect(track.area, QColor("#ffffff"))
        super().track(painter, track, today)
        painter.setPen(QPen(QColor(self.tokens["line"]), 1))
        painter.drawLine(track.area.topLeft(), track.area.bottomLeft())

    def block(self, painter: QPainter, rect: QRectF, drawn: Drawn, visible: QRectF) -> None:
        refused = drawn.verdict is not None and not drawn.verdict.ok
        face = QColor("#ffd0d0" if refused else self.tokens["surface"])
        if drawn.held and not refused:
            face = face.lighter(110)
        painter.fillRect(rect, face)
        bright = QColor(self.tokens["line"] if drawn.held else "#ffffff")
        dark = QColor("#ffffff" if drawn.held else self.tokens["line"])
        painter.setPen(QPen(bright, 2))
        painter.drawLine(rect.topLeft(), rect.topRight())
        painter.drawLine(rect.topLeft(), rect.bottomLeft())
        painter.setPen(QPen(dark, 2))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.fillRect(
            QRectF(rect.left() + 2, rect.top() + 2, 4, max(0.0, rect.height() - 4)),
            QColor(mark_of(drawn.category)),
        )
        if drawn.held or drawn.chosen:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(self.tokens["danger"] if refused else self.tokens["accent"]), 2))
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
        if drawn.columns > 1 and not drawn.held:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self.tokens["danger"]))
            painter.drawEllipse(QRectF(rect.right() - 10, rect.top() + 4, 7, 7))
        self.words(painter, rect, drawn, QColor(self.tokens["text"]), visible)


class RetroCanvas(HoursCanvas):
    """The week header sits outside the scroll, while the rig can find its day names."""

    def __init__(self, hand: Hand, painter: RetroPainter, *, week: bool) -> None:
        super().__init__(hand, painter, _columns if week else None, gutter=GUTTER)
        self.day_buttons: dict[int, QWidget] = {}

    def day_name(self, day: int) -> QPoint:
        pick = self.day_buttons.get(day)
        return pick.mapToGlobal(pick.rect().center()) if pick is not None else super().day_name(day)


class NoteLine(QPushButton):
    """A line of the notepad: a flag and a title, then when it is due. Short of room the date goes
    under the title, whole, and the title shortens only if it must, rather than the line running off
    the page."""

    def __init__(self, head: str, due: str, name: str) -> None:
        self._head, self._due = head, due
        super().__init__(f"{head}  {due}")
        self.setObjectName(name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("kind", "row")
        self.setProperty("mono", "true")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        fonts = self.fontMetrics()
        widest = max(fonts.horizontalAdvance(line) for line in self.text().split("\n"))
        room = max(self.width() - (super().sizeHint().width() - widest), 0)
        fitted = f"{self._head}  {self._due}"
        if fonts.horizontalAdvance(fitted) > room:
            # Under the title, in line with it past the flag.
            lines = (self._head, f"   {self._due}")
            fitted = "\n".join(fonts.elidedText(line, Qt.TextElideMode.ElideRight, room) for line in lines)
        if fitted != self.text():
            self.setText(fitted)
            self.updateGeometry()


class TitleBar(QLabel):
    """Dragging the title bar moves its window, kept inside the desktop."""

    def __init__(self, text: str, window: QFrame) -> None:
        super().__init__(text)
        self._window = window
        self._grab: QPoint | None = None
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._grab = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._grab is None:
            return
        desk = self._window.parentWidget()
        spot = event.globalPosition().toPoint() - self._grab
        limit_x = max(desk.width() - 60, 0) if desk is not None else spot.x()
        limit_y = max(desk.height() - 30, 0) if desk is not None else spot.y()
        self._window.move(min(max(spot.x(), 0), limit_x), min(max(spot.y(), 0), limit_y))
        self._window.setProperty("moved", True)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._grab = None


class RetroView(LayoutView):
    layout_id = "retro"

    def __init__(self, parent: QWidget | None = None, *, hand: Hand | None = None) -> None:
        super().__init__(parent, hand=hand)
        self._open: dict[str, bool] = {}
        self._spots: dict[str, QPoint] = {}
        self._opened_for = ""
        self._scrolls: dict[str, HoursScroll] = {}
        self._moved: set[str] = set()
        self.hand.preview_changed.connect(self._status)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._desk = QWidget()
        self._desk.setObjectName("retroDesk")
        self._desk.setMinimumSize(880, 470)
        self._surface = QWidget()
        self._surface.setObjectName("retroSurface")
        surface = QVBoxLayout(self._surface)
        surface.setContentsMargins(0, 0, 0, 0)
        surface.setSpacing(0)
        surface.addWidget(scrolling(self._desk, "retroScroll"), 1)
        self._bar = QFrame()
        self._bar.setObjectName("retroTaskbar")
        self._bar_row = QHBoxLayout(self._bar)
        self._bar_row.setContentsMargins(4, 3, 4, 3)
        surface.addWidget(self._bar)
        outer.addWidget(self._surface)

    def _shown_day(self, scene: Scene) -> int:
        if scene.surface == "day" and scene.iso_day:
            for day in range(7):
                if scene.week.date_of(day).isoformat() == scene.iso_day:
                    return day
        return scene.today if scene.today is not None else 0

    def _toggle(self, key: str) -> None:
        if self._scene is not None:
            self._open[key] = not self._open.get(key, False)
            self.render(self._scene, False)

    def render(self, scene: Scene, week_changed: bool) -> None:
        tokens, name = scene.tokens, self.objectName()
        wanted = scene.options.get("windows", "all")
        if wanted != self._opened_for:
            self._opened_for = wanted
            self._open = {key: wanted == "all" or key == "week" for key, _, _ in WINDOWS}
        raised = f"2px outset {tokens['line']}"
        self.setStyleSheet(
            base_sheet(name, tokens)
            + rules(
                name,
                {
                    "#retroScroll, #retroDesk": css(background=tokens["bg"]),
                    "#retroTaskbar": css(background=tokens["surface"], border_top=raised),
                    'QFrame[role="window"]': css(background=tokens["surface"], border=raised),
                    'QFrame[role="sunken"]': css(background="#ffffff", border=f"2px inset {tokens['line']}"),
                    "QLabel": css(color=tokens["text"], font_size=f"{scene.px(13)}px"),
                    'QLabel[role="title"]': css(
                        background=tokens["accent"],
                        color=tokens["accent_ink"],
                        font_weight=700,
                        padding=f"{scene.px(3)}px {scene.px(6)}px",
                    ),
                    'QLabel[role="today"]': css(font_weight=800),
                    "QPushButton": css(
                        background=tokens["surface"],
                        color=tokens["text"],
                        border=raised,
                        border_radius="0",
                        padding=f"{scene.px(2)}px {scene.px(10)}px",
                        min_height=f"{scene.px(24)}px",
                        font_size=f"{scene.px(13)}px",
                        font_weight=500,
                    ),
                    "QPushButton:pressed": css(border=f"2px inset {tokens['line']}"),
                    'QPushButton[kind="menu"], QPushButton[kind="main"]': css(
                        border="none", background="transparent"
                    ),
                    'QPushButton[kind="menu"]:hover, QPushButton[kind="main"]:hover': css(
                        background=tokens["accent"], color=tokens["accent_ink"]
                    ),
                    'QPushButton[kind="row"]': css(
                        background="#ffffff",
                        color="#000000",
                        border="none",
                        border_left="4px solid #808080",
                        text_align="left",
                        min_height=f"{scene.px(20)}px",
                    ),
                    'QPushButton[kind="row"][mono="true"]': css(font_family="DejaVu Sans Mono, monospace"),
                    'QPushButton[kind="day"]': css(padding="0", min_height=f"{scene.px(28)}px"),
                    'QPushButton[kind="day"][chosen="true"]': css(
                        border=f"2px inset {tokens['line']}", font_weight=800
                    ),
                    'QPushButton[tray="true"]': css(background="#ffffff", text_align="left"),
                    'QPushButton[zoom="true"]': css(min_height="0", padding="0"),
                    'QLabel#retroStatus[verdict="refused"]': css(color=tokens["danger"]),
                    'QPushButton[kind="task"][open="true"]': css(
                        border=f"2px inset {tokens['line']}", font_weight=700
                    ),
                    'QPushButton[kind="close"]': css(
                        padding="0", min_height="16px", max_height="16px", max_width="18px"
                    ),
                    "QPushButton:focus": css(border=f"2px dotted {tokens['text']}"),
                },
            )
        )
        for kept in self._scrolls.values():
            kept.hide()
            kept.setParent(self._desk)
        for child in self._desk.findChildren(QFrame, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if child.property("role") == "window":
                self._spots[child.objectName()] = child.pos()
                if child.property("moved"):
                    self._moved.add(child.objectName())
                child.setParent(None)
                child.deleteLater()
        builders = {"week": self._hours_window, "notes": self._notes_window, "next": self._next_window}
        for key, title, home in WINDOWS:
            if not self._open.get(key):
                continue
            if key == "week":
                title = self._main_title(scene)
            frame = self._frame(scene, key, title)
            builders[key](scene, frame.layout())
            frame.setParent(self._desk)
            if key == "week":
                frame.setFixedSize(self._main_width(), max(self._desk.height(), self.height() - 40) - 12)
            else:
                frame.setFixedWidth(self._side_width())
            frame.adjustSize()
            self._place(frame, home)
            frame.show()
        self._taskbar(scene)
        QTimer.singleShot(0, self._fit_windows)

    def _main_width(self) -> int:
        width = max(self.width(), self._desk.width())
        return min(round(width * 0.70), width - 280)

    def _side_width(self) -> int:
        return max(260, max(self.width(), self._desk.width()) - self._main_width() - 32)

    def _fit_windows(self) -> None:
        main = self.findChild(QFrame, "retroWindow-week")
        if main is not None:
            main.setFixedSize(self._main_width(), max(self._desk.height() - 12, 430))
            self._clamp(main)
        for key, top in (("notes", 40), ("next", 300)):
            frame = self.findChild(QFrame, f"retroWindow-{key}")
            if frame is None:
                continue
            frame.setFixedWidth(self._side_width())
            frame.adjustSize()
            if not frame.property("moved"):
                frame.move(self._main_width() + 20, top)
            else:
                self._clamp(frame)

    def _clamp(self, frame: QFrame) -> None:
        frame.move(
            min(max(frame.x(), 0), max(self._desk.width() - 60, 0)),
            min(max(frame.y(), 0), max(self._desk.height() - 30, 0)),
        )

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_desk"):
            QTimer.singleShot(0, self._fit_windows)

    def _main_title(self, scene: Scene) -> str:
        if scene.surface == "day":
            day = self._shown_day(scene)
            return f"Schedule.exe — {DAY_FULL[day]} {scene.week.date_of(day).day}"
        return f"Week.exe — {scene.week.date_of(0).day} to {scene.week.date_of(6).day}"

    def _place(self, frame: QFrame, home: QPoint) -> None:
        desk = self._desk
        if frame.objectName() in self._moved:
            spot = self._spots[frame.objectName()]
        elif frame.objectName() == "retroWindow-notes":
            spot = QPoint(self._main_width() + 20, 40)
        elif frame.objectName() == "retroWindow-next":
            spot = QPoint(self._main_width() + 20, 300)
        else:
            spot = home
        limit_x = max(desk.width() - 60, 0)
        limit_y = max(desk.height() - 30, 0)
        frame.move(min(max(spot.x(), 0), limit_x), min(max(spot.y(), 0), limit_y))

    def _frame(self, scene: Scene, key: str, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName(f"retroWindow-{key}")
        frame.setProperty("role", "window")
        frame.setProperty("moved", frame.objectName() in self._moved)
        body = QVBoxLayout(frame)
        body.setContentsMargins(3, 3, 3, 6)
        body.setSpacing(scene.px(5))
        head = QHBoxLayout()
        head.setSpacing(0)
        bar = TitleBar(title, frame)
        bar.setObjectName(f"retroTitle-{key}")
        bar.setProperty("role", "title")
        head.addWidget(bar, 1)
        close = button("x", f"retroClose-{key}", "close")
        close.setAccessibleName(f"Close {title}")
        close.clicked.connect(lambda _=False: self._toggle(key))
        head.addWidget(close)
        body.addLayout(head)
        return frame

    def _hours_window(self, scene: Scene, body: QVBoxLayout) -> None:
        menu = QHBoxLayout()
        for made in plan_buttons(self, "retro", "Add homework…"):
            made.setProperty("kind", "menu")
            menu.addWidget(made)
        menu.addStretch(1)
        body.addLayout(menu)
        is_day = scene.surface == "day"
        key = "day" if is_day else "week"
        if key not in self._scrolls:
            canvas = RetroCanvas(self.hand, RetroPainter(scene.tokens), week=not is_day)
            canvas.setObjectName("retroHours")
            canvas.day_opened.connect(
                lambda day: self.day_activated.emit(self.scene.week.date_of(day).isoformat())
            )
            scroll = self.keep_zoom(
                HoursScroll(
                    canvas,
                    DAY_SCALE if is_day else WEEK_SCALE,
                    _height,
                    name="retroDay" if is_day else "retroWeek",
                    gutter=GUTTER,
                )
            )
            if not is_day:
                names = QWidget()
                row = QHBoxLayout(names)
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(0)
                for day in range(7):
                    pick = button("", f"retroDay{day}", "day")
                    pick.clicked.connect(
                        lambda _=False, chosen=day: self.day_activated.emit(
                            self.scene.week.date_of(chosen).isoformat()
                        )
                    )
                    pick.setProperty("day_target", day)
                    canvas.day_buttons[day] = pick
                    row.addWidget(pick, 1)
                scroll.set_header(names)
            self._scrolls[key] = scroll
        scroll = self._scrolls[key]
        canvas = scroll.canvas
        canvas.set_painter(RetroPainter(scene.tokens))
        if is_day:
            day = self._shown_day(scene)
            canvas._lay_out = lambda area: [LinearTrack(day, area.adjusted(0, PAD, -PAD, -PAD))]
            canvas.relayout()
            items = [item for item in scene.week.occurrences if item.day == day]
        else:
            day = None
            items = scene.week.occurrences
            for target, pick in canvas.day_buttons.items():
                pick.setText(f"{DAYS[target]} {scene.week.date_of(target).day}")
                pick.setProperty("chosen", "true" if target == scene.today else "false")
                pick.style().unpolish(pick)
                pick.style().polish(pick)
        canvas.set_week(items, scene.today, scene.minute)
        body.addWidget(scroll, 1)
        scroll.show()
        opens = opening_minute(scene.week, scene.today, scene.minute, day)
        scroll.open_at((scene.week.week_start, day), opens)
        if scene.week.waiting and not self._open.get("notes"):
            # The notepad is where they live; here only while it is closed, so they are never shown twice.
            body.addWidget(label("Not placed yet · deadlines.txt", "retroWaitingLabel"))
            body.addLayout(self._tray(scene, "retroWaiting"))
        status = label("Ready. Drag a block, pull an edge, or drag empty time.", "retroStatus", wrap=True)
        status.setMinimumHeight(scene.px(32))
        body.addWidget(status)
        self._status()

    def _tray(self, scene: Scene, prefix: str) -> QHBoxLayout:
        row = QHBoxLayout()
        for index, waiting in enumerate(scene.week.waiting):
            chip = TrayChip(self.hand, waiting)
            chip.setObjectName(f"{prefix}{index}")
            chip.setToolTip(f"{chip.toolTip()} {waiting.reason}")
            chip.clicked.connect(
                lambda _=False, block_id=waiting.block_id: self.block_activated.emit(block_id)
            )
            row.addWidget(chip, 1)
        return row

    def _status(self) -> None:
        status = self.findChild(QLabel, "retroStatus")
        if status is None:
            return
        preview = self.hand.preview
        if preview is None:
            status.setText("Ready. Drag a block, pull an edge, or drag empty time.")
            status.setProperty("verdict", "ready")
        else:
            times = f"{clock_label(preview.span.start)}–{clock_label(preview.span.end)}"
            words = preview.verdict.words
            if preview.verdict.ok:
                status.setText(words or times)
            else:
                status.setText(f"{times} · {words}" if words else times)
            status.setProperty("verdict", "ok" if preview.verdict.ok else "refused")
        status.style().unpolish(status)
        status.style().polish(status)

    def _notes_window(self, scene: Scene, body: QVBoxLayout) -> None:
        sunken = QFrame()
        sunken.setProperty("role", "sunken")
        lines = QVBoxLayout(sunken)
        lines.setContentsMargins(4, 4, 4, 4)
        lines.setSpacing(2)
        lines.addWidget(label("Not placed yet · deadlines.txt", "retroNotesWaiting"))
        for index, waiting in enumerate(scene.week.waiting):
            chip = TrayChip(self.hand, waiting)
            chip.setObjectName(f"retroNoteWaiting{index}")
            chip.setToolTip(f"{chip.toolTip()} {waiting.reason}")
            chip.clicked.connect(
                lambda _=False, block_id=waiting.block_id: self.block_activated.emit(block_id)
            )
            lines.addWidget(chip)
        if not scene.week.waiting:
            lines.addWidget(label("Everything has a time.", "retroNotesNoWaiting"))
        for index, item in enumerate(scene.week.open_work()):
            flag = {"danger": "!!", "tight": " !"}.get(item.slack or "", "  ")
            due = due_label(item.due, scene.week.week_start)
            made = NoteLine(f"{flag} {item.title}", due, f"retroNote{index}")
            made.clicked.connect(lambda _=False, block_id=item.block_id: self.block_activated.emit(block_id))
            lines.addWidget(made)
        body.addWidget(sunken)

    def _next_window(self, scene: Scene, body: QVBoxLayout) -> None:
        queue = scene.week.day_queue(scene.today, scene.minute).queue if scene.today is not None else ()
        coming = next((item for item in queue if item.start > scene.minute), None)
        if scene.today is None:
            words = "This is another week, so nothing is next."
        elif coming is None:
            heading, title, line = scene.week.leftover_parts(scene.today)
            if scene.week.leftover_kind(scene.today) == "needs_time":
                words = f"{title} {heading.lower()}."
            else:
                words = (line or heading) + ("." if not (line or heading).endswith(".") else "")
        else:
            wait = length_label(coming.start - scene.minute)
            words = f"{coming.title} starts at {clock_label(coming.start)}, in {wait}."
        body.addWidget(label(words, "retroNextText", wrap=True))
        row = QHBoxLayout()
        ok = button("OK", "retroNextOk")
        ok.clicked.connect(lambda _=False: self._toggle("next"))
        day = button("My day", "retroNextDay")
        day.clicked.connect(self.my_day_requested.emit)
        row.addWidget(ok)
        row.addWidget(day)
        row.addStretch(1)
        body.addLayout(row)

    def _taskbar(self, scene: Scene) -> None:
        empty(self._bar_row)
        for key, title, _ in WINDOWS:
            if key == "week":
                title = "Schedule.exe" if scene.surface == "day" else "Week.exe"
            task = button(title, f"retroTask-{key}", "task")
            task.setProperty("open", "true" if self._open.get(key) else "false")
            task.setAccessibleName(("Hide " if self._open.get(key) else "Show ") + title)
            task.clicked.connect(lambda _=False, chosen=key: self._toggle(chosen))
            self._bar_row.addWidget(task)
        self._bar_row.addStretch(1)
        self._bar_row.addWidget(label(clock_label(scene.minute), "retroClock"))
