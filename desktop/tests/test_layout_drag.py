"""Dragging in every design, not only Today's app: homework and blocks put down at a time, by one rule
and in the same words everywhere.

Designs with hours of their own take the drop where it is let go. The others open a day's hours beside
themselves while a block is dragged, as Daily Scheduler's timeline draws them, and the drop goes there.
"""

from __future__ import annotations

import contextlib
import importlib.util
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
    from PySide6.QtCore import QByteArray, QMimeData, QPoint, QPointF, QStandardPaths, Qt
    from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QWidget

    from desktop.native.calendar import sunday_due
    from desktop.native.canvas import Timeline
    from desktop.native.layouts import drag
    from desktop.native.layouts.base import LayoutView
    from desktop.native.layouts.registry import sanitize_layout
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


def test_mission_lanes_take_the_day_and_time_under_the_pointer(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = use(qapp, window, "mission")
    lanes = named(view, "missionLanes")
    friday = lanes._lane(4).center().y()
    point = QPoint(round(lanes._x(16 * 60)), round(friday))
    assert let_go(qapp, lanes, point, session_of(window, "math")["id"]) == "Fri 16:00–17:00 · 1 h"
    settled(qapp, window)
    assert placed(window, "math") == ([4], "16:00", True)
    # A bar held by its middle lands where its middle is let go, not with its start under the pointer.
    lanes = named(shown_view(window), "missionLanes")
    point = QPoint(round(lanes._x(17 * 60 + 30)), round(friday))
    said = let_go(qapp, lanes, point, session_of(window, "essay")["id"], grab=30, from_day=3)
    assert said == "Fri 17:00–18:00 · 1 h"
    settled(qapp, window)
    assert placed(window, "essay") == ([4], "17:00", True)


def test_a_drop_on_school_sits_beside_it_and_stays_there(qapp: QApplication, window: NativeWindow) -> None:
    """Allowed and said, as in Daily Scheduler. Put there by hand, so no plan moves it off again."""
    view = use(qapp, window, "mission")
    lanes = named(view, "missionLanes")
    point = QPoint(round(lanes._x(10 * 60)), round(lanes._lane(4).center().y()))
    said = let_go(qapp, lanes, point, session_of(window, "math")["id"])
    assert said == "Fri 10:00–11:00 · 1 h · beside School"
    settled(qapp, window)
    assert placed(window, "math") == ([4], "10:00", True)
    window.session.save()
    settled(qapp, window)
    assert placed(window, "math") == ([4], "10:00", True)
    friday = window.week_table.hours
    if not friday.tracks:
        friday.resize(980, 640)
        friday.relayout()
    track = friday.track_for(4)
    assert track is not None
    drawn = {item.block_id for item, _rect in friday.drawn(track)}
    assert drawn >= {"school", session_of(window, "math")["id"]}


def test_a_repeating_block_dragged_in_a_design_moves_only_that_day(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = use(qapp, window, "mission")
    lanes = named(view, "missionLanes")
    point = QPoint(round(lanes._x(12 * 60)), round(lanes._lane(4).center().y()))
    said = let_go(qapp, lanes, point, "school", grab=180, from_day=4)
    assert said.startswith("Fri 09:00–15:30"), said
    settled(qapp, window)
    school = next(block for block in window.session.blocks if block["id"] == "school")
    assert school["days"] == [0, 1, 2, 3] and school["start"] == "08:00"
    friday = [
        block for block in window.session.blocks if block["title"] == "School" and block["id"] != "school"
    ]
    assert [(block["days"], block["start"], block["duration_min"]) for block in friday] == [
        ([4], "09:00", 390)
    ]


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


def test_a_painted_bar_opens_on_release_and_is_picked_up_where_it_was_held(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifted = recording_lifts(monkeypatch)
    view = use(qapp, window, "mission")
    lanes = named(view, "missionLanes")
    essay_id = session_of(window, "essay")["id"]
    held = QPoint(round(lanes._x(19 * 60 + 15)), round(lanes._lane(3).center().y()))
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    QTest.mouseClick(lanes, Qt.MouseButton.LeftButton, pos=held)
    assert opened == [essay_id] and lifted == []
    QTest.mousePress(lanes, Qt.MouseButton.LeftButton, pos=held)
    QTest.mouseMove(lanes, held + QPoint(40, 0))
    assert len(lifted) == 1 and lifted[0][0] == essay_id and lifted[0][2] == 3
    assert 10 <= lifted[0][1] <= 20, "held a quarter of an hour in"


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
