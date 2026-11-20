"""The keyboard goes back to the week after a sheet closes, a drop, Plan, Undo and redo, so the next arrow,
Tab or Enter works on the week and not on a control that is gone. Real key events through the Material
window; "on the week" is the grid itself or one of its blocks.

Thursday 19:00 is the clock, School runs Monday to Friday and the History essay is planned for 18:45."""

# ruff: noqa: F811
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.tests.material_support import quick_of, quick_window_of  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_material import (  # noqa: E402
    _block_named,
    _bridge,
    _homework,
    _named,
    _pump,
    _qml,
    _reset,
    _snack,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.week.test_material_drag_move_and_resize_blocks import (  # noqa: E402
    ROW,
    body_of,
    club,
    drag,
    on_screen,
)
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

CTRL = Qt.KeyboardModifier.ControlModifier


def _press(window, key: Qt.Key, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
    QTest.keyClick(quick_of(window), key, modifiers)
    _pump(QApplication.instance(), 10)


def _focus(window) -> QObject | None:
    return quick_window_of(window).activeFocusItem()


def _on_the_week(window) -> bool:
    """The keyboard is on a week block or on the week's scroll area, or inside one of them."""
    item = _focus(window)
    while item is not None:
        if str(item.objectName()) in ("weekBlock", "weekScroller"):
            return True
        item = item.parentItem()
    return False


def _on_block(window) -> str:
    """The title of the week block holding the keyboard, or an empty string."""
    item = _focus(window)
    while item is not None:
        if str(item.objectName()) == "weekBlock":
            return str(item.property("title"))
        item = item.parentItem()
    return ""


def _where(window) -> str:
    item = _focus(window)
    names = []
    while item is not None and len(names) < 4:
        names.append(str(item.objectName()) or type(item).__name__)
        item = item.parentItem()
    return " < ".join(names) or "nothing"


def _waiting_homework(qapp, window) -> None:
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, "math", "Math worksheet", 30, due)
    settled(qapp, window)
    _pump(qapp, 30)


def _plan_by_button(qapp, window) -> None:
    _bridge(window).week.planOne("math")
    wait_until(qapp, lambda: _snack(window).startswith("Placed") and not window.session.busy)
    _pump(qapp, 40)


def _focus_school(window, root: QObject) -> None:
    _block_named(root, "School").forceActiveFocus()
    _pump(QApplication.instance())
    assert _on_the_week(window), "the test could not put the keyboard on School"


def test_a_sheet_that_closes_gives_the_keyboard_back_to_the_block_that_opened_it(qapp, window) -> None:
    root = _reset(window, qapp)
    _focus_school(window, root)
    _press(window, Qt.Key.Key_Return)
    _pump(qapp, 30)
    assert _bridge(window).sheets.kind == "block"
    assert not _on_the_week(window), "the sheet did not take the keyboard, so the test says nothing"
    _press(window, Qt.Key.Key_Escape)
    _pump(qapp, 40)
    assert _bridge(window).sheets.kind == ""
    assert _on_the_week(window), f"the keyboard is on {_where(window)}, not on the week"


def test_after_plan_by_keyboard_the_keyboard_is_on_the_week(qapp, window) -> None:
    root = _reset(window, qapp)
    _waiting_homework(qapp, window)
    plan = _qml(root, "planHomework")
    plan.forceActiveFocus()
    _pump(qapp)
    _press(window, Qt.Key.Key_Return)
    wait_until(qapp, lambda: _snack(window).startswith("Placed") and not window.session.busy)
    _pump(qapp, 60)
    assert _on_the_week(window), f"the keyboard is on {_where(window)}, not on the week"


def test_ctrl_z_from_a_block_leaves_the_keyboard_on_the_week(qapp, window) -> None:
    root = _reset(window, qapp)
    _waiting_homework(qapp, window)
    _plan_by_button(qapp, window)
    _focus_school(window, root)
    _press(window, Qt.Key.Key_Z, CTRL)
    wait_until(qapp, lambda: not window.session.busy)
    _pump(qapp, 40)
    assert not any(
        str(label.property("text")) == "Math worksheet"
        for block in _named(root, "weekBlock")
        for label in _named(block, "title")
    ), "Undo did not take the plan back, so the test says nothing"
    assert _on_the_week(window), f"the keyboard is on {_where(window)}, not on the week"
    assert _on_block(window) == "School", "the block acted on keeps the keyboard"


def test_redo_leaves_the_keyboard_on_the_week(qapp, window) -> None:
    root = _reset(window, qapp)
    _waiting_homework(qapp, window)
    _plan_by_button(qapp, window)
    _press(window, Qt.Key.Key_Z, CTRL)
    wait_until(qapp, lambda: not window.session.busy)
    _pump(qapp, 40)
    _focus_school(window, root)
    _press(window, Qt.Key.Key_Y, CTRL)
    wait_until(qapp, lambda: not window.session.busy)
    _pump(qapp, 40)
    assert any(
        str(label.property("text")) == "Math worksheet"
        for block in _named(root, "weekBlock")
        for label in _named(block, "title")
    ), "redo did not put the plan back, so the test says nothing"
    assert _on_the_week(window), f"the keyboard is on {_where(window)}, not on the week"


def test_the_snackbars_undo_by_keyboard_leaves_the_keyboard_on_the_week(qapp, window) -> None:
    root = _reset(window, qapp)
    _waiting_homework(qapp, window)
    _plan_by_button(qapp, window)
    bar = _qml(root, "materialSnackbar")
    bar.forceActiveFocus()
    _pump(qapp)
    _press(window, Qt.Key.Key_Return)
    wait_until(qapp, lambda: not window.session.busy)
    _pump(qapp, 60)
    assert _on_the_week(window), f"the keyboard is on {_where(window)}, not on the week"


def test_a_dropped_block_keeps_the_keyboard_on_the_week(qapp, window) -> None:
    block = on_screen(qapp, window, "week", "Club")
    block.forceActiveFocus()
    _pump(qapp)
    assert _on_the_week(window), "the test could not put the keyboard on Club"
    start = body_of(block)
    drag(qapp, window, start, QPoint(start.x(), start.y() - 5 * ROW))
    assert club(window)["start"] == "11:00", "the block was not moved, so the test says nothing"
    _pump(qapp, 40)
    assert _on_the_week(window), f"the keyboard is on {_where(window)}, not on the week"
    assert _on_block(window) == "Club", "the dropped block keeps the keyboard"


def test_the_snackbars_undo_is_still_a_tab_away_after_plan(qapp, window) -> None:
    """Plan no longer puts the keyboard on the notice, but its Undo stays a Tab away from the week."""
    root = _reset(window, qapp)
    _waiting_homework(qapp, window)
    _plan_by_button(qapp, window)
    _focus_school(window, root)
    bar = _qml(root, "materialSnackbar")
    for _ in range(60):
        _press(window, Qt.Key.Key_Tab)
        if bool(bar.property("activeFocus")) or _focus(window) is bar:
            break
    else:
        pytest.fail(f"Tab never reached the notice's Undo; the keyboard ended on {_where(window)}")
    _press(window, Qt.Key.Key_Return)
    wait_until(qapp, lambda: not window.session.busy)
    _pump(qapp, 60)
    assert _snack(window).startswith("Undid"), _snack(window)
