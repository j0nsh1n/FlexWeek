"""Day dial: a day screen. The day is a clock face, and a list beside it reads the arcs out in words.

The face is painted, so it cannot be tabbed through. The hour-by-hour list is its keyboard and
screen-reader twin: every arc is also a row that opens the same block.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from desktop.native.calendar import DAY_FULL, DAYS
from desktop.native.layouts.base import (
    LayoutView,
    Scene,
    base_sheet,
    button,
    css,
    day_buttons,
    empty,
    label,
    mark_of,
    plural,
    rules,
    scrolling,
)
from desktop.native.weekmodel import Occurrence, clock_label, length_label

HOURS = {"day": (6 * 60, 22 * 60), "full": (0, 24 * 60)}
SWEEP = 300.0


class DialFace(QWidget):
    """One day as arcs on a ring. Fixed blocks sit on the ring, homework on a thinner ring outside it."""

    block_clicked = Signal(str)
    day_clicked = Signal(int)

    def __init__(self, day: int, mini: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.day, self.mini = day, mini
        self._blocks: tuple[Occurrence, ...] = ()
        self._minute: int | None = None
        self._span = HOURS["day"]
        self._tokens: dict[str, str] = {}
        self._chosen = False
        self.setObjectName(f"dialMini{day}" if mini else "dialFace")
        self.setMinimumSize(64, 64) if mini else self.setMinimumSize(280, 280)
        if mini:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_day(
        self,
        blocks: tuple[Occurrence, ...],
        minute: int | None,
        span: tuple[int, int],
        tokens: dict[str, str],
        chosen: bool = False,
    ) -> None:
        self._blocks, self._minute, self._span, self._tokens, self._chosen = (
            blocks,
            minute,
            span,
            tokens,
            chosen,
        )
        said = ", ".join(f"{item.title} {clock_label(item.start)}" for item in blocks) or "nothing planned"
        self.setAccessibleName(f"{DAY_FULL[self.day]}: {said}")
        self.update()

    def _geometry(self) -> tuple[QPointF, float, float]:
        side = min(self.width(), self.height())
        return QPointF(self.width() / 2, self.height() / 2), side * 0.36, side * (0.13 if self.mini else 0.10)

    def _angle(self, minute: int) -> float:
        start, end = self._span
        share = (min(max(minute, start), end) - start) / (end - start)
        return -SWEEP / 2 + share * SWEEP

    def _arc(
        self, painter: QPainter, radius: float, width: float, first: int, last: int, colour: QColor
    ) -> None:
        centre, _, _ = self._geometry()
        pen = QPen(colour, width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        box = QRectF(centre.x() - radius, centre.y() - radius, radius * 2, radius * 2)
        begin, finish = self._angle(first), self._angle(last)
        # Qt measures arcs anticlockwise from three o'clock in sixteenths of a degree.
        painter.drawArc(box, round((90 - begin) * 16), round(-(finish - begin) * 16))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        if not self._tokens:
            return
        tokens = self._tokens
        centre, radius, width = self._geometry()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._arc(painter, radius, width, self._span[0], self._span[1], QColor(tokens["line"]))
        for item in self._blocks:
            colour = QColor(mark_of(item.category))
            if not item.live:
                colour.setAlphaF(0.35)
            if item.work:
                self._arc(painter, radius + width * 0.8, width * 0.5, item.start, item.end, colour)
            else:
                self._arc(painter, radius, width, item.start, item.end, colour)
        if self.mini:
            if self._chosen:
                painter.setPen(QPen(QColor(tokens["accent"]), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(centre, radius * 0.55, radius * 0.55)
            painter.end()
            return
        painter.setPen(QColor(tokens["bg_muted"]))
        small = QFont(self.font())
        small.setPixelSize(max(round(radius * 0.085), 10))
        painter.setFont(small)
        step = 2 if self._span == HOURS["day"] else 3
        for hour in range(self._span[0] // 60, self._span[1] // 60 + 1, step):
            turn = math.radians(self._angle(hour * 60))
            spot = QPointF(
                centre.x() + (radius - width * 1.25) * math.sin(turn),
                centre.y() - (radius - width * 1.25) * math.cos(turn),
            )
            painter.drawText(
                QRectF(spot.x() - 16, spot.y() - 10, 32, 20), Qt.AlignmentFlag.AlignCenter, str(hour)
            )
        big = QFont(self.font())
        big.setPixelSize(max(round(radius * 0.26), 16))
        big.setBold(True)
        painter.setFont(big)
        painter.setPen(QColor(tokens["bg_ink"]))
        words = clock_label(self._minute) if self._minute is not None else DAYS[self.day]
        painter.drawText(
            QRectF(centre.x() - radius, centre.y() + radius * 0.12, radius * 2, radius * 0.4),
            Qt.AlignmentFlag.AlignCenter,
            words,
        )
        if self._minute is not None:
            turn = math.radians(self._angle(self._minute))
            hand = QPen(QColor(tokens["danger"]), 3)
            hand.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(hand)
            painter.drawLine(
                centre,
                QPointF(
                    centre.x() + (radius + width) * math.sin(turn),
                    centre.y() - (radius + width) * math.cos(turn),
                ),
            )
            painter.setBrush(QColor(tokens["danger"]))
            painter.drawEllipse(centre, 6, 6)
        painter.end()

    def block_at(self, spot: QPointF) -> Occurrence | None:
        centre, radius, width = self._geometry()
        dx, dy = spot.x() - centre.x(), spot.y() - centre.y()
        distance = math.hypot(dx, dy)
        if not radius - width <= distance <= radius + width * 1.3:
            return None
        turn = math.degrees(math.atan2(dx, -dy))
        if abs(turn) > SWEEP / 2:
            return None
        start, end = self._span
        minute = start + (turn + SWEEP / 2) / SWEEP * (end - start)
        under = [item for item in self._blocks if item.start <= minute < item.end]
        outer = distance > radius + width * 0.5
        under.sort(key=lambda item: item.work != outer)
        return under[0] if under else None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.mini:
            self.day_clicked.emit(self.day)
            return
        found = self.block_at(event.position())
        if found is not None:
            self.block_clicked.emit(found.block_id)


class DayDialView(LayoutView):
    layout_id = "dial"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day: int | None = None
        # A view's minimum height must not become the window's: three designs pushed it past a 768 pixel
        # laptop screen. Inside a scroll area, what does not fit scrolls and the window keeps its size.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._page = QWidget()
        self._page.setObjectName("dialPage")
        self._root = QHBoxLayout(self._page)
        self._root.setContentsMargins(22, 16, 22, 16)
        self._root.setSpacing(26)
        outer.addWidget(scrolling(self._page, "dialScroll"), 1)
        # The week strip is how another day is reached, so it is pinned below the scroller rather
        # than left at the bottom of a column. At large text it used to be sliced in half, with the
        # day names off screen entirely.
        self._strip_host = QWidget()
        self._strip_host.setObjectName("dialStrip")
        self._strip = QVBoxLayout(self._strip_host)
        self._strip.setContentsMargins(22, 0, 22, 10)
        outer.addWidget(self._strip_host)

    def shown_day(self, scene: Scene) -> int:
        return self._day if self._day is not None else (scene.today if scene.today is not None else 0)

    def _show_day(self, day: int) -> None:
        scene = self._scene
        if scene is None:
            return
        self._day = None if day == scene.today else day
        self.render(scene, False)

    def render(self, scene: Scene, week_changed: bool) -> None:
        if week_changed:
            self._day = None
        tokens, name = scene.tokens, self.objectName()
        day = self.shown_day(scene)
        is_today = day == scene.today
        span = HOURS.get(scene.options.get("hours", "day"), HOURS["day"])
        small = css(font_size=f"{scene.px(13)}px", letter_spacing="1px")
        self.setStyleSheet(
            base_sheet(name, tokens)
            + rules(
                name,
                {
                    "#dialScroll, #dialPage": css(background=tokens["bg"]),
                    "#dialCard": css(
                        background=tokens["surface"],
                        border=f"1px solid {tokens['line']}",
                        border_radius=f"{scene.px(16)}px",
                    ),
                    "#dialCard QLabel": css(color=tokens["text"]),
                    "#dialCard #dialKicker, #dialCard #dialThen": css(color=tokens["muted"]) + small,
                    "#dialTitle": css(font_size=f"{scene.px(30)}px", font_weight=700),
                    "#dialHeading": css(color=tokens["bg_muted"]) + small,
                    "#dialWaiting": css(color=tokens["bg_ink"]) + small,
                    "#dialMiniName": css(color=tokens["bg_muted"], font_size=f"{scene.px(12)}px"),
                    "QPushButton": css(
                        background="transparent",
                        color=tokens["bg_ink"],
                        border=f"1px solid {tokens['line']}",
                        border_radius=f"{scene.px(22)}px",
                        padding=f"0 {scene.px(18)}px",
                        min_height=f"{scene.px(44)}px",
                        font_size=f"{scene.px(14)}px",
                        font_weight=600,
                    ),
                    "#dialCard QPushButton": css(color=tokens["text"]),
                    'QPushButton[kind="main"]': css(
                        background=tokens["accent"], color=tokens["accent_ink"], border_color=tokens["accent"]
                    ),
                    'QPushButton[kind="row"]': css(
                        background=tokens["surface"],
                        color=tokens["text"],
                        border="none",
                        border_left=f"4px solid {tokens['line']}",
                        border_radius=f"{scene.px(8)}px",
                        text_align="left",
                        padding=f"0 {scene.px(10)}px",
                        min_height=f"{scene.px(38)}px",
                        font_weight=400,
                    ),
                    'QPushButton[kind="row"][state="past"]': css(
                        color=tokens["muted"], text_decoration="line-through"
                    ),
                    'QPushButton[kind="row"][state="now"]': css(
                        border=f"1px solid {tokens['accent']}",
                        border_left=f"4px solid {tokens['accent']}",
                        font_weight=700,
                    ),
                    "QPushButton:focus": css(border=f"2px solid {tokens['accent']}"),
                },
            )
        )
        empty(self._root)
        face = DialFace(day, False)
        face.set_day(scene.week.on_day(day), scene.minute if is_today else None, span, tokens)
        face.block_clicked.connect(self.block_activated.emit)
        self._root.addWidget(face, 6)
        side = QVBoxLayout()
        side.setSpacing(scene.px(10))
        side.addWidget(self._card(scene, day, is_today))
        blocks = scene.week.on_day(day)
        if scene.options.get("list") != "hide":
            side.addWidget(
                label(("Today" if is_today else DAY_FULL[day]).upper() + ", HOUR BY HOUR", "dialHeading")
            )
            current = scene.week.day_queue(day, scene.minute).current if is_today else None
            for index, item in enumerate(blocks):
                row = button(
                    f"{clock_label(item.start)}    {item.title}    ·  {length_label(item.minutes)}",
                    f"dialRow{index}",
                    "row",
                )
                past = not item.live or (
                    item.end <= scene.minute if is_today else (scene.today is not None and day < scene.today)
                )
                row.setProperty("state", "now" if item == current else "past" if past else "")
                row.setStyleSheet(f"border-left-color: {mark_of(item.category)};")
                row.clicked.connect(lambda _=False, key=item.block_id: self.block_activated.emit(key))
                side.addWidget(row)
            if not blocks:
                side.addWidget(label("A free day.", "dialHeading"))
        if scene.week.waiting:
            them = "it" if len(scene.week.waiting) == 1 else "them"
            side.addWidget(
                label(
                    f"{plural(len(scene.week.waiting), 'task')} not placed yet."
                    f" Go back to planning to give {them} a time.",
                    "dialWaiting",
                    wrap=True,
                )
            )
        side.addStretch(1)
        self._root.addLayout(side, 5)
        empty(self._strip)
        wanted = scene.options.get("week") != "hide"
        self._strip_host.setVisible(wanted)
        if wanted:
            self._strip.addLayout(self._minis(scene, day, span))

    def _card(self, scene: Scene, day: int, is_today: bool) -> QFrame:
        card = QFrame()
        card.setObjectName("dialCard")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(scene.px(18), scene.px(14), scene.px(18), scene.px(16))
        actions = QHBoxLayout()
        actions.setSpacing(scene.px(8))
        if is_today:
            found = scene.week.day_queue(day, scene.minute)
            item = found.queue[0] if found.queue else None
            if item is None:
                kicker, title = "DONE FOR TODAY", "Nothing else today"
            elif item == found.current:
                kicker, title = (
                    f"NOW · UNTIL {clock_label(item.end)} · "
                    f"{length_label(item.end - scene.minute).upper()} LEFT",
                    item.title,
                )
            else:
                kicker, title = (
                    f"UP NEXT · {clock_label(item.start)} · "
                    f"IN {length_label(item.start - scene.minute).upper()}",
                    item.title,
                )
            inner.addWidget(label(kicker, "dialKicker"))
            inner.addWidget(label(title, "dialTitle", wrap=True))
            if len(found.queue) > 1:
                inner.addWidget(
                    label(
                        f"THEN {found.queue[1].title.upper()} AT {clock_label(found.queue[1].start)}",
                        "dialThen",
                    )
                )
            made = day_buttons(self, scene, item, "dial")
        else:
            sessions = sum(1 for item in scene.week.on_day(day) if item.work and item.live)
            date = scene.week.date_of(day)
            inner.addWidget(
                label(f"{DAY_FULL[day].upper()}, {date.strftime('%B').upper()} {date.day}", "dialKicker")
            )
            inner.addWidget(label(plural(sessions, "homework session"), "dialTitle", wrap=True))
            made = []
            if scene.today is not None:
                today = button("Back to today", "dialToday", "main")
                today.clicked.connect(lambda _=False, target=scene.today: self._show_day(target))
                made.append(today)
            else:
                inner.addWidget(
                    label("THIS IS NOT THE CURRENT WEEK, SO THERE IS NO NOW TO SHOW.", "dialThen", wrap=True)
                )
            back = button("Back to planning", "dialBack")
            back.clicked.connect(self.back_requested.emit)
            made.append(back)
        for entry in made:
            actions.addWidget(entry)
        actions.addStretch()
        inner.addLayout(actions)
        return card

    def _minis(self, scene: Scene, day: int, span: tuple[int, int]) -> QHBoxLayout:
        strip = QHBoxLayout()
        strip.setSpacing(scene.px(8))
        for index, name in enumerate(DAYS):
            cell = QVBoxLayout()
            mini = DialFace(index, True)
            mini.setFixedHeight(scene.px(72))
            mini.set_day(scene.week.on_day(index), None, span, scene.tokens, chosen=index == day)
            mini.day_clicked.connect(self._show_day)
            cell.addWidget(mini)
            cell.addWidget(
                label(f"{name} {scene.week.date_of(index).day}", "dialMiniName"),
                0,
                Qt.AlignmentFlag.AlignHCenter,
            )
            strip.addLayout(cell)
        return strip
