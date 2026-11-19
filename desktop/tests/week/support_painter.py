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
from PySide6.QtGui import QFont, QFontMetricsF, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

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














__all__ = [
    "BLOCKS",
    "CLUB",
    "DINNER",
    "ESSAY",
    "HOMEWORK",
    "HOSTS",
    "MATHS",
    "TRACE",
    "WEEK",
    "Said",
    "qapp",
]
