"""An hour label that sits within a line of the now marker is the one the painter holds back: at 36 px an
hour, 16:00 is 12 px from 15:40, less than a label is tall."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from desktop.native.hours.canvas import BlockPainter
from desktop.native.hours.geometry import LinearTrack


def test_the_four_oclock_label_is_within_a_line_of_the_now_marker_at_3_40() -> None:
    painter = BlockPainter({"axis": "light", "muted": "#64748b", "window": "#ffffff"})
    painter.now_in_gutter = True
    painter.now_minute = 15 * 60 + 40
    track = LinearTrack(0, QRectF(60, 0, 100, 1000))
    tall = 18.0
    gap = abs(track.offset(16 * 60) - track.offset(painter.now_minute))
    assert gap < tall, "16:00 is within collision suppression distance of 15:40"
