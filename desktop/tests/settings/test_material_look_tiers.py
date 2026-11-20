"""Material 3 Settings, the Advanced look page's Simple, More and All switch: which controls each tier shows,
that switching never moves a value, that the tier is kept on this computer, and where it starts.

Which controls belong to which tier is the requirement (Jonathan's Look B1 pick), listed here by name."""

from __future__ import annotations

import json

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_material_settings import (
    _bridge,
    _material_file,
    _named,
    _open_settings,
    _panel,
    _pump,
)
from desktop.tests.window_support import look_file, qapp  # noqa: F401

# ruff: noqa: F811

SIMPLE = ["row_preset", "row_draftMode", "row_cornerShape", "row_block", "row_rowSize", "row_textSize"]
MORE = [
    "row_corner",
    "row_hour",
    "row_padding",
    "row_rail",
    "row_scale",
    "row_motionSpeed",
    "row_shadow",
    "row_lines",
    "row_today",
    "row_times",
    "row_lengths",
]
ALL = ["row_now", "row_catSchool", "row_catSports", "row_catStudy", "row_catHomework", "row_readable"]


def _visible(root: QObject, name: str) -> bool:
    return any(item.isVisible() for item in _named(root, name))


def _advanced(qapp: QApplication, window: NativeWindow) -> QObject:
    root = _open_settings(qapp, window)
    _panel(window).openAdvanced()
    _pump(qapp)
    return root


def test_each_tier_shows_its_controls_and_the_ones_below_it(qapp: QApplication, window: NativeWindow) -> None:
    root = _advanced(qapp, window)
    panel = _panel(window)
    assert panel.property("state")["tier"] == "simple"
    for tier, shown in (("simple", SIMPLE), ("more", SIMPLE + MORE), ("all", SIMPLE + MORE + ALL)):
        panel.setLookTier(tier)
        _pump(qapp)
        assert panel.property("state")["tier"] == tier
        for name in SIMPLE + MORE + ALL:
            assert _visible(root, name) is (name in shown), (tier, name)


def test_switching_tiers_never_changes_a_value(qapp: QApplication, window: NativeWindow) -> None:
    _advanced(qapp, window)
    panel = _panel(window)
    panel.setDraftPreset("Forest")
    panel.setDraftMode("dark")
    panel.setDraftDensity("compact")
    panel.setDraftTextSize("large")
    panel.setCornerShape("pill")
    panel.setBlock("Outline")
    panel.setHour(70)
    panel.setNow("#aa2211")
    before = dict(panel.property("state"))
    keys = ("draftPreset", "draftMode", "draftDensity", "textSize", "cornerShape", "block", "hour", "now",
            "corner", "scale", "dirty")
    for tier in ("all", "more", "simple", "all"):
        panel.setLookTier(tier)
        after = panel.property("state")
        assert {key: after[key] for key in keys} == {key: before[key] for key in keys}
    assert before["cornerShape"] == "pill" and before["corner"] == 28


def test_the_simple_tier_edits_the_draft_and_done_applies_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    _advanced(qapp, window)
    panel = _panel(window)
    bridge = _bridge(window)
    panel.setDraftPreset("Forest")
    panel.setDraftMode("dark")
    panel.setDraftDensity("compact")
    panel.setDraftTextSize("large")
    panel.setCornerShape("sharp")
    panel.setBlock("Filled")
    assert _material_file().get("preset") in (None, "Slate")
    assert panel.preview.property("theme")["corner"] == 0
    panel.done()
    saved = _material_file()
    assert (saved["preset"], saved["mode"], saved["density"]) == ("Forest", "dark", "compact")
    assert saved["advanced"]["scale"] == 1.3
    assert saved["advanced"]["corner"] == 0
    assert saved["advanced"]["block"] == "Filled"
    assert bridge.property("theme")["corner"] == 0


def test_back_drops_what_the_simple_tier_changed(qapp: QApplication, window: NativeWindow) -> None:
    _advanced(qapp, window)
    panel = _panel(window)
    panel.setDraftPreset("Forest")
    panel.setDraftDensity("compact")
    panel.closeAdvanced()
    assert _material_file().get("preset") in (None, "Slate")
    panel.openAdvanced()
    assert panel.property("state")["draftPreset"] == "Slate"
    assert panel.property("state")["draftDensity"] == "comfortable"


def test_a_corner_shape_card_matches_only_its_own_radius(qapp: QApplication, window: NativeWindow) -> None:
    _advanced(qapp, window)
    panel = _panel(window)
    assert panel.property("state")["cornerShape"] == "rounded"
    panel.setCornerShape("pill")
    assert panel.property("state")["cornerShape"] == "pill"
    panel.setCorner(14)
    assert panel.property("state")["cornerShape"] == ""
    panel.setCornerShape("rounded")
    assert panel.property("state")["cornerShape"] == "rounded"
    assert panel.property("state")["corner"] == 12


def test_the_tier_is_kept_on_this_computer(qapp: QApplication, window: NativeWindow) -> None:
    _advanced(qapp, window)
    panel = _panel(window)
    panel.setLookTier("more")
    assert _material_file()["lookTier"] == "more"
    panel.closeAdvanced()
    panel.openAdvanced()
    assert panel.property("state")["tier"] == "more"
    # A look saved from Settings keeps the tier beside it.
    panel.setPreset("Forest")
    assert _material_file()["lookTier"] == "more"
    panel.note_applied()
    assert panel.property("state")["tier"] == "more"
    assert json.loads(look_file().read_text(encoding="utf-8"))["material"]["lookTier"] == "more"
    panel.setLookTier("sideways")
    assert panel.property("state")["tier"] == "more"


def test_the_page_starts_on_all_after_a_setup_that_read_as_power_and_never_overrides_a_choice(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window)
    panel = _panel(window)
    assert panel.property("state")["tier"] == "simple"
    panel.seed_look_tier("all")
    assert panel.property("state")["tier"] == "all"
    assert _material_file()["lookTier"] == "all"
    panel.setLookTier("simple")
    panel.seed_look_tier("all")
    assert panel.property("state")["tier"] == "simple"
