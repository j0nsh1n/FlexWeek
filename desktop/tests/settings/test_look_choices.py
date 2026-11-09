"""Which looks a student can choose, and what choosing one means: the menu, the presets and their
knobs, the names a look saved by an older version keeps, and what a hand-edited file may hold."""

from __future__ import annotations

from desktop.native.look import (
    KNOB_LABELS,
    KNOB_VALUE_LABELS,
    LOOK_DEFAULTS,
    LOOK_KNOBS,
    LOOK_PRESETS,
    PACKS,
    effective_look,
    look_menu_items,
    look_menu_token,
    look_menu_value,
    look_motion,
    look_overrides,
    pack_axis,
    parse_look_menu_token,
    preset_knobs,
    resolved_pack_theme,
    sanitize_look,
)
from desktop.tests.settings.support_look import look_of


def test_the_look_menu_offers_four_looks_then_the_experimental_ones() -> None:
    """Decision 3 of 0.16: System, Light, Dark and High contrast, and the other seven under
    Experimental styles. Every pack and preset is still offered once, so a saved look can be picked."""
    standard, experimental = look_menu_items()
    assert [label for _name, label, _kind in standard] == ["System", "Light", "Dark", "High contrast"]
    assert [label for _name, label, _kind in experimental] == [
        "Nocturne",
        "Slate",
        "Poster",
        "Terminal",
        "Paper",
        "Ink",
        "Pastel",
    ]
    offered = {(kind, name) for name, _label, kind in standard + experimental}
    expected = {("pack", name) for name in PACKS} | {
        ("preset", name) for name in LOOK_PRESETS if name != "default"
    }
    assert offered == expected
    assert look_menu_value("nocturne", {"preset": "default", "knobs": {}}) == look_menu_token(
        "pack", "nocturne"
    )
    assert look_menu_value("nocturne", {"preset": "terminal", "knobs": {}}) == look_menu_token(
        "preset", "terminal"
    )
    assert parse_look_menu_token("preset:default") is None
    assert parse_look_menu_token("preset:terminal") == ("preset", "terminal")


def test_unknown_knobs_and_looks_fall_back_and_a_hand_edited_file_never_stops_the_look_loading() -> None:
    clean = sanitize_look({"preset": "neon", "knobs": {"font": "comic", "text": "large"}})
    assert clean["preset"] == "default"
    assert clean["knobs"] == {"text": "large"}
    assert effective_look(clean)["font"] == "sans"
    assert effective_look(clean)["text"] == "large"
    # A file edited by hand may hold anything; nothing in it can stop the look loading.
    odd = sanitize_look({"preset": ["poster"], "knobs": {"corners": ["round"], "depth": {"x": 1}}})
    assert odd == {"preset": "default", "knobs": {}}


def test_a_presets_knobs_come_first_and_the_students_own_knobs_win_over_them() -> None:
    effective = effective_look(sanitize_look(look_of("terminal", text="large")))
    assert effective["font"] == "mono"
    assert effective["corners"] == "sharp"
    assert effective["text"] == "large"


def test_system_follows_the_device_between_light_and_dark() -> None:
    """Decision 2 of 0.17: System is Light or Dark as the device is. The server still hears the
    frost looks as slate and nocturne, the axis a saved preference has always had."""
    assert pack_axis("light-frost") == "slate"
    assert pack_axis("dark-frost") == "nocturne"
    assert pack_axis("system") == "system"
    assert resolved_pack_theme("system", True) == "dark-frost"
    assert resolved_pack_theme("system", False) == "light-frost"
    assert resolved_pack_theme("slate", True) == "slate"


def test_choosing_a_preset_means_every_one_of_its_knobs() -> None:
    """Each look of 0.17's plan with the knobs it is drawn with. Blocks follow the default in all but
    High contrast, as the mock-up draws them."""
    blocks = LOOK_DEFAULTS["blocks"]
    common = {"density": "comfortable", "text": "normal", "blocks": blocks}
    expected = {
        "terminal": {**common, "surface": "layered", "corners": "sharp", "depth": "soft", "font": "mono"},
        "poster": {**common, "surface": "layered", "corners": "sharp", "depth": "bold", "font": "sans"},
        "ink": {**common, "surface": "layered", "corners": "soft", "depth": "soft", "font": "serif"},
        "paper": {**common, "surface": "layered", "corners": "soft", "depth": "none", "font": "serif"},
        "pastel": {**common, "surface": "layered", "corners": "rounded", "depth": "soft", "font": "sans"},
        "high-contrast": {
            "surface": "flat",
            "corners": "sharp",
            "depth": "bold",
            "font": "sans",
            "blocks": "outline",
            "density": "comfortable",
            "text": "large",
        },
    }
    assert preset_knobs("default") == LOOK_DEFAULTS
    for name, knobs in expected.items():
        assert preset_knobs(name) == knobs
        assert look_overrides(name, knobs) == {}
    assert look_overrides("terminal", {**preset_knobs("terminal"), "depth": "bold"}) == {"depth": "bold"}
    assert look_overrides("default", {**LOOK_DEFAULTS, "corners": "rounded"}) == {"corners": "rounded"}


def test_a_look_saved_by_016_opens_with_its_knobs_named_as_017_names_them() -> None:
    """0.17 renamed five knob values. A look file written by 0.16 keeps what it chose: frost is
    Layered, round Soft, pill Round, flat depth None, hard Bold, outlined Outline."""
    saved = {
        "preset": "terminal",
        "knobs": {"surface": "frost", "corners": "pill", "depth": "hard", "blocks": "outlined"},
    }
    assert sanitize_look(saved)["knobs"] == {
        "surface": "layered",
        "corners": "rounded",
        "depth": "bold",
        "blocks": "outline",
    }
    assert sanitize_look({"knobs": {"corners": "round", "depth": "flat"}})["knobs"] == {
        "corners": "soft",
        "depth": "none",
    }
    # Today's names pass through unchanged, Round among them.
    assert sanitize_look({"knobs": {"corners": "rounded"}})["knobs"] == {"corners": "rounded"}
    for knob, values in LOOK_KNOBS.items():
        assert all(value in KNOB_VALUE_LABELS for value in values), knob
    assert [KNOB_VALUE_LABELS[value] for value in LOOK_KNOBS["corners"]] == ["Soft", "Sharp", "Round"]
    assert set(KNOB_LABELS) == set(LOOK_KNOBS)


def test_paper_starts_at_reduce_motion() -> None:
    """E-Ink's "distinct page turns, sharp transitions": Paper's level when the student never chose
    one. Every other look starts at Normal, whatever the pack."""
    assert look_motion(look_of("paper")) == "reduce"
    for preset in ("default", "ink"):
        assert look_motion(look_of(preset)) == "normal", preset
