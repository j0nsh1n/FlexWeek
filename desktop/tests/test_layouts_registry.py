"""The design registry keeps each design's curated looks and sanitizes stored choices."""

from __future__ import annotations

import itertools
import math

import pytest

from desktop.native.layouts import registry as layouts_registry
from desktop.native.layouts.registry import (
    DESIGN_LOOKS,
    LAYOUTS,
    LEGACY_COLOURS,
    LEVELS,
    contrast_failures,
    layouts_for,
    options_for,
    sanitize_layout,
    tokens_for,
)
from desktop.native.look import AA_TEXT, ACCENTS, PACKS, contrast, design_look, resolved_palette
from desktop.tests.test_look import _lab


def test_the_two_roles_hold_the_designs_the_owner_picked() -> None:
    assert [spec.id for spec in LAYOUTS.values() if spec.role == "plan"] == [
        "classic", "timeline", "mission", "bento", "retro", "clay"
    ]
    assert [spec.id for spec in LAYOUTS.values() if spec.role == "day"] == ["dial", "one"]


def test_every_design_offers_its_signature_high_contrast_dark_and_your_look() -> None:
    for layout_id, curated in DESIGN_LOOKS.items():
        option = next(option for option in LAYOUTS[layout_id].options if option.key == "look")
        assert option.values == tuple(value for value, _label in curated) + ("your",)
        assert curated[0][0] not in {"preset:high-contrast", "pack:dark-frost"}, layout_id
        assert ("preset:high-contrast", "High contrast") in curated, layout_id
        assert any(
            value.startswith("pack:dark-") or value == "preset:terminal" for value, _ in curated
        ), layout_id
        assert len(curated) >= 4


def test_options_are_known_and_defaults_are_shipped() -> None:
    drawn = {level for level, _ in LEVELS}
    for spec in LAYOUTS.values():
        assert {option.level for option in spec.options} <= drawn
        assert len({option.key for option in spec.options}) == len(spec.options)
        for option in spec.options:
            assert option.default in option.values
    assert options_for(None, "classic")["look"] == "your"
    assert options_for(None, "dial")["look"] == "your"


def test_missing_design_looks_keep_the_account_look_for_every_design() -> None:
    choice = sanitize_layout({"main": "bento", "day": "one", "options": {}})
    assert choice["options"] == {}
    assert all(options_for(choice, layout_id)["look"] == "your" for layout_id in LAYOUTS)


def test_layout_sanitizer_drops_unknown_values_keys_and_non_dict_options() -> None:
    clean = sanitize_layout(
        {
            "main": "bento",
            "day": "dial",
            "options": {
                "bento": {"look": "preset:nope", "corners": "triangular", "strange": "value"},
                "timeline": "not a dict",
                "ghost": {"look": "your"},
            },
        }
    )
    assert clean == {"main": "bento", "day": "dial", "options": {}}


def test_layout_sanitizer_keeps_a_valid_main_day_pair() -> None:
    assert sanitize_layout({"main": "bento", "day": "dial"}) == {
        "main": "bento", "day": "dial", "options": {}
    }


def test_fold_bounds_options_merge_and_standard_layouts() -> None:
    assert [spec.id for spec in layouts_for("plan", experimental=False)] == ["classic", "timeline"]
    assert {spec.id for spec in layouts_for("plan", experimental=True)} == {
        "mission", "bento", "retro", "clay"
    }
    assert [spec.id for spec in layouts_for("day", experimental=False)] == ["dial"]
    assert [spec.id for spec in layouts_for("day", experimental=True)] == ["one"]
    assert options_for({"options": {"one": {"look": "preset:one-paper", "lead": "next"}}}, "one") == {
        "look": "preset:one-paper", "lead": "next", "actions": "show", "daybar": "show"
    }
    for value in ("0", "7", "x", 3, None):
        assert "timeline" not in sanitize_layout({"options": {"timeline": {"fold": value}}})["options"]
        assert options_for({"options": {"timeline": {"fold": value}}}, "timeline")["fold"] == "3"
    assert options_for({"options": {"timeline": {"fold": "6"}}}, "timeline")["fold"] == "6"


def test_bad_layouts_fall_back_and_wrong_roles_do_not_load() -> None:
    shipped = {"main": "classic", "day": "dial", "options": {}}
    for raw in (None, "bento", [], {"main": 7, "day": None, "options": "x"}):
        assert sanitize_layout(raw) == shipped
    assert sanitize_layout({"main": "one", "day": "bento"}) == shipped


def test_old_colour_choices_migrate_to_the_corresponding_shared_look() -> None:
    migrated = sanitize_layout(
        {
            "main": "bento",
            "day": "one",
            "options": {"bento": {"colour": "indigo"}, "one": {"colour": "black"}},
        }
    )
    assert migrated["options"] == {
        "bento": {"look": "preset:bento-indigo"},
        "one": {"look": "preset:one-poster"},
    }
    assert sanitize_layout({"options": {"clay": {"colour": "unknown"}}})["options"]["clay"]["look"] == "your"


def test_every_legacy_colour_maps_to_a_selectable_look() -> None:
    for layout_id, colours in LEGACY_COLOURS.items():
        offered = {token for token, _label in DESIGN_LOOKS[layout_id]} | {"your"}
        assert set(colours.values()) <= offered, layout_id
        for old, token in colours.items():
            migrated = sanitize_layout({"options": {layout_id: {"colour": old}}})
            assert migrated["options"][layout_id]["look"] == token, (layout_id, old)


def test_all_curated_design_looks_pass_the_shared_colour_safety_sweep() -> None:
    failures = []
    close_accents = []
    for layout_id, curated in DESIGN_LOOKS.items():
        looks = (*curated, ("your", "Your look"))
        for (token, _label), (pack, dark, accent, surface) in itertools.product(
            looks,
            itertools.product(PACKS, (False, True), ACCENTS, ("layered", "flat")),
        ):
            worn = {"preset": "default", "knobs": {"surface": surface}}
            palette, _ = design_look(token, pack, dark, worn, accent)
            tokens = tokens_for(layout_id, token, palette)
            where = f"{layout_id}/{token}/{pack}/{dark}/{accent}/{surface}"
            failures.extend((where, failure) for failure in contrast_failures(tokens))
            if contrast(tokens["fill"], tokens["surface"]) < 1.8:
                failures.append((where, "load bar below 1.8:1 against its tile"))
            for ground in ("bg", "surface"):
                ratio = contrast(tokens["accent"], tokens[ground])
                if ratio < AA_TEXT:
                    failures.append((where, f"accent on {ground}: {ratio:.2f}"))
            gap = math.dist(_lab(tokens["accent"]), _lab(tokens["danger"]))
            if gap < 25:
                close_accents.append((where, round(gap, 1)))
    assert failures == []
    assert close_accents == []


def test_every_design_offers_a_light_look() -> None:
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


def test_contrast_audit_reports_the_pair_that_fails() -> None:
    palette = resolved_palette("light-frost", False, None)
    good = tokens_for("bento", "your", palette)
    assert contrast_failures(good) == []
    assert contrast_failures({**good, "muted": good["surface"]})[0] == "muted 1.00"
    assert contrast_failures({**good, "cta_ink": good["cta"]}) == ["cta_ink 1.00"]


def test_tokens_for_cache_reuses_a_palette_and_misses_a_changed_palette(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layouts_registry._tokens_for_cache.clear()
    calls = 0
    real = layouts_registry.match_tokens

    def counted(palette: dict) -> dict:
        nonlocal calls
        calls += 1
        return real(palette)

    monkeypatch.setattr(layouts_registry, "match_tokens", counted)
    light = resolved_palette("light-frost", False, None)
    first = tokens_for("bento", "your", light)
    assert tokens_for("timeline", "preset:timeline-paper", light) == first
    assert calls == 1
    dark = resolved_palette("dark-frost", True, None)
    assert tokens_for("bento", "your", dark) != first
    assert calls == 2
    layouts_registry._tokens_for_cache.clear()


def test_legacy_look_alias_falls_back_to_the_accounts_look_when_unknown() -> None:
    palette = resolved_palette("nocturne", True, None)
    assert design_look("preset:unknown", "nocturne", True, None)[0]["window"] == palette["window"]
