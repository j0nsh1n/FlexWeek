"""The layout choice a look file keeps: Today's app is the only design, and an older file that names a
design this build no longer has still loads as Today's app."""

from __future__ import annotations

import itertools
import math

from desktop.native.layout_choice import (
    DESIGN_LOOKS,
    LAYOUTS,
    options_for,
    sanitize_layout,
)
from desktop.native.look import ACCENTS, PACKS, design_look, resolved_palette
from desktop.tests.week.support_design_registry import _lab

GONE = ("timeline", "bento", "retro")


def test_the_registry_holds_todays_app_and_no_day_screen() -> None:
    assert [spec.id for spec in LAYOUTS.values() if spec.role == "plan"] == ["classic"]
    assert [spec.id for spec in LAYOUTS.values() if spec.role == "day"] == []


def test_todays_app_offers_its_signature_high_contrast_dark_and_your_look() -> None:
    curated = DESIGN_LOOKS["classic"]
    option = next(option for option in LAYOUTS["classic"].options if option.key == "look")
    assert option.values == tuple(value for value, _label in curated) + ("your",)
    assert curated[0][0] not in {"preset:high-contrast", "pack:dark-frost"}
    assert ("preset:high-contrast", "High contrast") in curated
    assert any(value.startswith("pack:dark-") or value == "preset:terminal" for value, _ in curated)
    assert len(curated) >= 4


def test_options_are_known_and_defaults_are_shipped() -> None:
    for spec in LAYOUTS.values():
        assert {option.level for option in spec.options} <= {"style", "detail"}
        assert len({option.key for option in spec.options}) == len(spec.options)
        for option in spec.options:
            assert option.default in option.values
    assert options_for(None, "classic")["look"] == "your"


def test_missing_design_looks_keep_the_account_look() -> None:
    choice = sanitize_layout({"main": "classic", "options": {}})
    assert choice["options"] == {}
    assert all(options_for(choice, layout_id)["look"] == "your" for layout_id in LAYOUTS)


def test_layout_sanitizer_drops_unknown_values_keys_and_non_dict_options() -> None:
    clean = sanitize_layout(
        {
            "main": "classic",
            "day": "dial",
            "options": {
                "classic": {"look": "preset:nope", "strange": "value"},
                "timeline": "not a dict",
                "ghost": {"look": "your"},
            },
        }
    )
    assert clean == {"main": "classic", "day": "dial", "options": {}}


def test_layout_sanitizer_keeps_a_valid_look_choice() -> None:
    kept = sanitize_layout({"main": "classic", "options": {"classic": {"look": "preset:paper"}}})
    assert kept == {"main": "classic", "day": "dial", "options": {"classic": {"look": "preset:paper"}}}


def test_a_look_file_that_names_a_removed_design_loads_as_todays_app() -> None:
    for design in GONE:
        loaded = sanitize_layout(
            {"main": design, "day": "dial", "options": {design: {"look": "your", "density": "compact"}}}
        )
        assert loaded == {"main": "classic", "day": "dial", "options": {}}, design


def test_bad_layouts_fall_back_and_wrong_roles_do_not_load() -> None:
    shipped = {"main": "classic", "day": "dial", "options": {}}
    for raw in (None, "bento", [], {"main": 7, "day": None, "options": "x"}):
        assert sanitize_layout(raw) == shipped
    assert sanitize_layout({"main": "one", "day": "bento"}) == shipped


def test_an_old_colour_choice_for_todays_app_becomes_your_look() -> None:
    migrated = sanitize_layout({"main": "classic", "options": {"classic": {"colour": "unknown"}}})
    assert migrated["options"]["classic"]["look"] == "your"


def test_every_curated_design_looks_accent_stands_apart_from_its_danger_red() -> None:
    """Every curated look of Today's app, in every pack, accent and surface: the accent is never so
    near the danger red that a student could take one for the other. How well each reads is judged in
    the visual review."""
    close_accents = []
    for layout_id, curated in DESIGN_LOOKS.items():
        looks = (*curated, ("your", "Your look"))
        for (token, _label), (pack, dark, accent, surface) in itertools.product(
            looks,
            itertools.product(PACKS, (False, True), ACCENTS, ("layered", "flat")),
        ):
            worn = {"preset": "default", "knobs": {"surface": surface}}
            palette, _ = design_look(token, pack, dark, worn, accent)
            where = f"{layout_id}/{token}/{pack}/{dark}/{accent}/{surface}"
            gap = math.dist(_lab(palette["accent"]), _lab(palette["error"]))
            if gap < 25:
                close_accents.append((where, round(gap, 1)))
    assert close_accents == []


def test_todays_app_offers_a_light_look() -> None:
    missing = []
    for layout_id, curated in DESIGN_LOOKS.items():
        light = []
        for token, _label in curated:
            palette, _ = design_look(token, "light-frost", False, None)
            if palette["axis"] == "light":
                light.append(token)
        if not light:
            missing.append(layout_id)
    assert missing == []


def test_legacy_look_alias_falls_back_to_the_accounts_look_when_unknown() -> None:
    palette = resolved_palette("nocturne", True, None)
    assert design_look("preset:unknown", "nocturne", True, None)[0]["window"] == palette["window"]
