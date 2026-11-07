"""A button with words never has a fixed or largest width, so its row wraps when it runs out of room
instead of cutting the label. (Whether a label fits is a picture: pictures/screens_sheets_h9.py.)"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_button_labels import dress, each_screen, exempt, visible_buttons
from desktop.tests.window_support import qapp  # noqa: F401

QT_NO_LIMIT = 16777215


@pytest.mark.parametrize("size", ["normal", "large"])
def test_no_button_with_words_has_a_fixed_or_largest_width(qapp, window, size) -> None:
    dress(qapp, window, "classic", "default", size)
    held = []
    for screen, root in each_screen(qapp, window):
        for button in visible_buttons(root):
            if not exempt(button) and button.maximumWidth() < QT_NO_LIMIT:
                held.append(f"{screen}: {button.text()!r} max {button.maximumWidth()}")
    assert held == []
