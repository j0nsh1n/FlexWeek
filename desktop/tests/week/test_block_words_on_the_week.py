"""What a block on the week says, in the words a student reads: its name and times as far as the room
goes, and nothing but its colour when there is no room for three letters. The font a block is written
in is judged in the picture review."""

from __future__ import annotations

import importlib.util
import os

import pytest

from desktop.tests.week.support_painter import (  # noqa: F401
    CLUB,
    DINNER,
    ESSAY,
    HOUR_PX,
    MATHS,
    Said,
    custom_hours,
    lane_week,
    qapp,
    three_days,
    words_on,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = [
    pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtCore import QPoint, QRect, QRectF  # noqa: E402
from PySide6.QtGui import QFont, QFontMetricsF, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.fonts import load_fonts  # noqa: E402
from desktop.native.hours import canvas as canvas_module  # noqa: E402
from desktop.native.hours.canvas import BlockPainter, Drawn  # noqa: E402
from desktop.native.hours.geometry import Span  # noqa: E402
from desktop.native.hours.zoom import HoursScroll  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.weekmodel import minute_of  # noqa: E402


@pytest.mark.parametrize("points", [9, 13])
def test_a_block_with_no_room_for_three_letters_is_its_colour_alone(
    monkeypatch: pytest.MonkeyPatch, points: int
) -> None:
    """A week of lanes at 64 pixels an hour draws the 30-minute Dinner 30 pixels wide: no room for
    three letters of its name. Decision 14 of 0.17: below three letters, the colour alone, not "D"
    seven times down the week and not lines of "…". A block with room still says its name."""
    monkeypatch.setattr(canvas_module, "QPainter", Said)
    app = QApplication.instance()
    usual = QFont(app.font())
    font = QFont(usual)
    font.setPointSize(points)
    app.setFont(font)
    try:
        canvas = lane_week(app)
        assert canvas.block_rect("dinner", 0).width() < 34
        Said.words = []
        canvas.repaint()
        school = words_on(canvas, "school", 0)
        # Dinner in view, or it says nothing because it is off screen, whatever the check for letters.
        scroll = canvas.parentWidget()
        while not isinstance(scroll, HoursScroll):
            scroll = scroll.parentWidget()
        scroll.scroll_to(minute_of("18:00"))
        app.processEvents()
        port = scroll.viewport()
        seen = QRect(port.mapToGlobal(QPoint(0, 0)), port.size())
        assert all(seen.contains(canvas.block_rect("dinner", day)) for day in range(7))
        Said.words = []
        canvas.repaint()
    finally:
        app.setFont(usual)
    for day in range(7):
        assert words_on(canvas, "dinner", day) == [], f"Dinner on day {day}"
    assert school[0].startswith("School")


def test_a_block_says_the_most_it_can_without_cutting_a_word_or_ending_a_line_in_a_dot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 14 of 0.17. Club at 19:00 for an hour says its name and its times at the week's 48
    pixels an hour, and its length on a line of its own once there is room. A half-hour Dinner has no
    room for its name beside its range, so the range alone stays (T-W35: the time line first, the
    title cut first). No line ends in "·", which 0.16 left dangling after every time."""
    monkeypatch.setattr(canvas_module, "QPainter", Said)
    for hour_px, club in ((HOUR_PX, ["Club", "19:00–20:00"]), (96, ["Club", "19:00–20:00", "1 h"])):
        canvas = three_days(blocks=(CLUB, DINNER), hour_px=hour_px)
        Said.words = []
        canvas.grab()
        assert words_on(canvas, "club", 1) == club, hour_px
        assert not any(text.rstrip().endswith("·") for text, _where in Said.words)
    canvas = three_days(blocks=(DINNER,))
    Said.words = []
    canvas.grab()
    assert words_on(canvas, "dinner", 1) == ["18:30–19:00"]


def test_a_half_of_a_column_names_its_block_to_the_last_word_it_has_room_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Homework dropped on Soccer leaves each of them half a column. A half that has room for
    "Math…" says that, not "M…", and then its start, as every short block does (#13)."""
    monkeypatch.setattr(canvas_module, "QPainter", Said)
    load_fonts()
    blocks = BlockPainter(resolved_palette("system", False, None))
    title, _small = blocks.fonts(QFont("Inter", 11))
    need = QFontMetricsF(title).horizontalAdvance("Math…")
    # A block alone keeps 8 pixels before its words and 5 after; a half keeps 4 pixels fewer in all.
    wide = need + 9 + 0.5
    image = QImage(300, 200, QImage.Format.Format_ARGB32)
    page = QRectF(0, 0, 300, 200)
    drawn = Drawn("math", "Math worksheet", "homework", True, Span(1, 16 * 60 + 15, 17 * 60), 1, 2)
    paint = Said(image)
    paint.setFont(QFont("Inter", 11))
    Said.words, Said.inks = [], []
    blocks.block(paint, QRectF(20, 20, wide, 33), drawn, page)
    paint.end()
    assert [text for text, _where in Said.words] == ["Math…", "16:15"]


def test_a_half_hour_in_high_contrast_says_its_name_on_the_week(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """High contrast's text is Large, where a half-hour on the week is one caption line exactly. Kept a
    pixel clear of its top, the words said nothing, and High contrast draws blocks as outlines, so
    there was no colour to say it either: an empty box. Its range, which T-W35 keeps first, says it."""
    monkeypatch.setattr(canvas_module, "QPainter", Said)
    look = {"preset": "high-contrast", "knobs": {}}
    palette = resolved_palette("system", False, look)
    dinner = {
        "id": "dinner",
        "title": "Dinner",
        "kind": "locked",
        "category": "meals",
        "days": [0],
        "start": "18:30",
        "duration_min": 30,
    }
    canvas = three_days(blocks=(dinner,), palette=palette)
    canvas.set_painter(BlockPainter(palette, look))
    Said.words = []
    canvas.grab()
    assert "18:30–19:00" in [text for text, _where in Said.words]


def test_a_custom_look_can_leave_out_a_blocks_times_or_its_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(canvas_module, "QPainter", Said)
    for shown, missing, custom in (
        ("16:00–17:30", "1 h 30 min", {"show_lengths": False}),
        ("1 h 30 min", "16:00–17:30", {"show_times": False}),
    ):
        canvas, _palette = custom_hours(custom)
        Said.words = []
        canvas.grab()
        written = " ".join(text for text, _where in Said.words)
        assert shown in written and missing not in written, custom


def test_a_block_shadow_does_not_change_its_words(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cast is paint under the fill. The words on the block stay the ones depth none draws."""
    monkeypatch.setattr(canvas_module, "QPainter", Said)

    def written(depth: str) -> list[str]:
        look = {"preset": "default", "knobs": {"depth": depth}}
        palette = resolved_palette("light-frost", False, look)
        canvas = three_days(palette=palette)
        canvas.set_painter(BlockPainter(palette, look))
        Said.words = []
        canvas.grab()
        return [text for text, _where in Said.words]

    flat = written("none")
    assert flat
    assert written("soft") == flat
    assert written("bold") == flat
