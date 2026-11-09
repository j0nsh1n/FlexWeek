"""What the focus screen's buttons do to the one timer, and what its ring and countdown read."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.focus import format_countdown, phase_duration_ms
from desktop.native.window import NativeWindow
from desktop.tests.focus.support_focus_screen import (  # noqa: F401
    LEFT,
    end_sheet_answer,
    focus_window,
    on_screen,
    quick_focus,
    settled,
    visible_buttons,
)
from desktop.tests.window_support import qapp  # noqa: F401


def test_pause_skip_and_finish_act_on_the_one_timer(
    qapp: QApplication, focus_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = focus_window
    quick_focus(window)
    screen = window.focus_screen
    QTest.mouseClick(screen.pause, LEFT)
    assert window.session.focus["running"] is False
    assert screen.pause.text() == "Resume"
    assert screen.phase.text() == "Focus · Paused"
    assert window.focus_panel.phase.text() == "Focus session", "the strip shows the same timer"
    QTest.mouseClick(screen.pause, LEFT)
    assert window.session.focus["running"] is True
    QTest.mouseClick(screen.skip, LEFT)
    assert window.session.focus["phase"] == "break"
    assert screen.phase.text() == "Break"
    assert screen.time_text() == format_countdown(phase_duration_ms("break", window.session.preferences))
    end_sheet_answer(monkeypatch, window, "yes")
    assert window.session.focus is None
    assert on_screen(window) == "weekPage"


def test_a_finished_session_offers_finished_and_a_break(
    qapp: QApplication, focus_window: NativeWindow
) -> None:
    window = focus_window
    session = window.session
    essay = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    window._start_focus(essay["id"], 3)
    assert on_screen(window) == "focusPage"
    CLOCK.set_ms(session.now_ms() + phase_duration_ms("work", session.preferences) + 1000)
    session.tick_focus()
    settled(qapp, window)
    screen = window.focus_screen
    assert session.focus["phase"] == "ended"
    assert screen.phase.text() == "Session finished"
    assert screen.ring.left() == 0.0, "a finished session has no ring left"
    assert visible_buttons(screen) == ["Back", "Finished", "Take a break"]
    QTest.mouseClick(screen.finished, LEFT)
    settled(qapp, window)
    assert session.assignments["essay"]["completed"] is True
    essay = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    assert (essay["completed"], essay["completed_day"], essay["start"]) == (True, 3, "19:00")
    assert session.focus is None
    assert on_screen(window) == "weekPage"


def test_the_ring_counts_down_with_the_timer(qapp: QApplication, focus_window: NativeWindow) -> None:
    window = focus_window
    quick_focus(window)
    session = window.session
    whole = phase_duration_ms("work", session.preferences)
    started = session.now_ms()
    CLOCK.set_ms(started + whole // 4)
    session.tick_focus()
    screen = window.focus_screen
    assert screen.ring.left() == pytest.approx(0.75, abs=0.01)
    assert screen.time_text() == format_countdown(whole * 3 // 4)
