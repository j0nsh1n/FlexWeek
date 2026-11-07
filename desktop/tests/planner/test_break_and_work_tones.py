"""A quick focus session says when it moves into a break and when it goes back to work, each with its tone."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_moving_into_a_break_says_so_with_the_break_tone(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    """The web announces every phase change. Without this the end-of-session chime setting has
    nothing to fire on, because a quick focus session rolls straight into a break in silence."""
    session = window.session
    heard: list[dict] = []
    session.alerts.connect(lambda notices: heard.extend(notices))
    assert session.start_quick_focus() is True
    heard.clear()
    clock.move(minutes=30)
    session.tick_focus()
    wait_until(qapp, lambda: not session.busy)
    focus = [notice for notice in heard if notice.get("kind") == "focus"]
    assert focus, heard
    assert focus[0]["tone"] == "soft"
    assert session.focus is not None and session.focus["phase"] in ("break", "long_break")


def test_going_back_to_work_says_so_with_the_work_tone(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    session = window.session
    assert session.start_quick_focus() is True
    clock.move(minutes=30)
    session.tick_focus()
    wait_until(qapp, lambda: not session.busy)
    heard: list[dict] = []
    session.alerts.connect(lambda notices: heard.extend(notices))
    clock.move(minutes=60)
    session.tick_focus()
    wait_until(qapp, lambda: not session.busy)
    focus = [notice for notice in heard if notice.get("kind") == "focus"]
    assert focus, heard
    assert focus[0]["tone"] == "bright"
    assert session.focus is not None and session.focus["phase"] == "work"
