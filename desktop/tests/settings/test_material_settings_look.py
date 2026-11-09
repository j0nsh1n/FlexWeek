"""Material 3 Settings, the Look and Planning pages: each control writes its preference and the app reacts.

Expected numbers come from the spec (hour row 44 when compact, the Blue dark surface), not from
reading the QML or the bridge. Whether a control is cut off at a narrow window is a picture
(pictures/screens_settings_h3.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from backend.app import Preferences
from desktop.native.material import bridge_settings
from desktop.native.weekmodel import hhmm_text, set_clock_24h
from desktop.native.widgets import CUTOFFS as WIDGET_CUTOFFS
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_material_settings import (
    _bridge,
    _click,
    _click_segment,
    _every_quick,
    _material_file,
    _named,
    _open_settings,
    _panel,
    _prefs,
    _qml,
    _show_material,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811

TOKENS = json.loads(
    (Path(__file__).parents[2] / "native" / "material" / "tokens.json").read_text(encoding="utf-8")
)
BLUE_DARK_SURFACE = "#0b0d10"
BLUE_LIGHT_SURFACE = "#eef1f5"
FIELDS = set(Preferences.model_fields)


def test_the_clock_switch_changes_the_clock_in_the_material_shell(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    assert not _prefs(window).get("clock_24h")
    assert _qml(root, "materialClock").property("text") == "7:00 PM"
    _click(qapp, window, _named(root, "clock24")[0])
    wait_until(qapp, lambda: _prefs(window).get("clock_24h") is True)
    wait_until(qapp, lambda: _qml(root, "materialClock").property("text") == "19:00")
    _click(qapp, window, _named(root, "clock24")[0])
    wait_until(qapp, lambda: not _prefs(window).get("clock_24h"))
    wait_until(qapp, lambda: _qml(root, "materialClock").property("text") == "7:00 PM")


def test_mode_preset_contrast_and_density_apply_at_once(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window)
    bridge = _bridge(window)
    _click_segment(qapp, window, _named(root, "mode")[0], "Dark")
    wait_until(qapp, lambda: _material_file().get("mode") == "dark")
    assert bridge.property("theme")["surface"] == BLUE_DARK_SURFACE
    _click_segment(qapp, window, _named(root, "mode")[0], "Light")
    wait_until(qapp, lambda: _material_file().get("mode") == "light")
    assert bridge.property("theme")["surface"] == BLUE_LIGHT_SURFACE

    _click(qapp, window, _named(root, "preset_Sea")[0])
    wait_until(qapp, lambda: _material_file().get("preset") == "Sea")
    assert bridge.property("theme")["primary"] == TOKENS["Sea.light.std"]["primary"]

    assert int(bridge.property("hourRow")) == 56
    _click_segment(qapp, window, _named(root, "density")[0], "Compact")
    wait_until(qapp, lambda: _material_file().get("density") == "compact")
    assert int(bridge.property("hourRow")) == 44
    assert bridge.property("density") == "compact"

    assert bridge.property("highContrast") is False
    _click_segment(qapp, window, _named(root, "contrast")[0], "High")
    wait_until(qapp, lambda: _material_file().get("contrast") == "high")
    assert bridge.property("highContrast") is True
    assert bridge.property("theme")["primary"] == TOKENS["Sea.light.high"]["primary"]


def test_choosing_auto_mode_keeps_system_in_the_look_file(qapp: QApplication, window: NativeWindow) -> None:
    """Auto is the label; the look file keeps the account's system mode, not the word auto."""
    root = _open_settings(qapp, window)
    _click_segment(qapp, window, _named(root, "mode")[0], "Dark")
    wait_until(qapp, lambda: _material_file().get("mode") == "dark")
    _click_segment(qapp, window, _named(root, "mode")[0], "Auto")
    wait_until(qapp, lambda: _material_file().get("mode") == "system")
    assert _material_file().get("mode") != "auto"


def test_the_style_row_goes_back_to_the_widgets_styles(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window)
    button = _named(root, "useWidgets")[0]
    assert button.property("text") == "Widgets styles"
    _click(qapp, window, button)
    wait_until(qapp, lambda: window._surface == "widgets")


def test_widgets_styles_is_a_text_button_and_look_keeps_at_most_one_filled(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    button = _named(root, "useWidgets")[0]
    assert button.property("kind") == "text"
    look = _named(root, "lookSection")[0]
    filled = [
        item
        for item in _every_quick(look)
        if item.property("kind") == "filled" and item.property("text") is not None
    ]
    assert len(filled) <= 1


def test_every_section_opens_and_names_only_controls_with_a_real_effect(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    for name in ("planning", "focus", "alerts", "computer", "look"):
        _click(qapp, window, _named(root, "section_" + name)[0])
        wait_until(qapp, lambda name=name: _panel(window).property("state")["section"] == name)
        assert _named(root, name + "Section")
    for gone in (
        "dynamicColor",
        "offlineCache",
        "seedColour",
        "paletteStyle",
        "row_dynamic",
        "dimCompleted",
        "autoMute",
        "autoComplete",
        "tightWarn",
        "freeNudge",
        "morningBrief",
    ):
        assert _named(root, gone) == [], gone


def test_a_planner_row_exists_exactly_when_its_preference_does(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "planning")
    state = _panel(window).property("state")
    has = {
        "weekendFree": any(
            n in FIELDS
            for n in (
                "weekend_homework_free",
                "weekends_homework_free",
                "keep_weekends_free",
                "weekend_free",
            )
        ),
        "buffer": any(n in FIELDS for n in ("buffer_min", "smart_buffer_min")),
        "urgent": any(n in FIELDS for n in ("urgent_first", "prioritize_urgent")),
        "split": "split_long_tasks" in FIELDS,
        "cutoff": "day_cutoff" in FIELDS,
    }
    for key, expected in has.items():
        shown = [item for item in _named(root, "row_" + key) if item.property("visible")]
        assert bool(shown) is expected, key
        assert bool(state["show" + key[0].upper() + key[1:]]) is expected, key
    assert "auto_split_pomodoro" in FIELDS
    assert "split_long_tasks" in FIELDS
    assert state["showSplit"] is True


def test_the_planner_controls_write_the_planner_preferences(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whichever names the planner lane lands, each control writes its own one."""
    monkeypatch.setattr(bridge_settings, "_WEEKEND_FREE", "weekends_homework_free")
    monkeypatch.setattr(bridge_settings, "_BUFFER", "buffer_min")
    monkeypatch.setattr(bridge_settings, "_URGENT", "urgent_first")
    monkeypatch.setattr(bridge_settings, "_SPLIT", "split_long_tasks")
    monkeypatch.setattr(bridge_settings, "_SHOW_WEEKENDS", "show_weekends")
    _show_material(qapp, window)
    panel = _panel(window)
    heard: list[dict] = []
    monkeypatch.setattr(window.session, "save_preferences", lambda wanted, done: heard.append(wanted) or True)
    panel.setWeekendFree(True)
    panel.setBuffer(15)
    panel.setBuffer(20)
    panel.setUrgent(False)
    panel.setSplit(True)
    panel.setShowWeekends(False)
    panel.setCutoff("21:00")
    panel.setCutoff("23:00")
    assert heard == [
        {"weekends_homework_free": True},
        {"buffer_min": 15},
        {"urgent_first": False},
        {"split_long_tasks": True},
        {"show_weekends": False},
        {"day_cutoff": "21:00"},
        {"day_cutoff": "23:00"},
    ]


def test_planning_cutoff_labels_follow_the_clock(qapp: QApplication, window: NativeWindow) -> None:
    assert bridge_settings.CUTOFFS == WIDGET_CUTOFFS
    _open_settings(qapp, window, "planning")
    panel = _panel(window)
    set_clock_24h(False)
    panel._publish()
    twelve = [item["label"] for item in panel.state["cutoffChoices"]]
    assert twelve == ["No limit", *(hhmm_text(item) for item in WIDGET_CUTOFFS)]
    assert twelve[1] == "8:00 PM"
    assert twelve[-1] == "11:00 PM"
    set_clock_24h(True)
    panel._publish()
    twenty_four = [item["label"] for item in panel.state["cutoffChoices"]]
    assert twenty_four == ["No limit", *WIDGET_CUTOFFS]
    assert twenty_four[1] == "20:00"


def test_the_look_file_keeps_the_material_object_when_the_widgets_look_saves(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window)
    panel = _panel(window)
    panel.setDensity("compact")
    assert _material_file()["density"] == "compact"
    window._save_look()
    assert _material_file()["density"] == "compact"


def test_planning_cutoff_always_has_a_choice_that_is_the_current_value(
    qapp: QApplication, window: NativeWindow
) -> None:
    """With no cutoff set the row still marks "No limit", and a saved cutoff marks its own time."""
    _open_settings(qapp, window, "planning")
    panel = _panel(window)
    values = [item["value"] for item in panel.state["cutoffChoices"]]
    assert panel.state["cutoff"] == ""
    assert panel.state["cutoff"] in values
    assert next(i["label"] for i in panel.state["cutoffChoices"] if i["value"] == "") == "No limit"
    panel.setCutoff("21:00")
    wait_until(qapp, lambda: panel.state["cutoff"] == "21:00")
    assert panel.state["cutoff"] in values
    panel.setCutoff("")
    wait_until(qapp, lambda: panel.state["cutoff"] == "")
    assert panel.state["cutoff"] in values


def test_planning_cutoff_not_on_the_list_is_shown_as_its_own_time(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A saved 22:15 is not one of the usual times; it must be marked as itself, never as "No limit"."""
    _open_settings(qapp, window, "planning")
    panel = _panel(window)
    window.session.preferences["day_cutoff"] = "22:15"
    panel._publish()
    state = panel.state
    marked = [item["label"] for item in state["cutoffChoices"] if item["value"] == state["cutoff"]]
    assert marked == [hhmm_text("22:15")]
