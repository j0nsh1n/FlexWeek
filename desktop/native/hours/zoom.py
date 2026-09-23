"""How close the hours are: the levels a surface offers, the one it shows, and a scroll that keeps
the same minute in place while that changes.

A surface's hours sit in an `HoursScroll`. Ctrl and the wheel zoom about the pointer; Ctrl with =, -
or 0 zoom about the middle of what is on screen, as do the two buttons in the corner above the hour
labels. A header, such as the week's day names, stays above the scrolling hours and always spans
exactly the width the hours have, so a name sits over its column whether or not a scroll bar shows.

Each surface remembers its level on this device, in the look file, as pixels an hour. A level that
is no longer offered is read as the nearest one that is.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QScrollArea, QWidget

from desktop.native.hours.canvas import HoursCanvas

KEY = re.compile(r"[a-z]+\.[a-z]+")


@dataclass(frozen=True)
class Scale:
    """The pixels an hour a surface offers, smallest first, and the one it opens at."""

    key: str
    levels: tuple[int, ...]
    default: int

    def nearest(self, px: object) -> int:
        if not isinstance(px, int) or isinstance(px, bool):
            return self.default
        return min(self.levels, key=lambda level: (abs(level - px), level))

    def step(self, px: int, by: int) -> int:
        at = self.levels.index(self.nearest(px))
        return self.levels[min(max(at + by, 0), len(self.levels) - 1)]


def sanitize_zoom(raw: object) -> dict[str, int]:
    """The remembered levels, whatever the file on disk says."""
    if not isinstance(raw, dict):
        return {}
    clean: dict[str, int] = {}
    for key, px in raw.items():
        if len(clean) >= 32:
            break
        named = isinstance(key, str) and len(key) <= 40 and KEY.fullmatch(key) is not None
        if named and isinstance(px, int) and not isinstance(px, bool) and 8 <= px <= 480:
            clean[key] = px
    return clean


class ZoomButton(QPushButton):
    """A square button whose natural size is the square it is drawn at."""

    side = 24

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.side, self.side)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()


class ZoomButtons(QWidget):
    """Zoom out and zoom in, side by side, for the corner above the hour labels."""

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(f"{name}Zoom")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        self.out = self._button("−", f"{name}ZoomOut", "Zoom out", "Ctrl+-")
        self.into = self._button("+", f"{name}ZoomIn", "Zoom in", "Ctrl+=")
        row.addWidget(self.out)
        row.addWidget(self.into)
        row.addStretch(1)
        self._fit()

    def _fit(self) -> None:
        # Square, and grows with the text, never under 24 pixels a side.
        side = max(24, self.fontMetrics().height() + 8)
        for button in (self.out, self.into):
            button.side = side
            button.setFixedSize(side, side)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._fit()

    def _button(self, face: str, name: str, words: str, keys: str) -> ZoomButton:
        button = ZoomButton(face)
        button.setObjectName(name)
        button.setProperty("zoom", True)
        button.setToolTip(f"{words} on the hours ({keys}; Ctrl+0 goes back)")
        button.setAccessibleName(f"{words} on the hours")
        button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        return button


class HoursScroll(QScrollArea):
    """Hours that scroll and zoom, with a header kept above them."""

    # A level the student chose, to remember: the scale's key and its pixels an hour.
    zoomed = Signal(str, int)

    def __init__(
        self,
        canvas: HoursCanvas,
        scale: Scale,
        length_for: Callable[[int], int],
        *,
        name: str,
        gutter: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"{name}Scroll")
        self.canvas, self.scale = canvas, scale
        self.px = scale.default
        self._length_for = length_for
        self._gutter = gutter
        self._pending: tuple[int, int] | None = None
        # The header first: the scroll area starts filtering events as soon as it holds the hours.
        self.buttons = ZoomButtons(name)
        self.buttons.out.clicked.connect(lambda: self.zoom_by(-1))
        self.buttons.into.clicked.connect(lambda: self.zoom_by(1))
        self.header = QWidget(self)
        self.header.setObjectName(f"{name}Header")
        self._row = QHBoxLayout(self.header)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(0)
        self._row.addWidget(self.buttons, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.header.installEventFilter(self)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(canvas)
        canvas.setFixedHeight(length_for(self.px))
        canvas.zoom_asked.connect(self._asked)
        self._show_limits()

    def set_header(self, content: QWidget) -> None:
        """What sits over the hours, right of the corner. It is exactly as wide as the hours."""
        self._row.addWidget(content, 1)
        self._place_header()

    # Zoom

    def restore(self, remembered: dict[str, int]) -> None:
        """The level this device last chose for this surface, if any. Nothing is remembered again."""
        if self.scale.key in remembered:
            self._apply(self.scale.nearest(remembered[self.scale.key]), None)

    def zoom_by(self, steps: int, anchor: float | None = None) -> None:
        """Zoom in (positive) or out, keeping the minute at `anchor`, a height in the viewport, in
        place. Without one, the middle of what is on screen stays put. Nothing moves while a drag is
        under way: the block under the pointer must stay under it."""
        if self.canvas.hand.busy:
            return
        px = self.scale.default if steps == 0 else self.scale.step(self.px, steps)
        if px != self.px:
            self._apply(px, anchor)
            self.zoomed.emit(self.scale.key, px)

    def _asked(self, steps: int, at: object) -> None:
        anchor = None if at is None else float(at) - self.verticalScrollBar().value()
        self.zoom_by(steps, anchor)

    def _apply(self, px: int, anchor: float | None) -> None:
        bar = self.verticalScrollBar()
        height = self.viewport().height()
        at = height / 2 if anchor is None else min(max(anchor, 0.0), float(height))
        minute = self._minute_at(bar.value() + at)
        self.px = px
        self.canvas.setFixedHeight(self._length_for(px))
        self._show_limits()
        if not self.isVisible():
            return
        self._lay_out_now()
        if minute is not None and self.canvas.tracks:
            bar.setValue(round(self._y_for(minute) - at))

    def _lay_out_now(self) -> None:
        """Give the hours their size and the scroll bar its range now rather than on the next pass,
        so a time can be put on screen straight away."""
        length = self._length_for(self.px)
        self.canvas.resize(self.viewport().width(), length)
        self.canvas.relayout()
        self.verticalScrollBar().setRange(0, max(0, length - self.viewport().height()))

    def _show_limits(self) -> None:
        self.buttons.out.setEnabled(self.px > self.scale.levels[0])
        self.buttons.into.setEnabled(self.px < self.scale.levels[-1])

    # Scrolling to a time

    def scroll_to(self, minute: int, above: int = 90) -> None:
        """Put `minute` near the top, with `above` minutes of the day showing over it. Hours that are
        not on screen yet do it when they are shown, and only then."""
        self._pending = (minute, above)
        if not self.isVisible():
            return
        self._lay_out_now()
        if self.canvas.tracks:
            self._pending = None
            self.verticalScrollBar().setValue(round(self._y_for(minute - above)))

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)
        self._place_header()
        if self._pending is not None:
            self.scroll_to(*self._pending)

    def _minute_at(self, y: float) -> float | None:
        track = self.canvas.tracks[0] if self.canvas.tracks else None
        if track is None:
            return None
        return track.first + (y - track.area.top()) / track.per_minute()

    def _y_for(self, minute: float) -> float:
        track = self.canvas.tracks[0]
        return track.area.top() + track.offset(min(max(minute, track.first), track.last))

    # The header and the corner

    def _place_header(self) -> None:
        row = self.buttons.layout()
        corner = max(self._gutter, float(2 * self.buttons.out.side + row.spacing() + 10))
        if corner != self.canvas.gutter:
            self.canvas.gutter = corner
            self.canvas.relayout()
        self.buttons.setFixedWidth(round(corner))
        self.buttons.layout().setContentsMargins(4, 0, 0, 0)
        tall = max(30, self.header.sizeHint().height())
        if self.viewportMargins().top() != tall:
            self.setViewportMargins(0, tall, 0, 0)
        port = self.viewport().geometry()
        self.header.setGeometry(QRect(port.left(), port.top() - tall, port.width(), tall))

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_header()

    def viewportEvent(self, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Resize:
            # A scroll bar that comes or goes changes the width the hours have.
            self._place_header()
        return super().viewportEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.header and event.type() in (
            QEvent.Type.LayoutRequest,
            QEvent.Type.StyleChange,
            QEvent.Type.FontChange,
        ):
            self._place_header()
        return super().eventFilter(watched, event)
