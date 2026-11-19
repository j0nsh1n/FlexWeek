# ruff: noqa: F811
"""Which surface a look file chooses (always Material 3), and how the Material choice
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


def test_material_is_the_only_surface_and_the_default() -> None:
    assert SURFACES == ("material",)
    assert SURFACE_DEFAULT == "material"


def test_every_look_file_opens_material() -> None:
    """The Widgets value an older build wrote, a missing key, junk, and a surface buried in the layout all
    give Material: a student has no way to reach the Widgets styles."""
    files = [
        {"surface": "widgets"},
        {"preset": "paper", "layout": {"main": "timeline"}},
        {},
        None,
        {"surface": "nope"},
        {"surface": 7},
        {"surface": None},
        {"surface": "material"},
        "widgets",
        {"layout": {"main": "classic", "surface": "widgets"}},
    ]
    assert [sanitize_surface(stored) for stored in files] == ["material"] * len(files)


def test_sanitize_layout_still_returns_only_the_layout() -> None:
    cleaned = sanitize_layout(
        {
            "main": "timeline",
            "day": "dial",
            "options": {"timeline": {"density": "compact"}},
            "surface": "material",
        }
    )
    assert set(cleaned) == {"main", "day", "options"}
    assert cleaned["main"] == "timeline"
    assert cleaned["day"] == "dial"
    assert cleaned["options"] == {"timeline": {"density": "compact"}}


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
