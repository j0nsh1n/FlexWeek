# ruff: noqa: F811
"""The week page around its hours: Today, the title, the keys that act, the clipboard line, the top bar
while the session is busy, and when the window is dressed again."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.layout_choice import sanitize_layout  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    window,  # noqa: F401
)


def test_a_change_to_the_week_does_not_restyle_the_window_when_the_look_is_the_same(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every change to the week re-dressed the whole window, about 26 ms a time, for nothing."""
    dressed: list[str] = []
    original = window.setStyleSheet
    window._layout = sanitize_layout(
        {**window._layout, "options": {**window._layout["options"], "classic": {"look": "your"}}}
    )
    window._apply_appearance()
    monkeypatch.setattr(window, "setStyleSheet", lambda sheet: (dressed.append(sheet), original(sheet)))
    window._on_week()
    window._on_week()
    assert dressed == []
    window.session.preferences = {**window.session.preferences, "theme_pack": "dark-frost"}
    window._on_week()
    assert len(dressed) == 1, "a new look is still put on at once"
