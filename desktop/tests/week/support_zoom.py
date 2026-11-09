"""What the hours' zoom, scroll and opening-place tests share: standalone weeks, days and lanes, the
wheel, the light window with school and dinner, and the Material week helpers.

The names `DESIGNS`, `hours`, `qapp`, `wait_until`, `window`, `a_lane_week` and `settle` are imported
by tests of other groups (they came from the old test_hours_open and test_hours_zoom)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import (  # noqa: E402
    QAbstractAnimation,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QStandardPaths,
    Qt,
)
from PySide6.QtGui import QMouseEvent, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.tests.fake_clock import CLOCK  # noqa: E402
from desktop.native import motion  # noqa: E402
from desktop.native.hours.canvas import BlockPainter, HoursCanvas  # noqa: E402
from desktop.native.hours.classic import ClassicDay, ClassicWeek  # noqa: E402
from desktop.native.hours.geometry import Axis, LinearTrack  # noqa: E402
from desktop.native.hours.hand import Hand, Verdict, span_words  # noqa: E402
from desktop.native.hours.zoom import HoursScroll, Scale  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import LightWindows  # noqa: E402
from desktop.tests.material_support import faded_in  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402, F401

DESIGNS = ("classic", "timeline", "mission", "bento", "retro", "clay")
MONDAY = "2026-09-21"
SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "days": [0],
    "start": "08:00",
    "duration_min": 390,
}
QUARTER = {"id": "quiz", "title": "Quiz", "kind": "locked", "days": [3], "start": "16:00", "duration_min": 15}
ESSAY = {"id": "essay", "title": "Essay", "kind": "locked", "days": [3], "start": "19:00", "duration_min": 90}
NOW = 15 * 60 + 40
# Thursday 15:40 of the week beginning 2026-10-12, so the week the window opens on is not the
# machine's own.
HELD = datetime.fromisoformat("2026-10-15T15:40")
HELD_MONDAY = "2026-10-12"

# The hosts of the hands these tests make. A hand is its host's Qt child and holds no reference of
# its own to it, so the host has to be kept for as long as the hand is used.
HOSTS: list = []


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-zoom-test"])


class ManualTime:
    """The time motion.Clock reads (its own, not the app clock). It stands still until `advance` moves
    it, so an animation is at an exact place on its easing however busy the machine is."""

    def __init__(self) -> None:
        self.now = 1_000

    def __call__(self) -> int:
        return self.now

    def advance(self, ms: int) -> None:
        """Move the time `ms` on, and give every clock that is running the frame it would have had."""
        self.now += ms
        for clock in list(motion._RUNNING):
            # A paused clock has stopped its timer, so no frame comes for it.
            if clock._timer.isActive():
                clock._tick()


@pytest.fixture()
def manual_time(monkeypatch: pytest.MonkeyPatch) -> ManualTime:
    manual = ManualTime()
    monkeypatch.setattr(motion, "now_ms", manual)
    return manual


def settle(qapp: QApplication) -> None:
    for _ in range(5):
        qapp.processEvents()


# Standalone hours


def a_hand(words: bool = False) -> Hand:
    """A hand that allows everything, saying a held block's times when `words` is set."""
    host = QWidget()
    HOSTS.append(host)
    return Hand(lambda block_id, from_day, span: Verdict(True, span_words(span) if words else ""), host)


def a_week(qapp: QApplication, blocks: list[dict] | None = None, hand: Hand | None = None) -> ClassicWeek:
    # Inside the offscreen screen (800 by 800), where QApplication.widgetAt can find it.
    view = ClassicWeek(hand if hand is not None else a_hand())
    view.set_look(None, resolved_palette("system", False, None))
    view.set_week(build_week(MONDAY, blocks or [], {}, None), 3, NOW)
    view.move(0, 0)
    view.resize(760, 520)
    view.show()
    settle(qapp)
    return view


def a_day(qapp: QApplication, blocks: list[dict], day: int) -> ClassicDay:
    view = ClassicDay(a_hand())
    view.set_look(None, resolved_palette("system", False, None))
    view.move(0, 0)
    view.resize(760, 560)
    view.set_day(build_week(MONDAY, blocks, {}, None), day, 3, NOW)
    view.show()
    settle(qapp)
    return view


def minute_at(view: ClassicWeek | ClassicDay, y: float) -> float:
    """The minute at a height in the hours' viewport."""
    track = view.hours.tracks[0]
    inside = view.scroll.verticalScrollBar().value() + y
    return track.first + (inside - track.area.top()) / track.per_minute()


def hours_placed_by_hand(qapp: QApplication) -> ClassicWeek:
    """A week whose hours are placed by hand, as Clay's row places its card's, so they can be given no
    width at all: the week's own layout keeps them at least as wide as their gutter and a scroll bar,
    and whether that bar takes room depends on the app's style."""
    view = a_week(qapp)
    view.layout().removeWidget(view.scroll)
    view.scroll.setGeometry(0, 0, 760, 520)
    settle(qapp)
    return view


def wheel(widget: QWidget, at: QPointF, notches: float, ctrl: bool = True) -> None:
    modifiers = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    event = QWheelEvent(
        at,
        QPointF(widget.mapToGlobal(at.toPoint())),
        QPoint(),
        QPoint(0, round(120 * notches)),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)


def press_and_drag(widget: QWidget, local: QPointF, step: QPointF) -> None:
    """Press at `local` and move twice by `step`, holding the left button, so a block is picked up."""
    held = Qt.MouseButton.LeftButton
    for kind, point in (
        (QEvent.Type.MouseButtonPress, local),
        (QEvent.Type.MouseMove, local + step),
        (QEvent.Type.MouseMove, local + step * 2),
    ):
        global_at = QPointF(widget.mapToGlobal(point.toPoint()))
        QApplication.sendEvent(
            widget, QMouseEvent(kind, point, global_at, held, held, Qt.KeyboardModifier.NoModifier)
        )


def hold_still(canvas: HoursCanvas, day: int, minute: int) -> None:
    """Press the block at this day and minute and carry it a little across its time, so it is held
    where it is drawn."""
    press = QPointF(canvas.mapFromGlobal(canvas.point_for(day, minute)))
    step = QPointF(0, 6) if canvas.track_for(day).axis is Axis.ACROSS else QPointF(6, 0)
    press_and_drag(canvas, press, step)
    assert canvas.hand.preview is not None, f"nothing was picked up on day {day} at minute {minute}"


def shown(canvas: HoursCanvas, scroll: HoursScroll) -> QRect:
    """What shows of the canvas: the viewport, in the canvas's coordinates."""
    port = scroll.viewport()
    return QRect(canvas.mapFrom(port, QPoint(0, 0)), port.size())


# Lanes


def a_lane_week(qapp: QApplication, hand: Hand | None = None) -> HoursScroll:
    """Seven lanes whose time runs across, as Mission control's week lays them out, with their names
    kept in a strip on the left."""

    def lanes(area: QRectF) -> list[LinearTrack]:
        tall = area.height() / 7
        return [
            LinearTrack(
                day, QRectF(area.left() + 8, area.top() + day * tall, area.width() - 16, tall), Axis.ACROSS
            )
            for day in range(7)
        ]

    hand = hand if hand is not None else a_hand()
    canvas = HoursCanvas(hand, BlockPainter(resolved_palette("system", False, None)), lanes, header=24)
    scroll = HoursScroll(
        canvas,
        Scale("lanes.week", (32, 48, 64, 96), 48),
        lambda px: 24 * px + 16,
        name="lanes",
        gutter=70,
        axis=Axis.ACROSS,
    )
    names = QWidget()
    column = QVBoxLayout(names)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(0)
    for day in range(7):
        label = QLabel(f"Day {day}")
        label.setObjectName(f"laneName{day}")
        column.addWidget(label, 1)
    scroll.set_header(names)
    scroll.move(0, 0)
    scroll.resize(760, 420)
    scroll.show()
    settle(qapp)
    return scroll


def minute_across(scroll: HoursScroll, x: float) -> float:
    track = scroll.canvas.tracks[0]
    return track.first + (scroll.horizontalScrollBar().value() + x - track.area.left()) / track.per_minute()


def a_side(host: QWidget) -> QWidget:
    """A panel beside the hours, with something to take the focus, as Mission's radar."""
    side = QFrame(host)
    side.setFixedWidth(300)
    QVBoxLayout(side).addWidget(QPushButton("Science poster", side))
    return side


# The light window


@pytest.fixture()
def window(qapp: QApplication, tmp_path_factory: pytest.TempPathFactory, tmp_path) -> Iterator[NativeWindow]:
    """Signed in with the clock held at Thursday 15:40 on 2026-10-15 from before the week is first
    shown: school on weekdays from 08:00, dinner every day at 18:00, and nothing next week."""
    CLOCK.set(HELD)
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        made = windows.open((1280, 860))
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
    finally:
        windows.close()


def hours(window: NativeWindow) -> HoursScroll:
    shown_now = [
        scroll for scroll in window.planner.currentWidget().findChildren(HoursScroll) if scroll.isVisible()
    ]
    assert len(shown_now) == 1, f"{len(shown_now)} hours on screen"
    return shown_now[0]


def span_shown(scroll: HoursScroll) -> tuple[float, float]:
    """The first and last minute on screen, along the way time runs."""
    canvas, port = scroll.canvas, scroll.viewport()
    track = next(track for track in canvas.tracks if not track.turn)
    start = QPointF(canvas.mapFrom(port, QPoint(0, 0)))
    end = QPointF(canvas.mapFrom(port, QPoint(port.width(), port.height())))
    if track.axis is Axis.DOWN:
        start.setX(track.area.center().x())
        end.setX(track.area.center().x())
    else:
        start.setY(track.area.center().y())
        end.setY(track.area.center().y())
    return track.minute_at(start), track.minute_at(end)


def opens_at(qapp: QApplication, window: NativeWindow, minute: int, where: str) -> None:
    """`minute` is on screen, with at most half of what shows before it, or the hours go no further:
    now opens in the middle, a first block a little below the top. Clay deck slides its row to the day
    asked for, so the day is measured where it lands."""
    view = window.planner.currentWidget()
    running = QAbstractAnimation.State.Running
    # The app's own motion runs on `motion.Clock`, which is not a Qt animation.
    wait_until(
        qapp,
        lambda: (
            not motion.busy()
            and all(item.state() != running for item in view.findChildren(QAbstractAnimation))
        ),
    )
    for _ in range(4):
        qapp.processEvents()
    scroll = hours(window)
    first, last = span_shown(scroll)
    if scroll.axis is Axis.ACROSS:
        # Mission control's lanes: now always shows when it is in what is shown, and 22:00 does too
        # when both fit, else now sits 30 to 60 minutes from the left edge. Another week, or another
        # day, opens with the evening's end at the right edge.
        if minute == NOW:
            assert first <= minute <= last, f"{where}: now is not on screen"
            assert last >= 22 * 60 or 30 <= minute - first <= 60, f"{where}: now is not near the left edge"
        else:
            assert last >= 22 * 60, f"{where}: the lanes do not reach 22:00"
        return
    assert first <= minute <= last, f"{where}: {minute // 60:02d}:{minute % 60:02d} is not on screen"
    bar = scroll.verticalScrollBar() if scroll.axis is Axis.DOWN else scroll.horizontalScrollBar()
    at_end = bar.value() == bar.maximum()
    half = (last - first) / 2 + 1
    assert minute - first <= half or at_end, f"{where}: opens {minute - first:.0f} minutes above it"


# The Material week


def pump(qapp: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qapp.processEvents()


def show_material(qapp: QApplication, window: NativeWindow) -> QObject:
    """Put Material on screen on the week."""
    window._surface = "material"
    window._material_gave_up = False
    window._material_failed = ""
    if window._settings is not None and window._stack.currentWidget() is window._settings:
        window._close_settings(save=False)
    window.resize(1280, 800)
    window._on_week()
    pump(qapp)
    quick = window._material_page._quick
    quick.grabFramebuffer()
    pump(qapp)
    assert window._stack.currentWidget().objectName() == "materialPage"
    root = window._material_page.root
    assert root is not None
    faded_in(qapp, root)
    return root


def bridge_of(window: NativeWindow) -> QObject:
    return window._material_page.bridge


def qml(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, name
    return found


def visuals(item: QObject) -> list[QObject]:
    """Every painted QML child. A delegate's QObject parent is the repeater model, while its visual
    parent is the grid, so findChildren misses the rows."""
    found: list[QObject] = []
    if not hasattr(item, "childItems"):
        return found
    for child in item.childItems():
        found.append(child)
        found.extend(visuals(child))
    return found


def named(root: QObject, name: str) -> list[QObject]:
    return [item for item in visuals(root) if str(item.objectName()) == name]


def block_named(root: QObject, title: str) -> QObject:
    for block in named(root, "weekBlock"):
        if any(str(label.property("text")) == title for label in named(block, "title")):
            return block
    raise AssertionError(f"no block named {title}")


def click_item(window: NativeWindow, item: QObject) -> None:
    """A real left click on a QML item through the Quick widget, as the pointer does it."""
    quick = window._material_page._quick
    spot = item.mapToScene(item.boundingRect().center())
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=QPoint(int(spot.x()), int(spot.y())))
    pump(QApplication.instance())


def add_homework(window: NativeWindow, key: str, title: str, minutes: int, due: str) -> None:
    window.session.add_homework(
        {"id": key, "title": title, "due": due, "estimate_min": minutes, "revision": 0}
    )
    window.session.save()
    wait_until(QApplication.instance(), lambda: not window.session.busy and not window.session.dirty)
