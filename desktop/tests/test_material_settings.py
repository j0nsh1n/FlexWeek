# ruff: noqa: F811
"""The Material settings screen: each control writes its preference and the app reacts.

Expected numbers come from the spec (hour row 44 when compact, the Blue dark surface, the
contrast floors 4.5 and 3), not from reading the QML or the bridge.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.app import Preferences  # noqa: E402
from desktop.native.material import bridge_settings  # noqa: E402
from desktop.native.material.theme import category_paint  # noqa: E402
from desktop.native.tokens import contrast  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.test_layouts_window import look_file, wait_until  # noqa: E402
from desktop.tests.test_material_window import (  # noqa: E402, F401
    _named,
    _pump,
    _qml,
    _show_material,
    qapp,
    window,
)

TOKENS = json.loads(
    (Path(__file__).parents[1] / "native" / "material" / "tokens.json").read_text(encoding="utf-8")
)
BLUE_DARK_SURFACE = "#111318"
FIELDS = set(Preferences.model_fields)


def _flick_to(item: QObject) -> None:
    """Scroll the nearest Flickable above `item` so the item is on screen."""
    parent = item.parentItem()
    while parent is not None:
        if parent.property("contentY") is not None and parent.property("contentHeight") is not None:
            content = parent.property("contentItem")
            spot = item.mapToItem(content, QPointF(0, 0))
            room = max(0.0, float(parent.property("contentHeight")) - float(parent.height()))
            parent.setProperty("contentY", max(0.0, min(room, spot.y() - 60.0)))
            return
        parent = parent.parentItem()


def _click(qapp: QApplication, window: NativeWindow, item: QObject) -> None:
    _flick_to(item)
    _pump(qapp, 5)
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    quick = window._material_page._quick
    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(centre.x()), int(centre.y())),
    )
    _pump(qapp, 10)


def _click_segment(qapp: QApplication, window: NativeWindow, seg: QObject, label: str) -> None:
    for item in _texts(seg):
        if str(item.property("text")) == label:
            _click(qapp, window, item)
            return
    raise AssertionError(f"no segment {label!r}")


def _texts(item: QObject) -> list[QObject]:
    found: list[QObject] = []
    for child in item.childItems():
        if child.property("text") is not None and child.property("font") is not None:
            found.append(child)
        found.extend(_texts(child))
    return found


def _bridge(window: NativeWindow):
    return window._material_page.bridge


def _panel(window: NativeWindow):
    return window._material_page.bridge._settings_bridge


def _material_file() -> dict:
    return json.loads(look_file().read_text(encoding="utf-8")).get("material", {})


def _open_settings(qapp: QApplication, window: NativeWindow, section: str = "look") -> QObject:
    root = _show_material(qapp, window)
    _bridge(window).showPage("settings")
    _panel(window).closeAdvanced()
    _panel(window).setSection(section)
    _pump(qapp)
    return root


def _prefs(window: NativeWindow) -> dict:
    return dict(window.session.preferences or {})


def _reset(window: NativeWindow) -> None:
    panel = _panel(window)
    panel.closeAdvanced()
    look_file().unlink(missing_ok=True)
    window._material_page.bridge.reload_material()
    panel.note_applied()
    window._use_widgets_styles()


def test_the_look_section_writes_the_clock_and_the_shell_reads_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    try:
        assert not _prefs(window).get("clock_24h")
        assert _qml(root, "materialClock").property("text") == "7:00 PM"
        _click(qapp, window, _named(root, "clock24")[0])
        wait_until(qapp, lambda: _prefs(window).get("clock_24h") is True)
        wait_until(qapp, lambda: _qml(root, "materialClock").property("text") == "19:00")
        _click(qapp, window, _named(root, "clock24")[0])
        wait_until(qapp, lambda: not _prefs(window).get("clock_24h"))
        wait_until(qapp, lambda: _qml(root, "materialClock").property("text") == "7:00 PM")
    finally:
        _reset(window)


def test_preset_mode_contrast_and_density_apply_at_once(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window)
    bridge = _bridge(window)
    try:
        _click_segment(qapp, window, _named(root, "mode")[0], "Dark")
        wait_until(qapp, lambda: _material_file().get("mode") == "dark")
        assert bridge.property("theme")["surface"] == BLUE_DARK_SURFACE
        _click_segment(qapp, window, _named(root, "mode")[0], "Light")
        wait_until(qapp, lambda: _material_file().get("mode") == "light")
        assert bridge.property("theme")["surface"] == TOKENS["Blue.light.std"]["surface"]

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
    finally:
        _reset(window)


def test_auto_mode_stores_system(qapp: QApplication, window: NativeWindow) -> None:
    """Auto is the label; the look file keeps the account's system mode, not the word auto."""
    root = _open_settings(qapp, window)
    try:
        _click_segment(qapp, window, _named(root, "mode")[0], "Dark")
        wait_until(qapp, lambda: _material_file().get("mode") == "dark")
        _click_segment(qapp, window, _named(root, "mode")[0], "Auto")
        wait_until(qapp, lambda: _material_file().get("mode") == "system")
        assert _material_file().get("mode") != "auto"
    finally:
        _reset(window)


def test_the_style_row_goes_back_to_the_widgets_styles(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window)
    button = _named(root, "useWidgets")[0]
    assert button.property("text") == "Widgets styles"
    _click(qapp, window, button)
    wait_until(qapp, lambda: window._surface == "widgets")
    _reset(window)


def test_every_section_opens_and_names_only_controls_with_a_real_effect(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    try:
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
    finally:
        _reset(window)


def test_a_planner_row_exists_exactly_when_its_preference_does(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "planning")
    try:
        state = _panel(window).property("state")
        has = {
            "weekendFree": any(
                n in FIELDS for n in ("weekends_homework_free", "keep_weekends_free", "weekend_free")
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
        assert "split_long_tasks" not in FIELDS
        assert state["showSplit"] is False
    finally:
        _reset(window)


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
    try:
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
        ]
    finally:
        _reset(window)


def test_the_focus_section_writes_audio_the_link_and_pomodoro(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "focus")
    try:
        _click_segment(qapp, window, _named(root, "focusAudio")[0], "Rain")
        wait_until(qapp, lambda: _prefs(window).get("focus_audio") == "rain")
        _click_segment(qapp, window, _named(root, "focusAudio")[0], "Spotify")
        wait_until(qapp, lambda: _prefs(window).get("focus_audio") == "spotify")
        _click_segment(qapp, window, _named(root, "focusAudio")[0], "Off")
        wait_until(qapp, lambda: _prefs(window).get("focus_audio") in (None, "off"))

        link = "https://open.spotify.com/playlist/37i9dQZF1DX8Uebhn9wzrS"
        _panel(window).setSpotify("https://example.com/not-spotify")
        assert _panel(window).property("state")["spotifyError"] == "Use a link from open.spotify.com."
        assert _prefs(window).get("default_spotify_url") != "https://example.com/not-spotify"
        _panel(window).setSpotify(link)
        wait_until(qapp, lambda: _prefs(window).get("default_spotify_url") == link)
        assert _panel(window).property("state")["spotifyError"] == ""

        _click(qapp, window, _named(root, "pomodoro")[0])
        wait_until(qapp, lambda: _prefs(window).get("timer_work_min") == 25)
        assert _prefs(window).get("timer_break_min") == 5
        _click(qapp, window, _named(root, "pomodoro")[0])
        wait_until(qapp, lambda: _prefs(window).get("timer_work_min") == 30)
    finally:
        _panel(window).setSpotify("")
        _reset(window)


def test_the_alerts_section_writes_the_reminder_lead(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "alerts")
    try:
        _click_segment(qapp, window, _named(root, "reminder")[0], "10m")
        wait_until(qapp, lambda: _prefs(window).get("reminder_lead_min") == 10)
        assert _prefs(window).get("reminders_enabled", True) is True
        _click_segment(qapp, window, _named(root, "reminder")[0], "Off")
        wait_until(qapp, lambda: _prefs(window).get("reminders_enabled") is False)
        _click_segment(qapp, window, _named(root, "reminder")[0], "15m")
        wait_until(qapp, lambda: _prefs(window).get("reminders_enabled") is True)
        assert _prefs(window).get("reminder_lead_min") == 15
    finally:
        _reset(window)


def test_this_computer_login_motion_and_shortcuts(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    applied: list[bool] = []
    monkeypatch.setattr(window, "_apply_start_at_login", applied.append)
    root = _open_settings(qapp, window, "computer")
    bridge = _bridge(window)
    quick = window._material_page._quick
    try:
        _click(qapp, window, _named(root, "startAtLogin")[0])
        wait_until(qapp, lambda: _prefs(window).get("start_at_login") is True)
        assert applied == [True]

        assert bridge.property("reduceMotion") is False
        _click(qapp, window, _named(root, "reduceMotion")[0])
        wait_until(qapp, lambda: _prefs(window).get("motion") == "reduce")
        wait_until(qapp, lambda: bridge.property("reduceMotion") is True)
        _click(qapp, window, _named(root, "reduceMotion")[0])
        wait_until(qapp, lambda: _prefs(window).get("motion") == "normal")

        assert bridge.property("shortcuts") is True
        _click(qapp, window, _named(root, "shortcuts")[0])
        wait_until(qapp, lambda: bridge.property("shortcuts") is False)
        assert _material_file()["shortcuts"] is False
        root.forceActiveFocus()
        QTest.keyClick(quick, Qt.Key.Key_2)
        _pump(qapp)
        assert bridge.property("screen") == "settings"
        _click(qapp, window, _named(root, "shortcuts")[0])
        wait_until(qapp, lambda: bridge.property("shortcuts") is True)
        root.forceActiveFocus()
        QTest.keyClick(quick, Qt.Key.Key_2)
        _pump(qapp)
        assert bridge.property("screen") == "week"
    finally:
        _prefs_back = _prefs(window)
        if _prefs_back.get("start_at_login"):
            _panel(window).setStartAtLogin(False)
            wait_until(qapp, lambda: not _prefs(window).get("start_at_login"))
        _reset(window)


def test_this_computer_account_setup_updates_and_pairing_are_wired(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    heard: list[str] = []
    monkeypatch.setattr(window, "_open_account", lambda: heard.append("account"))
    monkeypatch.setattr(window, "_run_setup_again", lambda: heard.append("setup"))
    monkeypatch.setattr(window, "_check_updates", lambda asked=False: asked and heard.append("updates"))
    seen: list[object] = []

    def begin(done: object) -> bool:
        seen.append(done)
        done({"display_code": "ABCD-1234"}, None)  # type: ignore[operator]
        return True

    monkeypatch.setattr(window.session, "begin_pairing", begin)
    root = _open_settings(qapp, window, "computer")
    try:
        _click(qapp, window, _named(root, "row_account")[0])
        _click(qapp, window, _named(root, "row_setup")[0])
        _click(qapp, window, _named(root, "row_updates")[0])
        assert heard == ["account", "setup", "updates"]
        _click(qapp, window, _named(root, "row_pair")[0])
        wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "ABCD-1234")
        assert "ABCD-1234" in str(_named(root, "row_pair")[0].property("subtitle"))
    finally:
        _reset(window)


def test_advanced_is_a_draft_until_done_and_back_drops_it(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window)
    bridge = _bridge(window)
    panel = _panel(window)
    try:
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
    finally:
        _reset(window)


def test_reset_all_returns_the_dials_to_the_preset(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window)
    panel = _panel(window)
    bridge = _bridge(window)
    try:
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
    finally:
        _reset(window)


def test_export_then_import_gives_back_the_same_look(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window)
    panel = _panel(window)
    try:
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
        assert panel.property("state")["importError"] == "That file is not a FlexWeek material look."
        panel.importText(json.dumps({"kind": "something else", "version": 1}))
        assert panel.property("state")["importError"] == "That file is not a FlexWeek material look."
    finally:
        _reset(window)


def test_the_import_and_save_prompts_open_and_report_a_bad_answer(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    try:
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
    finally:
        _reset(window)


def test_a_new_preset_asks_whether_to_keep_the_advanced_dials(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    try:
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
    finally:
        _reset(window)


def test_readability_lists_failing_colours_and_fix_makes_them_read(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    try:
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
    finally:
        _reset(window)


def test_the_preview_shows_each_real_view_and_both_sizes(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    try:
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
    finally:
        _reset(window)


def test_the_look_file_keeps_the_material_object_when_the_widgets_look_saves(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window)
    panel = _panel(window)
    try:
        panel.setDensity("compact")
        assert _material_file()["density"] == "compact"
        window._save_look()
        assert _material_file()["density"] == "compact"
    finally:
        _reset(window)
