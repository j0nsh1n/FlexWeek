"""Look knobs and pack pairing. Device-only knobs never become preference fields."""

from __future__ import annotations

from desktop.native.look import (
    effective_look,
    pack_axis,
    pack_stylesheet,
    resolved_pack_theme,
    sanitize_look,
)


def test_unknown_knobs_and_packs_fall_back() -> None:
    clean = sanitize_look({"preset": "neon", "knobs": {"font": "comic", "text": "large"}})
    assert clean["preset"] == "default"
    assert clean["knobs"] == {"text": "large"}
    assert effective_look(clean)["font"] == "sans"
    assert effective_look(clean)["text"] == "large"


def test_terminal_preset_layers_before_knob_overrides() -> None:
    look = sanitize_look({"preset": "terminal", "knobs": {"text": "large"}})
    effective = effective_look(look)
    assert effective["font"] == "mono"
    assert effective["corners"] == "sharp"
    assert effective["text"] == "large"


def test_pack_axis_pairs_frost_with_slate_or_nocturne() -> None:
    assert pack_axis("light-frost") == "slate"
    assert pack_axis("dark-frost") == "nocturne"
    assert pack_axis("system") == "system"
    assert resolved_pack_theme("system", True) == "nocturne"
    assert resolved_pack_theme("system", False) == "slate"
    assert resolved_pack_theme("slate", True) == "slate"


def test_stylesheet_mentions_the_resolved_palette() -> None:
    sheet = pack_stylesheet("nocturne", False, {"preset": "default", "knobs": {}}, "sky")
    assert "#121826" in sheet
    assert "#0ea5e9" in sheet
    terminal = pack_stylesheet("slate", False, {"preset": "terminal", "knobs": {}}, "default")
    assert "#000000" in terminal
    assert "monospace" in terminal
