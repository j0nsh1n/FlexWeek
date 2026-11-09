"""The Undo toast's countdown: it waits while the pointer, the keyboard or the window's absence says
the student is not ready, shows how long is left, is announced once, and follows the Animations setting."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.window import NativeWindow
from desktop.tests.grid_support import window  # noqa: F401
from desktop.tests.light_app import window as signed_in  # noqa: F401
from desktop.tests.planner.undo_support import planned
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp, settled  # noqa: F401

# Leaving the toast starts its clock again with at least this much left.
RESUME_MS = 4_000
SAYS_SECONDS = r"Undo · (\d+) s"


def test_the_undo_timer_pauses_while_its_button_has_the_keyboard(
    qapp: QApplication, window: NativeWindow
) -> None:
    planned(qapp, window)
    window.activateWindow()
    wait_until(qapp, window.isActiveWindow)
    toast = window.toast
    window.solve_button.setFocus(Qt.FocusReason.TabFocusReason)
    qapp.processEvents()
    toast._timer.start(1_000)
    toast.button.setFocus(Qt.FocusReason.TabFocusReason)
    wait_until(qapp, lambda: toast._keys and not toast._timer.isActive())
    assert toast._timer.isActive() is False
    window.solve_button.setFocus(Qt.FocusReason.TabFocusReason)
    wait_until(qapp, lambda: not toast._keys and toast._timer.isActive())
    assert toast._timer.isActive() is True
    # `start` was given at least 4s. A little of that has already run by the time this reads it back.
    assert toast._timer.interval() >= RESUME_MS


def test_the_undo_timer_pauses_while_the_pointer_is_over_its_button(
    qapp: QApplication, window: NativeWindow
) -> None:
    planned(qapp, window)
    window.activateWindow()
    wait_until(qapp, window.isActiveWindow)
    toast = window.toast
    QTest.mouseMove(window.solve_button)
    wait_until(qapp, lambda: not toast._pointer)
    toast._timer.start(1_000)
    QTest.mouseMove(toast.button)
    wait_until(qapp, lambda: toast._pointer and not toast._timer.isActive())
    assert toast._timer.isActive() is False
    QTest.mouseMove(window.solve_button)
    wait_until(qapp, lambda: not toast._pointer and toast._timer.isActive())
    assert toast._timer.isActive() is True
    assert toast._timer.interval() >= RESUME_MS


def test_the_toast_counts_the_pointer_over_its_card_on_a_page_that_does_not_track_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    under = window.centralWidget()
    assert not under.hasMouseTracking()
    toast = window.toast
    toast.show_message("Placed 1 homework block.", "Undo", lambda: None)
    settled(qapp, window)
    point = toast.card.mapToGlobal(toast.card.rect().center())
    QCursor.setPos(point)
    toast._poll_state()
    assert toast._over_point(point)
    assert toast._pointer


@pytest.mark.parametrize(
    ("which", "unavailable"),
    [("visible", False), ("minimized", True), ("active", False)],
    ids=["hidden", "minimized", "inactive"],
)
def test_the_toast_holds_its_remaining_time_while_the_window_is_unavailable(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, which: str, unavailable: bool
) -> None:
    state = {"visible": True, "minimized": False, "active": True}
    monkeypatch.setattr(window, "isVisible", lambda: state["visible"])
    monkeypatch.setattr(window, "isMinimized", lambda: state["minimized"])
    monkeypatch.setattr(window, "isActiveWindow", lambda: state["active"])
    toast = window.toast
    toast.show_message("Placed 1 homework block.", "Undo", lambda: None)
    toast._pointer = False
    toast._sync_pause()
    left = toast._left_ms()
    state[which] = unavailable
    toast._sync_pause()
    # Held: the time left is kept and the timer that would use it up is stopped.
    assert toast._paused and abs(toast._held_ms - left) <= 50
    assert not toast._timer.isActive()
    assert toast._left_ms() == toast._held_ms
    state[which] = not unavailable
    toast._sync_pause()
    assert not toast._paused and toast._timer.isActive() and toast._timer.remainingTime() >= left - 250


def test_the_toast_announces_once_and_politely(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    announcements = []
    monkeypatch.setattr(
        "desktop.native.widgets.announce",
        lambda widget, words, *, assertive=False: announcements.append((widget, words, assertive)),
    )
    window.toast.show_message("Placed 1 homework block.", "Undo", lambda: None)
    assert announcements == [(window.toast, "Placed 1 homework block.", False)]


def test_the_progress_line_is_hidden_when_animations_are_reduced_or_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    planned(qapp, window)
    bar = window.toast.findChild(QWidget, "toastProgress")
    assert bar is not None and bar.isVisible()
    window.toast.motion = "off"
    window.toast.sync_progress()
    assert bar.isVisible() is False
    window.toast.motion = "reduce"
    window.toast.sync_progress()
    assert bar.isVisible() is False


def test_a_repeat_does_not_fade_the_card_when_animations_are_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    planned(qapp, window)
    window.toast.motion = "off"
    window.toast.bump()
    assert window.toast.graphicsEffect() is None
    window.toast.motion = "normal"
    window.toast.bump()
    assert window.toast.graphicsEffect() is not None


@pytest.mark.parametrize("motion", ["reduce", "off"])
def test_the_undo_countdown_keeps_its_accessible_name_and_decreases(
    qapp: QApplication, window: NativeWindow, motion: str
) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "motion": motion}
    window._apply_appearance()
    # The toast counts on the test's clock, which the test moves, instead of a timer that runs.
    window.toast.clock_ms = CLOCK.now_ms
    planned(qapp, window)
    # The toast pauses its countdown while the window is not the active one; adding homework
    # takes focus away, so the window is made active again before the countdown is read.
    window.activateWindow()
    wait_until(qapp, window.isActiveWindow)
    initial = re.fullmatch(SAYS_SECONDS, window.toast.button.text())
    assert initial
    assert window.toast.button.accessibleName() == "Undo"
    assert not window.toast._progress.isVisible()
    CLOCK.move(seconds=3)
    window.toast.sync_progress()
    remaining = re.fullmatch(SAYS_SECONDS, window.toast.button.text())
    assert remaining and int(remaining.group(1)) < int(initial.group(1))
    assert window.toast.button.accessibleName() == "Undo"
