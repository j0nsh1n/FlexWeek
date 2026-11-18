# ruff: noqa: F811
"""The Open on preference the window obeys: where the app opens, and only once."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    window,  # noqa: F401
)


def test_open_on_day_is_honoured_instead_of_always_coming_up_on_the_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The setting could be saved from the desktop but only the web read it."""
    window._day_mode = False
    window._opened_on_preference = False
    window.session.preferences = {**(window.session.preferences or {}), "preferred_view": "day"}
    window._on_week()
    qapp.processEvents()
    assert window._day_mode is True


def test_open_on_is_a_starting_point_not_a_lock(qapp: QApplication, window: NativeWindow) -> None:
    """Every week refresh runs through the same path, so applying it more than once would drag the
    student back to the day screen whenever the week reloaded."""
    window._day_mode = False
    window._opened_on_preference = False
    window.session.preferences = {**(window.session.preferences or {}), "preferred_view": "day"}
    window._on_week()
    qapp.processEvents()
    window._leave_day()
    qapp.processEvents()
    assert window._day_mode is False
    window._on_week()
    qapp.processEvents()
    assert window._day_mode is False
