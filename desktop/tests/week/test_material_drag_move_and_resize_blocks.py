"""Dragging a block in Material Week and Day (Jonathan, 2026-11-10): press and drag the body to move it to
another time (and, in Week, another day); drag the top or bottom edge to change its start or end. Fixed
times and homework, snapped to the student's step (5 or 15 minutes), saved through the hand-move rule the
plain look uses, with the Undo notice. Esc during the drag puts the block back with nothing saved; a plain
click still opens it.

Expected values are worked out from the seed: Club on Friday 16:00 for an hour, School Monday to Friday
08:00 to 14:30, the History essay planned Thursday 18:45 for an hour, the one clock at Thursday 19:00, and a
row of 56 px an hour (Comfortable, no zoom). Friday is ahead of the clock, so no past-time rule is involved.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import named, pump, qml  # noqa: E402
from desktop.tests.sheets.support_material_sheets import bridge, material_week, week_monday  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_material import _pref  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

THURSDAY = 3
FRIDAY = 4
ROW = 56


def quick_of(window: NativeWindow):
    return window._material_page._quick


def seed_club(qapp, window: NativeWindow, start: str = "16:00") -> None:
    window.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": start,
            "duration_min": 60,
            "days": [FRIDAY],
        }
    )
    window.session.save()
    settled(qapp, window)
    pump(qapp)


def block_on(page: QObject, title: str) -> QObject:
    for block in named(page, "weekBlock"):
        if any(str(label.property("text")) == title for label in named(block, "title")):
            return block
    raise AssertionError(f"no block named {title}")


def on_screen(
    qapp, window: NativeWindow, screen: str, title: str, day: int = FRIDAY, start: str = "16:00"
) -> QObject:
    """Material on Week, or on Day for `day`; returns the named block."""
    root = material_week(qapp, window)
    seed_club(qapp, window, start)
    if screen == "week":
        page = qml(root, "materialWeek")
    else:
        window.session.open_day((week_monday(window) + timedelta(days=day)).isoformat())
        bridge(window).open_page("day", today=False)
        pump(qapp)
        wait_until(qapp, lambda: root.findChild(QObject, "materialDay") is not None)
        page = qml(root, "materialDay")
        wait_until(qapp, lambda: any(
            any(str(label.property("text")) == title for label in named(blk, "title"))
            for blk in named(page, "weekBlock")
        ))
    return block_on(page, title)


def page_of(window: NativeWindow, screen: str) -> QObject:
    return qml(window._material_page.root, "materialWeek" if screen == "week" else "materialDay")


def scene_point(item: QObject, x: float, y: float) -> QPoint:
    spot = item.mapToScene(QPointF(x, y))
    return QPoint(int(spot.x()), int(spot.y()))


def hold_and_move(qapp, window: NativeWindow, start: QPoint, to: QPoint) -> None:
    """Press at `start` and travel to `to` without letting go."""
    quick = quick_of(window)
    QTest.mouseMove(quick, start)
    pump(qapp, 4)
    QTest.mousePress(quick, Qt.MouseButton.LeftButton, pos=start)
    pump(qapp, 4)
    for step in range(1, 13):
        dx, dy = to.x() - start.x(), to.y() - start.y()
        at = QPoint(start.x() + dx * step // 12, start.y() + dy * step // 12)
        QTest.mouseMove(quick, at)
        pump(qapp, 2)


def drag(qapp, window: NativeWindow, start: QPoint, to: QPoint) -> None:
    hold_and_move(qapp, window, start, to)
    QTest.mouseRelease(quick_of(window), Qt.MouseButton.LeftButton, pos=to)
    pump(qapp, 10)
    settled(qapp, window)


def body_of(block: QObject) -> QPoint:
    return scene_point(block, block.width() / 2, block.height() / 2)


def use_step(qapp, window: NativeWindow, minutes: int) -> None:
    _pref(window, drag_step_min=minutes)
    window._material_page.publish()
    pump(qapp, 6)


def club(window: NativeWindow) -> dict:
    return next(item for item in window.session.blocks if item["id"] == "club")


def minutes(text: str) -> int:
    return int(text[:2]) * 60 + int(text[3:])


@pytest.mark.parametrize("screen", ["week", "day"])
def test_dragging_the_body_moves_a_fixed_time_to_another_time_and_undo_puts_it_back(
    qapp, window: NativeWindow, screen: str
) -> None:
    block = on_screen(qapp, window, screen, "Club")
    start = body_of(block)
    drag(qapp, window, start, QPoint(start.x(), start.y() + 2 * ROW))
    moved = club(window)
    assert (moved["days"], moved["start"], moved["duration_min"]) == ([FRIDAY], "18:00", 60)
    assert qml(window._material_page.root, "materialSnackbar").property("visible") is True
    bridge(window).undo()
    settled(qapp, window)
    assert (club(window)["days"], club(window)["start"]) == ([FRIDAY], "16:00")


def test_dragging_a_fixed_time_sideways_moves_it_to_another_day_at_the_same_time(
    qapp, window: NativeWindow
) -> None:
    block = on_screen(qapp, window, "week", "Club")
    day_width = qml(window._material_page.root, "materialWeek").property("dayWidth")
    start = body_of(block)
    drag(qapp, window, start, QPoint(start.x() + int(day_width), start.y()))
    assert (club(window)["days"], club(window)["start"]) == ([FRIDAY + 1], "16:00")


@pytest.mark.parametrize("screen", ["week", "day"])
def test_a_move_snaps_to_a_quarter_hour(qapp, window: NativeWindow, screen: str) -> None:
    block = on_screen(qapp, window, screen, "Club")
    start = body_of(block)
    # 20 minutes of travel is 18.7 px at 56 px an hour: the nearest quarter hour is 15 minutes.
    drag(qapp, window, start, QPoint(start.x(), start.y() + round(20 * ROW / 60)))
    assert club(window)["start"] == "16:15"


@pytest.mark.parametrize("screen", ["week", "day"])
def test_dragging_the_bottom_edge_changes_the_end_and_the_top_edge_changes_the_start(
    qapp, window: NativeWindow, screen: str
) -> None:
    block = on_screen(qapp, window, screen, "Club")
    bottom = scene_point(block, block.width() / 2, block.height() - 3)
    drag(qapp, window, bottom, QPoint(bottom.x(), bottom.y() + ROW))
    assert (club(window)["start"], club(window)["duration_min"]) == ("16:00", 120)
    block = block_on(page_of(window, screen), "Club")
    top = scene_point(block, block.width() / 2, 3)
    drag(qapp, window, top, QPoint(top.x(), top.y() - ROW // 2))
    assert (minutes(club(window)["start"]), club(window)["duration_min"]) == (minutes("15:30"), 150)


def test_dragging_homework_moves_it_and_it_stays_where_it_was_put(qapp, window: NativeWindow) -> None:
    block = on_screen(qapp, window, "week", "History essay")
    start = body_of(block)
    drag(qapp, window, start, QPoint(start.x(), start.y() + 2 * ROW))
    essay = next(item for item in window.session.blocks if item.get("assignment_id") == "essay")
    assert (essay["days"], essay["start"]) == ([THURSDAY], "20:45")


@pytest.mark.parametrize("screen", ["week", "day"])
def test_escape_in_the_middle_of_a_drag_puts_the_block_back_and_saves_nothing(
    qapp, window: NativeWindow, screen: str
) -> None:
    block = on_screen(qapp, window, screen, "Club")
    before = [dict(item) for item in window.session.blocks]
    steps_before = window.session.last_step()
    start = body_of(block)
    hold_and_move(qapp, window, start, QPoint(start.x(), start.y() + 2 * ROW))
    QTest.keyClick(quick_of(window), Qt.Key.Key_Escape)
    pump(qapp, 10)
    end = QPoint(start.x(), start.y() + 2 * ROW)
    QTest.mouseRelease(quick_of(window), Qt.MouseButton.LeftButton, pos=end)
    pump(qapp, 10)
    settled(qapp, window)
    assert [dict(item) for item in window.session.blocks] == before
    assert window.session.last_step() == steps_before
    assert club(window)["start"] == "16:00"


def test_dropping_on_another_block_lands_there(qapp, window: NativeWindow) -> None:
    """Moving onto another block is allowed: the block lands, and Material draws the two overlapping."""
    block = on_screen(qapp, window, "week", "Club")
    start = body_of(block)
    drag(qapp, window, start, QPoint(start.x(), start.y() - 5 * ROW))
    assert (club(window)["days"], club(window)["start"]) == ([FRIDAY], "11:00")
    assert any(item["id"] == "school" for item in window.session.blocks)


@pytest.mark.parametrize("screen", ["week", "day"])
def test_a_plain_click_still_opens_the_block_and_a_tiny_wiggle_moves_nothing(
    qapp, window: NativeWindow, screen: str
) -> None:
    block = on_screen(qapp, window, screen, "Club")
    start = body_of(block)
    QTest.mouseClick(quick_of(window), Qt.MouseButton.LeftButton, pos=start)
    pump(qapp, 20)
    sheets = bridge(window).sheets
    wait_until(qapp, lambda: sheets.kind == "block")
    assert sheets.form["title"] == "Club"
    sheets.forceClose()
    assert club(window)["start"] == "16:00"


def _add_locked(qapp, window: NativeWindow, block_id: str, title: str, day: int, start: str) -> None:
    window.session.add_block(
        {
            "id": block_id,
            "title": title,
            "kind": "locked",
            "category": "extra",
            "start": start,
            "duration_min": 60,
            "days": [day],
        }
    )
    window.session.save()
    settled(qapp, window)
    pump(qapp, 10)


def _start_of(window: NativeWindow, block_id: str) -> str:
    return next(item for item in window.session.blocks if item["id"] == block_id)["start"]


@pytest.mark.parametrize("weekends", [True, False], ids=["weekends shown", "weekends hidden"])
def test_a_drag_on_day_moves_a_saturday_block_whether_week_shows_weekends(
    qapp, window: NativeWindow, weekends: bool
) -> None:
    saturday = 5
    root = material_week(qapp, window)
    _add_locked(qapp, window, "gym", "Gym", saturday, "16:00")
    if not weekends:
        bridge(window).week.toggleWeekends()
        settled(qapp, window)
        pump(qapp, 10)
    window.session.open_day((week_monday(window) + timedelta(days=saturday)).isoformat())
    bridge(window).open_page("day", today=False)
    pump(qapp)
    wait_until(qapp, lambda: root.findChild(QObject, "materialDay") is not None)
    page = qml(root, "materialDay")
    wait_until(
        qapp,
        lambda: any(
            any(str(label.property("text")) == "Gym" for label in named(block, "title"))
            for block in named(page, "weekBlock")
        ),
    )
    start = body_of(block_on(page, "Gym"))
    drag(qapp, window, start, QPoint(start.x(), start.y() + 2 * ROW))

    assert _start_of(window, "gym") == "18:00"


@pytest.mark.parametrize("focused", [False, True], ids=["later block on top", "focused block on top"])
def test_a_hold_on_overlapping_blocks_moves_the_one_drawn_on_top(
    qapp, window: NativeWindow, focused: bool
) -> None:
    """A block with the keyboard is drawn over the later one, so a press where they overlap takes it."""
    root = material_week(qapp, window)
    _add_locked(qapp, window, "a", "Alpha", FRIDAY, "16:00")
    _add_locked(qapp, window, "b", "Beta", FRIDAY, "16:30")
    page = qml(root, "materialWeek")
    alpha = block_on(page, "Alpha")
    beta = block_on(page, "Beta")
    if focused:
        alpha.forceActiveFocus()
        pump(qapp, 5)
    point = scene_point(beta, 10, 14)
    drag(qapp, window, point, QPoint(point.x(), point.y() + 2 * ROW))

    moved, kept = ("a", "b") if focused else ("b", "a")
    starts = {"a": "16:00", "b": "16:30"}
    assert _start_of(window, moved) != starts[moved], "the block drawn on top did not move"
    assert _start_of(window, kept) == starts[kept], "a block not held moved"


# At 56 px an hour a pixel is 60/56 = 1.071 minutes. A drag of 10 px is 10.71 minutes: nearest mark is
# 10 on fives and 15 on quarter hours. 20 px is 21.43 minutes: 20 on fives, 15 on quarter hours. 6 px is
# 6.43 minutes: 5 on fives (a press that moves less than a few pixels is a click, not a drag).
@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize(
    ("step", "pixels", "landed"),
    [(5, 10, "16:10"), (15, 10, "16:15"), (5, 20, "16:20"), (15, 20, "16:15"), (5, 6, "16:05")],
)
def test_a_move_lands_on_the_students_step(
    qapp, window: NativeWindow, screen: str, step: int, pixels: int, landed: str
) -> None:
    block = on_screen(qapp, window, screen, "Club")
    use_step(qapp, window, step)
    start = body_of(block)
    drag(qapp, window, start, QPoint(start.x(), start.y() + pixels))
    assert (club(window)["start"], club(window)["duration_min"]) == (landed, 60)


def edge_point(block: QObject, edge: str) -> QPoint:
    return scene_point(block, block.width() / 2, 3 if edge == "top" else block.height() - 3)


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize(
    ("step", "edge", "pixels", "start", "duration"),
    [
        (5, "bottom", 10, "16:00", 70),
        (15, "bottom", 10, "16:00", 75),
        (5, "top", -10, "15:50", 70),
        (15, "top", -10, "15:45", 75),
    ],
)
def test_a_resize_lands_on_the_students_step_at_either_edge(
    qapp, window: NativeWindow, screen: str, step: int, edge: str, pixels: int, start: str, duration: int
) -> None:
    """Club is 16:00 to 17:00. An edge 10 px (10.71 minutes) away is at 10 minutes on fives and 15 on
    quarter hours: 17:10 or 17:15 for the bottom, 15:50 or 15:45 for the top."""
    block = on_screen(qapp, window, screen, "Club")
    use_step(qapp, window, step)
    at = edge_point(block, edge)
    drag(qapp, window, at, QPoint(at.x(), at.y() + pixels))
    assert (club(window)["start"], club(window)["duration_min"]) == (start, duration)


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize(
    ("step", "edge", "start", "duration"),
    [
        (5, "top", "16:55", 5),
        (15, "top", "16:45", 15),
        (5, "bottom", "16:00", 5),
        (15, "bottom", "16:00", 15),
    ],
)
def test_a_resize_cannot_leave_a_block_shorter_than_one_step(
    qapp, window: NativeWindow, screen: str, step: int, edge: str, start: str, duration: int
) -> None:
    """The plain look keeps a resized edge one step from the other; Material does the same."""
    block = on_screen(qapp, window, screen, "Club")
    use_step(qapp, window, step)
    at = edge_point(block, edge)
    drag(qapp, window, at, QPoint(at.x(), at.y() + (2 * ROW if edge == "top" else -2 * ROW)))
    assert (club(window)["start"], club(window)["duration_min"]) == (start, duration)


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize(("step", "landed"), [(5, "16:35"), (15, "16:30")])
def test_a_block_off_the_step_moves_onto_the_steps_marks_not_by_keeping_its_offset(
    qapp, window: NativeWindow, screen: str, step: int, landed: str
) -> None:
    """The plain look snaps the new time to the step's marks. Club at 16:22 dragged 10 px (10.71 minutes)
    is at 16:32.7: the nearest mark is 16:35 on fives and 16:30 on quarter hours (keeping the offset would
    give 16:33)."""
    block = on_screen(qapp, window, screen, "Club", start="16:22")
    use_step(qapp, window, step)
    start = body_of(block)
    drag(qapp, window, start, QPoint(start.x(), start.y() + 10))
    assert (club(window)["start"], club(window)["duration_min"]) == (landed, 60)


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize(("step", "duration"), [(5, 73), (15, 68)])
def test_resizing_a_block_off_the_step_puts_only_the_moved_edge_on_a_mark(
    qapp, window: NativeWindow, screen: str, step: int, duration: int
) -> None:
    """Club is 16:22 to 17:22. Its bottom edge 10 px lower is at 17:32.7: 17:35 on fives (73 minutes long),
    17:30 on quarter hours (68). The start is not touched."""
    block = on_screen(qapp, window, screen, "Club", start="16:22")
    use_step(qapp, window, step)
    at = edge_point(block, "bottom")
    drag(qapp, window, at, QPoint(at.x(), at.y() + 10))
    assert (club(window)["start"], club(window)["duration_min"]) == ("16:22", duration)


@pytest.mark.parametrize("screen", ["week", "day"])
@pytest.mark.parametrize(("step", "start", "duration"), [(5, "17:15", 7), (15, "17:00", 22)])
def test_the_shortest_off_step_block_keeps_its_end_and_starts_on_a_mark(
    qapp, window: NativeWindow, screen: str, step: int, start: str, duration: int
) -> None:
    """Club is 16:22 to 17:22. Pulling its top edge far down starts it on the last mark a step or more before
    17:22: 17:15 on fives, 17:00 on quarter hours. The end stays at 17:22."""
    block = on_screen(qapp, window, screen, "Club", start="16:22")
    use_step(qapp, window, step)
    top = scene_point(block, block.width() / 2, 3)
    drag(qapp, window, top, QPoint(top.x(), top.y() + 2 * ROW))
    assert (club(window)["start"], club(window)["duration_min"]) == (start, duration)
