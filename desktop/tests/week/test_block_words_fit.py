"""A block's words are laid in whole lines: none is cut in half by the edge of the room it has, a word
that is too wide gives way with "…", and with no room for three letters the block says nothing."""

from __future__ import annotations

import importlib.util
import os

import pytest

from desktop.tests.week.support_painter import Said, qapp  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = [
    pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QFont, QFontMetricsF, QImage  # noqa: E402

from desktop.native.hours.canvas import (  # noqa: E402
    TEXT_LEFT,
    TEXT_RIGHT,
    TEXT_TOP,
    BlockPainter,
    Drawn,
    block_layout,
    fit_lines,
    word_elide,
)
from desktop.native.hours.geometry import Span  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.weekmodel import range_label  # noqa: E402

DETAIL = "16:00–17:30 · 1 h 30 min · Missed · Pinned"


def fits(lines: list[str], font: QFont, width: float) -> bool:
    metrics = QFontMetricsF(font)
    return all(metrics.horizontalAdvance(line) <= width for line in lines)


def test_room_for_one_line_gives_one_shortened_line() -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance(DETAIL) / 2
    lines = fit_lines(DETAIL, font, width, metrics.height())
    assert len(lines) == 1
    assert lines[0].endswith("…")
    assert fits(lines, font, width)


def test_room_for_two_and_a_half_lines_gives_two() -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance("16:00–17:30 · 1 h") + 1
    lines = fit_lines(DETAIL, font, width, 2.5 * metrics.lineSpacing())
    assert lines[0] == "16:00–17:30 · 1 h"
    assert len(lines) == 2
    assert lines[1].endswith("…")
    assert fits(lines, font, width)


def test_ample_room_says_it_all() -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance("16:00–17:30 · 1 h") + 1
    lines = fit_lines(DETAIL, font, width, 20 * metrics.lineSpacing())
    assert " ".join(lines) == DETAIL
    assert len(lines) >= 3
    assert fits(lines, font, width)


def test_a_word_wider_than_the_room_is_shortened_and_the_rest_still_follows() -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance("16:00–1")
    lines = fit_lines("16:00–17:30 · 1 h", font, width, 20 * metrics.lineSpacing())
    assert lines[0].endswith("…") and lines[0] != "16:00–17:30"
    assert lines[1:] == ["· 1 h"]
    assert fits(lines, font, width)


def test_a_line_with_room_for_nothing_but_dots_is_left_out() -> None:
    font = QFont()
    width = QFontMetricsF(font).horizontalAdvance("…") + 1
    assert fit_lines("18:00–18:30 · 30 min", font, width, 20 * QFontMetricsF(font).lineSpacing()) == []


def test_no_room_for_a_whole_line_gives_nothing() -> None:
    font = QFont()
    assert fit_lines(DETAIL, font, 400, QFontMetricsF(font).height() - 1) == []


def test_a_length_is_never_broken_between_its_number_and_unit() -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    # Room for "08:00–14:30 · 6" but not for "08:00–14:30 · 6 h".
    width = metrics.horizontalAdvance("08:00–14:30 · 6") + 2
    lines = fit_lines("08:00–14:30 · 6 h 30 min", font, width, metrics.lineSpacing() * 4)
    assert lines == ["08:00–14:30 ·", "6 h 30 min"], lines


def test_a_short_new_block_says_only_whole_lines_of_its_times() -> None:
    """A new block too short for its times on two lines says one line, shortened, rather than two
    with the second cut in half by its bottom edge."""
    font = QFont()
    bold = QFont(font)
    bold.setBold(True)
    metrics = QFontMetricsF(bold)
    words = "Thu 16:00–17:30 · 1 h 30 min"
    # The ghost writes 8 px in from its left, 6 from its right and 3 from its top and bottom.
    rect = QRectF(10, 10, metrics.horizontalAdvance("Thu 16:00–17:30") + 16, 1.5 * metrics.lineSpacing() + 6)
    image = QImage(240, 120, QImage.Format.Format_ARGB32)

    painter = Said(image)
    painter.setFont(font)
    Said.words = []
    BlockPainter(resolved_palette("system", False, None)).ghost(painter, rect, words, True)
    painter.end()
    assert len(Said.words) == 1, "the ghost writes one whole line, not two with the second cut off"
    assert Said.words[0][0].startswith("Thu 16:00")


def test_a_word_too_wide_for_its_block_is_shortened_only_when_nothing_else_fits() -> None:
    """A word is never cut while a smaller arrangement would say it whole; with none, the title gives
    way with "…", and with no room for three letters there are no words at all."""
    title, small = BlockPainter(resolved_palette("system", False, None)).fonts(QFont("Inter", 12))
    tall = QFontMetricsF(title).lineSpacing() * 4
    drawn = Drawn("long", "Photosynthesis", "class", False, Span(1, 9 * 60, 10 * 60), 0, 1)
    whole = QFontMetricsF(title).horizontalAdvance("Photosynthesis")
    said = [line.text for line in block_layout(drawn, title, small, QRectF(0, 0, whole + 2, tall))]
    assert said[0] == "Photosynthesis"
    narrow = [line.text for line in block_layout(drawn, title, small, QRectF(0, 0, whole / 2, tall))]
    assert narrow[0].endswith("…") and narrow[0] != "…"
    three = QFontMetricsF(title).horizontalAdvance("Pho")
    assert block_layout(drawn, title, small, QRectF(0, 0, three - 1, tall)) == []


def test_the_icon_gives_way_before_a_name_is_left_with_fewer_than_three_letters() -> None:
    """The name, then its start, then the icon: with room for "Sch…" and the start but not the icon
    as well, the block says those, not the icon and "Sc…"."""
    title, small = BlockPainter(resolved_palette("system", False, None)).fonts(QFont("Inter", 12))
    tm, sm = QFontMetricsF(title), QFontMetricsF(small)
    drawn = Drawn("school", "Schoolwork", "class", False, Span(1, 9 * 60, 10 * 60), 0, 1)
    icon = 16 + 3
    room = (tm.horizontalAdvance("Sch…"), icon + tm.horizontalAdvance("Sch"), sm.horizontalAdvance("09:00"))
    width = max(room) + 0.5
    assert width < icon + tm.horizontalAdvance("Sch…"), "room for the icon and three letters, not the dots"
    lay = block_layout(drawn, title, small, QRectF(0, 0, width, tm.lineSpacing() * 4), book=True)
    assert [(line.text, line.book) for line in lay if line.title] == [("Sch…", False)]
    assert "09:00" in [line.text for line in lay]


def test_a_short_block_at_large_text_keeps_its_time_range_whole() -> None:
    """At Large text a 45-minute block on the week has room for one line. The range "19:00–19:45"
    stays whole (T-W35): beside it there is no room for "Piano lesson" or "Math worksheet", so the
    title is what goes, whether or not it is homework. The words are whole, never a cut range."""
    large = {"preset": "default", "knobs": {"text": "large"}}
    title, small = BlockPainter(resolved_palette("system", False, None), large).fonts(QFont("Inter", 15))
    # A column of the week beside the rail at 1280, 45 minutes at 48 pixels an hour.
    rect = QRectF(0, 0, 128, 45 * 48 / 60 - 3)
    room = rect.adjusted(TEXT_LEFT, TEXT_TOP, -TEXT_RIGHT, -1)
    tight = QRectF(room.left(), 1, room.width(), rect.height() - 1)

    def said(name: str, homework: bool) -> list[str]:
        span = Span(1, 19 * 60, 19 * 60 + 45)
        drawn = Drawn(name, name, "assignments" if homework else "extra", homework, span, 0, 1)
        return [line.text for line in block_layout(drawn, title, small, room, tight=tight, book=homework)]

    whole = range_label(19 * 60, 19 * 60 + 45)
    assert said("Piano lesson", False) == [whole]
    assert said("Math worksheet", True) == [whole]
    # Qt's elide keeps a letter of the next word ("Math w…"); the title gives way at a space.
    metrics = QFontMetricsF(title)
    assert word_elide("Math worksheet", metrics, 77) == "Math…"
