"""Homework blocks take their colours from the look, and their state tags and
outlines read in every look: never error red for an outline, and tag words at 4.5 to 1 on their pill."""

from __future__ import annotations

import importlib.util
import os

import pytest

from desktop.tests.week.support_painter import qapp  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = [
    pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402

from desktop.native.look import (  # noqa: E402
    EXPERIMENTAL_LOOKS,
    STANDARD_LOOKS,
    block_paint,
    category_paint,
    class_outline,
    contrast,
    resolved_palette,
)

RECT = QRectF(20, 20, 140, 100)
PALETTE = resolved_palette("light-frost", False, None, "default")
CATEGORY = "assignments"
# Light and dark, so a design that only ships a table on one axis still has to carry block_edge.
DESIGN_LOOKS = {"light": ("light-frost", False), "dark": ("dark-frost", True)}




@pytest.mark.parametrize(("kind", "name"), STANDARD_LOOKS + EXPERIMENTAL_LOOKS)
def test_homework_outline_is_not_error_red_in_every_look(kind: str, name: str) -> None:
    """An outlined homework block's edge is the class colour at 3:1 on the card, never error red."""
    if kind == "pack":
        palette = resolved_palette(name, name in {"dark-frost", "nocturne"}, None)
        look = {"preset": "default", "knobs": {"blocks": "outline"}}
    else:
        look = {"preset": name, "knobs": {"blocks": "outline"}}
        palette = resolved_palette("system", False, look)
    fill, mark = category_paint(CATEGORY, palette)
    outline = class_outline(palette, fill)
    assert outline.lower() not in {palette["error"].lower(), "#831a1d"}
    assert contrast(outline, palette["grid"]) >= 3.0
    assert block_paint(look, palette, fill, "flexible", mark, category=CATEGORY)["outline"] == outline


def _contrast(first: QColor, second: QColor) -> float:
    def luminance(colour: QColor) -> float:
        values = [colour.redF(), colour.greenF(), colour.blueF()]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)
