"""The shared design system's numbers: shadows, the category fill, the type scale and the stylesheet's
shape. How the colours look (contrast, spread of lightness, colour blindness) is judged on the
pictures in pictures/screens_settings_tokens.py.

The category colours worked out from their hues, and the five sizes of the Text knob, are held by the
engine's desk_tokens.rs.
"""

from __future__ import annotations

import re
from collections import defaultdict
from itertools import product
from pathlib import Path

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.calendar import CATEGORIES
from desktop.native.elevation import flatten, lift
from desktop.native.hours.rail import Colours
from desktop.native.layouts.registry import MATCH, tokens_for
from desktop.native.look import category_paint, pack_stylesheet, resolved_palette
from desktop.native.material.theme import _schemes
from desktop.native.tokens import (
    FILL,
    HOMEWORK_DARKER,
    SHADOW_LARGE,
    SHADOW_SMALL,
    TEXT_SCALE,
    TYPE_PT,
    WEIGHT_NUMBER,
    WEIGHT_REGULAR,
    WEIGHT_STRONG,
    Shadow,
    family_colours,
    oklch_of,
    type_pt,
)
from desktop.tests.settings.support_tokens import CASES, LOOKS, look_for, palette_for
from desktop.tests.window_support import qapp  # noqa: F401


def test_the_small_shadow_is_deep_enough_to_read_and_the_large_one_stays() -> None:
    """A faint shadow reads as a dirty edge. The small one stays small: one pixel down, a short blur,
    and a light opacity a student can see. The large shadow, and the darker opacity a dark look
    already uses, do not move."""
    assert Shadow(12, 32, 0.16, 0.50) == SHADOW_LARGE
    assert SHADOW_SMALL.y == 1
    assert SHADOW_SMALL.dark_opacity == 0.40
    assert 2 <= SHADOW_SMALL.blur <= 6
    assert 0.12 <= SHADOW_SMALL.opacity <= 0.18
    assert round(255 * SHADOW_SMALL.opacity) >= 30


def test_a_lifted_card_casts_the_small_shadow_and_stronger_on_a_dark_look(qapp: QApplication) -> None:  # noqa: F811
    card = QWidget()
    effect = lift(card, SHADOW_SMALL)
    assert card.graphicsEffect() is effect
    assert (effect.offset().y(), effect.blurRadius()) == (1, 4)
    assert effect.color() == QColor(0, 0, 0, 36)
    dark = lift(card, SHADOW_LARGE, dark=True)
    assert card.graphicsEffect() is dark
    assert (dark.offset().y(), dark.blurRadius(), dark.color().alpha()) == (12, 32, 128)
    flatten(card)
    assert card.graphicsEffect() is dark
    assert not dark.isEnabled()
    assert (dark.blurRadius(), dark.color().alpha()) == (0, 0)
    again = lift(card, SHADOW_SMALL)
    assert again is dark
    assert dark.isEnabled()
    assert (dark.offset().y(), dark.blurRadius()) == (1, 4)


def test_a_computed_fill_is_richer_than_the_saved_family() -> None:
    """A hue the student chooses sits a little deeper and richer than the family the engine still
    returns. Light still paints that saved family, homework's mark stays the darker one, and the hue
    does not move."""
    light, chroma = FILL
    assert 0.88 <= light < 0.92
    assert 0.05 < chroma < 0.07
    stock = resolved_palette("light-frost", False, {"preset": "default", "knobs": {}})
    for key in ("class", "study", "assignments", "sleep"):
        assert category_paint(key, stock) == (CATEGORIES[key]["color"], CATEGORIES[key]["mark"]), key
    chosen = resolved_palette(
        "system",
        False,
        {
            "preset": "default",
            "knobs": {},
            "custom": {"base": "light", "categories": {"class": {"hue": 140}, "assignments": {"hue": 140}}},
        },
    )
    fill, mark = category_paint("class", chosen)
    saved_fill, saved_mark = family_colours(140)["light"]
    assert oklch_of(fill)[0] < oklch_of(saved_fill)[0]
    assert oklch_of(fill)[1] > oklch_of(saved_fill)[1]
    assert oklch_of(fill)[2] == pytest.approx(oklch_of(saved_fill)[2], abs=1)
    assert oklch_of(mark)[2] == pytest.approx(oklch_of(saved_mark)[2], abs=1)
    homework = category_paint("assignments", chosen)[1]
    assert oklch_of(mark)[0] - oklch_of(homework)[0] == pytest.approx(HOMEWORK_DARKER, abs=0.01)


@pytest.mark.parametrize("name", ["Dark", "Nocturne", "Ink", "Terminal"])
def test_the_rails_homework_red_keeps_the_categorys_hue_on_the_dark_surfaces(name: str) -> None:
    """The rail draws a lighter red in the dark looks (3 to 1 on its surfaces, judged on the
    pictures), and the same hue as the category's own mark, which stays as it was."""
    palette = palette_for(name)
    rail = Colours.of(palette).homework
    mark = category_paint("assignments", palette)[1]
    assert abs(oklch_of(rail)[2] - oklch_of(mark)[2]) < 3, (rail, mark)


@pytest.mark.parametrize("name", ["Light", "Slate", "High contrast"])
def test_the_rails_homework_red_is_the_categorys_own_in_the_light_looks(name: str) -> None:
    palette = palette_for(name)
    assert Colours.of(palette).homework == category_paint("assignments", palette)[1]


# The rules that paint a page, a card or a panel. A background named in one may be neutral or the
# look's own surfaces, never the accent or the accent laid over them.
LARGE = re.compile(
    r"(QMainWindow|QDialog|QFrame, QGroupBox|#(settingsPage|settingsRail|settingsCard|dialogCard|sheetCard|"
    r"setupRail|setupNav|setupChoice|setupGroup|authCard|weekTable|dayView|planReview|toast|commandBox))\b"
)


def painted_backgrounds(sheet: str) -> list[tuple[str, str]]:
    return [
        (selector.strip(), colour)
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", sheet)
        if LARGE.search(selector)
        for colour in re.findall(r"background: (#[0-9a-f]{6})", body)
    ]


@pytest.mark.parametrize(("name", "surface", "accent"), CASES)
def test_the_accent_is_never_a_page_card_or_wash(name: str, surface: str, accent: str) -> None:
    """The accent marks controls and is never spread over anything larger. Gold once turned today's
    column khaki, and the setup cards were washed blue."""
    palette = palette_for(name, surface, accent)
    reference = palette_for(name, surface, "default")
    for key in ("window", "panel", "field", "grid"):
        assert palette[key] == reference[key], key
    pack, dark, _look = LOOKS[name]
    painted = painted_backgrounds(pack_stylesheet(pack, dark, look_for(name, surface), accent, palette))
    assert painted, "the pattern found no page or card to check"
    probe = {**palette, "accent": "#ff00ff"}
    probed = painted_backgrounds(pack_stylesheet(pack, dark, look_for(name, surface), accent, probe))
    assert painted == probed
    # A design in Match my look wears the look: its cards are not the accent either.
    match = tokens_for("clay", MATCH, palette)
    large = [key for key in match if key.startswith("card_") or key in {"bg", "surface"}]
    probed_match = tokens_for("clay", MATCH, probe)
    assert {key: match[key] for key in large} == {key: probed_match[key] for key in large}


SIZE = re.compile(r"font-size: ([^;}]+)")
WEIGHT = re.compile(r"font-weight: ([^;}]+)")
# control_rules only writes the images' paths into the sheet.
ART = defaultdict(lambda: "art.png")


@pytest.mark.parametrize(("name", "text"), list(product(LOOKS, TEXT_SCALE)))
def test_every_font_size_and_weight_in_the_stylesheet_is_on_the_scale(name: str, text: str) -> None:
    """Caption, body, heading, title and display, which the Text knob scales together, and two
    weights, with 700 only for display numbers. The focus screen's countdown is the one size drawn
    beyond the scale, and it is a number."""
    pack, dark, _look = LOOKS[name]
    look = look_for(name)
    look = {**look, "knobs": {**look["knobs"], "text": text}}
    palette = resolved_palette(pack, dark, look)
    sheet = pack_stylesheet(pack, dark, look, "default", palette, ART)
    scale = {type_pt(role, text) for role in TYPE_PT}
    display = type_pt("display", text)
    off = []
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", sheet):
        where = selector.strip()
        # "11pt" and "11.0pt" are one size.
        sizes = [float(size.strip().removesuffix("pt")) for size in SIZE.findall(body)]
        off += [f"{where}: {size:g}pt" for size in sizes if size not in scale]
        for weight in (weight.strip() for weight in WEIGHT.findall(body)):
            number = weight == str(WEIGHT_NUMBER) and sizes == [display]
            if weight not in {str(WEIGHT_REGULAR), str(WEIGHT_STRONG)} and not number:
                off.append(f"{where}: weight {weight}")
    assert SIZE.search(sheet) and WEIGHT.search(sheet), "the patterns found nothing to check"
    assert off == [], (name, text)


def test_the_type_scale_is_five_sizes_that_small_and_large_scale_together() -> None:
    """The roles' own five sizes and their order are the engine's (desk_tokens.rs); what is held
    here is how Large and a custom factor move them."""
    roles = ("caption", "body", "heading", "title", "display")
    assert [type_pt(role) for role in roles] == [11, 13, 15, 20, 28]
    assert type_pt("body", "small") < type_pt("body") < type_pt("body", "large")
    assert type_pt("display", "large") / type_pt("display") == pytest.approx(1.2, abs=0.02)
    assert type_pt("body", 1.1) == 14.5


# The only modules that may set a font's size or weight: the stylesheet and the scale's own helpers.
# ring.py fits the focus screen's countdown numeral to its ring, beyond the scale on purpose, as
# 0.16's countdown was; its other words are the scale's. feel.py writes a style's extra stylesheet,
# its sizes from type_pt; the style feel tests hold it to that.
SCALE_KEEPERS = {"look.py", "fonts.py", "ring.py", "feel.py"}
OWN_FONT = re.compile(r"\.set(Bold|Weight|PointSize|PointSizeF|PixelSize)\(|font-size|font-weight")


def test_no_widget_outside_the_designs_sets_a_size_or_weight_of_its_own() -> None:
    """A widget that sets its own size or weight is off the scale however the scale changes. The
    designs under layouts/ keep their own sizes until their lanes redraw them."""
    native = Path(__file__).resolve().parents[2] / "native"
    found = [
        f"{path.relative_to(native)}:{number}: {line.strip()}"
        for path in sorted(native.rglob("*.py"))
        if path.name not in SCALE_KEEPERS and "layouts" not in path.parts
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if OWN_FONT.search(line) and not line.strip().startswith("#")
    ]
    assert found == []


@pytest.mark.parametrize("name", LOOKS)
def test_every_stylesheet_is_whole_rules_that_qt_can_parse(name: str) -> None:
    """Qt drops a whole stylesheet it cannot parse, with only a line on the console. A stray
    declaration left by a merge once did that to the window in every look, and every test still
    passed: the window was drawn in Qt's own grey."""
    for text in ("small", "normal", "large"):
        pack, dark, look = LOOKS[name]
        look = {**(look or {"preset": "default", "knobs": {}}), "knobs": {"text": text}}
        sheet = pack_stylesheet(pack, dark, look, "default", resolved_palette(pack, dark, look))
        leftover = re.sub(r"[^{}]+\{[^{}]*\}", "", sheet)
        assert leftover.strip() == "", (name, text, leftover[:200])


def test_the_material_theme_cache_keeps_thirty_two_schemes() -> None:
    """One scheme a time thrashed the cache while the shell crossed screens; thirty-two holds every
    preset in both modes at once."""
    assert _schemes.cache_info().maxsize == 32

