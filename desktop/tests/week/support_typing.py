"""What the tests of typing a time share: input sent the way the window system sends it, one place
for each time box, the Week windows the time tests open on, and the clock they hold.

Other test files import `_setup`, `_up`, `enter`, `press`, `type_text`, `state`, `THURSDAY` and
`hold_clock` from here."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QLineEdit, QPushButton, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import monday_of, sunday_due
from desktop.native.fields import ClockField
from desktop.native.hours.zoom import HoursScroll
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.setup import WEEK, SetupPage, SetupState
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.waiting import wait_until

DESIGNS = ("classic", "timeline", "mission", "bento", "retro", "clay")
# Thursday 15:40 of the week beginning 2026-10-12.
HELD = datetime.fromisoformat("2026-10-15T15:40")

MONDAY, THURSDAY, FRIDAY, SUNDAY = 0, 3, 4, 6

CLOCKS = pytest.mark.parametrize("twenty_four", [True, False])
CTRL = Qt.KeyboardModifier.ControlModifier
NONE = Qt.KeyboardModifier.NoModifier


# Input through the window system's path ---------------------------------------------------------
# All keys and clicks go to the box's QWindow, as the window system sends them, so a key never
# reaches a box before the window's own focus and activation events.


def press(field: ClockField, key, mods=NONE) -> None:
    QTest.keyClick(field.window().windowHandle(), key, mods)
    QApplication.processEvents()


def type_text(field: ClockField, text: str) -> None:
    for char in text:
        press(field, char)


def type_over(field: ClockField, text: str) -> None:
    """What a student does: select the whole time and write another."""
    QTest.keyClick(field, Qt.Key.Key_A, CTRL)
    QTest.keyClicks(field, text)


def click_at(field: ClockField, fraction: float) -> None:
    line = field.lineEdit()
    keep = line.cursorPosition()
    line.setCursorPosition(round(len(line.text()) * fraction))
    at = line.cursorRect().center()
    line.setCursorPosition(keep)
    window = field.window()
    QTest.mouseClick(window.windowHandle(), Qt.MouseButton.LeftButton, NONE, line.mapTo(window, at))
    QApplication.processEvents()


def enter(field: ClockField, how: str) -> None:
    """Get the keyboard into the box the way a student does."""
    if how == "tab-in":
        # A real Tab from the widget before the box in the focus chain. The chain is a ring: a dialog
        # that was never shown has no visible widget in it, so stop after one lap.
        before = field.previousInFocusChain()
        for _lap in range(len(QApplication.allWidgets()) + 2):
            if (
                before.isVisible()
                and before.isEnabled()
                and before.focusPolicy() & Qt.FocusPolicy.TabFocus
                and before is not field.lineEdit()
            ):
                break
            before = before.previousInFocusChain()
        else:
            raise AssertionError("no visible, tab-focusable widget before the box: is its dialog shown?")
        before.setFocus(Qt.FocusReason.OtherFocusReason)
        QApplication.processEvents()
        press(field, Qt.Key.Key_Tab)
    elif how == "ctrl-a":
        click_at(field, 0.5)
        press(field, Qt.Key.Key_A, CTRL)
    else:
        click_at(field, {"click-start": 0.0, "click-middle": 0.5, "click-end": 1.0}[how])
    assert field.hasFocus() or field.lineEdit().hasFocus(), f"{how} did not give the box the keyboard"


def up(qapp: QApplication, widget: QWidget) -> QWidget:
    widget.show()
    wait_until(qapp, widget.isExposed, what="the widget being on screen")
    widget.activateWindow()
    qapp.processEvents()
    return widget


_up = up


def drain(qapp: QApplication) -> None:
    """Let work a widget put off to the next turn of the event loop (a dialog's refit) run before
    the widget is freed: freeing in the same turn ran it on a deleted dialog."""
    for _ in range(3):
        qapp.processEvents()


def shown(field: ClockField, qapp: QApplication, host: QWidget) -> ClockField:
    """The box on screen with the keyboard, as it is when a student starts typing."""
    layout = host.layout()
    if layout is None:
        from PySide6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(host)
    layout.addWidget(field)
    host.show()
    wait_until(qapp, host.isExposed, what="the host being on screen")
    host.activateWindow()
    field.setFocus()
    qapp.processEvents()
    return field


def line_of(field: ClockField) -> QLineEdit:
    line = field.lineEdit()
    assert line is not None
    return line


def go_when(dialog) -> None:
    """Add event's and Add homework's second question. Both open on a first page that asks for a title."""
    if dialog._add_step is None or dialog._add_step >= 1:
        return
    if not dialog.title.text().strip():
        dialog.title.setText("Club")
    dialog._save.click()
    QApplication.processEvents()


# The setup wizard --------------------------------------------------------------------------------


def state(**changes: object) -> SetupState:
    base = SetupState(
        pack="system",
        look={"preset": "default", "knobs": {}},
        layout=sanitize_layout(None),
        preferences={},
        blocks=[],
        week_start=monday_of("2026-09-23"),
    )
    for key, value in changes.items():
        setattr(base, key, value)
    return base


def opened_setup(qapp: QApplication, **changes: object) -> SetupPage:
    setup = SetupPage()
    setup.motion = "off"
    setup.resize(1100, 720)
    setup.open(state(**changes))
    setup.show()
    qapp.processEvents()
    return setup


@dataclass
class Box:
    top: QWidget
    field: ClockField
    read: Callable[[], str]  # the time the place would save, "HH:MM"
    forward: QPushButton  # Next / Save / Add: what the student presses to go on
    owned: list


def end_of(start: str, minutes: int) -> str:
    h, m = map(int, start.split(":"))
    total = h * 60 + m + minutes
    return f"{total // 60:02d}:{total % 60:02d}"


def _setup(qapp, which: str) -> Box:
    setup = SetupPage()
    setup.motion = "off"
    setup.resize(1100, 720)
    setup.open(state())
    setup._show(WEEK)
    _up(qapp, setup)
    if which.startswith("school"):
        times = setup.school_times
        title = "School"
    else:
        row = setup.activities[0]
        row.name.setText("Soccer")
        row.days.set_days([1])
        times = row.times
        title = "Soccer"
    if which.endswith("start"):
        times.end.setTime(QTime(18, 0))
    else:
        times.start.setTime(QTime(8, 0))

    def read() -> str:
        block = next(b for b in setup.week_blocks() if b["title"] == title)
        return block["start"] if which.endswith("start") else end_of(block["start"], block["duration_min"])

    field = times.start if which.endswith("start") else times.end
    return Box(setup, field, read, setup.next, [setup])


# The Week windows the time tests open on ----------------------------------------------------------


@pytest.fixture()
def hours_window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> Iterator[NativeWindow]:
    """Signed in with the clock held at Thursday 15:40 on 2026-10-15 from before the week is first
    shown: school on weekdays from 08:00, dinner every day at 18:00, and nothing next week."""
    CLOCK.set(HELD)
    made = open_light((1280, 860))
    session = made.session
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
            "id": "dinner",
            "title": "Dinner",
            "kind": "locked",
            "category": "meals",
            "start": "18:00",
            "duration_min": 30,
            "days": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    yield made


def hours(window: NativeWindow) -> HoursScroll:
    on_screen = [
        scroll for scroll in window.planner.currentWidget().findChildren(HoursScroll) if scroll.isVisible()
    ]
    assert len(on_screen) == 1, f"{len(on_screen)} hours on screen"
    return on_screen[0]


def settled(qapp: QApplication, window: NativeWindow) -> None:
    """The save and the refreshes it starts have all landed."""
    session = window.session
    wait_until(
        qapp, lambda: not session.busy and not session.dirty and not any(session.client._replies.values())
    )
    for _ in range(5):
        qapp.processEvents()


def session_of(window: NativeWindow, assignment_id: str) -> dict:
    return next(block for block in window.session.blocks if block.get("assignment_id") == assignment_id)


@pytest.fixture()
def week_window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> Iterator[NativeWindow]:
    """School on weekdays 08:00-14:30, Piano on Thursday 17:00-17:30, the History essay on Thursday
    19:00-20:00 and a Math worksheet with no time yet. The clock is held at Thursday 10:00."""
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


def hold_clock(window: NativeWindow, day: int, clock: str) -> None:
    """The window's clock at "HH:MM" or "HH:MM:SS" on a day of the open week."""
    hour, minute, *seconds = (int(part) for part in clock.split(":"))
    moment = datetime.fromisoformat(window.session.week_start) + timedelta(
        days=day, hours=hour, minutes=minute, seconds=seconds[0] if seconds else 0
    )
    CLOCK.set(moment)
