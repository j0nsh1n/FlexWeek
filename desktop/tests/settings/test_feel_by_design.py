"""A Setup style's feel on Settings, a sheet, Setup and sign-in: the feel follows the main view, each
style adds its own faces, radii and frame, and the week's own chrome is left alone."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QLabel, QWidget

import desktop.native.feel as feel_module
import desktop.native.window as native_window
from desktop.native.feel import (
    Context,
    PaperEdge,
    apply_feel,
    design_key,
    dressed_stylesheet,
    extra_stylesheet,
    feel_for,
    page_feel,
    sanitize_design,
    set_current,
)
from desktop.native.layouts.registry import options_for, sanitize_layout, tokens_for
from desktop.native.look import design_look, pack_stylesheet, sanitize_look
from desktop.native.motion import apply_ui_effects
from desktop.native.settings import SettingsPage
from desktop.native.setup import STYLE as SETUP_STEP
from desktop.native.setup import SetupPage, style_layout
from desktop.native.tokens import (
    RADIUS_CARD,
    RADIUS_SHEET,
    SHADOW_SMALL,
    TEXT_SCALE,
    TYPE_PT,
    WEIGHT_REGULAR,
    WEIGHT_STRONG,
    type_pt,
)
from desktop.native.widgets import HomeworkDialog, control_art
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_feel import HEROES, STYLE, _dressed, _host, _setup_style
from desktop.tests.window_support import free, look_file, qapp, still  # noqa: F401


@pytest.fixture(autouse=True)
def nothing_is_left_dressed() -> Iterator[None]:
    apply_ui_effects("normal")
    yield
    set_current(None)
    apply_ui_effects("normal")


def test_the_feel_is_the_main_view_not_the_colourway() -> None:
    assert feel_for("classic").key == "plain"
    assert feel_for("timeline").key == "night_owl"
    assert feel_for("bento").key == "dashboard"
    assert feel_for("retro").key == "retro"
    assert feel_for("clay").key == "plain"
    assert feel_for("mission").key == "plain"
    assert feel_for("dial").key == "plain"
    assert feel_for("one").key == "plain"
    assert design_key("bento") == "bento"
    assert design_key("clay") == "classic"
    assert sanitize_design("retro") == "retro"
    assert sanitize_design("nope") == "classic"


def test_plain_keeps_todays_stylesheet_byte_for_byte(qapp: QApplication) -> None:  # noqa: F811
    pack, look, palette, tokens, feel, base, _layout = _dressed("plain")
    assert extra_stylesheet(base, feel, palette, tokens, look) == ""
    art = control_art(palette)
    dressed = dressed_stylesheet(pack, False, look, feel, "default", palette, art, tokens)
    assert dressed == base


@pytest.mark.parametrize(
    ("style_key", "want"),
    [
        ("night", "Newsreader"),
        ("dashboard", f"border-radius: {RADIUS_SHEET}px"),
        ("retro", "Pixelify Sans"),
    ],
)
def test_each_style_adds_its_faces_or_radius(
    qapp: QApplication, style_key: str, want: str  # noqa: F811
) -> None:
    pack, look, palette, tokens, feel, base, _layout = _dressed(style_key)
    extra = extra_stylesheet(base, feel, palette, tokens, look, ("settingsTitle", "sheetTitle"))
    assert extra
    assert want in extra
    if style_key == "night":
        assert f"border-radius: {RADIUS_CARD}px" in extra
    if style_key == "retro":
        assert "border-radius: 0px" in extra
        assert "VT323" in extra
    if style_key == "dashboard":
        assert "hero" in extra.lower() or "background:" in extra


def test_feel_sizes_are_on_the_scale(qapp: QApplication) -> None:  # noqa: F811
    """A style's extra sheet sets sizes and weights of its own, so each one must still be a step of
    the type scale at every text size, and one of the two weights."""
    checked = 0
    for style_key in ("night", "dashboard", "retro"):
        for text in TEXT_SCALE:
            _pack, look, palette, tokens, feel, base, _layout = _dressed(style_key)
            look = sanitize_look({**look, "knobs": {**look.get("knobs", {}), "text": text}})
            extra = extra_stylesheet(base, feel, palette, tokens, look, HEROES)
            scale = {type_pt(role, text) for role in TYPE_PT}
            found = re.findall(r"font-size: ([^;}]+)", extra)
            sizes = [float(size.strip().removesuffix("pt")) for size in found]
            weights = [weight.strip() for weight in re.findall(r"font-weight: ([^;}]+)", extra)]
            checked += len(sizes)
            assert [size for size in sizes if size not in scale] == [], (style_key, text)
            assert set(weights) <= {str(WEIGHT_REGULAR), str(WEIGHT_STRONG)}, (style_key, text, weights)
    assert checked, "the pattern found no size to check"


def test_settings_and_a_sheet_and_setup_show_the_feel(qapp: QApplication) -> None:  # noqa: F811
    for style_key, radius, font, frame in (
        ("plain", None, None, False),
        ("night", RADIUS_CARD, "Newsreader", False),
        ("dashboard", RADIUS_SHEET, None, False),
        ("retro", 0, "Pixelify", True),
    ):
        host, ctx = _host(qapp, style_key)
        chosen = _setup_style(style_key)
        prefs = {"alarms": [], "reminders_enabled": True, "theme_pack": chosen.pack}
        layout = style_layout(chosen, sanitize_layout(None))
        page = SettingsPage(host, prefs, ctx.look, {}, layout)
        apply_feel(page, ctx)
        qapp.processEvents()
        extra = extra_stylesheet(
            ctx.base_sheet, ctx.feel, ctx.palette, ctx.tokens, ctx.look, ("settingsTitle",)
        )
        if font:
            assert font in host.styleSheet() or font in extra
        assert (page.findChild(QWidget, "win98Frame") is not None) is frame
        if ctx.feel.chrome == "hero":
            assert page.findChild(QWidget, "bentoHeroIcon") is not None
        dialog = HomeworkDialog(host, today="2026-10-01")
        dialog.show()
        apply_feel(dialog, ctx)
        qapp.processEvents()
        assert (dialog.findChild(QWidget, "win98Frame") is not None) is frame
        if radius is not None and ctx.feel.key != "plain":
            extra = extra_stylesheet(
                ctx.base_sheet, ctx.feel, ctx.palette, ctx.tokens, ctx.look, ("sheetTitle",)
            )
            assert f"border-radius: {radius}px" in extra
        setup = SetupPage(host)
        setup.motion = "off"
        apply_feel(setup, ctx)
        qapp.processEvents()
        assert (setup.findChild(QWidget, "win98Frame") is not None) is frame
        dialog.close()
        free(dialog)
        free(page)
        free(setup)
        free(host)


def test_motion_off_changes_the_feel_at_once(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    apply_ui_effects("off")
    window.session.preferences = {**(window.session.preferences or {}), "motion": "off"}
    for fade in window.findChildren(QLabel, "motionFade"):
        fade.hide()
        fade.deleteLater()
    qapp.processEvents()
    window._layout = sanitize_layout({"main": "bento", "day": "dial"})
    window._apply_appearance()
    assert window._motion == "off"
    assert page_feel().key == "dashboard"
    assert page_feel().chrome == "hero"
    still(window)


def test_week_page_chrome_is_not_changed_by_a_designs_feel(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    window._layout = sanitize_layout({"main": "classic", "day": "dial"})
    window._apply_appearance()
    still(window)
    week = window.findChild(QWidget, "weekPage")
    assert week is not None
    title = window.week_title.font()
    original_week_title = (title.family(), title.pointSizeF(), title.weight())
    rail = window.rail.font()
    original_rail_font = (rail.family(), rail.pointSizeF(), rail.weight())
    for main in ("classic", "timeline", "bento", "retro"):
        window._layout = sanitize_layout({"main": main, "day": "dial"})
        window._apply_appearance()
        still(window)
        title_font = window.week_title.font()
        rail_font = window.rail.font()
        assert (title_font.family(), title_font.pointSizeF(), title_font.weight()) == original_week_title
        assert (rail_font.family(), rail_font.pointSizeF(), rail_font.weight()) == original_rail_font
        assert week.findChild(QWidget, "win98Frame") is None
        assert window.rail.findChild(QWidget, "win98Frame") is None
        # The design's own dressing (Retro's bevels, a design's fonts) stays off the window's chrome.
        pack, system_dark, accent = window._look_inputs()
        palette, look = design_look(
            options_for(window._layout, main)["look"], pack, system_dark, window._worn_look(), accent
        )
        base = pack_stylesheet(pack, system_dark, look, accent, palette, control_art(palette))
        feel = feel_for(main)
        extra = extra_stylesheet(base, feel, palette, tokens_for(feel.layout, "your", palette), look)
        if extra:
            assert extra not in window.styleSheet(), main
            assert extra not in window.planner.styleSheet(), main


def test_sign_in_wears_the_last_design_this_computer_used(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    path = look_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "preset": "default",
                "knobs": {},
                "layout": {"main": "retro", "day": "dial", "options": {}},
            }
        )
    )
    window._load_look()
    window._apply_appearance()
    # The sign-in page is dressed whichever page is showing; the light window is signed in already.
    window._show_page("authPage")
    still(window)
    assert page_feel().key == "retro"
    assert window.findChild(QWidget, "win98Frame") is not None
    assert "Pixelify" in window.findChild(QWidget, "authPage").styleSheet()
    window._save_look()
    saved = json.loads(path.read_text())
    assert "design" not in saved
    assert saved["layout"]["main"] == "retro"


def test_a_sheet_keeps_one_feel_stylesheet_across_shows(qapp: QApplication) -> None:  # noqa: F811
    host, _ctx = _host(qapp, "retro")
    dialog = HomeworkDialog(host, today="2026-10-01")
    dialog.show()
    qapp.processEvents()
    first = dialog.styleSheet()
    assert first
    dialog.hide()
    qapp.processEvents()
    dialog.show()
    qapp.processEvents()
    assert dialog.styleSheet() == first
    dialog.close()
    free(dialog)
    free(host)


def test_plain_pages_inherit_the_window_sheet(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    window._layout = sanitize_layout({"main": "classic", "day": "dial"})
    window._apply_appearance()
    still(window)
    for name in ("authPage", "recoveryPage"):
        page = window.findChild(QWidget, name)
        if page is not None:
            assert page.styleSheet() == ""
    assert window.setup_page.styleSheet() == ""
    text = Path(__file__).resolve().parents[2].joinpath("native/window.py").read_text()
    assert text.count("self._dress_entry(palette, look)") == 1


def test_setup_style_page_wears_the_style_being_picked(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    window._open_setup(SETUP_STEP, first_run=True)
    still(window)
    assert page_feel().key == "plain"
    window.setup_page._choose_style(STYLE["retro"])
    still(window)
    qapp.processEvents()
    assert page_feel().key == "retro"
    assert window.setup_page.findChild(QWidget, "win98Frame") is not None
    window.setup_page._choose_style(STYLE["plain"])
    still(window)
    qapp.processEvents()
    assert page_feel().key == "plain"


def test_card_depth_follows_the_feel_and_the_shared_small_shadow(qapp: QApplication) -> None:  # noqa: F811
    """Depth is the feel's own shadow, using the shared small shadow. Radii stay the design's. How the
    shadow looks is the picture's; this holds which cards get one and with which numbers."""
    names = ("settingsCard", "dialogCard", "setupGroup", "sheetCard", "authCard")
    assert (feel_for("bento").shape.card, feel_for("bento").shape.sheet, feel_for("bento").shape.shadow) == (
        RADIUS_SHEET,
        RADIUS_SHEET,
        "small",
    )
    assert (feel_for("classic").shape.card, feel_for("classic").shape.shadow) == (None, "keep")
    assert (feel_for("timeline").shape.card, feel_for("timeline").shape.shadow) == (RADIUS_CARD, "keep")
    assert (feel_for("retro").shape.card, feel_for("retro").shape.sheet, feel_for("retro").shape.shadow) == (
        0,
        0,
        "none",
    )

    def cards_for(style_key: str) -> tuple[Context, QWidget, dict[str, QWidget]]:
        _pack, look, palette, tokens, feel, base, _layout = _dressed(style_key)
        host = QWidget()
        made = {}
        for name in (*names, "notACard"):
            widget = QWidget(host)
            widget.setObjectName(name)
            made[name] = widget
        ctx = Context(feel, look, palette, tokens, base)
        set_current(ctx)
        apply_feel(host, ctx)
        qapp.processEvents()
        return ctx, host, made

    hosts: list[QWidget] = []
    try:
        ctx, host, made = cards_for("dashboard")
        hosts.append(host)
        dark = ctx.palette.get("axis") == "dark"
        opacity = SHADOW_SMALL.dark_opacity if dark else SHADOW_SMALL.opacity
        for name in names:
            effect = made[name].graphicsEffect()
            assert isinstance(effect, QGraphicsDropShadowEffect), name
            assert (effect.xOffset(), effect.yOffset(), effect.blurRadius()) == (
                0,
                SHADOW_SMALL.y,
                SHADOW_SMALL.blur,
            )
            assert effect.color().alpha() == round(255 * opacity), name
        assert made["notACard"].graphicsEffect() is None

        _ctx, host, made = cards_for("plain")
        hosts.append(host)
        assert all(made[name].graphicsEffect() is None for name in (*names, "notACard"))

        _ctx, host, made = cards_for("retro")
        hosts.append(host)
        assert all(made[name].graphicsEffect() is None for name in (*names, "notACard"))

        _ctx, host, made = cards_for("night")
        hosts.append(host)
        for name in names:
            assert isinstance(made[name].graphicsEffect(), PaperEdge), name
        assert made["notACard"].graphicsEffect() is None

        ctx, host, made = cards_for("dashboard")
        hosts.append(host)
        assert isinstance(made["settingsCard"].graphicsEffect(), QGraphicsDropShadowEffect)
        plain = Context(feel_for("classic"), ctx.look, ctx.palette, ctx.tokens, ctx.base_sheet)
        set_current(plain)
        apply_feel(host, plain)
        assert made["settingsCard"].graphicsEffect() is None
        assert made["notACard"].graphicsEffect() is None
    finally:
        set_current(None)
        for host in hosts:
            free(host)


def test_window_imports_current_once() -> None:
    assert native_window.current is feel_module.current
    source = Path(native_window.__file__).read_text()
    assert source.count("from desktop.native.feel import current") == 0
    assert "current," in source.split("from desktop.native.feel import", 1)[1].split("\n", 1)[0]
