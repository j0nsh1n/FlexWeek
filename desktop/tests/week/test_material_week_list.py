"""The Material week read as a list, for a keyboard or a screen reader: every block with its day and times in
reading order, Enter opens a block, and Esc gives the keyboard back to where it came from.

Thursday 19:00 is the clock, School runs 08:00 to 14:30 on weekdays and the History essay is planned for
Thursday 18:45 to 19:45. The expected rows are worked out from that seed and the week's dates."""

# ruff: noqa: F811
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from desktop.tests.material_support import quick_of, quick_window_of  # noqa: E402
from desktop.tests.week.support_material import (  # noqa: E402
    _bridge,
    _named,
    _pump,
    _qml,
    _reset,
    _visuals,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp  # noqa: E402,F401

CTRL_SHIFT = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SHOWN = ("weekListDay", "weekListItem", "weekListNone")


def _open_list(window, qapp) -> QObject:
    root = _reset(window, qapp)
    _bridge(window).sheets.openWeekList()
    _pump(qapp, 40)
    assert _bridge(window).sheets.kind == "weekList"
    return root


def _rows(root: QObject) -> list[tuple[str, str]]:
    """What the list shows, top to bottom: (kind, words). A row that is not drawn is left out."""
    drawn = [item for item in _visuals(root) if str(item.objectName()) in SHOWN and item.property("visible")]
    drawn.sort(key=lambda item: item.mapToScene(QPointF(0, 0)).y())
    rows = []
    for item in drawn:
        kind = str(item.objectName())
        if kind == "weekListItem":
            rows.append((kind, f"{item.property('title')} | {item.property('subtitle')}"))
        else:
            rows.append((kind, str(item.property("text"))))
    return rows


def _focus(window) -> QObject | None:
    return quick_window_of(window).activeFocusItem()


def test_the_week_list_names_each_block_with_its_day_and_times_in_reading_order(qapp, window) -> None:
    root = _open_list(window, qapp)
    monday = _week_monday(window)
    expected: list[tuple[str, str]] = []
    for offset, name in enumerate(DAYS):
        day = monday + timedelta(days=offset)
        expected.append(("weekListDay", f"{name} {day.day} {day:%b}"))
        if offset < 5:
            expected.append(("weekListItem", "School | 08:00–14:30 · 6 h 30 min · Fixed time"))
        if offset == 3:
            expected.append(("weekListItem", "History essay | 18:45–19:45 · 1 h · Placed by Plan"))
        if offset >= 5:
            expected.append(("weekListNone", "Nothing planned"))
    assert _rows(root) == expected


def test_enter_on_a_row_opens_that_block(qapp, window) -> None:
    root = _open_list(window, qapp)
    essay = next(
        item for item in _named(root, "weekListItem") if item.property("title") == "History essay"
    )
    essay.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(quick_of(window), Qt.Key.Key_Return)
    _pump(qapp, 40)
    sheets = _bridge(window).sheets
    assert sheets.kind != "weekList", "Enter left the list open"
    assert "History essay" in str(sheets.form.get("title", "")), f"opened {sheets.kind}, {sheets.form}"


@pytest.mark.parametrize("start", ["weekBlock", "toggleWeekends"])
def test_esc_closes_the_list_and_returns_the_keyboard_to_where_it_came_from(qapp, window, start) -> None:
    root = _reset(window, qapp)
    origin = (
        _named(root, "weekBlock")[0] if start == "weekBlock" else _qml(root, start)
    )
    origin.forceActiveFocus()
    _pump(qapp)
    assert _focus(window) is origin, "the test could not put the keyboard on its starting control"
    QTest.keyClick(quick_of(window), Qt.Key.Key_L, CTRL_SHIFT)
    _pump(qapp, 40)
    sheets = _bridge(window).sheets
    assert sheets.kind == "weekList"
    assert str(_focus(window).objectName()) == "weekListItem", "the list did not take the keyboard"
    QTest.keyClick(quick_of(window), Qt.Key.Key_Escape)
    _pump(qapp, 40)
    assert sheets.kind == ""
    assert _focus(window) is origin, "Esc did not return the keyboard to where it came from"
