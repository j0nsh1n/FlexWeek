"""Where minutes are: the geometry every design's hours share.

A track is one day's stretch of time inside a painted widget: a rectangle, the minutes at its two
ends, which way time runs, and a turn for a card laid at an angle. A widget can hold several (a week
of columns, a day cut into tiles). Everything here is plain arithmetic on Qt's point and rectangle
types, so it is tested with numbers and knows nothing about gestures or painting.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QTransform

from backend.slots import DAY_END_MIN, DAY_START_MIN, SLOT_MIN

FIRST, LAST = DAY_START_MIN, DAY_END_MIN
# Space between blocks that share a time, and between a block and its track's sides.
GAP = 2.0


class Axis(Enum):
    DOWN = "down"
    ACROSS = "across"


@dataclass(frozen=True)
class Span:
    day: int
    start: int
    end: int

    @property
    def minutes(self) -> int:
        return self.end - self.start


def snap(minute: float) -> int:
    return round(minute / SLOT_MIN) * SLOT_MIN


@dataclass(frozen=True)
class LinearTrack:
    """A day's minutes laid along a straight line: down a column or across a lane.

    `area` is where the track lies before it is turned; `turn` is degrees clockwise about the area's
    centre, for a card laid at an angle. Points in and out are in the owning widget's coordinates.
    """

    day: int
    area: QRectF
    axis: Axis = Axis.DOWN
    first: int = FIRST
    last: int = LAST
    turn: float = 0.0
    _into: QTransform = field(init=False, repr=False, compare=False)
    _back: QTransform = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        centre = self.area.center()
        into = QTransform()
        into.translate(centre.x(), centre.y())
        into.rotate(self.turn)
        into.translate(-centre.x(), -centre.y())
        object.__setattr__(self, "_into", into)
        object.__setattr__(self, "_back", into.inverted()[0])

    @property
    def transform(self) -> QTransform:
        """From the track's own upright frame to the widget: what a painter sets to draw on it."""
        return self._into

    @property
    def length(self) -> float:
        return self.area.height() if self.axis is Axis.DOWN else self.area.width()

    def per_minute(self) -> float:
        return self.length / (self.last - self.first)

    def upright(self, point: QPointF) -> QPointF:
        return self._back.map(point)

    def minute_at(self, point: QPointF) -> float:
        """The minute under a point, past either end too: a drag that leaves the track keeps a time."""
        local = self.upright(point)
        along = local.y() - self.area.top() if self.axis is Axis.DOWN else local.x() - self.area.left()
        return self.first + along / self.per_minute()

    def contains(self, point: QPointF) -> bool:
        return self.area.contains(self.upright(point))

    def offset(self, minute: float) -> float:
        """How far along the track, from its start edge, a minute lies."""
        return (minute - self.first) * self.per_minute()

    def rect_for(self, start: int, end: int, column: int = 0, columns: int = 1) -> QRectF:
        """Where a span is drawn, in the track's upright frame, as one of `columns` side by side."""
        start, end = max(start, self.first), min(end, self.last)
        if self.axis is Axis.DOWN:
            width = (self.area.width() - 2 * GAP) / columns
            return QRectF(
                self.area.left() + GAP + column * width,
                self.area.top() + self.offset(start) + 1,
                width - GAP,
                max(self.offset(end) - self.offset(start) - 2, 4.0),
            )
        height = (self.area.height() - 2 * GAP) / columns
        return QRectF(
            self.area.left() + self.offset(start) + 1,
            self.area.top() + GAP + column * height,
            max(self.offset(end) - self.offset(start) - 2, 4.0),
            height - GAP,
        )

    def point_for(self, minute: int) -> QPointF:
        """The middle of the track at a minute, in the widget's coordinates."""
        if self.axis is Axis.DOWN:
            upright = QPointF(self.area.center().x(), self.area.top() + self.offset(minute))
        else:
            upright = QPointF(self.area.left() + self.offset(minute), self.area.center().y())
        return self._into.map(upright)


Track = LinearTrack


def overlap_columns(spans: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """Side by side for spans that overlap: each one's column and how many share its time, in the
    order given. Daily Scheduler's assign_overlap_cols. By position, not by value, since a repeating
    block dragged onto another of its days can be two equal spans."""
    order = sorted(range(len(spans)), key=lambda at: spans[at])
    ends: list[int] = []
    column = [0] * len(spans)
    for at in order:
        start = spans[at][0]
        free = next((index for index, end in enumerate(ends) if end <= start), len(ends))
        if free == len(ends):
            ends.append(0)
        ends[free] = spans[at][1]
        column[at] = free
    return [
        (
            column[at],
            max(column[other] for other, (s, e) in enumerate(spans) if s < end and start < e) + 1,
        )
        for at, (start, end) in enumerate(spans)
    ]
