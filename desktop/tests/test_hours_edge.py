"""Homework state tags and edges use the shared painter across designs and looks."""

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
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from desktop.native.hours.canvas import BlockPainter, Drawn
    from desktop.native.hours.classic import ClassicPainter
    from desktop.native.hours.geometry import Span
    from desktop.native.layouts.bento import BentoPainter
    from desktop.native.layouts.clay import ClayPainter
    from desktop.native.layouts.dial import DialFace
    from desktop.native.layouts.mission import MissionPainter
    from desktop.native.layouts.one_thing import BarPainter
    from desktop.native.layouts.registry import LAYOUTS, MATCH, tokens_for
    from desktop.native.layouts.retro import RetroPainter, scheme
    from desktop.native.layouts.timeline import TimelinePainter
    from desktop.native.look import EXPERIMENTAL_LOOKS, STANDARD_LOOKS, category_paint, resolved_palette
    from desktop.native.weekmodel import Occurrence

RECT = QRectF(20, 20, 140, 100)
PALETTE = resolved_palette("light-frost", False, None, "default")
CATEGORY = "assignments"
LOOKS = {"filled or edged": None, "outlined": {"preset": "default", "knobs": {"blocks": "outline"}}}
# Light and dark, so a design that only ships a table on one axis still has to carry block_edge.
DESIGN_LOOKS = {"light": ("light-frost", False), "dark": ("dark-frost", True)}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-edge-test"])


def block(*, work: bool = True, **more: bool) -> Drawn:
    return Drawn("essay", "History essay", CATEGORY, work, Span(3, 17 * 60, 18 * 60 + 30), 0, 1, **more)


def top_edge(drawn: Drawn, look: dict | None) -> list[QColor]:
    """The pixels along the block's top edge, clear of its rounded corners and its left strip."""
    image = QImage(200, 140, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    BlockPainter(PALETTE, look).body(painter, RECT, drawn)
    painter.end()
    y = int(RECT.top()) + 1
    return [image.pixelColor(x, y) for x in range(int(RECT.left()) + 16, int(RECT.right()) - 16)]


def share(pixels: list[QColor], wanted: str) -> float:
    """How much of the line is `wanted`, give or take the last bits of each channel."""
    goal = QColor(wanted).getRgb()[:3]
    near = [p for p in pixels if all(abs(a - b) <= 6 for a, b in zip(p.getRgb()[:3], goal, strict=True))]
    return len(near) / len(pixels)


def runs(pixels: list[QColor], wanted: str) -> int:
    """How many times the line changes between `wanted` and anything else: a dash is two changes."""
    goal = QColor(wanted).getRgb()[:3]
    marked = [all(abs(a - b) <= 6 for a, b in zip(p.getRgb()[:3], goal, strict=True)) for p in pixels]
    return sum(one != two for one, two in zip(marked, marked[1:], strict=False))


def mark_colour() -> str:
    mark = category_paint(CATEGORY, PALETTE)[1]
    assert mark
    return mark


@pytest.mark.parametrize("look", LOOKS.values(), ids=LOOKS.keys())
def test_homework_flexweek_planned_has_no_dashed_red_edge(qapp: QApplication, look: dict | None) -> None:  # noqa: F811
    mark = mark_colour()
    edge = top_edge(block(), look)
    assert runs(edge, mark) < 6, "the overdue state replaces the old dashed edge"


@pytest.mark.parametrize("look", LOOKS.values(), ids=LOOKS.keys())
def test_homework_the_student_placed_has_a_solid_edge(qapp: QApplication, look: dict | None) -> None:  # noqa: F811
    mark = mark_colour()
    edge = top_edge(block(pinned=True), look)
    assert share(edge, mark) > 0.97 and runs(edge, mark) == 0


def test_homework_being_carried_has_no_gaps_in_its_edge(qapp: QApplication) -> None:  # noqa: F811
    """The ring that marks the carried block is solid, as the edge it will have once dropped."""
    edge = top_edge(block(held=True), None)
    assert len({pixel.name() for pixel in edge}) == 1


def test_history_tags_fit_a_30_minute_block_at_large_text(qapp: QApplication) -> None:  # noqa: F811
    look = {"preset": "default", "knobs": {"text": "large"}}
    painter = BlockPainter(PALETTE, look)
    for state in ("Overdue", "Left from last week"):
        image = QImage(100, 70, QImage.Format.Format_ARGB32)
        image.fill(QColor("white"))
        paint = QPainter(image)
        paint.setFont(QFont("Inter", 14))
        drawn = Drawn("essay", "History essay", CATEGORY, True, Span(3, 17 * 60, 17 * 60 + 30), 0, 1,
                      history=state)
        painter.history_tag(paint, QRectF(15, 15, 70, 38), drawn)
        paint.end()
        assert any(
            image.pixelColor(x, y) != QColor("white")
            for x in range(15, 85)
            for y in range(15, 53)
        ), state
        assert all(
            image.pixelColor(x, y) == QColor("white")
            for x in range(100)
            for y in range(70)
            if x < 15 or x >= 85 or y < 15 or y >= 53
        ), state


def _contrast(first: QColor, second: QColor) -> float:
    def luminance(colour: QColor) -> float:
        values = [colour.redF(), colour.greenF(), colour.blueF()]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("kind,name", STANDARD_LOOKS + EXPERIMENTAL_LOOKS)
def test_history_tag_text_has_accessible_contrast_in_every_look(
    qapp: QApplication, kind: str, name: str
) -> None:
    if kind == "pack":
        look = None
        palette = resolved_palette(name, name in {"dark-frost", "nocturne"}, look)
    else:
        look = {"preset": name, "knobs": {}}
        palette = resolved_palette("light-frost", False, look)
    fill, ink, _outline, _edge = BlockPainter(palette, look).fills(block(history="Overdue"))
    assert _contrast(fill, ink) >= 4.5, name


@pytest.mark.parametrize("drawn", [block(work=False), block(done=True), block(pinned=True, done=True)])
def test_a_fixed_block_and_finished_homework_have_neither_edge(
    qapp: QApplication,  # noqa: F811
    drawn: Drawn,
) -> None:
    assert share(top_edge(drawn, None), mark_colour()) < 0.03


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
def test_each_design_paints_homework_in_its_own_colours(
    qapp: QApplication,  # noqa: F811
    design: str,
    look: str,
    pinned: bool,
) -> None:
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
