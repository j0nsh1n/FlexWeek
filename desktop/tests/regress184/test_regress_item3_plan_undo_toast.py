"""Regression (item 3): a Plan run with nothing to do does not replace the previous plan's
Undo toast. Pressing Plan again (a second click, or Space while Plan still has the keyboard) used to
say "All your homework already has a time." over "Placed 1 homework block." and its Undo was gone.

Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

from desktop.tests.grid_support import (  # noqa: F401
    key,
    qapp,
    server,
    settled,
    signed_in,
    signed_out,
    wait_until,
    window,
)
from desktop.tests.test_focus_returns import add_homework

KNOWN = "known failure (item 3): 'All your homework already has a time.' replaces the Undo toast"
PLACED = "Placed 1 homework block."


def planned(qapp, window) -> QPushButton:
    add_homework(qapp, window)
    solve = window.findChild(QPushButton, "solveButton")
    QTest.mouseClick(solve, Qt.MouseButton.LeftButton)
    wait_until(qapp, lambda: window.toast.isVisible() and window.toast.button.isVisible())
    settled(qapp, window)
    assert (window.toast.text(), window.toast.button.text()) == (PLACED, "Undo")
    return solve


def undo_still_offered(window) -> tuple[bool, str, bool, str]:
    toast = window.toast
    return toast.isVisible(), toast.text(), toast.button.isVisible(), toast.button.text()


def test_plan_offers_undo_in_its_toast(qapp, window) -> None:
    """Guard: the toast this finding is about."""
    planned(qapp, window)
    assert undo_still_offered(window) == (True, PLACED, True, "Undo")


@pytest.mark.xfail(strict=True, reason=KNOWN)
def test_a_second_plan_click_with_nothing_to_do_keeps_the_undo_toast(qapp, window) -> None:
    solve = planned(qapp, window)
    QTest.mouseClick(solve, Qt.MouseButton.LeftButton)
    settled(qapp, window)
    assert undo_still_offered(window) == (True, PLACED, True, "Undo")


@pytest.mark.xfail(strict=True, reason=KNOWN)
def test_space_on_plan_with_nothing_to_do_keeps_the_undo_toast(qapp, window) -> None:
    solve = planned(qapp, window)
    solve.setFocus(Qt.FocusReason.MouseFocusReason)
    key(window, Qt.Key.Key_Space)
    settled(qapp, window)
    assert undo_still_offered(window) == (True, PLACED, True, "Undo")


@pytest.mark.xfail(strict=True, reason=KNOWN)
def test_a_plan_with_nothing_to_do_from_any_design_keeps_the_undo_toast(qapp, window) -> None:
    """The session's own Plan (what every design's Plan calls), not tied to one button."""
    planned(qapp, window)
    window.session.solve()
    settled(qapp, window)
    assert undo_still_offered(window) == (True, PLACED, True, "Undo")


def test_the_kept_undo_still_takes_the_plan_back(qapp, window) -> None:
    """Guard: Undo in the toast undoes the plan (and stays the plan's Undo once the fix lands)."""
    planned(qapp, window)
    session = window.session
    window.toast.button.click()
    settled(qapp, window)
    assert not any(b.get("start") for b in session.blocks if b.get("assignment_id"))
