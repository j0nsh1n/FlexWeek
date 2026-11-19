"""Material Week: a line above the grid says "N overdue · N left from last week" with Plan into this week and
Mark as finished, the Widgets chip's words and calls, and shows only while something is left over."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from desktop.tests.planner.support import left_in_week_one, overdue_this_week
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import (
    _click,
    _pump,
    _qml,
    _reset,
    _show_material,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def _row(root):
    return _qml(root, "leftOverRow")


def test_the_row_is_hidden_when_nothing_is_left_over(qapp, window) -> None:
    root = _reset(window, qapp)

    assert _row(root).property("visible") is False
    assert _qml(root, "leftOverPlan").property("visible") is False


def test_the_row_says_what_the_line_says(qapp, window) -> None:
    left_in_week_one(qapp, window)
    root = _show_material(qapp, window)
    _pump(qapp)

    assert _row(root).property("visible") is True
    # The seeded essay is overdue by then, besides the lab report left from last week.
    assert _qml(root, "leftOverWords").property("text") == "1 overdue · 1 left from last week"
    assert _qml(root, "leftOverPlan").property("accessName") == "Plan into this week"
    assert _qml(root, "leftOverDone").property("accessName") == "Mark as finished"


def test_the_row_counts_overdue_homework(qapp, window) -> None:
    overdue_this_week(qapp, window)
    root = _show_material(qapp, window)
    _pump(qapp)

    assert _qml(root, "leftOverWords").property("text") == "1 overdue"


def test_a_homework_left_overdue_shows_the_row_with_its_two_buttons_on(qapp, window) -> None:
    overdue_this_week(qapp, window)
    root = _show_material(qapp, window)
    _pump(qapp)

    assert _row(root).property("visible") is True, "the overdue row is not showing"
    for name in ("leftOverPlan", "leftOverDone"):
        button = _qml(root, name)
        assert button.property("visible") is True and button.property("enabled") is True, name
        assert str(button.property("text") or button.property("accessName")), name


def test_plan_into_this_week_places_the_left_over_session(qapp, window) -> None:
    left_in_week_one(qapp, window)
    root = _show_material(qapp, window)
    _pump(qapp)
    assert not [b for b in window.session.blocks if b.get("assignment_id") == "lab" and b.get("start")]

    _click(window, _qml(root, "leftOverPlan"))
    wait_until(
        qapp,
        lambda: not window.session.busy
        and any(b.get("assignment_id") == "lab" and b.get("start") for b in window.session.blocks),
        what="the left-over session placed",
    )


def test_mark_as_finished_finishes_it_and_the_row_goes(qapp, window) -> None:
    left_in_week_one(qapp, window)
    root = _show_material(qapp, window)
    _pump(qapp)

    _click(window, _qml(root, "leftOverDone"))
    wait_until(
        qapp,
        lambda: not window.session.busy and bool(window.session.assignments["lab"].get("completed")),
        what="lab finished",
    )
    _pump(qapp)

    assert _row(root).property("visible") is False


def test_the_two_buttons_are_reached_by_tab_and_pressed_by_the_keyboard(qapp, window) -> None:
    left_in_week_one(qapp, window)
    root = _show_material(qapp, window)
    _pump(qapp)
    plan, done = _qml(root, "leftOverPlan"), _qml(root, "leftOverDone")
    assert plan.property("activeFocusOnTab") is True and done.property("activeFocusOnTab") is True

    plan.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Tab)
    _pump(qapp)
    assert done.property("activeFocus") is True

    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Return)
    wait_until(
        qapp,
        lambda: not window.session.busy and bool(window.session.assignments["lab"].get("completed")),
        what="lab finished from the keyboard",
    )
