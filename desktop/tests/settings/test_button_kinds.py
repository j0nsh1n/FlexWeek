"""The `outlined`, `danger` and `tonal` buttons and a disabled main button are written as the rules
the app promises in every shipped look. Whether their words and edges read (4.5 to 1, 3 to 1, about
7 to 1) is judged on the pictures in pictures/screens_settings_h2.py.
"""

from __future__ import annotations

import re
from functools import cache
from itertools import product

from desktop.native.look import ACCENTS, LOOK_KNOBS, LOOK_PRESETS, PACKS, pack_stylesheet, resolved_palette

EVERY_LOOK = list(product(PACKS, (False, True), LOOK_PRESETS, ACCENTS, LOOK_KNOBS["surface"]))


def rule(sheet: str, selector: str) -> dict[str, str]:
    """The declarations of the rule written for exactly `selector`; a missing rule is the failure."""
    found = re.search(r"(?:^|\})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", sheet)
    assert found is not None, f"no rule for {selector}"
    pairs = (part.split(":", 1) for part in found.group(1).split(";") if ":" in part)
    return {name.strip(): value.strip() for name, value in pairs}


@cache
def look_of(pack: str, dark: bool, preset: str, accent: str, surface: str) -> tuple[dict, dict, str]:
    look = {"preset": preset, "knobs": {"surface": surface}}
    palette = resolved_palette(pack, dark, look, accent)
    return palette, look, pack_stylesheet(pack, dark, look, accent, palette)


def test_a_tonal_buttons_tint_is_the_accent_and_not_the_card() -> None:
    palette, _look, sheet = look_of("light-frost", False, "default", "default", "flat")
    tonal = rule(sheet, 'QPushButton[tonal="true"]')
    assert tonal["background"] != palette["panel"]


def test_every_look_writes_a_tonal_rule() -> None:
    for look in EVERY_LOOK:
        _palette, _knobs, sheet = look_of(*look)
        assert {"color", "background"} <= set(rule(sheet, 'QPushButton[tonal="true"]')), look


def test_an_outlined_button_is_a_one_pixel_edge_round_transparent_text_colour_in_every_look() -> None:
    for look in EVERY_LOOK:
        palette, _knobs, sheet = look_of(*look)
        outlined = rule(sheet, 'QPushButton[outlined="true"]')
        assert outlined["background"] == "transparent" and outlined["border"].startswith("1px solid "), look
        assert outlined["color"] == palette["text"], look


def test_a_danger_outline_is_words_and_edge_in_the_error_colour_in_every_look() -> None:
    for look in EVERY_LOOK:
        palette, _knobs, sheet = look_of(*look)
        danger = rule(sheet, 'QPushButton[outlined="true"][danger="true"]')
        assert danger["color"] == palette["error"] == danger["border-color"], look


def test_a_disabled_main_button_is_the_text_colour_on_a_fill_in_a_plain_page_and_a_dialog_alike() -> None:
    """The label is the text colour, not white on a pale accent (#91 was 1.82 to 1)."""
    for look in EVERY_LOOK:
        palette, _knobs, sheet = look_of(*look)
        for selector in ("QPushButton:disabled", "QDialog QPushButton:disabled"):
            off = rule(sheet, selector)
            assert off["color"] == palette["text"], (look, selector)
            assert off["background"], (look, selector)
