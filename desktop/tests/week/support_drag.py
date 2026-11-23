"""Setup shared by the Week tests about dragging on the hours, the notice that says what a change did,
the block and free-time menus and Ctrl+K. Other test files import `qapp`, `settled`, `wait_until`,
`window`, `session_of`, `minute`, `click`, `drag`, `tray_chip`, `menus` and `right_click` from here."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QWidget,
)

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

LEFT = Qt.MouseButton.LeftButton
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


def settled(qapp: QApplication, window: NativeWindow) -> None:
    """The save and the refreshes it starts have all landed."""
    session = window.session
    wait_until(
        qapp,
        lambda: (
            not session.busy
            and not session.dirty
            and not session.client._waiting
            and not getattr(session.client, "pending", 0)
        ),
    )
    for _ in range(5):
        qapp.processEvents()


def session_of(window: NativeWindow, assignment_id: str) -> dict:
    return next(block for block in window.session.blocks if block.get("assignment_id") == assignment_id)


def minute(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


@pytest.fixture()
def window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> Iterator[NativeWindow]:  # noqa: F811
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
    settled(qapp, made)
    essay = session_of(made, "essay")
    session.add_block({**essay, "start": "19:00", "days": [3], "pinned": True})
    session.save()
    settled(qapp, made)
    made.findChild(QAbstractButton, "viewWeek").click()
    settled(qapp, made)
    yield made


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






def click(qapp: QApplication, widget: QWidget, at: QPoint) -> None:
    send(widget, QEvent.Type.MouseButtonPress, at, True)
    send(widget, QEvent.Type.MouseButtonRelease, at, False)
    qapp.processEvents()














def right_click(widget: QWidget, at: QPoint) -> None:
    """A context-menu request at the global point `at`, as the system sends it."""
    local = widget.mapFromGlobal(at)
    QApplication.sendEvent(widget, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local, at))




# The classic Week on a Wednesday afternoon, for the tests that press the system's own mouse.
