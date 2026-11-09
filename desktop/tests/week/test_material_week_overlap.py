"""Material Week and Day: blocks that share time overlap, each one visible and clickable.

Expected values come from Jonathan's picks of 2026-11-08 (the earlier item keeps the day's width, a
later one lies on it, shifted right, every block at its own time, and the covered item's name shows
above or below the one on top or, without room there, on its side in its uncovered strip), from
spec.md (ranges are half-open, so back to back is not an overlap) and from the account's own blocks.
"""

# ruff: noqa: F811
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.material.bridge_week import overlapped
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import (
    NOW_DAY,
    _block_named,
    _bridge,
    _centre,
    _click,
    _drag,
    _homework,
    _named,
    _pref,
    _pump,
    _qml,
    _reset,
    _snack,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def _soccer_and_a_pinned_reading(
    window: NativeWindow, qapp: QApplication, minutes: int = 60, soccer: int = 90, at: str = "16:00"
) -> None:
    """Soccer Thursday 16:00 for `soccer` minutes, Reading pinned over it at `at` for `minutes`, Snack
    for half an hour right after Soccer. Soccer and Snack end by 18:45, where the History essay sits."""
    session = window.session
    session.add_block(
        {
            "id": "soccer",
            "title": "Soccer",
            "kind": "locked",
            "category": "exercise",
            "start": "16:00",
            "duration_min": soccer,
            "days": [NOW_DAY],
        }
    )
    session.add_block(
        {
            "id": "snack",
            "title": "Snack",
            "kind": "locked",
            "category": "other",
            "start": f"{16 + soccer // 60:02d}:{soccer % 60:02d}",
            "duration_min": 30,
            "days": [NOW_DAY],
        }
    )
    session.save()
    settled(qapp, window)
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "reading", "Pinned reading", minutes, due)
    work = next(block for block in session.blocks if block.get("assignment_id") == "reading")
    work.update({"start": at, "days": [NOW_DAY], "duration_min": minutes, "pinned": True})
    session.add_block(work)
    session.save()
    settled(qapp, window)
    _pump(qapp)


def _rect(item: QObject) -> QRectF:
    return item.mapRectToScene(item.boundingRect())


def _pinned(window: NativeWindow, qapp: QApplication, key: str, title: str, start: str, minutes: int) -> None:
    """A homework pinned on Thursday at `start` for `minutes`."""
    session = window.session
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, key, title, minutes, due)
    work = next(block for block in session.blocks if block.get("assignment_id") == key)
    work.update({"start": start, "days": [NOW_DAY], "duration_min": minutes, "pinned": True})
    session.add_block(work)
    session.save()
    settled(qapp, window)
    _pump(qapp)


def _shown_name(block: QObject) -> QObject:
    """The one place the block's name is drawn: its title row, or its side strip. Never both."""
    title, side = _named(block, "title")[0], _named(block, "sideName")[0]
    shown = [item for item in (title, side) if item.property("visible")]
    assert len(shown) == 1, f"{block.property('title')}: name shown {len(shown)} times"
    return shown[0]


def _name_whole_and_clear(block: QObject, over: list[QObject]) -> QObject:
    """The covered block's name reads in full, inside the block, under none of the blocks over it; its
    time line, when it shows, is whole and clear too (recheck M5: a lone "4" peeked out)."""
    name = _shown_name(block)
    assert name.property("truncated") is False
    assert _rect(block).adjusted(-0.5, -0.5, 0.5, 0.5).contains(_rect(name))
    for top in over:
        assert not _rect(top).intersects(_rect(name)), (block.property("title"), top.property("title"))
    detail = _named(block, "detail")[0]
    if detail.property("visible"):
        assert _rect(block).adjusted(-0.5, -0.5, 0.5, 0.5).contains(_rect(detail))
        assert all(not _rect(top).intersects(_rect(detail)) for top in over)
    return name


@contextmanager
def _narrow_window(window: NativeWindow, qapp: QApplication) -> Iterator[None]:
    """1000 px wide: a day of the Week is about 76 px, so a block over another is still narrow."""
    window.resize(1000, 800)
    _pump(qapp, 6)
    try:
        yield
    finally:
        window.resize(1280, 800)
        _pump(qapp, 6)


@contextmanager
def _nothing() -> Iterator[None]:
    yield


def _show_thursday_afternoon(root: QObject, window: NativeWindow, qapp: QApplication) -> None:
    grid = _qml(root, "weekScroller")
    row = int(_bridge(window).property("hourRow"))
    grid.setProperty("contentY", float(15 * row))
    _pump(qapp, 4)


def test_items_that_share_time_come_in_time_order_and_each_later_one_steps_past_what_it_covers() -> None:
    rows = [
        {"title": "Short", "day": 3, "start": 960, "end": 1020},
        {"title": "Long", "day": 3, "start": 960, "end": 1050},
        {"title": "After", "day": 3, "start": 1050, "end": 1080},
        {"title": "Middle", "day": 3, "start": 990, "end": 1020},
        {"title": "Monday", "day": 0, "start": 960, "end": 1050},
    ]
    placed = overlapped(rows)

    # Day, then start, the longer first on a tie: the order they are drawn in and tabbed through.
    assert [row["title"] for row in placed] == ["Monday", "Long", "Short", "Middle", "After"]
    by_title = {row["title"]: row for row in placed}
    # Each later item sits one step past the deepest one it covers; After starts as Long ends.
    assert {title: row["indent"] for title, row in by_title.items()} == {
        "Monday": 0,
        "Long": 0,
        "Short": 1,
        "Middle": 2,
        "After": 0,
    }
    # `under` names, by place in the list, the items each one lies on: what QML needs to keep their
    # names in sight. Long is at 1 and Short at 2.
    assert {title: row["under"] for title, row in by_title.items()} == {
        "Monday": [],
        "Long": [],
        "Short": [1],
        "Middle": [1, 2],
        "After": [],
    }


def test_the_rows_given_to_qml_put_the_pinned_reading_over_soccer(
    qapp: QApplication, window: NativeWindow
) -> None:
    _reset(window, qapp)
    _soccer_and_a_pinned_reading(window, qapp)
    rows = list(_bridge(window).property("week").property("blockRows"))
    titles = [(row["title"], row["day"]) for row in rows]
    by_key = {(row["title"], row["day"]): row for row in rows}

    # Same start: Soccer is longer, so it lies underneath and comes first.
    assert titles.index(("Soccer", NOW_DAY)) < titles.index(("Pinned reading", NOW_DAY))
    assert by_key[("Soccer", NOW_DAY)]["indent"] == 0
    assert by_key[("Pinned reading", NOW_DAY)]["indent"] == 1
    # Snack starts the minute Soccer ends: no shared time, so it keeps the whole lane.
    assert by_key[("Snack", NOW_DAY)]["indent"] == 0
    assert by_key[("History essay", NOW_DAY)]["indent"] == 0
    assert by_key[("School", 0)]["indent"] == 0


def test_in_week_the_later_block_lies_over_soccer_with_both_names_whole_and_opens(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    # Long enough for a two-line title beside the time; Soccer is longer still, so it lies underneath.
    _soccer_and_a_pinned_reading(window, qapp, minutes=120, soccer=135)
    _show_thursday_afternoon(root, window, qapp)

    soccer, reading = _block_named(root, "Soccer"), _block_named(root, "Pinned reading")
    reading_title = _named(reading, "title")[0]
    # Normal text, the 1280 px window: the top item's title reads in full, and Soccer's name is not
    # under the block that lies on it.
    assert reading_title.property("truncated") is False
    _name_whole_and_clear(soccer, [reading])
    # The done circle shows whole, inside the block, and leaves the title its room: on the title row
    # when the title fits beside it, under it otherwise.
    finish = _named(reading, "weekBlockFinish")[0]
    assert finish.property("visible") is True
    assert _rect(reading).contains(_rect(finish))
    assert not _rect(finish).intersects(_rect(reading_title))

    _click(window, reading)
    sheets = window._material_page.bridge.sheets
    assert sheets.kind == "homework"
    assert sheets.form["title"] == "Pinned reading"
    sheets.forceClose()
    _pump(qapp)


def test_a_squeezed_homework_block_keeps_a_done_circle_that_finishes_it_and_undo_reopens_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    # Long enough that the circle has room under the time, however narrow the lane is.
    _soccer_and_a_pinned_reading(window, qapp, minutes=120, soccer=135)
    with _narrow_window(window, qapp):
        _show_thursday_afternoon(root, window, qapp)
        reading = _block_named(root, "Pinned reading")
        # Over Soccer in a 1000 px window, its title has no room beside a circle on the title row.
        # What the student relies on is where the circle is: below the title's last line, inside the block's
        # border, so a click on it marks the homework done instead of opening the title.
        finish = _named(reading, "weekBlockFinish")[0]
        assert finish.property("visible") is True
        assert finish.property("activeFocusOnTab") is True
        circle, title, block = _rect(finish), _rect(_named(reading, "title")[0]), _rect(reading)
        assert circle.top() >= title.bottom()
        assert block.contains(circle)

        _click(window, finish)
        wait_until(
            qapp,
            lambda: not window.session.busy and bool(window.session.assignments["reading"].get("completed")),
        )
        wait_until(qapp, lambda: _snack(window) == "Finished Pinned reading.")
        _pump(qapp)
        assert _block_named(root, "Pinned reading").property("done") is True
        bar = _qml(root, "materialSnackbar")
        _click(window, bar, dx=int(bar.property("width")) // 2 - 30)
        wait_until(
            qapp,
            lambda: not window.session.busy and not window.session.assignments["reading"].get("completed"),
        )
        _pump(qapp)
        assert _block_named(root, "Pinned reading").property("done") is False


def test_a_squeezed_blocks_title_never_runs_past_its_column_and_shows_it_is_cut(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    _soccer_and_a_pinned_reading(window, qapp, minutes=120, soccer=135)
    with _narrow_window(window, qapp):
        _show_thursday_afternoon(root, window, qapp)
        reading = _block_named(root, "Pinned reading")
        title = _named(reading, "title")[0]
        # The column is narrower than the word "Pinned": the word breaks inside itself, no line is wider
        # than the column (so the block's edge never cuts a letter), and the cut title says so with "...".
        assert float(title.property("contentWidth")) <= float(title.property("width")) + 0.5
        assert title.property("truncated") is True


def test_a_squeezed_block_too_short_for_the_circle_hides_it_and_the_menu_still_finishes_the_homework(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    # The default 60 minutes: narrow over Soccer, the block is too short for the circle under its words.
    _soccer_and_a_pinned_reading(window, qapp)
    with _narrow_window(window, qapp):
        _show_thursday_afternoon(root, window, qapp)
        reading = _block_named(root, "Pinned reading")
        finish = _named(reading, "weekBlockFinish")[0]
        assert finish.property("visible") is False
        assert finish.property("activeFocusOnTab") is False
        assert reading.property("activeFocusOnTab") is True

        quick = window._material_page._quick
        reading.forceActiveFocus()
        _pump(qapp)
        for _ in range(3):
            QTest.keyClick(quick, Qt.Key.Key_Tab)
            _pump(qapp)
            assert finish.property("activeFocus") is False
        reading.forceActiveFocus()
        _pump(qapp)

        menu = _named(root, "blockMenu")[0]
        QTest.keyClick(quick, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
        _pump(qapp)
        assert menu.property("open") is True
        assert "Mark finished" in [e["label"] for e in menu.property("entries").toVariant()]
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)
        assert menu.property("open") is False

        QTest.mouseClick(quick, Qt.MouseButton.RightButton, pos=_centre(root, reading))
        _pump(qapp)
        assert menu.property("open") is True
        assert "Mark finished" in [e["label"] for e in menu.property("entries").toVariant()]
        QTest.keyClick(quick, Qt.Key.Key_Escape)
        _pump(qapp)


def test_a_wide_homework_block_keeps_its_circle_where_it_was(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    assert essay.property("circleBelow") is False
    assert _named(essay, "weekBlockFinish")[0].property("visible") is True


def test_in_day_both_blocks_that_share_time_open_and_take_tab_in_time_order(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    _soccer_and_a_pinned_reading(window, qapp)
    session = window.session
    thursday = (date.fromisoformat(session.week_start) + timedelta(days=NOW_DAY)).isoformat()
    session.open_day(thursday)
    settled(qapp, window)
    _bridge(window).showPage("day")
    _pump(qapp, 6)
    sheets = window._material_page.bridge.sheets
    quick = window._material_page._quick
    try:
        day = _qml(root, "materialDay")
        _qml(day, "dayScroller").setProperty("contentY", 15 * float(day.property("row")))
        _pump(qapp, 4)
        soccer, reading = _block_named(day, "Soccer"), _block_named(day, "Pinned reading")
        snack = _block_named(day, "Snack")
        # Back to back with Soccer: Snack is not stepped right.
        assert _rect(snack).left() == pytest.approx(_rect(soccer).left(), abs=1)

        # The block on top opens where it shows.
        _click(window, reading)
        assert (sheets.kind, sheets.form["title"]) == ("homework", "Pinned reading")
        sheets.forceClose()
        _pump(qapp)
        # Soccer, underneath, opens on its name where it shows and on its edge left of the reading.
        soccer_name = _name_whole_and_clear(soccer, [reading])
        _click(window, soccer_name)
        assert (sheets.kind, sheets.form["title"]) == ("block", "Soccer")
        sheets.forceClose()
        _pump(qapp)
        edge = QPoint(int(_rect(soccer).left()) + 6, int(_rect(reading).center().y()))
        QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=edge)
        _pump(qapp)
        assert (sheets.kind, sheets.form["title"]) == ("block", "Soccer")
        sheets.forceClose()
        _pump(qapp)

        # Tab goes in time order: Soccer, then the reading over it; back to Soccer, its ring shows in
        # front of the block that covers it.
        soccer.forceActiveFocus()
        _pump(qapp)
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        _pump(qapp)
        assert reading.property("activeFocus") is True
        QTest.keyClick(quick, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        _pump(qapp)
        assert soccer.property("activeFocus") is True
        assert any(ring.property("shown") for ring in _named(soccer, "focusRing"))
        assert float(soccer.property("z")) > float(reading.property("z"))
    finally:
        sheets.forceClose()
        _bridge(window).showPage("week")
        _pump(qapp, 4)


def test_every_block_that_shares_time_starts_at_its_own_time(
    qapp: QApplication, window: NativeWindow
) -> None:
    # Jonathan, 2026-11-08: no block is lowered to keep a name in sight; the recheck read the drop as
    # "starts half an hour late".
    root = _reset(window, qapp)
    _soccer_and_a_pinned_reading(window, qapp)
    _pinned(window, qapp, "sheet", "Math worksheet", "16:15", 60)
    _show_thursday_afternoon(root, window, qapp)
    row = float(_bridge(window).property("hourRow"))
    for title, minute in (("Soccer", 960), ("Pinned reading", 960), ("Math worksheet", 975)):
        top = float(_block_named(root, title).property("y"))
        assert top == pytest.approx(minute / 60 * row, abs=0.5), title


def test_a_covered_items_name_shows_above_the_one_on_top_when_that_starts_later(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    # Soccer 16:00 to 17:30 and the reading pinned 16:45 to 17:15: Soccer's first 45 minutes are free,
    # more than a name line, so its name goes there, above the reading.
    _soccer_and_a_pinned_reading(window, qapp, minutes=30, soccer=90, at="16:45")
    _show_thursday_afternoon(root, window, qapp)
    soccer, reading = _block_named(root, "Soccer"), _block_named(root, "Pinned reading")
    name = _name_whole_and_clear(soccer, [reading])
    assert name.property("objectName") == "title"
    assert _rect(name).bottom() <= _rect(reading).top()
    _click(window, name)
    sheets = window._material_page.bridge.sheets
    try:
        assert (sheets.kind, sheets.form["title"]) == ("block", "Soccer")
    finally:
        sheets.forceClose()
        _pump(qapp)


def test_a_covered_items_name_shows_below_the_shorter_one_on_top(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    # The reading (an hour) lies on Soccer (an hour and three quarters): Soccer's last 45 minutes are
    # free, so its name goes there, below the reading.
    _soccer_and_a_pinned_reading(window, qapp, soccer=105)
    _show_thursday_afternoon(root, window, qapp)
    soccer, reading = _block_named(root, "Soccer"), _block_named(root, "Pinned reading")
    name = _name_whole_and_clear(soccer, [reading])
    assert name.property("objectName") == "title"
    assert _rect(name).top() >= _rect(reading).bottom()
    _click(window, name)
    sheets = window._material_page.bridge.sheets
    try:
        assert (sheets.kind, sheets.form["title"]) == ("block", "Soccer")
    finally:
        sheets.forceClose()
        _pump(qapp)


def test_a_covered_items_name_runs_up_its_strip_when_the_one_on_top_leaves_no_room_below(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    # The reading covers Soccer to within a quarter hour of its end: no room for a name below it. An
    # hour and a quarter is long enough for "Soccer" on its side.
    _soccer_and_a_pinned_reading(window, qapp, minutes=60, soccer=75)
    _show_thursday_afternoon(root, window, qapp)
    soccer, reading = _block_named(root, "Soccer"), _block_named(root, "Pinned reading")
    name = _name_whole_and_clear(soccer, [reading])
    assert name.property("objectName") == "sideName"
    assert name.property("text") == "Soccer"
    # Turned on its side, left of the reading.
    assert abs(float(name.property("rotation"))) == 90
    assert _rect(name).right() <= _rect(reading).left()
    _click(window, name)
    sheets = window._material_page.bridge.sheets
    try:
        assert (sheets.kind, sheets.form["title"]) == ("block", "Soccer")
    finally:
        sheets.forceClose()
        _pump(qapp)


def test_with_three_items_each_covered_name_reads_whole_and_clear(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    # The recheck's shape: one item at Soccer's start and one a quarter hour later, both on Soccer,
    # each long enough for the name it covers to read whole on its side.
    _soccer_and_a_pinned_reading(window, qapp, minutes=120, soccer=135)
    _pinned(window, qapp, "sheet", "Math worksheet", "16:15", 120)
    for wide in (True, False):
        with _narrow_window(window, qapp) if not wide else _nothing():
            _show_thursday_afternoon(root, window, qapp)
            soccer, reading = _block_named(root, "Soccer"), _block_named(root, "Pinned reading")
            sheet = _block_named(root, "Math worksheet")
            _name_whole_and_clear(soccer, [reading, sheet])
            _name_whole_and_clear(reading, [sheet])


def test_a_deep_stack_stays_inside_its_day(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    _soccer_and_a_pinned_reading(window, qapp, soccer=120)
    for at, start in enumerate(("16:05", "16:10", "16:15", "16:20")):
        _pinned(window, qapp, f"stack{at}", f"Stack {at}", start, 60)
    with _narrow_window(window, qapp):
        _show_thursday_afternoon(root, window, qapp)
        soccer = _block_named(root, "Soccer")
        lane = _rect(soccer)
        for title in ("Pinned reading", "Stack 0", "Stack 1", "Stack 2", "Stack 3"):
            block = _rect(_block_named(root, title))
            assert block.left() >= lane.left() and block.right() <= lane.right() + 0.5, title


def test_a_covered_homeworks_done_circle_is_whole_and_clear_or_hidden(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    # The reading (two and a half hours) is longer than Soccer (an hour) at the same start, so Soccer,
    # and Snack after it, lie on it.
    _soccer_and_a_pinned_reading(window, qapp, minutes=150, soccer=60)
    _show_thursday_afternoon(root, window, qapp)
    reading, soccer = _block_named(root, "Pinned reading"), _block_named(root, "Soccer")
    snack = _block_named(root, "Snack")
    _name_whole_and_clear(reading, [soccer, snack])
    finish = _named(reading, "weekBlockFinish")[0]
    if finish.property("visible"):
        assert _rect(reading).contains(_rect(finish))
        assert not _rect(soccer).intersects(_rect(finish))
        assert not _rect(snack).intersects(_rect(finish))


def test_in_week_a_drop_over_the_overlap_lands_on_the_students_step(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    # Friday, after the clock's Thursday 19:00, so the drop is not in the past: Tennis 16:00-17:30.
    friday = NOW_DAY + 1
    window.session.add_block(
        {
            "id": "tennis",
            "title": "Tennis",
            "kind": "locked",
            "category": "exercise",
            "start": "16:00",
            "duration_min": 90,
            "days": [friday],
        }
    )
    window.session.save()
    settled(qapp, window)
    week = _qml(root, "materialWeek")
    row = float(_bridge(window).property("hourRow"))
    gutter, day_width = float(week.property("gutter")), float(week.property("dayWidth"))
    grid = _qml(root, "weekScroller")
    hours_item = next(child for child in grid.childItems()[0].childItems() if child.property("width"))
    try:
        # The second drop lands over Tennis and the first poster.
        for step, expected in ((15, "16:15"), (5, "16:20")):
            _pref(window, drag_step_min=step)
            window._material_page.publish()
            _pump(qapp)
            due = (_week_monday(window) + timedelta(days=6)).isoformat()
            key = f"poster{step}"
            _homework(window, key, f"Poster {step}", 30, due)
            _pump(qapp)
            _show_thursday_afternoon(root, window, qapp)
            # The poster is the one card waiting; the earlier poster is placed.
            cards = _named(root, "homeworkCard")
            assert len(cards) == 1
            # Let go at 16:20 over Tennis: on a 15-minute step that is 16:15, on a 5-minute one 16:20.
            x = gutter + friday * day_width + day_width / 2
            spot = hours_item.mapToScene(QPointF(x, (16 + 1 / 3) * row + 1))
            _drag(window, cards[0], QPoint(int(spot.x()), int(spot.y())))
            wait_until(qapp, lambda key=key: not window.session.busy and not window.session.dirty)
            placed = next(block for block in window.session.blocks if block.get("assignment_id") == key)
            assert (placed["start"], placed["days"]) == (expected, [friday]), step
    finally:
        (window.session.preferences or {}).pop("drag_step_min", None)
        window._material_page.publish()
        _pump(qapp)
