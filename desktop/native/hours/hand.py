"""What the pointer is doing: one gesture engine for every design's hours, chips and month.

Anything a student can pick up calls `Hand.press` with what it holds. From then on the hand follows
the pointer itself: it waits for a real drag, finds the hours under the pointer, snaps, asks the
window's rule, shows the result in place, scrolls a scroll area after the pointer rests at its
edge, and on release reports one change. Moves arrive through Qt's implicit grab (the widget pressed
keeps receiving the mouse until release), so no system drag-and-drop is involved and X11 and
Wayland behave alike.

A press that never becomes a drag is a tap, handed back to whoever pressed. Escape lets go.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QWidget
from shiboken6 import isValid

from desktop.native.calendar import DAYS
from desktop.native.hours.geometry import FIRST, LAST, SLOT_MIN, LinearTrack, Span, snap
from desktop.native.weekmodel import length_label

if TYPE_CHECKING:
    from desktop.native.hours.canvas import HoursCanvas

# A drag near a scroll area's edge scrolls it only after resting there this long, so passing
# through the edge on the way in never shifts the hours under the pointer.
EDGE_PX, DWELL_S, SCROLL_STEP = 36, 0.3, 10


class Gesture(Enum):
    MOVE = "move"
    RESIZE_START = "resize_start"
    RESIZE_END = "resize_end"
    CREATE = "create"
    PLACE = "place"
    MOVE_DATE = "move_date"


@dataclass(frozen=True)
class Verdict:
    """Whether a span can stand, and the words that say so or say why not."""

    ok: bool
    words: str


@dataclass(frozen=True)
class Held:
    """What the pointer holds, fixed at the press."""

    kind: Gesture
    title: str
    minutes: int
    block_id: str | None = None
    from_day: int = -1
    origin: Span | None = None
    grab: int = 0
    # For a Month chip: the date it was lifted from.
    from_iso: str = ""


@dataclass(frozen=True)
class Preview:
    held: Held
    span: Span
    verdict: Verdict


@dataclass(frozen=True)
class Move:
    """A block given a new day, start or end. `from_day` is the copy that was picked up."""

    block_id: str
    from_day: int
    span: Span


@dataclass(frozen=True)
class Place:
    """Homework that had no time, given this one."""

    block_id: str
    span: Span


@dataclass(frozen=True)
class Create:
    span: Span


@dataclass(frozen=True)
class MoveDate:
    block_id: str
    from_iso: str
    to_iso: str


Change = Move | Place | Create | MoveDate
Judge = Callable[[str, int, Span], Verdict]


def span_words(span: Span) -> str:
    return f"{DAYS[span.day]} {_clock(span.start)}–{_clock(span.end)} · {length_label(span.minutes)}"


def _clock(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


class Hand(QObject):
    """The one pointer. The window owns it and applies what it reports."""

    committed = Signal(object)
    refused = Signal(str)
    opened = Signal(str)
    selected = Signal(str, int)
    active_changed = Signal(bool)
    preview_changed = Signal()

    def __init__(self, judge: Judge, host: QWidget) -> None:
        super().__init__(host)
        self._judge, self._host = judge, host
        self.preview: Preview | None = None
        self.selection: tuple[str, int] | None = None
        self.month_target: str | None = None
        self._held: Held | None = None
        self._source: QWidget | None = None
        self._tap: Callable[[], None] | None = None
        self._pressed_at = QPoint()
        self._last = QPoint()
        self._active = False
        self._home: tuple[HoursCanvas, LinearTrack] | None = None
        self._track: tuple[HoursCanvas, LinearTrack] | None = None
        self._edge: tuple[QScrollArea, int, int, float] | None = None
        self._scroller = QTimer(self)
        self._scroller.setInterval(16)
        self._scroller.timeout.connect(self._scroll_tick)
        self._chip = QLabel(host)
        self._chip.setObjectName("heldChip")
        self._chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._chip.hide()

    # What a picked-up thing calls

    @property
    def busy(self) -> bool:
        return self._held is not None

    @property
    def active(self) -> bool:
        return self._active

    def press(
        self,
        source: QWidget,
        held: Held,
        at: QPoint,
        tap: Callable[[], None] | None = None,
        home: tuple[HoursCanvas, LinearTrack] | None = None,
    ) -> None:
        """Pick something up at a global point. `home` is the canvas and track it came from."""
        self._end(silent=True)
        self._held, self._source, self._tap, self._home = held, source, tap, home
        self._pressed_at = self._last = at
        QApplication.instance().installEventFilter(self)

    def select(self, block_id: str, day: int) -> None:
        self.selection = (block_id, day)
        self.selected.emit(block_id, day)
        self.preview_changed.emit()

    def open(self, block_id: str) -> None:
        self._end(silent=True)
        self.opened.emit(block_id)

    def commit(self, change: Change) -> None:
        """For a tap that makes something, such as a click on free time."""
        self.committed.emit(change)

    def cancel(self) -> None:
        self._end(silent=True)

    # Following the pointer

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
            self._moved(event.globalPosition().toPoint())
        elif kind == QEvent.Type.MouseButtonRelease and isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self._released()
        elif kind == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Escape:
                self._end(silent=True)
                return True
        elif kind in (QEvent.Type.ApplicationDeactivate, QEvent.Type.WindowDeactivate):
            self._end(silent=True)
        return False

    def _moved(self, at: QPoint) -> None:
        if self._held is None:
            return
        self._last = at
        if not self._active:
            if (at - self._pressed_at).manhattanLength() < QApplication.startDragDistance():
                return
            self._active = True
            self.active_changed.emit(True)
        self._follow(at)
        self._watch_edge(at)

    def _released(self) -> None:
        held, active, preview, target = self._held, self._active, self.preview, self.month_target
        tap = self._tap
        self._end(silent=True)
        if held is None:
            return
        if not active:
            if tap is not None:
                tap()
            return
        if held.kind is Gesture.MOVE_DATE:
            if target and held.block_id and target != held.from_iso:
                self.committed.emit(MoveDate(held.block_id, held.from_iso, target))
            return
        if preview is None:
            return
        if not preview.verdict.ok:
            if preview.verdict.words:
                self.refused.emit(preview.verdict.words)
            return
        if held.kind is Gesture.CREATE:
            self.committed.emit(Create(preview.span))
        elif held.kind is Gesture.PLACE and held.block_id:
            self.committed.emit(Place(held.block_id, preview.span))
        elif held.block_id and held.origin is not None and preview.span != held.origin:
            self.committed.emit(Move(held.block_id, held.from_day, preview.span))

    # Where the pointer is

    def _follow(self, at: QPoint) -> None:
        held = self._held
        assert held is not None
        if held.kind is Gesture.MOVE_DATE:
            self._follow_month(at)
            return
        if held.kind in (Gesture.RESIZE_START, Gesture.RESIZE_END, Gesture.CREATE):
            found = self._home
        else:
            found = self._hours_at(at) or (self._track if held.kind is Gesture.MOVE else None)
        self._track = found or self._track
        if found is None:
            self._show(None)
            self._float(held.title, at)
            return
        self._chip.hide()
        canvas, track = found
        minute = track.minute_at(QPointF(canvas.mapFromGlobal(at)))
        self._show(self._span_for(held, track, minute))

    def _span_for(self, held: Held, track: LinearTrack, minute: float) -> Span:
        origin = held.origin
        if held.kind is Gesture.RESIZE_START and origin is not None:
            return replace(origin, start=min(max(snap(minute - held.grab), FIRST), origin.end - SLOT_MIN))
        if held.kind is Gesture.RESIZE_END and origin is not None:
            return replace(origin, end=max(min(snap(minute - held.grab), LAST), origin.start + SLOT_MIN))
        if held.kind is Gesture.CREATE and origin is not None:
            here = min(max(snap(minute), FIRST), LAST)
            anchor = origin.start
            start, end = (
                (anchor, max(here, anchor + SLOT_MIN)) if here >= anchor else (here, anchor + SLOT_MIN)
            )
            return Span(origin.day, start, end)
        start = min(max(snap(minute - held.grab), FIRST), LAST - held.minutes)
        return Span(track.day, start, start + held.minutes)

    def _show(self, span: Span | None) -> None:
        held = self._held
        if held is None or span is None:
            changed = self.preview is not None
            self.preview = None
        else:
            if held.kind is Gesture.CREATE:
                verdict = Verdict(True, span_words(span))
            else:
                verdict = self._judge(held.block_id or "", held.from_day, span)
            fresh = Preview(held, span, verdict)
            changed = fresh != self.preview
            self.preview = fresh
        if changed:
            self.preview_changed.emit()

    def _hours_at(self, at: QPoint) -> tuple[HoursCanvas, LinearTrack] | None:
        """The canvas and track under a global point. Cards laid at an angle overlap, so a canvas
        whose rectangle is under the pointer but whose track is not passes to its siblings."""
        from desktop.native.hours.canvas import HoursCanvas

        widget = QApplication.widgetAt(at)
        while widget is not None and not isinstance(widget, HoursCanvas):
            widget = widget.parentWidget()
        if widget is None:
            return None
        tried = [widget]
        parent = widget.parentWidget()
        if parent is not None:
            tried += [
                sibling
                for sibling in reversed(
                    parent.findChildren(HoursCanvas, options=Qt.FindChildOption.FindDirectChildrenOnly)
                )
                if sibling is not widget and sibling.isVisible()
            ]
        for canvas in tried:
            track = canvas.track_at(QPointF(canvas.mapFromGlobal(at)))
            if track is not None:
                return canvas, track
        return None

    def _follow_month(self, at: QPoint) -> None:
        from desktop.native.hours.month import MonthCanvas

        widget = QApplication.widgetAt(at)
        while widget is not None and not isinstance(widget, MonthCanvas):
            widget = widget.parentWidget()
        target = widget.date_at(QPointF(widget.mapFromGlobal(at))) if widget is not None else None
        held = self._held
        assert held is not None
        words = f"{_clock(held.origin.start) if held.origin else ''} {held.title}".strip()
        self._float(words + (f" → {target[8:].lstrip('0')}" if target else ""), at)
        if target != self.month_target:
            self.month_target = target
            self.preview_changed.emit()

    def _float(self, words: str, at: QPoint) -> None:
        self._chip.setText(words)
        self._chip.adjustSize()
        self._chip.move(self._host.mapFromGlobal(at) + QPoint(14, 10))
        self._chip.show()
        self._chip.raise_()

    # Scrolling while held

    def _watch_edge(self, at: QPoint) -> None:
        area = _scroll_area_at(at)
        direction = (0, 0)
        if area is not None:
            inside = area.viewport().mapFromGlobal(at)
            port = area.viewport().rect()
            vertical = area.verticalScrollBar().maximum() > 0
            if vertical:
                direction = (
                    0,
                    -1 if inside.y() < EDGE_PX else 1 if inside.y() > port.height() - EDGE_PX else 0,
                )
            elif area.horizontalScrollBar().maximum() > 0:
                direction = (
                    -1 if inside.x() < EDGE_PX else 1 if inside.x() > port.width() - EDGE_PX else 0,
                    0,
                )
        if area is None or direction == (0, 0):
            self._edge = None
            self._scroller.stop()
            return
        if self._edge is None or self._edge[0] is not area or self._edge[1:3] != direction:
            self._edge = (area, *direction, time.monotonic())
            self._scroller.start()

    def _scroll_tick(self) -> None:
        if self._edge is None or self._held is None:
            self._scroller.stop()
            return
        area, dx, dy, since = self._edge
        if not isValid(area):
            self._edge = None
            return
        if time.monotonic() - since < DWELL_S:
            return
        if dy:
            area.verticalScrollBar().setValue(area.verticalScrollBar().value() + dy * SCROLL_STEP)
        if dx:
            area.horizontalScrollBar().setValue(area.horizontalScrollBar().value() + dx * SCROLL_STEP)
        self._follow(self._last)

    # Letting go

    def _end(self, silent: bool) -> None:
        was_active = self._active
        if self._held is not None:
            QApplication.instance().removeEventFilter(self)
        self._held = self._source = self._tap = None
        self._home = self._track = None
        self._active = False
        self._edge = None
        self._scroller.stop()
        self._chip.hide()
        had = self.preview is not None or self.month_target is not None
        self.preview = None
        self.month_target = None
        if had:
            self.preview_changed.emit()
        if was_active:
            self.active_changed.emit(False)


def _scroll_area_at(at: QPoint) -> QScrollArea | None:
    widget = QApplication.widgetAt(at)
    while widget is not None and not isinstance(widget, QScrollArea):
        widget = widget.parentWidget()
    return widget
