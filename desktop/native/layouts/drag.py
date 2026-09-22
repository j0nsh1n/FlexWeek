"""Dragging in every design: a block picked up wherever a design shows it, and put down at a time.

Designs with hours of their own, Mission control's lanes, the Day dial's face and One thing's day bar,
take a drop at the time under the pointer. The others open a day's hours beside themselves while a
block is dragged (layouts/drawer.py), so every drop, in every design, is at a time. The window says
whether it can go there, by the rule Today's app's calendar uses, and the design shows the answer
while the pointer is still moving. Nothing changes until the drop, and then only through the window.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, QEvent, QMimeData, QObject, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QDrag, QDropEvent, QFont, QFontMetrics, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QWidget

from backend.slots import DAY_END_MIN, DAY_START_MIN, SLOT_MIN
from desktop.native.widgets import SESSION_MIME

if TYPE_CHECKING:
    from desktop.native.layouts.base import LayoutView
    from desktop.native.weekmodel import Occurrence

# Minutes between a block's start and the point it was held by, so a bar dragged by its middle lands
# where its middle is let go rather than jumping its start to the pointer.
GRAB_MIME = "application/x-flexweek-grab"
# The day it was lifted from. A block that repeats moves only that day's copy.
DAY_MIME = "application/x-flexweek-day"
EDGE_SCROLL_PX, EDGE_SCROLL_STEP = 28, 14


@dataclass(frozen=True)
class Spot:
    """Where a drop would put a block: a day and a start."""

    day: int
    start: int


@dataclass(frozen=True)
class Verdict:
    """Whether a block can go at a spot, and the words that say so or say why not."""

    ok: bool
    words: str
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True)
class Carried:
    block_id: str
    grab: int = 0
    from_day: int = -1


@dataclass(frozen=True)
class Mark:
    """How a painted time axis shows where a drop would land: it paints the ghost itself."""

    paint: Callable[[Verdict | None], None]


Where = Callable[[QPoint, Carried], "tuple[Spot, Mark] | None"]


def _number(data: QMimeData, kind: str, fallback: int) -> int:
    if not data.hasFormat(kind):
        return fallback
    words = bytes(data.data(kind).data()).decode()
    return int(words) if words.lstrip("-").isdigit() else fallback


def carried(event: QEvent) -> Carried | None:
    data = event.mimeData()  # type: ignore[attr-defined]
    if not data.hasFormat(SESSION_MIME):
        return None
    block_id = bytes(data.data(SESSION_MIME).data()).decode()
    return Carried(block_id, _number(data, GRAB_MIME, 0), _number(data, DAY_MIME, -1))


def snap(minute: float) -> int:
    """The nearest quarter hour inside the hours FlexWeek plans in."""
    return min(max(round(minute / SLOT_MIN) * SLOT_MIN, DAY_START_MIN), DAY_END_MIN - SLOT_MIN)


def host_view(widget: QWidget) -> LayoutView | None:
    from desktop.native.layouts.base import LayoutView

    parent: QWidget | None = widget
    while parent is not None and not isinstance(parent, LayoutView):
        parent = parent.parentWidget()
    return parent


def chip_picture(title: str, tokens: dict[str, str], ratio: float) -> QPixmap:
    """What follows the pointer: the block's name on a pill in the design's accent, however large the
    card it was lifted from."""
    font = QFont(QApplication.font())
    font.setPixelSize(13)
    font.setBold(True)
    metrics = QFontMetrics(font)
    words = metrics.elidedText(title, Qt.TextElideMode.ElideRight, 240)
    width, height = metrics.horizontalAdvance(words) + 28, metrics.height() + 14
    picture = QPixmap(round(width * ratio), round(height * ratio))
    picture.setDevicePixelRatio(ratio)
    picture.fill(Qt.GlobalColor.transparent)
    painter = QPainter(picture)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    fill = QColor(tokens.get("accent", "#3b82f6"))
    fill.setAlphaF(0.94)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(fill)
    painter.drawRoundedRect(QRectF(0, 0, width, height), height / 2, height / 2)
    painter.setPen(QColor(tokens.get("accent_ink", "#ffffff")))
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, width, height), Qt.AlignmentFlag.AlignCenter, words)
    painter.end()
    return picture


def start_drag(view: LayoutView, block_id: str, grab: int = 0, from_day: int = -1) -> None:
    """Pick a block up. The drag belongs to the view, which outlives the button it started on."""
    data = QMimeData()
    data.setData(SESSION_MIME, QByteArray(block_id.encode()))
    data.setData(GRAB_MIME, QByteArray(str(grab).encode()))
    data.setData(DAY_MIME, QByteArray(str(from_day).encode()))
    drag = QDrag(view)
    drag.setMimeData(data)
    tokens = view.scene.tokens if view.scene is not None else {}
    picture = chip_picture(view.title_of(block_id), tokens, view.devicePixelRatioF())
    drag.setPixmap(picture)
    drag.setHotSpot(QPoint(16, round(picture.height() / picture.devicePixelRatio() / 2)))
    view.drag_began(block_id, from_day)
    try:
        drag.exec(Qt.DropAction.MoveAction)
    finally:
        view.drag_ended()


class Lift(QObject):
    """Picks a block up off a button once the pointer has moved far enough. A click still opens it."""

    def __init__(self, target: QWidget, block_id: str, day: int = -1) -> None:
        super().__init__(target)
        self._target, self._block_id, self._day = target, block_id, day
        self._at: QPoint | None = None
        target.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self._at = event.position().toPoint()
        elif kind == QEvent.Type.MouseMove and isinstance(event, QMouseEvent) and self._at is not None:
            moved = (event.position().toPoint() - self._at).manhattanLength()
            view = host_view(self._target)
            if moved >= QApplication.startDragDistance() and view is not None:
                self._at = None
                down = getattr(self._target, "setDown", None)
                if down is not None:
                    down(False)
                start_drag(view, self._block_id, 0, self._day)
                return True
        elif kind == QEvent.Type.MouseButtonRelease:
            self._at = None
        return False


def liftable(target: QWidget, block_id: str, day: int = -1) -> None:
    Lift(target, block_id, day)


class Pickup:
    """A painted surface's items, picked up the way a button is: press and move to drag, or press and
    let go to open. The open happens on release, since a press alone may be the start of a drag.
    `minute_at` is the time under a point on a time axis, so a bar keeps where it was held."""

    def __init__(
        self,
        widget: QWidget,
        item_at: Callable[[QPointF], Occurrence | None],
        opened: Callable[[str], None],
        minute_at: Callable[[QPointF], int] | None = None,
    ) -> None:
        self._widget, self._item_at, self._opened, self._minute_at = widget, item_at, opened, minute_at
        self._held: tuple[Occurrence, QPointF] | None = None
        widget.setMouseTracking(True)

    def press(self, event: QMouseEvent) -> bool:
        found = self._item_at(event.position()) if event.button() == Qt.MouseButton.LeftButton else None
        self._held = (found, event.position()) if found is not None else None
        return found is not None

    def move(self, event: QMouseEvent) -> None:
        if self._held is None:
            over = self._item_at(event.position()) is not None
            self._widget.setCursor(Qt.CursorShape.OpenHandCursor if over else Qt.CursorShape.ArrowCursor)
            return
        item, at = self._held
        if (event.position() - at).manhattanLength() < QApplication.startDragDistance():
            return
        self._held = None
        view = host_view(self._widget)
        if view is None:
            return
        grab = self._minute_at(at) - item.start if self._minute_at is not None else 0
        start_drag(view, item.block_id, max(0, min(grab, item.minutes)), item.day)

    def release(self, event: QMouseEvent) -> bool:
        held, self._held = self._held, None
        if held is None:
            return False
        self._opened(held[0].block_id)
        return True


class Zone(QObject):
    """Lets a painted time axis take a dropped block. `where` says what a point on it means."""

    def __init__(self, view: LayoutView, target: QWidget, where: Where) -> None:
        super().__init__(target)
        self._view, self._target, self._where = view, target, where
        target.setAcceptDrops(True)
        target.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QEvent.Type.DragLeave:
            self._view.clear_drop()
            return False
        if kind not in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            return False
        thing = carried(event)
        if thing is None:
            return False
        assert isinstance(event, QDropEvent)
        point = event.position().toPoint()
        found = self._where(point, thing)
        self._view.edge_scroll(self._target.mapTo(self._view, point))
        if found is None:
            if kind == QEvent.Type.DragEnter:
                # Taken, so the moves that follow come here and may reach a part that does mean something.
                event.acceptProposedAction()
                return True
            self._view.clear_drop()
            event.ignore()
            return True
        spot, mark = found
        if kind == QEvent.Type.Drop:
            self._view.clear_drop()
            event.acceptProposedAction()
            self._view.placement_requested.emit(thing.block_id, thing.from_day, spot.day, spot.start)
            return True
        verdict = self._view.judge_drop(thing.block_id, thing.from_day, spot)
        self._view.show_drop(verdict, mark, self._target.mapTo(self._view, point))
        event.acceptProposedAction()
        return True


class DropShow:
    """The answer by the pointer while a block is dragged over a painted time axis. The bubble is the
    view's own, laid over the design, so no rule of the design's can hide it."""

    def __init__(self, view: QWidget) -> None:
        self._view = view
        self.hint = QLabel(view)
        self.hint.setObjectName("dropHint")
        # Never in the way of the drop it is showing: childAt, and so the drag, looks straight through.
        self.hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hint.hide()
        self._mark: Mark | None = None

    def show(self, verdict: Verdict, mark: Mark, point: QPoint) -> None:
        if mark != self._mark:
            self.clear()
        self._mark = mark
        mark.paint(verdict)
        self.hint.setText(verdict.words)
        restyle(self.hint, "ok" if verdict.ok else "refused")
        self.hint.adjustSize()
        room = self._view.rect()
        left = min(point.x() + 18, room.right() - self.hint.width() - 4)
        below = point.y() + 20
        top = below if below + self.hint.height() < room.bottom() else point.y() - 20 - self.hint.height()
        self.hint.move(max(left, 4), max(top, 4))
        self.hint.setVisible(bool(verdict.words))
        self.hint.raise_()

    def clear(self) -> None:
        mark, self._mark = self._mark, None
        if mark is not None:
            mark.paint(None)
        self.hint.hide()

    def showing(self) -> str:
        """The bubble's words while it is up, for tests and screen readers."""
        return self.hint.text() if self.hint.isVisible() else ""


def restyle(widget: QWidget, state: str) -> None:
    if widget.property("drop") == state:
        return
    widget.setProperty("drop", state)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def scroll_areas(view: QWidget) -> list[QScrollArea]:
    return [area for area in view.findChildren(QScrollArea) if area.isVisible()]
