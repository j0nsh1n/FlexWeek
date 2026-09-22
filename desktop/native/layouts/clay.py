"""Clay deck: a main view. Soft day cards in a deck, one day in the middle, its neighbours tucked behind.

The middle card is real buttons. The neighbours are painted so they can tilt, and the pager under the
deck is their keyboard twin: every day of the week is one button away.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
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
from desktop.native.weekmodel import Occurrence, clock_label, due_label, length_label

CARD_KEYS = ("card_a", "card_b", "card_c", "card_d")


def card_colour(tokens: dict[str, str], day: int) -> str:
    return tokens[CARD_KEYS[day % len(CARD_KEYS)]]


class SideCard(QWidget):
    """A neighbouring day, painted so it can lean. A click brings it to the middle."""

    day_clicked = Signal(int)

    def __init__(self, day: int, offset: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.day, self.offset = day, offset
        self.setObjectName(f"claySide{day}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title = ""
        self._lines: list[str] = []
        self._tokens: dict[str, str] = {}
        self._tilt = 0.0

    def set_day(
        self, title: str, blocks: tuple[Occurrence, ...], tokens: dict[str, str], tilted: bool
    ) -> None:
        self._title, self._tokens = title, tokens
        self._lines = [f"{clock_label(item.start)}  {item.title}" for item in blocks]
        self._tilt = self.offset * 3.5 if tilted else 0.0
        self.setAccessibleName(f"{title}: {', '.join(self._lines) or 'a free day'}. Click to open.")
        self.update()

    @property
    def tilt(self) -> float:
        return self._tilt

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        if not self._tokens:
            return
        tokens = self._tokens
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._tilt)
        scale = 0.9 if abs(self.offset) == 1 else 0.78
        width, height = self.width() * scale * 0.92, self.height() * scale * 0.9
        body = QRectF(-width / 2, -height / 2, width, height)
        shade = QColor(tokens["text"])
        shade.setAlpha(40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shade)
        painter.drawRoundedRect(body.translated(5, 8), 22, 22)
        painter.setPen(QPen(QColor(tokens["surface"]), 4))
        painter.setBrush(QColor(card_colour(tokens, self.day)))
        painter.drawRoundedRect(body, 22, 22)
        painter.setPen(QColor(tokens["text"]))
        heading = QFont(self.font())
        heading.setPixelSize(max(round(17 * scale), 11))
        heading.setBold(True)
        painter.setFont(heading)
        head_box = body.adjusted(14, 12, -10, 0)
        painter.drawText(
            head_box,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            QFontMetrics(heading).elidedText(self._title, Qt.TextElideMode.ElideRight, int(head_box.width())),
        )
        small = QFont(self.font())
        small.setPixelSize(max(round(13 * scale), 10))
        painter.setFont(small)
        for index, words in enumerate(self.painted_lines()):
            spot = body.adjusted(14, 44 + index * 22 * scale, -10, 0)
            painter.drawText(spot, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, words)
        painter.end()

    def painted_lines(self) -> list[str]:
        """The block lines as they will actually appear on the card.

        Qt clips drawText to its rectangle, so a long title was not spilling over the edge, it was
        being cut mid-word with nothing to say it had been cut. These end in an ellipsis instead.
        """
        scale = 0.9 if abs(self.offset) == 1 else 0.78
        small = QFont(self.font())
        small.setPixelSize(max(round(13 * scale), 10))
        room = int(self.width() * scale * 0.92) - 24
        metrics = QFontMetrics(small)
        return [
            metrics.elidedText(line, Qt.TextElideMode.ElideRight, max(room, 1))
            for line in (self._lines[:6] or ["A free day."])
        ]

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.day_clicked.emit(self.day)


class ClayDeckView(LayoutView):
    layout_id = "clay"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day: int | None = None
        # A view's minimum height must not become the window's: three designs pushed it past a 768 pixel
        # laptop screen. Inside a scroll area, what does not fit scrolls and the window keeps its size.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._page = QWidget()
        self._page.setObjectName("clayPage")
        self._root = QVBoxLayout(self._page)
        self._root.setContentsMargins(22, 16, 22, 16)
        outer.addWidget(scrolling(self._page, "clayScroll"))

    def shown_day(self, scene: Scene) -> int:
        return self._day if self._day is not None else (scene.today if scene.today is not None else 0)

    def _show_day(self, day: int) -> None:
        if self._scene is not None:
            self._day = None if day == self._scene.today else max(0, min(6, day))
            self.render(self._scene, False)

    def render(self, scene: Scene, week_changed: bool) -> None:
        if week_changed:
            self._day = None
        tokens, name = scene.tokens, self.objectName()
        soft = css(
            background=tokens["surface"],
            color=tokens["text"],
            border=f"3px solid {tokens['surface']}",
            border_radius=f"{scene.px(18)}px",
            padding=f"0 {scene.px(18)}px",
            min_height=f"{scene.px(44)}px",
            font_size=f"{scene.px(15)}px",
            font_weight=700,
        )
        self.setStyleSheet(
            base_sheet(name, tokens)
            + rules(
                name,
                {
                    "#clayScroll, #clayPage": css(background=tokens["bg"]),
                    "#clayTitle": css(font_size=f"{scene.px(28)}px", font_weight=800),
                    "#claySub, #clayTrayLabel": css(color=tokens["bg_muted"], font_size=f"{scene.px(14)}px"),
                    "#clayCentre": css(
                        border=f"4px solid {tokens['surface']}", border_radius=f"{scene.px(24)}px"
                    ),
                    "#clayCentre QLabel": css(
                        color=tokens["text"], font_size=f"{scene.px(22)}px", font_weight=800
                    ),
                    "QPushButton": soft,
                    'QPushButton[kind="main"]': css(background=tokens["accent"], color=tokens["accent_ink"]),
                    'QPushButton[kind="pill"], QPushButton[kind="row"]': css(
                        text_align="left",
                        font_weight=600,
                        font_size=f"{scene.px(14)}px",
                        border_left=f"8px solid {tokens['line']}",
                    ),
                    'QPushButton[kind="pill"][state="past"]': css(
                        background=tokens["bg"], color=tokens["muted"], text_decoration="line-through"
                    ),
                    'QPushButton[kind="day"]': css(
                        min_height=f"{scene.px(32)}px",
                        padding=f"0 {scene.px(10)}px",
                        font_size=f"{scene.px(12)}px",
                    ),
                    'QPushButton[kind="day"][chosen="true"]': css(border=f"3px solid {tokens['accent']}"),
                    "QPushButton:focus": css(border=f"3px solid {tokens['accent']}"),
                },
            )
        )
        empty(self._root)
        self._root.setSpacing(scene.px(10))
        day, week = self.shown_day(scene), scene.week
        self._root.addWidget(label("Your week, one day at a time", "clayTitle"))
        self._root.addWidget(label(f"{DAY_FULL[day]} is in the middle.", "claySub"))
        if week.waiting:
            tray = QHBoxLayout()
            tray.addWidget(label("Not placed yet:", "clayTrayLabel"))
            for index, item in enumerate(week.waiting):
                made = block_button(
                    self, f"{item.title} · {length_label(item.minutes)}", f"clayWaiting{index}", item.block_id
                )
                made.setToolTip(item.reason)
                made.setStyleSheet(f"border-left-color: {mark_of(item.category)};")
                tray.addWidget(made)
            tray.addStretch(1)
            self._root.addLayout(tray)
        reach = 2 if scene.options.get("cards") != "three" else 1
        reach = min(reach, 1) if self.cramped else reach
        tilted = scene.options.get("tilt") != "off"
        deck = QHBoxLayout()
        deck.setSpacing(0)
        deck.addStretch(1)
        for offset in range(-reach, reach + 1):
            target = day + offset
            if not 0 <= target <= 6:
                continue
            if offset == 0:
                deck.addWidget(self._centre(scene, day), 5)
                continue
            side = SideCard(target, offset)
            side.set_day(
                f"{DAY_FULL[target]} {week.date_of(target).day}", week.on_day(target), tokens, tilted
            )
            side.setMinimumSize(scene.px(170), scene.px(240))
            side.day_clicked.connect(self._show_day)
            deck.addWidget(side, 4 if abs(offset) == 1 else 3)
        deck.addStretch(1)
        self._root.addLayout(deck, 1)
        self._root.addLayout(self._pager(scene, day))

    def _centre(self, scene: Scene, day: int) -> QFrame:
        card = QFrame()
        card.setObjectName("clayCentre")
        card.setStyleSheet(f"#clayCentre {{ background: {card_colour(scene.tokens, day)}; }}")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(scene.px(16), scene.px(14), scene.px(16), scene.px(14))
        inner.setSpacing(scene.px(8))
        today = " · today" if day == scene.today else ""
        inner.addWidget(label(f"{DAY_FULL[day]} {scene.week.date_of(day).day}{today}", "clayCentreTitle"))
        for index, item in enumerate(scene.week.on_day(day)):
            words = f"{item.title}\n{clock_label(item.start)} · {length_label(item.minutes)}"
            if item.work and item.live:
                words += (
                    f" · {item.slack_words.lower() or 'due ' + due_label(item.due, scene.week.week_start)}"
                )
            pill = block_button(self, words, f"clayPill{index}", item.block_id, "pill", day=item.day)
            over = (
                item.end <= scene.minute
                if day == scene.today
                else (scene.today is not None and day < scene.today)
            )
            pill.setProperty("state", "past" if over or not item.live else "")
            pill.setStyleSheet(f"border-left-color: {mark_of(item.category)}; min-height: {scene.px(46)}px;")
            inner.addWidget(pill)
        if not scene.week.on_day(day):
            if day == scene.today:
                heading, title, line = scene.week.leftover_parts(day)
                words = (
                    f"{title} · {heading}"
                    if scene.week.leftover_kind(day) == "needs_time"
                    else (line or heading)
                )
                inner.addWidget(label(words, "clayCentreEmpty"))
            else:
                inner.addWidget(label("A free day.", "clayCentreEmpty"))
        inner.addStretch(1)
        return card

    def _pager(self, scene: Scene, day: int) -> QVBoxLayout:
        holder = QVBoxLayout()
        days = QHBoxLayout()
        days.addStretch(1)
        for target, name in enumerate(DAYS):
            pick = button(name, f"clayDay{target}", "day")
            pick.setProperty("chosen", "true" if target == day else "false")
            pick.setProperty("day_target", target)
            pick.setAccessibleName(f"Show {DAY_FULL[target]}")
            pick.clicked.connect(lambda _=False, chosen=target: self._show_day(chosen))
            days.addWidget(pick)
        days.addStretch(1)
        holder.addLayout(days)
        nav = QHBoxLayout()
        nav.setSpacing(scene.px(10))
        nav.addStretch(1)
        for words, key, step in (
            ("Earlier", "clayEarlier", -1),
            ("Today", "clayToday", 0),
            ("Later", "clayLater", 1),
        ):
            move = button(words, key)
            target = (scene.today if scene.today is not None else 0) if step == 0 else day + step
            move.setEnabled(0 <= target <= 6)
            move.clicked.connect(lambda _=False, chosen=target: self._show_day(chosen))
            nav.addWidget(move)
        nav.addSpacing(scene.px(18))
        for made in plan_buttons(self, "clay", "Add homework"):
            nav.addWidget(made)
        nav.addStretch(1)
        holder.addLayout(nav)
        return holder
