"""Material 3 Settings, the Advanced look: a draft until Done, Reset all, Export and Import, the save and
import prompts, the preset question, the readability list and its Fix, and the preview.

The contrast floors (4.5 to 1 for text, 3 to 1 for the Now line) are values the panel computes for its
Fix buttons, so they are checked here; how the preview is drawn is not."""

from __future__ import annotations

import json

from PySide6.QtWidgets import QApplication

from desktop.native.material.theme import category_paint
from desktop.native.tokens import contrast
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_material_settings import (
    _bridge,
    _click,
    _click_segment,
    _material_file,
    _named,
    _open_settings,
    _panel,
    _pump,
    _qml,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811


def test_advanced_is_a_draft_until_done_and_back_drops_it(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window)
    bridge = _bridge(window)
    panel = _panel(window)
    _click(qapp, window, _named(root, "openAdvanced")[0])
    wait_until(qapp, lambda: panel.property("state")["page"] == "advanced")
    assert _named(root, "advancedPage")
    panel.setHour(70)
    panel.setCorner(20)
    assert int(bridge.property("hourRow")) == 56
    assert "corner" not in bridge.property("theme")
    assert int(panel.preview.property("hourRow")) == 70
    assert panel.preview.property("theme")["corner"] == 20
    assert _named(root, "settingsPreviewWeek")
    assert _material_file().get("advanced", {}).get("hour") is None

    _click(qapp, window, _named(root, "advancedBack")[0])
    wait_until(qapp, lambda: panel.property("state")["page"] == "sections")
    assert int(bridge.property("hourRow")) == 56
    assert panel.property("state")["notice"] == "Advanced changes were not applied. Done applies them."
    _click(qapp, window, _named(root, "openAdvanced")[0])
    wait_until(qapp, lambda: panel.property("state")["page"] == "advanced")
    assert panel.property("state")["hour"] == 56

    panel.setHour(70)
    panel.setCorner(20)
    _click(qapp, window, _named(root, "advancedDone")[0])
    wait_until(qapp, lambda: panel.property("state")["page"] == "sections")
    assert int(bridge.property("hourRow")) == 70
    assert bridge.property("theme")["corner"] == 20
    assert _material_file()["advanced"]["hour"] == 70
    assert _material_file()["advanced"]["corner"] == 20
    assert _qml(root, "materialWeek") is not None


def test_reset_all_returns_the_dials_to_the_preset(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window)
    panel = _panel(window)
    bridge = _bridge(window)
    panel.openAdvanced()
    panel.setHour(80)
    panel.setScale(1.2)
    panel.setBlock("Outline")
    panel.resetAdvanced()
    state = panel.property("state")
    assert (state["hour"], state["scale"], state["block"]) == (56, 1.0, "Edge")
    panel.done()
    assert int(bridge.property("hourRow")) == 56
    assert _material_file()["advanced"]["hour"] is None
    panel.openAdvanced()
    panel.setShadow(2)
    panel.setCorner(4)
    panel.resetGroup("depth")
    assert panel.property("state")["shadow"] == 0
    assert panel.property("state")["corner"] == 4


def test_export_then_import_gives_back_the_same_look(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window)
    panel = _panel(window)
    panel.openAdvanced()
    panel.setCorner(4)
    panel.setScale(1.2)
    panel.setBlock("Outline")
    panel.setLines("Clear")
    panel.setNow("#aa2211")
    panel.exportLook()
    text = str(panel.property("state")["exportText"])
    panel.resetAdvanced()
    assert panel.property("state")["corner"] == 12
    panel.importText(text)
    state = panel.property("state")
    assert (state["corner"], state["scale"], state["block"], state["lines"], state["now"]) == (
        4,
        1.2,
        "Outline",
        "Clear",
        "#aa2211",
    )
    assert state["dirty"] is True
    panel.importText("{not json")
    assert panel.property("state")["importError"] == "That file isn't a FlexWeek material look."
    panel.importText(json.dumps({"kind": "something else", "version": 1}))
    assert panel.property("state")["importError"] == "That file isn't a FlexWeek material look."


def test_the_import_and_save_prompts_open_and_report_a_bad_answer(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    panel.openAdvanced()
    _pump(qapp)
    _click(qapp, window, _named(root, "importLook")[0])
    assert panel.property("state")["prompt"] == "import"
    assert _named(root, "importPrompt")[0].property("visible") is True
    panel.confirmPrompt("nonsense")
    assert panel.property("state")["prompt"] == "import"
    assert panel.property("state")["importError"] != ""
    panel.dismissPrompt()
    _click(qapp, window, _named(root, "saveLook")[0])
    assert panel.property("state")["prompt"] == "save"
    panel.confirmPrompt("  ")
    assert panel.property("state")["saveError"] == "Name the look first."
    assert panel.property("state")["prompt"] == "save"
    panel.setBlock("Outline")
    panel.beginSave()
    panel.confirmPrompt("Study look")
    assert panel.property("state")["savedNames"] == ["Study look"]
    assert _material_file()["saved"][0]["advanced"]["block"] == "Outline"
    assert _material_file().get("advanced", {}).get("block") != "Outline"
    panel.done()
    panel.openAdvanced()
    panel.setBlock("Filled")
    panel.done()
    assert panel.property("state")["block"] == "Filled"
    panel.useSaved("Study look")
    assert panel.property("state")["block"] == "Outline"
    assert _material_file()["advanced"]["block"] == "Outline"
    _click(qapp, window, _named(root, "forgetSaved_0")[0])
    wait_until(qapp, lambda: panel.property("state")["savedNames"] == [])
    assert _material_file().get("saved") in (None, [])


def test_a_new_preset_asks_whether_to_keep_the_advanced_dials(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    panel.setPreset("Gold")
    assert panel.property("state")["askPreset"] is False
    assert _material_file()["preset"] == "Gold"
    panel.openAdvanced()
    panel.setHour(66)
    panel.done()
    panel.setPreset("Rose")
    assert panel.property("state")["askPreset"] is True
    assert _material_file()["preset"] == "Gold"
    _pump(qapp)
    assert _named(root, "presetPrompt")[0].property("visible") is True
    panel.answerPreset("cancel")
    assert panel.property("state")["askPreset"] is False
    assert _material_file()["preset"] == "Gold"
    panel.setPreset("Rose")
    panel.answerPreset("keep")
    assert _material_file()["preset"] == "Rose"
    assert _material_file()["advanced"]["hour"] == 66
    panel.setPreset("Plum")
    panel.answerPreset("discard")
    assert _material_file()["preset"] == "Plum"
    assert _material_file()["advanced"]["hour"] is None


def test_readability_lists_failing_colours_and_fix_makes_them_read(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    panel.setMode("light")
    panel.openAdvanced()
    _pump(qapp)
    assert panel.property("state")["problems"] == []
    school_ink = category_paint("school", "light")[1]
    sports_ink = category_paint("soccer", "light")[1]
    panel.setCategory("school", school_ink)
    panel.setCategory("sports", sports_ink)
    panel.setNow("#fafafa")
    _pump(qapp)
    roles = sorted(item["role"] for item in panel.property("state")["problems"])
    assert roles == ["now", "school", "sports"]
    assert _named(root, "fix_school") and _named(root, "fixAll")

    _click(qapp, window, _named(root, "fix_school")[0])
    state = panel.property("state")
    assert sorted(item["role"] for item in state["problems"]) == ["now", "sports"]
    assert contrast(school_ink, state["catSchool"]) >= 4.5

    _click(qapp, window, _named(root, "fixAll")[0])
    state = panel.property("state")
    assert state["problems"] == []
    assert contrast(sports_ink, state["catSports"]) >= 4.5
    assert contrast(state["now"], "#ffffff") >= 3.0
    panel.setCategory("study", "#12")
    assert panel.property("state")["catStudy"] == ""
    assert panel.property("state")["notice"] == "Use a colour like #1a1c20."


def test_the_preview_shows_each_real_view_and_both_sizes(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    panel.openAdvanced()
    _pump(qapp)
    canvas = _named(root, "previewCanvas")[0]
    assert _named(root, "settingsPreviewWeek")
    assert 0 < float(canvas.property("scale")) <= 1
    _click_segment(qapp, window, _named(root, "previewFit")[0], "Actual size")
    wait_until(qapp, lambda: panel.property("state")["previewFit"] == "Actual")
    assert float(canvas.property("scale")) == 1.0
    _click_segment(qapp, window, _named(root, "previewFit")[0], "Fit")
    for name, view in (
        ("Day", "settingsPreviewDay"),
        ("Month", "settingsPreviewMonth"),
        ("Week", "settingsPreviewWeek"),
    ):
        _click_segment(qapp, window, _named(root, "previewView")[0], name)
        wait_until(qapp, lambda view=view: bool(_named(root, view)))
    assert _qml(root, "materialWeek") is not None
