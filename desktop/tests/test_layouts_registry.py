"""The design registry keeps each design's curated looks and sanitizes stored choices."""

from __future__ import annotations

import pytest

from desktop.native.layouts.registry import (
    DESIGN_LOOKS,
    LAYOUTS,
    LEGACY_COLOURS,
    LEVELS,
    options_for,
    sanitize_layout,
    tokens_for,
)
from desktop.native.look import contrast, design_look, resolved_palette


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
    assert options_for(None, "classic")["look"] == "pack:light-frost"
    assert options_for(None, "dial")["look"] == "preset:dial-midnight"


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


@pytest.mark.parametrize("layout_id", LAYOUTS)
def test_each_design_uses_the_selected_look_tokens(layout_id: str) -> None:
    for token, _label in (*DESIGN_LOOKS[layout_id], ("your", "Your look")):
        palette, _look = design_look(
            token, "light-frost", False, {"preset": "default", "knobs": {}}
        )
        tokens = tokens_for(layout_id, token, palette)
        assert tokens["bg"] == palette["window"]
        assert tokens["surface"] == palette["panel"]
        assert tokens["accent"] == palette["accent"]
        assert contrast(tokens["text"], tokens["surface"]) >= 4.5


def test_the_same_look_has_the_same_shared_tokens_in_each_design() -> None:
    palette = resolved_palette("dark-frost", True, None)
    expected = tokens_for("classic", "your", palette)
    for layout_id in LAYOUTS:
        assert tokens_for(layout_id, "your", palette) == expected
