"""The colours each look is made of: the neutral light and dark pages, the one blue every look wears by
default, what an accent swatch changes, and what keeps the surfaces of a look apart."""

from __future__ import annotations

from itertools import product

from desktop.native.calendar import CATEGORIES
from desktop.native.look import (
    AA_TEXT,
    ACCENTS,
    DESIGN_PALETTE_PRESETS,
    LOOK_PRESETS,
    PACKS,
    category_paint,
    contrast,
    look_menu_items,
    pack_stylesheet,
    palette_from_tokens,
    resolved_palette,
)
from desktop.native.tokens import mix, oklch_of
from desktop.tests.settings.support_look import look_of


def test_light_and_dark_are_the_neutral_surfaces_of_decision_2() -> None:
    light = resolved_palette("light-frost", False, None)
    dark = resolved_palette("dark-frost", True, None)
    assert (light["window"], light["panel"]) == ("#f7f8fa", "#ffffff")
    assert (light["text"], light["muted"]) == ("#111827", "#5b6474")
    assert (dark["window"], dark["panel"]) == ("#111315", "#1a1d21")
    assert (dark["text"], dark["muted"]) == ("#e8eaed", "#9aa1ab")
    for palette in (light, dark):
        surfaces = [palette[key] for key in ("panel", "card_2", "field", "grid")]
        assert len(set(surfaces)) == 4
        assert contrast(palette["hairline"], palette["panel"]) >= 1.55


def test_every_look_but_high_contrast_wears_flexweeks_blue_by_default() -> None:
    """Decision 1 of 0.17: one accent, the icon's blue, #3d6fc4 on a light look and #7fa8ff on a
    dark one. A student saw three accents before placing any homework. Where a tinted page needs it for
    the accent's words to read, as Slate's and Pastel's do, it is the blue's darker shade: the same hue,
    a little lower in lightness."""
    for pack, system_dark, preset in product(PACKS, (False, True), LOOK_PRESETS):
        palette = resolved_palette(pack, system_dark, look_of(preset))
        if preset == "high-contrast":
            assert (palette["accent"], palette["accent_ink"]) == ("#ffd400", "#000000")
            sheet = pack_stylesheet(pack, system_dark, look_of(preset))
            assert "qproperty-shade: 0;" in sheet
            assert "border-bottom: 4px solid" in sheet
            continue
        if preset == "paper":
            assert palette["accent"] == "#1f3a68"
            continue
        wanted = "#7fa8ff" if palette["axis"] == "dark" else "#3d6fc4"
        where = (pack, system_dark, preset)
        if palette["accent"] != wanted:
            light, _chroma, hue = oklch_of(palette["accent"])
            wanted_light, _wanted_chroma, wanted_hue = oklch_of(wanted)
            assert abs(hue - wanted_hue) < 1.5 and 0 < wanted_light - light < 0.02, where
            assert contrast(wanted, palette["window"]) < AA_TEXT, where
        assert contrast(palette["accent"], palette["window"]) >= AA_TEXT, where
    assert resolved_palette("light-frost", False, None)["accent"] == "#3d6fc4"
    assert resolved_palette("slate", False, None)["accent"] == "#3b6cc1"


def test_an_accent_always_changes_the_accent() -> None:
    """Sky once equalled the Light frost default, so choosing it did nothing. High contrast is the
    one look whose accent no swatch replaces: its yellow is part of its contrast."""
    for pack, system_dark, preset in product(PACKS, (False, True), LOOK_PRESETS):
        plain = resolved_palette(pack, system_dark, look_of(preset))["accent"]
        if preset == "high-contrast":
            for accent in ACCENTS:
                chosen = resolved_palette(pack, system_dark, look_of(preset), accent)
                assert (chosen["accent"], chosen["accent_ink"]) == ("#ffd400", "#000000"), accent
            continue
        seen = {plain}
        for accent in ACCENTS:
            if accent == "default":
                continue
            chosen = resolved_palette(pack, system_dark, look_of(preset), accent)["accent"]
            assert chosen not in seen, f"{accent} on {pack}/{preset} repeats {chosen}"
            seen.add(chosen)


def test_a_students_accent_wins_over_the_presets_own() -> None:
    assert resolved_palette("slate", False, look_of("terminal"))["accent"] == "#7fa8ff"
    chosen = resolved_palette("slate", False, look_of("terminal"), "sky")
    # Terminal is a dark look whatever the pack underneath, so it takes the dark-axis sky and its ink.
    assert (chosen["accent"], chosen["accent_ink"]) == ("#38bdf8", "#0b1224")
    clay = resolved_palette("slate", False, look_of("default"), "sky", palette_preset="clay-lavender")
    assert (clay["accent"], clay["accent_ink"]) == ("#0369a1", "#ffffff")


def test_ink_is_papers_night_on_any_pack() -> None:
    """0.16's Ink followed the pack between a light and a dark sheet. 0.17's is Paper's night
    counterpart (looks.css): charcoal and warm ivory whatever the pack, and Paper is its day."""
    for pack, system_dark in (("slate", False), ("nocturne", True), ("light-frost", False)):
        ink = resolved_palette(pack, system_dark, look_of("ink"))
        paper = resolved_palette(pack, system_dark, look_of("paper"))
        assert (ink["axis"], ink["window"], ink["text"]) == ("dark", "#1c1b19", "#f3eee3"), pack
        assert (paper["axis"], paper["window"], paper["text"]) == ("light", "#f7f0e1", "#1a1a1a"), pack


def test_flat_surface_has_no_raised_panels_and_layered_does() -> None:
    frost = resolved_palette("nocturne", True, look_of("default"))
    flat = resolved_palette("nocturne", True, look_of("default", surface="flat"))
    assert frost["panel"] != frost["window"]
    assert flat["panel"] == flat["window"] == frost["window"]
    assert flat["field"] == flat["window"]


def test_paper_and_pastel_are_light_looks_on_any_pack_and_close_the_menu() -> None:
    _standard, experimental = look_menu_items()
    assert [name for name, _label, _kind in experimental][-3:] == ["paper", "ink", "pastel"]
    for preset in ("paper", "pastel"):
        for pack, system_dark in (("nocturne", True), ("dark-frost", True), ("slate", False)):
            palette = resolved_palette(pack, system_dark, look_of(preset))
            assert palette["axis"] == "light", f"{preset} on {pack}"
            assert palette["accent"] == resolved_palette("slate", False, look_of(preset))["accent"]
        # A chosen accent therefore takes its light-axis colour, even over a dark pack.
        chosen = resolved_palette("nocturne", True, look_of(preset), "sea")
        assert (chosen["accent"], chosen["accent_ink"]) == ("#0f766e", "#ffffff")


def test_the_seven_looks_keep_their_pages_and_separate_their_surfaces() -> None:
    """Each look keeps the page and ink that name it. Cards, fields and the grid are no longer one
    colour, and a hairline can be seen without becoming the loudest thing on the page. Poster keeps
    its black rules. High contrast is not one of these seven."""
    identity = {
        ("slate", "default"): {"window": "#eef1f5", "panel": "#ffffff", "grid": "#ffffff", "text": "#0f172a"},
        ("nocturne", "default"): {"window": "#0a0e27", "text": "#e0e4f0"},
        ("system", "paper"): {"window": "#f7f0e1", "panel": "#fbf6ea", "text": "#1a1a1a"},
        ("system", "ink"): {"window": "#1c1b19", "text": "#f3eee3"},
        ("system", "terminal"): {"window": "#0d1117", "text": "#c9d1d9"},
        ("system", "poster"): {"window": "#fff8e7", "text": "#111111", "hairline": "#111111"},
        ("system", "pastel"): {"window": "#f3ecff", "text": "#1e1b2e"},
    }
    for (pack, preset), anchors in identity.items():
        palette = resolved_palette(pack, False, look_of(preset))
        assert {key: palette[key] for key in anchors} == anchors, (pack, preset)
        surfaces = [palette[key] for key in ("panel", "card_2", "field", "grid")]
        assert len(set(surfaces)) >= 3, (pack, preset)
        if preset == "poster":
            continue
        edge = contrast(palette["hairline"], palette["panel"])
        assert edge >= 1.55, (pack, preset, edge)
        marks = [contrast(category_paint(key, palette)[1], palette["panel"]) for key in CATEGORIES]
        assert edge < min(marks), (pack, preset, edge)


def test_design_palettes_separate_the_card_the_field_and_the_grid() -> None:
    """A design keeps its page. The card, the nested card, the field and the grid are not one
    surface, and a quiet hairline stays quieter than the category marks. Retro keeps its heavy
    rules and one white for the field and the grid."""
    for preset in sorted(DESIGN_PALETTE_PRESETS):
        palette = resolved_palette("system", False, look_of(preset))
        if preset == "retro-teal":
            assert palette["field"] == palette["grid"]
            assert contrast(palette["hairline"], palette["panel"]) > 1.55
            continue
        surfaces = [palette[key] for key in ("panel", "card_2", "field", "grid")]
        assert len(set(surfaces)) == 4, preset
        edge = contrast(palette["hairline"], palette["panel"])
        assert edge >= 1.55, (preset, edge)
        marks = [contrast(category_paint(key, palette)[1], palette["panel"]) for key in CATEGORIES]
        assert edge < min(marks), (preset, edge, min(marks))


def test_paper_draws_the_family_quieter_and_poster_bolder() -> None:
    """looks.css: Paper's fills at chroma 0.035, Poster's at lightness 0.88 and chroma 0.09. The
    marks stay the family's, so an edge or outline is the same colour in every light look."""
    light = resolved_palette("light-frost", False, None)
    paper = resolved_palette("system", False, look_of("paper"))
    poster = resolved_palette("system", False, look_of("poster"))
    for key in CATEGORIES:
        plain, mark = category_paint(key, light)
        quiet, quiet_mark = category_paint(key, paper)
        bold, bold_mark = category_paint(key, poster)
        assert mark == quiet_mark == bold_mark, key
        if key == "free":
            continue
        assert oklch_of(quiet)[1] < oklch_of(plain)[1] < oklch_of(bold)[1], key
        assert oklch_of(bold)[0] < oklch_of(plain)[0], key


def test_posters_week_rule_is_its_own_colour_not_the_hairline() -> None:
    """U11: the week's rule colour in Poster is 14% of black over its page, not the hairline's black."""
    palette = resolved_palette("system", False, look_of("poster"))
    week_rule = palette.get("rule") or palette["hairline"]
    assert week_rule == mix("#111111", "#fff8e7", 0.14)
    assert week_rule != palette["hairline"]


def test_a_design_page_falls_back_to_readable_ink_when_its_own_ink_is_too_light() -> None:
    tokens = {
        "line": "#dddddd",
        "bg": "#ffffff",
        "bg_ink": "#eeeeee",
        "bg_muted": "#777777",
        "surface": "#ffffff",
        "text": "#000000",
        "muted": "#444444",
        "accent": "#0055aa",
        "accent_ink": "#ffffff",
        "danger": "#aa0000",
    }
    page = palette_from_tokens(tokens, {"window": "#ffffff", "text": "#000000"})
    assert (page["window"], page["text"], page["muted"]) == (
        tokens["surface"], tokens["text"], tokens["muted"]
    )
    assert contrast(page["text"], page["window"]) >= AA_TEXT
