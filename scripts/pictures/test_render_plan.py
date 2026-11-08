"""What the renderer plans to draw, worked out from spec.md's Testing structure rule 6, with no Qt."""

from __future__ import annotations

import json

import pytest

from scripts.pictures import render

# A registry like the app's: main views ("plan") and day screens ("day"), in its order.
DESIGNS = {"classic": "plan", "timeline": "plan", "bento": "plan", "dial": "day", "one": "day"}
DEFAULTS = ("classic", "dial")
SCALES = {"small": 0.85, "normal": 1.0, "large": 1.2}


def test_a_screen_is_drawn_in_every_main_view_and_material_light_and_dark():
    variants = render.plan_variants("week", False, (), DESIGNS)
    assert [variant.name for variant in variants] == [
        "classic.light.normal.1280x800",
        "classic.dark.normal.1280x800",
        "timeline.light.normal.1280x800",
        "timeline.dark.normal.1280x800",
        "bento.light.normal.1280x800",
        "bento.dark.normal.1280x800",
        "material.light.normal.1280x800",
        "material.dark.normal.1280x800",
    ]


def test_a_main_screen_adds_the_edge_set_large_text_high_contrast_light():
    variants = render.plan_variants("week", True, ("classic", "material"), DESIGNS)
    edge = [variant for variant in variants if variant.size == render.EDGE_SIZE]
    assert [variant.name for variant in edge] == [
        "classic.light.large.1024x640.hc",
        "material.light.large.1024x640.hc",
    ]
    assert all(variant.high_contrast and variant.text == "large" for variant in edge)
    assert len(variants) == 2 * 2 + 2


def test_a_my_day_screen_is_drawn_in_the_day_screens():
    styles = {variant.style for variant in render.plan_variants("myday", False, (), DESIGNS)}
    assert styles == {"dial", "one", "material"}


def test_a_style_nobody_knows_is_refused_with_the_known_ones():
    with pytest.raises(ValueError, match="unknown style poster; the styles are classic"):
        render.plan_variants("week", False, ("poster",), DESIGNS)


def test_widgets_means_every_widgets_design_of_the_screens_role_and_no_material():
    week = {variant.style for variant in render.plan_variants("settings", False, ("widgets",), DESIGNS)}
    assert week == {"classic", "timeline", "bento"}
    day = {variant.style for variant in render.plan_variants("myday", False, ("widgets",), DESIGNS)}
    assert day == {"dial", "one"}


def test_widgets_and_material_together_are_every_style_once():
    variants = render.plan_variants("week", False, ("widgets", "material", "classic"), DESIGNS)
    styles = [variant.style for variant in variants if variant.mode == "light"]
    assert styles == ["classic", "timeline", "bento", "material"]


def test_a_widgets_main_view_is_worn_as_the_main_slot_on_the_widgets_surface():
    variant = render.Variant("timeline", "dark", "normal", render.FULL_SIZE)
    body = render.look_body(None, variant, DESIGNS, DEFAULTS, SCALES)
    assert body["surface"] == "widgets"
    assert body["layout"] == {"main": "timeline", "day": "dial", "options": {}}
    assert body["preset"] == "default"
    assert body["knobs"] == {"text": "normal"}


def test_a_day_screen_is_worn_as_the_day_slot():
    variant = render.Variant("one", "light", "normal", render.FULL_SIZE)
    body = render.look_body(None, variant, DESIGNS, DEFAULTS, SCALES)
    assert body["layout"] == {"main": "classic", "day": "one", "options": {}}


def test_material_takes_its_own_mode_contrast_and_text_size():
    variant = render.Variant("material", "light", "large", render.EDGE_SIZE, True)
    stored = json.dumps({"material": {"preset": "Sea", "advanced": {"rail": False}}}).encode()
    body = render.look_body(stored, variant, DESIGNS, DEFAULTS, SCALES)
    assert body["surface"] == "material"
    assert body["material"] == {
        "preset": "Sea",
        "mode": "light",
        "contrast": "high",
        "advanced": {"rail": False, "scale": 1.2},
    }
    assert body["preset"] == "high-contrast"


def test_the_accounts_own_look_keeps_what_the_variant_does_not_set_and_loses_a_material_failure():
    stored = json.dumps(
        {
            "preset": "paper",
            "knobs": {"font": "serif", "text": "small"},
            "zoom": {"week": 2},
            "material_failed": "1.2.0",
            "custom": {"base": "light"},
        }
    ).encode()
    variant = render.Variant("classic", "light", "normal", render.FULL_SIZE)
    body = render.look_body(stored, variant, DESIGNS, DEFAULTS, SCALES)
    assert body["preset"] == "default"
    assert body["knobs"] == {"font": "serif", "text": "normal"}
    assert body["zoom"] == {"week": 2}
    assert "material_failed" not in body
    assert "custom" not in body


def test_screen_ids_are_read_one_per_line(tmp_path):
    ids = tmp_path / "ids"
    ids.write_text("week.grid\n\n# a note\n  day.hours  \n")
    assert render.read_ids(ids) == ["week.grid", "day.hours"]
