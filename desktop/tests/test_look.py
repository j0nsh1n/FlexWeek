"""Look knobs, presets and palettes. Device-only knobs never become preference fields.

Expected colours come from frontend/styles.css, where they already passed the web client's
readability and accent-distance audits; expected behaviour comes from the appearance contract.
"""

from __future__ import annotations

import re
from itertools import product
from pathlib import Path

from desktop.native.calendar import CATEGORIES
from desktop.native.look import (
    AA_TEXT,
    ACCENT_COLORS,
    ACCENTS,
    LOOK_DEFAULTS,
    LOOK_KNOBS,
    LOOK_PRESETS,
    PACKS,
    PALETTES,
    PRESET_PALETTES,
    block_paint,
    contrast,
    effective_look,
    look_menu_items,
    look_menu_token,
    look_menu_value,
    look_overrides,
    mix,
    pack_axis,
    pack_stylesheet,
    parse_look_menu_token,
    preset_knobs,
    readable_ink,
    resolved_pack_theme,
    resolved_palette,
    sanitize_look,
)

CSS = re.sub(r"/\*.*?\*/", "", (Path(__file__).parents[2] / "frontend/styles.css").read_text(), flags=re.S)
# Every look a student can reach: pack, the device's light or dark setting, preset, accent, surface.
EVERY_LOOK = list(product(PACKS, (False, True), LOOK_PRESETS, ACCENTS, LOOK_KNOBS["surface"]))


def web_tokens(selector: str) -> dict[str, str]:
    start = CSS.index(selector + " {")
    body = CSS[CSS.index("{", start) + 1 : CSS.index("}", start)]
    return {name: value.strip() for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", body)}


def look_of(preset: str, **knobs: str) -> dict:
    return {"preset": preset, "knobs": knobs}


def test_the_look_menu_lists_packs_then_device_presets() -> None:
    items = look_menu_items()
    assert [kind for _name, _label, kind in items[:5]] == ["pack"] * 5
    assert all(kind == "preset" for _name, _label, kind in items[5:])
    assert look_menu_value("nocturne", {"preset": "default", "knobs": {}}) == look_menu_token(
        "pack", "nocturne"
    )
    assert look_menu_value("nocturne", {"preset": "terminal", "knobs": {}}) == look_menu_token(
        "preset", "terminal"
    )
    assert parse_look_menu_token("preset:default") is None
    assert parse_look_menu_token("preset:terminal") == ("preset", "terminal")


def test_unknown_knobs_and_packs_fall_back() -> None:
    clean = sanitize_look({"preset": "neon", "knobs": {"font": "comic", "text": "large"}})
    assert clean["preset"] == "default"
    assert clean["knobs"] == {"text": "large"}
    assert effective_look(clean)["font"] == "sans"
    assert effective_look(clean)["text"] == "large"


def test_terminal_preset_layers_before_knob_overrides() -> None:
    effective = effective_look(sanitize_look(look_of("terminal", text="large")))
    assert effective["font"] == "mono"
    assert effective["corners"] == "sharp"
    assert effective["text"] == "large"


def test_pack_axis_pairs_frost_with_slate_or_nocturne() -> None:
    assert pack_axis("light-frost") == "slate"
    assert pack_axis("dark-frost") == "nocturne"
    assert pack_axis("system") == "system"
    assert resolved_pack_theme("system", True) == "nocturne"
    assert resolved_pack_theme("system", False) == "slate"
    assert resolved_pack_theme("slate", True) == "slate"


def test_every_knob_value_changes_what_is_drawn() -> None:
    """A control that stores a value nothing reads is a quiet click. Three of seven knobs once were."""
    palette = resolved_palette("nocturne", True, None)
    base_sheet = pack_stylesheet("nocturne", True, look_of("default"))
    base_block = block_paint(look_of("default"), palette, "#3b82f6")
    for knob, values in LOOK_KNOBS.items():
        for value in values:
            if value == LOOK_DEFAULTS[knob]:
                continue
            chosen = look_of("default", **{knob: value})
            if knob == "blocks":
                # Calendar blocks are painted per cell, not by the window stylesheet.
                drawn = block_paint(chosen, palette, "#3b82f6")
                assert drawn != base_block, f"blocks={value} draws nothing new"
            else:
                sheet = pack_stylesheet("nocturne", True, chosen)
                assert sheet != base_sheet, f"{knob}={value} draws nothing new"


def test_choosing_a_preset_means_every_one_of_its_knobs() -> None:
    expected = {
        "terminal": {
            "surface": "flat", "corners": "sharp", "depth": "flat", "font": "mono",
            "blocks": "outlined", "density": "compact", "text": "normal",
        },
        "poster": {
            "surface": "flat", "corners": "sharp", "depth": "hard", "font": "sans",
            "blocks": "filled", "density": "compact", "text": "large",
        },
        "ink": {
            "surface": "flat", "corners": "sharp", "depth": "flat", "font": "serif",
            "blocks": "edge", "density": "comfortable", "text": "normal",
        },
        "high-contrast": {
            "surface": "flat", "corners": "sharp", "depth": "hard", "font": "sans",
            "blocks": "outlined", "density": "comfortable", "text": "large",
        },
        "paper": {
            "surface": "flat", "corners": "round", "depth": "soft", "font": "serif",
            "blocks": "filled", "density": "comfortable", "text": "normal",
        },
        "pastel": {
            "surface": "frost", "corners": "pill", "depth": "soft", "font": "sans",
            "blocks": "filled", "density": "comfortable", "text": "normal",
        },
    }
    assert preset_knobs("default") == LOOK_DEFAULTS
    for name, knobs in expected.items():
        assert preset_knobs(name) == knobs
        assert look_overrides(name, knobs) == {}
    assert look_overrides("terminal", {**preset_knobs("terminal"), "depth": "hard"}) == {"depth": "hard"}
    assert look_overrides("default", {**LOOK_DEFAULTS, "corners": "pill"}) == {"corners": "pill"}


def test_native_colours_are_the_audited_web_tokens() -> None:
    names = {
        "window": "--bg", "panel": "--surface-solid", "field": "--field", "grid": "--grid-cell",
        "text": "--text", "muted": "--muted", "accent": "--accent", "accent_ink": "--accent-ink",
        "error": "--error", "block_locked": "--block-locked", "block_locked_ink": "--block-locked-ink",
        "block_flex": "--block-flex", "block_flex_ink": "--block-flex-ink", "block_edge": "--block-edge",
    }
    selectors = {
        "nocturne": ":root", "slate": ':root[data-theme="slate"]',
        "dark-frost": ':root[data-theme="dark-frost"]', "light-frost": ':root[data-theme="light-frost"]',
    }
    tables = [(name, PALETTES[name], selector) for name, selector in selectors.items()]
    tables.append(("terminal", PRESET_PALETTES["terminal"], ':root[data-preset="terminal"]'))
    tables.append(("poster", PRESET_PALETTES["poster"], ':root[data-preset="poster"]'))
    tables.append(("high-contrast", PRESET_PALETTES["high-contrast"], ':root[data-preset="high-contrast"]'))
    tables.append(("paper", PRESET_PALETTES["paper"], ':root[data-preset="paper"]'))
    tables.append(("pastel", PRESET_PALETTES["pastel"], ':root[data-preset="pastel"]'))
    tables.append(("ink-dark", PRESET_PALETTES["ink"]["dark"], ':root[data-preset="ink"]'))
    tables.append(
        ("ink-light", PRESET_PALETTES["ink"]["light"], ':root[data-theme="slate"][data-preset="ink"]'),
    )
    for look, native, selector in tables:
        web = web_tokens(selector)
        for key, token in names.items():
            assert native[key] == web[token], f"{look}: {key} differs from the web's {token}"
        # The web states hairlines as a tint at an alpha; native settles them over the panel.
        for key, token in (("hairline", "--hairline"), ("hairline_strong", "--hairline-strong")):
            red, green, blue, alpha = (float(part) for part in re.findall(r"[\d.]+", web[token]))
            tint = f"#{int(red):02x}{int(green):02x}{int(blue):02x}"
            assert native[key] == mix(tint, native["panel"], alpha), f"{look}: {key}"
    for accent, by_axis in ACCENT_COLORS.items():
        dark = web_tokens(f':root[data-accent="{accent}"]')
        light = web_tokens(f':root[data-theme="slate"][data-accent="{accent}"]')
        assert by_axis["dark"] == (dark["--accent"], dark["--accent-ink"]), accent
        assert by_axis["light"] == (light["--accent"], light["--accent-ink"]), accent


def test_every_look_keeps_its_text_readable() -> None:
    pairs = [
        ("text", "window"), ("text", "panel"), ("text", "field"), ("text", "grid"),
        ("muted", "window"), ("muted", "panel"), ("error", "panel"),
        ("accent_ink", "accent"), ("block_locked_ink", "block_locked"), ("block_flex_ink", "block_flex"),
    ]
    assert len(EVERY_LOOK) == 5 * 2 * 7 * 5 * 2
    for pack, system_dark, preset, accent, surface in EVERY_LOOK:
        palette = resolved_palette(pack, system_dark, look_of(preset, surface=surface), accent)
        for ink, fill in pairs:
            ratio = contrast(palette[ink], palette[fill])
            where = f"{pack}/{'dark' if system_dark else 'light'}/{preset}/{accent}/{surface}"
            assert ratio >= AA_TEXT, f"{where}: {ink} on {fill} is {ratio:.2f} to 1"


def test_button_text_comes_from_the_palette_not_a_fixed_white() -> None:
    # White on Terminal's amber was 1.8 to 1. The ink has to be the one paired with the accent.
    sheet = pack_stylesheet("slate", False, look_of("terminal"))
    assert "QPushButton { background: #ffb000; color: #000000;" in sheet
    assert "#ffffff" not in sheet
    dark = pack_stylesheet("nocturne", True, look_of("default"), "gold")
    assert "QPushButton { background: #eab308; color: #0b1224;" in dark


def test_an_accent_always_changes_the_accent() -> None:
    """Sky once equalled the Light frost default, so choosing it did nothing."""
    for pack, system_dark, preset in product(PACKS, (False, True), LOOK_PRESETS):
        plain = resolved_palette(pack, system_dark, look_of(preset))["accent"]
        seen = {plain}
        for accent in ACCENTS:
            if accent == "default":
                continue
            chosen = resolved_palette(pack, system_dark, look_of(preset), accent)["accent"]
            assert chosen not in seen, f"{accent} on {pack}/{preset} repeats {chosen}"
            seen.add(chosen)


def test_ink_follows_the_pack_axis() -> None:
    light = resolved_palette("slate", False, look_of("ink"))
    dark = resolved_palette("nocturne", True, look_of("ink"))
    frost_light = resolved_palette("light-frost", False, look_of("ink"))
    assert light["text"] == frost_light["text"] == "#1a1a1a"
    assert dark["text"] == "#eaeaea"
    assert light["axis"] == "light"
    assert dark["axis"] == "dark"


def test_a_students_accent_wins_over_the_presets_own() -> None:
    assert resolved_palette("slate", False, look_of("terminal"))["accent"] == "#ffb000"
    chosen = resolved_palette("slate", False, look_of("terminal"), "sky")
    # Terminal is a dark look whatever the pack underneath, so it takes the dark-axis sky and its ink.
    assert (chosen["accent"], chosen["accent_ink"]) == ("#38bdf8", "#0b1224")


def test_flat_surface_has_no_raised_panels_and_frost_does() -> None:
    frost = resolved_palette("nocturne", True, look_of("default"))
    flat = resolved_palette("nocturne", True, look_of("default", surface="flat"))
    assert frost["panel"] != frost["window"]
    assert flat["panel"] == flat["window"] == frost["window"]
    assert flat["field"] == flat["window"]


def test_depth_is_drawn_with_edges_because_qt_has_no_shadows() -> None:
    soft = pack_stylesheet("nocturne", True, look_of("default"))
    flat = pack_stylesheet("nocturne", True, look_of("default", depth="flat"))
    hard = pack_stylesheet("nocturne", True, look_of("default", depth="hard"))
    assert "border: 1px solid" in soft and "border: none;" not in soft.split("QHeaderView")[0]
    assert "border: none;" in flat and "1px solid" not in flat
    assert "border-bottom: 4px solid" in hard and "border-right: 4px solid" in hard


def test_a_block_shows_its_category_colour_in_the_place_the_knob_names() -> None:
    palette = resolved_palette("nocturne", True, None)
    blue = "#3b82f6"
    filled = block_paint(look_of("default"), palette, blue)
    assert (filled["fill"], filled["outline"], filled["edge"]) == (blue, None, None)
    outlined = block_paint(look_of("default", blocks="outlined"), palette, blue)
    assert (outlined["fill"], outlined["outline"], outlined["edge"]) == (palette["grid"], blue, None)
    assert outlined["ink"] == palette["text"]
    edge = block_paint(look_of("default", blocks="edge"), palette, blue)
    assert (edge["fill"], edge["edge"]) == (palette["panel"], blue)
    # No category: a filled block uses the palette's own block colours, flexible work the warm pair.
    plain = block_paint(look_of("default"), palette, None, "flexible")
    assert (plain["fill"], plain["ink"]) == (palette["block_flex"], palette["block_flex_ink"])
    bare = block_paint(look_of("default", blocks="outlined"), palette, None)
    assert bare["outline"] == palette["block_edge"]
    # A pale fill makes a vanishing outline on a light pack, so an outline or an edge uses the strong mark.
    pale, strong = "#bfdbfe", "#3b82f6"
    assert block_paint(look_of("default"), palette, pale, "locked", strong)["fill"] == pale
    outlined_pale = block_paint(look_of("default", blocks="outlined"), palette, pale, "locked", strong)
    assert outlined_pale["outline"] == strong
    assert block_paint(look_of("default", blocks="edge"), palette, pale, "locked", strong)["edge"] == strong


def test_a_filled_block_is_readable_on_every_category_colour() -> None:
    assert len(CATEGORIES) == 8
    for name, category in CATEGORIES.items():
        color = category["color"]
        ratio = contrast(readable_ink(color), color)
        assert ratio >= AA_TEXT, f"{name} {color}: best ink is only {ratio:.2f} to 1"


def test_category_marks_are_the_web_clients_category_colours() -> None:
    app_js = (Path(__file__).parents[2] / "frontend/app.js").read_text()
    web = dict(re.findall(r'id: "([a-z]+)", label: "[^"]+", color: "(#[0-9a-f]{6})"', app_js))
    assert len(web) == 8
    assert {name: category["mark"] for name, category in CATEGORIES.items()} == web


def test_paper_and_pastel_are_light_looks_on_any_pack_and_close_the_menu() -> None:
    assert [name for name, _label, kind in look_menu_items() if kind == "preset"] == [
        "terminal", "poster", "ink", "high-contrast", "paper", "pastel",
    ]
    for preset, accent in (("paper", "#8a4b2a"), ("pastel", "#7a3e9d")):
        for pack, system_dark in (("nocturne", True), ("dark-frost", True), ("slate", False)):
            palette = resolved_palette(pack, system_dark, look_of(preset))
            assert (palette["axis"], palette["accent"]) == ("light", accent), f"{preset} on {pack}"
        # A chosen accent therefore takes its light-axis colour, even over a dark pack.
        chosen = resolved_palette("nocturne", True, look_of(preset), "sea")
        assert (chosen["accent"], chosen["accent_ink"]) == ("#0f766e", "#ffffff")


def test_paper_and_pastel_are_the_soft_looks_and_are_not_ink() -> None:
    """Every earlier preset is flat and sharp. These two keep rounded corners and drawn depth."""
    for preset in ("paper", "pastel"):
        sheet = pack_stylesheet("slate", False, look_of(preset))
        assert "border-radius: 0px" not in sheet
        assert "border: 1px solid" in sheet, "soft depth is a hairline edge"
    assert "border-radius: 16px" in pack_stylesheet("slate", False, look_of("pastel"))
    assert "Noto Serif" in pack_stylesheet("slate", False, look_of("paper"))
    # Pastel is the one preset with raised panels; Paper's pages sit flat in the cream.
    pastel = resolved_palette("slate", False, look_of("pastel"))
    paper = resolved_palette("slate", False, look_of("paper"))
    assert pastel["panel"] != pastel["window"]
    assert paper["panel"] == paper["window"] == "#f7ecd2"
    ink = resolved_palette("slate", False, look_of("ink"))
    assert (paper["text"], paper["window"]) != (ink["text"], ink["window"])
    assert preset_knobs("paper")["blocks"] == "filled" and preset_knobs("ink")["blocks"] == "edge"
