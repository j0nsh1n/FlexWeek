"""Finish on the focus screen asks before it ends the session, and says what the minutes done count for."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from backend.tests.fake_clock import CLOCK
from desktop.native.focus import phase_duration_ms
from desktop.native.window import NativeWindow
from desktop.tests.focus.support_focus_screen import (  # noqa: F401
    end_sheet_answer,
    focus_window,
    on_screen,
    quick_focus,
)
from desktop.tests.window_support import qapp  # noqa: F401


def test_finish_asks_first_and_keep_going_leaves_the_timer_running(
    qapp: QApplication, focus_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = focus_window
    quick_focus(window)
    seen = end_sheet_answer(monkeypatch, window, "stay")
    assert len(seen) == 1
    sheet = seen[0]
    assert "End this session?" in [label.text() for label in sheet.findChildren(QLabel)]
    assert sheet.question.text() == "You have done 0 min of Quick focus."
    assert sheet.buttons["stay"].text() == "Keep going"
    assert sheet.buttons["yes"].text() == "End session"
    assert window.session.focus is not None
    assert on_screen(window) == "focusPage"


def test_finish_ends_the_session_only_on_end_session(
    qapp: QApplication, focus_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = focus_window
    quick_focus(window)
    end_sheet_answer(monkeypatch, window, "yes")
    assert window.session.focus is None
    assert on_screen(window) == "weekPage"


def test_the_sheet_says_the_minutes_done_and_that_they_count_toward_the_homework(
    qapp: QApplication, focus_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = focus_window
    session = window.session
    essay = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    assert session.start_focus(essay["id"], 3)
    window._open_focus_screen()
    state = session.focus
    left = phase_duration_ms("work", session.preferences) - 7 * 60_000
    CLOCK.set_ms(int(state["endsAt"]) - left)
    seen = end_sheet_answer(monkeypatch, window, "stay")
    assert seen[0].question.text() == "You have done 7 min of History essay. It counts toward the homework."
