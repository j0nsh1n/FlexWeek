"""The week as one painted timeline: Today's app's calendar, and the day other designs drop onto.

Ported from Daily Scheduler's TimelineWidget, with a column for each day. A block is one painted shape
rather than a run of table cells, and dragging moves the block itself: it follows the pointer a quarter
hour at a time, into another day, with its new times written on it, and lands where it is let go.
Near its top or bottom edge a drag resizes it instead. Blocks that overlap sit side by side, each
marked so the overlap is easy to spot.

The canvas only draws and says what the student did. Whether a drop can stand is the window's rule,
asked through `judge`, so Today's app refuses what every other design refuses, in the same words.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QFontMetrics,
    QHelpEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import QFrame, QScrollArea, QToolTip, QVBoxLayout, QWidget

from backend.slots import DAY_END_MIN, DAY_START_MIN, SLOT_MIN, hhmm_to_minutes, minutes_to_hhmm
from desktop.native.calendar import CATEGORIES, DAYS, create_click_range, monday_of
from desktop.native.layouts.drag import Verdict, carried
from desktop.native.look import block_paint, resolved_palette
from desktop.native.weekmodel import length_label

# As in Daily Scheduler: an hour is 96 pixels, so a quarter hour has room for a line of text.
HOUR_PX = 96
GUTTER, HEADER = 56, 30
# How close to a block's top or bottom edge a press resizes it rather than moving it.
EDGE_PX = 7
GAP = 3
# Where the day's hours begin and how far a drag near the top or bottom edge scrolls.
EDGE_SCROLL = 30
FREE_HINT = "+ drag to create, or click"

Judge = Callable[[str, int, int, int, int], Verdict]


@dataclass(frozen=True)
class Shape:
    """One block on one day, as the canvas draws it."""

    block_id: str
    day: int
    start: int
    end: int
    title: str
    detail: str
    tip: str
    fill: str
    ink: str
    outline: str | None = None
    edge: str | None = None


def shapes_from_blocks(
    week_start: str, blocks: list[dict], trace: dict | None, look: dict | None, palette: dict
) -> list[Shape]:
    """The week's blocks, one shape per day each is on, painted by the Blocks look knob."""
    placed = {block["id"]: block for block in (trace or {}).get("placed", [])}
    shapes = []
    for original in blocks:
        block = placed.get(original["id"], original) if not original.get("completed") else original
        if not block.get("start"):
            continue
        start = hhmm_to_minutes(block["start"])
        end = start + int(block["duration_min"])
        days = list(block.get("days") or [])
        if block.get("completed") and block.get("completed_day") is not None:
            days = [block["completed_day"]]
        category = CATEGORIES.get(block.get("category") or "", {})
        paint = block_paint(look, palette, category.get("color"), block["kind"], category.get("mark"))
        for day in days:
            label = "Fixed" if block["kind"] == "locked" else "Work"
            if day in original.get("missed_days", []):
                label += " · Missed"
            if block.get("completed"):
                label += " · Done"
            elif block.get("pinned"):
                label += " · Pinned"
            detail = f"{block['start']} · {label}"
            shapes.append(
                Shape(
                    block_id=block["id"],
                    day=day,
                    start=start,
                    end=end,
                    title=block["title"],
                    detail=detail,
                    tip=f"{block['title']}\n{detail}",
                    fill=paint["fill"],
                    ink=paint["ink"],
                    outline=paint["outline"],
                    edge=paint["edge"],
                )
            )
    return shapes


def overlap_columns(shapes: list[Shape]) -> list[tuple[int, int]]:
    """Side by side for blocks that overlap: each block's column and how many share its time, in the
    order given. Daily Scheduler's assign_overlap_cols, for one day's shapes. By position, not by
    shape, since a repeating block dragged onto another of its days can be two equal shapes."""
    order = sorted(range(len(shapes)), key=lambda at: (shapes[at].start, shapes[at].end, shapes[at].block_id))
    ends: list[int] = []
    column = [0] * len(shapes)
    for at in order:
        free = next((index for index, end in enumerate(ends) if end <= shapes[at].start), len(ends))
        if free == len(ends):
            ends.append(0)
        ends[free] = shapes[at].end
        column[at] = free
    return [
        (
            column[at],
            max(
                column[other]
                for other, them in enumerate(shapes)
                if them.start < shape.end and shape.start < them.end
            )
            + 1,
        )
        for at, shape in enumerate(shapes)
    ]


def snap(minute: float) -> int:
    return round(minute / SLOT_MIN) * SLOT_MIN


def span_words(day: int, start: int, end: int) -> str:
    return f"{DAYS[day]} {minutes_to_hhmm(start)}–{minutes_to_hhmm(end)} · {length_label(end - start)}"


class Timeline(QWidget):
    """The painted hours of one or more days. Lives in a scroll area; the day names are drawn above
    it by the owner, so they stay put while the hours scroll."""

    block_activated = Signal(str)
    block_selected = Signal(str, int)
    range_created = Signal(int, int, int)
    # A block dragged to a new time: its id, the day it was on, the day it went to, its start and end.
    moved = Signal(str, int, int, int, int)
    # A block dragged in from elsewhere: its id, the day it came from (-1 when it had none), the day
    # it was let go on, and its start.
    dropped = Signal(str, int, int, int)
    refused = Signal(str)

    def __init__(self, days: list[int] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("weekTimeline")
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Week timeline")
        self.setAccessibleDescription(
            "Drag a block to move it, its top or bottom edge to resize it, or empty time to add something."
            " Double-click a block, or press Enter, to open it."
        )
        self.days = days if days is not None else list(range(7))
        self.shapes: list[Shape] = []
        self.palette_colours = resolved_palette("system", False, None)
        self.hour_px = HOUR_PX
        self.today: int | None = None
        self.now_min: int | None = None
        self.judge: Judge | None = None
        # For a block dragged in from elsewhere: how long it is, and what it is called.
        self.minutes_of: Callable[[str], int] = lambda _block_id: 60
        self.title_of: Callable[[str], str] = lambda _block_id: ""
        self.selected: tuple[str, int] | None = None
        self._gesture: dict | None = None
        self._hover: tuple[int, int] | None = None
        self._incoming: tuple[str, int, int, int, int, Verdict] | None = None
        self.setMinimumHeight(self.full_height())

    # Geometry

    def full_height(self) -> int:
        return round((DAY_END_MIN - DAY_START_MIN) / 60 * self.hour_px) + 12

    def y_of(self, minute: float) -> float:
        return 6 + (minute - DAY_START_MIN) / 60 * self.hour_px

    def minute_at(self, y: float) -> float:
        return DAY_START_MIN + (y - 6) / self.hour_px * 60

    def column_width(self) -> float:
        return max((self.width() - GUTTER) / max(len(self.days), 1), 1.0)

    def column_rect(self, index: int) -> QRectF:
        width = self.column_width()
        return QRectF(GUTTER + index * width, 0, width, self.height())

    def day_at(self, x: float) -> int | None:
        if x < GUTTER:
            return None
        index = min(int((x - GUTTER) / self.column_width()), len(self.days) - 1)
        return self.days[index]

    def _index_of(self, day: int) -> int | None:
        return self.days.index(day) if day in self.days else None

    def set_hour_px(self, hour_px: int) -> None:
        if hour_px != self.hour_px:
            self.hour_px = hour_px
            self.setMinimumHeight(self.full_height())
            self.setFixedHeight(self.full_height())
            self.update()

    # What is drawn

    def set_shapes(self, shapes: list[Shape]) -> None:
        # Every day's, not only the days on show: the drawer turns to another day without new shapes.
        self.shapes = list(shapes)
        known = {(shape.block_id, shape.day) for shape in self.shapes}
        if self.selected is not None and self.selected not in known:
            self.selected = None
        self.update()

    def laid_out(self) -> list[tuple[Shape, QRectF, int, bool]]:
        """Every shape's rectangle, with the one being dragged where it is being dragged to, how many
        blocks share its time, and whether it is the one held. Painting and pressing both use this,
        so they always agree."""
        shapes = []
        gesture = self._gesture
        held = None
        if gesture is not None and gesture["kind"] != "create" and gesture.get("moved"):
            held = (gesture["block_id"], gesture["from_day"])
        for shape in self.shapes:
            if (shape.block_id, shape.day) == held:
                day, start, end = gesture["preview"]  # type: ignore[index]
                shapes.append((replace(shape, day=day, start=start, end=end), True))
            else:
                shapes.append((shape, False))
        out = []
        for day in self.days:
            today = [(shape, holding) for shape, holding in shapes if shape.day == day]
            columns = overlap_columns([shape for shape, _holding in today])
            area = self.column_rect(self.days.index(day))
            for (shape, holding), (column, count) in zip(today, columns, strict=True):
                width = (area.width() - 2 * GAP) / count
                top, bottom = self.y_of(shape.start), self.y_of(shape.end)
                rect = QRectF(
                    area.left() + GAP + column * width, top + 1, width - GAP, max(bottom - top - 2, 6)
                )
                out.append((shape, rect, count, holding))
        return out

    def shape_at(self, point: QPointF) -> tuple[Shape, QRectF] | None:
        hit = None
        for shape, rect, _count, _holding in self.laid_out():
            if rect.contains(point):
                hit = (shape, rect)
        return hit

    def _mode_for(self, rect: QRectF, y: float) -> str:
        """Resize from within a few pixels of the top or bottom edge, on a block tall enough to
        have edges; move from anywhere else. As in Daily Scheduler."""
        if rect.height() >= 2 * EDGE_PX + 6:
            if y - rect.top() <= EDGE_PX:
                return "resize_top"
            if rect.bottom() - y <= EDGE_PX:
                return "resize_bottom"
        return "move"

    def _judge(self, block_id: str, from_day: int, day: int, start: int, end: int) -> Verdict:
        if self.judge is None:
            return Verdict(True, span_words(day, start, end), start, end)
        return self.judge(block_id, from_day, day, start, end)

    # Painting

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        colours = self.palette_colours
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(colours["window"]))
        self._paint_hours(painter)
        self._paint_free(painter)
        visible = event.rect()
        held = None
        for shape, rect, count, holding in self.laid_out():
            self._paint_shape(painter, shape, rect, count, holding, visible)
            if holding:
                held = rect
        self._paint_create(painter)
        self._paint_incoming(painter)
        self._paint_now(painter)
        if held is not None:
            self._paint_label(painter, held)
        painter.end()

    def held_words(self) -> str:
        """What the block being dragged says about where it would land, for tests and screen readers."""
        gesture = self._gesture
        if gesture is None or gesture["kind"] == "create" or not gesture.get("moved"):
            return ""
        return gesture["verdict"].words or span_words(*gesture["preview"])

    def _paint_label(self, painter: QPainter, rect: QRectF) -> None:
        """The held block's words beside it when the block is too narrow to say them, as it is when it
        shares its time and sits in half a day's width."""
        words = self.held_words()
        plain = QFont(self.font())
        plain.setPointSizeF(max(plain.pointSizeF() * 0.88, 7))
        metrics = QFontMetrics(plain)
        width = metrics.horizontalAdvance(words) + 20
        if rect.width() - 14 >= width - 20:
            return
        height = metrics.height() + 10
        left = rect.right() + 6 if rect.right() + 6 + width <= self.width() else rect.left() - 6 - width
        pill = QRectF(max(left, GUTTER), rect.top(), width, height)
        refused = not self._gesture["verdict"].ok  # type: ignore[index]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.palette_colours["error" if refused else "accent"]))
        painter.drawRoundedRect(pill, height / 2, height / 2)
        painter.setPen(QColor(self.palette_colours["accent_ink"]))
        painter.setFont(plain)
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, words)

    def _paint_hours(self, painter: QPainter) -> None:
        colours = self.palette_colours
        small = QFont(self.font())
        small.setPointSizeF(max(small.pointSizeF() * 0.8, 7))
        painter.setFont(small)
        for index, day in enumerate(self.days):
            area = self.column_rect(index)
            if day == self.today:
                wash = QColor(colours["accent"])
                wash.setAlphaF(0.05)
                painter.fillRect(area, wash)
            painter.setPen(QPen(QColor(colours["hairline"]), 1))
            painter.drawLine(QPointF(area.left(), 0), QPointF(area.left(), self.height()))
        for hour in range(DAY_START_MIN // 60, DAY_END_MIN // 60 + 1):
            y = self.y_of(hour * 60)
            painter.setPen(QPen(QColor(colours["hairline"]), 1))
            painter.drawLine(QPointF(GUTTER, y), QPointF(self.width(), y))
            if hour * 60 < DAY_END_MIN:
                half = self.y_of(hour * 60 + 30)
                painter.setPen(QPen(QColor(colours["grid"]), 1, Qt.PenStyle.DashLine))
                painter.drawLine(QPointF(GUTTER, half), QPointF(self.width(), half))
            painter.setPen(QColor(colours["muted"]))
            painter.drawText(
                QRectF(0, y - 9, GUTTER - 8, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{hour:02d}:00",
            )

    def _paint_free(self, painter: QPainter) -> None:
        """The free time under the pointer, lit, with how to use it. Not while anything is dragged."""
        if self._hover is None or self._gesture is not None or self._incoming is not None:
            return
        day, minute = self._hover
        taken = sorted((shape.start, shape.end) for shape in self.shapes if shape.day == day)
        low, high = DAY_START_MIN, DAY_END_MIN
        for start, end in taken:
            if start <= minute < end:
                return
            if end <= minute:
                low = max(low, end)
            elif start > minute:
                high = min(high, start)
        if high - low < SLOT_MIN:
            return
        area = self.column_rect(self.days.index(day))
        rect = QRectF(
            area.left() + GAP, self.y_of(low), area.width() - 2 * GAP, self.y_of(high) - self.y_of(low)
        )
        accent = QColor(self.palette_colours["accent"])
        wash = QColor(accent)
        wash.setAlphaF(0.07)
        painter.setBrush(wash)
        line = QColor(accent)
        line.setAlphaF(0.4)
        painter.setPen(QPen(line, 1, Qt.PenStyle.DashLine))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 5, 5)
        if rect.height() >= 26:
            words = QColor(accent)
            words.setAlphaF(0.75)
            painter.setPen(words)
            spot = QRectF(rect.left() + 8, self.y_of(snap(minute - 15)), rect.width() - 12, 22)
            metrics = QFontMetrics(painter.font())
            painter.drawText(
                spot.intersected(rect),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                metrics.elidedText(FREE_HINT, Qt.TextElideMode.ElideRight, int(spot.width())),
            )

    def _paint_shape(
        self, painter: QPainter, shape: Shape, rect: QRectF, count: int, dragging: bool, visible: QRect
    ) -> None:
        colours = self.palette_colours
        refused = dragging and self._gesture is not None and not self._gesture["verdict"].ok
        chosen = self.selected == (shape.block_id, shape.day)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(shape.fill))
        painter.drawRoundedRect(rect, 5, 5)
        if shape.outline:
            painter.setPen(QPen(QColor(shape.outline), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 5, 5)
        if shape.edge:
            # Over the outline, which the edge look draws as a hairline: the colour is what shows.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(shape.edge))
            painter.drawRoundedRect(QRectF(rect.left(), rect.top(), 4, rect.height()), 2, 2)
        if dragging or chosen:
            ring = colours["error"] if refused else colours["accent"]
            painter.setPen(QPen(QColor(ring), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 5, 5)
        if count > 1:
            # It shares its time with another block. Allowed, and marked so it is not missed.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colours["error"]))
            painter.drawEllipse(QPointF(rect.right() - 7, rect.top() + 7), 3.5, 3.5)
        self._paint_words(painter, shape, rect, visible, dragging, refused)

    def _paint_words(
        self, painter: QPainter, shape: Shape, rect: QRectF, visible: QRect, dragging: bool, refused: bool
    ) -> None:
        bold = QFont(self.font())
        bold.setBold(True)
        plain = QFont(self.font())
        plain.setPointSizeF(max(plain.pointSizeF() * 0.88, 7))
        line = QFontMetrics(bold).height()
        # The name stays in sight while the top of a long block is scrolled away.
        top = (
            max(rect.top() + 3, visible.top() + 3)
            if rect.bottom() - visible.top() > 2 * line
            else rect.top() + 3
        )
        room = QRectF(rect.left() + 8, top, rect.width() - 14, rect.bottom() - top - 2)
        if room.height() < 6 or room.width() < 8:
            return
        painter.setPen(QColor(shape.ink))
        detail = self.held_words() if dragging else shape.detail
        if dragging and QFontMetrics(plain).horizontalAdvance(detail) > room.width():
            detail = ""  # said in the label beside it instead
        if room.height() < 2 * line:
            painter.setFont(plain)
            words = f"{shape.title} · {detail}"
            elided = QFontMetrics(plain).elidedText(words, Qt.TextElideMode.ElideRight, int(room.width()))
            painter.drawText(room, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)
            return
        painter.setFont(bold)
        name = QFontMetrics(bold).elidedText(shape.title, Qt.TextElideMode.ElideRight, int(room.width()))
        painter.drawText(
            QRectF(room.left(), room.top(), room.width(), line), Qt.AlignmentFlag.AlignLeft, name
        )
        painter.setFont(plain)
        faint = QColor(shape.ink)
        faint.setAlphaF(0.8)
        painter.setPen(QColor(self.palette_colours["error"]) if refused else faint)
        below = QRectF(room.left(), room.top() + line + 1, room.width(), room.height() - line - 1)
        painter.drawText(
            below, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, detail
        )

    def _paint_create(self, painter: QPainter) -> None:
        gesture = self._gesture
        if gesture is None or gesture["kind"] != "create" or not gesture.get("moved"):
            return
        day, start, end = gesture["day"], *gesture["span"]
        self._paint_ghost(painter, day, start, end, span_words(day, start, end), True)

    def _paint_incoming(self, painter: QPainter) -> None:
        if self._incoming is None:
            return
        block_id, _from_day, day, start, end, verdict = self._incoming
        title = self.title_of(block_id)
        words = verdict.words or span_words(day, start, end)
        self._paint_ghost(painter, day, start, end, f"{title}\n{words}" if title else words, verdict.ok)

    def _paint_ghost(self, painter: QPainter, day: int, start: int, end: int, words: str, ok: bool) -> None:
        """Something about to be made or dropped: a tinted block where it would go, with its times."""
        index = self._index_of(day)
        if index is None:
            return
        area = self.column_rect(index)
        rect = QRectF(
            area.left() + GAP,
            self.y_of(start) + 1,
            area.width() - 2 * GAP,
            self.y_of(end) - self.y_of(start) - 2,
        )
        colour = QColor(self.palette_colours["accent" if ok else "error"])
        wash = QColor(colour)
        wash.setAlphaF(0.28)
        painter.setBrush(wash)
        painter.setPen(QPen(colour, 2))
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(QColor(self.palette_colours["text"]))
        bold = QFont(self.font())
        bold.setBold(True)
        painter.setFont(bold)
        painter.drawText(
            rect.adjusted(8, 3, -6, -3),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            words,
        )

    def _paint_now(self, painter: QPainter) -> None:
        if self.today is None or self.now_min is None or self.today not in self.days:
            return
        if not DAY_START_MIN <= self.now_min <= DAY_END_MIN:
            return
        area = self.column_rect(self.days.index(self.today))
        y = self.y_of(self.now_min)
        colour = QColor(self.palette_colours["error"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawEllipse(QPointF(area.left() + 1, y), 4, 4)
        painter.setPen(QPen(colour, 2))
        painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))

    # Pointer

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        point = event.position()
        day = self.day_at(point.x())
        if event.button() != Qt.MouseButton.LeftButton or day is None:
            super().mousePressEvent(event)
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        hit = self.shape_at(point)
        if hit is not None:
            shape, rect = hit
            self.selected = (shape.block_id, shape.day)
            self.block_selected.emit(shape.block_id, shape.day)
            self._gesture = {
                "kind": self._mode_for(rect, point.y()),
                "block_id": shape.block_id,
                "from_day": shape.day,
                "origin": (shape.start, shape.end),
                "press": self.minute_at(point.y()),
                "preview": (shape.day, shape.start, shape.end),
                "verdict": Verdict(True, ""),
                "moved": False,
            }
        else:
            self.selected = None
            start = min(snap(self.minute_at(point.y()) - SLOT_MIN / 2), DAY_END_MIN - SLOT_MIN)
            start = max(start, DAY_START_MIN)
            self._gesture = {"kind": "create", "day": day, "anchor": start, "span": (start, start + SLOT_MIN)}
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        point = event.position()
        gesture = self._gesture
        if gesture is None:
            self._hover_at(point)
            return
        self._scroll_near_edge(point)
        if gesture["kind"] == "create":
            here = min(max(snap(self.minute_at(point.y())), DAY_START_MIN), DAY_END_MIN)
            anchor = gesture["anchor"]
            span = (anchor, max(here, anchor + SLOT_MIN)) if here >= anchor else (here, anchor + SLOT_MIN)
            gesture["span"] = span
            gesture["moved"] = gesture.get("moved") or span != (anchor, anchor + SLOT_MIN)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()
            return
        origin_start, origin_end = gesture["origin"]
        delta = snap(self.minute_at(point.y()) - gesture["press"])
        day = gesture["from_day"]
        if gesture["kind"] == "move":
            length = origin_end - origin_start
            start = min(max(origin_start + delta, DAY_START_MIN), DAY_END_MIN - length)
            span = (start, start + length)
            day = self.day_at(point.x()) if self.day_at(point.x()) is not None else day
        elif gesture["kind"] == "resize_top":
            span = (min(max(origin_start + delta, DAY_START_MIN), origin_end - SLOT_MIN), origin_end)
        else:
            span = (origin_start, max(min(origin_end + delta, DAY_END_MIN), origin_start + SLOT_MIN))
        preview = (day, *span)
        if preview != gesture["preview"] or not gesture["moved"]:
            moved = preview != (gesture["from_day"], origin_start, origin_end)
            gesture["moved"] = gesture["moved"] or moved
            gesture["preview"] = preview
            if gesture["moved"]:
                gesture["verdict"] = self._judge(gesture["block_id"], gesture["from_day"], *preview)
            self.update()
        self.setCursor(
            Qt.CursorShape.ClosedHandCursor if gesture["kind"] == "move" else Qt.CursorShape.SizeVerCursor
        )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        gesture, self._gesture = self._gesture, None
        if gesture is None or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        self.update()
        self._hover_at(event.position())
        if gesture["kind"] == "create":
            if gesture.get("moved"):
                self.range_created.emit(gesture["day"], *gesture["span"])
                return
            taken = sorted((shape.start, shape.end) for shape in self.shapes if shape.day == gesture["day"])
            made = create_click_range(gesture["anchor"], taken)
            if made is not None:
                self.range_created.emit(gesture["day"], *made)
            return
        if not gesture.get("moved"):
            return
        day, start, end = gesture["preview"]
        if (day, start, end) == (gesture["from_day"], *gesture["origin"]):
            return
        verdict = gesture["verdict"]
        if not verdict.ok:
            # It goes back where it was, and the status line says why.
            self.refused.emit(verdict.words)
            return
        self.selected = (gesture["block_id"], day)
        self.moved.emit(gesture["block_id"], gesture["from_day"], day, start, end)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        hit = self.shape_at(event.position())
        if event.button() != Qt.MouseButton.LeftButton or hit is None:
            super().mouseDoubleClickEvent(event)
            return
        self._gesture = None
        self.block_activated.emit(hit[0].block_id)
        event.accept()

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        if self._gesture is None and self._hover is not None:
            self._hover = None
            self.update()

    def _hover_at(self, point: QPointF) -> None:
        day = self.day_at(point.x())
        hit = self.shape_at(point) if day is not None else None
        if hit is not None:
            mode = self._mode_for(hit[1], point.y())
            self.setCursor(Qt.CursorShape.SizeVerCursor if mode != "move" else Qt.CursorShape.OpenHandCursor)
            hover = None
        else:
            self.setCursor(
                Qt.CursorShape.PointingHandCursor if day is not None else Qt.CursorShape.ArrowCursor
            )
            hover = (day, snap(self.minute_at(point.y()))) if day is not None else None
        if hover != self._hover:
            self._hover = hover
            self.update()

    def _scroll_near_edge(self, point: QPointF) -> None:
        """A drag near the top or bottom of what is showing scrolls, so any hour can be reached."""
        area = self._scroller()
        if area is not None:
            area.ensureVisible(int(point.x()), int(point.y()), 0, EDGE_SCROLL)

    def _scroller(self) -> QScrollArea | None:
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        return parent

    def event(self, event: object) -> bool:  # noqa: A003
        if isinstance(event, QHelpEvent):
            hit = self.shape_at(QPointF(event.pos()))
            if hit is not None:
                QToolTip.showText(event.globalPos(), hit[0].tip, self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)

    # Keys

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Escape lets go of a drag without moving anything. Enter opens the chosen block. Everything
        else goes to the window, whose shortcuts work wherever the student is."""
        if event.key() == Qt.Key.Key_Escape and self._gesture is not None:
            self._gesture = None
            self.update()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.selected is not None:
            self.block_activated.emit(self.selected[0])
            event.accept()
            return
        event.ignore()

    # Dropped in from elsewhere

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if carried(event) is not None:
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        thing = carried(event)
        point = event.position()
        day = self.day_at(point.x())
        if thing is None or day is None:
            self._set_incoming(None)
            event.ignore()
            return
        self._scroll_near_edge(point)
        from_day = thing.from_day
        length = self.minutes_of(thing.block_id)
        start = min(max(snap(self.minute_at(point.y()) - thing.grab), DAY_START_MIN), DAY_END_MIN - length)
        verdict = self._judge(thing.block_id, from_day, day, start, start + length)
        self._set_incoming((thing.block_id, from_day, day, start, start + length, verdict))
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self._set_incoming(None)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        incoming = self._incoming
        self._set_incoming(None)
        if incoming is None:
            event.ignore()
            return
        block_id, from_day, day, start, _end, verdict = incoming
        event.acceptProposedAction()
        if not verdict.ok:
            self.refused.emit(verdict.words)
            return
        self.selected = (block_id, day)
        self.dropped.emit(block_id, from_day, day, start)

    def _set_incoming(self, incoming: tuple[str, int, int, int, int, Verdict] | None) -> None:
        if incoming != self._incoming:
            self._incoming = incoming
            self.update()

    def incoming_words(self) -> str:
        """What a block being dragged in would do here, for tests and screen readers."""
        if self._incoming is None:
            return ""
        _block_id, _from, day, start, end, verdict = self._incoming
        return verdict.words or span_words(day, start, end)


class DayHeader(QWidget):
    """The day names over a timeline's columns, which stay put while the hours scroll."""

    def __init__(self, timeline: Timeline, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("weekHeader")
        self.timeline = timeline
        self.week_start = monday_of(date.today().isoformat())
        self.setFixedHeight(HEADER)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        colours = self.timeline.palette_colours
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(colours["window"]))
        monday = date.fromisoformat(self.week_start)
        bold = QFont(self.font())
        for index, day in enumerate(self.timeline.days):
            area = self.timeline.column_rect(index)
            label = f"{DAYS[day]} {(monday + timedelta(days=day)).day}"
            today = day == self.timeline.today
            bold.setBold(today)
            painter.setFont(bold)
            painter.setPen(QColor(colours["accent" if today else "muted"]))
            painter.drawText(
                QRectF(area.left(), 0, area.width(), self.height()), Qt.AlignmentFlag.AlignCenter, label
            )
        painter.setPen(QPen(QColor(colours["hairline"]), 1))
        painter.drawLine(QPointF(0, self.height() - 1), QPointF(self.width(), self.height() - 1))
        painter.end()


class WeekCanvas(QWidget):
    """Today's app's week: the day names, and the hours under them in a scroll area."""

    def __init__(self, days: list[int] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("weekTable")
        self.body = Timeline(days)
        self.header = DayHeader(self.body)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("weekScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.scroll, 1)
        self._look: dict | None = None
        self._shown: tuple[str, list[dict], dict | None] | None = None
        self._revealed: str | None = None
        self.body.setFixedHeight(self.body.full_height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.header.update()

    def set_look(self, look: dict | None, palette: dict) -> None:
        """Repaint the week on screen with a new look; the blocks themselves do not change."""
        self._look = look
        self.body.palette_colours = palette
        if self._shown is not None:
            self.set_week(*self._shown)
        self.header.update()

    def set_week(self, week_start: str, blocks: list[dict], trace: dict | None = None) -> None:
        self._shown = (week_start, blocks, trace)
        self.header.week_start = week_start
        self.body.set_shapes(
            shapes_from_blocks(week_start, blocks, trace, self._look, self.body.palette_colours)
        )
        self.header.update()

    def set_clock(self, week_start: str, now_ms: int) -> None:
        moment = datetime.fromtimestamp(now_ms / 1000.0)
        this_week = monday_of(moment.date().isoformat()) == week_start
        self.body.today = moment.weekday() if this_week else None
        self.body.now_min = moment.hour * 60 + moment.minute if this_week else None
        self.header.update()
        self.body.update()

    def reveal(self, week_start: str, now_ms: int) -> None:
        """Open this week on the time that matters: now, or the first block, not 06:00."""
        self.set_clock(week_start, now_ms)
        if self._revealed == week_start:
            return
        self._revealed = week_start
        if self.body.now_min is not None:
            minute = self.body.now_min
        else:
            starts = [shape.start for shape in self.body.shapes]
            minute = min(starts) if starts else 8 * 60
        top = self.body.y_of(max(minute - 30, DAY_START_MIN))
        self.scroll.verticalScrollBar().setValue(int(top))

    def block_titles(self, ids: list[str]) -> list[str]:
        titles = {shape.block_id: shape.title for shape in self.body.shapes}
        return [titles.get(block_id, block_id) for block_id in ids]

    def point_of(self, day: int, minute: int) -> QPoint:
        """Where on the timeline a day and minute are, for tests and for keyboard reach."""
        index = self.body.days.index(day)
        area = self.body.column_rect(index)
        return QPoint(int(area.center().x()), int(self.body.y_of(minute)))
