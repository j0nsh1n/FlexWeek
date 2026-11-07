"""Every text field's placeholder is written in a colour of the look's own, not Qt's default. That it
reads at 4.5 to 1 and is drawn in that colour is judged on the pictures in
pictures/screens_settings_h2.py."""

from __future__ import annotations

import re

import pytest

from desktop.native.look import pack_stylesheet, resolved_palette, sanitize_look

PRESETS = ("default", "paper", "ink", "pastel", "terminal", "poster", "high-contrast")


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("pack", ["light-frost", "dark-frost"])
def test_a_placeholder_has_a_colour_of_its_own_in_every_look(pack: str, preset: str) -> None:
    look = sanitize_look({"preset": preset})
    palette = resolved_palette(pack, False, look)
    css = pack_stylesheet(pack, False, look, "default", palette)
    rule = re.search(r"QLineEdit, QPlainTextEdit \{ placeholder-text-color: (#[0-9a-f]{6}); \}", css)
    assert rule is not None, (pack, preset)
