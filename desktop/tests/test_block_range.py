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
    from PySide6.QtGui import QFont, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from desktop.native.hours.canvas import INNER_PAD, BlockPainter, Drawn, block_layout
    from desktop.native.hours.geometry import Span
    from desktop.native.look import EXPERIMENTAL_LOOKS, STANDARD_LOOKS, resolved_palette
    from desktop.native.weekmodel import range_label


LOOKS = STANDARD_LOOKS + EXPERIMENTAL_LOOKS
TEXTS = ("small", "normal", "large")


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-block-range-test"])


def layout_times(drawn: Drawn, look: dict | None, text: str) -> list[str]:
    knobs = {"text": text, **((look or {}).get("knobs") or {})}
    worn = {**(look or {}), "knobs": knobs}
    palette = resolved_palette("system", False, worn)
    painter_obj = BlockPainter(palette, worn)
    title, small = painter_obj.fonts(QFont("Inter", 12))
    rect = QRectF(0, 0, 128, 48 - 3)
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

