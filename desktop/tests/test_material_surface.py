"""Material 3's look file and colour rules, checked against the spec's own numbers.

Expected colours, densities and clock words are written out here. They are not
read back from the function under test.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from desktop.native.layouts.registry import (
    SURFACE_DEFAULT,
    SURFACES,
    sanitize_layout,
    sanitize_surface,
)
from desktop.native.material.theme import (
    DENSITY,
    HIGH_CONTRAST_STROKE,
    category_paint,
    event_category,
    paint_for_category,
    read_material_choice,
    resolved_mode,
    scheme,
    stroke_for,
    theme_object,
    tokens_path,
)
from desktop.native.tokens import contrast
from desktop.native.weekmodel import clock_label, set_clock_24h

# The spec's category fills: class colour mixed 14% into white (light) or 24% into dark card (#14171c).
SCHOOL = {"light": "#e4ebf7", "dark": "#1e2c44"}
SOCCER = {"light": "#e1f0e9", "dark": "#1a352e"}
CLUBS = {"light": "#ddefef", "dark": "#133336"}
READING = {"light": "#f6e7ec", "dark": "#3e2633"}
HOMEWORK = {"light": "#f3ecde", "dark": "#382e1a"}
SPEC_FILLS = {
    "school": SCHOOL,
    "soccer": SOCCER,
    "reading": READING,
    "homework": HOMEWORK,
}
PRESET_NAMES = ("Slate", "Blue", "Sea", "Forest", "Gold", "Rose", "Plum")
INK_DARK = "#0f172a"
INK_LIGHT = "#ececec"


@pytest.fixture()
def clock_restored() -> Iterator[None]:
    set_clock_24h(True)
    yield
    set_clock_24h(True)


def test_surface_names_and_the_default() -> None:
    assert SURFACES == ("widgets", "material")
    assert SURFACE_DEFAULT == "widgets"


def test_an_old_look_file_with_no_surface_is_the_widgets_styles() -> None:
    assert sanitize_surface({"preset": "paper", "layout": {"main": "timeline"}}) == "widgets"
    assert sanitize_surface({}) == "widgets"
    assert sanitize_surface(None) == "widgets"


def test_an_unknown_surface_is_the_widgets_styles() -> None:
    assert sanitize_surface({"surface": "nope"}) == "widgets"
    assert sanitize_surface({"surface": 7}) == "widgets"
    assert sanitize_surface({"surface": None}) == "widgets"


def test_material_is_only_the_top_level_surface_key() -> None:
    assert sanitize_surface({"surface": "material"}) == "material"
    assert sanitize_surface("material") == "material"
    # A surface buried inside the layout is not the window's surface.
    buried = {"layout": {"main": "classic", "surface": "material"}}
    assert sanitize_surface(buried) == "widgets"


def test_sanitize_layout_still_returns_only_the_layout() -> None:
    cleaned = sanitize_layout(
        {
            "main": "timeline",
            "day": "one",
            "options": {"one": {"daybar": "hide"}},
            "surface": "material",
        }
    )
    assert set(cleaned) == {"main", "day", "options"}
    assert cleaned["main"] == "timeline"
    assert cleaned["day"] == "one"
    assert cleaned["options"] == {"one": {"daybar": "hide"}}


def test_seven_presets_each_have_light_dark_standard_and_high_contrast() -> None:
    loaded = json.loads(tokens_path().read_text(encoding="utf-8"))
    assert len(loaded) == 28
    for preset in PRESET_NAMES:
        for mode in ("light", "dark"):
            for contrast_name in ("std", "high"):
                key = f"{preset}.{mode}.{contrast_name}"
                assert key in loaded
                expected_primary = (
                    "#3d6fc4" if mode == "light" else "#7fa8ff"
                ) if preset == "Slate" else loaded[key]["primary"]
                assert scheme(preset, mode, contrast_name)["primary"] == expected_primary


def test_blue_light_standard_is_the_shipped_scheme() -> None:
    colours = scheme("Blue", "light", "std")
    assert colours["primary"] == "#425e91"
    assert colours["surface"] == "#eef1f5"
    assert colours["onSurface"] == "#0f172a"


# The component README's roles, written out here so a dropped key is not also dropped from the check.
THEME_KEYS = (
    "primary",
    "onPrimary",
    "primaryContainer",
    "onPrimaryContainer",
    "secondary",
    "onSecondary",
    "secondaryContainer",
    "onSecondaryContainer",
    "tertiary",
    "onTertiary",
    "tertiaryContainer",
    "onTertiaryContainer",
    "error",
    "onError",
    "errorContainer",
    "onErrorContainer",
    "surface",
    "onSurface",
    "onSurfaceVariant",
    "surfaceContainerLowest",
    "surfaceContainerLow",
    "surfaceContainer",
    "surfaceContainerHigh",
    "surfaceContainerHighest",
    "surfaceVariant",
    "outline",
    "outlineVariant",
    "inverseSurface",
    "inverseOnSurface",
    "inversePrimary",
)


def test_the_theme_object_carries_every_role_and_the_ink_aliases() -> None:
    theme = theme_object(scheme("Blue", "light", "std"), "comfortable", False, False)
    for key in THEME_KEYS:
        assert theme[key] == scheme("Blue", "light", "std")[key]
    assert theme["primary"] == "#425e91"
    assert theme["onSurface"] == "#0f172a"
    assert theme["inkSurface"] == "#0f172a"
    assert theme["inkPrimary"] == "#ffffff"
    assert theme["inkMuted"] == "#475569"
    assert theme["inverseOnSurface"] == "#f0f0f7"
    assert "inkInverseSurface" not in theme
    assert theme["density"] == "comfortable"
    assert theme["reduceMotion"] is False
    assert theme["highContrast"] is False


def test_a_missing_or_unknown_material_choice_is_blue_system_standard_comfortable() -> None:
    blank = {"preset": "Slate", "mode": "system", "contrast": "std", "density": "comfortable"}
    assert read_material_choice(None) == blank
    assert read_material_choice({}) == blank
    assert read_material_choice({"material": "nope"}) == blank
    assert read_material_choice({"preset": "Sea"}) == blank
    chosen = read_material_choice(
        {"material": {"preset": "Sea", "mode": "dark", "contrast": "high", "density": "compact"}}
    )
    assert chosen == {"preset": "Sea", "mode": "dark", "contrast": "high", "density": "compact"}
    unknown = read_material_choice(
        {"material": {"preset": "Mauve", "mode": "dim", "contrast": "max", "density": "roomy"}}
    )
    assert unknown == blank


def test_system_mode_follows_the_worn_axis_and_an_explicit_mode_wins() -> None:
    assert resolved_mode("system", True) == "dark"
    assert resolved_mode("system", False) == "light"
    assert resolved_mode("light", True) == "light"
    assert resolved_mode("dark", False) == "dark"


def test_event_block_categories_use_the_blocks_own_names() -> None:
    assert event_category("class") == "class"
    assert event_category("exercise") == "exercise"
    assert event_category("extra") == "extra"
    assert event_category("study") == "study"
    assert event_category("assignments") == "assignments"
    assert event_category("meal") == "other"


def test_an_unknown_preset_mode_or_contrast_is_refused() -> None:
    with pytest.raises(KeyError):
        scheme("Mauve", "light", "std")
    with pytest.raises(KeyError):
        scheme("Blue", "dim", "std")
    with pytest.raises(KeyError):
        scheme("Blue", "light", "max")


def test_density_and_high_contrast_stroke() -> None:
    assert DENSITY["comfortable"] == {"hour_row": 56, "settings_row_pad": 16, "card_pad": 12}
    assert DENSITY["compact"] == {"hour_row": 44, "settings_row_pad": 10, "card_pad": 8}
    assert stroke_for("high") == HIGH_CONTRAST_STROKE == 1.5
    assert stroke_for("std") == 0.0


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_category_fills_are_the_spec_colours(mode: str) -> None:
    for role, fills in SPEC_FILLS.items():
        fill, ink = category_paint(role, mode)
        assert fill == fills[mode]
        assert ink in {INK_DARK, INK_LIGHT}
        assert contrast(fill, ink) >= 4.5


def test_week_categories_use_those_fills() -> None:
    assert paint_for_category("class", "light")[0] == SCHOOL["light"]
    assert paint_for_category("exercise", "dark")[0] == SOCCER["dark"]
    assert paint_for_category("extra", "light")[0] == CLUBS["light"]
    assert paint_for_category("study", "dark")[0] == READING["dark"]
    assert paint_for_category("assignments", "light")[0] == HOMEWORK["light"]


def test_clock_words_follow_the_24_hour_switch(clock_restored: None) -> None:
    del clock_restored
    set_clock_24h(True)
    assert clock_label(15 * 60 + 40) == "15:40"
    assert clock_label(8 * 60) == "08:00"
    assert clock_label(19 * 60) == "19:00"
    set_clock_24h(False)
    assert clock_label(15 * 60 + 40) == "3:40 PM"
    assert clock_label(8 * 60) == "8:00 AM"
    assert clock_label(19 * 60) == "7:00 PM"
