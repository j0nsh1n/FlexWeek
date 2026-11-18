"""What the style-feel tests share: a style (one of the four Setup used to offer) dressed, and a host
widget wearing it. `_host` is also used by the sheet-dim tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.feel import Context, extra_stylesheet, feel_for, set_current
from desktop.native.layouts.registry import MATCH, sanitize_layout, tokens_for
from desktop.native.look import pack_stylesheet, resolved_palette, sanitize_look
from desktop.native.widgets import control_art

# The four styles first-run setup offered before Material was the only interface, each a design
# dressed in a look: what the feel tests dress a page in.


@dataclass(frozen=True)
class Style:
    key: str
    name: str
    note: str
    main: str
    colour: str | None
    pack: str
    knobs: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)


STYLES = (
    Style(
        "plain",
        "Plain calendar",
        "Your week as a timetable grid",
        "classic",
        "pack:light-frost",
        "light-frost",
    ),
    Style(
        "dashboard",
        "Dashboard",
        "Next up and due soon, as tiles",
        "bento",
        "preset:bento-indigo",
        "light-frost",
    ),
    Style(
        "night",
        "Night owl",
        "Dark colours, compact spacing",
        "timeline",
        "pack:dark-frost",
        "dark-frost",
        {"density": "compact"},
        {"density": "compact"},
    ),
    Style(
        "retro",
        "Retro",
        "A 90s desktop, with large text",
        "retro",
        "preset:retro-teal",
        "light-frost",
        {"text": "large"},
    ),
)


def style_layout(style: Style, layout: dict) -> dict:
    options = deepcopy(sanitize_layout(layout)["options"])
    if style.colour is not None or style.options:
        chosen = dict(options.get(style.main, {}))
        if style.colour is not None:
            chosen["look"] = style.colour
        chosen.update(style.options)
        options[style.main] = chosen
    return sanitize_layout({"main": style.main, "day": sanitize_layout(layout)["day"], "options": options})


def style_look(style: Style) -> dict:
    return sanitize_look({"preset": "default", "knobs": dict(style.knobs)})


HEROES = ("settingsTitle", "sheetTitle", "setupTitle", "authBrand")

STYLE = {style.key: style for style in STYLES}


def _dressed(style_key: str) -> tuple:
    style = STYLE[style_key if style_key != "night_owl" else "night"]
    look = style_look(style)
    layout = style_layout(style, sanitize_layout(None))
    palette = resolved_palette(style.pack, False, look, "default")
    feel = feel_for(layout["main"])
    tokens = tokens_for(feel.layout, style.colour or MATCH, palette)
    base = pack_stylesheet(style.pack, False, look, "default", palette, control_art(palette))
    return style.pack, look, palette, tokens, feel, base, layout


def _host(app: QApplication, style_key: str) -> tuple[QWidget, Context]:
    pack, look, palette, tokens, feel, base, _layout = _dressed(style_key)
    extra = extra_stylesheet(base, feel, palette, tokens, look, HEROES)
    host = QWidget()
    host.setStyleSheet(base + extra)
    host.resize(1280, 800)
    ctx = Context(feel, look, palette, tokens, base)
    set_current(ctx)
    host.show()
    app.processEvents()
    return host, ctx


def _setup_style(style_key: str):  # noqa: ANN202
    return STYLE["night" if style_key == "night_owl" else style_key]
