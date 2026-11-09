"""The toast and the menus in every look: a dark toast with light words, Undo in the accent's light shade
on a light look, a hovered row that differs from its card, and a menu's shadow. Whether their words
read and where a menu opens are judged on the pictures in pictures/screens_settings_h2.py.
"""

from __future__ import annotations

from itertools import product

from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QLabel, QMenu, QWidget

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
from desktop.native.menus import Menu, menu_colours
from desktop.native.tokens import SHADOW_LARGE
from desktop.native.widgets import add_heading, control_art
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


def test_a_menu_casts_the_large_shadow_only_in_a_look_with_depth(qapp: QApplication) -> None:  # noqa: F811
    light = resolved_palette("light-frost", False, None)
    menu = Menu()
    menu.set_colours(menu_colours(light, lifted=True))
    shadow = menu.graphicsEffect()
    assert isinstance(shadow, QGraphicsDropShadowEffect)
    assert (shadow.offset().y(), shadow.blurRadius()) == (SHADOW_LARGE.y, SHADOW_LARGE.blur)
    inner = menu.add_menu("Undo, copy and save", "pencil")
    assert isinstance(inner.graphicsEffect(), QGraphicsDropShadowEffect), "a submenu too"
    menu.set_colours(menu_colours(light, lifted=False))
    assert not shadow_drawn(menu) and not shadow_drawn(inner)


def test_clearing_a_menu_shadow_keeps_the_effect_across_windows_and_palettes(
    qapp: QApplication,  # noqa: F811
) -> None:
    """Deleting a drop shadow aborts in Shiboken when another window already lifted a menu."""
    looks = (
        resolved_palette("light-frost", False, None),
        resolved_palette("dark-frost", True, None),
        resolved_palette("light-frost", False, {"preset": "high-contrast"}),
    )
    first = QWidget()
    second = QWidget()
    first.resize(240, 160)
    second.resize(240, 160)
    first.show()
    second.show()
    qapp.processEvents()
    menus = [Menu(first), Menu(second)]
    try:
        for palette in looks:
            lifted = menu_colours(palette, lifted=True)
            flat = menu_colours(palette, lifted=False)
            for menu in menus:
                menu.set_colours(lifted)
                held = menu.graphicsEffect()
                assert isinstance(held, QGraphicsDropShadowEffect)
                assert shadow_drawn(menu)
                inner = next((action.menu() for action in menu.actions() if action.menu()), None)
                if inner is None:
                    inner = menu.add_menu("Undo, copy and save", "pencil")
                inner_held = inner.graphicsEffect()
                menu.set_colours(flat)
                assert menu.graphicsEffect() is held
                assert inner.graphicsEffect() is inner_held
                assert not shadow_drawn(menu)
                assert not shadow_drawn(inner)
                menu.set_colours(lifted)
                assert menu.graphicsEffect() is held
                assert inner.graphicsEffect() is inner_held
                assert shadow_drawn(menu)
                assert shadow_drawn(inner)
    finally:
        first.hide()
        second.hide()


def test_a_menu_heading_is_drawn_as_text(qapp: QApplication) -> None:  # noqa: F811
    """Fusion drew `addSection` as a plain line, so More never showed Adding or Planning."""
    palette = resolved_palette("light-frost", False, None)
    page = QWidget()
    page.setStyleSheet(pack_stylesheet("light-frost", False, None, "default", palette, control_art(palette)))
    menu = QMenu(page)
    add_heading(menu, "Adding")
    menu.addAction("Add homework")
    menu.popup(page.mapToGlobal(page.rect().center()))
    for _ in range(5):
        qapp.processEvents()
    heading = menu.findChild(QLabel, "menuHeading")
    assert heading is not None and heading.text() == "Adding"
    assert heading.isVisible()
    menu.hide()
    page.close()
