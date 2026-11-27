"""Material 3 colour schemes, density, and the category fills the spec names.

`tokens.json` is the 24 schemes (six presets, light and dark, standard and high
contrast). A frozen build looks beside this file and, if that copy is not
there, beside the executable.
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import flexweek_engine  # type: ignore[import-untyped]

from desktop.native.tokens import contrast as contrast

PRESETS = (
    "Slate",
    "Blue",
    "Sea",
    "Forest",
    "Gold",
    "Rose",
    "Plum",
    "High contrast",
    "Paper",
    "Ink",
    "Terminal",
)
# The four old looks (look.py's PALETTES) carry their own surfaces and one mode each, so a student's
# Light or Dark choice cannot turn them into something they are not. Their schemes are whole in
# tokens.json; the B3A3 surfaces below belong to the other presets.
ONE_MODE = {"High contrast": "dark", "Paper": "light", "Ink": "dark", "Terminal": "dark"}
# A look's own font and corner, used only until the student chooses their own (read_font, the
# advanced Corners dial). Paper and Ink keep the default soft corners.
PRESET_LOOK = {
    "High contrast": {"font": "sans", "corner": 0},
    "Paper": {"font": "serif", "corner": None},
    "Ink": {"font": "serif", "corner": None},
    "Terminal": {"font": "mono", "corner": 0},
}
FONTS = ("sans", "serif", "mono")
FONT_LABELS = {"sans": "Sans", "serif": "Serif", "mono": "Mono"}
# The bundled faces: the body face, and the headings' face (Serif is Newsreader headings over Inter).
FONT_FAMILIES = {
    "sans": ("Inter", "Inter"),
    "serif": ("Inter", "Newsreader"),
    "mono": ("JetBrains Mono", "JetBrains Mono"),
}
# Accent colours on top of a preset, the Widgets accents' light-axis colours (look.ACCENT_COLORS).
# "default" is Same as preset: the preset's own colours stay.
ACCENTS = ("default", "sky", "gold", "sea", "sand")
ACCENT_LABELS = {"default": "Same as preset", "sky": "Sky", "gold": "Gold", "sea": "Sea", "sand": "Sand"}
ACCENT_SEEDS = {"sky": "#0369a1", "gold": "#a16207", "sea": "#0f766e", "sand": "#805441"}
# High contrast's yellow is part of its contrast, so no accent replaces it.
ACCENT_LOCKED = ("High contrast",)
MODES = ("light", "dark")
CONTRASTS = ("std", "high")
HIGH_CONTRAST_STROKE = 1.5
# Comfortable is the mock-up's hour row. Compact is the same grid, tightened.
DENSITY = {
    "comfortable": {"hour_row": 56, "settings_row_pad": 16, "card_pad": 12},
    "compact": {"hour_row": 44, "settings_row_pad": 10, "card_pad": 8},
}

# B3a3 neutral surfaces for every preset (with Material 3 five-step tonal container hierarchy),
# and fixed accents for Slate.
B3A3 = {
    "surface": {"light": "#eef1f5", "dark": "#0b0d10"},
    "surfaceContainerLowest": {"light": "#ffffff", "dark": "#0e1116"},
    "surfaceContainerLow": {"light": "#f6f8fc", "dark": "#14171c"},
    "surfaceContainer": {"light": "#edf0f7", "dark": "#1b202a"},
    "surfaceContainerHigh": {"light": "#e3e8f2", "dark": "#232936"},
    "surfaceContainerHighest": {"light": "#d8dfec", "dark": "#2c3444"},
    "surfaceVariant": {"light": "#e3e8f2", "dark": "#232936"},
    "outlineVariant": {"light": "#d4dce8", "dark": "#252a33"},
    "outline": {"light": "#64748b", "dark": "#6b7280"},
    "onSurface": {"light": "#0f172a", "dark": "#ececec"},
    "onSurfaceVariant": {"light": "#475569", "dark": "#9a9fa8"},
    "onSurfaceVariant_high": {"light": "#334155", "dark": "#c4c8d0"},
    "slate": {
        "primary": {"light": "#3d6fc4", "dark": "#7fa8ff"},
        "onPrimary": {"light": "#ffffff", "dark": "#0b1220"},
        "secondaryContainer": {"light": "#e6edf8", "dark": "#1c2433"},
        "onSecondaryContainer": {"light": "#0f172a", "dark": "#ececec"},
    },
}

# Status colours: dark from spec; light values proposed, not in the spec
STATUS_COLORS = {
    "dark": {
        "statusDone": "#8fd19e",
        "statusDueSoon": "#f0c674",
        "statusOverdue": "#ff9b8f",
    },
    "light": {
        "statusDone": "#276b3f",
        "statusDueSoon": "#8a5a00",
        "statusOverdue": "#b42318",
    },
}

CLASS_COLORS = {
    "class": "#3d6fc4",       # School
    "exercise": "#2b9665",    # Sports (darker than the spec's #2f9e6b: 3:1 on the page, Jonathan 11-04)
    "extra": "#0f8a8a",       # Clubs
    "assignments": "#a87512", # Work
    "study": "#c2557a",       # Personal
    "meals": "#64748b",       # Other
    "sleep": "#64748b",       # Other
    "free": "#64748b",        # Other
}
OTHER_CLASS_COLOR = "#64748b"
SIX_CLASSES = ("class", "exercise", "extra", "assignments", "study", "other")
INK_DARK = "#0f172a"
INK_LIGHT = "#ececec"
_AA = 4.5


def tokens_path() -> Path:
    """Where a build reads the schemes: next to this module, or next to the executable."""
    beside = Path(__file__).resolve().with_name("tokens.json")
    if beside.is_file():
        return beside
    return Path(sys.executable).resolve().parent / "desktop" / "native" / "material" / "tokens.json"


def qml_path() -> Path:
    """The shell page. Same two places as the schemes."""
    beside = Path(__file__).resolve().parent / "qml" / "Main.qml"
    if beside.is_file():
        return beside
    return Path(sys.executable).resolve().parent / "desktop" / "native" / "material" / "qml" / "Main.qml"


@lru_cache(maxsize=32)
def _schemes() -> dict[str, dict[str, str]]:
    try:
        loaded = json.loads(tokens_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("Material tokens must be a JSON object of schemes")
    return loaded


def scheme_key(preset: str, mode: str, contrast_name: str) -> str:
    return str(flexweek_engine.views_theme_scheme_key(preset, mode, contrast_name))


def scheme(preset: str, mode: str, contrast_name: str) -> dict[str, str]:
    """One scheme. An unknown preset, mode or contrast is a KeyError, not a quiet fallback."""
    return json.loads(flexweek_engine.views_theme_scheme(preset, mode, contrast_name, _schemes()))


def stroke_for(contrast_name: str) -> float:
    """High contrast draws a solid 1.5px outline. Standard contrast does not add one."""
    return float(flexweek_engine.views_theme_stroke_for(contrast_name))


def bar_for_category(category: str) -> str:
    """The solid accent bar colour for an event category."""
    return str(flexweek_engine.views_theme_bar_for_category(category))


def paint_for_category(category: str, mode: str) -> tuple[str, str]:
    """A week block's category key (`class`, `assignments`, …) as a Material fill and ink."""
    fill, ink = flexweek_engine.views_theme_paint_for_category(category, mode)
    return str(fill), str(ink)


_ROLE_TO_CATEGORY = {
    "school": "class",
    "class": "class",
    "soccer": "exercise",
    "sports": "exercise",
    "exercise": "exercise",
    "clubs": "extra",
    "extra": "extra",
    "homework": "assignments",
    "assignments": "assignments",
    "reading": "study",
    "study": "study",
}


def category_paint(role: str, mode: str) -> tuple[str, str]:
    """Fill and ink for a role or category."""
    fill, ink = flexweek_engine.views_theme_category_paint(role, mode)
    return str(fill), str(ink)


# The EventBlock class keys for event categories.
EVENT_CATEGORY = {
    "class": "class",
    "exercise": "exercise",
    "extra": "extra",
    "assignments": "assignments",
    "study": "study",
    "other": "other",
    "meals": "other",
    "sleep": "other",
    "free": "other",
}
# Every camelCase role the component README lists, in that order.
THEME_ROLES = (
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
# QML treats a name starting with "on" as a signal handler. The same object carries both.
INK_ALIASES = {
    "onPrimary": "inkPrimary",
    "onPrimaryContainer": "inkPrimaryContainer",
    "onSecondary": "inkSecondary",
    "onSecondaryContainer": "inkSecondaryContainer",
    "onTertiary": "inkTertiary",
    "onTertiaryContainer": "inkTertiaryContainer",
    "onError": "inkError",
    "onErrorContainer": "inkErrorContainer",
    "onSurface": "inkSurface",
    "onSurfaceVariant": "inkMuted",
}
SAVED_MODES = ("system", "light", "dark")
DEFAULT_PRESET = "Slate"
DEFAULT_MODE = "system"
DEFAULT_CONTRAST = "std"
DEFAULT_DENSITY = "comfortable"
FONT_FILES = (
    "Inter-Regular.ttf",
    "Inter-Medium.ttf",
    "Inter-SemiBold.ttf",
)
INTER = "Inter"


def qml_dir() -> Path:
    """The directory `import components 1.0` is added from. Main.qml lives in it."""
    return qml_path().parent


def event_category(category: str) -> str:
    """The EventBlock category for a week block: the category itself when in SIX_CLASSES, else 'other'."""
    return str(flexweek_engine.views_theme_event_category(category))


def read_material_choice(stored: object) -> dict[str, str]:
    """Preset, mode, contrast, and density from a look file's top-level `material` object.

    A missing file, a missing object, or a value this build does not know falls back to Slate,
    follow system, standard contrast, and comfortable. Nothing here raises.
    """
    return json.loads(flexweek_engine.views_look_read_material_choice(stored))


def resolved_mode(mode: str, worn_dark: bool) -> str:
    """`system` follows the worn look's light or dark axis. An explicit light or dark wins."""
    return str(flexweek_engine.views_theme_resolved_mode(mode, worn_dark))


def mode_of(choice: dict[str, str], worn_dark: bool) -> str:
    """The light or dark a choice shows: its preset's own when it has only one, else Mode's."""
    return str(flexweek_engine.views_theme_mode_of(json.dumps(choice), worn_dark))


def read_font(stored: object) -> str:
    """The student's own font from the look file's `material` object; "" means the preset's own."""
    return str(flexweek_engine.views_look_read_font(stored))


def shown_font(preset: str, font: str) -> str:
    """The font worn: the student's choice, else the preset's own, else Sans."""
    return str(flexweek_engine.views_theme_shown_font(preset, font))


def read_accent(preferences: object) -> str:
    """The saved accent name; anything this build does not know is Same as preset."""
    return str(flexweek_engine.views_theme_read_accent(preferences))


def accented(
    colours: dict[str, str], accent: str, preset: str, mode: str, contrast_name: str
) -> dict[str, str]:
    """`colours` with the accent's primary roles over the preset's. Same as preset, High contrast and a
    name this build does not know leave them as they are."""
    return json.loads(
        flexweek_engine.views_theme_accented(json.dumps(colours), accent, preset, mode, contrast_name)
    )


def theme_object(
    colours: dict[str, str],
    density: str,
    reduce_motion: bool,
    high_contrast: bool,
    chips_accent: bool = False,
) -> dict[str, object]:
    """One map for every control: the Material roles, the ink aliases, and the three shell flags."""
    return json.loads(
        flexweek_engine.views_theme_object(
            json.dumps(colours), density, reduce_motion, high_contrast, chips_accent
        )
    )


def register_fonts() -> tuple[int, ...]:
    """Register the three Inter faces. The ids Qt returned, skipping a file it refused."""
    from PySide6.QtGui import QFontDatabase

    from desktop.native.fonts import FONT_DIR

    ids: list[int] = []
    for name in FONT_FILES:
        ident = QFontDatabase.addApplicationFont(str(FONT_DIR / name))
        if ident >= 0:
            ids.append(ident)
    return tuple(ids)


# Advanced settings sit on the preset. None means "the component's own value", so an untouched
# Done does not restyle the week. Seed colour, palette style, per-role colour overrides, the
# contrast dial, font, heading weight and surface separation wait for the palette generator.
CORNER_RANGE = (0, 28)
SCALE_RANGE = (0.85, 1.8)
HOUR_RANGE = (36, 90)
PAD_RANGE = (4, 24)
SHADOW_RANGE = (0, 3)
MOTION_SPEEDS = ("Slower", "Normal", "Faster", "Off")
# Motion speed times the level's own pace: Slower takes half as long again, Faster 0.6 as long.
MOTION_SPEED_PACE = {"Slower": 1.5, "Faster": 0.6}
BLOCK_STYLES = ("Edge", "Filled", "Outline")
HOUR_LINES = ("None", "Faint", "Clear")
CATEGORY_KEYS = ("school", "sports", "study", "homework")
LOOK_KIND = "FlexWeek material look"
LOOK_VERSION = 1
_CATEGORY_ROLE = {"school": "school", "sports": "soccer", "study": "reading", "homework": "homework"}


def advanced_default() -> dict[str, Any]:
    """The advanced draft before anyone moves a dial."""
    return json.loads(flexweek_engine.views_look_advanced_default())


def _hex(value: object) -> str | None:
    return flexweek_engine.views_look_hex_color(value)


def _int_in(value: object, bounds: tuple[int, int]) -> int | None:
    return flexweek_engine.views_look_int_in(value, bounds)


def _float_in(value: object, bounds: tuple[float, float]) -> float | None:
    return flexweek_engine.views_look_float_in(value, bounds)


def read_advanced(stored: object) -> dict[str, Any]:
    """Advanced dials from the look file. A missing or unknown value stays at the default."""
    return json.loads(flexweek_engine.views_look_read_advanced(stored))


def read_shortcuts(stored: object) -> bool:
    """The number keys (1 to 5) stay on unless the look file turns them off."""
    return bool(flexweek_engine.views_look_read_shortcuts(stored))


def read_letter_keys(stored: object) -> bool:
    """The P, Z and F keys are off unless the look file turns them on. The number keys' own switch does
    not carry over: nobody has used these keys yet, so none starts on."""
    return bool(flexweek_engine.views_look_read_letter_keys(stored))


def read_saved_material(stored: object) -> list[dict[str, Any]]:
    """Named material looks kept beside the preset. A broken entry is left out."""
    return json.loads(flexweek_engine.views_look_read_saved_material(stored))


def advanced_overrides(advanced: dict[str, Any]) -> dict[str, Any]:
    """Only the dials that differ from the default, so a preset can stay in charge of the rest."""
    return json.loads(flexweek_engine.views_look_advanced_overrides(json.dumps(advanced)))


LOOK_TIERS = ("simple", "more", "all")
DAY_SIDE_RANGE = (240, 480)
DAY_SIDE_DEFAULT = 312
SETTINGS_NAV_RANGE = (72, 340)
SETTINGS_NAV_DEFAULT = 220


def read_look_tier(stored: object) -> str:
    """How many Look controls the Advanced page shows on this computer: simple, more or all. An empty string
    means nobody chose yet, so the page starts on simple (or on all after a setup that read as power)."""
    return str(flexweek_engine.views_look_read_look_tier(stored))


def read_day_side_width(stored: object) -> int:
    """Remembered width of the Day right sidebar (Now card + mini month) on this computer."""
    return int(flexweek_engine.views_look_read_day_side_width(stored))


def read_settings_nav_width(stored: object) -> int:
    """Remembered width of the Settings section list on this computer."""
    return int(flexweek_engine.views_look_read_settings_nav_width(stored))


def pack_material(
    choice: dict[str, str],
    advanced: dict[str, Any],
    shortcuts: bool,
    letters: bool,
    saved: list[dict[str, Any]],
    font: str = "",
    tier: str = "",
    day_side_width: int | None = None,
    settings_nav_width: int | None = None,
) -> dict[str, Any]:
    """The `material` object written into the look file."""
    return json.loads(
        flexweek_engine.views_look_pack_material(
            json.dumps(choice),
            json.dumps(advanced),
            bool(shortcuts),
            bool(letters),
            json.dumps(saved),
            font,
            tier,
            day_side_width,
            settings_nav_width,
        )
    )


def store_material(path: Path, material: dict[str, Any]) -> None:
    """Put `material` on the look file and leave every other key where it was."""
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        existing = None
    text = str(flexweek_engine.views_look_merge_material(existing, json.dumps(material)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def kept_material(path: Path) -> dict[str, Any] | None:
    """The material object already in the look file, so a later save of the widgets look keeps it."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    found = flexweek_engine.views_look_extract_kept_material(text)
    if found is None:
        return None
    return json.loads(found)


def hour_row_px(density: str, advanced: dict[str, Any]) -> int:
    """The week row. An advanced hour replaces the density's row; anything else uses the density."""
    return int(flexweek_engine.views_theme_hour_row_px(density, json.dumps(advanced)))


def dress_theme(
    theme: dict[str, Any], advanced: dict[str, Any], preset: str = "", font: str = ""
) -> dict[str, Any]:
    """The theme object plus the advanced dials that actually differ from the components' own values,
    and the font. A preset's own font and corner are only defaults: the student's choice wins."""
    return json.loads(
        flexweek_engine.views_theme_dress_theme(json.dumps(theme), json.dumps(advanced), preset, font)
    )


def export_document(choice: dict[str, str], advanced: dict[str, Any]) -> str:
    """The advanced page's export: the basic look and the draft, for a later import."""
    return str(flexweek_engine.views_look_export_document(json.dumps(choice), json.dumps(advanced)))


def import_document(text: str) -> tuple[dict[str, Any] | None, str]:
    """A document from `export_document`, or a sentence saying why it was refused."""
    found, error = flexweek_engine.views_look_import_document(text)
    if found is None:
        return None, str(error)
    return json.loads(found), str(error)


def reading_problems(mode: str, advanced: dict[str, Any]) -> list[dict[str, Any]]:
    """Category colours the student set that read under 4.5 to 1 against that category's ink.

    Seed colours are not checked here. They belong to the palette generator, which is not in yet.
    """
    return json.loads(flexweek_engine.views_theme_reading_problems(mode, json.dumps(advanced)))
