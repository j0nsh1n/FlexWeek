"""The words a block says: its name and its time, and what gives way when the room is short."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF, QImage

from desktop.native.fonts import load_fonts
from desktop.native.hours.canvas import (
    TEXT_LEFT,
    TEXT_RIGHT,
    TEXT_TOP,
    BlockPainter,
    Drawn,
    Started,
    block_layout,
)
from desktop.native.hours.geometry import Span
from desktop.native.look import resolved_palette
from desktop.native.weekmodel import clock_label, range_label, set_clock_24h, short_clock
from desktop.tests.week.support_material import Said
from desktop.tests.window_support import qapp  # noqa: F401


def _fonts(look: dict | None = None) -> tuple[QFont, QFont]:
    # The bundled Inter, not whatever the computer has: CI has no Inter and fits other words.
    load_fonts()
    painter = BlockPainter(resolved_palette("system", False, look), look)
    return painter.fonts(QFont("Inter", 12))


def _math(
    *, short: bool = False, started: bool = False, large: bool = False
) -> tuple[Drawn, QFont, QFont, QRectF, QRectF]:
    look = {"preset": "default", "knobs": {"text": "large"}} if large else None
    title, small = _fonts(look)
    # A column of the week beside the rail at 1280, 45 minutes at 48 pixels an hour.
    rect = QRectF(0, 0, 128, 45 * 48 / 60 - 3)
    room = rect.adjusted(TEXT_LEFT, TEXT_TOP, -TEXT_RIGHT, -1)
    tight = QRectF(room.left(), 1, room.width(), rect.height() - 1)
    span = Span(1, 17 * 60, 17 * 60 + 45)
    kind = Started if started else Drawn
    drawn = kind("math", "Math worksheet", "assignments", True, span, 0, 1, short=short)
    return drawn, title, small, room, tight


def _said(drawn: Drawn, title: QFont, small: QFont, room: QRectF, tight: QRectF) -> list[str]:
    return [line.text for line in block_layout(drawn, title, small, room, tight=tight, book=drawn.work)]


def test_a_short_block_says_its_name_then_its_start(qapp) -> None:
    """A 45-minute Math worksheet at 17:00 always keeps its whole range; the title is what gives way.
    At Large text the name does not fit, so the painted words are the range alone (the title is in
    the tooltip and the focus tooltip)."""
    start = clock_label(17 * 60)
    ranged = range_label(17 * 60, 17 * 60 + 45)
    for short, started, large in (
        (False, False, False),
        (False, False, True),
        (False, True, False),
    ):
        drawn, title, small, room, tight = _math(short=short, started=started, large=large)
        words = _said(drawn, title, small, room, tight)
        assert ranged in words or start in words, (short, started, large, words)
        if large:
            assert words == [ranged], (short, started, large, words)
        else:
            assert any("Math" in line for line in words), (short, started, large, words)


def test_a_short_block_keeps_its_whole_time_and_cuts_its_name_first(qapp) -> None:
    """The time always shows, whole, and the name is what gets cut. A range that does not fit shows its
    start time alone, never a time cut part-way."""
    title, small = BlockPainter({}).fonts(QFont("Inter", 12))
    room = QRectF(0, 0, 120, 72)
    soccer = Drawn("soccer", "Soccer practice", "sport", False, Span(3, 16 * 60, 17 * 60 + 30), 0, 1)
    whole_times = (range_label(16 * 60, 17 * 60 + 30), clock_label(16 * 60))
    for drawn in (soccer, Drawn(**{**soccer.__dict__, "short": True})):
        lines = [line.text for line in block_layout(drawn, title, small, room)]
        assert any(line in whole_times for line in lines), lines
        assert not any(line.startswith("16:") and line not in whole_times for line in lines), lines
    # Narrow room: the time still shows whole, and the name gives way.
    narrow = QRectF(0, 0, 60, 72)
    lines = [line.text for line in block_layout(soccer, title, small, narrow)]
    assert any(line in whole_times for line in lines), lines


def test_a_blocks_range_stays_on_one_line_and_the_two_times_are_never_stacked(qapp) -> None:
    """At 810 px, and on the 12-hour clock, stacking 08:30 over 14:15 with no dash reads as two
    events. The range stays on one line; the duration is dropped first; then the start alone."""
    title, small = _fonts()
    tm, sm = QFontMetricsF(title), QFontMetricsF(small)
    span = Span(4, 8 * 60 + 30, 14 * 60 + 15)
    drawn = Drawn("school", "School", "class", False, span, 0, 1)
    range_words = range_label(span.start, span.end)
    start, end = clock_label(span.start), clock_label(span.end)
    # Narrower than the range as one extra, wide enough for each time on its own line.
    width = sm.horizontalAdvance(start) + 8
    assert sm.horizontalAdvance(range_words) > width
    room = QRectF(0, 0, width, tm.lineSpacing() * 4 + sm.lineSpacing() * 3)
    extras = [line.text for line in block_layout(drawn, title, small, room) if not line.title]
    assert extras != [start, end], extras
    assert range_words in extras or start in extras or short_clock(span.start) in extras, extras

    set_clock_24h(False)
    drawn12 = Drawn("school", "School", "class", False, span, 0, 1)
    range12 = range_label(span.start, span.end)
    assert "–" in range12
    start12 = clock_label(span.start)
    width12 = sm.horizontalAdvance(start12) + 8
    room12 = QRectF(0, 0, width12, tm.lineSpacing() * 4 + sm.lineSpacing() * 3)
    extras12 = [line.text for line in block_layout(drawn12, title, small, room12) if not line.title]
    assert extras12 != [clock_label(span.start), clock_label(span.end)], extras12
    assert range12 in extras12 or short_clock(span.start) in extras12, extras12


def test_overlapping_blocks_cut_the_title_first_and_keep_the_time_whole(qapp) -> None:
    """Two blocks that share a time are half a column. Wrapping leftover words of the title beside
    the neighbour reads as a second event, such as "Soccer | Pract... extra"."""
    title, small = _fonts()
    tm = QFontMetricsF(title)
    span = Span(1, 16 * 60, 17 * 60)
    practice = Drawn("practice", "Practice extra", "extra", False, span, 1, 2)
    width = tm.horizontalAdvance("Pract") + 12
    room = QRectF(0, 0, width, tm.lineSpacing() * 4)
    words = [line.text for line in block_layout(practice, title, small, room)]
    extras = [line.text for line in block_layout(practice, title, small, room) if not line.title]
    assert extras != [clock_label(span.start), clock_label(span.end)], words
    assert "extra" not in words, words


def test_mission_timeline_and_clay_painters_at_810_keep_a_short_blocks_start_and_a_range_on_one_line(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At 810 px a 45-minute Math worksheet keeps its name and its start; a 08:30–14:15 block never
    stacks those times as two events."""
    from desktop.native.fonts import load_fonts
    from desktop.native.hours import canvas as canvas_module
    from desktop.native.layouts.clay import ClayPainter, slots
    from desktop.native.layouts.mission import MissionPainter
    from desktop.native.layouts.registry import MATCH, tokens_for
    from desktop.native.layouts.timeline import TimelinePainter

    load_fonts()
    monkeypatch.setattr(canvas_module, "QPainter", Said)
    palette = resolved_palette("light-frost", False, None, "default")
    math = Drawn("math", "Math worksheet", "assignments", True, Span(1, 17 * 60, 17 * 60 + 45), 0, 1)
    span = Span(0, 8 * 60 + 30, 14 * 60 + 15)
    school = Drawn("school", "School", "class", False, span, 0, 1)
    ranged = range_label(span.start, span.end)
    start = clock_label(span.start)
    end = clock_label(span.end)
    page = QRectF(0, 0, 800, 800)
    clay_w = slots(810, 632, 3, 1.0, wide=False)[3].width()
    painters = {
        "mission": (
            MissionPainter(tokens_for("mission", MATCH, palette)),
            QRectF(40, 40, 39, 36),
            QRectF(40, 90, 361, 36),
        ),
        "timeline": (
            TimelinePainter(tokens_for("timeline", MATCH, palette)),
            QRectF(40, 40, 78.5, 24),
            QRectF(40, 90, 78.5, 231),
        ),
        "clay": (
            ClayPainter(tokens_for("clay", MATCH, palette), full=True),
            QRectF(40, 40, clay_w, 45 * 38 / 60),
            QRectF(40, 90, clay_w, 6 * 38),
        ),
    }

    def said(painter, rect, drawn) -> list[str]:
        image = QImage(900, 400, QImage.Format.Format_ARGB32)
        paint = Said(image)
        paint.setFont(QFont("Inter", 13))
        Said.words = []
        painter.block(paint, rect, drawn, page)
        paint.end()
        return [text for text, _where in Said.words]

    for name, (painter, short_rect, range_rect) in painters.items():
        if name == "mission":
            painter.taken = {math.span.day: (0.0, 800.0, []), school.span.day: (0.0, 800.0, [])}
        short_words = said(painter, short_rect, math)
        # Timeline's 45-minute block at 810 is 78.5×24 px. The whole range does not fit, so the start
        # stands alone and the name goes to the tooltip. Mission writes the start beside the bar;
        # Clay's card is wide enough for name and start.
        if name == "timeline":
            assert short_words == ["17:00"], (name, short_words)
        else:
            assert any("Math" in text for text in short_words), (name, short_words)
            assert any("17:00" in text for text in short_words), (name, short_words)
        range_words = said(painter, range_rect, school)
        extras = [text for text in range_words if text in (start, end, ranged) or "–" in text]
        assert extras != [start, end], (name, range_words)
        assert ranged in range_words or start in extras, (name, range_words)
