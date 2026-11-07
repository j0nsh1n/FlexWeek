"""The Week-as-a-list panel opens over the planner. That it is a 360 px overlay that does not crush the
planner is judged on the pictures in pictures/screens_settings_audit.py."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


def test_the_week_as_a_list_panel_opens(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    window.resize(1280, 800)
    window.show()
    qapp.processEvents()
    window._toggle_week_access_list()
    qapp.processEvents()
    assert window.week_list_panel.isVisible(), "drawer is open"
    window._close_week_access_list()
