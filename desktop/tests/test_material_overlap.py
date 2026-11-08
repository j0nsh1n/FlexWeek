"""Material Week and Day: blocks that share time overlap, each one visible and clickable.

Expected values come from Jonathan's pick of 2026-11-08 (the earlier item keeps the day's width, a
later one lies on it, shifted right, and both names read), from spec.md (ranges are half-open, so
back to back is not an overlap) and from the account's own blocks.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

pytest_plugins = ["desktop.tests.test_material_week"]

from PySide6.QtCore import QObject, QPoint, QRectF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.material.bridge_week import overlapped  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.test_layouts_window import settled, wait_until  # noqa: E402
from desktop.tests.test_material_week import (  # noqa: E402
    NOW_DAY,
    _block_named,
    _bridge,
    _centre,
    _click,
    _homework,
    _pump,
    _qml,
    _reset,
    _snack,
    _week_monday,
)
from desktop.tests.test_material_window import _named  # noqa: E402


def _soccer_and_a_pinned_reading(
    window: NativeWindow, qapp: QApplication, minutes: int = 60, soccer: int = 90
) -> None:
    """Soccer Thursday 16:00 for `soccer` minutes, Reading pinned over it 16:00 for `minutes`, Snack
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
    work.update({"start": "16:00", "days": [NOW_DAY], "duration_min": minutes, "pinned": True})
    session.add_block(work)
    session.save()
    settled(qapp, window)
    _pump(qapp)


def _rect(item: QObject) -> QRectF:
    return item.mapRectToScene(item.boundingRect())


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
    # Short starts with Long, so it sits at least one name strip below Long's top; Middle covers both,
    # so at least two strips below their 16:00.
    assert [960, 1] in by_title["Short"]["lifts"]
    assert [960, 2] in by_title["Middle"]["lifts"]
    assert by_title["After"]["lifts"] == [[1050, 0]]


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
    reading_title, soccer_title = _named(reading, "title")[0], _named(soccer, "title")[0]
    # Normal text, the 1280 px window: the top item's title reads in full, and Soccer's name is not
    # under the block that lies on it.
    assert reading_title.property("truncated") is False
    assert soccer_title.property("truncated") is False
    assert not _rect(reading).intersects(_rect(soccer_title))
    # With room on the title row, the done circle is back beside the title.
    assert reading.property("circleBelow") is False

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
        # Soccer, underneath, opens on its name above the reading and on its edge left of it.
        soccer_name = _named(soccer, "title")[0]
        _click(window, soccer_name, dx=-int(_rect(soccer_name).width() / 2) + 4)
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
