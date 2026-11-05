"""Tests for Material B3a3 colour tokens, the Slate default preset, and Inter fonts.

Written directly from the B3a3 specification tables and requirements.
"""

from __future__ import annotations

from pathlib import Path

from desktop.native.material.theme import (
    DEFAULT_PRESET,
    FONT_FILES,
    INTER,
    PRESETS,
    SIX_CLASSES,
    STATUS_COLORS,
    bar_for_category,
    paint_for_category,
    read_material_choice,
    scheme,
    theme_object,
)
from desktop.native.tokens import contrast, mix

QML_DIR = Path(__file__).resolve().parents[1] / "native" / "material" / "qml"
FONTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"

EXPECTED_NEUTRALS = {
    "light": {
        "surface": "#eef1f5",
        "surfaceContainerLowest": "#ffffff",
        "surfaceContainerLow": "#ffffff",
        "surfaceContainer": "#ffffff",
        "surfaceContainerHigh": "#ffffff",
        "surfaceContainerHighest": "#ffffff",
        "surfaceVariant": "#ffffff",
        "outlineVariant": "#e5e9f0",
        "outline": "#64748b",
        "onSurface": "#0f172a",
        "onSurfaceVariant": "#475569",
    },
    "dark": {
        "surface": "#0b0d10",
        "surfaceContainerLowest": "#14171c",
        "surfaceContainerLow": "#14171c",
        "surfaceContainer": "#14171c",
        "surfaceContainerHigh": "#14171c",
        "surfaceContainerHighest": "#14171c",
        "surfaceVariant": "#14171c",
        "outlineVariant": "#252a33",
        "outline": "#6b7280",
        "onSurface": "#ececec",
        "onSurfaceVariant": "#9a9fa8",
    },
}

EXPECTED_SLATE_ACCENTS = {
    "light": {
        "primary": "#3d6fc4",
        "onPrimary": "#ffffff",
        "secondaryContainer": "#e6edf8",
        "onSecondaryContainer": "#0f172a",
    },
    "dark": {
        "primary": "#7fa8ff",
        "onPrimary": "#0b1220",
        "secondaryContainer": "#1c2433",
        "onSecondaryContainer": "#ececec",
    },
}

EXPECTED_CLASSES = {
    "class": "#3d6fc4",
    "exercise": "#2f9e6b",
    "extra": "#0f8a8a",
    "assignments": "#a87512",
    "study": "#c2557a",
    "other": "#64748b",
}


def test_slate_is_the_default_preset_and_listed_first() -> None:
    assert DEFAULT_PRESET == "Slate"
    assert PRESETS[0] == "Slate"
    assert PRESETS == ("Slate", "Blue", "Sea", "Forest", "Gold", "Rose", "Plum")
    assert read_material_choice(None)["preset"] == "Slate"
    assert read_material_choice({})["preset"] == "Slate"
    # A saved "Blue" still loads as Blue
    assert read_material_choice({"material": {"preset": "Blue"}})["preset"] == "Blue"


def test_every_preset_has_the_b3a3_page_card_edge_text_and_muted() -> None:
    for preset in PRESETS:
        for mode in ("light", "dark"):
            s = scheme(preset, mode, "std")
            for role, expected_val in EXPECTED_NEUTRALS[mode].items():
                assert s[role] == expected_val, f"{preset}.{mode}.std {role} should be {expected_val}"


def test_slate_takes_the_b3a3_accent_and_nav_tint() -> None:
    for mode in ("light", "dark"):
        s = scheme("Slate", mode, "std")
        for role, expected_val in EXPECTED_SLATE_ACCENTS[mode].items():
            assert s[role] == expected_val, f"Slate.{mode}.std {role} should be {expected_val}"


def test_high_contrast_darkens_only_the_muted_text() -> None:
    expected_muted = {"light": "#334155", "dark": "#c4c8d0"}
    for preset in PRESETS:
        for mode in ("light", "dark"):
            std = scheme(preset, mode, "std")
            high = scheme(preset, mode, "high")
            assert high["onSurfaceVariant"] == expected_muted[mode]
            for role in (
                "surface",
                "surfaceContainerLowest",
                "surfaceContainerLow",
                "surfaceContainer",
                "surfaceContainerHigh",
                "surfaceContainerHighest",
                "surfaceVariant",
                "outlineVariant",
                "outline",
                "onSurface",
            ):
                assert high[role] == std[role]
            if preset == "Slate":
                for role in ("primary", "onPrimary", "secondaryContainer", "onSecondaryContainer"):
                    assert high[role] == std[role]


def test_status_colours_and_their_tints() -> None:
    # Dark values from the spec
    assert STATUS_COLORS["dark"]["statusDone"] == "#8fd19e"
    assert STATUS_COLORS["dark"]["statusDueSoon"] == "#f0c674"
    assert STATUS_COLORS["dark"]["statusOverdue"] == "#ff9b8f"

    # Light values reach at least 4.5:1 on #ffffff
    for name, hex_val in STATUS_COLORS["light"].items():
        assert contrast(hex_val, "#ffffff") >= 4.5, f"{name} {hex_val} contrast on #ffffff < 4.5"

    for mode in ("light", "dark"):
        s = scheme("Slate", mode, "std")
        t = theme_object(s, "comfortable", False, False)
        card = "#ffffff" if mode == "light" else "#14171c"
        for key in ("statusDone", "statusDueSoon", "statusOverdue"):
            expected_color = STATUS_COLORS[mode][key]
            assert t[key] == expected_color
            assert t[f"{key}Tint"] == mix(expected_color, card, 0.16)
            # A status word may be drawn in its colour on its own tint (Sol review of PR 6a).
            assert contrast(expected_color, t[f"{key}Tint"]) >= 4.5, f"{mode} {key} on its tint"


def test_class_colours_by_category_and_block_ink_is_never_white() -> None:
    assert len(SIX_CLASSES) == 6
    for cat, expected_bar in EXPECTED_CLASSES.items():
        assert bar_for_category(cat) == expected_bar

    # Unknown category falls back to Other
    assert bar_for_category("unknown_cat") == EXPECTED_CLASSES["other"]
    assert bar_for_category("meals") == EXPECTED_CLASSES["other"]
    assert bar_for_category("sleep") == EXPECTED_CLASSES["other"]
    assert bar_for_category("free") == EXPECTED_CLASSES["other"]

    for mode in ("light", "dark"):
        card = "#ffffff" if mode == "light" else "#14171c"
        expected_ink = "#0f172a" if mode == "light" else "#ececec"
        t = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
        assert len(t["classes"]) == 6

        for cat in SIX_CLASSES:
            fill, ink = paint_for_category(cat, mode)
            bar = bar_for_category(cat)
            assert ink != "#ffffff", f"{cat} ink must never be white"
            assert ink != bar, f"{cat} ink must never be class colour"
            assert ink == expected_ink
            assert contrast(ink, fill) >= 4.5, f"{cat} ink on fill ratio < 4.5"
            assert contrast(bar, card) >= 3.0, f"{cat} bar on card ratio < 3.0"
            assert t["classes"][cat] == {"bar": bar, "fill": fill, "ink": ink}


def test_the_focus_ring_reaches_3_to_1_on_card_and_page() -> None:
    for mode in ("light", "dark"):
        t = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
        focus_ring = str(t["focusRing"])
        card = str(t["card"])
        page = str(t["page"])
        edge = str(t["edge"])
        assert focus_ring == t["primary"]
        assert contrast(focus_ring, card) >= 3.0, f"focusRing vs card in {mode} < 3:1"
        assert contrast(focus_ring, page) >= 3.0, f"focusRing vs page in {mode} < 3:1"
        assert card == ("#ffffff" if mode == "light" else "#14171c")
        assert page == ("#eef1f5" if mode == "light" else "#0b0d10")
        assert edge == ("#e5e9f0" if mode == "light" else "#252a33")


def test_material_fonts_are_inter_and_roboto_flex_is_gone() -> None:
    assert FONT_FILES == ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf")
    assert INTER == "Inter"

    m3font_text = (QML_DIR / "components" / "M3Font.qml").read_text(encoding="utf-8")
    assert "Inter-Regular.ttf" in m3font_text
    assert "Inter-Medium.ttf" in m3font_text
    assert "Inter-SemiBold.ttf" in m3font_text
    assert 'family: regular.name !== "" ? regular.name : "Inter"' in m3font_text
    assert "Roboto Flex" not in m3font_text
    assert "RobotoFlex" not in m3font_text

    for qml_path in QML_DIR.rglob("*.qml"):
        content = qml_path.read_text(encoding="utf-8")
        assert "Roboto Flex" not in content, f"{qml_path} still contains 'Roboto Flex'"
        assert "RobotoFlex" not in content, f"{qml_path} still contains 'RobotoFlex'"

    for font_file in FONTS_DIR.glob("RobotoFlex*"):
        assert not font_file.exists(), f"RobotoFlex file {font_file} was not removed"
