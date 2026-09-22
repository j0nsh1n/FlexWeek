"""Dragging in every design: homework onto a time or a day, and a block to another one.

A design says two things: where a block can be picked up, and what a point on it means. That is an
exact day and time on a painted time axis, a place between two items in a list, or just a day. The
window says whether that works, by the rule Today's app's grid uses, and the design shows the answer
while the pointer is still moving. Nothing changes until the drop, and then only through the window.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, QEvent, QMimeData, QObject, QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QDrag, QDropEvent, QFont, QFontMetrics, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QScrollArea, QWidget

from backend.slots import DAY_END_MIN, DAY_START_MIN, SLOT_MIN
from desktop.native.widgets import SESSION_MIME

if TYPE_CHECKING:
    from desktop.native.layouts.base import LayoutView
    from desktop.native.weekmodel import Occurrence

# Minutes between a block's start and the point it was held by, so a bar dragged by its middle lands
# where its middle is let go rather than jumping its start to the pointer.
GRAB_MIME = "application/x-flexweek-grab"
EDGE_SCROLL_PX, EDGE_SCROLL_STEP = 28, 14


@dataclass(frozen=True)
class Spot:
    """Where a drop would put a block: a day, and a start, or None for the planner's pick that day."""

    day: int
    start: int | None = None


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


@dataclass(frozen=True)
class Mark:
    """How a design shows where a drop would land: a widget outlined, a line between two items, or a
    ghost the widget paints itself."""

    widget: QWidget | None = None
    line: QRect | None = None
    paint: Callable[[Verdict | None], None] | None = None


Where = Callable[[QPoint, Carried], "tuple[Spot, Mark] | None"]


def carried(event: QEvent) -> Carried | None:
    data = event.mimeData()  # type: ignore[attr-defined]
    if not data.hasFormat(SESSION_MIME):
        return None
    block_id = bytes(data.data(SESSION_MIME).data()).decode()
    grab = bytes(data.data(GRAB_MIME).data()).decode() if data.hasFormat(GRAB_MIME) else ""
    return Carried(block_id, int(grab) if grab.lstrip("-").isdigit() else 0)


def snap(minute: float) -> int:
    """The nearest quarter hour inside the hours FlexWeek plans in."""
    return min(max(round(minute / SLOT_MIN) * SLOT_MIN, DAY_START_MIN), DAY_END_MIN - SLOT_MIN)


def slot_up(minute: int) -> int:
    return math.ceil(minute / SLOT_MIN) * SLOT_MIN


def slot_down(minute: int) -> int:
    return math.floor(minute / SLOT_MIN) * SLOT_MIN


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


def start_drag(view: LayoutView, block_id: str, grab: int = 0) -> None:
    """Pick a block up. The drag belongs to the view, which outlives the button it started on."""
    data = QMimeData()
    data.setData(SESSION_MIME, QByteArray(block_id.encode()))
    data.setData(GRAB_MIME, QByteArray(str(grab).encode()))
    drag = QDrag(view)
    drag.setMimeData(data)
    tokens = view.scene.tokens if view.scene is not None else {}
    picture = chip_picture(view.title_of(block_id), tokens, view.devicePixelRatioF())
    drag.setPixmap(picture)
    drag.setHotSpot(QPoint(16, round(picture.height() / picture.devicePixelRatio() / 2)))
    view.drag_began()
    try:
        drag.exec(Qt.DropAction.MoveAction)
    finally:
        view.drag_ended()


class Lift(QObject):
    """Picks a block up off a button once the pointer has moved far enough. A click still opens it."""

    def __init__(self, target: QWidget, block_id: str) -> None:
        super().__init__(target)
        self._target, self._block_id = target, block_id
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
                start_drag(view, self._block_id)
                return True
        elif kind == QEvent.Type.MouseButtonRelease:
            self._at = None
        return False


def liftable(target: QWidget, block_id: str) -> None:
    Lift(target, block_id)


class Pickup:
    """A painted surface's items, picked up the way a button is: press and move to drag, or press and
    let go to open. The open happens on release now, since a press alone may be the start of a drag.
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
        start_drag(view, item.block_id, max(0, min(grab, item.minutes)))

    def release(self, event: QMouseEvent) -> bool:
        held, self._held = self._held, None
        if held is None:
            return False
        self._opened(held[0].block_id)
        return True


class Zone(QObject):
    """Lets `target` take a dropped block. `where` says what a point on it means and how to show it."""

    def __init__(self, view: LayoutView, target: QWidget, where: Where) -> None:
        super().__init__(target)
        self._view, self._target, self._where = view, target, where
        # A widget that outlives a render gets a new zone each time. The last one's answers were about
        # widgets that render deleted, so it goes.
        earlier = getattr(target, "_drop_zone", None)
        if isinstance(earlier, Zone):
            target.removeEventFilter(earlier)
            earlier.deleteLater()
        target._drop_zone = self  # type: ignore[attr-defined]
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
            start = -1 if spot.start is None else spot.start
            self._view.placement_requested.emit(thing.block_id, spot.day, start)
            return True
        verdict = self._view.judge_drop(thing.block_id, spot)
        self._view.show_drop(verdict, mark, self._target.mapTo(self._view, point))
        event.acceptProposedAction()
        return True


def day_zone(view: LayoutView, target: QWidget, day: int) -> None:
    """A day: a block keeps its time there, and homework waiting for one gets the planner's pick."""
    Zone(view, target, lambda _point, _thing: (Spot(day), Mark(widget=target)))


def painted_day_zone(
    view: LayoutView, target: QWidget, day: int, show: Callable[[Verdict | None], None]
) -> None:
    Zone(view, target, lambda _point, _thing: (Spot(day), Mark(paint=show)))


Items = list[tuple[QWidget, "Occurrence"]]


def list_zone(
    view: LayoutView,
    target: QWidget,
    day: int,
    items: Items,
    *,
    vertical: bool = True,
    top: Callable[[], int] | None = None,
    heading: QWidget | None = None,
) -> None:
    """A day's items in time order. A drop between two starts right after the one above; before the
    first, it ends as the first begins. On a list with nothing in it, it is a drop on the day.

    `top` is where the list starts on `target`. Above it a point means nothing, or, when the day's
    `heading` is up there, the day."""

    def where(point: QPoint, thing: Carried) -> tuple[Spot, Mark] | None:
        if top is not None and (point.y() if vertical else point.x()) < top():
            return (Spot(day), Mark(widget=heading)) if heading is not None else None
        return between(view, target, day, items, point, thing, vertical)

    Zone(view, target, where)


def column_zone(view: LayoutView, target: QWidget, columns: list[tuple[QWidget, int, Items]]) -> None:
    """Days side by side, each a heading over its items: the heading is the day, and below it a drop
    goes between two of that day's items. Each column runs from its heading to the next one's."""

    def where(point: QPoint, thing: Carried) -> tuple[Spot, Mark] | None:
        lefts = [heading.mapTo(target, QPoint(0, 0)).x() for heading, _day, _items in columns]
        found = None
        for index, (heading, day, items) in enumerate(columns):
            right = lefts[index + 1] if index + 1 < len(columns) else target.width()
            if lefts[index] <= point.x() < right:
                found = heading, day, items
        if found is None:
            return None
        heading, day, items = found
        if point.y() < heading.mapTo(target, QPoint(0, heading.height())).y():
            return Spot(day), Mark(widget=heading)
        return between(view, target, day, items, point, thing, True)

    Zone(view, target, where)


def between(
    view: LayoutView,
    target: QWidget,
    day: int,
    items: Items,
    point: QPoint,
    thing: Carried,
    vertical: bool,
) -> tuple[Spot, Mark]:
    """The two items a point falls between, and the start that means. A block already in that gap, as
    it is when it is let go where it was, keeps its time. Anything else starts right after the item
    above, or before the first ends as it begins."""
    own = next((item for _widget, item in items if item.block_id == thing.block_id), None)
    # The block being moved is not a neighbour of itself.
    shown = [
        (widget, item) for widget, item in items if item.block_id != thing.block_id and not widget.isHidden()
    ]
    if not shown and own is None:
        return Spot(day), Mark(widget=target)
    spans = [(widget.mapTo(target, QPoint(0, 0)), widget) for widget, _item in shown]
    along = point.y() if vertical else point.x()
    index = len(shown)
    for position, (corner, widget) in enumerate(spans):
        middle = (corner.y() + widget.height() / 2) if vertical else (corner.x() + widget.width() / 2)
        if along < middle:
            index = position
            break
    after = shown[index - 1][1].end if index > 0 else DAY_START_MIN
    before = shown[index][1].start if index < len(shown) else DAY_END_MIN
    if own is not None and after <= own.start and own.end <= before:
        start = own.start
    elif index == 0 and shown:
        start = slot_down(shown[0][1].start - view.minutes_of(thing.block_id))
    else:
        start = slot_up(after)
    start = min(max(start, DAY_START_MIN), DAY_END_MIN - SLOT_MIN)
    line = gap_line(view, target, spans, index, vertical) if spans else QRect()
    return Spot(day, start), (Mark(line=line) if spans else Mark(widget=target))


def gap_line(
    view: LayoutView, target: QWidget, spans: list[tuple[QPoint, QWidget]], index: int, vertical: bool
) -> QRect:
    """The line just after the item a drop would follow, in the view's coordinates. Just after it, not
    halfway to the next: that is what the drop means, and halfway could fall across a label."""
    thick = 4
    if index == 0:
        corner, widget = spans[0]
        edge = (corner.y() if vertical else corner.x()) - 4
    else:
        corner, widget = spans[index - 1]
        edge = (corner.y() + widget.height() if vertical else corner.x() + widget.width()) + 3
    if vertical:
        left = target.mapTo(view, QPoint(corner.x(), edge))
        return QRect(left.x(), left.y() - thick // 2, widget.width(), thick)
    top = target.mapTo(view, QPoint(edge, corner.y()))
    return QRect(top.x() - thick // 2, top.y(), thick, widget.height())


class DropShow:
    """What a view shows during a drag: the answer in a bubble by the pointer, and where it would land.

    The outline, the line and the bubble are the view's own, laid over the design rather than set on
    its buttons, whose own rules would win over any outline given to them."""

    def __init__(self, view: QWidget) -> None:
        self._view = view
        self.outline = self._part(QFrame(view), "dropOutline")
        self.line = self._part(QFrame(view), "dropLine")
        self.hint = self._part(QLabel(view), "dropHint")
        self._mark: Mark | None = None

    @staticmethod
    def _part(widget: QWidget, name: str) -> QWidget:
        widget.setObjectName(name)
        # Never in the way of the drop it is showing: childAt, and so the drag, looks straight through.
        widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        widget.hide()
        return widget

    def show(self, verdict: Verdict, mark: Mark, point: QPoint) -> None:
        if mark != self._mark:
            self.clear()
        self._mark = mark
        state = "ok" if verdict.ok else "refused"
        if mark.widget is not None:
            corner = mark.widget.mapTo(self._view, QPoint(0, 0))
            self._lay(self.outline, QRect(corner, mark.widget.size()).adjusted(-3, -3, 3, 3), state)
        if mark.line is not None:
            self._lay(self.line, mark.line, state)
        if mark.paint is not None:
            mark.paint(verdict)
        assert isinstance(self.hint, QLabel)
        self.hint.setText(verdict.words)
        restyle(self.hint, state)
        self.hint.adjustSize()
        room = self._view.rect()
        left = min(point.x() + 18, room.right() - self.hint.width() - 4)
        below = point.y() + 20
        top = below if below + self.hint.height() < room.bottom() else point.y() - 20 - self.hint.height()
        self.hint.move(max(left, 4), max(top, 4))
        self.hint.setVisible(bool(verdict.words))
        self.hint.raise_()

    @staticmethod
    def _lay(widget: QWidget, where: QRect, state: str) -> None:
        widget.setGeometry(where)
        restyle(widget, state)
        widget.show()
        widget.raise_()

    def clear(self) -> None:
        mark, self._mark = self._mark, None
        if mark is not None and mark.paint is not None:
            mark.paint(None)
        for part in (self.outline, self.line, self.hint):
            part.hide()

    def showing(self) -> str:
        """The bubble's words while it is up, for tests and screen readers."""
        return self.hint.text() if self.hint.isVisible() else ""  # type: ignore[attr-defined]

    def outlined(self) -> QRect | None:
        return self.outline.geometry() if self.outline.isVisible() else None

    def lined(self) -> QRect | None:
        return self.line.geometry() if self.line.isVisible() else None


def restyle(widget: QWidget, state: str) -> None:
    if widget.property("drop") == state:
        return
    widget.setProperty("drop", state)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def scroll_areas(view: QWidget) -> list[QScrollArea]:
    return [area for area in view.findChildren(QScrollArea) if area.isVisible()]
