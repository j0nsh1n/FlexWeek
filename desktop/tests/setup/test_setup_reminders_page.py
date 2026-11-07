"""Setup's Reminders page: Play is an icon button that says what it does."""

# ruff: noqa: F811  (a test's fixture parameter has the name of the imported fixture)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.setup import REMINDERS
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.setup.support_setup_page import show_setup
from desktop.tests.window_support import qapp  # noqa: F401


def test_play_is_an_icon_button_with_a_tooltip(qapp: QApplication, window: NativeWindow) -> None:
    setup = show_setup(qapp, window, REMINDERS)
    assert setup.play_buttons
    for play in setup.play_buttons:
        assert play.text() == "" and play.toolTip() == "Play"
        assert not play.icon().isNull()
