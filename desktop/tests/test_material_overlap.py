"""Material Week and Day: blocks that share time sit side by side, each one visible and clickable.

Expected values come from spec.md ("overlaps are allowed, drawn side by side and named"; ranges are
half-open, so back to back is not an overlap) and from the account's own blocks.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

pytest_plugins = ["desktop.tests.test_material_week"]

from PySide6.QtCore import QObject, QRectF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.test_layouts_window import settled, wait_until  # noqa: E402
from desktop.tests.test_material_week import (  # noqa: E402
    NOW_DAY,
    _block_named,
    _bridge,
    _click,
    _homework,
    _pump,
    _qml,
    _reset,
    _snack,
    _week_monday,
)
from desktop.tests.test_material_window import _named  # noqa: E402


def _soccer_and_a_pinned_reading(window: NativeWindow, qapp: QApplication, minutes: int = 60) -> None:
    """Soccer Thursday 16:00-17:30, Reading pinned over it 16:00 for `minutes`, Snack right after Soccer."""
    session = window.session
    session.add_block(
        {
            "id": "soccer",
            "title": "Soccer",
            "kind": "locked",
            "category": "exercise",
            "start": "16:00",
            "duration_min": 90,
            "days": [NOW_DAY],
        }
    )
    session.add_block(
        {
            "id": "snack",
            "title": "Snack",
            "kind": "locked",
            "category": "other",
            "start": "17:30",
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


def test_the_rows_given_to_qml_carry_each_blocks_column_and_column_count(
    qapp: QApplication, window: NativeWindow
) -> None:
    _reset(window, qapp)
    _soccer_and_a_pinned_reading(window, qapp)
    rows = {(row["title"], row["day"]): row for row in _bridge(window).property("week").property("blockRows")}

    soccer, reading = rows[("Soccer", NOW_DAY)], rows[("Pinned reading", NOW_DAY)]
    assert (soccer["columns"], reading["columns"]) == (2, 2)
    assert {soccer["column"], reading["column"]} == {0, 1}
    # Snack starts the minute Soccer ends: no shared time, so it keeps the whole lane.
    assert (rows[("Snack", NOW_DAY)]["column"], rows[("Snack", NOW_DAY)]["columns"]) == (0, 1)
    assert (rows[("History essay", NOW_DAY)]["column"], rows[("History essay", NOW_DAY)]["columns"]) == (0, 1)
    assert (rows[("School", 0)]["column"], rows[("School", 0)]["columns"]) == (0, 1)


def test_overlapping_blocks_in_week_sit_side_by_side_and_the_pinned_one_opens(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    _soccer_and_a_pinned_reading(window, qapp)
    grid = _qml(root, "weekScroller")
    row = int(_bridge(window).property("hourRow"))
    grid.setProperty("contentY", float(15 * row))
    _pump(qapp, 4)
    day_width = float(_qml(root, "materialWeek").property("dayWidth"))

    soccer, reading = _block_named(root, "Soccer"), _block_named(root, "Pinned reading")
    assert not _rect(soccer).intersects(_rect(reading))
    assert _rect(soccer).width() <= day_width / 2
    assert _rect(reading).width() <= day_width / 2

    # On the title, left of the finish circle, which takes the top right of a half-width block.
    _click(window, reading, dx=-int(_rect(reading).width() / 2) + 10)
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
    _soccer_and_a_pinned_reading(window, qapp, minutes=150)
    grid = _qml(root, "weekScroller")
    row = int(_bridge(window).property("hourRow"))
    grid.setProperty("contentY", float(15 * row))
    _pump(qapp, 4)
    reading = _block_named(root, "Pinned reading")
    # A block shares the lane with Soccer, so its title has no room beside a circle on the title row.
    assert reading.property("circleBelow") is True
    finish = _named(reading, "weekBlockFinish")[0]
    assert finish.property("visible") is True
    assert finish.property("activeFocusOnTab") is True

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


def test_a_wide_homework_block_keeps_its_circle_where_it_was(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    essay = _block_named(root, "History essay")
    assert essay.property("circleBelow") is False
    assert _named(essay, "weekBlockFinish")[0].property("visible") is True


def test_overlapping_blocks_in_day_sit_side_by_side(qapp: QApplication, window: NativeWindow) -> None:
    root = _reset(window, qapp)
    _soccer_and_a_pinned_reading(window, qapp)
    session = window.session
    thursday = (date.fromisoformat(session.week_start) + timedelta(days=NOW_DAY)).isoformat()
    session.open_day(thursday)
    settled(qapp, window)
    _bridge(window).showPage("day")
    _pump(qapp, 6)
    try:
        day = _qml(root, "materialDay")
        soccer, reading = _block_named(day, "Soccer"), _block_named(day, "Pinned reading")
        assert not _rect(soccer).intersects(_rect(reading))
        snack = _block_named(day, "Snack")
        # Back to back with Soccer: Snack keeps the whole lane, wider than either half.
        assert _rect(snack).width() > _rect(soccer).width() + _rect(reading).width()
    finally:
        _bridge(window).showPage("week")
        _pump(qapp, 4)
