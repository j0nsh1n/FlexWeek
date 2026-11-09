"""Plan's Undo toast stays until it is used.

A second Plan with nothing new used to replace "Placed 1 homework block." and its Undo with "All your
homework already has a time." After Plan the keyboard stays on the week, and a re-plan offers Undo for
the changes it placed.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from copy import deepcopy

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.widgets import TOAST_MS
from desktop.native.window import NativeWindow
from desktop.tests.grid_support import key, window  # noqa: F401
from desktop.tests.light_app import window as signed_in  # noqa: F401
from desktop.tests.planner.undo_support import PLACED, planned, undo_still_offered
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp, settled  # noqa: F401

# An action toast stays at least this long. Plain messages stay at TOAST_MS.
ACTION_MS = 10_000


def test_plan_offers_undo_in_its_toast(qapp: QApplication, window: NativeWindow) -> None:
    planned(qapp, window)
    assert undo_still_offered(window) == (True, PLACED, True, "Undo")
    assert window.toast._timer.interval() >= ACTION_MS
    assert window.toast._timer.interval() > TOAST_MS


def test_a_second_plan_click_with_nothing_to_do_keeps_the_undo_toast(
    qapp: QApplication, window: NativeWindow
) -> None:
    solve = planned(qapp, window)
    window.toast._timer.start(5_000)
    QTest.mouseClick(solve, Qt.MouseButton.LeftButton)
    settled(qapp, window)
    assert undo_still_offered(window) == (True, PLACED, True, "Undo")
    # The second Plan starts the Undo toast's time over, rather than leaving the short remainder.
    assert window.toast._timer.remainingTime() > 5_000


def test_space_on_plan_with_nothing_to_do_keeps_the_undo_toast(
    qapp: QApplication, window: NativeWindow
) -> None:
    solve = planned(qapp, window)
    solve.setFocus(Qt.FocusReason.MouseFocusReason)
    key(window, Qt.Key.Key_Space)
    settled(qapp, window)
    assert undo_still_offered(window) == (True, PLACED, True, "Undo")


def test_a_plan_with_nothing_to_do_from_any_design_keeps_the_undo_toast(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The session's own Plan (what every design's Plan calls), not tied to one button."""
    planned(qapp, window)
    window.session.solve()
    settled(qapp, window)
    assert undo_still_offered(window) == (True, PLACED, True, "Undo")


def test_the_undo_in_the_toast_takes_the_plan_back(qapp: QApplication, window: NativeWindow) -> None:
    planned(qapp, window)
    session = window.session
    window.toast.button.click()
    settled(qapp, window)
    assert not any(b.get("start") for b in session.blocks if b.get("assignment_id"))


def _week_has_the_keyboard(window: NativeWindow) -> None:
    focus = window.focusWidget()
    assert focus is not None
    assert getattr(focus, "takes_blocks", False), focus.objectName()
    assert not (focus.objectName() or "").startswith("clayDay")
    assert focus is not window.solve_button
    assert focus.objectName() != "moreButton"


def test_after_plan_clay_leaves_the_keyboard_on_the_week(qapp: QApplication, window: NativeWindow) -> None:
    """A day header used to take the keyboard, and Space there changed the day."""
    window._day_mode = False
    window._layout = {"main": "clay", "day": "dial", "options": {}}
    window._on_week()
    settled(qapp, window)
    planned(qapp, window)
    _week_has_the_keyboard(window)


def test_after_plan_dial_leaves_the_keyboard_on_the_week(qapp: QApplication, window: NativeWindow) -> None:
    """The keyboard used to stay on More."""
    window._day_mode = True
    window._layout = {"main": "classic", "day": "dial", "options": {}}
    window._on_week()
    settled(qapp, window)
    planned(qapp, window)
    _week_has_the_keyboard(window)


@pytest.mark.parametrize("mode", ["joined-save", "queued-save", "auto-split"])
def test_replan_offers_undo_for_the_changes_it_placed(
    qapp: QApplication, window: NativeWindow, mode: str
) -> None:
    session = window.session
    if mode == "auto-split":
        session.preferences = {**(session.preferences or {}), "auto_split": True}
    planned(qapp, window)
    before_edit = deepcopy(session.blocks)
    essay = next(b for b in session.blocks if b.get("assignment_id") == "essay")
    session.blocks = [{**b, "start": None} if b is essay else b for b in session.blocks]
    if mode == "queued-save":
        session.save()
        before_replan = deepcopy(session.blocks)
        session.solve(everything=True)
    else:
        session.save()
        settled(qapp, window)
        before_replan = deepcopy(session.blocks)
        if mode == "joined-save":
            session.solve(everything=True, join=True)
        else:
            window.plan_review.replan_requested.emit()
    wait_until(
        qapp,
        lambda: not session.planning
        and not session.busy
        and not session.dirty
        and window.toast.text().startswith("Placed")
        and window.toast.button.isVisible(),
        timeout=20,
        what="the re-plan's Undo toast",
    )
    settled(qapp, window)
    assert window.toast.button.accessibleName() == "Undo"
    window.toast.button.click()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled(qapp, window)
    assert session.blocks == (before_edit if mode == "joined-save" else before_replan)
