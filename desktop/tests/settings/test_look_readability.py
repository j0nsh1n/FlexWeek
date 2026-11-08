"""Every look a student can reach keeps its text readable and its lines visible.

The palettes began as the retired web client's CSS custom properties, which had already passed its
readability and accent-distance audits. That client is gone, so what is checked here is the property
the audit was for: in every look, text reads at 4.5 to 1 and the lines and rings that are not text at
3 to 1. These check the colours the code works out (the palette table and the rules built from it);
how a look is drawn is in the settings pictures.
"""

from __future__ import annotations

import re
from itertools import product
from math import dist

import pytest

from desktop.native.calendar import CATEGORIES
from desktop.native.look import (
    AA_GRAPHIC,
    AA_TEXT,
    ACCENTS,
    DESIGN_PALETTE_PRESETS,
    EXPERIMENTAL_LOOKS,
    LOOK_DEFAULTS,
    LOOK_KNOBS,
    LOOK_PRESETS,
    PACKS,
    STANDARD_LOOKS,
    accent_words,
    auth_rules,
    block_paint,
    block_time_colour,
    category_paint,
    class_outline,
    contrast,
    control_rules,
    effective_look,
    pack_stylesheet,
    readable_edge,
    readable_focus_edge,
    readable_ink,
    resolved_palette,
    sanitize_look,
    settings_rules,
    setup_rules,
    switch_track_edge,
)
from desktop.native.look_editor import editor_rules
from desktop.native.tokens import SINK, mix, mix_oklab, oklab
from desktop.tests.settings.support_look import _lab, look_of

# Every look a student can reach: pack, the device's light or dark setting, preset, accent, surface.
EVERY_LOOK = list(product(PACKS, (False, True), LOOK_PRESETS, ACCENTS, LOOK_KNOBS["surface"]))

# Every pair of window colours the app puts text on.
TEXT_PAIRS = [
    ("text", "window"),
    ("text", "panel"),
    ("text", "field"),
    ("text", "grid"),
    ("muted", "window"),
    ("muted", "panel"),
    ("error", "panel"),
    ("accent_ink", "accent"),
    ("block_locked_ink", "block_locked"),
    ("block_flex_ink", "block_flex"),
]

SWITCH_ART = {
    "tick": "tick",
    "down": "down",
    "up": "up",
    "switch_off": "off",
    "switch_on": "on",
    "switch_off_off": "off-disabled",
    "switch_on_off": "on-disabled",
}


@pytest.mark.parametrize("preset", LOOK_PRESETS)
@pytest.mark.parametrize("system_dark", [False, True], ids=["light", "dark"])
def test_control_edges_have_three_to_one_contrast(preset: str, system_dark: bool) -> None:
    palette = resolved_palette("slate", system_dark, look_of(preset))
    grounds = (palette["field"], palette["panel"])
    border = readable_edge(palette)
    focus = readable_focus_edge(palette)
    switch_edge = switch_track_edge(palette)
    assert min(contrast(border, ground) for ground in grounds) >= 3
    assert min(contrast(focus, ground) for ground in grounds) >= 3
    auth = auth_rules(palette, {**LOOK_DEFAULTS, "depth": "soft"}, 6, 10)
    assert f"QWidget#authCard QLineEdit:focus {{ border: 2px solid {focus}; }}" in auth
    assert f"QToolButton#passwordReveal:focus {{ border: 2px solid {focus}; }}" in auth
    assert contrast(focus, palette["field"]) >= AA_GRAPHIC
    if preset != "high-contrast":
        assert min(contrast(focus, ground) for ground in grounds) > min(
            contrast(border, ground) for ground in grounds
        )
    assert f"border: 1px solid {border}" in pack_stylesheet("slate", system_dark, look_of(preset))
    assert f"border: 1px solid {border}" in settings_rules(palette, 6, "normal", 8, "soft")
    controls = control_rules(palette, 6, "normal", SWITCH_ART)
    assert (
        f'QPushButton[step="true"] {{ background: {palette["window"]}; color: {palette["muted"]}; '
        f'border: 1px solid {border}; padding: 0; min-width: 34px; max-width: 34px; min-height: 0; }}'
    ) in controls
    assert f"border: 2px solid {focus}" in controls
    switch_grounds = (palette["field"], palette["panel"], palette["window"])
    assert min(contrast(switch_edge, ground) for ground in switch_grounds) >= 3


def test_the_default_focus_edge_stays_the_accent_that_already_reads() -> None:
    palette = resolved_palette("system", False, None)
    assert palette["accent"] == "#3d6fc4"
    assert accent_words(palette) == palette["accent"]
    assert readable_focus_edge(palette) == palette["accent"]
    auth = auth_rules(palette, {**LOOK_DEFAULTS, "depth": "soft"}, 6, 10)
    assert f"QWidget#authCard QLineEdit:focus {{ border: 2px solid {palette['accent']}; }}" in auth


def test_a_pale_typed_accent_focus_ring_is_fitted_not_raw() -> None:
    look = {"custom": {"name": "Lime", "base": "light", "accent": "#dfff00"}}
    palette = resolved_palette("system", False, look)
    assert palette["accent"] == "#dfff00"
    words = accent_words(palette)
    focus = readable_focus_edge(palette)
    assert words != palette["accent"]
    assert focus != palette["accent"]
    for ground in ("window", "panel", "grid"):
        assert contrast(words, palette[ground]) >= AA_TEXT, (words, ground)
    grounds = (palette["field"], palette["panel"])
    assert min(contrast(focus, ground) for ground in grounds) >= AA_GRAPHIC
    auth = auth_rules(palette, {**LOOK_DEFAULTS, "depth": "soft"}, 6, 10)
    assert f"QWidget#authCard QLineEdit:focus {{ border: 2px solid {focus}; }}" in auth
    assert f"QWidget#authCard QLineEdit:focus {{ border: 2px solid {palette['accent']}; }}" not in auth


def test_control_edges_and_focus_rings_hold_in_every_pack_preset_and_system_mode() -> None:
    for pack, preset, system_dark in product(PACKS, LOOK_PRESETS, (False, True)):
        look = look_of(preset)
        palette = resolved_palette(pack, system_dark, look)
        field, card = palette["field"], palette["panel"]
        resting, focus = readable_edge(palette), readable_focus_edge(palette)
        case = f"{pack}/{preset}/{'dark' if system_dark else 'light'}"
        assert min(contrast(resting, ground) for ground in (field, card)) >= AA_GRAPHIC, case
        assert min(contrast(focus, ground) for ground in (field, card)) >= AA_GRAPHIC, case
        if preset != "high-contrast":
            assert min(contrast(focus, ground) for ground in (field, card)) > min(
                contrast(resting, ground) for ground in (field, card)
            ), case

        sheet = pack_stylesheet(pack, system_dark, look, art=SWITCH_ART)
        setup = setup_rules(palette, 8, "normal", 8, effective_look(look)["depth"])
        assert f"border: 1px solid {resting}" in sheet, case
        assert f"border: 2px solid {focus}" in sheet, case
        assert f"border: 1px solid {resting}" in setup, case
        assert f"border: 2px solid {focus}; padding: 3px 11px" in setup, case
        assert f"{focus}" in setup and 'QPushButton[pill="true"]:focus' in setup, case
        assert "QPushButton#setupChip:focus" in setup and "QPushButton#setupStudyChip:focus" in setup, case
        assert f"border-color: {palette['accent']}" in setup, case


def test_every_look_keeps_its_text_readable() -> None:
    assert len(EVERY_LOOK) == 5 * 2 * 7 * 5 * 2
    for pack, system_dark, preset, accent, surface in EVERY_LOOK:
        palette = resolved_palette(pack, system_dark, look_of(preset, surface=surface), accent)
        for ink, fill in TEXT_PAIRS:
            ratio = contrast(palette[ink], palette[fill])
            where = f"{pack}/{'dark' if system_dark else 'light'}/{preset}/{accent}/{surface}"
            assert ratio >= AA_TEXT, f"{where}: {ink} on {fill} is {ratio:.2f} to 1"


def test_every_design_palette_preset_keeps_its_text_readable() -> None:
    for preset, accent in product(DESIGN_PALETTE_PRESETS, ACCENTS):
        palette = resolved_palette("light-frost", False, None, accent, palette_preset=preset)
        for ink, fill in TEXT_PAIRS:
            ratio = contrast(palette[ink], palette[fill])
            assert ratio >= AA_TEXT, f"{preset}/{accent}: {ink} on {fill} is {ratio:.2f} to 1"
        assert dist(_lab(palette["accent"]), _lab(palette["error"])) >= 25, (preset, accent)


def test_the_now_line_and_the_selection_ring_show_at_3_to_1_and_keep_the_accent() -> None:
    """They are lines, not text: the bar for a graphic is 3 to 1, not 4.5. In every look the shade is
    at least 3 to 1 on every category's fill and on the grid, and is the accent or only as far from
    it as that takes; in Light, where the blue asked for 4.5 and went to #2153a4, it stays the blue.
    The time on the pill at its start is text and keeps 4.5."""
    for pack, system_dark, preset, accent, surface in EVERY_LOOK:
        palette = resolved_palette(pack, system_dark, look_of(preset, surface=surface), accent)
        where = f"{pack}/{'dark' if system_dark else 'light'}/{preset}/{accent}/{surface}"
        grounds = [category_paint(key, palette)[0] for key in CATEGORIES] + [palette["grid"]]
        lowest = min(contrast(palette["now"], ground) for ground in grounds)
        assert lowest >= AA_GRAPHIC, f"{where}: {lowest:.2f} to 1"
        assert palette["selection"] == palette["now"], where
        if palette["now"] != palette["accent"]:
            assert lowest < AA_GRAPHIC + 0.05, f"{where}: moved to {lowest:.2f} to 1, past the 3 it needs"
        pill = contrast(readable_ink(palette["now"]), palette["now"])
        assert pill >= AA_TEXT, f"{where}: the time on the pill is {pill:.2f} to 1"
    blue = resolved_palette("light-frost", False, look_of("default"))
    assert dist(oklab(blue["accent"]), oklab(blue["now"])) < 0.02


@pytest.mark.parametrize(("kind", "name"), STANDARD_LOOKS + EXPERIMENTAL_LOOKS)
def test_homework_outline_is_class_colour_not_error_red(kind: str, name: str) -> None:
    """U5: homework's outline is the class colour at 3:1 on the card, never the error red."""
    if kind == "pack":
        palette = resolved_palette(name, name in {"dark-frost", "nocturne"}, None)
        look = look_of("default", blocks="outline")
    else:
        look = look_of(name, blocks="outline")
        palette = resolved_palette("system", False, look)
    fill, mark = category_paint("assignments", palette)
    paint = block_paint(look, palette, fill, "flexible", mark, category="assignments")
    outline, card = paint["outline"], paint["fill"]
    assert outline
    assert outline.lower() not in {palette["error"].lower(), "#831a1d"}
    assert contrast(outline, card) >= AA_GRAPHIC
    assert class_outline(palette, fill) == outline


@pytest.mark.parametrize(("kind", "name"), STANDARD_LOOKS + EXPERIMENTAL_LOOKS)
def test_plan_button_label_reads_with_margin_in_every_look(kind: str, name: str) -> None:
    """U6: Plan's secondary label is 4.6:1 on its 10% accent tint; High contrast is on the window."""
    if kind == "pack":
        palette = resolved_palette(name, name in {"dark-frost", "nocturne"}, None)
    else:
        palette = resolved_palette("system", False, look_of(name))
    tint = mix(palette["accent"], palette["window"], 0.10)
    ground = palette["window"] if palette.get("family") == "contrast" else tint
    assert contrast(palette["accent_text"], ground) >= AA_TEXT + 0.1, name


def test_a_filled_block_is_readable_on_every_category_colour() -> None:
    assert len(CATEGORIES) == 8
    for name, category in CATEGORIES.items():
        color = category["color"]
        ratio = contrast(readable_ink(color), color)
        assert ratio >= AA_TEXT, f"{name} {color}: best ink is only {ratio:.2f} to 1"


@pytest.mark.parametrize(("kind", "name"), STANDARD_LOOKS + EXPERIMENTAL_LOOKS)
def test_block_time_line_reads_with_margin_in_every_look(kind: str, name: str) -> None:
    """U7: a block's time line is 4.6:1 on its fill, so Terminal, Ink and Nocturne keep a margin."""
    if kind == "pack":
        palette = resolved_palette(name, name in {"dark-frost", "nocturne"}, None)
        look = look_of("default")
    else:
        look = look_of(name)
        palette = resolved_palette("system", False, look)
    for category_name, category in CATEGORIES.items():
        fill, mark = category_paint(category_name, palette)
        drawn = block_paint(look, palette, fill, category["kind"], mark)
        paper = drawn["fill"] or palette["window"]
        ratio = contrast(block_time_colour(drawn["ink"], paper), paper)
        assert ratio >= AA_TEXT + 0.1, f"{name} {category_name}: {ratio:.2f}"


def test_a_blocks_times_read_in_every_look_and_block_style() -> None:
    """Times and length are drawn quieter than the title, but Terminal's read at 3.95 to 1: they give
    up quiet before they give up 4.5 to 1."""
    for pack, system_dark, preset, accent, surface in EVERY_LOOK:
        palette = resolved_palette(pack, system_dark, look_of(preset, surface=surface), accent)
        for blocks, (name, category) in product(LOOK_KNOBS["blocks"], CATEGORIES.items()):
            fill, mark = category_paint(name, palette)
            drawn = block_paint(look_of(preset, blocks=blocks), palette, fill, category["kind"], mark)
            paper = drawn["fill"] or palette["window"]
            ratio = contrast(block_time_colour(drawn["ink"], paper), paper)
            where = f"{pack}/{system_dark}/{preset}/{accent}/{surface}/{blocks} {name}"
            assert ratio >= AA_TEXT, f"{where}: {ratio:.2f}"


def test_a_blocks_times_stay_quieter_than_its_title_where_they_can() -> None:
    palette = resolved_palette("system", False, look_of("default"), "default")
    fill, mark = category_paint("study", palette)
    drawn = block_paint(look_of("default"), palette, fill, CATEGORIES["study"]["kind"], mark)
    times = block_time_colour(drawn["ink"], drawn["fill"])
    assert contrast(times, drawn["fill"]) < contrast(drawn["ink"], drawn["fill"])


def test_a_filled_block_on_a_dark_look_is_its_colour_sunk_into_the_panel_with_light_ink() -> None:
    """A pale fill on near-black glared off the page. Every dark look, packs and presets, fills a
    block with the category's tone mixed into its panel, and writes on it in its own light text."""
    seen = 0
    for pack, system_dark, preset, accent, surface in EVERY_LOOK:
        palette = resolved_palette(pack, system_dark, look_of(preset, surface=surface), accent)
        if palette["axis"] != "dark":
            continue
        seen += 1
        filled = look_of(preset, blocks="filled")
        for name, category in CATEGORIES.items():
            fill, mark = category_paint(name, palette)
            drawn = block_paint(filled, palette, fill, "locked", mark)
            where = f"{pack}/{preset}/{surface} {name}"
            tone = category[palette["family"]][0]
            assert drawn["fill"] == mix_oklab(tone, palette["panel"], SINK), where
            assert drawn["ink"] == palette["text"], where
            assert contrast(drawn["ink"], drawn["fill"]) >= AA_TEXT, where
    assert seen


CHIP_PRESETS = ("default", "paper", "ink", "pastel", "terminal", "poster", "high-contrast")
# A pale accent is the case where the plain accent cannot be words on its own tint.
CHIP_ACCENTS = ("default", "gold", "sand", "#dfff00", "#809dce")


def chip_colours(css: str) -> tuple[str, str]:
    rule = re.search(r"QLabel#lookTag \{ background: (#[0-9a-f]{6}|transparent); color: (#[0-9a-f]{6});", css)
    assert rule, "the editor's rules have no Changed chip"
    return rule.group(1), rule.group(2)


@pytest.mark.parametrize("accent", CHIP_ACCENTS)
@pytest.mark.parametrize("pack", ["light-frost", "dark-frost"])
def test_the_changed_chip_reads_at_4_5_to_1_on_its_tint(pack: str, accent: str) -> None:
    palette = resolved_palette(pack, False, None, accent)
    tint, words = chip_colours(editor_rules(palette, 6))
    assert contrast(words, tint) >= AA_TEXT, (pack, accent, words, tint)


@pytest.mark.parametrize("preset", CHIP_PRESETS)
def test_the_changed_chip_reads_in_every_look(preset: str) -> None:
    look = sanitize_look({"preset": preset})
    palette = resolved_palette("light-frost", False, look)
    tint, words = chip_colours(editor_rules(palette, 6))
    ground = palette["panel"] if tint == "transparent" else tint
    assert contrast(words, ground) >= AA_TEXT, (preset, words, ground)
