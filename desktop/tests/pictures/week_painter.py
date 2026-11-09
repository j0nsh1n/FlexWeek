"""Week screens for the hours painter: what the old painter tests asserted about colours, pixels,
positions and fit, now judged on pictures. Each screen builds its widget (a canvas or a sheet of
blocks) and ignores the window it is given; the code half of each old test is in
desktop/tests/week/test_block_words_*.py, test_the_hours_grid.py and the tests beside them."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.fonts import load_fonts
from desktop.native.hours.canvas import BlockPainter, Drawn, HoursCanvas
from desktop.native.hours.classic import ClassicPainter
from desktop.native.hours.geometry import FIRST, LAST, Axis, LinearTrack, Span
from desktop.native.hours.hand import Hand, Verdict
from desktop.native.look import resolved_palette
from desktop.native.weekmodel import build_week
from desktop.tests.pictures.screen import Screen
from desktop.tests.week.support_painter import (
    CLUB,
    DINNER,
    ESSAY,
    HOSTS,
    MATHS,
    custom_hours,
    lane_week,
    three_days,
)

CANVAS = "desktop/native/hours/canvas.py"
GEOMETRY = "desktop/native/hours/geometry.py"
LOOK = "desktop/native/look.py"
SOURCES = (CANVAS, GEOMETRY, LOOK)


class Sheet(QWidget):
    """A widget that paints what `draw` is told to, on the light window colour, so blocks and rules
    are photographed as the painter makes them."""

    def __init__(self, width: int, height: int, draw: Callable[[QPainter], None]) -> None:
        super().__init__()
        self._draw = draw
        self.resize(width, height)
        HOSTS.append(self)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(resolved_palette("light-frost", False, None)["window"]))
        painter.setFont(QFont("Inter", 12))
        self._draw(painter)
        painter.end()


def _app() -> QApplication:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    return app


def _grid(window: object) -> object:
    load_fonts()
    palette = resolved_palette("light-frost", False, None, "gold")
    return three_days(now_min=15 * 60 + 40, palette=palette)


def _day(window: object) -> object:
    load_fonts()
    palette = resolved_palette("light-frost", False, None, "gold")
    return three_days(now_min=15 * 60 + 40, palette=palette, days=1)


def _now_over_block(window: object) -> object:
    return three_days(now_min=15 * 60 + 55, blocks=({**ESSAY, "duration_min": 15},))


def _custom_grid(window: object) -> object:
    canvas, _palette = custom_hours(
        {"blocks": "edge", "today_highlight": False, "now_line": "text", "edge_width": 6}
    )
    return canvas


def _words_on_the_week(window: object) -> object:
    return three_days(blocks=(CLUB, DINNER, MATHS))


def _same_font(window: object) -> object:
    class Marked(BlockPainter):
        def block(self, painter: QPainter, rect: QRectF, drawn: Drawn, visible: QRectF) -> None:
            super().block(painter, rect, drawn, visible)
            painter.setFont(QFont("DejaVu Sans Mono", 8))

    def columns(area: QRectF) -> list[LinearTrack]:
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
    canvas.set_week(sorted(occurrences, key=lambda item: item.block_id != "maths"))
    canvas.relayout()
    return canvas


def _high_contrast(window: object) -> object:
    look = {"preset": "high-contrast", "knobs": {}}
    palette = resolved_palette("system", False, look)
    dinner = {**DINNER, "category": "meals", "days": [0, 1, 2]}
    piano = {
        "id": "piano",
        "title": "Piano lesson",
        "kind": "locked",
        "days": [1],
        "start": "19:00",
        "duration_min": 45,
    }
    canvas = three_days(blocks=(dinner, piano), palette=palette)
    canvas.set_painter(BlockPainter(palette, look))
    return canvas


def _lanes(window: object) -> object:
    canvas = lane_week(_app())
    return canvas.window()


def _lane_edge(window: object) -> object:
    """Lanes scrolled so 08:00 sits on the left edge of what shows."""
    canvas = lane_week(_app())
    scroll = canvas._scroll_area()
    track = canvas.tracks[0]
    scroll.horizontalScrollBar().setValue(round(track.area.left() + track.offset(8 * 60)))
    _app().processEvents()
    return canvas.window()


def _body(drawn: Drawn, look: dict | None, palette: dict) -> Callable[[QPainter, QRectF], None]:
    def paint(painter: QPainter, rect: QRectF) -> None:
        BlockPainter(palette, look).body(painter, rect, drawn)

    return paint


def _depths(window: object) -> object:
    essay = Drawn("essay", "History essay", "class", False, Span(1, 9 * 60, 10 * 60), 0, 1)
    contrast = {"preset": "high-contrast", "knobs": {}}
    soft = {"preset": "default", "knobs": {"depth": "soft"}}
    cases = [
        ({"preset": "default", "knobs": {"depth": "none"}}, resolved_palette("light-frost", False, None)),
        (soft, resolved_palette("light-frost", False, soft)),
        ({"preset": "default", "knobs": {"depth": "bold"}}, resolved_palette("light-frost", False, soft)),
        (contrast, resolved_palette("light-frost", False, contrast)),
        (soft, resolved_palette("dark-frost", True, soft)),
    ]

    def draw(painter: QPainter) -> None:
        for index, (look, palette) in enumerate(cases):
            _body(essay, look, palette)(painter, QRectF(14 + index * 130, 14, 116, 80))

    return Sheet(14 + 130 * len(cases), 110, draw)


def _homework_edges(window: object) -> object:
    palette = resolved_palette("light-frost", False, None, "default")
    states = [
        (True, {}),
        (True, {"pinned": True}),
        (True, {"held": True}),
        (False, {}),
        (True, {"done": True}),
    ]
    looks = [None, {"preset": "default", "knobs": {"blocks": "outline"}}]

    def draw(painter: QPainter) -> None:
        for row, look in enumerate(looks):
            for column, (work, flags) in enumerate(states):
                drawn = Drawn(
                    "essay", "History essay", "assignments", work, Span(3, 1020, 1110), 0, 1, **flags
                )
                box = QRectF(14 + column * 112, 14 + row * 100, 100, 84)
                BlockPainter(palette, look).body(painter, box, drawn)

    return Sheet(14 + 112 * len(states), 14 + 100 * len(looks), draw)


def _cut_by_view(window: object) -> object:
    """One block with the edge of what shows moved across it from each side."""
    load_fonts()
    palette = resolved_palette("system", False, None)
    drawn = Drawn("lab", "Photosynthesis lab", "class", False, Span(1, 540, 600), 0, 1)
    rect = QRectF(20, 20, 170, 90)
    cuts = [
        QRectF(60, 0, 400, 300),
        QRectF(0, 0, 130, 300),
        QRectF(0, 60, 400, 300),
        QRectF(0, 0, 400, 80),
    ]

    def draw(painter: QPainter) -> None:
        for index, visible in enumerate(cuts):
            painter.save()
            painter.translate(index * 210, 0)
            painter.setClipRect(visible.translated(0, 0).intersected(QRectF(0, 0, 210, 140)))
            BlockPainter(palette).block(painter, rect, drawn, visible)
            painter.restore()

    return Sheet(210 * len(cuts), 140, draw)


def _shared_and_half(window: object) -> object:
    palette = resolved_palette("system", False, None)
    alone = Drawn("soccer", "Soccer practice", "extra", False, Span(1, 960, 1050), 0, 1)
    shared = Drawn("soccer", "Soccer practice", "extra", False, Span(1, 960, 1050), 0, 2)
    math = Drawn("math", "Math worksheet", "homework", True, Span(1, 975, 1020), 1, 2)

    def draw(painter: QPainter) -> None:
        painter.setFont(QFont("Inter", 11))
        painter.translate(10, 10)
        BlockPainter(palette).block(painter, QRectF(0, 0, 60, 90), alone, QRectF(0, 0, 400, 200))
        BlockPainter(palette).block(painter, QRectF(90, 0, 60, 90), shared, QRectF(0, 0, 400, 200))
        BlockPainter(palette).block(painter, QRectF(180, 0, 62, 33), math, QRectF(0, 0, 400, 200))

    return Sheet(270, 110, draw)


def _icons(window: object) -> object:
    palette = resolved_palette("system", False, None)
    drawn = Drawn("school", "School", "class", False, Span(0, 480, 660), 0, 1)

    def draw(painter: QPainter) -> None:
        blocks = BlockPainter(palette)
        for index, height in enumerate((20, 26, 32, 40, 60)):
            blocks.block(painter, QRectF(10 + index * 120, 10, 110, height), drawn, QRectF(0, 0, 700, 200))

    return Sheet(620, 90, draw)


def _ghost(window: object) -> object:
    def draw(painter: QPainter) -> None:
        bold = QFont(painter.font())
        bold.setBold(True)
        height = 1.5 * painter.fontMetrics().lineSpacing() + 6
        width = painter.fontMetrics().horizontalAdvance("Thu 16:00–17:30") + 16
        BlockPainter(resolved_palette("system", False, None)).ghost(
            painter, QRectF(10, 10, width, height), "Thu 16:00–17:30 · 1 h 30 min", True
        )

    return Sheet(240, 80, draw)


def _scaled_rules(window: object) -> object:
    palette = resolved_palette("light-frost", False, None, "default")

    def draw(painter: QPainter) -> None:
        painter.scale(1.25, 1.25)
        down = LinearTrack(0, QRectF(10, 10, 80, 150), first=FIRST, last=LAST)
        across = LinearTrack(1, QRectF(110, 10, 150, 60), Axis.ACROSS, first=FIRST, last=LAST)
        ClassicPainter(palette).track(painter, down, False)
        ClassicPainter(palette).track(painter, across, False)

    return Sheet(360, 230, draw)


def _pills(window: object) -> object:
    palette = resolved_palette("light-frost", False, None, "default")
    look = {"preset": "default", "knobs": {"text": "large"}}

    def draw(painter: QPainter) -> None:
        painter.setFont(QFont("Inter", 14))
        for index, state in enumerate(("Overdue", "Left from last week")):
            span = Span(3, 17 * 60, 17 * 60 + 30)
            drawn = Drawn("essay", "History essay", "assignments", True, span, 0, 1, history=state)
            BlockPainter(palette, look).history_tag(painter, QRectF(15 + index * 100, 15, 70, 38), drawn)

    return Sheet(220, 70, draw)


def _screen(
    id_: str, prepare: Callable[[object], object], checks: str, *, main: bool = False, sources=SOURCES
) -> Screen:
    return Screen(id_, "week", prepare, checks, sources, main=main)


SCREENS: list[Screen] = [
    _screen(
        "week.hours-grid-rules-and-wash",
        _grid,
        "A rule at each hour and none at the half, one pixel row each, in the look's rule colour: the "
        "stronger hairline on a dark look, 40 % white in High contrast, 8 % of the text in Nocturne, "
        "Ink and Terminal. Today's column is washed in a little (3 % at most) of the text colour, "
        "never the accent: picked as Gold it must not turn khaki; the other days are not washed. "
        "Every time on the hours (labels and blocks) is in figures of one width, so 11:00 is as wide "
        "as 20:00. The now line is in the look's now colour, not red, starting from a pill with 15:40 "
        "level with the line at its start.",
        main=True,
    ),
    _screen(
        "week.hours-day-without-wash",
        _day,
        "On hours of one day today's column is not washed: washing the one day marks nothing.",
    ),
    _screen(
        "week.now-pill-over-block",
        _now_over_block,
        "At 15:55 the line is four pixels above a quarter-hour Essay and the pill reaches a few pixels "
        "into it. That part is drawn over the Essay's colour, whole, with its foot; on a block too "
        "short to say its name the pill is left out of the words.",
    ),
    _screen(
        "week.custom-look-grid-and-edge",
        _custom_grid,
        "With today's highlight off, today is not washed; the now line is in the text colour, not the "
        "accent; the category edge on each block is 6 pixels wide (the look's own is 3), and 5 pixels "
        "in is still the edge colour.",
    ),
    _screen(
        "week.block-words-on-the-week",
        _words_on_the_week,
        "Club (an hour at 48 px an hour) says its name and its times inside the block; Dinner (half an "
        "hour) says its range alone; no line ends in a dot; no word is cut in half by a block's edge.",
    ),
    _screen(
        "week.blocks-in-one-font",
        _same_font,
        "The same Essay on three days looks alike: after the hour labels, after Maths and after "
        "nothing, same font, same words, same pixels.",
    ),
    _screen(
        "week.half-hour-in-high-contrast",
        _high_contrast,
        "High contrast's Large text: a half-hour Dinner draws as an outline with its range inside it, "
        "not an empty box, and the words sit inside the block; a 45-minute Piano lesson keeps its "
        "whole range.",
    ),
    _screen(
        "week.lanes-week-small-blocks",
        _lanes,
        "On lanes at 64 pixels an hour a 30-minute Dinner is about 30 pixels wide and shows its colour "
        "alone: no letters, no row of dots, and no lone initial seven times down the week; blocks "
        "with room still say their name.",
    ),
    _screen(
        "week.hour-label-at-the-view-edge",
        _lane_edge,
        "Scrolled so 08:00 sits on the left edge of what shows, the label 08:00 is written whole inside "
        "what shows, not cut to ')8:00'; the same at the right edge for 20:00.",
    ),
    _screen(
        "week.block-depth-and-shadow",
        _depths,
        "Depth none and High contrast add nothing under a block; soft adds a faint cast one pixel under "
        "it and bold a darker cast in that same pixel, never a larger one; dark looks a stronger cast; "
        "the corners keep the block's radius.",
        sources=(CANVAS, LOOK),
    ),
    _screen(
        "week.homework-block-edges",
        _homework_edges,
        "Planned homework has no dashed red edge; homework the student placed has a solid edge in its "
        "class colour; homework being carried has a solid ring with no gaps; a fixed block and "
        "finished homework have neither; an outlined block's edge is the class colour, never error red.",
        sources=(CANVAS, LOOK),
    ),
    _screen(
        "week.words-cut-by-the-edge-of-view",
        _cut_by_view,
        "With the left, right, top or bottom edge of what shows moved across a block, each word that "
        "is written lies whole inside what shows, and when nothing fits only the colour is left; no "
        "word is cut in half at the edge.",
    ),
    _screen(
        "week.shared-time-and-half-columns",
        _shared_and_half,
        "A block that shares its time looks like one that does not (no corner dot, no mark on the name); "
        "a half column with room for 'Math…' says that and then its start, and no word runs out of the "
        "half.",
    ),
    _screen(
        "week.category-icon-in-short-blocks",
        _icons,
        "A category icon is 16 pixels and sits wholly inside the block at every height that draws one; "
        "it does not poke out of a short block.",
    ),
    _screen(
        "week.new-block-ghost-whole-lines",
        _ghost,
        "A new block too short for its times on two lines shows one shortened line, not two with the "
        "second cut in half by the bottom edge.",
    ),
    _screen(
        "week.state-pill-in-a-short-block",
        _pills,
        "A state pill ('Overdue', 'Left from last week') drawn into the 70 by 38 room of a half-hour "
        "block at Large text stays inside that room: nothing is inked outside it.",
        sources=(CANVAS,),
    ),
    _screen(
        "week.hour-rules-at-125-percent",
        _scaled_rules,
        "At 125 % scale each hour rule is one crisp pixel row, not two pale rows; a down track is "
        "closed by a one-pixel vertical rule on its left, an across track by a horizontal rule on its "
        "top, each inked end to end.",
    ),
]
