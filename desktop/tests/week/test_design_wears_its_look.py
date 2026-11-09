# ruff: noqa: F811
"""Which colours a design is given: its own curated look, the account's palette when it has none, and a
changed look reaching a design that follows it. These read the colours the window hands the design, not
the pixels it paints (those are pictures)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    click,
    qapp,  # noqa: F401
    signature,
    window,  # noqa: F401
)


def test_a_changed_look_reaches_a_design_that_matches_it(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {"one": {"look": "your"}}}
    click(window, "viewMyDay")
    view = window.planner.currentWidget()
    before = view.scene.tokens["bg"]
    window._look = {"preset": "terminal", "knobs": {}}
    window._apply_appearance()
    assert view.scene.tokens["bg"] != before


def test_the_chrome_and_canvas_follow_the_same_look(qapp: QApplication, window: NativeWindow) -> None:
    """The active design look supplies every canvas view, and the hours the week draws."""
    from desktop.native.layouts.registry import tokens_for
    from desktop.native.look import design_look

    pack, system_dark, accent = window._look_inputs()

    for layout_id in ("classic", "timeline", "mission", "bento", "retro", "clay"):
        colour = signature(layout_id)
        window._layout = {"main": layout_id, "day": "one", "options": {layout_id: {"look": colour}}}
        for view in ("week", "day", "month"):
            window.session.set_view(view)
            window._apply_appearance()
            qapp.processEvents()
            page = window._scene_for(layout_id).tokens
            palette, _ = design_look(colour, pack, system_dark, window._worn_look(), accent)
            assert page == tokens_for(layout_id, colour, palette)
            assert window.week_table.hours.painter.colours["window"] == palette["window"]
        window.session.set_view("week")


@pytest.mark.parametrize(
    ("pack", "look", "dark"),
    [("system", "high-contrast", False), ("nocturne", "default", True)],
)
@pytest.mark.parametrize(
    "layout_id", ("classic", "timeline", "mission", "bento", "retro", "clay", "dial", "one")
)
def test_missing_design_look_keeps_the_accounts_own_palette(
    qapp: QApplication, window: NativeWindow, pack: str, look: str, dark: bool, layout_id: str
) -> None:
    from desktop.native.look import resolved_palette, sanitize_look

    window.session.preferences = {**(window.session.preferences or {}), "theme_pack": pack}
    window._look = sanitize_look({"preset": look, "knobs": {}})
    palette = resolved_palette(pack, dark, window._worn_look())
    expected_bg = "#000000" if look == "high-contrast" else "#0a0e27"
    assert palette["window"] == expected_bg
    if layout_id in {"dial", "one"}:
        window._layout = {"main": "classic", "day": layout_id, "options": {}}
        window._day_mode = True
    else:
        window._layout = {"main": layout_id, "day": "dial", "options": {}}
        window._day_mode = False
    window._on_week()
    click(window, "viewMyDay" if layout_id in {"dial", "one"} else "viewWeek")
    qapp.processEvents()
    shown = window.planner.currentWidget()
    if layout_id == "classic":
        assert window.week_table.hours.painter.colours["window"] == expected_bg
    else:
        assert shown.scene.tokens["bg"] == expected_bg, layout_id


def test_a_day_screen_uses_its_selected_look_for_every_token(
    qapp: QApplication, window: NativeWindow
) -> None:
    from desktop.native.layouts.registry import tokens_for
    from desktop.native.look import design_look

    window._layout = {"main": "classic", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    pack, system_dark, accent = window._look_inputs()
    palette, _ = design_look(signature("one"), pack, system_dark, window._worn_look(), accent)
    colour = signature("one")
    window._layout = {"main": "classic", "day": "one", "options": {"one": {"look": colour}}}
    click(window, "viewMyDay")
    qapp.processEvents()
    assert window.planner.currentWidget().scene.tokens == tokens_for("one", colour, palette)
