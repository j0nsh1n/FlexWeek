"""Hours a student can drag on, drawn any way a design likes.

An `HoursCanvas` is one painted widget holding one or more tracks: a day's column, seven columns, a
lane per day, a card laid at an angle. It draws the week's blocks on them through a `BlockPainter`,
which is the only thing a design replaces to look like itself, and passes every press to the window's
`Hand`, which owns the gestures. While something is held, the canvas draws it where it would land,
with its times written on it.

The canvas also answers the rig and the tests in global coordinates: where a day and minute are,
where a block is drawn, and how to bring a stretch of hours into view.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

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
from PySide6.QtWidgets import QScrollArea, QWidget

from desktop.native.calendar import CATEGORIES, DAYS, create_click_range
from desktop.native.hours.geometry import (
    FIRST,
    LAST,
    SLOT_MIN,
    Axis,
    LinearTrack,
    Span,
    overlap_columns,
    snap,
)
from desktop.native.hours.hand import Create, Gesture, Hand, Held, Verdict, span_words
from desktop.native.look import block_paint
from desktop.native.weekmodel import Occurrence, clock_label, length_label

# A press this close to a block's start or end edge resizes it, on a block long enough to have edges.
EDGE_PX = 7
FREE_HINT = "+ drag to create, or click"


@dataclass(frozen=True)
class Drawn:
    """A block as it is drawn right now: where, beside how many, and whether it is the one held."""

    block_id: str
    title: str
    category: str
    work: bool
    span: Span
    column: int
    columns: int
    held: bool = False
    verdict: Verdict | None = None
    chosen: bool = False
    done: bool = False
    missed: bool = False
    pinned: bool = False

    @property
    def detail(self) -> str:
        if self.held and self.verdict is not None:
            return self.verdict.words
        words = (
            f"{clock_label(self.span.start)}–{clock_label(self.span.end)} · {length_label(self.span.minutes)}"
        )
        for flag, word in (
            (self.done, "Done"),
            (self.missed, "Missed"),
            (self.pinned and not self.done, "Pinned"),
        ):
            if flag:
                words += f" · {word}"
        return words


class BlockPainter:
    """How hours and blocks look. This default is Daily Scheduler's: pale category fills, a strong
    edge, hour rules with dashed half hours, a red now line. Designs subclass it."""

    def __init__(self, colours: dict[str, str], look: dict | None = None) -> None:
        self.colours = colours
        self.look = look

    def c(self, name: str) -> QColor:
        return QColor(self.colours[name])

    def background(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self.c("window"))

    def track(self, painter: QPainter, track: LinearTrack, today: bool) -> None:
        """Hour and half-hour rules, in the track's upright frame."""
        area = track.area
        if today:
            wash = self.c("accent")
            wash.setAlphaF(0.05)
            painter.fillRect(area, wash)
        for minute in range((track.first // 30) * 30, track.last + 1, 30):
            if minute < track.first:
                continue
            offset = track.offset(minute)
            half = minute % 60 != 0
            painter.setPen(
                QPen(
                    self.c("grid" if half else "hairline"),
                    1,
                    Qt.PenStyle.DashLine if half else Qt.PenStyle.SolidLine,
                )
            )
            if track.axis is Axis.DOWN:
                painter.drawLine(
                    QPointF(area.left(), area.top() + offset), QPointF(area.right(), area.top() + offset)
                )
            else:
                painter.drawLine(
                    QPointF(area.left() + offset, area.top()), QPointF(area.left() + offset, area.bottom())
                )
        painter.setPen(QPen(self.c("hairline"), 1))
        if track.axis is Axis.DOWN:
            painter.drawLine(area.topLeft(), area.bottomLeft())
        else:
            painter.drawLine(area.topLeft(), area.topRight())

    def hour_labels(self, painter: QPainter, track: LinearTrack, room: float, every: int = 60) -> None:
        """Hours beside the first track: to its left down a column, above it across a lane."""
        painter.setPen(self.c("muted"))
        painter.setFont(_small(painter.font()))
        for minute in range(((track.first + every - 1) // every) * every, track.last + 1, every):
            at = track.offset(minute)
            if track.axis is Axis.DOWN:
                box = QRectF(track.area.left() - room, track.area.top() + at - 9, room - 6, 18)
                align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            else:
                box = QRectF(track.area.left() + at - 30, track.area.top() - room, 60, room - 2)
                align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
            painter.drawText(box, align, clock_label(minute))

    def fills(self, drawn: Drawn) -> tuple[QColor, QColor, QColor | None, QColor | None]:
        """Fill, ink, outline and edge for a block: the Blocks look knob and the category."""
        category = CATEGORIES.get(drawn.category, {})
        paint = block_paint(
            self.look,
            self.colours,
            category.get("color"),
            "flexible" if drawn.work else "locked",
            category.get("mark"),
        )
        return (
            QColor(paint["fill"]),
            QColor(paint["ink"]),
            QColor(paint["outline"]) if paint["outline"] else None,
            QColor(paint["edge"]) if paint["edge"] else None,
        )

    def block(self, painter: QPainter, rect: QRectF, drawn: Drawn, visible: QRectF) -> None:
        fill, ink, outline, edge = self.fills(drawn)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 5, 5)
        if outline is not None:
            painter.setPen(QPen(outline, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 5, 5)
        if edge is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(edge)
            painter.drawRoundedRect(QRectF(rect.left(), rect.top(), 4, rect.height()), 2, 2)
        if drawn.held or drawn.chosen:
            refused = drawn.verdict is not None and not drawn.verdict.ok
            painter.setPen(QPen(self.c("error" if refused else "accent"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 5, 5)
        if drawn.columns > 1 and not drawn.held:
            # Shares its time with another block: allowed, and marked so it is not missed.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.c("error"))
            painter.drawEllipse(QPointF(rect.right() - 7, rect.top() + 7), 3.5, 3.5)
        self.words(painter, rect, drawn, ink, visible)

    def words(self, painter: QPainter, rect: QRectF, drawn: Drawn, ink: QColor, visible: QRectF) -> None:
        bold = QFont(painter.font())
        bold.setBold(True)
        plain = _small(painter.font())
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
        detail = drawn.detail
        if drawn.held and QFontMetrics(plain).horizontalAdvance(detail) > room.width():
            detail = ""  # said in the label beside it instead
        painter.setPen(ink)
        if room.height() < 2 * line:
            painter.setFont(plain)
            text = f"{drawn.title} · {detail}" if detail else drawn.title
            elided = QFontMetrics(plain).elidedText(text, Qt.TextElideMode.ElideRight, int(room.width()))
            painter.drawText(room, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)
            return
        painter.setFont(bold)
        name = QFontMetrics(bold).elidedText(drawn.title, Qt.TextElideMode.ElideRight, int(room.width()))
        painter.drawText(
            QRectF(room.left(), room.top(), room.width(), line), Qt.AlignmentFlag.AlignLeft, name
        )
        painter.setFont(plain)
        faint = QColor(ink)
        faint.setAlphaF(0.8)
        refused = drawn.verdict is not None and not drawn.verdict.ok
        painter.setPen(self.c("error") if refused else faint)
        below = QRectF(room.left(), room.top() + line + 1, room.width(), room.height() - line - 1)
        painter.drawText(
            below, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, detail
        )

    def ghost(self, painter: QPainter, rect: QRectF, words: str, ok: bool) -> None:
        """Something about to be made: a tinted block where it would go, with its times."""
        colour = self.c("accent" if ok else "error")
        wash = QColor(colour)
        wash.setAlphaF(0.28)
        painter.setBrush(wash)
        painter.setPen(QPen(colour, 2))
        painter.drawRoundedRect(rect, 5, 5)
        bold = QFont(painter.font())
        bold.setBold(True)
        painter.setFont(bold)
        painter.setPen(self.c("text"))
        painter.drawText(
            rect.adjusted(8, 3, -6, -3),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            words,
        )

    def hint(self, painter: QPainter, rect: QRectF, big: bool) -> None:
        """The free time under the pointer, lit, with how to use it."""
        accent = self.c("accent")
        wash = QColor(accent)
        wash.setAlphaF(0.07)
        line = QColor(accent)
        line.setAlphaF(0.4)
        painter.setBrush(wash)
        painter.setPen(QPen(line, 1, Qt.PenStyle.DashLine))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 5, 5)
        if big:
            words = QColor(accent)
            words.setAlphaF(0.75)
            painter.setPen(words)
            painter.setFont(_small(painter.font()))
            painter.drawText(
                rect.adjusted(8, 2, -4, -2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, FREE_HINT
            )

    def now(self, painter: QPainter, track: LinearTrack, minute: int) -> None:
        colour = self.c("error")
        at = track.offset(minute)
        area = track.area
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        if track.axis is Axis.DOWN:
            painter.drawEllipse(QPointF(area.left() + 1, area.top() + at), 4, 4)
            painter.setPen(QPen(colour, 2))
            painter.drawLine(QPointF(area.left(), area.top() + at), QPointF(area.right(), area.top() + at))
        else:
            painter.drawEllipse(QPointF(area.left() + at, area.top() + 1), 4, 4)
            painter.setPen(QPen(colour, 2))
            painter.drawLine(QPointF(area.left() + at, area.top()), QPointF(area.left() + at, area.bottom()))

    def label(self, painter: QPainter, beside: QRectF, words: str, ok: bool, room: QRectF) -> None:
        """The held block's words on a pill beside it, when the block is too small to say them."""
        plain = _small(painter.font())
        metrics = QFontMetrics(plain)
        width, height = metrics.horizontalAdvance(words) + 20, metrics.height() + 10
        left = beside.right() + 6 if beside.right() + 6 + width <= room.right() else beside.left() - 6 - width
        pill = QRectF(max(left, room.left()), beside.top(), width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.c("accent" if ok else "error"))
        painter.drawRoundedRect(pill, height / 2, height / 2)
        painter.setPen(self.c("accent_ink"))
        painter.setFont(plain)
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, words)

    def day_name(self, painter: QPainter, box: QRectF, words: str, today: bool) -> None:
        font = QFont(painter.font())
        font.setBold(today)
        painter.setFont(font)
        painter.setPen(self.c("accent" if today else "muted"))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, words)


def _small(font: QFont) -> QFont:
    made = QFont(font)
    made.setPointSizeF(max(made.pointSizeF() * 0.86, 7))
    return made


class HoursCanvas(QWidget):
    """One painted widget of hours. `lay_out` says where each day's track lies in it."""

    # A day's name was clicked: open it on Day.
    day_opened = Signal(int)

    def __init__(
        self,
        hand: Hand,
        painter: BlockPainter,
        lay_out: Callable[[QRectF], list[LinearTrack]] | None = None,
        *,
        gutter: float = 0,
        header: float = 0,
        names: Callable[[int], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("hoursCanvas")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Hours")
        self.setAccessibleDescription(
            "Drag a block to move it, its top or bottom edge to resize it, or empty time to add something."
            " Double-click a block, or press Enter, to open it."
        )
        self.hand, self.painter = hand, painter
        self._lay_out = lay_out
        self.gutter, self.header = gutter, header
        self._names = names or (lambda day: DAYS[day])
        self.tracks: list[LinearTrack] = []
        self.occurrences: tuple[Occurrence, ...] = ()
        self.today: int | None = None
        self.now_min: int | None = None
        self._hover: tuple[LinearTrack, int] | None = None
        hand.preview_changed.connect(self.update)

    # What it shows

    def set_week(
        self, occurrences: Sequence[Occurrence], today: int | None = None, now_min: int | None = None
    ) -> None:
        self.occurrences = tuple(occurrences)
        self.today, self.now_min = today, now_min
        self.update()

    def set_clock(self, today: int | None, now_min: int | None) -> None:
        if (today, now_min) != (self.today, self.now_min):
            self.today, self.now_min = today, now_min
            self.update()

    def set_painter(self, painter: BlockPainter) -> None:
        self.painter = painter
        self.update()

    def lay_out(self, area: QRectF) -> list[LinearTrack]:
        if self._lay_out is not None:
            return self._lay_out(area)
        return [LinearTrack(0, area)]

    def relayout(self) -> None:
        area = QRectF(self.rect()).adjusted(self.gutter, self.header, 0, 0)
        self.tracks = self.lay_out(area) if area.width() > 0 and area.height() > 0 else []
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.relayout()

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)
        self.relayout()

    def track_at(self, point: QPointF) -> LinearTrack | None:
        for track in self.tracks:
            if track.contains(point):
                return track
        return None

    def track_for(self, day: int, minute: int | None = None) -> LinearTrack | None:
        for track in self.tracks:
            if track.day == day and (minute is None or track.first <= minute <= track.last):
                return track
        return None

    # Where blocks are drawn

    def drawn(self, track: LinearTrack) -> list[tuple[Drawn, QRectF]]:
        """Every block on a track, the held one where it would land, with its rectangle in the track's
        upright frame. Painting and pressing both read this, so they always agree."""
        preview = self.hand.preview
        held = preview.held if preview is not None else None
        chosen = self.hand.selection
        items: list[Drawn] = []
        moving = held is not None and held.kind in (Gesture.MOVE, Gesture.RESIZE_START, Gesture.RESIZE_END)
        for item in self.occurrences:
            if item.day != track.day or item.end <= track.first or item.start >= track.last:
                continue
            if moving and held is not None and item.block_id == held.block_id and item.day == held.from_day:
                continue
            items.append(
                Drawn(
                    item.block_id,
                    item.title,
                    item.category,
                    item.work,
                    Span(item.day, item.start, item.end),
                    0,
                    1,
                    chosen=chosen == (item.block_id, item.day),
                    done=item.done,
                    missed=item.missed,
                    pinned=item.pinned,
                )
            )
        if (
            preview is not None
            and held is not None
            and held.kind in (Gesture.MOVE, Gesture.RESIZE_START, Gesture.RESIZE_END, Gesture.PLACE)
        ):
            span = preview.span
            if span.day == track.day and span.end > track.first and span.start < track.last:
                category = next((o.category for o in self.occurrences if o.block_id == held.block_id), "")
                work = next(
                    (o.work for o in self.occurrences if o.block_id == held.block_id),
                    held.kind is Gesture.PLACE,
                )
                items.append(
                    Drawn(
                        held.block_id or "",
                        held.title,
                        category or ("homework" if work else ""),
                        work,
                        span,
                        0,
                        1,
                        held=True,
                        verdict=preview.verdict,
                    )
                )
        columns = overlap_columns([(d.span.start, d.span.end) for d in items])
        out = []
        for drawn, (column, count) in zip(items, columns, strict=True):
            placed = Drawn(**{**drawn.__dict__, "column": column, "columns": count})
            out.append((placed, track.rect_for(drawn.span.start, drawn.span.end, column, count)))
        return out

    def _block_at(self, point: QPointF) -> tuple[Drawn, QRectF, LinearTrack] | None:
        track = self.track_at(point)
        if track is None:
            return None
        upright = track.upright(point)
        hit = None
        for drawn, rect in self.drawn(track):
            if not drawn.held and rect.contains(upright):
                hit = (drawn, rect, track)
        return hit

    # Painting

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        visible = QRectF(event.rect())
        self.painter.background(painter, QRectF(self.rect()))
        preview = self.hand.preview
        held = preview.held if preview is not None else None
        for index, track in enumerate(self.tracks):
            painter.save()
            painter.setTransform(track.transform, True)
            self.painter.track(painter, track, track.day == self.today)
            if index == 0 and self.gutter and track.axis is Axis.DOWN:
                self.painter.hour_labels(painter, track, self.gutter)
            if index == 0 and self.header and track.axis is Axis.ACROSS:
                self.painter.hour_labels(painter, track, self.header, every=120)
            self._paint_hint(painter, track)
            upright_visible = track.transform.inverted()[0].mapRect(visible)
            for drawn, rect in self.drawn(track):
                self.painter.block(painter, rect, drawn, upright_visible)
            if (
                preview is not None
                and held is not None
                and held.kind is Gesture.CREATE
                and preview.span.day == track.day
            ):
                rect = track.rect_for(preview.span.start, preview.span.end)
                self.painter.ghost(painter, rect, span_words(preview.span), True)
            if (
                self.today == track.day
                and self.now_min is not None
                and track.first <= self.now_min <= track.last
            ):
                self.painter.now(painter, track, self.now_min)
            painter.restore()
        if self.header and any(track.axis is Axis.DOWN for track in self.tracks):
            for track in self.tracks:
                self.painter.day_name(
                    painter, self._name_box(track), self._names(track.day), track.day == self.today
                )
        self._paint_label(painter)
        painter.end()

    def _name_box(self, track: LinearTrack) -> QRectF:
        return QRectF(track.area.left(), 0, track.area.width(), self.header)

    def _paint_label(self, painter: QPainter) -> None:
        preview = self.hand.preview
        if preview is None or preview.held.kind is Gesture.CREATE:
            return
        for track in self.tracks:
            for drawn, rect in self.drawn(track):
                if not drawn.held:
                    continue
                words = preview.verdict.words
                small = QFontMetrics(_small(painter.font())).horizontalAdvance(words) > rect.width() - 14
                if small or rect.height() < 30:
                    self.painter.label(
                        painter, track.transform.mapRect(rect), words, preview.verdict.ok, QRectF(self.rect())
                    )
                return

    def _paint_hint(self, painter: QPainter, track: LinearTrack) -> None:
        if self._hover is None or self.hand.busy or self._hover[0] is not track:
            return
        minute = self._hover[1]
        low, high = track.first, track.last
        for item in self.occurrences:
            if item.day != track.day:
                continue
            if item.start <= minute < item.end:
                return
            if item.end <= minute:
                low = max(low, item.end)
            elif item.start > minute:
                high = min(high, item.start)
        if high - low < SLOT_MIN:
            return
        rect = track.rect_for(low, high)
        big = (rect.height() if track.axis is Axis.DOWN else rect.width()) >= 26
        self.painter.hint(painter, rect, big)

    # Pointer

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        point = event.position()
        name = self._name_at(point)
        if name is not None:
            self.day_opened.emit(name)
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        at = event.globalPosition().toPoint()
        hit = self._block_at(point)
        if hit is not None:
            drawn, rect, track = hit
            minute = track.minute_at(point)
            upright = track.upright(point)
            kind = self._edge_kind(rect, upright, track)
            # How far the pointer is from the edge it moves, so nothing jumps on the first move.
            edge = drawn.span.end if kind is Gesture.RESIZE_END else drawn.span.start
            held = Held(
                kind,
                drawn.title,
                drawn.span.minutes,
                drawn.block_id,
                drawn.span.day,
                drawn.span,
                round(minute - edge),
            )
            self.hand.select(drawn.block_id, drawn.span.day)
            self.hand.press(self, held, at, home=(self, track))
            return
        track = self.track_at(point)
        if track is None:
            return
        anchor = min(max(snap(track.minute_at(point) - SLOT_MIN / 2), FIRST), LAST - SLOT_MIN)
        held = Held(Gesture.CREATE, "", SLOT_MIN, None, track.day, Span(track.day, anchor, anchor + SLOT_MIN))
        self.hand.selection = None
        self.hand.press(self, held, at, tap=lambda: self._quick_create(track.day, anchor), home=(self, track))

    def _edge_kind(self, rect: QRectF, upright: QPointF, track: LinearTrack) -> Gesture:
        """Resize from within a few pixels of the start or end edge of a block long enough to have
        edges; move from anywhere else. As in Daily Scheduler."""
        down = track.axis is Axis.DOWN
        length = rect.height() if down else rect.width()
        if length < 2 * EDGE_PX + 6:
            return Gesture.MOVE
        from_start = upright.y() - rect.top() if down else upright.x() - rect.left()
        from_end = rect.bottom() - upright.y() if down else rect.right() - upright.x()
        if from_start <= EDGE_PX:
            return Gesture.RESIZE_START
        if from_end <= EDGE_PX:
            return Gesture.RESIZE_END
        return Gesture.MOVE

    def _quick_create(self, day: int, anchor: int) -> None:
        """A click on free time makes up to an hour there, stopping at the next block."""
        taken = sorted((item.start, item.end) for item in self.occurrences if item.day == day)
        if any(start <= anchor < end for start, end in taken):
            return
        made = create_click_range(anchor, taken)
        if made is not None:
            self.hand.commit(Create(Span(day, *made)))

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        hit = self._block_at(event.position())
        if event.button() != Qt.MouseButton.LeftButton or hit is None:
            super().mouseDoubleClickEvent(event)
            return
        self.hand.open(hit[0].block_id)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.hand.busy:
            return
        point = event.position()
        hit = self._block_at(point)
        track = self.track_at(point)
        if hit is not None:
            kind = self._edge_kind(hit[1], hit[2].upright(point), hit[2])
            self.setCursor(
                Qt.CursorShape.OpenHandCursor if kind is Gesture.MOVE else self._resize_cursor(hit[2])
            )
            hover = None
        elif self._name_at(point) is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            hover = None
        else:
            self.setCursor(
                Qt.CursorShape.PointingHandCursor if track is not None else Qt.CursorShape.ArrowCursor
            )
            hover = (track, snap(track.minute_at(point))) if track is not None else None
        if hover != self._hover:
            self._hover = hover
            self.update()

    def _resize_cursor(self, track: LinearTrack) -> Qt.CursorShape:
        return Qt.CursorShape.SizeVerCursor if track.axis is Axis.DOWN else Qt.CursorShape.SizeHorCursor

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        if self._hover is not None:
            self._hover = None
            self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Enter opens the chosen block. Everything else goes to the window's shortcuts."""
        chosen = self.hand.selection
        mine = chosen is not None and any(item.block_id == chosen[0] for item in self.occurrences)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and chosen is not None and mine:
            self.hand.open(chosen[0])
            event.accept()
            return
        event.ignore()

    def _name_at(self, point: QPointF) -> int | None:
        if not self.header or point.y() > self.header:
            return None
        for track in self.tracks:
            if track.axis is Axis.DOWN and self._name_box(track).contains(point):
                return track.day
        return None

    # For the rig and the tests, in global coordinates

    def point_for(self, day: int, minute: int) -> QPoint:
        track = self.track_for(day, minute)
        if track is None:
            raise LookupError(f"no track for day {day} at minute {minute}")
        return self.mapToGlobal(track.point_for(minute).toPoint())

    def block_rect(self, block_id: str, day: int) -> QRect | None:
        for track in self.tracks:
            if track.day != day:
                continue
            for drawn, rect in self.drawn(track):
                if drawn.block_id == block_id and not drawn.held:
                    box = track.transform.mapRect(rect).toRect()
                    return QRect(self.mapToGlobal(box.topLeft()), box.size())
        return None

    def day_name(self, day: int) -> QPoint:
        track = self.track_for(day)
        if track is None or not self.header:
            raise LookupError(f"no name drawn for day {day}")
        return self.mapToGlobal(self._name_box(track).center().toPoint())

    def reveal(self, day: int, first: int, last: int) -> None:
        """Scroll the nearest scroll area so this stretch of the day is on screen."""
        area = self.parentWidget()
        while area is not None and not isinstance(area, QScrollArea):
            area = area.parentWidget()
        track = self.track_for(day, first) or self.track_for(day)
        if area is None or track is None:
            return
        for minute in (last, first):
            local = track.point_for(min(max(minute, track.first), track.last)).toPoint()
            inside = self.mapTo(area.widget(), local) if area.widget() is not self else local
            area.ensureVisible(inside.x(), inside.y(), 20, 40)

    def held_words(self) -> str:
        preview = self.hand.preview
        return preview.verdict.words if preview is not None else ""
