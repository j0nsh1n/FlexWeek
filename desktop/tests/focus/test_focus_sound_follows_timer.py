"""The focus sound plays while the timer works, pauses with the timer and in the break, and stops when
the session ends."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.focus.support_focus_screen import (  # noqa: F401
    material_focus_window,
    rules,
)
from desktop.tests.window_support import qapp  # noqa: F401


def test_pause_and_break_hold_ambient_sound_and_finish_stops_it(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    with rules(window, focus_audio="white-noise"):
        player = window._focus_audio.player
        assert window.session.start_quick_focus()
        assert player.state == "playing" and player.kind == "white-noise"
        window.session.toggle_focus_pause()
        assert player.state == "paused"
        window.session.toggle_focus_pause()
        assert player.state == "playing"
        window.session.advance_focus(False)
        assert window.session.focus["phase"] == "break"
        assert player.state == "paused"
        window.session.reset_focus()
        assert player.state == "stopped"
