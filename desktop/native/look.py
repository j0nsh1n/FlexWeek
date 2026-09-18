"""Device-only look knobs and account theme packs. No Qt.

A look has two halves. The palette says what colours exist; the knobs say how
the interface is drawn with them. A preset is a bundle of knob values, and may
bring its own palette. Every knob has to change something a student can see:
a control that stores a value nothing reads is the bug this module exists to
prevent, and desktop/tests/test_look.py proves each value moves the output.

Colours mirror frontend/styles.css, where the same names already passed the
readability and accent-distance audits, so both clients show the same look.
"""

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
    "poster": {
        "surface": "flat",
        "corners": "sharp",
        "depth": "hard",
        "font": "sans",
        "blocks": "filled",
        "density": "compact",
        "text": "large",
    },
    "ink": {
        "surface": "flat",
        "corners": "sharp",
        "depth": "flat",
        "font": "serif",
        "blocks": "edge",
        "density": "comfortable",
        "text": "normal",
    },
    "high-contrast": {
        "surface": "flat",
        "corners": "sharp",
        "depth": "hard",
        "font": "sans",
        "blocks": "outlined",
        "density": "comfortable",
        "text": "large",
    },
    # The two soft looks. Every preset above is flat and sharp; these keep rounded corners and depth.
    "paper": {
        "surface": "flat",
        "corners": "round",
        "depth": "soft",
        "font": "serif",
        "blocks": "filled",
        "density": "comfortable",
        "text": "normal",
    },
    "pastel": {
        "surface": "frost",
        "corners": "pill",
        "depth": "soft",
        "font": "sans",
        "blocks": "filled",
        "density": "comfortable",
        "text": "normal",
    },
}
LOOK_PRESET_LABELS = {
    "default": "Pack default",
    "terminal": "Terminal",
    "poster": "Poster",
    "ink": "Ink",
    "high-contrast": "High contrast",
    "paper": "Paper",
    "pastel": "Pastel",
}
PACK_LABELS = {
    "system": "System",
    "light-frost": "Light frost",
    "dark-frost": "Dark frost",
    "nocturne": "Nocturne",
    "slate": "Slate",
}
PACKS = ("system", "light-frost", "dark-frost", "nocturne", "slate")
ACCENTS = ("default", "sky", "gold", "sea", "sand")
TEXT_PT = {"small": 10, "normal": 12, "large": 15}
DENSITY_PAD = {"comfortable": 8, "compact": 4}
CORNER_RADIUS = {"round": 8, "sharp": 0, "pill": 16}
FONT_FAMILIES = {
    "sans": "Noto Sans, DejaVu Sans, sans-serif",
    "mono": "Noto Sans Mono, DejaVu Sans Mono, monospace",
    "serif": "Noto Serif, DejaVu Serif, serif",
}
AA_TEXT = 4.5
DARK_INK = "#0b1224"
LIGHT_INK = "#ffffff"


def _channels(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def mix(top: str, bottom: str, alpha: float) -> str:
    """The solid colour of `top` laid over `bottom` at `alpha`.

    The web palette states its hairlines as translucent tints. Qt stylesheets
    disagree between versions about alpha syntax, so the tint is settled here.
    """
    pairs = zip(_channels(top), _channels(bottom), strict=True)
    blended = [round(over * alpha + under * (1 - alpha)) for over, under in pairs]
    return "#{:02x}{:02x}{:02x}".format(*blended)


def luminance(color: str) -> float:
    linear = []
    for channel in _channels(color):
        value = channel / 255
        linear.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def readable_ink(background: str) -> str:
    """Black or white, whichever reads better on a colour the palette does not own, such as a category.

    Pure black, not the palette's navy ink: on the violet Study colour navy reaches about 4.4 to 1 and
    white about 4.2, so neither passes, while black does.
    """
    return max(("#000000", LIGHT_INK), key=lambda ink: contrast(ink, background))


def _palette(axis: str, tint: str, soft: float = 0.12, strong: float = 0.24, **colors: str) -> dict:
    """A colour table. Hairlines are `tint` over the panel; the web's light themes use a weaker strong one."""
    panel = colors["panel"]
    return {
        "axis": axis,
        **colors,
        "hairline": mix(tint, panel, soft),
        "hairline_strong": mix(tint, panel, strong),
    }


# window is the page, panel the raised surface, field an input, grid the calendar cell.
PALETTES = {
    "nocturne": _palette(
        "dark", "#baccff",
        window="#0e1320", panel="#161d2b", field="#121827", grid="#131a27",
        text="#e6ebf5", muted="#9ba6ba", accent="#7fa8ff", accent_ink="#0b1224", error="#ff9b9b",
        block_locked="#2b3a52", block_locked_ink="#eef2fa", block_flex="#4a3c1c", block_flex_ink="#fff4dc",
        block_edge="#7d93b8",
    ),
    "slate": _palette(
        "light", "#182c58", strong=0.22,
        window="#edf2fa", panel="#ffffff", field="#fbfcfe", grid="#fbfcff",
        text="#172033", muted="#536079", accent="#3d6fc4", accent_ink="#ffffff", error="#b42318",
        block_locked="#dde6f3", block_locked_ink="#18233a", block_flex="#f5e6c3", block_flex_ink="#3b2a05",
        block_edge="#8a9bb8",
    ),
    "dark-frost": _palette(
        "dark", "#a0e6f0",
        window="#071018", panel="#0f1c26", field="#0b151c", grid="#0d1820",
        text="#e4f3f6", muted="#8ea8b0", accent="#5eead4", accent_ink="#0b1224", error="#ff9b9b",
        block_locked="#234050", block_locked_ink="#eef8fa", block_flex="#4a3c1c", block_flex_ink="#fff4dc",
        block_edge="#6a93a0",
    ),
    "light-frost": _palette(
        "light", "#0c4050", strong=0.22,
        window="#e7f4fa", panel="#ffffff", field="#f7fcfe", grid="#f7fcfe",
        text="#14303a", muted="#4d6870", accent="#0e7490", accent_ink="#ffffff", error="#b42318",
        block_locked="#d7e8ee", block_locked_ink="#14303a", block_flex="#f5e6c3", block_flex_ink="#3b2a05",
        block_edge="#7a9aa4",
    ),
}
# A preset may replace the pack's colours outright. Terminal is true black with phosphor text.
# Ink has a light map and a dark map so it follows the pack axis; the others are one look.
PRESET_PALETTES = {
    "terminal": _palette(
        "dark", "#78ff78", soft=0.25, strong=0.45,
        window="#000000", panel="#0a0a0a", field="#000000", grid="#050505",
        text="#d6ffd6", muted="#7fbf7f", accent="#ffb000", accent_ink="#000000", error="#ff6b6b",
        block_locked="#0a0a0a", block_locked_ink="#d6ffd6",
        block_flex="#0a0a0a", block_flex_ink="#ffe9a8", block_edge="#7fbf7f",
    ),
    "poster": _palette(
        "light", "#0b132b", soft=0.75, strong=1.0,
        window="#ffd60a", panel="#ffd60a", field="#ffd60a", grid="#ffe14d",
        text="#0b132b", muted="#5c3d2e", accent="#8b0000", accent_ink="#ffd60a", error="#6b0000",
        block_locked="#0b132b", block_locked_ink="#ffd60a",
        block_flex="#8b0000", block_flex_ink="#ffd60a", block_edge="#0b132b",
    ),
    "high-contrast": _palette(
        "dark", "#ffffff", soft=0.95, strong=1.0,
        window="#000000", panel="#000000", field="#000000", grid="#000000",
        text="#ffffff", muted="#ffff00", accent="#ffff00", accent_ink="#000000", error="#ffff00",
        block_locked="#000000", block_locked_ink="#ffffff",
        block_flex="#000000", block_flex_ink="#ffff00", block_edge="#ffff00",
    ),
    # Light looks whatever pack sits underneath, as Poster is. Paper is warmer than Ink's light sheet
    # on purpose. Pastel's softness is in its surfaces; a pale lavender accent could not pass as text.
    "paper": _palette(
        "light", "#4a341e", soft=0.16, strong=0.30,
        window="#f7ecd2", panel="#fdf8ea", field="#fffcf2", grid="#fffcf2",
        text="#2f2418", muted="#6a5a45", accent="#8a4b2a", accent_ink="#fdf8ea", error="#9b1b30",
        block_locked="#eadfc6", block_locked_ink="#2f2418",
        block_flex="#f3dca6", block_flex_ink="#3b2a05", block_edge="#a08a68",
    ),
    "pastel": _palette(
        "light", "#7a3e9d", soft=0.16, strong=0.30,
        window="#fdf2f8", panel="#ffffff", field="#fffafd", grid="#fffafd",
        text="#3b2a4a", muted="#6b5a7a", accent="#7a3e9d", accent_ink="#ffffff", error="#b42318",
        block_locked="#ede4fb", block_locked_ink="#2e1f47",
        block_flex="#ffe4ef", block_flex_ink="#4a1230", block_edge="#a78bda",
    ),
    "ink": {
        "dark": _palette(
            "dark", "#eaeaea", soft=0.28, strong=0.50,
            window="#111111", panel="#111111", field="#111111", grid="#161616",
            text="#eaeaea", muted="#9a9a9a", accent="#eaeaea", accent_ink="#111111", error="#ff6b6b",
            block_locked="#111111", block_locked_ink="#eaeaea",
            block_flex="#111111", block_flex_ink="#eaeaea", block_edge="#9a9a9a",
        ),
        "light": _palette(
            "light", "#1a1a1a", strong=0.22,
            window="#f4f1ea", panel="#f4f1ea", field="#f4f1ea", grid="#efece4",
            text="#1a1a1a", muted="#5a5a5a", accent="#1a1a1a", accent_ink="#f4f1ea", error="#9b1b30",
            block_locked="#f4f1ea", block_locked_ink="#1a1a1a",
            block_flex="#f4f1ea", block_flex_ink="#1a1a1a", block_edge="#1a1a1a",
        ),
    },
}
# Each accent has a dark-axis and a light-axis colour with its own ink, so it reads on either.
ACCENT_COLORS = {
    "sky": {"dark": ("#38bdf8", DARK_INK), "light": ("#0369a1", LIGHT_INK)},
    "gold": {"dark": ("#eab308", DARK_INK), "light": ("#a16207", LIGHT_INK)},
    "sea": {"dark": ("#2dd4bf", DARK_INK), "light": ("#0f766e", LIGHT_INK)},
    "sand": {"dark": ("#e7d5a3", DARK_INK), "light": ("#926a2a", LIGHT_INK)},
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


def look_menu_items() -> list[tuple[str, str, str]]:
    """One Look list: account packs first, then device presets. Pack default is the pack itself."""
    items = [(name, PACK_LABELS[name], "pack") for name in PACKS]
    items.extend(
        (name, LOOK_PRESET_LABELS[name], "preset") for name in LOOK_PRESETS if name != "default"
    )
    return items


def look_menu_token(kind: str, name: str) -> str:
    return f"{kind}:{name}"


def parse_look_menu_token(token: object) -> tuple[str, str] | None:
    if not isinstance(token, str) or ":" not in token:
        return None
    kind, name = token.split(":", 1)
    if kind == "pack" and name in PACKS:
        return kind, name
    if kind == "preset" and name in LOOK_PRESETS and name != "default":
        return kind, name
    return None


def look_menu_value(pack: object, look: dict | None) -> str:
    preset = sanitize_look(look)["preset"]
    if preset != "default":
        return look_menu_token("preset", preset)
    return look_menu_token("pack", known_pack(pack))


def sanitize_look(raw: object) -> dict:
    clean: dict = {"preset": "default", "knobs": {}}
    if not isinstance(raw, dict):
        return clean
    if raw.get("preset") in LOOK_PRESETS:
        clean["preset"] = raw["preset"]
    stored = raw.get("knobs")
    knobs = stored if isinstance(stored, dict) else {}
    for knob, values in LOOK_KNOBS.items():
        value = knobs.get(knob)
        if value in values:
            clean["knobs"][knob] = value
    return clean


def effective_look(choice: dict | None) -> dict:
    selected = sanitize_look(choice)
    layered = {**LOOK_DEFAULTS, **LOOK_PRESETS[selected["preset"]], **selected["knobs"]}
    return layered


def preset_knobs(preset: object) -> dict:
    """Every knob as the preset alone sets it, which is what choosing that preset means."""
    return effective_look({"preset": preset, "knobs": {}})


def look_overrides(preset: object, shown: dict) -> dict:
    """Only the knobs a student moved away from the preset, so the preset keeps governing the rest."""
    bundle = preset_knobs(preset)
    return {knob: value for knob, value in shown.items() if knob in bundle and value != bundle[knob]}


def known_accent(name: object) -> str:
    return name if name in ACCENTS else "default"


def _preset_palette(preset: str, pack: object, system_dark: bool) -> dict | None:
    table = PRESET_PALETTES.get(preset)
    if table is None:
        return None
    if "axis" in table:
        return table
    theme = resolved_pack_theme(pack, system_dark)
    return table["dark" if theme in {"nocturne", "dark-frost"} else "light"]


def resolved_palette(pack: object, system_dark: bool, look: dict | None, accent: object = "default") -> dict:
    """The colours on screen: the preset's palette or the pack's, then the accent, then the surface knob."""
    choice = sanitize_look(look)
    pack_colours = PALETTES[resolved_pack_theme(pack, system_dark)]
    base = _preset_palette(choice["preset"], pack, system_dark) or pack_colours
    palette = dict(base)
    chosen = known_accent(accent)
    if chosen != "default":
        # A student's own accent wins over the pack's and the preset's, as it does in the web client.
        palette["accent"], palette["accent_ink"] = ACCENT_COLORS[chosen][palette["axis"]]
    if effective_look(choice)["surface"] == "flat":
        # Flat has no raised surfaces: panels and inputs sit in the page and only hairlines divide them.
        palette["panel"] = palette["window"]
        palette["field"] = palette["window"]
    return palette


def block_paint(
    look: dict | None, palette: dict, category_color: str | None, kind: str = "locked",
    mark: str | None = None,
) -> dict:
    """How one calendar block is drawn: its fill, its ink, and where the category colour goes.

    `category_color` is the pale fill; `mark` is the strong colour of the same category. A pale
    outline vanishes on a light pack, so an outline or an edge is drawn with the mark.
    """
    flexible = kind == "flexible"
    neutral = palette["block_flex" if flexible else "block_locked"]
    neutral_ink = palette["block_flex_ink" if flexible else "block_locked_ink"]
    mark = mark or category_color or palette["block_edge"]
    mode = effective_look(look)["blocks"]
    if mode == "outlined":
        return {"mode": mode, "fill": palette["grid"], "ink": palette["text"], "outline": mark, "edge": None}
    if mode == "edge":
        return {
            "mode": mode, "fill": palette["panel"], "ink": palette["text"],
            "outline": palette["hairline"], "edge": mark,
        }
    if category_color:
        return {"mode": mode, "fill": category_color, "ink": readable_ink(category_color), "outline": None,
                "edge": None}
    return {"mode": mode, "fill": neutral, "ink": neutral_ink, "outline": None, "edge": None}


def _depth_rules(depth: str, palette: dict) -> str:
    # Qt stylesheets have no shadows. Depth is drawn with edges instead: a hairline for soft, nothing
    # for flat, and a heavy bottom and right edge for hard, which reads as a hard offset shadow.
    if depth == "flat":
        return "border: none;"
    if depth == "hard":
        strong = palette["hairline_strong"]
        heavy = f"4px solid {strong}"
        return f"border: 2px solid {strong}; border-bottom: {heavy}; border-right: {heavy};"
    return f"border: 1px solid {palette['hairline']};"


def pack_stylesheet(pack: object, system_dark: bool, look: dict | None, accent: object = "default") -> str:
    palette = resolved_palette(pack, system_dark, look, accent)
    knobs = effective_look(look)
    pad = DENSITY_PAD[knobs["density"]]
    size = TEXT_PT[knobs["text"]]
    family = FONT_FAMILIES[knobs["font"]]
    radius = CORNER_RADIUS[knobs["corners"]]
    edges = _depth_rules(knobs["depth"], palette)
    item_h = 36 if knobs["text"] == "large" else 22
    button_min = f" min-height: {item_h}px;" if knobs["text"] == "large" else ""
    return (
        f"QMainWindow, QDialog, QWidget {{ background: {palette['window']}; color: {palette['text']}; "
        f"font-family: {family}; font-size: {size}pt; }}"
        f"QFrame, QGroupBox, QTableWidget, QListWidget {{ background: {palette['panel']}; "
        f"color: {palette['text']}; padding: {pad}px; border-radius: {radius}px; {edges} }}"
        f"QPlainTextEdit, QLineEdit, QComboBox, QSpinBox {{ background: {palette['field']}; "
        f"color: {palette['text']}; padding: {pad}px; border-radius: {radius}px; {edges} }}"
        f"QTableWidget {{ gridline-color: {palette['hairline']}; "
        f"selection-background-color: {palette['accent']}; selection-color: {palette['accent_ink']}; }}"
        # Headers and the view stack are QFrames too. Left to the panel rule, each header is padded and
        # rounded inside a fixed height, which slices its text in half, and the calendar sits in two boxes.
        f"QHeaderView, QStackedWidget {{ background: transparent; border: none; "
        f"padding: 0; border-radius: 0; }}"
        f"QHeaderView::section, QTableCornerButton::section {{ background: {palette['panel']}; "
        f"color: {palette['muted']}; padding: 2px 6px; border: none; }}"
        # QLabel is a QFrame in Qt, so without this every label, even an empty one, is drawn as a panel.
        f"QLabel {{ background: transparent; border: none; padding: 0; }}"
        f"QPushButton {{ background: {palette['accent']}; color: {palette['accent_ink']}; "
        f"padding: {pad}px {pad * 2}px; border-radius: {radius}px; {edges}{button_min} }}"
        f"QPushButton:disabled {{ background: {palette['hairline_strong']}; color: {palette['muted']}; }}"
        f"QMenu::item {{ min-height: {item_h}px; padding: {pad}px {pad * 2}px; }}"
        f"QLabel#nowNext {{ font-weight: 600; }}"
    )


def copy_look(choice: dict | None) -> dict:
    return deepcopy(sanitize_look(choice))
