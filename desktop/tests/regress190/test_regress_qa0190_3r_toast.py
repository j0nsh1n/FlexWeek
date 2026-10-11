"""Regression for QA's 3-R (fix-specs-0190.md, reopens item 3): Plan's Undo toast goes too soon, Undo is
hard to reach by keyboard, Replan has no Undo, and Reduce/Off motion has no time-left cue.

Not covered here, and why: required behaviour 1 (hover decided by pointer geometry over untracked parts
of the page) and 2 (the timer pauses while the window is minimised) need a real pointer and a window
manager; offscreen has neither (QCursor.setPos sends no hover to untracked widgets and showMinimized
does not change the window state). Those are Assistant Local's X11 acceptance checks 1 and 5.
Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from desktop.native.calendar import sunday_due
from desktop.native.hours.canvas import HoursCanvas
from desktop.native.widgets import Toast
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
from desktop.tests.regress184.test_regress_item3_plan_undo_toast import PLACED, planned
from desktop.tests.test_focus_returns import add_homework

KNOWN_TAB = "known failure (3-R.3): with the plan bar open, Tab from the week goes to planReviewDetails"
KNOWN_SECONDS = "known failure (3-R.5): the Undo button has no seconds left ('Undo · 8 s')"
KNOWN_FILTER = "known failure (3-R / C3): Toast installs an app-wide event filter (app.installEventFilter)"


def test_3r_guard_plan_offers_undo(qapp, window) -> None:
    planned(qapp, window)
    assert window.toast.button.isVisible() and window.toast.text() == PLACED


@pytest.mark.parametrize(
    "bar",
    [False, pytest.param(True, marks=pytest.mark.xfail(strict=True, reason=KNOWN_TAB))],
    ids=["no-plan-bar", "plan-bar-open"],
)
def test_3r_first_tab_from_the_week_after_plan_goes_to_undo(qapp, window, bar) -> None:
    """Timmy: Tab reaches the plan bar's Details and Replan before Undo. With the bar open (one homework
    that cannot fit, so the plan has something to explain) and without it."""
    if bar:
        session = window.session
        session.add_homework({"id": "huge", "title": "Huge project", "due": sunday_due(session.week_start),
                              "estimate_min": 1200, "revision": 0})
        session.save()
        settled(qapp, window)
        add_homework(qapp, window)
        QTest.mouseClick(window.findChild(QPushButton, "solveButton"), Qt.MouseButton.LeftButton)
        wait_until(qapp, lambda: window.toast.isVisible() and window.toast.button.isVisible())
        settled(qapp, window)
        assert window.plan_review.isVisible(), "the plan bar did not open"
    else:
        planned(qapp, window)
    canvas = next(c for c in window.findChildren(HoursCanvas) if c.isVisible())
    canvas.setFocus(Qt.FocusReason.OtherFocusReason)
    settled(qapp, window)
    key(window, Qt.Key.Key_Tab)
    got = QApplication.focusWidget()
    assert got is window.toast.button, f"Tab went to {got.objectName() or type(got).__name__}"


@pytest.mark.parametrize("split", [False, True], ids=["plain", "auto-split"])
def test_3r_replan_all_my_homework_ends_with_placed_and_undo(qapp, window, split) -> None:
    """A passing guard on 0.19.0 offscreen (Timmy's missing Undo did not reproduce here, plain or with the
    focus split's note, cause 4c); Coder's spec asks for a probe of the pending-save and join cases."""
    session = window.session
    if split:
        session.preferences = {**(session.preferences or {}), "auto_split": True}
    planned(qapp, window)
    essay = next(b for b in session.blocks if b.get("assignment_id") == "essay")
    first = (essay.get("days"), essay.get("start"))
    # Take its time away by hand so Replan has something to change.
    session.blocks = [{**b, "start": None} if b is essay else b for b in session.blocks]
    session.save()
    settled(qapp, window)
    window.plan_review.replan_requested.emit()
    wait_until(qapp, lambda: not session.planning and not session.busy and not session.dirty, timeout=20)
    settled(qapp, window)
    assert first[1] is not None
    assert window.toast.isVisible() and window.toast.text().startswith("Placed"), window.toast.text()
    assert window.toast.button.isVisible() and window.toast.button.text().startswith("Undo")


@pytest.mark.xfail(strict=True, reason=KNOWN_SECONDS)
@pytest.mark.parametrize("motion", ["normal", "reduce"])
def test_3r_undo_says_how_many_seconds_are_left(qapp, window, motion) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "motion": motion}
    window._apply_appearance()
    planned(qapp, window)
    said = window.toast.button.text()
    assert re.fullmatch(r"Undo · \d+ s", said), said
    assert window.toast.button.accessibleName() in ("Undo", "")


@pytest.mark.xfail(strict=True, reason=KNOWN_FILTER)
def test_3r_a_toast_installs_no_app_wide_event_filter(qapp, monkeypatch) -> None:
    installed: list = []
    real = qapp.installEventFilter
    monkeypatch.setattr(qapp, "installEventFilter", lambda obj: (installed.append(obj), real(obj))[1])
    host = QWidget()
    over = QWidget(host)
    toast = Toast(host, over)
    toast.show_message("Placed 1 homework block.", "Undo", lambda: None)
    qapp.processEvents()
    try:
        assert [type(obj).__name__ for obj in installed] == []
    finally:
        toast.hide()
        host.deleteLater()
        qapp.processEvents()
