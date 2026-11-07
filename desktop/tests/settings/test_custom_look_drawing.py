"""A look of the student's own (0.17's Customise): one of the ten looks with what they changed, drawn as
the built-in looks are."""

from __future__ import annotations

import pytest

from desktop.native.calendar import CATEGORIES
from desktop.native.custom_look import apply_fix, readability
from desktop.native.look import (
    AA_TEXT,
    FILL,
    FONT_FAMILIES,
    LOOK_BASES,
    block_paint,
    category_paint,
    contrast,
    effective_look,
    look_measures,
    look_motion,
    pack_stylesheet,
    resolved_palette,
)
from desktop.native.tokens import MARK, oklab, oklch, oklch_of


def worn(custom: dict) -> dict:
    return {"preset": "default", "knobs": {}, "custom": custom}


def test_a_custom_look_with_nothing_changed_draws_as_its_base() -> None:
    """Every one of the ten looks is a starting point: customised with nothing moved, it is that look."""
    for base, (pack, preset) in LOOK_BASES.items():
        for system_dark in (False, True):
            as_built = resolved_palette(pack, system_dark, {"preset": preset, "knobs": {}}, "sea")
            custom = resolved_palette("slate", system_dark, worn({"base": base, "accent": "sea"}))
            if preset == "high-contrast":
                # High contrast keeps its yellow unless the student picks an accent of their own.
                as_built = {
                    **as_built,
                    "accent": "#2dd4bf",
                    "accent_ink": "#0b1224",
                    "accent_text": "#2dd4bf",
                    "now": "#2dd4bf",
                    "selection": "#2dd4bf",
                }
            assert custom == as_built, (base, system_dark)
            sheet = pack_stylesheet(pack, system_dark, {"preset": preset, "knobs": {}}, "sea")
            if preset != "high-contrast":
                assert pack_stylesheet("slate", system_dark, worn({"base": base, "accent": "sea"})) == sheet


def test_the_students_colours_replace_the_bases_and_the_rest_follows_from_them() -> None:
    """Page, card, text and line as set; muted text, the raised card and the strong line worked out
    from them, muted as quiet as it can be while it still reads."""
    colours = {"page": "#f4efe6", "card": "#fffaf0", "text": "#2b2118", "line": "#e2d6c2"}
    custom = {"base": "light", "colours": colours}
    palette = resolved_palette("system", False, worn(custom))
    assert (palette["window"], palette["panel"], palette["text"], palette["hairline"]) == (
        "#f4efe6",
        "#fffaf0",
        "#2b2118",
        "#e2d6c2",
    )
    assert palette["muted"] not in {palette["text"], palette["panel"]}
    assert contrast(palette["muted"], palette["panel"]) >= AA_TEXT
    assert contrast(palette["muted"], palette["window"]) >= AA_TEXT
    assert palette["card_2"] != palette["panel"] and palette["hairline_strong"] != palette["hairline"]
    # A dark page makes it a dark look: the dark accent, and fills sunk into the card.
    night = {"page": "#101418", "card": "#1b2026", "text": "#e6e9ee"}
    dark = resolved_palette("system", False, worn({"base": "light", "colours": night}))
    assert (dark["axis"], dark["family"], dark["accent"]) == ("dark", "dark", "#7fa8ff")
    assert category_paint("class", dark)[0] != CATEGORIES["class"]["color"]


def test_a_category_takes_a_hue_on_the_family_or_an_exact_colour() -> None:
    """A hue sits on the family's lightness and chroma, so it reads by construction; an exact colour
    is the block's fill in any look."""
    custom = {"base": "light", "categories": {"class": {"hue": 140}, "meals": {"colour": "#ffcc66"}}}
    palette = resolved_palette("system", False, worn(custom))
    fill, mark = category_paint("class", palette)
    assert (fill, mark) == (oklch(FILL[0], FILL[1], 140), oklch(*MARK["light"], 140))
    assert abs(oklab(fill)[0] - oklab(CATEGORIES["exercise"]["color"])[0]) <= 0.02
    assert category_paint("meals", palette)[0] == "#ffcc66"
    assert category_paint("study", palette) == (CATEGORIES["study"]["color"], CATEGORIES["study"]["mark"])
    night = resolved_palette("system", True, worn({**custom, "base": "dark"}))
    assert category_paint("meals", night)[0] == "#ffcc66"
    assert oklch_of(category_paint("class", night)[1])[0] == pytest.approx(MARK["dark"][0], abs=0.01)


def test_every_measure_and_choice_reaches_what_is_drawn() -> None:
    """Corners, spacing, shadows, faces, text size, blocks, the grid and motion, each as set."""
    custom = {
        "base": "light",
        "corners": 14,
        "spacing": "compact",
        "shadows": "bold",
        "body_font": "serif",
        "heading_font": "mono",
        "text_scale": 1.2,
        "blocks": "outline",
        "edge_width": 5,
        "show_times": False,
        "show_lengths": True,
        "today_highlight": False,
        "hour_lines": "none",
        "now_line": "text",
        "motion": "off",
    }
    look = worn(custom)
    measures = look_measures(look)
    # The body size at 1.2 times the type scale's 13 points, to the half point.
    assert (measures["card_radius"], measures["radius"], measures["size"]) == (14, 8, 15.5)
    assert (measures["body"], measures["heading"]) == (FONT_FAMILIES["serif"], FONT_FAMILIES["mono"])
    assert (measures["edge_width"], measures["show_times"], measures["today_highlight"]) == (5, False, False)
    knobs = effective_look(look)
    drawn = (knobs["density"], knobs["depth"], knobs["blocks"], knobs["text"])
    assert drawn == ("compact", "bold", "outline", "large")
    sheet = pack_stylesheet("system", False, look)
    assert "font-family: Newsreader" in sheet.split("QWidget {")[1].split("}")[0]
    assert "font-size: 15.5pt" in sheet and "border-radius: 14px" in sheet
    assert "border-bottom: 4px solid" in sheet
    palette = resolved_palette("system", False, look)
    assert palette["rule"] == palette["window"] and palette["now"] == palette["text"]
    assert block_paint(look, palette, "#dddddd")["outline"] == "#dddddd"
    assert look_motion(look) == "off"
    assert look_motion(worn({"base": "paper"})) == "reduce"


def test_a_colour_of_the_students_own_as_the_accent() -> None:
    palette = resolved_palette("system", False, worn({"base": "light", "accent": "#9a3412"}))
    assert palette["accent"] == "#9a3412"
    assert contrast(palette["accent_ink"], palette["accent"]) >= AA_TEXT
    # One so pale its words would not read stays as typed, and the check offers the darker shade.
    pale = {"base": "light", "accent": "#9fd3ff"}
    assert resolved_palette("system", False, worn(pale))["accent"] == "#9fd3ff"
    problem = next(p for p in readability(pale) if p.words == "Accent text on cards")
    mended = resolved_palette("system", False, worn(apply_fix(pale, problem)))
    assert mended["accent"] == problem.fixed
    for ground in ("window", "panel"):
        assert contrast(mended["accent"], mended[ground]) >= AA_TEXT, ground
    assert contrast(mended["accent_ink"], mended["accent"]) >= AA_TEXT
    assert abs(oklch_of(mended["accent"])[2] - oklch_of("#9fd3ff")[2]) < 3
    # A swatch on a tinted page is its own darker shade already, as in the built-in looks.
    swatch = resolved_palette("system", False, worn({"base": "slate", "accent": "default"}))
    assert swatch["accent"] == "#3b6cc1"
