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
