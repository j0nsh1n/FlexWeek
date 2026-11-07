"""What the style-feel tests share: a style dressed from its Setup choice, and a host widget wearing it.
`_host` is also used by the sheet-dim tests."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.feel import Context, extra_stylesheet, feel_for, set_current
from desktop.native.layouts.registry import MATCH, sanitize_layout, tokens_for
from desktop.native.look import pack_stylesheet, resolved_palette
from desktop.native.setup import STYLES, style_layout, style_look
from desktop.native.widgets import control_art

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
