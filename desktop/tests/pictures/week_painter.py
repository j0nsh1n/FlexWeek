"""Week screens for the hours painter: what the old painter tests asserted about colours, pixels,
positions and fit, now judged on pictures. Each screen builds its widget (a canvas or a sheet of
blocks) and ignores the window it is given; the code half of each old test is in
desktop/tests/week/test_block_words_*.py, test_the_hours_grid.py and the tests beside them."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.fonts import load_fonts
from desktop.native.look import resolved_palette
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
]
