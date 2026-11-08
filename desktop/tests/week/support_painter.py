"""What the hours-painter tests share: the app, a painter that keeps what it writes and draws, and
the few canvases they build.

Other Week tests import `qapp`, `Said`, `three_days` and `words_on` from here (they came from
test_hours_painter.py)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402

from desktop.native.fonts import load_fonts  # noqa: E402
from desktop.native.hours.canvas import BlockPainter, HoursCanvas  # noqa: E402
from desktop.native.hours.geometry import Axis, LinearTrack  # noqa: E402
from desktop.native.hours.hand import Hand, Verdict  # noqa: E402
from desktop.native.hours.zoom import HoursScroll, Scale  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.weekmodel import build_week, minute_of  # noqa: E402

# The week every layout test builds from (the same one test_weekmodel.py holds).
WEEK = "2026-09-14"
HOMEWORK = {
    "chem": {"id": "chem", "title": "Chem lab report", "due": "2026-09-17T23:59", "completed": False},
    "essay": {"id": "essay", "title": "History essay", "due": "2026-09-18T21:00", "completed": False},
    "poster": {"id": "poster", "title": "Science fair poster", "due": "2026-09-20T20:00", "completed": False},
    "math": {"id": "math", "title": "Math worksheet", "due": "2026-09-15T08:00", "completed": True},
}


def _block(
    block_id: str, kind: str, days: list[int], start: str | None, minutes: int, **extra: object
) -> dict:
    return {
        "id": block_id,
        "title": extra.pop("title", block_id.title()),
        "kind": kind,
        "category": extra.pop("category", "class" if kind == "locked" else "assignments"),
        "days": days,
        "start": start,
        "duration_min": minutes,
        **extra,
    }


BLOCKS = [
    _block("school", "locked", [0, 1, 2, 3, 4], "08:00", 390),
    _block("dinner", "locked", [0, 1, 2, 3, 4, 5, 6], "18:00", 30, category="meals"),
    _block("chem-1", "flexible", [3], None, 90, assignment_id="chem"),
    _block("essay-1", "flexible", [3], "18:45", 60, assignment_id="essay"),
    _block("poster-1", "flexible", [], None, 120, assignment_id="poster"),
    _block("math-1", "flexible", [0, 1], "15:45", 45, assignment_id="math", completed=True, completed_day=0),
]
TRACE = {
    "placed": [_block("chem-1", "flexible", [3], "20:00", 90, assignment_id="chem")],
    "unplaced": [_block("poster-1", "flexible", [], None, 120, assignment_id="poster")],
    "explanations": [
        {
            "block_id": "chem-1",
            "message": "Finishes only 2 h 29 min before it's due.",
            "slack_min": 149,
            "slack_status": "danger",
        },
        {
            "block_id": "essay-1",
            "message": "Finishes 25 h 15 min before it's due.",
            "slack_min": 1515,
            "slack_status": "tight",
        },
        {
            "block_id": "poster-1",
            "message": "There isn't enough time left before it's due, even with nothing else planned.",
            "reason": "DEADLINE_MISS",
        },
    ],
}

ESSAY = {
    "id": "essay",
    "title": "Essay",
    "kind": "locked",
    "days": [0, 1, 2],
    "start": "16:00",
    "duration_min": 90,
}
MATHS = {"id": "maths", "title": "Maths", "kind": "locked", "days": [1], "start": "09:00", "duration_min": 60}
CLUB = {"id": "club", "title": "Club", "kind": "locked", "days": [1], "start": "19:00", "duration_min": 60}
DINNER = {
    "id": "dinner",
    "title": "Dinner",
    "kind": "locked",
    "days": [1],
    "start": "18:30",
    "duration_min": 30,
}

HOUR_PX = 48

# Widgets a test builds are parented here so they live as long as the test module.
HOSTS: list = []


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-painter-test"])


class Said(QPainter):
    """A painter that keeps every word it writes, where, and the ink it covers, in the widget's
    coordinates. Put in place of the canvas module's QPainter, it is the one a real paint event
    draws with."""

    words: list[tuple[str, QRectF]] = []
    inks: list[tuple[str, QRectF]] = []
    fonts: list[tuple[str, QFont]] = []

    def drawText(self, *args: object) -> None:  # noqa: N802
        text = next(arg for arg in reversed(args) if isinstance(arg, str))
        where = next(arg for arg in args if isinstance(arg, (QRectF, QRect, QPointF)))
        box = QRectF(where, where) if isinstance(where, QPointF) else QRectF(where)
        flags = next((arg for arg in args if isinstance(arg, (int, Qt.AlignmentFlag))), 0)
        ink = QFontMetricsF(self.font()).boundingRect(box, int(flags), text)
        Said.words.append((text, self.worldTransform().mapRect(box)))
        Said.inks.append((text, self.worldTransform().mapRect(ink)))
        Said.fonts.append((text, QFont(self.font())))
        super().drawText(*args)


class Inked(Said):
    """Said, and the fills, filled shapes and straight lines it is told to draw, each with the colour
    (and a line's width) it was given: what the painter was asked to do, not the pixels that came of it."""

    fills: list[tuple[QRectF, QColor]] = []
    lines: list[tuple[QPointF, QPointF, QColor, float]] = []
    paths: list[QColor] = []

    def fillPath(self, *args: object) -> None:  # noqa: N802
        if len(args) == 2 and isinstance(args[1], QColor):
            Inked.paths.append(QColor(args[1]))
        super().fillPath(*args)

    def fillRect(self, *args: object) -> None:  # noqa: N802
        if len(args) == 2 and isinstance(args[0], (QRectF, QRect)) and isinstance(args[1], QColor):
            Inked.fills.append((QRectF(args[0]), QColor(args[1])))
        super().fillRect(*args)

    def drawLine(self, *args: object) -> None:  # noqa: N802
        if len(args) == 2 and all(isinstance(arg, QPointF) for arg in args):
            Inked.lines.append((QPointF(args[0]), QPointF(args[1]), self.pen().color(), self.pen().widthF()))
        super().drawLine(*args)

    @classmethod
    def clear(cls) -> None:
        Said.words, Said.inks, Said.fonts = [], [], []
        cls.fills, cls.lines, cls.paths = [], [], []


def words_on(canvas: HoursCanvas, block_id: str, day: int) -> list[str]:
    box = canvas.block_rect(block_id, day)
    inside = QRectF(QRect(canvas.mapFromGlobal(box.topLeft()), box.size()))
    return [text for text, where in Said.words if inside.contains(where.center())]


def a_hand() -> Hand:
    host = QWidget()
    HOSTS.append(host)
    return Hand(lambda block_id, from_day, span: Verdict(True, ""), host)


def three_days(
    now_min: int | None = None,
    blocks: tuple[dict, ...] = (ESSAY,),
    hour_px: int = HOUR_PX,
    palette: dict | None = None,
    days: int = 3,
    column: int = 140,
) -> HoursCanvas:
    """Three days from 08:00 to 20:00, at Today's app's default 48 pixels an hour unless told, in
    Inter at the normal text size, with today on the first when there is a now."""
    load_fonts()

    def columns(area: QRectF) -> list[LinearTrack]:
        return [
            LinearTrack(day, QRectF(60 + 150 * day, 10, column, 12 * hour_px), first=8 * 60, last=20 * 60)
            for day in range(days)
        ]

    host = QWidget()
    HOSTS.append(host)
    canvas = HoursCanvas(
        Hand(lambda block_id, from_day, span: Verdict(True, ""), host),
        BlockPainter(palette or resolved_palette("system", False, None)),
        columns,
        gutter=56,
    )
    canvas.setFont(QFont("Inter", 12))
    canvas.resize(520, 12 * hour_px + 20)
    occurrences = build_week("2026-09-21", list(blocks), {}, None).occurrences
    canvas.set_week(occurrences, 0 if now_min is not None else None, now_min)
    canvas.relayout()
    return canvas


def custom_hours(custom: dict) -> tuple[HoursCanvas, dict]:
    """Three days at 15:40 in a custom look on Light, with its painter."""
    look = {"preset": "default", "knobs": {}, "custom": {"base": "light", **custom}}
    palette = resolved_palette("system", False, look)
    canvas = three_days(now_min=15 * 60 + 40, palette=palette)
    canvas.set_painter(BlockPainter(palette, look))
    return canvas, palette


def lane_week(qapp: QApplication) -> HoursCanvas:
    """Seven lanes whose time runs across at 64 pixels an hour, with the hour labels in a strip
    above them, as Mission control lays its week out."""

    def lanes(area: QRectF) -> list[LinearTrack]:
        tall = area.height() / 7
        return [
            LinearTrack(
                day,
                QRectF(area.left() + 24, area.top() + day * tall + 6, area.width() - 48, tall - 12),
                Axis.ACROSS,
            )
            for day in range(7)
        ]

    host = QWidget()
    HOSTS.append(host)
    canvas = HoursCanvas(
        Hand(lambda block_id, from_day, span: Verdict(True, ""), host),
        BlockPainter(resolved_palette("light-frost", False, None, "default")),
        lanes,
    )
    scroll = HoursScroll(
        canvas,
        Scale("lanes.week", (48, 64, 80, 96), 64),
        lambda px: 24 * px + 48,
        name="lanes",
        gutter=170,
        axis=Axis.ACROSS,
    )
    QVBoxLayout(host).addWidget(scroll)
    host.resize(1150, 700)
    canvas.set_week(build_week(WEEK, BLOCKS, HOMEWORK, TRACE).occurrences, 3, minute_of("17:00"))
    host.show()
    qapp.processEvents()
    return canvas


__all__ = [
    "BLOCKS",
    "CLUB",
    "DINNER",
    "ESSAY",
    "HOMEWORK",
    "HOSTS",
    "HOUR_PX",
    "MATHS",
    "TRACE",
    "WEEK",
    "Inked",
    "Said",
    "a_hand",
    "custom_hours",
    "lane_week",
    "qapp",
    "three_days",
    "words_on",
]
