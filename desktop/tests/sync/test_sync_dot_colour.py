# ruff: noqa: F811
"""The sync dot's problem colour is the error colour of the look the window wears."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


from desktop.native import devices  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.window_support import qapp  # noqa: E402, F401


def test_the_window_hands_the_dot_the_error_colour_of_the_look_it_wears(qapp, window: NativeWindow) -> None:
    window._look = {"preset": "default", "knobs": {}}
    window.session.preferences = {**(window.session.preferences or {}), "theme_pack": "light-frost"}
    window._dressed = None
    window._apply_appearance()
    assert devices._error_colour == resolved_palette("light-frost", False, None)["error"]
