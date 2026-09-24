"""Dragging in every design, not only Today's app: homework and blocks put down at a time, by one rule
and in the same words everywhere.

Designs with hours of their own take the drop where it is let go. The others open a day's hours beside
themselves while a block is dragged, as Daily Scheduler's timeline draws them, and the drop goes there.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import math
import os
import time
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QByteArray, QEvent, QMimeData, QPoint, QPointF, QStandardPaths, Qt
    from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QVBoxLayout, QWidget

    from desktop.native.calendar import sunday_due
    from desktop.native.canvas import Timeline
    from desktop.native.hours.canvas import BlockPainter, HoursCanvas
    from desktop.native.hours.hand import Hand
    from desktop.native.hours.zoom import HoursScroll, Scale
    from desktop.native.layouts import drag
    from desktop.native.layouts.base import LayoutView, Scene, empty
    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.layouts.views import VIEW_CLASSES
    from desktop.native.look import resolved_palette
    from desktop.native.widgets import SESSION_MIME, HomeworkDialog
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_setup

PASSWORD = "a-long-test-password"
DRAWER_VIEWS = ("timeline", "bento", "retro", "clay")


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-drag-test"])


def wait_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


def settled(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    for _ in range(5):
        qapp.processEvents()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)


def look_file() -> Path:
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(root) / "flexweek-look.json"


@pytest.fixture()
def window(qapp: QApplication, tmp_path: Path) -> Iterator[NativeWindow]:
    """This week: School Monday to Friday 08:00-14:30, the History essay on Thursday 19:00-20:00, and
    a Math worksheet that still needs a time. The clock is held at Thursday 10:00."""
    look_file().unlink(missing_ok=True)
    server = LocalServer(tmp_path / "flexweek.db")
    server.start()
    made = NativeWindow(server.origin)
    made.resize(1280, 860)
    made.show()
    try:
        made.username.setText("drag_student")
        made.password.setText(PASSWORD)
        made.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
        made.recovery_ack.setChecked(True)
        made.recovery_continue.click()
        past_setup(qapp, made)
        session = made.session
        thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=10)
        session.now_ms = lambda: int(thursday.timestamp() * 1000)
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
        due = sunday_due(session.week_start)
        for key, title in (("essay", "History essay"), ("math", "Math worksheet")):
            session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
        session.save()
        settled(qapp, made)
        essay = session_of(made, "essay")
        session.add_block({**essay, "start": "19:00", "days": [3]})
        session.save()
        settled(qapp, made)
        yield made
    finally:
        with contextlib.suppress(RuntimeError):
            made.session.client.reset()
        made.hide()
        qapp.processEvents()
        server.stop()
        look_file().unlink(missing_ok=True)


def session_of(window: NativeWindow, assignment_id: str) -> dict:
    return next(block for block in window.session.blocks if block.get("assignment_id") == assignment_id)


def placed(window: NativeWindow, assignment_id: str) -> tuple[list[int], str | None, bool]:
    block = session_of(window, assignment_id)
    return list(block["days"]), block.get("start"), bool(block.get("pinned"))


def use(qapp: QApplication, window: NativeWindow, main: str, day: str = "one") -> LayoutView:
    window._layout = sanitize_layout({"main": main, "day": day})
    window._apply_appearance()
    window._on_week()
    for _ in range(10):
        qapp.processEvents()
    shown = window.planner.currentWidget()
    assert isinstance(shown, LayoutView)
    return shown


def shown_view(window: NativeWindow) -> LayoutView:
    view = window.planner.currentWidget()
    assert isinstance(view, LayoutView)
    return view


def taker(widget: QWidget) -> QWidget:
    """The widget a real drag over `widget` is given to: the nearest one that takes drops."""
    target: QWidget | None = widget
    while target is not None and not target.acceptDrops():
        target = target.parentWidget()
    assert target is not None, widget.objectName()
    return target


def carrying(block_id: str, grab: int = 0, from_day: int = -1) -> QMimeData:
    data = QMimeData()
    data.setData(SESSION_MIME, QByteArray(block_id.encode()))
    data.setData(drag.GRAB_MIME, QByteArray(str(grab).encode()))
    data.setData(drag.DAY_MIME, QByteArray(str(from_day).encode()))
    return data


HELD, KEYS, MOVE = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, Qt.DropAction.MoveAction


def answer(target: QWidget) -> str:
    """What the student is told while a block is over `target`: written on the hours themselves, or in
    the bubble a design with painted hours shows by the pointer."""
    if isinstance(target, Timeline):
        return target.incoming_words()
    view = drag.host_view(target)
    assert view is not None
    return view.drops.showing()


def hover(
    qapp: QApplication, widget: QWidget, point: QPoint, block_id: str, grab: int = 0, from_day: int = -1
) -> str:
    """Bring a block over `point` on `widget`, as a drag does, and read the answer it shows."""
    target = taker(widget)
    spot = widget.mapTo(target, point) if widget is not target else point
    data = carrying(block_id, grab, from_day)
    QApplication.sendEvent(target, QDragEnterEvent(spot, MOVE, data, HELD, KEYS))
    QApplication.sendEvent(target, QDragMoveEvent(spot, MOVE, data, HELD, KEYS))
    qapp.processEvents()
    return answer(target)


def let_go(
    qapp: QApplication, widget: QWidget, point: QPoint, block_id: str, grab: int = 0, from_day: int = -1
) -> str:
    said = hover(qapp, widget, point, block_id, grab, from_day)
    target = taker(widget)
    spot = widget.mapTo(target, point) if widget is not target else point
    data = carrying(block_id, grab, from_day)
    QApplication.sendEvent(target, QDropEvent(QPointF(spot), MOVE, data, HELD, KEYS))
    qapp.processEvents()
    return said


def middle(widget: QWidget) -> QPoint:
    return widget.rect().center()


def named(view: QWidget, name: str) -> QWidget:
    found = view.findChild(QWidget, name)
    assert found is not None, name
    return found


def turn_to(qapp: QApplication, view: LayoutView, day: int, block_id: str) -> None:
    """Hold the dragged block over a day's name in the drawer."""
    pick = named(view.drawer, f"dropDay{day}")
    data = carrying(block_id)  # held here: the event keeps only a pointer to it
    QApplication.sendEvent(pick, QDragEnterEvent(middle(pick), MOVE, data, HELD, KEYS))
    qapp.processEvents()


def hour_point(hours: Timeline, minute: int) -> QPoint:
    return QPoint(round(hours.column_rect(0).center().x()), round(hours.y_of(minute)) + 2)


@pytest.mark.parametrize("main", DRAWER_VIEWS)
def test_a_design_without_hours_opens_a_days_hours_while_dragging_and_the_drop_lands_there(
    qapp: QApplication, window: NativeWindow, main: str
) -> None:
    view = use(qapp, window, main)
    math_id = session_of(window, "math")["id"]
    view.drag_began(math_id, -1)
    drawer = view.drawer
    assert drawer.isVisible() and drawer.day == 3, "homework with no day opens on today"
    turn_to(qapp, view, 4, math_id)
    assert drawer.day == 4 and drawer.hours.days == [4]
    assert drawer.title.text() == "Drop it at a time on Friday"
    said = let_go(qapp, drawer.hours, hour_point(drawer.hours, 17 * 60), math_id)
    view.drag_ended()
    assert said == "Fri 17:00–18:00 · 1 h", main
    assert not drawer.isVisible(), "it goes with the drag"
    settled(qapp, window)
    assert placed(window, "math") == ([4], "17:00", True), main


def test_the_drawer_opens_on_the_day_and_near_the_time_the_block_was_lifted_from(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = use(qapp, window, "bento")
    essay_id = session_of(window, "essay")["id"]
    view.drag_began(essay_id, 3)
    drawer = view.drawer
    assert drawer.day == 3
    top = drawer.scroll.verticalScrollBar().value()
    assert top <= drawer.hours.y_of(19 * 60) <= top + drawer.scroll.viewport().height()
    ghost = drawer.hours.laid_out()
    assert any(shape.block_id == essay_id and shape.day == 3 for shape, _r, _c, _h in ghost), (
        "the day's blocks are drawn, the essay among them"
    )
    view.drag_ended()
    view.drag_began("school", 1)
    assert drawer.day == 1, "Tuesday's School opens on Tuesday, not on today"
    view.drag_ended()


def test_a_days_name_in_the_drawer_is_for_looking_not_for_dropping(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = use(qapp, window, "clay")
    math_id = session_of(window, "math")["id"]
    view.drag_began(math_id, -1)
    pick = named(view.drawer, "dropDay5")
    let_go(qapp, pick, middle(pick), math_id)
    view.drag_ended()
    settled(qapp, window)
    assert view.drawer.day == 5
    assert placed(window, "math")[1] is None


@pytest.mark.parametrize("main", ("mission",))
def test_a_design_with_its_own_hours_opens_no_drawer(
    qapp: QApplication, window: NativeWindow, main: str
) -> None:
    view = use(qapp, window, main)
    view.drag_began(session_of(window, "math")["id"], -1)
    assert view._drawer is None or not view._drawer.isVisible()
    view.drag_ended()


def test_a_drop_after_the_due_date_is_refused_and_changes_nothing(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.session.add_homework(
        {
            "id": "poster",
            "title": "Science poster",
            "due": (date.fromisoformat(window.session.week_start) + timedelta(days=4)).isoformat() + "T23:59",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    window.session.save()
    settled(qapp, window)
    view = use(qapp, window, "bento")
    poster_id = session_of(window, "poster")["id"]
    view.drag_began(poster_id, -1)
    turn_to(qapp, view, 5, poster_id)
    said = let_go(qapp, view.drawer.hours, hour_point(view.drawer.hours, 17 * 60), poster_id)
    view.drag_ended()
    assert said == "That ends after it is due, so it stayed where it was."
    settled(qapp, window)
    assert placed(window, "poster")[1] is None
    assert window.session.message == said


def test_the_day_dial_takes_the_time_round_the_clock(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = sanitize_layout({"main": "classic", "day": "dial"})
    window.findChild(QPushButton, "viewMyDay").click()
    for _ in range(10):
        qapp.processEvents()
    face = named(shown_view(window), "dialFace")
    centre, radius, _width = face._geometry()
    turn = math.radians(face._angle(20 * 60))
    point = QPoint(round(centre.x() + radius * math.sin(turn)), round(centre.y() - radius * math.cos(turn)))
    assert let_go(qapp, face, point, session_of(window, "essay")["id"], from_day=3) == "Thu 20:00–21:00 · 1 h"
    settled(qapp, window)
    assert placed(window, "essay") == ([3], "20:00", True)


def test_one_thing_puts_the_thing_later_along_the_day_bar(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window.findChild(QPushButton, "viewMyDay").click()
    for _ in range(10):
        qapp.processEvents()
    bar = named(shown_view(window), "oneDayBar")
    point = QPoint(round(bar._x(20 * 60 + 30)), bar.height() // 2)
    assert let_go(qapp, bar, point, session_of(window, "essay")["id"], from_day=3) == "Thu 20:30–21:30 · 1 h"
    settled(qapp, window)
    assert placed(window, "essay") == ([3], "20:30", True)


def recording_lifts(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int, int]]:
    lifted: list[tuple[str, int, int]] = []
    monkeypatch.setattr(
        drag,
        "start_drag",
        lambda view, block_id, grab=0, from_day=-1: lifted.append((block_id, grab, from_day)),
    )
    # A click opens the homework editor, which would wait for a student to close it.
    monkeypatch.setattr(HomeworkDialog, "exec", lambda _dialog: QDialog.DialogCode.Rejected)
    return lifted


def test_pressing_and_moving_picks_a_block_up_and_a_click_still_opens_it(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifted = recording_lifts(monkeypatch)
    view = use(qapp, window, "timeline")
    essay_id = session_of(window, "essay")["id"]
    card = named(view, "timelineRow1")
    QTest.mousePress(card, Qt.MouseButton.LeftButton, pos=middle(card))
    QTest.mouseMove(card, middle(card) + QPoint(30, 0))
    QTest.mouseRelease(card, Qt.MouseButton.LeftButton, pos=middle(card) + QPoint(30, 0))
    assert lifted == [(essay_id, 0, 3)], "lifted off Thursday, so only Thursday's copy would move"
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=middle(card))
    assert opened == [essay_id] and len(lifted) == 1


def test_a_redraw_during_a_drag_waits_for_the_drop(qapp: QApplication, window: NativeWindow) -> None:
    """A redraw mid-drag would delete what the drag started on. The minute ticking over redraws."""
    view = use(qapp, window, "timeline")
    card = named(view, "timelineRow1")
    view.drag_began()
    later = window.session.now_ms() + 60_000
    window.session.now_ms = lambda: later
    window._refresh_layout()
    qapp.processEvents()
    assert named(view, "timelineRow1") is card
    view.drag_ended()
    qapp.processEvents()
    assert view.findChild(QWidget, "timelineRow1") is not card


def test_a_drop_while_a_save_is_under_way_lands_once_it_is_done(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = use(qapp, window, "clay")
    window.session.add_block(
        {
            "id": "band",
            "title": "Band",
            "kind": "locked",
            "category": "extra",
            "start": "16:00",
            "duration_min": 60,
            "days": [1],
        }
    )
    window.session.save()
    assert window.session.busy
    view = shown_view(window)
    math_id = session_of(window, "math")["id"]
    view.drag_began(math_id, -1)
    turn_to(qapp, view, 4, math_id)
    let_go(qapp, view.drawer.hours, hour_point(view.drawer.hours, 17 * 60), math_id)
    view.drag_ended()
    settled(qapp, window)
    wait_until(qapp, lambda: placed(window, "math")[1] is not None)
    settled(qapp, window)
    assert placed(window, "math") == ([4], "17:00", True)
    assert not window.session.conflict
    assert any(block["id"] == "band" for block in window.session.blocks)


def test_leaving_the_hours_takes_the_ghost_away(qapp: QApplication, window: NativeWindow) -> None:
    view = use(qapp, window, "retro")
    math_id = session_of(window, "math")["id"]
    view.drag_began(math_id, -1)
    hours = view.drawer.hours
    assert hover(qapp, hours, hour_point(hours, 18 * 60), math_id) == "Thu 18:00–19:00 · 1 h"
    QApplication.sendEvent(hours, QDragLeaveEvent())
    assert hours.incoming_words() == ""
    view.drag_ended()


def test_how_close_the_hours_are_is_kept_for_this_device(qapp: QApplication, window: NativeWindow) -> None:
    """A zoom chosen on Week is in the look file, and the next window opens the Week at it."""
    window.findChild(QPushButton, "viewWeek").click()
    qapp.processEvents()
    QTest.mouseClick(window.findChild(QPushButton, "weekZoomIn"), Qt.MouseButton.LeftButton)
    assert window.week_table.scroll.px == 64
    assert json.loads(look_file().read_text())["zoom"] == {"classic.week": 64}
    again = NativeWindow(window.session.client.origin)
    try:
        assert again.week_table.scroll.px == 64
        assert again.day_view.scroll.px == 96, "the Day was not zoomed, so it opens at its own level"
    finally:
        # Closed and deleted here, so nothing of this second window runs during a later test.
        with contextlib.suppress(RuntimeError):
            again.session.client.reset()
        again.close()
        again.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class ZoomingDesign(LayoutView):
    """The least a design with hours of its own does: hours that scroll and zoom, made anew on every
    render, as a design that rebuilds its page does."""

    layout_id = "mission"
    uses_drawer = False

    def __init__(self, parent: QWidget | None = None, *, hand: Hand | None = None) -> None:
        super().__init__(parent, hand=hand)
        self._box = QVBoxLayout(self)
        self.scroll: HoursScroll | None = None

    def render(self, scene: Scene, week_changed: bool) -> None:
        empty(self._box)
        hours = HoursCanvas(self.hand, BlockPainter(resolved_palette("system", False, None)))
        hours.set_week(scene.week.occurrences, scene.today, scene.minute)
        scale = Scale("test.hours", (32, 48, 64, 96), 48)
        self.scroll = self.keep_zoom(HoursScroll(hours, scale, lambda px: 24 * px, name="test", gutter=48))
        self._box.addWidget(self.scroll)


def zooming_design(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> ZoomingDesign:
    """The test design, where a real design goes: chosen as the main view, in Mission's place."""
    monkeypatch.setitem(VIEW_CLASSES, "mission", ZoomingDesign)
    view = use(qapp, window, "mission")
    assert isinstance(view, ZoomingDesign)
    return view


def zoom_in(view: ZoomingDesign) -> None:
    assert view.scroll is not None
    QTest.mouseClick(view.scroll.buttons.into, Qt.MouseButton.LeftButton)


def redrawn(qapp: QApplication, window: NativeWindow) -> None:
    """A real change, saved: the design draws a new scene, as it does after any edit."""
    window.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "18:00",
            "duration_min": 60,
            "days": [5],
        }
    )
    window.session.save()
    settled(qapp, window)


def test_a_designs_zoom_is_kept_under_its_own_key(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = zooming_design(qapp, window, monkeypatch)
    zoom_in(view)
    assert view.scroll is not None and view.scroll.px == 64
    assert json.loads(look_file().read_text())["zoom"] == {"test.hours": 64}


def test_hours_a_design_makes_again_open_at_the_level_just_chosen(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hours made on the next render open where the student left the last ones, not where the
    design first opened."""
    view = zooming_design(qapp, window, monkeypatch)
    zoom_in(view)
    zoomed = view.scroll
    redrawn(qapp, window)
    assert view.scroll is not zoomed, "the save drew new hours"
    assert view.scroll is not None and view.scroll.px == 64


def test_a_new_window_opens_a_designs_hours_at_the_remembered_level(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = zooming_design(qapp, window, monkeypatch)
    zoom_in(view)
    again = NativeWindow(window.session.client.origin)
    try:
        again.username.setText("drag_student")
        again.password.setText(PASSWORD)
        again.findChild(QPushButton, "signIn").click()
        wait_until(qapp, lambda: again._stack.currentWidget().objectName() == "weekPage")
        shown = use(qapp, again, "mission")
        assert isinstance(shown, ZoomingDesign) and shown.scroll is not None
        assert shown.scroll.px == 64
    finally:
        with contextlib.suppress(RuntimeError):
            again.session.client.reset()
        again.close()
        again.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_a_design_that_never_zooms_leaves_the_kept_levels_alone(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.findChild(QPushButton, "viewWeek").click()
    qapp.processEvents()
    QTest.mouseClick(window.findChild(QPushButton, "weekZoomIn"), Qt.MouseButton.LeftButton)
    view = zooming_design(qapp, window, monkeypatch)
    redrawn(qapp, window)
    assert view.scroll is not None and view.scroll.px == 48
    assert json.loads(look_file().read_text())["zoom"] == {"classic.week": 64}


def test_a_design_holds_its_renders_from_the_press_and_has_the_windows_hand(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A design is given the window's one hand, and a new scene waits from the moment anything is
    pressed, not from the moment it starts to move."""
    from desktop.native.hours.hand import Gesture, Held

    view = use(qapp, window, "timeline")
    assert view.hand is window.hand
    window.hand.press(window, Held(Gesture.PLACE, "Essay", 60, "essay"), QPoint(20, 20))
    assert view._dragging, "a press, before any movement, holds the design's renders"
    window.hand.cancel()
    assert not view._dragging


def test_month_stays_where_the_student_scrolled_it_through_a_refresh(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Month opens on the week the student is in, once. It used to scroll back there every time
    anything refreshed, such as a save, undoing the student's own scrolling."""
    window.resize(900, 560)
    window.findChild(QPushButton, "viewMonth").click()
    wait_until(qapp, lambda: window.session.month_data is not None and not window.session.busy)
    for _ in range(10):
        qapp.processEvents()
    bar = window.month_grid.scroll.verticalScrollBar()
    assert bar.maximum() > 0, "the month is taller than the window, so it scrolls"
    bar.setValue(0 if bar.value() else bar.maximum())
    chosen = bar.value()
    window._on_week()
    for _ in range(10):
        qapp.processEvents()
    assert bar.value() == chosen


def test_a_chip_let_go_after_a_save_failed_is_refused_not_kept_for_later(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A drop after a save that did not go through used to be parked in silence, overwritten by the
    next drop, and made much later when some other save finished."""
    from desktop.native.hours.hand import MoveDate

    session = window.session
    settled(qapp, window)
    essay = session_of(window, "essay")
    thursday = date.fromisoformat(session.week_start) + timedelta(days=3)
    saturday = thursday + timedelta(days=2)
    session.pending_save = {"weeks": [], "assignments": [], "operation_id": "failed-before"}
    try:
        window._apply_change(MoveDate(essay["id"], thursday.isoformat(), saturday.isoformat()))
        assert window._date_waiting is None, "kept to be made later"
        assert "not saved yet" in session.message
    finally:
        session.pending_save = None
    settled(qapp, window)
    assert placed(window, "essay")[:2] == ([3], "19:00")


def test_a_designs_month_stays_where_the_student_scrolled_it_through_a_refresh(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.resize(900, 560)
    view = use(qapp, window, "timeline")
    window.findChild(QPushButton, "viewMonth").click()
    wait_until(qapp, lambda: window.session.month_data is not None and not window.session.busy)
    for _ in range(10):
        qapp.processEvents()
    board = view.findChild(QWidget, "layoutMonthBoard")
    assert board is not None and board.isVisible()
    bar = board.scroll.verticalScrollBar()
    assert bar.maximum() > 0, "the month is taller than the window, so it scrolls"
    bar.setValue(0 if bar.value() else bar.maximum())
    chosen = bar.value()
    # A real change, saved: the design draws a new scene, as it does after any edit.
    window.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "18:00",
            "duration_min": 60,
            "days": [5],
        }
    )
    window.session.save()
    settled(qapp, window)
    wait_until(qapp, lambda: window.session.month_data is not None and not window.session.busy)
    for _ in range(10):
        qapp.processEvents()
    assert board.canvas.index_of(window.session.selected_day) is not None
    assert bar.value() == chosen
