# ruff: noqa: F811
"""Which surface a look file chooses (Widgets styles or Material 3), and how the Material choice
(preset, mode, contrast, density) is read from it.

Expected words are written out here. They are not read back from the function under test.
"""

from __future__ import annotations

from desktop.native.layouts.registry import (
    SURFACE_DEFAULT,
    SURFACES,
    sanitize_layout,
    sanitize_surface,
)
from desktop.native.material.theme import read_material_choice, resolved_mode


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


def test_a_missing_or_unknown_material_choice_is_slate_system_standard_comfortable() -> None:
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
