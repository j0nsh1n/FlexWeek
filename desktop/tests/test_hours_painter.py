"""A block's words are laid in whole lines: none is cut in half by the edge of the room it has. And
every block is written in the canvas's own font, whatever was drawn before it."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QRect, QRectF
    from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter
    from PySide6.QtWidgets import QApplication, QWidget

    from desktop.native.hours.canvas import BlockPainter, Drawn, HoursCanvas, fit_lines
    from desktop.native.hours.geometry import LinearTrack
    from desktop.native.hours.hand import Hand, Verdict
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week

DETAIL = "16:00–17:30 · 1 h 30 min · Missed · Pinned"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-painter-test"])


def fits(lines: list[str], font: QFont, width: float) -> bool:
    metrics = QFontMetricsF(font)
    return all(metrics.horizontalAdvance(line) <= width for line in lines)


def test_room_for_one_line_gives_one_shortened_line(qapp: QApplication) -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance(DETAIL) / 2
    lines = fit_lines(DETAIL, font, width, metrics.height())
    assert len(lines) == 1
    assert lines[0].endswith("…")
    assert fits(lines, font, width)


def test_room_for_two_and_a_half_lines_gives_two(qapp: QApplication) -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance("16:00–17:30 · 1 h") + 1
    lines = fit_lines(DETAIL, font, width, 2.5 * metrics.lineSpacing())
    assert lines[0] == "16:00–17:30 · 1 h"
    assert len(lines) == 2
    assert lines[1].endswith("…")
    assert fits(lines, font, width)


def test_ample_room_says_it_all(qapp: QApplication) -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance("16:00–17:30 · 1 h") + 1
    lines = fit_lines(DETAIL, font, width, 20 * metrics.lineSpacing())
    assert " ".join(lines) == DETAIL
    assert len(lines) >= 3
    assert fits(lines, font, width)


def test_a_word_wider_than_the_room_is_shortened_and_the_rest_still_follows(qapp: QApplication) -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance("16:00–1")
    lines = fit_lines("16:00–17:30 · 1 h", font, width, 20 * metrics.lineSpacing())
    assert lines[0].endswith("…") and lines[0] != "16:00–17:30"
    assert lines[1:] == ["· 1 h"]
    assert fits(lines, font, width)


def test_no_room_for_a_whole_line_gives_nothing(qapp: QApplication) -> None:
    font = QFont()
    assert fit_lines(DETAIL, font, 400, QFontMetricsF(font).height() - 1) == []


def test_a_short_ghost_shows_only_whole_lines(qapp: QApplication) -> None:
    """A new block too short for its times on two lines says one line, shortened, rather than two
    with the second cut in half by its bottom edge."""
    font = QFont()
    bold = QFont(font)
    bold.setBold(True)
    metrics = QFontMetricsF(bold)
    words = "Thu 16:00–17:30 · 1 h 30 min"
    # The ghost writes 8 px in from its left, 6 from its right and 3 from its top and bottom.
    rect = QRectF(10, 10, metrics.horizontalAdvance("Thu 16:00–17:30") + 16, 1.5 * metrics.lineSpacing() + 6)
    room = rect.adjusted(8, 3, -6, -3)

    def ghost(text: str) -> QImage:
        image = QImage(240, 120, QImage.Format.Format_ARGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setFont(font)
        BlockPainter(resolved_palette("system", False, None)).ghost(painter, rect, text, True)
        painter.end()
        return image

    written, blank = ghost(words), ghost("")
    inked = [
        y
        for y in range(int(room.top()), int(room.bottom()) + 1)
        for x in range(int(room.left()), int(room.right()) + 1)
        if written.pixel(x, y) != blank.pixel(x, y)
    ]
    assert inked, "the ghost says nothing"
    second = room.top() + metrics.lineSpacing()
    assert max(inked) < second, f"a line starting at y {second:.0f} is cut at the ghost's bottom edge"


HOSTS: list = []
ESSAY = {
    "id": "essay",
    "title": "Essay",
    "kind": "locked",
    "days": [0, 1, 2],
    "start": "16:00",
    "duration_min": 90,
}
MATHS = {"id": "maths", "title": "Maths", "kind": "locked", "days": [1], "start": "09:00", "duration_min": 60}


def test_every_block_is_written_in_the_canvas_font_whatever_was_drawn_before_it(qapp: QApplication) -> None:
    """The same Essay on three days, drawn in one paint. On the first day it follows the hour labels,
    on the second it follows Maths, drawn by a painter that, like Mission's, sets a font of its own
    after the default block; on the third it follows nothing. All three are drawn alike."""

    class Marked(BlockPainter):
        def block(self, painter: QPainter, rect: QRectF, drawn: Drawn, visible: QRectF) -> None:
            super().block(painter, rect, drawn, visible)
            painter.setFont(QFont("DejaVu Sans Mono", 8))

    def columns(area: QRectF) -> list[LinearTrack]:
        # Whole pixels apart, so the same block on each day covers the same pixels.
        return [
            LinearTrack(day, QRectF(60 + 150 * day, 10, 140, 600), first=8 * 60, last=20 * 60)
            for day in range(3)
        ]

    host = QWidget()
    HOSTS.append(host)
    canvas = HoursCanvas(
        Hand(lambda block_id, from_day, span: Verdict(True, ""), host),
        Marked(resolved_palette("system", False, None)),
        columns,
        gutter=56,
    )
    canvas.resize(520, 620)
    occurrences = build_week("2026-09-21", [ESSAY, MATHS], {}, None).occurrences
    # Maths first, so on its day the Essay is drawn after it.
    canvas.set_week(sorted(occurrences, key=lambda item: item.block_id != "maths"))
    canvas.relayout()
    image = canvas.grab().toImage()
    boxes = [canvas.block_rect("essay", day) for day in range(3)]
    essays = [image.copy(QRect(canvas.mapFromGlobal(box.topLeft()), box.size())) for box in boxes]
    assert essays[2] == essays[0], "the Essay after the hour labels is drawn unlike the one after nothing"
    assert essays[2] == essays[1], "the Essay after Maths is drawn unlike the one after nothing"
