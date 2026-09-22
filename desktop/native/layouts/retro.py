"""Retro desktop: a main view. The week is a window, deadlines are a notepad, what is next is a dialog.

The windows drag by their title bars and close, and the taskbar brings them back. Work with no time
yet is listed in the week window as well as the notepad, so closing the notepad cannot hide it.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from desktop.native.calendar import DAYS
from desktop.native.layouts.base import (
    LayoutView,
    Scene,
    base_sheet,
    block_button,
    button,
    css,
    empty,
    label,
    plan_buttons,
    rules,
    scrolling,
)
from desktop.native.weekmodel import clock_label, due_label, length_label

WINDOWS = (
    ("week", "Week.exe", QPoint(24, 14)),
    ("notes", "deadlines.txt", QPoint(470, 330)),
    ("next", "Up next", QPoint(60, 360)),
)


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

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._grab = None


class RetroView(LayoutView):
    layout_id = "retro"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._open: dict[str, bool] = {}
        self._spots: dict[str, QPoint] = {}
        self._opened_for = ""
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
                    # The drop drawer is a window here too: square, raised, its days square keys.
                    "QFrame#dropDrawer": css(border=raised, border_radius="0"),
                    ", ".join(f"QPushButton#dropDay{day}" for day in range(7)): css(border_radius="0"),
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
                    'QPushButton[kind="row"][state="past"]': css(
                        color="#3a3a3a", text_decoration="line-through"
                    ),
                    'QPushButton[kind="row"][mono="true"]': css(font_family="DejaVu Sans Mono, monospace"),
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
        for child in self._desk.findChildren(QFrame, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if child.property("role") == "window":
                self._spots[child.objectName()] = child.pos()
                child.setParent(None)
                child.deleteLater()
        builders = {"week": self._week_window, "notes": self._notes_window, "next": self._next_window}
        for key, title, home in WINDOWS:
            if not self._open.get(key):
                continue
            frame = self._frame(scene, key, title)
            builders[key](scene, frame.layout())
            frame.setParent(self._desk)
            frame.setMaximumWidth(max(self.width(), self._desk.width(), 280) - 16)
            frame.adjustSize()
            self._place(frame, home)
            frame.show()
        self._taskbar(scene)

    def _place(self, frame: QFrame, home: QPoint) -> None:
        desk = self._desk
        spot = self._spots.get(frame.objectName(), home)
        limit_x = max(desk.width() - 60, 0)
        limit_y = max(desk.height() - 30, 0)
        frame.move(min(max(spot.x(), 0), limit_x), min(max(spot.y(), 0), limit_y))

    def _frame(self, scene: Scene, key: str, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName(f"retroWindow-{key}")
        frame.setProperty("role", "window")
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

    def _week_window(self, scene: Scene, body: QVBoxLayout) -> None:
        menu = QHBoxLayout()
        for made in plan_buttons(self, "retro", "Add homework…"):
            made.setProperty("kind", "menu")
            menu.addWidget(made)
        menu.addStretch(1)
        body.addLayout(menu)
        sunken = QFrame()
        sunken.setProperty("role", "sunken")
        grid = QGridLayout(sunken)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(scene.px(6))
        for day, name in enumerate(DAYS):
            today = day == scene.today
            head = label(
                f"{name} {scene.week.date_of(day).day}" + (" (today)" if today else ""), f"retroDay{day}"
            )
            head.setProperty("role", "today" if today else "")
            grid.addWidget(head, 0, day)
            for row, item in enumerate(scene.week.on_day(day), start=1):
                words = f"{clock_label(item.start)} {item.title}"
                made = block_button(self, words, f"retroBlock{day}-{row}", item.block_id, day=day)
                made.setProperty("state", "" if item.live else "past")
                grid.addWidget(made, row, day)
        grid.setRowStretch(grid.rowCount(), 1)
        pane = scrolling(sunken, "retroWeekPane")
        pane.setWidgetResizable(False)
        pane.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sunken.adjustSize()
        pane.setMinimumSize(520, 220)
        body.addWidget(pane, 1)
        if scene.week.waiting:
            waiting = QHBoxLayout()
            waiting.addWidget(label("Not placed yet:", "retroWaitingLabel"))
            for index, item in enumerate(scene.week.waiting):
                made = block_button(
                    self,
                    f"{item.title} ({length_label(item.minutes)})",
                    f"retroWaiting{index}",
                    item.block_id,
                )
                made.setToolTip(item.reason)
                waiting.addWidget(made)
            waiting.addStretch(1)
            body.addLayout(waiting)

    def _notes_window(self, scene: Scene, body: QVBoxLayout) -> None:
        sunken = QFrame()
        sunken.setProperty("role", "sunken")
        lines = QVBoxLayout(sunken)
        lines.setContentsMargins(4, 4, 4, 4)
        lines.setSpacing(0)
        index = 0
        for item in scene.week.open_work():
            flag = {"danger": "!!", "tight": " !"}.get(item.slack or "", "  ")
            made = block_button(
                self,
                f"{flag} {item.title:<26} {due_label(item.due, scene.week.week_start)}",
                f"retroNote{index}",
                item.block_id,
                day=item.day,
            )
            made.setProperty("mono", "true")
            lines.addWidget(made)
            index += 1
        for item in scene.week.waiting:
            made = block_button(
                self, f"?? {item.title:<26} not placed yet", f"retroNote{index}", item.block_id
            )
            made.setProperty("mono", "true")
            lines.addWidget(made)
            index += 1
        if not index:
            lines.addWidget(label("nothing open.", "retroNotesEmpty"))
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
            task = button(title, f"retroTask-{key}", "task")
            task.setProperty("open", "true" if self._open.get(key) else "false")
            task.setAccessibleName(("Hide " if self._open.get(key) else "Show ") + title)
            task.clicked.connect(lambda _=False, chosen=key: self._toggle(chosen))
            self._bar_row.addWidget(task)
        self._bar_row.addStretch(1)
        self._bar_row.addWidget(label(clock_label(scene.minute), "retroClock"))
