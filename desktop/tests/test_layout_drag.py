"""Dragging in every design, not only Today's app: homework onto a day or a time, and a block to another
one, by the grid's own rules and in its words."""

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

    from desktop.native.calendar import SERIES_DRAG_MESSAGE, sunday_due
    from desktop.native.layouts import drag
    from desktop.native.layouts.base import LayoutView
    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.widgets import SESSION_MIME, HomeworkDialog
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_setup

PASSWORD = "a-long-test-password"
MAIN_VIEWS = ("timeline", "mission", "bento", "retro", "clay")
# The part of each design that means Friday, as a student sees it.
FRIDAY = {
    "timeline": "timelineDay4",
    "mission": "missionDay4",
    "bento": "bentoDay4",
    "retro": "retroDay4",
    "clay": "clayDay4",
}
# Thursday's School and History essay, as each design lists them.
THURSDAY_PAIR = {
    "timeline": ("timelineRow0", "timelineRow1"),
    "mission": ("missionChip0", "missionChip1"),
    "bento": ("bentoChip0", "bentoChip1"),
    "retro": ("retroBlock3-1", "retroBlock3-2"),
    "clay": ("clayPill0", "clayPill1"),
}


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


def carrying(block_id: str, grab: int = 0) -> QMimeData:
    data = QMimeData()
    data.setData(SESSION_MIME, QByteArray(block_id.encode()))
    data.setData(drag.GRAB_MIME, QByteArray(str(grab).encode()))
    return data


def hover(qapp: QApplication, widget: QWidget, point: QPoint, block_id: str, grab: int = 0) -> str:
    """Bring a block over `point` on `widget`, as a drag does, and read the answer it shows."""
    target = taker(widget)
    spot = widget.mapTo(target, point) if widget is not target else point
    data = carrying(block_id, grab)
    held, keys, action = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, Qt.DropAction.MoveAction
    QApplication.sendEvent(target, QDragEnterEvent(spot, action, data, held, keys))
    QApplication.sendEvent(target, QDragMoveEvent(spot, action, data, held, keys))
    qapp.processEvents()
    view = drag.host_view(target)
    assert view is not None
    return view.drops.showing()


def let_go(qapp: QApplication, widget: QWidget, point: QPoint, block_id: str, grab: int = 0) -> str:
    said = hover(qapp, widget, point, block_id, grab)
    target = taker(widget)
    spot = widget.mapTo(target, point) if widget is not target else point
    data = carrying(block_id, grab)
    QApplication.sendEvent(
        target,
        QDropEvent(
            QPointF(spot),
            Qt.DropAction.MoveAction,
            data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )
    qapp.processEvents()
    return said


def middle(widget: QWidget) -> QPoint:
    return widget.rect().center()


def named(view: QWidget, name: str) -> QWidget:
    found = view.findChild(QWidget, name)
    assert found is not None, name
    return found


def gap(view: QWidget, upper_name: str, lower_name: str, vertical: bool = True) -> tuple[QWidget, QPoint]:
    """The point halfway between two neighbouring items, on the list that holds them."""
    upper, lower = named(view, upper_name), named(view, lower_name)
    target = taker(upper)
    top_left = lower.mapTo(target, QPoint(0, 0))
    bottom_right = upper.mapTo(target, QPoint(upper.width(), upper.height()))
    if vertical:
        return target, QPoint(top_left.x() + lower.width() // 2, (bottom_right.y() + top_left.y()) // 2)
    return target, QPoint((bottom_right.x() + top_left.x()) // 2, top_left.y() + lower.height() // 2)


@pytest.mark.parametrize("main", MAIN_VIEWS)
def test_every_design_takes_homework_and_blocks_onto_a_day(
    qapp: QApplication, window: NativeWindow, main: str
) -> None:
    """Homework waiting for a time gets the planner's best time that day. A block with a time keeps it
    on the day it is dropped on. Both stay put in every later plan."""
    view = use(qapp, window, main)
    friday = named(view, FRIDAY[main])
    math_id, essay_id = session_of(window, "math")["id"], session_of(window, "essay")["id"]
    assert let_go(qapp, friday, middle(friday), math_id) == "Plan it on Friday"
    settled(qapp, window)
    days, start, pinned = placed(window, "math")
    assert days == [4] and start is not None and pinned, (main, days, start)
    assert window.session.message.startswith(f"Math worksheet: Friday {start}")
    view = shown_view(window)
    friday = named(view, FRIDAY[main])
    assert let_go(qapp, friday, middle(friday), essay_id) == "Fri 19:00–20:00"
    settled(qapp, window)
    assert placed(window, "essay") == ([4], "19:00", True), main


@pytest.mark.parametrize("main", MAIN_VIEWS)
def test_a_drop_between_two_items_starts_right_after_the_one_above(
    qapp: QApplication, window: NativeWindow, main: str
) -> None:
    view = use(qapp, window, main)
    upper, lower = THURSDAY_PAIR[main]
    target, point = gap(view, upper, lower, vertical=main not in {"mission", "bento"})
    math_id = session_of(window, "math")["id"]
    assert let_go(qapp, target, point, math_id) == "Thu 14:30–15:30", main
    settled(qapp, window)
    assert placed(window, "math") == ([3], "14:30", True), main


def test_the_line_shows_where_it_would_go_and_goes_when_the_pointer_leaves(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = use(qapp, window, "timeline")
    target, point = gap(view, "timelineRow0", "timelineRow1")
    assert hover(qapp, target, point, session_of(window, "math")["id"]) == "Thu 14:30–15:30"
    line = view.drops.lined()
    assert line is not None and line.height() <= 6, "a line between the two cards"
    QApplication.sendEvent(target, QDragLeaveEvent())
    assert view.drops.showing() == "" and view.drops.lined() is None


def test_mission_lanes_take_the_day_and_time_under_the_pointer(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = use(qapp, window, "mission")
    lanes = named(view, "missionLanes")
    friday = lanes._lane(4).center().y()
    point = QPoint(round(lanes._x(16 * 60)), round(friday))
    assert let_go(qapp, lanes, point, session_of(window, "math")["id"]) == "Fri 16:00–17:00"
    settled(qapp, window)
    assert placed(window, "math") == ([4], "16:00", True)
    # A bar held by its middle lands where its middle is let go, not with its start under the pointer.
    lanes = named(shown_view(window), "missionLanes")
    point = QPoint(round(lanes._x(17 * 60 + 30)), round(friday))
    assert let_go(qapp, lanes, point, session_of(window, "essay")["id"], grab=30) == "Fri 17:00–18:00"
    settled(qapp, window)
    assert placed(window, "essay") == ([4], "17:00", True)


def test_a_refused_drop_says_why_in_the_grids_words_and_changes_nothing(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = use(qapp, window, "mission")
    lanes = named(view, "missionLanes")
    point = QPoint(round(lanes._x(10 * 60)), round(lanes._lane(4).center().y()))
    said = let_go(qapp, lanes, point, session_of(window, "math")["id"])
    assert said == "School is at that time, so it stayed where it was."
    assert lanes._ghost is None, "the outline goes with the drop"
    settled(qapp, window)
    assert placed(window, "math")[1] is None
    assert window.session.message == said


def test_a_repeating_block_cannot_be_dragged_in_a_design_either(
    qapp: QApplication, window: NativeWindow
) -> None:
    view = use(qapp, window, "timeline")
    friday = named(view, "timelineDay4")
    said = let_go(qapp, friday, middle(friday), "school")
    assert said == SERIES_DRAG_MESSAGE.format(title="School", count=5)
    school = next(block for block in window.session.blocks if block["id"] == "school")
    assert school["days"] == [0, 1, 2, 3, 4] and school["start"] == "08:00"


def test_a_day_gone_by_or_after_the_due_date_is_refused(qapp: QApplication, window: NativeWindow) -> None:
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
    monday, saturday = named(view, "bentoDay0"), named(view, "bentoDay5")
    math_id, poster_id = session_of(window, "math")["id"], session_of(window, "poster")["id"]
    assert hover(qapp, monday, middle(monday), math_id) == "Monday has already gone by."
    assert hover(qapp, saturday, middle(saturday), poster_id) == "Saturday is after it is due."


def test_the_day_dial_takes_the_time_round_the_clock(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = sanitize_layout({"main": "classic", "day": "dial"})
    window.findChild(QPushButton, "viewMyDay").click()
    for _ in range(10):
        qapp.processEvents()
    face = named(shown_view(window), "dialFace")
    centre, radius, _width = face._geometry()
    turn = math.radians(face._angle(20 * 60))
    point = QPoint(round(centre.x() + radius * math.sin(turn)), round(centre.y() - radius * math.cos(turn)))
    assert let_go(qapp, face, point, session_of(window, "essay")["id"]) == "Thu 20:00–21:00"
    settled(qapp, window)
    assert placed(window, "essay") == ([3], "20:00", True)


def test_one_thing_puts_the_thing_later_along_the_day_bar(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window.findChild(QPushButton, "viewMyDay").click()
    for _ in range(10):
        qapp.processEvents()
    bar = named(shown_view(window), "oneDayBar")
    point = QPoint(round(bar._x(20 * 60 + 30)), bar.height() // 2)
    assert let_go(qapp, bar, point, session_of(window, "essay")["id"]) == "Thu 20:30–21:30"
    settled(qapp, window)
    assert placed(window, "essay") == ([3], "20:30", True)


def test_pressing_and_moving_picks_a_block_up_and_a_click_still_opens_it(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifted: list[tuple[str, int]] = []
    monkeypatch.setattr(drag, "start_drag", lambda view, block_id, grab=0: lifted.append((block_id, grab)))
    # A click opens the homework editor, which would wait for a student to close it.
    monkeypatch.setattr(HomeworkDialog, "exec", lambda _dialog: QDialog.DialogCode.Rejected)
    view = use(qapp, window, "timeline")
    essay_id = session_of(window, "essay")["id"]
    card = named(view, "timelineRow1")
    QTest.mousePress(card, Qt.MouseButton.LeftButton, pos=middle(card))
    QTest.mouseMove(card, middle(card) + QPoint(30, 0))
    QTest.mouseRelease(card, Qt.MouseButton.LeftButton, pos=middle(card) + QPoint(30, 0))
    assert lifted == [(essay_id, 0)]
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=middle(card))
    assert opened == [essay_id] and len(lifted) == 1


def test_a_painted_bar_opens_on_release_and_is_picked_up_where_it_was_held(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifted: list[tuple[str, int]] = []
    monkeypatch.setattr(drag, "start_drag", lambda view, block_id, grab=0: lifted.append((block_id, grab)))
    monkeypatch.setattr(HomeworkDialog, "exec", lambda _dialog: QDialog.DialogCode.Rejected)
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
    assert len(lifted) == 1 and lifted[0][0] == essay_id
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


def test_a_day_drop_while_a_save_is_under_way_is_planned_once_it_is_done(
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
    friday = named(shown_view(window), "clayDay4")
    let_go(qapp, friday, middle(friday), session_of(window, "math")["id"])
    settled(qapp, window)
    wait_until(qapp, lambda: placed(window, "math")[1] is not None)
    settled(qapp, window)
    assert placed(window, "math")[0] == [4]
    assert not window.session.conflict
    assert any(block["id"] == "band" for block in window.session.blocks)
    del view


def test_a_block_let_go_where_it_was_keeps_its_time(qapp: QApplication, window: NativeWindow) -> None:
    """Dropped back on its own card, or anywhere in its own gap, the essay stays at 19:00. It used to be
    read as "after the one above" and jumped to the end of School."""
    view = use(qapp, window, "timeline")
    card = named(view, "timelineRow1")
    essay_id = session_of(window, "essay")["id"]
    assert hover(qapp, card, middle(card), essay_id) == "Thu 19:00–20:00"
    below = QPoint(card.width() // 2, card.height() + 12)
    assert let_go(qapp, card, below, essay_id) == "Thu 19:00–20:00"
    settled(qapp, window)
    assert placed(window, "essay")[:2] == ([3], "19:00")


def test_a_drop_above_the_first_item_ends_as_it_begins(qapp: QApplication, window: NativeWindow) -> None:
    view = use(qapp, window, "clay")
    first = named(view, "clayPill0")
    above = QPoint(first.width() // 2, -3)
    assert let_go(qapp, first, above, session_of(window, "math")["id"]) == "Thu 07:00–08:00"
    settled(qapp, window)
    assert placed(window, "math") == ([3], "07:00", True)
