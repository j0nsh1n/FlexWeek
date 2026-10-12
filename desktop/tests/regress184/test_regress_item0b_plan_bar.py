"""Regression for fix-specs.md item 0b: the plan bar's layout throws on every refresh.

`window.py::_layout_plan_review` calls `mapTo` and `width` on `self._column`, a QVBoxLayout, so it raises
AttributeError whenever the plan bar is open, and the rest of `_on_week` (Undo/Redo/Retry, the focus
panel, the end of the animation) is skipped. Qt swallows the exception, so no test saw it.

The spec's guard is in desktop/tests/conftest.py (`no_exception_is_raised_inside_a_qt_slot`): every
desktop test now fails on an exception raised inside a Qt slot; with it, `test_layouts_window.py -k plan`
errors on today's code (test_the_plan_bar_counts_what_the_toast_counts). This file pins the bug itself.
Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import sys
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QPushButton

from desktop.tests.window_support import qapp, server, settled, signed_out, wait_until, window  # noqa: F401

KNOWN = "known failure (item 0b): _layout_plan_review calls mapTo/width on a QVBoxLayout (AttributeError)"
KNOWN_DELETED = (
    "known failure (item 0b): Dialog.refit's QTimer.singleShot(0, self._refit_now) still fires after the "
    "dialog is deleted (widgets.py:2501, RuntimeError: Internal C++ object already deleted)"
)


def open_plan_bar(qapp, window) -> None:
    """As test_layouts_window.test_the_plan_bar_counts_what_the_toast_counts: a plan with something it
    could not place, so the bar stays open."""
    session = window.session
    session.add_block({"id": "school", "title": "School", "kind": "locked", "category": "class",
                       "start": "08:00", "duration_min": 390, "days": [0, 1, 2, 3, 4]})
    due = f"{(date.fromisoformat(session.week_start) + timedelta(days=6)).isoformat()}T23:59"
    session.add_homework({"id": "essay", "title": "History essay", "due": due, "estimate_min": 60,
                          "revision": 0})
    session.add_homework({"id": "poster", "title": "Science fair poster",
                          "due": f"{session.week_start}T08:00", "estimate_min": 600, "revision": 0})
    session.save()
    settled(qapp, window)
    session.solve()
    wait_until(qapp, lambda: session.trace is not None and not session.busy)
    qapp.processEvents()
    assert window.plan_review.isVisible()


@pytest.fixture()
def slot_errors(monkeypatch):
    caught: list[BaseException] = []
    monkeypatch.setattr(sys, "excepthook", lambda _kind, value, _trace: caught.append(value))
    return caught


def refresh(qapp, window, caught: list) -> None:
    """Things that refresh the week while the bar is open: an edit that saves, and a resize (called
    from Python here, so its exception comes back to the caller instead of the excepthook)."""
    session = window.session
    session.add_block({"id": "gym", "title": "Gym", "kind": "locked", "start": "19:00", "duration_min": 60,
                       "days": [2]})
    session.save()
    settled(qapp, window)
    try:
        window.resize(window.width() + 40, window.height())
    except AttributeError as error:
        caught.append(error)
    qapp.processEvents()


@pytest.mark.slot_errors_ok
@pytest.mark.xfail(strict=True, reason=KNOWN)
def test_refreshing_with_the_plan_bar_open_raises_nothing(qapp, window, slot_errors) -> None:
    open_plan_bar(qapp, window)
    refresh(qapp, window, slot_errors)
    assert [repr(error) for error in slot_errors] == []


@pytest.mark.slot_errors_ok
@pytest.mark.xfail(strict=True, reason=KNOWN)
def test_the_plan_bar_sits_over_the_planner_column(qapp, window, slot_errors) -> None:
    open_plan_bar(qapp, window)
    refresh(qapp, window, slot_errors)
    column = window._column  # the QVBoxLayout the bar is meant to float over
    holder = column.parentWidget()
    where = holder.mapTo(window._week_page, column.geometry().topLeft())
    bar = window.plan_review.geometry()
    assert bar.width() in (column.geometry().width(), holder.width()), (bar, column.geometry())
    assert bar.x() in (where.x(), holder.mapTo(window._week_page, QPoint(0, 0)).x()), (bar, where)


@pytest.mark.slot_errors_ok
def test_undo_follows_the_session_while_the_plan_bar_is_open(qapp, window, slot_errors) -> None:
    """Part of the refresh the exception skips; guard (Undo is also synced elsewhere today)."""
    open_plan_bar(qapp, window)
    refresh(qapp, window, slot_errors)
    undo = window.findChild(QPushButton, "undoButton")
    if undo is None:
        pytest.skip("this design has no Undo button on the bar")
    assert undo.isEnabled() == bool(window.session.can_undo())


# The other 70 of the 75 existing tests the guard catches: timers and callbacks on deleted widgets.


@pytest.mark.slot_errors_ok
@pytest.mark.parametrize("sheet", ["homework", "block", "school-hours"])
@pytest.mark.xfail(strict=True, reason=KNOWN_DELETED)
def test_closing_a_sheet_right_after_it_refits_raises_nothing(qapp, slot_errors, sheet) -> None:
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QWidget

    from desktop.native.widgets import BlockDialog, HomeworkDialog, SchoolHoursDialog
    from desktop.tests.window_support import free

    host = QWidget()
    make = {
        "homework": lambda: HomeworkDialog(host, today="2026-10-05", category="assignments"),
        "block": lambda: BlockDialog(host, day=2, start="16:00", duration_min=60),
        "school-hours": lambda: SchoolHoursDialog(host),
    }[sheet]
    dialog = make()
    dialog.show()
    qapp.processEvents()
    dialog.refit()  # what More details, a style change or a resize asks for
    dialog.hide()
    free(dialog)  # closed and deleted in the same turn, as a parent window closing does
    QTest.qWait(30)
    free(host)
    assert [repr(error) for error in slot_errors] == []
