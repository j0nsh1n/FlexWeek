"""Setup shared by the Week tests about the hand (drag, click, scroll at the edge), the surfaces it
lands blocks on, the classic hours and the grid's keyboard: small copies of what the old files took
from other test modules."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QMouseEvent, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
)

from desktop.native.weekmodel import Occurrence
from desktop.native.window import NativeWindow
from desktop.tests.window_support import free


def occurrence(block_id: str, day: int, start: int, end: int, work: bool = False) -> Occurrence:
    return Occurrence(
        block_id,
        block_id.title(),
        "homework" if work else "class",
        day,
        start,
        end,
        work,
        False,
        False,
        None,
        None,
        None,
    )


WEEK = [
    *(occurrence("school", day, 8 * 60, 14 * 60 + 30) for day in range(5)),
    occurrence("essay", 2, 18 * 60, 19 * 60, work=True),
]


def send_mouse(widget: QWidget, kind: QEvent.Type, at: QPoint, held: bool) -> None:
    """A left-button mouse event at a global point, sent to `widget`."""
    local = QPointF(widget.mapFromGlobal(at))
    buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
    event = QMouseEvent(
        kind, local, QPointF(at), Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(widget, event)














class Stage:

    def send(self, widget: QWidget, kind: QEvent.Type, at: QPoint, held: bool) -> None:
        send_mouse(widget, kind, at, held)

    def carry(self, start: QPoint, end: QPoint, source: QWidget) -> None:
        for step in range(1, 9):
            self.send(source, QEvent.Type.MouseMove, start + (end - start) * step / 8, True)
        self.send(source, QEvent.Type.MouseButtonRelease, end, False)



@pytest.fixture()
def stage_of(qapp: QApplication) -> Iterator[Callable[[], Stage]]:
    made: list[Stage] = []

    def make() -> Stage:
        stage = Stage(qapp)
        made.append(stage)
        return stage

    yield make
    for stage in made:
        free(stage.window)


class Said(QPainter):
    """A painter that keeps every word it writes and where, in the widget's coordinates. Put in place
    of the canvas module's QPainter, it is the one a real paint event draws with."""

    words: list[tuple[str, QRectF]] = []

    def drawText(self, *args: object) -> None:  # noqa: N802
        text = next(arg for arg in reversed(args) if isinstance(arg, str))
        where = next(arg for arg in args if isinstance(arg, (QRectF, QRect, QPointF)))
        box = QRectF(where, where) if isinstance(where, QPointF) else QRectF(where)
        Said.words.append((text, self.worldTransform().mapRect(box)))
        super().drawText(*args)


# The hosts of the hands these tests make. A hand is its host's Qt child and holds no reference of
# its own to it, so the host has to be kept for as long as the hand is used.
HOSTS: list[QWidget] = []




SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "days": [0, 1, 2, 3, 4],
    "start": "08:00",
    "duration_min": 405,
}
GYM = {
    "id": "gym",
    "title": "Gym",
    "kind": "locked",
    "category": "exercise",
    "days": [5],
    "start": "10:00",
    "duration_min": 90,
}






# The classic Week in a signed-in light window, and its keyboard.

NONE = Qt.KeyboardModifier.NoModifier
WEDNESDAY = 2
PIANO = {
    "id": "piano",
    "kind": "locked",
    "title": "Piano",
    "category": "extra",
    "start": "15:00",
    "duration_min": 60,
    "days": [WEDNESDAY],
}










def key(window: NativeWindow, which: Qt.Key, mods: Qt.KeyboardModifier = NONE) -> None:
    """A key from the system, to whatever the window has focused."""
    QTest.keyClick(window.windowHandle(), which, mods)
    QApplication.processEvents()
