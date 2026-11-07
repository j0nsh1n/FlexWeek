"""Homework blocks take their colours from the look in every design, and their state tags and
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
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402

from desktop.native.hours.canvas import BlockPainter, Drawn  # noqa: E402
from desktop.native.hours.classic import ClassicPainter  # noqa: E402
from desktop.native.hours.geometry import Span  # noqa: E402
from desktop.native.layouts.bento import BentoPainter  # noqa: E402
from desktop.native.layouts.clay import ClayPainter  # noqa: E402
from desktop.native.layouts.dial import DialFace  # noqa: E402
from desktop.native.layouts.mission import MissionPainter  # noqa: E402
from desktop.native.layouts.one_thing import BarPainter  # noqa: E402
from desktop.native.layouts.registry import LAYOUTS, MATCH, tokens_for  # noqa: E402
from desktop.native.layouts.retro import RetroPainter, scheme  # noqa: E402
from desktop.native.layouts.timeline import TimelinePainter  # noqa: E402
from desktop.native.look import (  # noqa: E402
    EXPERIMENTAL_LOOKS,
    STANDARD_LOOKS,
    block_paint,
    category_paint,
    class_outline,
    contrast,
    resolved_palette,
)
from desktop.native.weekmodel import Occurrence  # noqa: E402

RECT = QRectF(20, 20, 140, 100)
PALETTE = resolved_palette("light-frost", False, None, "default")
CATEGORY = "assignments"
# Light and dark, so a design that only ships a table on one axis still has to carry block_edge.
DESIGN_LOOKS = {"light": ("light-frost", False), "dark": ("dark-frost", True)}


def block(*, work: bool = True, **more: bool) -> Drawn:
    return Drawn("essay", "History essay", CATEGORY, work, Span(3, 17 * 60, 18 * 60 + 30), 0, 1, **more)


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


@pytest.mark.parametrize("kind,name", STANDARD_LOOKS + EXPERIMENTAL_LOOKS)
def test_history_tag_text_has_accessible_contrast_in_every_look(kind: str, name: str) -> None:
    if kind == "pack":
        look = None
        palette = resolved_palette(name, name in {"dark-frost", "nocturne"}, look)
    else:
        look = {"preset": name, "knobs": {}}
        palette = resolved_palette("light-frost", False, look)
    fill, ink, _outline, _edge = BlockPainter(palette, look).fills(block(history="Overdue"))
    assert _contrast(fill, ink) >= 4.5, name


def test_a_30_minute_block_at_large_text_has_no_room_for_a_state_pill() -> None:
    """A half-hour block at Large has no room for a pill above its words, so the paint loop does not
    draw one (see BlockPainter.pills_fit); its state stays in the tooltip and the accessible name."""
    look = {"preset": "default", "knobs": {"text": "large"}}
    painter = BlockPainter(PALETTE, look)
    for state in ("Overdue", "Left from last week"):
        span = Span(3, 17 * 60, 17 * 60 + 30)
        drawn = Drawn("essay", "History essay", CATEGORY, True, span, 0, 1, history=state)
        pill_block = QRectF(0, 0, 128, 30 * 48 / 60 - 3)
        assert not painter.pills_fit(QFont("Inter", 14), pill_block, drawn, QRectF(0, 0, 128, 200)), state


def design_painter(design: str, palette: dict) -> BlockPainter | None:
    """The painter that design actually hands the hours, in that look's colours. Dial has no hours
    painter: it draws homework on the ring."""
    if design == "classic":
        return ClassicPainter(palette)
    if design == "dial":
        return None
    tokens = tokens_for(design, MATCH, palette)
    if design == "timeline":
        return TimelinePainter(tokens)
    if design == "mission":
        return MissionPainter(tokens)
    if design == "bento":
        return BentoPainter(tokens)
    if design == "clay":
        return ClayPainter(tokens, full=True)
    if design == "retro":
        return RetroPainter(scheme(tokens))
    if design == "one":
        return BarPainter(tokens, None)
    raise AssertionError(f"no painter wired for {design}")


@pytest.mark.parametrize("design", list(LAYOUTS))
@pytest.mark.parametrize("look", DESIGN_LOOKS, ids=list(DESIGN_LOOKS))
@pytest.mark.parametrize("pinned", [False, True], ids=["planned", "pinned"])
def test_each_design_paints_homework_in_its_own_colours(design: str, look: str, pinned: bool) -> None:
    """Timeline, Mission and Bento used to raise KeyError: 'block_edge' on every homework block."""
    pack, dark = DESIGN_LOOKS[look]
    palette = resolved_palette(pack, dark, None)
    painter = design_painter(design, palette)
    drawn = block(pinned=pinned)
    if painter is None:
        face = DialFace(0, False)
        face.resize(240, 240)
        item = Occurrence(
            "essay",
            "History essay",
            CATEGORY,
            0,
            17 * 60,
            18 * 60 + 30,
            True,
            False,
            False,
            None,
            None,
            None,
            pinned,
        )
        face.set_day((item,), 0, tokens_for("dial", MATCH, palette))
        face.grab()
        return
    image = QImage(200, 140, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    paint = QPainter(image)
    paint.setFont(QFont("Inter", 12))
    try:
        painter.block(paint, RECT, drawn, RECT.adjusted(-4, -4, 4, 4))
    finally:
        paint.end()
    assert "block_edge" in painter.colours
