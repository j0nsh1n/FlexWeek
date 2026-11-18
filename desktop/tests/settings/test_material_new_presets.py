"""High contrast, Paper, Ink and Terminal as Material presets, and the accent laid over a preset.

Readability is the spec's: text at 4.5 to 1 against the page and its cards, 7 to 1 for High contrast.
Each look supports one mode (High contrast, Ink and Terminal dark, Paper light), as look.py's
palettes do."""

from __future__ import annotations

import pytest

from desktop.native.material.theme import (
    ACCENT_LOCKED,
    ACCENTS,
    CONTRASTS,
    ONE_MODE,
    PRESET_LOOK,
    PRESETS,
    accented,
    read_accent,
    scheme,
    shown_font,
)
from desktop.native.tokens import contrast, luminance

NEW = ("High contrast", "Paper", "Ink", "Terminal")


def _floor(preset: str) -> float:
    return 7.0 if preset == "High contrast" else 4.5


@pytest.mark.parametrize("preset", NEW)
@pytest.mark.parametrize("level", CONTRASTS)
def test_text_reads_on_the_page_and_the_cards(preset: str, level: str) -> None:
    colours = scheme(preset, ONE_MODE[preset], level)
    floor = _floor(preset)
    for ground in ("surface", "surfaceContainer", "surfaceContainerLow", "surfaceVariant"):
        assert contrast(colours["onSurface"], colours[ground]) >= floor, (preset, level, ground)
        assert contrast(colours["onSurfaceVariant"], colours[ground]) >= floor, (preset, level, ground)


@pytest.mark.parametrize("preset", NEW)
@pytest.mark.parametrize("level", CONTRASTS)
def test_every_ink_reads_on_the_fill_it_sits_on(preset: str, level: str) -> None:
    colours = scheme(preset, ONE_MODE[preset], level)
    floor = _floor(preset)
    for ink, fill in (
        ("onPrimary", "primary"),
        ("onPrimaryContainer", "primaryContainer"),
        ("onSecondaryContainer", "secondaryContainer"),
        ("onError", "error"),
        ("onErrorContainer", "errorContainer"),
        ("inverseOnSurface", "inverseSurface"),
    ):
        assert contrast(colours[ink], colours[fill]) >= floor, (preset, level, ink)


@pytest.mark.parametrize("preset", NEW)
def test_lines_that_mark_a_control_are_seen_at_three_to_one(preset: str) -> None:
    colours = scheme(preset, ONE_MODE[preset], "std")
    assert contrast(colours["outline"], colours["surface"]) >= 3.0
    assert contrast(colours["outline"], colours["surfaceContainer"]) >= 3.0


def test_each_new_look_is_the_mode_look_py_gives_it() -> None:
    assert ONE_MODE == {"High contrast": "dark", "Paper": "light", "Ink": "dark", "Terminal": "dark"}
    for preset, mode in ONE_MODE.items():
        dark = luminance(scheme(preset, mode, "std")["surface"]) < 0.18
        assert dark == (mode == "dark"), preset


@pytest.mark.parametrize("preset", NEW)
def test_asking_for_the_other_mode_still_gives_the_looks_own(preset: str) -> None:
    other = "light" if ONE_MODE[preset] == "dark" else "dark"
    assert scheme(preset, other, "std") == scheme(preset, ONE_MODE[preset], "std")


def test_the_looks_own_colours_are_the_ones_in_look_py() -> None:
    assert scheme("High contrast", "dark", "std")["primary"] == "#ffd400"
    assert scheme("High contrast", "dark", "std")["surface"] == "#000000"
    assert scheme("Paper", "light", "std")["surface"] == "#f7f0e1"
    assert scheme("Ink", "dark", "std")["surface"] == "#1c1b19"
    assert scheme("Terminal", "dark", "std")["surface"] == "#0d1117"


def test_the_new_looks_are_listed_after_the_original_presets() -> None:
    assert PRESETS[-4:] == NEW
    assert PRESETS[:7] == ("Slate", "Blue", "Sea", "Forest", "Gold", "Rose", "Plum")


def test_a_looks_font_is_its_default_and_the_students_own_choice_wins() -> None:
    assert PRESET_LOOK["Terminal"]["font"] == "mono" and PRESET_LOOK["Terminal"]["corner"] == 0
    assert PRESET_LOOK["Paper"]["font"] == "serif" and PRESET_LOOK["Ink"]["font"] == "serif"
    assert PRESET_LOOK["High contrast"]["corner"] == 0
    assert shown_font("Terminal", "") == "mono"
    assert shown_font("Terminal", "sans") == "sans"
    assert shown_font("Slate", "") == "sans"


@pytest.mark.parametrize("accent", [name for name in ACCENTS if name != "default"])
@pytest.mark.parametrize("preset", [name for name in PRESETS if name not in ACCENT_LOCKED])
@pytest.mark.parametrize("level", CONTRASTS)
def test_an_accent_over_any_preset_keeps_its_ink_readable(accent: str, preset: str, level: str) -> None:
    mode = ONE_MODE.get(preset, "light")
    base = scheme(preset, mode, level)
    found = accented(base, accent, preset, mode, level)
    assert found["primary"] != base["primary"]
    assert contrast(found["onPrimary"], found["primary"]) >= 4.5
    assert contrast(found["onPrimaryContainer"], found["primaryContainer"]) >= 4.5
    assert contrast(found["onSecondaryContainer"], found["secondaryContainer"]) >= 4.5


@pytest.mark.parametrize("preset", PRESETS)
def test_same_as_preset_changes_nothing(preset: str) -> None:
    mode = ONE_MODE.get(preset, "dark")
    base = scheme(preset, mode, "std")
    assert accented(base, "default", preset, mode, "std") == base


def test_high_contrast_keeps_its_yellow_under_any_accent() -> None:
    base = scheme("High contrast", "dark", "std")
    for accent in ACCENTS:
        assert accented(base, accent, "High contrast", "dark", "std") == base


def test_an_unknown_saved_accent_reads_as_same_as_preset() -> None:
    assert read_accent({"accent": "neon"}) == "default"
    assert read_accent({"accent": "sea"}) == "sea"
    assert read_accent(None) == "default"
