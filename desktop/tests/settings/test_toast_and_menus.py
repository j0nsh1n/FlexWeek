"""The toast and the menus in every look: a dark toast with light words, Undo in the accent's light shade
on a light look, a hovered row that differs from its card, and a menu's shadow. Whether their words
read and where a menu opens are judged on the pictures in pictures/screens_settings_h2.py.
"""

from __future__ import annotations

from itertools import product

from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from desktop.native.look import (
    ACCENTS,
    LOOK_KNOBS,
    LOOK_PRESETS,
    PACKS,
    hover_tint,
    luminance,
    pack_stylesheet,
    resolved_palette,
    toast_colours,
)
from desktop.tests.window_support import qapp  # noqa: F401

EVERY_LOOK = list(product(PACKS, (False, True), LOOK_PRESETS, ACCENTS, LOOK_KNOBS["surface"]))


def palette_of(pack: str, dark: bool, preset: str, accent: str, surface: str) -> dict:
    return resolved_palette(pack, dark, {"preset": preset, "knobs": {"surface": surface}}, accent)


def test_the_toast_is_dark_with_light_words_in_every_look() -> None:
    failed = []
    for look in EVERY_LOOK:
        toast = toast_colours(palette_of(*look))
        if not luminance(toast["background"]) < luminance(toast["text"]):
            failed.append(look)
    assert failed == []


def test_undo_is_the_accents_light_shade_on_a_light_look_and_the_accent_on_a_dark_one() -> None:
    light = resolved_palette("light-frost", False, None)
    toast = toast_colours(light)
    assert toast["background"] == light["text"] and toast["text"] == light["window"]
    assert toast["action"] != light["accent"]
    assert luminance(toast["action"]) > luminance(light["accent"]), "lighter than the accent"
    dark = resolved_palette("dark-frost", True, None)
    assert toast_colours(dark)["action"] == dark["accent"]
    sheet = pack_stylesheet("light-frost", False, None)
    rule = sheet.split("QFrame#toast {")[1].split("}")[0]
    assert f"background: {light['text']};" in rule and "border-radius: 16px;" in rule


def test_a_row_under_the_pointer_differs_from_its_card_in_every_look() -> None:
    failed = []
    for look in EVERY_LOOK:
        palette = palette_of(*look)
        if hover_tint(palette) == palette["panel"]:
            failed.append(look)
    assert failed == []


def shadow_drawn(widget: QWidget) -> bool:
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsDropShadowEffect):
        return False
    return bool(effect.isEnabled() and effect.blurRadius() > 0 and effect.color().alpha() > 0)






