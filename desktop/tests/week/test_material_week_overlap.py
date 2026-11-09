"""Material Week and Day: blocks that share time sit side by side, each one visible and clickable.

Expected values come from spec.md ("overlaps are allowed, drawn side by side and named"; ranges are
half-open, so back to back is not an overlap) and from the account's own blocks.
"""

# ruff: noqa: F811
from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QRectF
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.week.support_material import (
    NOW_DAY,
    _block_named,
    _bridge,
    _click,
    _homework,
    _pump,
    _qml,
    _reset,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def _soccer_and_a_pinned_reading(window: NativeWindow, qapp: QApplication) -> None:
    """Soccer Thursday 16:00-17:30, Reading pinned over it 16:00-17:00, Snack right after Soccer."""
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
    _homework(window, "reading", "Pinned reading", 60, due)
    work = next(block for block in session.blocks if block.get("assignment_id") == "reading")
    work.update({"start": "16:00", "days": [NOW_DAY], "duration_min": 60, "pinned": True})
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
