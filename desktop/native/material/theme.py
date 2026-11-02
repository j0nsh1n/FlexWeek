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

from desktop.native.tokens import contrast

PRESETS = ("Blue", "Sea", "Forest", "Gold", "Rose", "Plum")
MODES = ("light", "dark")
CONTRASTS = ("std", "high")
HIGH_CONTRAST_STROKE = 1.5
# Comfortable is the mock-up's hour row. Compact is the same grid, tightened.
DENSITY = {
    "comfortable": {"hour_row": 56, "settings_row_pad": 16, "card_pad": 12},
    "compact": {"hour_row": 44, "settings_row_pad": 10, "card_pad": 8},
}
# The spec's category colours, not the widgets look's OKLCH family.
CATEGORY_FILLS = {
    "school": {"light": "#EAE6FA", "dark": "#2A244D"},
    "soccer": {"light": "#E2F5EA", "dark": "#1B3B2B"},
    "reading": {"light": "#F9E6F0", "dark": "#3D2232"},
    "homework": {"light": "#F7EBD9", "dark": "#4A3219"},
}
# Meals, sleep and free time have no spec colour. These neutrals still read.
NEUTRAL_FILLS = {"light": "#F3F3FA", "dark": "#2E3036"}
ROLE_FOR_CATEGORY = {
    "class": "school",
    "exercise": "soccer",
    "extra": "soccer",
    "study": "reading",
    "assignments": "homework",
}
INK_DARK = "#1A1C20"
INK_LIGHT = "#FFFFFF"
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


@lru_cache(maxsize=1)
def _schemes() -> dict[str, dict[str, str]]:
    loaded = json.loads(tokens_path().read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Material tokens must be a JSON object of schemes")
    return loaded


def scheme_key(preset: str, mode: str, contrast_name: str) -> str:
    return f"{preset}.{mode}.{contrast_name}"


def scheme(preset: str, mode: str, contrast_name: str) -> dict[str, str]:
    """One scheme. An unknown preset, mode or contrast is a KeyError, not a quiet fallback."""
    if preset not in PRESETS or mode not in MODES or contrast_name not in CONTRASTS:
        raise KeyError(scheme_key(preset, mode, contrast_name))
    found = _schemes()[scheme_key(preset, mode, contrast_name)]
    return dict(found)


def stroke_for(contrast_name: str) -> float:
    """High contrast draws a solid 1.5px outline. Standard contrast does not add one."""
    if contrast_name not in CONTRASTS:
        raise KeyError(contrast_name)
    return HIGH_CONTRAST_STROKE if contrast_name == "high" else 0.0


def category_paint(role: str, mode: str) -> tuple[str, str]:
    """Fill and ink for a spec role (`school`, `soccer`, `reading`, `homework`) or a neutral."""
    if mode not in MODES:
        raise KeyError(mode)
    fills = CATEGORY_FILLS.get(role, NEUTRAL_FILLS)
    fill = fills[mode]
    ink = max((INK_DARK, INK_LIGHT), key=lambda item: contrast(fill, item))
    return fill, ink


def paint_for_category(category: str, mode: str) -> tuple[str, str]:
    """A week block's category key (`class`, `assignments`, …) as a Material fill and ink."""
    return category_paint(ROLE_FOR_CATEGORY.get(category, "neutral"), mode)


# EventBlock's own names. Soccer and reading use different words there than the fill table.
EVENT_CATEGORY = {
    "class": "school",
    "exercise": "sports",
    "extra": "sports",
    "study": "study",
    "assignments": "homework",
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
DEFAULT_PRESET = "Blue"
DEFAULT_MODE = "system"
DEFAULT_CONTRAST = "std"
DEFAULT_DENSITY = "comfortable"
FONT_FILES = (
    "RobotoFlex-Regular.ttf",
    "RobotoFlex-Medium.ttf",
    "RobotoFlex-SemiBold.ttf",
)
ROBOTO_FLEX = "Roboto Flex"


def qml_dir() -> Path:
    """The directory `import components 1.0` is added from. Main.qml lives in it."""
    return qml_path().parent


def event_category(category: str) -> str:
    """The EventBlock category for a week block. One the block does not know reads as homework."""
    return EVENT_CATEGORY.get(category, "homework")


def read_material_choice(stored: object) -> dict[str, str]:
    """Preset, mode, contrast, and density from a look file's top-level `material` object.

    A missing file, a missing object, or a value this build does not know falls back to Blue,
    follow system, standard contrast, and comfortable. Nothing here raises.
    """
    material = stored.get("material") if isinstance(stored, dict) else None
    raw = material if isinstance(material, dict) else {}
    preset = raw.get("preset")
    mode = raw.get("mode")
    contrast_name = raw.get("contrast")
    density = raw.get("density")
    return {
        "preset": preset if isinstance(preset, str) and preset in PRESETS else DEFAULT_PRESET,
        "mode": mode if isinstance(mode, str) and mode in SAVED_MODES else DEFAULT_MODE,
        "contrast": (
            contrast_name
            if isinstance(contrast_name, str) and contrast_name in CONTRASTS
            else DEFAULT_CONTRAST
        ),
        "density": density if isinstance(density, str) and density in DENSITY else DEFAULT_DENSITY,
    }


def resolved_mode(mode: str, worn_dark: bool) -> str:
    """`system` follows the worn look's light or dark axis. An explicit light or dark wins."""
    if mode in MODES:
        return mode
    return "dark" if worn_dark else "light"


def theme_object(
    colours: dict[str, str], density: str, reduce_motion: bool, high_contrast: bool
) -> dict[str, object]:
    """One map for every control: the Material roles, the ink aliases, and the three shell flags."""
    theme: dict[str, object] = {role: colours[role] for role in THEME_ROLES}
    for source, alias in INK_ALIASES.items():
        theme[alias] = colours[source]
    theme["density"] = density
    theme["reduceMotion"] = reduce_motion
    theme["highContrast"] = high_contrast
    return theme


def register_fonts() -> tuple[int, ...]:
    """Register the three Roboto Flex faces. The ids Qt returned, skipping a file it refused."""
    from PySide6.QtGui import QFontDatabase

    from desktop.native.fonts import FONT_DIR

    ids: list[int] = []
    for name in FONT_FILES:
        ident = QFontDatabase.addApplicationFont(str(FONT_DIR / name))
        if ident >= 0:
            ids.append(ident)
    return tuple(ids)
