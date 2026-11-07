"""Setup shared by the Week tests about the hand (drag, click, scroll at the edge), the surfaces it
lands blocks on, the classic hours and the grid's keyboard: small copies of what the old files took
from other test modules."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QMouseEvent, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from backend.tests.fake_clock import CLOCK
from desktop.native import window as window_module
from desktop.native.hours import hand as hand_module
from desktop.native.hours.canvas import BlockPainter, HoursCanvas
from desktop.native.hours.classic import ClassicWeek
from desktop.native.hours.geometry import Axis, DialTrack, LinearTrack
from desktop.native.hours.hand import Gesture, Hand, Held, Verdict, span_words
from desktop.native.layouts.base import LayoutView
from desktop.native.look import resolved_palette
from desktop.native.menus import Menu
from desktop.native.weekmodel import Occurrence, build_week
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free, settled


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


class Rig:
    """A window with a week of hours, a tray chip and a hand, and what the hand reported."""

    def __init__(
        self, qapp: QApplication, judge=None, lay_out=None, height: int = 680, step: int = 15
    ) -> None:
        self.window = QWidget()
        # Inside the offscreen screen (800 by 800), where QApplication.widgetAt can find it.
        self.window.resize(760, 760)
        box = QVBoxLayout(self.window)
        box.setContentsMargins(0, 0, 0, 0)
        self.chip = QPushButton("Math worksheet")
        box.addWidget(self.chip)
        self.said: list[object] = []
        self.hand = Hand(
            judge or (lambda block_id, from_day, span: Verdict(True, span_words(span))), self.window
        )
        # The rules below hold at any step. At this height five minutes is two pixels, finer than a
        # point aimed at a minute can promise, so they are checked a quarter hour at a time.
        self.hand.step = step
        self.hand.committed.connect(self.said.append)
        self.hand.refused.connect(lambda words: self.said.append(("refused", words)))
        self.hand.opened.connect(lambda block_id: self.said.append(("opened", block_id)))
        self.hand.menu_requested.connect(lambda block_id, day, _at: self.said.append(("menu", block_id, day)))
        painter = BlockPainter(resolved_palette("system", False, None))
        self.canvas = HoursCanvas(
            self.hand,
            painter,
            lay_out
            or (
                lambda area: [
                    LinearTrack(day, QRectF(area.left() + day * 100, area.top(), 100, area.height()))
                    for day in range(7)
                ]
            ),
        )
        self.canvas.setFixedHeight(height)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.canvas)
        box.addWidget(self.scroll, 1)
        self.canvas.set_week(WEEK)
        self.window.show()
        qapp.processEvents()
        self.canvas.relayout()

    def at(self, day: int, minute: int, nudge: int = 0) -> QPoint:
        return self.canvas.point_for(day, minute) + QPoint(0, nudge)

    def send(self, widget: QWidget, kind: QEvent.Type, at: QPoint, held: bool) -> None:
        send_mouse(widget, kind, at, held)

    def drag(
        self, start: QPoint, end: QPoint, *, release: bool = True, source: QWidget | None = None
    ) -> None:
        source = source or self.canvas
        self.send(source, QEvent.Type.MouseButtonPress, start, True)
        for step in range(1, 9):
            self.send(source, QEvent.Type.MouseMove, start + (end - start) * step / 8, True)
        if release:
            self.send(source, QEvent.Type.MouseButtonRelease, end, False)

    def right(self, kind: QEvent.Type, at: QPoint, held: bool) -> None:
        local = QPointF(self.canvas.mapFromGlobal(at))
        buttons = Qt.MouseButton.RightButton if held else Qt.MouseButton.NoButton
        event = QMouseEvent(
            kind, local, QPointF(at), Qt.MouseButton.RightButton, buttons, Qt.KeyboardModifier.NoModifier
        )
        QApplication.sendEvent(self.canvas, event)


@pytest.fixture()
def rig_of(qapp: QApplication) -> Iterator[Callable[..., Rig]]:
    """Makes rigs; every window they made is freed when the test ends."""
    made: list[Rig] = []

    def make(**options: object) -> Rig:
        rig = Rig(qapp, **options)
        made.append(rig)
        return rig

    yield make
    for rig in made:
        free(rig.window)


@pytest.fixture()
def hand_time(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """The seconds the hand reads for its dwell and its double-click interval; the test moves them
    by changing the list's one number."""
    now = [1000.0]
    clock = type("Clock", (), {"monotonic": staticmethod(lambda: now[0])})
    monkeypatch.setattr(hand_module, "time", clock)
    return now


class Dial(QWidget):
    """The least a surface needs: it takes blocks and says which track lies under a point."""

    takes_blocks = True

    def __init__(self, day: int, parent: QWidget) -> None:
        super().__init__(parent)
        self.track = DialTrack(day, QPointF(90, 90), 50, 85, first=6 * 60, last=22 * 60)

    def track_at(self, point: QPointF) -> DialTrack | None:
        return self.track if self.track.contains(point) else None

    def track_for(self, day: int, minute: int | None = None) -> DialTrack | None:
        return self.track if day == self.track.day else None


class Everything(LayoutView):
    """Monday and Tuesday down, Wednesday and Thursday across, Friday on a tilted card, Saturday in
    a morning tile and an afternoon tile, Sunday on a dial."""

    layout_id = "targets"

    def __init__(self, hand: Hand) -> None:
        super().__init__(hand=hand)
        painter = BlockPainter(resolved_palette("system", False, None))

        def columns(area: QRectF) -> list[LinearTrack]:
            half = area.width() / 2
            return [
                LinearTrack(day, QRectF(area.left() + day * half, area.top(), half, area.height()))
                for day in (0, 1)
            ]

        def lanes(area: QRectF) -> list[LinearTrack]:
            half = area.height() / 2
            return [
                LinearTrack(
                    day, QRectF(area.left(), area.top() + (day - 2) * half, area.width(), half), Axis.ACROSS
                )
                for day in (2, 3)
            ]

        def card(area: QRectF) -> list[LinearTrack]:
            return [LinearTrack(4, area.adjusted(30, 20, -30, -20), turn=8)]

        def tile(first: int, last: int):
            return lambda area: [LinearTrack(5, area, first=first, last=last)]

        self.down = HoursCanvas(hand, painter, columns, gutter=40, header=24, parent=self)
        self.down.setGeometry(QRect(0, 0, 300, 500))
        self.across = HoursCanvas(hand, painter, lanes, gutter=60, header=20, parent=self)
        self.across.setGeometry(QRect(310, 0, 440, 160))
        self.card = HoursCanvas(hand, painter, card, parent=self)
        self.card.setGeometry(QRect(310, 170, 200, 330))
        self.morning = HoursCanvas(hand, painter, tile(6 * 60, 12 * 60), parent=self)
        self.morning.setGeometry(QRect(520, 170, 110, 160))
        self.afternoon = HoursCanvas(hand, painter, tile(12 * 60, 18 * 60), parent=self)
        self.afternoon.setGeometry(QRect(520, 340, 110, 160))
        self.dial = Dial(6, self)
        self.dial.setGeometry(QRect(0, 520, 180, 180))
        self.morning.set_week([occurrence("run", 5, 8 * 60, 9 * 60)])


class Stage:
    def __init__(self, qapp: QApplication) -> None:
        self.window = QWidget()
        # Inside the offscreen screen (800 by 800), where QApplication.widgetAt can find it.
        self.window.setGeometry(QRect(0, 0, 760, 720))
        self.said: list[object] = []
        self.hand = Hand(lambda block_id, from_day, span: Verdict(True, span_words(span)), self.window)
        # A pixel of the morning tile is over two minutes, too coarse to aim within a 5-minute step.
        # What these prove, bounds and targets, holds at any step.
        self.hand.step = 15
        self.hand.committed.connect(self.said.append)
        self.view = Everything(self.hand)
        self.view.setParent(self.window)
        self.view.setGeometry(self.window.rect())
        self.window.show()
        qapp.processEvents()
        for canvas in (
            self.view.down,
            self.view.across,
            self.view.card,
            self.view.morning,
            self.view.afternoon,
        ):
            canvas.relayout()

    def send(self, widget: QWidget, kind: QEvent.Type, at: QPoint, held: bool) -> None:
        send_mouse(widget, kind, at, held)

    def carry(self, start: QPoint, end: QPoint, source: QWidget) -> None:
        for step in range(1, 9):
            self.send(source, QEvent.Type.MouseMove, start + (end - start) * step / 8, True)
        self.send(source, QEvent.Type.MouseButtonRelease, end, False)

    def place(self, day: int, minute: int, surface: QWidget) -> None:
        """Homework with no time, carried from nowhere in particular and let go at a day and minute."""
        start = QPoint(750, 700)
        self.hand.press(self.window, Held(Gesture.PLACE, "Essay", 60, "essay"), start)
        self.carry(
            start,
            surface.mapToGlobal(surface.track_for(day, minute).point_for(minute).toPoint()),
            self.window,
        )


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


def a_hand() -> Hand:
    host = QWidget()
    HOSTS.append(host)
    return Hand(lambda block_id, from_day, span: Verdict(True, ""), host)


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


def week_view(qapp: QApplication, blocks: tuple[dict, ...] = ()) -> ClassicWeek:
    view = ClassicWeek(a_hand())
    view.set_look(None, resolved_palette("system", False, None))
    view.set_week(build_week("2026-09-21", list(blocks), {}, None), 3, 15 * 60 + 40)
    view.resize(980, 500)
    view.show()
    qapp.processEvents()
    view.hours.relayout()
    qapp.processEvents()
    return view


def day_widths(view: ClassicWeek) -> list[float]:
    return [view.hours.track_for(day).area.width() for day in range(7)]


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


def hold_clock(window: NativeWindow, day: int, minute: int) -> None:
    CLOCK.set(datetime.fromisoformat(window.session.week_start) + timedelta(days=day, minutes=minute))
    window._fill_classic()
    QApplication.processEvents()


@pytest.fixture()
def classic_window(qapp: QApplication, window: NativeWindow) -> NativeWindow:
    """The classic Week on Wednesday 14:07 of the open week, with one early block on Monday: a week
    with nothing in it shows a button in place of the hours. `window` is the light window."""
    window.resize(1280, 860)
    window._layout = {"main": "classic", "day": "one", "options": {}}
    window.session.add_block({**PIANO, "id": "early", "title": "Early", "start": "06:00", "days": [0]})
    window.session.save()
    settled(qapp, window)
    window.findChild(QAbstractButton, "viewWeek").click()
    settled(qapp, window)
    window.show()
    wait_until(qapp, window.isExposed)
    window.activateWindow()
    wait_until(qapp, window.isActiveWindow)
    hold_clock(window, WEDNESDAY, 14 * 60 + 7)
    return window


@pytest.fixture()
def menus(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Every menu shown, with its name and words and where it was asked for. None is chosen."""
    seen: list[dict] = []

    class Shown(Menu):
        def exec(self, at: QPoint | None = None, *_rest: object) -> object:
            seen.append({"name": self.objectName(), "rows": [a.text() for a in self.actions()], "at": at})
            return None

    monkeypatch.setattr(window_module, "Menu", Shown)
    return seen


def grid(window: NativeWindow) -> HoursCanvas:
    return window.week_table.hours


def key(window: NativeWindow, which: Qt.Key, mods: Qt.KeyboardModifier = NONE) -> None:
    """A key from the system, to whatever the window has focused."""
    QTest.keyClick(window.windowHandle(), which, mods)
    QApplication.processEvents()


def tab_to_grid(window: NativeWindow) -> None:
    """Tab from the top of the page until the week is reached."""
    window.prev_nav.setFocus(Qt.FocusReason.TabFocusReason)
    for _ in range(40):
        key(window, Qt.Key.Key_Tab)
        focus = window.focusWidget()
        if focus is not None and (focus is window.week_table or window.week_table.isAncestorOf(focus)):
            if window.week_table.scroll.header.isAncestorOf(focus):
                continue  # the zoom buttons come first, in the corner
            assert focus is grid(window), f"Tab reached {type(focus).__name__} before the grid"
            return
    raise AssertionError("Tab never reached the week")


def add_piano(qapp: QApplication, window: NativeWindow) -> None:
    window.session.add_block(dict(PIANO))
    window.session.save()
    settled(qapp, window)
    hold_clock(window, WEDNESDAY, 14 * 60 + 7)
