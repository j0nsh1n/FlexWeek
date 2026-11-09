"""A timer length changed in Settings applies to the next phase, not the one running.

These run on the one fake clock: a focus session starts at its start, and the test moves the clock
the minutes it wants to have passed."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import essay, settled
from desktop.tests.window_support import qapp  # noqa: F401


def focusing_on_the_essay(qapp: QApplication, window: NativeWindow) -> NativeSession:
    """The essay on Monday 16:00, and a focus session started on its block at the clock's start."""
    session = window.session
    session.add_homework(essay(session))
    block = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    block["start"], block["days"] = "16:00", [0]
    session.save()
    settled(qapp, session)
    assert session.start_focus(block["id"], 0) is True
    return session


def finish_after(qapp: QApplication, session: NativeSession, minutes: int) -> None:
    CLOCK.move(minutes=minutes)
    session.tick_focus()
    settled(qapp, session)


def test_a_longer_work_timer_chosen_mid_session_does_not_inflate_the_credit(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = focusing_on_the_essay(qapp, window)
    session.preferences = {**session.preferences, "timer_work_min": 60}
    finish_after(qapp, session, 30)
    assert session.assignments["essay"]["focus_minutes"] == 30


def test_a_shorter_work_timer_chosen_mid_session_does_not_shrink_the_credit(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = focusing_on_the_essay(qapp, window)
    session.preferences = {**session.preferences, "timer_work_min": 15}
    finish_after(qapp, session, 30)
    assert session.assignments["essay"]["focus_minutes"] == 30


def test_the_minutes_shown_while_focusing_follow_the_running_session(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = focusing_on_the_essay(qapp, window)
    session.preferences = {**session.preferences, "timer_work_min": 60}
    CLOCK.move(minutes=10)
    assert session.focus_elapsed_min() == 10


def test_a_session_paused_and_resumed_keeps_its_length(qapp: QApplication, window: NativeWindow) -> None:
    session = focusing_on_the_essay(qapp, window)
    CLOCK.move(minutes=10)
    session.toggle_focus_pause()
    session.preferences = {**session.preferences, "timer_work_min": 60}
    session.toggle_focus_pause()
    CLOCK.move(minutes=20)
    session.tick_focus()
    settled(qapp, session)
    assert session.assignments["essay"]["focus_minutes"] == 30


def test_the_next_work_phase_uses_the_new_length(qapp: QApplication, window: NativeWindow) -> None:
    session = focusing_on_the_essay(qapp, window)
    session.preferences = {**session.preferences, "timer_work_min": 45}
    session.focus["phase"] = "break"
    session.advance_focus(completed=False)
    assert session.focus["phase"] == "work"
    CLOCK.move(minutes=45)
    session.tick_focus()
    settled(qapp, session)
    assert session.assignments["essay"]["focus_minutes"] == 45
