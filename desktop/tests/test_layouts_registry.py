"""The registry is what the layout dialog is built from and what the file on disk is checked against,
so it is tested as data: the roles, the three levels, what survives a bad file, and the contrast of
every colourway including the one that follows the student's own look.
"""

from __future__ import annotations

import itertools

import pytest

from desktop.native.layouts.registry import (
    LAYOUTS,
    MATCH,
    contrast_failures,
    layouts_for,
    options_for,
    sanitize_layout,
    tokens_for,
)
from desktop.native.look import ACCENT_COLORS, LOOK_PRESETS, PACKS, contrast, resolved_palette

DESIGNS = [spec.id for spec in LAYOUTS.values() if spec.options]


def test_the_two_roles_hold_the_designs_the_owner_picked() -> None:
    assert [spec.id for spec in layouts_for("plan")] == [
        "classic",
        "timeline",
        "mission",
        "bento",
        "retro",
        "clay",
    ]
    assert [spec.id for spec in layouts_for("day")] == ["one", "dial"]


def test_every_design_offers_all_three_levels() -> None:
    for layout_id in DESIGNS:
        levels = {option.level for option in LAYOUTS[layout_id].options}
        assert levels == {"style", "detail"}, layout_id


def test_every_design_ships_its_own_colours_first_and_can_follow_the_students_look() -> None:
    for layout_id in DESIGNS:
        spec = LAYOUTS[layout_id]
        colour = spec.options[0]
        assert colour.key == "colour" and colour.level == "style", layout_id
        assert colour.default == spec.colourways[0][0], layout_id
        assert colour.values == (*[value for value, _, _ in spec.colourways], MATCH), layout_id


def test_option_keys_and_choices_are_unambiguous() -> None:
    for spec in LAYOUTS.values():
        keys = [option.key for option in spec.options]
        assert len(keys) == len(set(keys)), spec.id
        for option in spec.options:
            assert len(option.values) == len(set(option.values)) >= 2, (spec.id, option.key)


def test_a_missing_or_broken_file_gives_the_shipped_choice() -> None:
    shipped = {"main": "classic", "day": "one", "options": {}}
    for raw in (None, "bento", [], {"main": 7, "day": None, "options": "x"}):
        assert sanitize_layout(raw) == shipped


def test_a_day_screen_cannot_be_the_main_view_nor_the_other_way_round() -> None:
    assert sanitize_layout({"main": "one", "day": "bento"}) == {
        "main": "classic",
        "day": "one",
        "options": {},
    }
    assert sanitize_layout({"main": "bento", "day": "dial"}) == {
        "main": "bento",
        "day": "dial",
        "options": {},
    }


def test_only_known_options_with_known_values_survive() -> None:
    raw = {
        "main": "bento",
        "options": {
            "bento": {"colour": "sunset", "corners": "triangular", "wallpaper": "cats"},
            "one": {"actions": "hide"},
            "heatmap": {"colour": "red"},
            "clay": "tilted",
        },
    }
    assert sanitize_layout(raw)["options"] == {"bento": {"colour": "sunset"}, "one": {"actions": "hide"}}


def test_options_are_the_students_choice_over_the_designs_defaults() -> None:
    choice = {"options": {"one": {"actions": "hide", "colour": "paper"}}}
    assert options_for(choice, "one") == {
        "colour": "paper",
        "lead": "now",
        "actions": "hide",
        "daybar": "show",
    }
    assert options_for(None, "dial") == {"colour": "midnight", "hours": "day", "list": "show", "week": "show"}
    assert options_for(choice, "classic") == {}


@pytest.mark.parametrize("layout_id", DESIGNS)
def test_every_shipped_colourway_is_readable(layout_id: str) -> None:
    palette = resolved_palette("light-frost", False, None, "default")
    for value, _, _ in LAYOUTS[layout_id].colourways:
        assert contrast_failures(tokens_for(layout_id, value, palette)) == [], (layout_id, value)


def test_match_my_look_is_readable_in_every_look_the_app_has() -> None:
    failures = []
    combos = list(itertools.product(PACKS, (False, True), LOOK_PRESETS, ACCENT_COLORS, ("frost", "flat")))
    for pack, dark, preset, accent, surface in combos:
        look = {"preset": preset, "knobs": {"surface": surface}}
        tokens = tokens_for("bento", MATCH, resolved_palette(pack, dark, look, accent))
        failures += [(pack, dark, preset, accent, surface, item) for item in contrast_failures(tokens)]
    assert len(combos) == 5 * 2 * 7 * len(ACCENT_COLORS) * 2
    assert failures == []


def test_a_design_can_ask_for_a_colour_its_colourway_does_not_name() -> None:
    palette = resolved_palette("light-frost", False, None, "default")
    tokens = tokens_for("one", "black", palette)
    assert (tokens["bg"], tokens["cta"], tokens["cta_ink"]) == ("#000000", "#fb923c", "#000000")
    # Derived from the colourway itself. Borrowed from the student's light look it was white on pale.
    assert [tokens[key] for key in ("card_a", "card_b", "card_c", "card_d")] == [
        "#190f06",
        "#28170a",
        "#37200d",
        "#211308",
    ]
    assert contrast(tokens["text"], tokens["card_c"]) >= 4.5


def test_an_unknown_colourway_falls_back_to_the_students_look() -> None:
    palette = resolved_palette("nocturne", True, None, "default")
    assert tokens_for("clay", "no-such-colours", palette) == tokens_for("clay", MATCH, palette)
    assert tokens_for("clay", MATCH, palette)["bg"] == palette["window"]


def test_the_audit_names_each_unreadable_pair() -> None:
    palette = resolved_palette("light-frost", False, None, "default")
    good = tokens_for("bento", "indigo", palette)
    assert contrast_failures(good) == []
    assert contrast_failures({**good, "muted": good["surface"]})[0] == "muted 1.00"
    assert contrast_failures({**good, "cta_ink": good["cta"]}) == ["cta_ink 1.00"]
    assert contrast_failures({**good, "bg_muted": good["bg"]}) == ["bg_muted 1.00"]
    assert contrast_failures({**good, "card_b": good["text"]}) == [
        "text on card_b 1.00",
        "muted on card_b 1.93",
    ]
