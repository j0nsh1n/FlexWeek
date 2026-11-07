"""What each look and accent is: Paper's cream and serif, Pastel's tinted cards, Sand against Gold, the
chosen blue, and the Readability list that names and mends a pale accent. The category hues and the
darker Sleep fill are held by the engine's desk_looks_polish.rs; whether the colours read is judged on
the pictures in pictures/screens_settings_h2.py.
"""

from __future__ import annotations

import pytest

from desktop.native.custom_look import apply_fix, readability
from desktop.native.look import (
    AA_GRAPHIC,
    ACCENT_COLORS,
    button_rules,
    effective_look,
    look_measures,
    mix,
    resolved_palette,
)
from desktop.native.tokens import contrast, oklab, oklch_of


def test_paper_is_a_cream_planner_with_serif_figures() -> None:
    palette = resolved_palette("light-frost", False, {"preset": "paper"})
    assert palette["accent"] == "#1f3a68"
    assert palette["panel"] == "#fbf6ea"
    assert look_measures({"preset": "paper"})["body"].startswith("Newsreader")


def test_pastel_has_tinted_cards_and_fuller_fills() -> None:
    pastel = resolved_palette("light-frost", False, {"preset": "pastel"})
    assert pastel["panel"] != "#ffffff"
    assert pastel.get("fill", (1.0, 0.0))[0] < 0.92


def test_paper_has_no_shadows_and_pastel_has_rounder_corners() -> None:
    assert effective_look({"preset": "paper"})["depth"] == "none"
    assert look_measures({"preset": "pastel"})["card_radius"] > look_measures(None)["card_radius"]


@pytest.mark.parametrize("axis", ["light", "dark"])
def test_sand_is_a_different_colour_from_gold(axis: str) -> None:
    gold, sand = ACCENT_COLORS["gold"][axis][0], ACCENT_COLORS["sand"][axis][0]
    a, b = oklab(gold), oklab(sand)
    assert sum((first - second) ** 2 for first, second in zip(a, b, strict=True)) ** 0.5 >= 0.05
    hue_a, hue_b = oklch_of(gold)[2], oklch_of(sand)[2]
    assert min(abs(hue_a - hue_b), 360 - abs(hue_a - hue_b)) >= 20


def test_the_chosen_blue_is_exact_and_now_and_selection_share_it() -> None:
    palette = resolved_palette("light-frost", False, None)
    assert palette["accent"] == "#3d6fc4"
    assert palette["now"] == palette["selection"]


def test_readability_names_each_use_of_a_pale_accent_and_fixes_them() -> None:
    """The fixer's contract: each named use is mended to the ratio its words need, so the ratios here
    are what apply_fix computes, not a picture."""
    custom = {"name": "Lime", "base": "light", "accent": "#dfff00"}
    problems = readability(custom)
    named = {problem.words: problem for problem in problems}
    rows = (("The Plan button's words", 4.5), ("Today's day name", 4.5), ("Now line", AA_GRAPHIC))
    for words, need in rows:
        assert words in named
        fixed = apply_fix(custom, named[words])
        palette = resolved_palette("light-frost", False, {"custom": fixed})
        ratios = [contrast(palette["accent"], palette[under]) for under in ("window", "panel", "grid")]
        assert min(ratios) >= need


@pytest.mark.parametrize(("accent", "flagged"), [("#8a8a8a", False), ("#a6a6a6", True)])
def test_the_now_line_is_flagged_only_when_the_line_would_not_show(accent: str, flagged: bool) -> None:
    custom = {"name": "Grey", "base": "light", "accent": accent}
    palette = resolved_palette("light-frost", False, {"custom": custom})
    ratio = contrast(accent, palette["grid"])
    # The fixtures sit either side of 3 to 1; the first is a line that shows but text that does not.
    assert (ratio < AA_GRAPHIC) is flagged
    assert 2.0 < ratio < 4.5
    assert ("Now line" in {problem.words for problem in readability(custom)}) is flagged


def test_a_pale_custom_accent_stays_chosen_but_its_words_are_readable() -> None:
    custom = {"name": "Lime", "base": "light", "accent": "#dfff00"}
    palette = resolved_palette("light-frost", False, {"custom": custom})
    assert palette["accent"] == "#dfff00"
    tint = mix(palette["accent"], palette["window"], 0.10)
    assert contrast(palette.get("accent_text", palette["accent"]), tint) >= 4.5
    assert contrast(palette.get("now", palette["accent"]), palette["grid"]) >= 3
    assert f'color: {palette["accent_text"]};' in button_rules(palette, 8, 6, "flat", "")


@pytest.mark.parametrize("accent", [None, "default", "sky", "gold", "sea", "sand"])
def test_stock_accents_have_no_readability_warning(accent: str | None) -> None:
    custom = {"name": "Stock", "base": "light"}
    if accent is not None:
        custom["accent"] = accent
    assert not [problem for problem in readability(custom) if problem.field == ("accent",)]

