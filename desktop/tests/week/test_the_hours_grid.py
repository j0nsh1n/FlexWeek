"""The grid under the blocks: a rule at each hour and none between, today washed on a week and not on a
day, the now line carrying its time, and a custom look's settings reaching the painter.

These read what the painter is told to draw (its fills, lines and words), not the pixels that come
of it; how they look together is judged on the pictures (week.hours-grid-rules-and-wash and others)."""

from __future__ import annotations

import importlib.util
import os

import pytest

from desktop.tests.week.support_painter import (  # noqa: F401
    HOUR_PX,
    Inked,
    Said,
    custom_hours,
    qapp,
    three_days,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = [
    pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402

from desktop.native.hours import canvas as canvas_module  # noqa: E402
from desktop.native.hours.canvas import BlockPainter, Drawn  # noqa: E402
from desktop.native.hours.geometry import LinearTrack, Span  # noqa: E402
from desktop.native.look import mix, resolved_palette  # noqa: E402

ESSAY_QUARTER = {
    "id": "essay",
    "title": "Essay",
    "kind": "locked",
    "days": [0, 1, 2],
    "start": "16:00",
    "duration_min": 15,
}


@pytest.mark.parametrize(
    ("pack", "dark", "look", "rule"),
    [
        ("slate", False, None, lambda palette: palette["hairline"]),
        ("dark-frost", True, None, lambda palette: palette["hairline_strong"]),
        ("nocturne", True, None, lambda palette: mix("#e0e4f0", "#0a0e27", 0.08)),
        ("light-frost", False, {"preset": "high-contrast", "knobs": {}}, lambda palette: "#666666"),
    ],
    ids=["light", "dark", "nocturne", "high-contrast"],
)
def test_each_look_names_its_hour_rule(pack: str, dark: bool, look: dict | None, rule) -> None:
    """On a dark look the hour rules take the stronger hairline, since the plain one all but vanished
    on the page; High contrast's are 40 % white, since full white turned the grid into graph paper.
    Nocturne draws looks.css's 8 % of its text."""
    palette = resolved_palette(pack, dark, look)
    assert palette["rule"] == rule(palette)


def test_the_hours_have_a_rule_at_each_hour_and_none_at_the_half() -> None:
    """The dashed half-hour rules crowded the grid. One track from 08:00 to 10:00 at 48 pixels an
    hour gets a horizontal rule at 08:00, 09:00 and 10:00 and none between, in the look's rule
    colour, beside the track's own left edge."""
    track = LinearTrack(0, QRectF(10, 10, 100, 2 * HOUR_PX), first=8 * 60, last=10 * 60)
    for pack, dark in (("slate", False), ("dark-frost", True), ("nocturne", True)):
        palette = resolved_palette(pack, dark, None)
        Inked.clear()
        paint = Inked(QImage(120, 2 * HOUR_PX + 20, QImage.Format.Format_ARGB32))
        BlockPainter(palette).track(paint, track, False)
        paint.end()
        across = [line for line in Inked.lines if line[0].y() == line[1].y()]
        assert [line[0].y() for line in across] == [10.5, 10.5 + HOUR_PX, 10.5 + 2 * HOUR_PX], pack
        assert {line[2].name() for line in Inked.lines} == {QColor(palette["rule"]).name()}, pack


def washes(canvas) -> dict[int, QColor]:
    """The colour each day's whole column was filled with, by day."""
    Inked.clear()
    canvas.grab()
    return {
        track.day: colour for track in canvas.tracks for rect, colour in Inked.fills if rect == track.area
    }


def test_today_is_washed_in_a_little_of_the_text_colour_on_a_week_and_not_at_all_on_a_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 13 of 0.17: 3 % of the text colour at most, never the accent, which picked as Gold
    turned today's column khaki; and none on Day, where washing the one day marks nothing."""
    monkeypatch.setattr(canvas_module, "QPainter", Inked)
    for pack, dark, accent in (("light-frost", False, "gold"), ("dark-frost", True, "default")):
        palette = resolved_palette(pack, dark, None, accent)
        week = washes(three_days(now_min=15 * 60 + 40, palette=palette))
        assert list(week) == [0], f"{pack}: only today's column is washed"
        assert week[0].getRgb()[:3] == QColor(palette["text"]).getRgb()[:3], pack
        assert 0 < week[0].alphaF() <= 0.035, pack
        day = washes(three_days(now_min=15 * 60 + 40, palette=palette, days=1))
        assert day == {}, f"{pack}: a day is not washed"


def test_a_custom_look_sets_todays_wash_the_now_line_and_the_edge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Customise's grid and block settings: today's highlight off, the now line in the text colour,
    and a 6-pixel category edge, where the look's own are a 3 % wash, the accent and 3 pixels."""
    monkeypatch.setattr(canvas_module, "QPainter", Inked)

    def drawn(custom: dict):
        canvas, palette = custom_hours(custom)
        Inked.clear()
        canvas.grab()
        edges = {rect.width() for rect, _ in Inked.fills if rect.width() < 10 and rect.height() > 30}
        now = {line[2].name() for line in Inked.lines if line[3] == 2.0}
        washed = [t.day for t in canvas.tracks for rect, _ in Inked.fills if rect == t.area]
        return palette, washed, now, edges

    plain_palette, washed, now, edges = drawn({"blocks": "edge"})
    assert washed == [0]
    assert now == {QColor(plain_palette["now"]).name()}
    assert edges == {3.0}
    palette, washed, now, edges = drawn(
        {"blocks": "edge", "today_highlight": False, "now_line": "text", "edge_width": 6}
    )
    assert washed == []
    assert now == {QColor(palette["text"]).name()}
    assert edges == {6.0}


def test_the_now_line_carries_the_time_on_a_pill_once_in_the_accent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The line said where now is but not what time it is. At 15:40 it starts from a pill reading
    "15:40" and is drawn in the look's now colour: red is for what cannot be, and now is not that.
    The next block is 20 minutes away, past the dot's reach, so the time is not drawn again on it."""
    monkeypatch.setattr(canvas_module, "QPainter", Inked)
    canvas = three_days(now_min=15 * 60 + 40)
    Inked.clear()
    canvas.grab()
    assert [text for text, _where in Said.words].count("15:40") == 1
    palette = resolved_palette("system", False, None)
    assert {line[2].name() for line in Inked.lines if line[3] == 2.0} == {QColor(palette["now"]).name()}
    assert palette["now"].lower() != palette["error"].lower()


def test_a_now_pill_that_reaches_into_a_block_is_drawn_again_over_its_colour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At 15:55 the line is four pixels above an Essay that starts at 16:00, and the pill on it
    reaches a few pixels into the Essay. That part is drawn over the Essay's colour, as the line is
    where it crosses a block: under the colour, the pill lost its foot. So the time is written twice,
    once on the line and once over the block."""
    monkeypatch.setattr(canvas_module, "QPainter", Inked)
    canvas = three_days(now_min=15 * 60 + 55, blocks=(ESSAY_QUARTER,))
    Inked.clear()
    canvas.grab()
    assert [text for text, _where in Said.words].count("15:55") == 2


def test_a_block_casts_a_shadow_only_when_the_look_has_depth() -> None:
    """Depth none, Paper and High contrast add nothing under a block (its fill is the only shape
    filled). Soft adds one faint cast under it and bold a darker one, both with the block's own
    shape; a dark look casts a stronger one than a light look."""
    essay = Drawn("essay", "History essay", "class", False, Span(1, 9 * 60, 10 * 60), 0, 1)
    contrast = {"preset": "high-contrast", "knobs": {}}
    soft = {"preset": "default", "knobs": {"depth": "soft"}}

    def casts(look: dict, palette: dict) -> list[float]:
        """The alpha of each shape filled before the block's own fill, which is opaque."""
        Inked.clear()
        paint = Inked(QImage(180, 140, QImage.Format.Format_ARGB32))
        BlockPainter(palette, look).body(paint, QRectF(24, 24, 120, 80), essay)
        paint.end()
        return [colour.alphaF() for colour in Inked.paths[:-1]]

    none = {"preset": "default", "knobs": {"depth": "none"}}
    bold = {"preset": "default", "knobs": {"depth": "bold"}}
    light = resolved_palette("light-frost", False, soft)
    assert casts(none, resolved_palette("light-frost", False, none)) == []
    assert casts({"preset": "paper", "knobs": {}}, resolved_palette("light-frost", False, None)) == []
    assert casts(contrast, resolved_palette("light-frost", False, contrast)) == []
    # The palette is High contrast even though the knobs ask for a soft cast.
    assert casts(soft, resolved_palette("light-frost", False, contrast)) == []
    (faint,) = casts(soft, light)
    (darker,) = casts(bold, light)
    (stronger,) = casts(soft, resolved_palette("dark-frost", True, soft))
    assert 0 < faint < darker
    assert stronger > faint
