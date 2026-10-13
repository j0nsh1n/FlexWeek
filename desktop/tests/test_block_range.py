"""Every block keeps its time range on screen before the title gives way (T-W35)."""

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
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from desktop.native.hours.canvas import INNER_PAD, BlockPainter, Drawn, block_layout
    from desktop.native.hours.geometry import Span
    from desktop.native.look import EXPERIMENTAL_LOOKS, STANDARD_LOOKS, resolved_palette
    from desktop.native.weekmodel import clock_label, range_label


LOOKS = STANDARD_LOOKS + EXPERIMENTAL_LOOKS
TEXTS = ("small", "normal", "large")


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-block-range-test"])


def layout_times(drawn: Drawn, look: dict | None, text: str, width: float = 128) -> list[str]:
    knobs = {"text": text, **((look or {}).get("knobs") or {})}
    worn = {**(look or {}), "knobs": knobs}
    palette = resolved_palette("system", False, worn)
    painter_obj = BlockPainter(palette, worn)
    title, small = painter_obj.fonts(QFont("Inter", 12))
    rect = QRectF(0, 0, width, 48 - 3)
    room = QRectF(
        rect.left() + 8,
        rect.top() + INNER_PAD,
        rect.width() - 8 - INNER_PAD,
        rect.height() - 2 * INNER_PAD,
    )
    tight = QRectF(room.left(), room.top(), room.width(), room.height())
    layout = block_layout(drawn, title, small, room, tight=tight, book=drawn.work)
    return [line.text for line in layout if not line.title]


@pytest.mark.parametrize(("kind", "name"), LOOKS)
@pytest.mark.parametrize("text", TEXTS)
def test_a_one_hour_block_keeps_its_whole_range_in_every_look_and_text_size(
    qapp: QApplication, kind: str, name: str, text: str
) -> None:
    look = None if kind == "pack" else {"preset": name, "knobs": {}}
    span = Span(1, 16 * 60 + 45, 17 * 60 + 45)
    drawn = Drawn("school", "School hours block", "class", False, span, 0, 1)
    expected = range_label(span.start, span.end)
    lines = layout_times(drawn, look, text)
    assert any(line == expected for line in lines), (name, text, lines)


@pytest.mark.parametrize(("kind", "name"), LOOKS)
@pytest.mark.parametrize("text", TEXTS)
def test_a_range_in_a_96_px_column_is_whole_or_the_start_alone_never_cut(
    qapp: QApplication, kind: str, name: str, text: str
) -> None:
    """T-W35: "16:45–1…" is a cut range, which is worse than the start alone. At Small text the whole
    range still fits 96 px; at Normal and Large it does not, so only the start time stays."""
    look = None if kind == "pack" else {"preset": name, "knobs": {}}
    span = Span(1, 16 * 60 + 45, 17 * 60 + 45)
    drawn = Drawn("school", "School hours block", "class", False, span, 0, 1)
    expected = range_label(span.start, span.end) if text == "small" else clock_label(span.start)
    assert layout_times(drawn, look, text, width=96)[0] == expected, (name, text)


def test_a_block_whose_name_has_no_room_says_so_for_its_tooltip(qapp: QApplication) -> None:
    """T-W35: a 45-minute "Piano lesson" at Large has room for its range only, so its name is in the
    hover tooltip; a two-hour block has room for the name."""
    look = {"preset": "default", "knobs": {"text": "large"}}
    palette = resolved_palette("system", False, look)
    painter_obj = BlockPainter(palette, look)
    font = QFont("Inter", 15)
    visible = QRectF(0, 0, 128, 400)
    short = Drawn("piano", "Piano lesson", "extra", False, Span(1, 19 * 60, 19 * 60 + 45), 0, 1)
    tall = Drawn("piano", "Piano lesson", "extra", False, Span(1, 19 * 60, 21 * 60), 0, 1)
    assert not painter_obj.title_shown(font, QRectF(0, 0, 128, 45 * 48 / 60 - 3), short, visible)
    assert painter_obj.title_shown(font, QRectF(0, 0, 128, 2 * 48 - 3), tall, visible)
