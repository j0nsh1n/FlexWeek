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

from desktop.native.tokens import contrast, fit_lightness

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
    try:
        loaded = json.loads(tokens_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
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


# Advanced settings sit on the preset. None means "the component's own value", so an untouched
# Done does not restyle the week. Seed colour, palette style, per-role colour overrides, the
# contrast dial, font, heading weight and surface separation wait for the palette generator.
CORNER_RANGE = (0, 28)
SCALE_RANGE = (0.85, 1.8)
HOUR_RANGE = (36, 90)
PAD_RANGE = (4, 24)
SHADOW_RANGE = (0, 3)
MOTION_SPEEDS = ("Slower", "Normal", "Faster", "Off")
BLOCK_STYLES = ("Edge", "Filled", "Outline")
HOUR_LINES = ("None", "Faint", "Clear")
CATEGORY_KEYS = ("school", "sports", "study", "homework")
LOOK_KIND = "FlexWeek material look"
LOOK_VERSION = 1
_CATEGORY_ROLE = {"school": "school", "sports": "soccer", "study": "reading", "homework": "homework"}


def advanced_default() -> dict[str, Any]:
    """The advanced draft before anyone moves a dial."""
    return {
        "corner": None,
        "hour": None,
        "padding": None,
        "rail": True,
        "scale": 1.0,
        "motion": "Normal",
        "shadow": None,
        "block": "Edge",
        "lines": "Faint",
        "today": True,
        "times": True,
        "lengths": False,
        "now": None,
        "cat": {key: None for key in CATEGORY_KEYS},
    }


def _hex(value: object) -> str | None:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return None
    try:
        int(value[1:], 16)
    except ValueError:
        return None
    return value.lower()


def _int_in(value: object, bounds: tuple[int, int]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    low, high = bounds
    if low <= value <= high:
        return value
    return None


def _float_in(value: object, bounds: tuple[float, float]) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = round(float(value), 2)
    low, high = bounds
    if low - 1e-9 <= number <= high + 1e-9:
        return number
    return None


def read_advanced(stored: object) -> dict[str, Any]:
    """Advanced dials from the look file. A missing or unknown value stays at the default."""
    found = advanced_default()
    material = stored.get("material") if isinstance(stored, dict) else None
    raw = material.get("advanced") if isinstance(material, dict) else None
    if not isinstance(raw, dict):
        return found
    corner = _int_in(raw.get("corner"), CORNER_RANGE)
    if corner is not None:
        found["corner"] = corner
    hour = _int_in(raw.get("hour"), HOUR_RANGE)
    if hour is not None:
        found["hour"] = hour
    padding = _int_in(raw.get("padding"), PAD_RANGE)
    if padding is not None:
        found["padding"] = padding
    if isinstance(raw.get("rail"), bool):
        found["rail"] = raw["rail"]
    scale = _float_in(raw.get("scale"), SCALE_RANGE)
    if scale is not None:
        found["scale"] = scale
    if raw.get("motion") in MOTION_SPEEDS:
        found["motion"] = raw["motion"]
    shadow = _int_in(raw.get("shadow"), SHADOW_RANGE)
    if shadow is not None:
        found["shadow"] = shadow
    if raw.get("block") in BLOCK_STYLES:
        found["block"] = raw["block"]
    if raw.get("lines") in HOUR_LINES:
        found["lines"] = raw["lines"]
    if isinstance(raw.get("today"), bool):
        found["today"] = raw["today"]
    if isinstance(raw.get("times"), bool):
        found["times"] = raw["times"]
    if isinstance(raw.get("lengths"), bool):
        found["lengths"] = raw["lengths"]
    now = _hex(raw.get("now"))
    if now is not None:
        found["now"] = now
    cats = raw.get("cat")
    if isinstance(cats, dict):
        for key in CATEGORY_KEYS:
            colour = _hex(cats.get(key))
            if colour is not None:
                found["cat"][key] = colour
    return found


def read_shortcuts(stored: object) -> bool:
    """Keyboard shortcuts stay on unless the look file turns them off."""
    material = stored.get("material") if isinstance(stored, dict) else None
    if isinstance(material, dict) and isinstance(material.get("shortcuts"), bool):
        return bool(material["shortcuts"])
    return True


def read_saved_material(stored: object) -> list[dict[str, Any]]:
    """Named material looks kept beside the preset. A broken entry is left out."""
    material = stored.get("material") if isinstance(stored, dict) else None
    raw = material.get("saved") if isinstance(material, dict) else None
    if not isinstance(raw, list):
        return []
    kept: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            continue
        choice = read_material_choice({"material": item})
        kept.append(
            {
                "name": item["name"].strip(),
                "preset": choice["preset"],
                "mode": choice["mode"],
                "contrast": choice["contrast"],
                "density": choice["density"],
                "advanced": read_advanced({"material": {"advanced": item.get("advanced")}}),
            }
        )
    return kept


def advanced_overrides(advanced: dict[str, Any]) -> dict[str, Any]:
    """Only the dials that differ from the default, so a preset can stay in charge of the rest."""
    default = advanced_default()
    changed: dict[str, Any] = {}
    for key, value in advanced.items():
        if key == "cat":
            colours = {
                name: colour for name, colour in (value or {}).items() if name in CATEGORY_KEYS and colour
            }
            if colours:
                changed["cat"] = colours
        elif value != default.get(key):
            changed[key] = value
    return changed


def pack_material(
    choice: dict[str, str],
    advanced: dict[str, Any],
    shortcuts: bool,
    saved: list[dict[str, Any]],
) -> dict[str, Any]:
    """The `material` object written into the look file."""
    body: dict[str, Any] = {
        "preset": choice["preset"],
        "mode": choice["mode"],
        "contrast": choice["contrast"],
        "density": choice["density"],
        "shortcuts": bool(shortcuts),
        "advanced": advanced,
    }
    if saved:
        body["saved"] = saved
    return body


def store_material(path: Path, material: dict[str, Any]) -> None:
    """Put `material` on the look file and leave every other key where it was."""
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stored = {}
    if not isinstance(stored, dict):
        stored = {}
    stored["material"] = material
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stored) + "\n", encoding="utf-8")


def kept_material(path: Path) -> dict[str, Any] | None:
    """The material object already in the look file, so a later save of the widgets look keeps it."""
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    material = stored.get("material") if isinstance(stored, dict) else None
    return material if isinstance(material, dict) else None


def hour_row_px(density: str, advanced: dict[str, Any]) -> int:
    """The week row. An advanced hour replaces the density's row; anything else uses the density."""
    hour = advanced.get("hour")
    if isinstance(hour, int):
        return hour
    base = int(DENSITY[density if density in DENSITY else DEFAULT_DENSITY]["hour_row"])
    scale = advanced.get("scale")
    if isinstance(scale, (int, float)) and scale > 0:
        return int(round(base * scale))
    return base


def dress_theme(theme: dict[str, Any], advanced: dict[str, Any]) -> dict[str, Any]:
    """The theme object plus the advanced dials that actually differ from the components' own values."""
    dressed = dict(theme)
    over = advanced_overrides(advanced)
    if "corner" in over:
        dressed["corner"] = over["corner"]
    if "scale" in over:
        dressed["typeScale"] = over["scale"]
    if "shadow" in over:
        dressed["shadow"] = over["shadow"]
    if "block" in over:
        dressed["blockStyle"] = over["block"]
    if "lines" in over:
        dressed["hourLines"] = over["lines"]
    if "today" in over:
        dressed["todayHighlight"] = over["today"]
    if "times" in over:
        dressed["showTimes"] = over["times"]
    if "lengths" in over:
        dressed["showLengths"] = over["lengths"]
    if "rail" in over:
        dressed["railLabels"] = over["rail"]
    if "padding" in over:
        dressed["cardPad"] = over["padding"]
    if "now" in over:
        dressed["nowLine"] = over["now"]
    if advanced.get("motion") == "Off":
        dressed["reduceMotion"] = True
    # Normal is the components' own speed. Naming it on every theme would change the object a
    # student has not touched.
    if advanced.get("motion") not in (None, "Normal"):
        dressed["motionSpeed"] = advanced["motion"]
    for name, colour in (over.get("cat") or {}).items():
        dressed["cat" + name[0].upper() + name[1:]] = colour
    return dressed


def export_document(choice: dict[str, str], advanced: dict[str, Any]) -> str:
    """The advanced page's export: the basic look and the draft, for a later import."""
    return json.dumps(
        {
            "kind": LOOK_KIND,
            "version": LOOK_VERSION,
            "preset": choice["preset"],
            "mode": choice["mode"],
            "contrast": choice["contrast"],
            "density": choice["density"],
            "advanced": advanced,
        },
        indent=2,
    )


def import_document(text: str) -> tuple[dict[str, Any] | None, str]:
    """A document from `export_document`, or a sentence saying why it was refused."""
    try:
        raw = json.loads(text)
    except ValueError:
        return None, "That file isn't a FlexWeek material look."
    if not isinstance(raw, dict) or raw.get("kind") != LOOK_KIND or raw.get("version") != LOOK_VERSION:
        return None, "That file isn't a FlexWeek material look."
    choice = read_material_choice({"material": raw})
    advanced = read_advanced({"material": {"advanced": raw.get("advanced")}})
    return {"choice": choice, "advanced": advanced}, ""


def reading_problems(mode: str, advanced: dict[str, Any]) -> list[dict[str, Any]]:
    """Category colours the student set that read under 4.5 to 1 against that category's ink.

    Seed colours are not checked here. They belong to the palette generator, which is not in yet.
    """
    problems: list[dict[str, Any]] = []
    cats = advanced.get("cat") or {}
    for key in CATEGORY_KEYS:
        fill = cats.get(key)
        if not isinstance(fill, str):
            continue
        _ground, ink = category_paint(_CATEGORY_ROLE[key], mode)
        ratio = contrast(ink, fill)
        if ratio >= 4.5:
            continue
        problems.append(
            {
                "words": f"{key} colour on its ink",
                "role": key,
                "ink": ink,
                "ground": fill,
                "ratio": round(ratio, 2),
                "fixed": fit_lightness(fill, (ink,), 4.5),
            }
        )
    now = advanced.get("now")
    if isinstance(now, str):
        surface = "#1a1c20" if mode == "dark" else "#ffffff"
        ratio = contrast(now, surface)
        if ratio < 3.0:
            problems.append(
                {
                    "words": "now line on the page",
                    "role": "now",
                    "ink": now,
                    "ground": surface,
                    "ratio": round(ratio, 2),
                    "fixed": fit_lightness(now, (surface,), 3.0),
                }
            )
    return problems
