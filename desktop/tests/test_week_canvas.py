"""Today's app's week under a real mouse: Daily Scheduler's timeline, a column for each day.

A block is one painted shape. Dragging it moves the block itself, a quarter hour at a time and into
another day, and it lands where it is let go. Its top or bottom edge resizes it. Blocks that overlap
sit side by side. Expected results come from Daily Scheduler (views.py, TimelineWidget).
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from datetime import datetime

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QByteArray, QEvent, QMimeData, QPointF, Qt
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from backend.slots import DAY_START_MIN
    from desktop.native.canvas import (
        EDGE_PX,
        Timeline,
        WeekCanvas,
        overlap_columns,
        shapes_from_blocks,
    )
    from desktop.native.layouts.drag import DAY_MIME, GRAB_MIME, Verdict
    from desktop.native.look import resolved_palette
    from desktop.native.widgets import SESSION_MIME

WEEK = "2026-09-14"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-canvas-test"])


def block(block_id: str, start: str, minutes: int, days: list[int], **fields: object) -> dict:
    return {
        "id": block_id,
        "title": block_id.title(),
        "kind": "locked",
        "start": start,
        "duration_min": minutes,
        "days": days,
        **fields,
    }


def homework(block_id: str, start: str, day: int, minutes: int = 60) -> dict:
    return {**block(block_id, start, minutes, [day]), "kind": "flexible", "assignment_id": "hw-" + block_id}


def labels(blocks: list[dict]) -> list[tuple[str, int, str]]:
    palette = resolved_palette("system", False, None)
    return [
        (shape.title, shape.day, shape.detail)
        for shape in shapes_from_blocks(WEEK, blocks, None, None, palette)
    ]


def timeline(qapp: QApplication, blocks: list[dict]) -> Timeline:
    canvas = WeekCanvas()
    canvas.resize(1256, 700)
    canvas.set_week(WEEK, blocks)
    canvas.show()
    qapp.processEvents()
    hours = canvas.body
    hours.canvas = canvas  # type: ignore[attr-defined]
    return hours


def at(hours: Timeline, day: int, hhmm: str, nudge: float = 0) -> QPointF:
    minute = int(hhmm[:2]) * 60 + int(hhmm[3:])
    return QPointF(hours.column_rect(hours.days.index(day)).center().x(), hours.y_of(minute) + nudge)


def send(hours: Timeline, kind: QEvent.Type, point: QPointF, held: bool) -> None:
    buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
    event = QMouseEvent(
        kind,
        point,
        QPointF(hours.mapToGlobal(point.toPoint())),
        Qt.MouseButton.LeftButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(hours, event)


def drag(hours: Timeline, start: QPointF, end: QPointF, *, release: bool = True) -> None:
    send(hours, QEvent.Type.MouseButtonPress, start, True)
    send(hours, QEvent.Type.MouseMove, (start + end) / 2, True)
    send(hours, QEvent.Type.MouseMove, end, True)
    if release:
        send(hours, QEvent.Type.MouseButtonRelease, end, False)


def recorded(hours: Timeline) -> dict[str, list[tuple]]:
    seen: dict[str, list[tuple]] = {"moved": [], "refused": [], "created": [], "opened": []}
    hours.moved.connect(lambda *args: seen["moved"].append(args))
    hours.refused.connect(lambda words: seen["refused"].append((words,)))
    hours.range_created.connect(lambda *args: seen["created"].append(args))
    hours.block_activated.connect(lambda block_id: seen["opened"].append((block_id,)))
    return seen


def where(hours: Timeline, block_id: str) -> list[tuple[int, int, int]]:
    return [
        (shape.day, shape.start, shape.end)
        for shape, _rect, _count, _held in hours.laid_out()
        if shape.block_id == block_id
    ]


def test_a_block_says_its_time_and_whether_it_was_missed_done_or_pinned() -> None:
    missed = block("school", "08:00", 60, [0], missed_days=[0])
    done = {**homework("essay", "16:00", 1), "days": [1, 2], "completed": True, "completed_day": 1}
    pinned = {**homework("maths", "17:00", 3), "pinned": True}
    assert labels([missed, done, pinned]) == [
        ("School", 0, "08:00 · Fixed · Missed"),
        ("Essay", 1, "16:00 · Work · Done"),
        ("Maths", 3, "17:00 · Work · Pinned"),
    ], "finished work sits only on the day it was done"


def test_blocks_that_overlap_sit_side_by_side_and_are_marked(qapp: QApplication) -> None:
    hours = timeline(
        qapp,
        [
            block("band", "07:00", 60, [2]),
            block("tutoring", "07:30", 60, [2]),
            block("lunch", "12:00", 30, [2]),
        ],
    )
    shapes = {shape.block_id: (rect, count) for shape, rect, count, _held in hours.laid_out()}
    (band, band_count), (tutoring, tutoring_count) = shapes["band"], shapes["tutoring"]
    assert (band_count, tutoring_count, shapes["lunch"][1]) == (2, 2, 1), (
        "only the two that overlap are marked"
    )
    assert band.right() < tutoring.left(), "side by side, not on top of each other"
    assert shapes["lunch"][0].width() > band.width() * 1.8, "a block alone has its day's full width"


def test_equal_shapes_still_get_a_column_each() -> None:
    palette = resolved_palette("system", False, None)
    one = shapes_from_blocks(WEEK, [block("school", "08:00", 60, [3])], None, None, palette)[0]
    assert overlap_columns([one, one]) == [(0, 2), (1, 2)]


def test_a_block_moves_with_the_pointer_by_where_it_was_held_and_into_another_day(qapp: QApplication) -> None:
    hours = timeline(qapp, [homework("essay", "18:00", 2)])
    seen = recorded(hours)
    # Held by its middle, let go an hour and a day later: its middle lands there, not its top.
    drag(hours, at(hours, 2, "18:30"), at(hours, 3, "19:30"), release=False)
    assert where(hours, "essay") == [(3, 19 * 60, 20 * 60)], "the block itself follows the pointer"
    assert seen["moved"] == [], "nothing changes before it is let go"
    assert hours.held_words() == "Thu 19:00–20:00 · 1 h", "its new times are written on it"
    send(hours, QEvent.Type.MouseButtonRelease, at(hours, 3, "19:30"), False)
    assert seen["moved"] == [("essay", 2, 3, 19 * 60, 20 * 60)]


def test_a_move_snaps_to_the_quarter_hour(qapp: QApplication) -> None:
    hours = timeline(qapp, [homework("essay", "18:00", 2)])
    seen = recorded(hours)
    drag(hours, at(hours, 2, "18:30"), at(hours, 2, "18:52"))
    assert seen["moved"] == [("essay", 2, 2, 18 * 60 + 15, 19 * 60 + 15)]


def test_the_edges_resize_and_the_middle_moves(qapp: QApplication) -> None:
    hours = timeline(qapp, [homework("essay", "18:00", 2)])
    seen = recorded(hours)
    drag(hours, at(hours, 2, "19:00", -EDGE_PX / 2), at(hours, 2, "19:45", -EDGE_PX / 2))
    assert seen["moved"] == [("essay", 2, 2, 18 * 60, 19 * 60 + 45)], "the bottom edge moves the end"
    seen["moved"].clear()
    # Nothing is saved here, so the block is still 18:00 to 19:00.
    drag(hours, at(hours, 2, "18:00", EDGE_PX / 2 + 1), at(hours, 2, "17:30", EDGE_PX / 2 + 1))
    assert seen["moved"] == [("essay", 2, 2, 17 * 60 + 30, 19 * 60)], "the top edge moves the start"
    seen["moved"].clear()
    drag(hours, at(hours, 2, "18:00", EDGE_PX / 2 + 1), at(hours, 2, "21:00"))
    assert seen["moved"] == [("essay", 2, 2, 18 * 60 + 45, 19 * 60)], "never shorter than a quarter hour"


def test_a_refused_drop_goes_back_and_says_why(qapp: QApplication) -> None:
    hours = timeline(qapp, [homework("essay", "18:00", 2)])
    hours.judge = lambda _id, _from, day, start, end: (
        Verdict(False, "That ends after it is due, so it stayed where it was.")
        if day > 2
        else Verdict(True, "", start, end)
    )
    seen = recorded(hours)
    drag(hours, at(hours, 2, "18:30"), at(hours, 4, "18:30"), release=False)
    assert hours.held_words() == "That ends after it is due, so it stayed where it was.", (
        "the block says so while held"
    )
    send(hours, QEvent.Type.MouseButtonRelease, at(hours, 4, "18:30"), False)
    assert seen["moved"] == []
    assert seen["refused"] == [("That ends after it is due, so it stayed where it was.",)]
    assert where(hours, "essay") == [(2, 18 * 60, 19 * 60)]


def test_escape_lets_go_of_a_drag(qapp: QApplication) -> None:
    hours = timeline(qapp, [homework("essay", "18:00", 2)])
    seen = recorded(hours)
    drag(hours, at(hours, 2, "18:30"), at(hours, 2, "19:30"), release=False)
    QTest.keyClick(hours, Qt.Key.Key_Escape)
    assert where(hours, "essay") == [(2, 18 * 60, 19 * 60)]
    send(hours, QEvent.Type.MouseButtonRelease, at(hours, 2, "19:30"), False)
    assert seen["moved"] == []


def test_double_clicking_anywhere_on_a_block_opens_it_and_enter_opens_the_chosen_one(
    qapp: QApplication,
) -> None:
    hours = timeline(qapp, [block("soccer", "07:00", 60, [0])])
    seen = recorded(hours)
    for hhmm in ("07:00", "07:30", "07:55"):
        point = at(hours, 0, hhmm, 2)
        send(hours, QEvent.Type.MouseButtonPress, point, True)
        send(hours, QEvent.Type.MouseButtonRelease, point, False)
        send(hours, QEvent.Type.MouseButtonDblClick, point, True)
        send(hours, QEvent.Type.MouseButtonRelease, point, False)
    assert seen["opened"] == [("soccer",)] * 3
    assert seen["moved"] == [], "a double-click is not a drag"
    QTest.keyClick(hours, Qt.Key.Key_Return)
    assert seen["opened"][-1] == ("soccer",) and len(seen["opened"]) == 4


def test_dragging_empty_time_makes_a_block_of_that_span_and_a_click_fills_the_gap(qapp: QApplication) -> None:
    hours = timeline(qapp, [block("school", "08:00", 390, [0]), block("soccer", "16:00", 60, [0])])
    seen = recorded(hours)
    drag(hours, at(hours, 1, "17:00", 2), at(hours, 1, "18:30"))
    assert seen["created"] == [(1, 17 * 60, 18 * 60 + 30)]
    point = at(hours, 0, "15:30", 2)
    send(hours, QEvent.Type.MouseButtonPress, point, True)
    send(hours, QEvent.Type.MouseButtonRelease, point, False)
    assert seen["created"][-1] == (0, 15 * 60 + 30, 16 * 60), "an hour, cut short where Soccer starts"


def test_a_block_dragged_in_from_elsewhere_shows_where_it_lands_and_drops_there(qapp: QApplication) -> None:
    hours = timeline(qapp, [block("school", "08:00", 60, [0])])
    hours.minutes_of = lambda _block_id: 45
    dropped: list[tuple] = []
    hours.dropped.connect(lambda *args: dropped.append(args))
    data = QMimeData()
    data.setData(SESSION_MIME, QByteArray(b"essay"))
    data.setData(GRAB_MIME, QByteArray(b"15"))
    data.setData(DAY_MIME, QByteArray(b"1"))
    point = at(hours, 4, "17:15", 2)
    action, held, keys = Qt.DropAction.MoveAction, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    QApplication.sendEvent(hours, QDragEnterEvent(point.toPoint(), action, data, held, keys))
    QApplication.sendEvent(hours, QDragMoveEvent(point.toPoint(), action, data, held, keys))
    assert hours.incoming_words() == "Fri 17:00–17:45 · 45 min", (
        "held a quarter hour in, so it starts at 17:00"
    )
    QApplication.sendEvent(hours, QDropEvent(point, action, data, held, keys))
    assert dropped == [("essay", 1, 4, 17 * 60)]
    assert hours.incoming_words() == ""


def test_the_current_week_opens_on_now_not_dawn(qapp: QApplication) -> None:
    canvas = WeekCanvas()
    canvas.resize(960, 320)
    canvas.show()
    qapp.processEvents()
    canvas.set_week(WEEK, [block("school", "08:00", 60, [0])])
    now = datetime(2026, 9, 17, 13, 40)
    canvas.reveal(WEEK, int(now.timestamp() * 1000))
    qapp.processEvents()
    top = canvas.scroll.verticalScrollBar().value()
    shown = canvas.scroll.viewport().height()
    assert top > canvas.body.y_of(DAY_START_MIN)
    assert top <= canvas.body.y_of(13 * 60 + 40) <= top + shown
    assert (canvas.body.today, canvas.body.now_min) == (3, 13 * 60 + 40)
