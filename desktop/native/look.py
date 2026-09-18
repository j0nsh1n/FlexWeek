"""Device-only look knobs and account theme packs. No Qt."""

from __future__ import annotations

from copy import deepcopy

LOOK_KNOBS = {
    "surface": ("frost", "flat"),
    "corners": ("round", "sharp", "pill"),
    "depth": ("soft", "flat", "hard"),
    "font": ("sans", "mono", "serif"),
    "blocks": ("filled", "outlined", "edge"),
    "density": ("comfortable", "compact"),
    "text": ("small", "normal", "large"),
}
LOOK_DEFAULTS = {
    "surface": "frost",
    "corners": "round",
    "depth": "soft",
    "font": "sans",
    "blocks": "filled",
    "density": "comfortable",
    "text": "normal",
}
LOOK_PRESETS = {
    "default": {},
    "terminal": {
        "surface": "flat",
        "corners": "sharp",
        "depth": "flat",
        "font": "mono",
        "blocks": "outlined",
        "density": "compact",
        "text": "normal",
    },
}
PACKS = ("system", "light-frost", "dark-frost", "nocturne", "slate")
ACCENTS = ("default", "sky", "gold", "sea", "sand")
TEXT_PT = {"small": 10, "normal": 12, "large": 15}
DENSITY_PAD = {"comfortable": 8, "compact": 4}
FONT_FAMILIES = {
    "sans": "Noto Sans, DejaVu Sans, sans-serif",
    "mono": "Noto Sans Mono, DejaVu Sans Mono, monospace",
    "serif": "Noto Serif, DejaVu Serif, serif",
}
PACK_COLORS = {
    "slate": {"window": "#e8eef4", "text": "#1a2332", "panel": "#f7fafc", "accent": "#2563eb"},
    "nocturne": {"window": "#121826", "text": "#e8eef4", "panel": "#1c2434", "accent": "#60a5fa"},
    "light-frost": {"window": "#dbe7f3", "text": "#16324f", "panel": "#f3f8fc", "accent": "#0ea5e9"},
    "dark-frost": {"window": "#0f1724", "text": "#d7e6f5", "panel": "#182233", "accent": "#38bdf8"},
}
ACCENT_COLORS = {
    "default": None,
    "sky": "#0ea5e9",
    "gold": "#d97706",
    "sea": "#0d9488",
    "sand": "#b45309",
}


def known_pack(pack: object) -> str:
    return pack if pack in PACKS else "system"


def pack_axis(pack: object) -> str:
    chosen = known_pack(pack)
    if chosen in {"light-frost", "slate"}:
        return "slate"
    if chosen in {"dark-frost", "nocturne"}:
        return "nocturne"
    return "system"


def pack_motion(pack: object) -> str:
    chosen = known_pack(pack)
    return "extra" if chosen in {"light-frost", "dark-frost"} else "normal"


def resolved_pack_theme(pack: object, system_dark: bool) -> str:
    chosen = known_pack(pack)
    if chosen == "system":
        return "nocturne" if system_dark else "slate"
    return chosen


def sanitize_look(raw: object) -> dict:
    clean: dict = {"preset": "default", "knobs": {}}
    if not isinstance(raw, dict):
        return clean
    if raw.get("preset") in LOOK_PRESETS:
        clean["preset"] = raw["preset"]
    knobs = raw.get("knobs") if isinstance(raw.get("knobs"), dict) else {}
    for knob, values in LOOK_KNOBS.items():
        value = knobs.get(knob)
        if value in values:
            clean["knobs"][knob] = value
    return clean


def effective_look(choice: dict | None) -> dict:
    selected = sanitize_look(choice)
    layered = {**LOOK_DEFAULTS, **LOOK_PRESETS[selected["preset"]], **selected["knobs"]}
    return layered


def known_accent(name: object) -> str:
    return name if name in ACCENTS else "default"


def pack_stylesheet(pack: object, system_dark: bool, look: dict | None, accent: object = "default") -> str:
    theme = resolved_pack_theme(pack, system_dark)
    palette = PACK_COLORS[theme]
    knobs = effective_look(look)
    choice = sanitize_look(look)
    if choice["preset"] == "terminal":
        palette = {"window": "#000000", "text": "#33ff66", "panel": "#050505", "accent": "#ffb000"}
    accent_color = ACCENT_COLORS.get(known_accent(accent)) or palette["accent"]
    pad = DENSITY_PAD[knobs["density"]]
    size = TEXT_PT[knobs["text"]]
    family = FONT_FAMILIES[knobs["font"]]
    radius = {"round": 8, "sharp": 0, "pill": 16}[knobs["corners"]]
    return (
        f"QMainWindow, QDialog, QWidget {{ background: {palette['window']}; color: {palette['text']}; "
        f"font-family: {family}; font-size: {size}pt; }}"
        f"QFrame, QGroupBox, QTableWidget, QListWidget, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox {{ "
        f"background: {palette['panel']}; color: {palette['text']}; padding: {pad}px; "
        f"border-radius: {radius}px; }}"
        f"QPushButton {{ background: {accent_color}; color: #ffffff; padding: {pad}px {pad * 2}px; "
        f"border-radius: {radius}px; }}"
        f"QPushButton:disabled {{ background: #6b7280; }}"
        f"QLabel#nowNext {{ font-weight: 600; }}"
    )


def copy_look(choice: dict | None) -> dict:
    return deepcopy(sanitize_look(choice))
