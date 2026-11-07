"""Shared pieces of the clock, time-box, hour-label, block-range and week-list tests: the busy week they
start from, the pointer helpers, and a recorder of the clock words the hours write."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native import window as window_module
from desktop.native.calendar import sunday_due
from desktop.native.hours import canvas as canvas_module
from desktop.native.hours.canvas import HoursCanvas
from desktop.native.hours.zoom import HoursScroll
from desktop.native.menus import Menu
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until

DESIGNS = ("classic", "timeline", "mission", "bento", "retro", "clay")
CLOCK_WORDS = re.compile(r"\d{1,2}:\d{2}(?: [AP]M)?")


def saved(qapp: QApplication, window: NativeWindow) -> None:
    """The save and the refreshes it starts have all landed."""
    session = window.session
    wait_until(
        qapp, lambda: not session.busy and not session.dirty and not any(session.client._replies.values())
    )
    for _ in range(5):
        qapp.processEvents()


def session_of(window: NativeWindow, assignment_id: str) -> dict:
    return next(block for block in window.session.blocks if block.get("assignment_id") == assignment_id)


def minute(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def send(widget: QWidget, kind: QEvent.Type, at: QPoint, held: bool) -> None:
    buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
    event = QMouseEvent(
        kind,
        QPointF(widget.mapFromGlobal(at)),
        QPointF(at),
        Qt.MouseButton.LeftButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)


def drag(qapp: QApplication, source: QWidget, hours: HoursCanvas, start: QPoint, end: QPoint) -> None:
    """Press on `source`, move over `hours` and let go, as a mouse does."""
    send(source, QEvent.Type.MouseButtonPress, start, True)
    for step in range(1, 9):
        send(hours, QEvent.Type.MouseMove, start + (end - start) * step / 8, True)
    send(hours, QEvent.Type.MouseButtonRelease, end, False)
    qapp.processEvents()


def click(qapp: QApplication, widget: QWidget, at: QPoint) -> None:
    send(widget, QEvent.Type.MouseButtonPress, at, True)
    send(widget, QEvent.Type.MouseButtonRelease, at, False)
    qapp.processEvents()


def right_click(widget: QWidget, at: QPoint) -> None:
    local = widget.mapFromGlobal(at)
    QApplication.sendEvent(widget, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local, at))


def tray_chip(window: NativeWindow, block_id: str) -> QPushButton:
    return next(
        chip
        for chip in window.findChildren(QPushButton)
        if chip.property("block_id") == block_id and chip.property("tray") and chip.isVisible()
    )


@pytest.fixture()
def menus(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Every menu shown, as its items' words."""
    seen: dict = {"shown": []}

    class Shown(Menu):
        def exec(self, at: QPoint | None = None, *_rest: object) -> object:
            seen["shown"].append([action.text() or "---" for action in self.actions()])
            return None

    # The window's own name for it: a method set on Qt's class is not the one Qt's object calls.
    monkeypatch.setattr(window_module, "Menu", Shown)
    return seen


@pytest.fixture()
def busy_week(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> Iterator[NativeWindow]:
    """Today's app's Week: School on weekdays 08:00-14:30, Piano on Thursday 17:00-17:30, the History
    essay on Thursday 19:00-20:00 and a Math worksheet with no time yet. The clock is held at Thursday
    10:00."""
    made = open_light((1280, 860))
    session = made.session
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=10)
    CLOCK.set(thursday)
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.add_block(
        {
            "id": "piano",
            "title": "Piano",
            "kind": "locked",
            "category": "extra",
            "start": "17:00",
            "duration_min": 30,
            "days": [3],
        }
    )
    due = sunday_due(session.week_start)
    for key, title in (("essay", "History essay"), ("math", "Math worksheet")):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    saved(qapp, made)
    essay = session_of(made, "essay")
    session.add_block({**essay, "start": "19:00", "days": [3], "pinned": True})
    session.save()
    saved(qapp, made)
    made.findChild(QAbstractButton, "viewWeek").click()
    saved(qapp, made)
    yield made


def hours_scroll(window: NativeWindow) -> HoursScroll:
    shown = [
        scroll for scroll in window.planner.currentWidget().findChildren(HoursScroll) if scroll.isVisible()
    ]
    assert len(shown) == 1, f"{len(shown)} hours on screen"
    return shown[0]


@pytest.fixture()
def written_clock_words(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every clock time the hours' painter writes, as its words, in the order it writes them."""
    from PySide6.QtGui import QPainter

    words: list[str] = []

    class Wrote(QPainter):
        def drawText(self, *args: object) -> None:  # noqa: N802
            text = next((arg for arg in reversed(args) if isinstance(arg, str)), "")
            if CLOCK_WORDS.fullmatch(text):
                words.append(text)
            super().drawText(*args)

    monkeypatch.setattr(canvas_module, "QPainter", Wrote)
    return words
