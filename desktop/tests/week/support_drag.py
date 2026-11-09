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
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QWidget,
)

from backend.slots import minutes_to_hhmm
from backend.tests.fake_clock import CLOCK
from desktop.native import window as window_module
from desktop.native.calendar import sunday_due
from desktop.native.controller import NativeSession
from desktop.native.hours.canvas import HoursCanvas
from desktop.native.menus import Menu
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
            and not any(session.client._replies.values())
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


def drag(qapp: QApplication, source: QWidget, hours: HoursCanvas, start: QPoint, end: QPoint) -> None:
    """Press on `source`, move over `hours` and let go, as a mouse does."""
    send(source, QEvent.Type.MouseButtonPress, start, True)
    for step in range(1, 9):
        send(hours, QEvent.Type.MouseMove, start + (end - start) * step / 8, True)
    send(hours, QEvent.Type.MouseButtonRelease, end, False)
    qapp.processEvents()


def press_drag(hours: HoursCanvas, day: int, start: int, end: int) -> None:
    """Press two pixels into the first minute of free time, move across and let go, through QTest."""
    start_point = hours.point_for(day, start) + QPoint(0, 2)
    end_point = hours.point_for(day, end)
    QTest.mousePress(hours, LEFT, pos=start_point)
    for step in range(1, 9):
        QTest.mouseMove(hours, start_point + (end_point - start_point) * step / 8)
    QTest.mouseRelease(hours, LEFT, pos=end_point)


def click(qapp: QApplication, widget: QWidget, at: QPoint) -> None:
    send(widget, QEvent.Type.MouseButtonPress, at, True)
    send(widget, QEvent.Type.MouseButtonRelease, at, False)
    qapp.processEvents()


def open_thursday(qapp: QApplication, window: NativeWindow) -> HoursCanvas:
    """A click on Thursday's name in the Week opens it on Day."""
    QTest.mouseClick(window.findChild(QLabel, "weekDayName3"), LEFT)
    settled(qapp, window)
    assert window.session.planner_view == "day"
    return window.day_view.hours


def answer_editors(monkeypatch: pytest.MonkeyPatch, *titles: str | None) -> list[tuple[str, str]]:
    """Each block editor that opens is shown, and what its title and category say is kept. Then the
    title is typed and Save pressed, or with None, Cancel pressed."""
    from desktop.native.widgets import BlockDialog

    seen: list[tuple[str, str]] = []
    queue = list(titles)

    def run(dialog: BlockDialog) -> int:
        dialog.show()
        seen.append((dialog.title.text(), dialog.category.currentText()))
        buttons = dialog.findChild(QDialogButtonBox, "dialogButtons")
        title = queue.pop(0)
        if title is None:
            QTest.mouseClick(buttons.button(QDialogButtonBox.StandardButton.Cancel), LEFT)
        else:
            dialog.title.selectAll()
            QTest.keyClicks(dialog.title, title)
            save = buttons.button(QDialogButtonBox.StandardButton.Save)
            # Add is What / When / Category; Save on What is Next. Edit stays one page.
            while getattr(dialog, "_add_step", None) is not None and dialog._add_step < 2:
                QTest.mouseClick(save, LEFT)
                QApplication.processEvents()
            QTest.mouseClick(save, LEFT)
        return dialog.result()

    monkeypatch.setattr(BlockDialog, "exec", run)
    return seen


def create_on(
    qapp: QApplication, window: NativeWindow, hours: HoursCanvas, day: int, span: str, title: str
) -> None:
    """Drag across free time from the first to the second of "HH:MM-HH:MM", and wait until the
    block the editor names `title` is saved."""
    start, end = minute(span[:5]), minute(span[6:])
    hours.reveal(day, start - 60, end + 60)
    qapp.processEvents()
    # Two pixels into the first minute, so the press is on free time rather than a block's edge.
    drag(qapp, hours, hours, hours.point_for(day, start) + QPoint(0, 2), hours.point_for(day, end))
    wait_until(qapp, lambda: any(block["title"] == title for block in window.session.blocks))
    settled(qapp, window)


def notice(window: NativeWindow) -> tuple[bool, str, str]:
    """The toast with a button to press: whether it shows, its words and its button."""
    toast = window.toast
    if not toast.isVisible() or not toast.button.isVisible():
        return False, "", ""
    return True, toast.text(), toast.button.accessibleName()


def toast(window: NativeWindow) -> str:
    return window.toast.text() if window.toast.isVisible() else ""


def tray_chip(window: NativeWindow, block_id: str) -> QPushButton:
    return next(
        chip
        for chip in window.findChildren(QPushButton)
        if chip.property("block_id") == block_id and chip.property("tray") and chip.isVisible()
    )


def right_click(widget: QWidget, at: QPoint) -> None:
    """A context-menu request at the global point `at`, as the system sends it."""
    local = widget.mapFromGlobal(at)
    QApplication.sendEvent(widget, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local, at))


@pytest.fixture()
def menus(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Every menu shown, as its items' words, and the item to choose from the next one, by name."""
    seen: dict = {"shown": [], "choose": None, "at": [], "rows": []}

    class Shown(Menu):
        def exec(self, at: QPoint | None = None, *_rest: object) -> object:
            seen["shown"].append([action.text() or "---" for action in self.actions()])
            seen["rows"].append(list(self.actions()))
            seen["at"].append(at)
            wanted = seen["choose"]
            return next((action for action in self.actions() if action.objectName() == wanted), None)

    # The window's own name for it: a method set on Qt's class is not the one Qt's object calls.
    monkeypatch.setattr(window_module, "Menu", Shown)
    return seen


# The classic Week on a Wednesday afternoon, for the tests that press the system's own mouse.


def hold_clock(window: NativeWindow, day: int, minute_of_day: int) -> None:
    CLOCK.set(datetime.fromisoformat(window.session.week_start) + timedelta(days=day, minutes=minute_of_day))
    window._fill_classic()
    QApplication.processEvents()


@pytest.fixture()
def classic_week(qapp: QApplication, light_window: NativeWindow) -> Iterator[NativeWindow]:  # noqa: F811
    """The classic Week on Wednesday 14:07 of the open week, with one early block on Monday: a week
    with nothing in it shows a button in place of the hours."""
    light_window.resize(1280, 860)
    light_window._layout = {"main": "classic", "day": "one", "options": {}}
    light_window.session.add_block({**PIANO, "id": "early", "title": "Early", "start": "06:00", "days": [0]})
    light_window.session.save()
    settled(qapp, light_window)
    light_window.findChild(QAbstractButton, "viewWeek").click()
    settled(qapp, light_window)
    handle = light_window.windowHandle()
    wait_until(qapp, lambda: handle is not None and handle.isExposed())
    light_window.activateWindow()
    wait_until(qapp, light_window.isActiveWindow)
    hold_clock(light_window, WEDNESDAY, 14 * 60 + 7)
    yield light_window


@pytest.fixture()
def listed_menus(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Every menu shown, with its name and words and where it was asked for. None is chosen."""
    seen: list[dict] = []

    class Shown(Menu):
        def exec(self, at: QPoint | None = None, *_rest: object) -> object:
            seen.append({"name": self.objectName(), "rows": [a.text() for a in self.actions()], "at": at})
            return None

    monkeypatch.setattr(window_module, "Menu", Shown)
    return seen


def in_window(window: NativeWindow, day: int, minute_of_day: int) -> QPoint:
    hours = window.week_table.hours
    hours.reveal(day, minute_of_day, minute_of_day + 15)
    QApplication.processEvents()
    return window.mapFromGlobal(hours.point_for(day, minute_of_day))


def press_right_button(window: NativeWindow, at: QPoint, jitter: QPoint | None = None) -> None:
    """A right press and release through the window's handle, as the system sends them."""
    handle = window.windowHandle()
    QTest.mousePress(handle, Qt.MouseButton.RightButton, NONE, at)
    QTest.mouseRelease(handle, Qt.MouseButton.RightButton, NONE, at + (jitter or QPoint(0, 0)))
    QApplication.processEvents()


def plant_block(
    session: NativeSession,
    block_id: str,
    day: int,
    start_min: int,
    end_min: int,
    *,
    pinned: bool | None = None,
) -> None:
    """Set a block's start, day and length where it lives and drop it from the needs-time list, with
    no hand-move rule (which refuses a start in the past) and no Undo step: setup only."""
    block = next(item for item in session.blocks if item["id"] == block_id)
    block["start"] = minutes_to_hhmm(start_min)
    block["days"] = [day]
    block["duration_min"] = end_min - start_min
    if pinned is not None:
        block["pinned"] = pinned
    session.needs_time.pop(block_id, None)
