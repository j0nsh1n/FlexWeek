"""Material 3 Settings, step 4a: Alerts, Focus, Planning hours and Look carry every setting the Widgets
Settings had. Each control shows its saved value, a change saves the right preference through the backend,
and a value outside the limits is refused. Expected values are the rules' (backend Preferences limits,
TIMER_PRESETS, the 15-minute grid), not what the code prints."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from desktop.native.material.theme import contrast, scheme
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
    _prefs,
    _pump,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811


def _state(window: NativeWindow) -> dict:
    return dict(_panel(window).property("state"))


def _save(qapp: QApplication, window: NativeWindow, updates: dict) -> None:
    window.session.save_preferences(updates)
    wait_until(qapp, lambda: all(_prefs(window).get(key) == value for key, value in updates.items()))


# Alerts


def test_alerts_switches_show_the_saved_value_and_save_the_right_field(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "alerts")
    # Defaults (Preferences): sound on, do-not-disturb override off, end chime off, tray on, mute on.
    state = _state(window)
    assert (state["reminderSound"], state["dnd"], state["endChime"], state["tray"], state["autoMute"]) == (
        True,
        False,
        False,
        True,
        True,
    )
    for name, field, key, saved in (
        ("setReminderSound", "reminder_sound", "reminderSound", False),
        ("setDnd", "reminder_dnd_override", "dnd", True),
        ("setEndChime", "end_chime", "endChime", True),
        ("setTray", "tray_notifications", "tray", False),
        ("setAutoMute", "focus_auto_mute", "autoMute", False),
    ):
        getattr(_panel(window), name)(saved)
        wait_until(qapp, lambda field=field, saved=saved: _prefs(window).get(field, not saved) == saved)
        assert _state(window)[key] is saved
    assert _named(root, "row_reminderSound")


def test_a_click_on_the_sound_switch_saves_it(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "alerts")
    _click(qapp, window, _named(root, "reminderSound")[0])
    wait_until(qapp, lambda: _prefs(window).get("reminder_sound") is False)


def test_the_tone_is_saved_and_an_unknown_one_is_refused(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "alerts")
    assert _state(window)["tone"] == "chime"
    _panel(window).setTone("glass")
    wait_until(qapp, lambda: _prefs(window).get("alarm_tone") == "glass")
    assert _state(window)["tone"] == "glass"
    _panel(window).setTone("airhorn")
    _pump(qapp)
    assert _prefs(window).get("alarm_tone") == "glass"
    assert [item["value"] for item in _state(window)["toneChoices"]] == [
        "chime",
        "soft",
        "bright",
        "low",
        "glass",
        "spotify",
    ]


def test_the_volume_saves_inside_zero_to_one_hundred_and_refuses_outside(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "alerts")
    assert _state(window)["volume"] == 80
    _panel(window).setVolume(35)
    wait_until(qapp, lambda: _prefs(window).get("alert_volume") == 35)
    assert _state(window)["volume"] == 35
    for bad in (101, -1):
        _panel(window).setVolume(bad)
        _pump(qapp)
        assert _prefs(window).get("alert_volume") == 35
        assert _state(window)["notice"] == "Could not save that."


def test_play_sounds_the_chosen_tone_at_the_saved_volume(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_settings(qapp, window, "alerts")
    _save(qapp, window, {"alarm_tone": "low", "alert_volume": 40})
    heard: list[tuple[str, float]] = []
    monkeypatch.setattr(
        _panel(window)._bell, "once", lambda tone, volume: heard.append((tone, volume)) or True
    )
    _panel(window).playTone()
    assert heard == [("low", 40)]


def test_play_with_spotify_and_no_link_rings_the_chime(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_settings(qapp, window, "alerts")
    _save(qapp, window, {"alarm_tone": "spotify"})
    heard: list[str] = []
    monkeypatch.setattr(_panel(window)._bell, "once", lambda tone, volume: heard.append(tone) or True)
    _panel(window).playTone()
    assert heard == ["chime"]


def test_a_play_that_reaches_no_sound_card_says_what_to_check(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_settings(qapp, window, "alerts")
    monkeypatch.setattr(_panel(window)._bell, "once", lambda tone, volume: False)
    _panel(window).playTone()
    assert _state(window)["notice"].startswith("No sound played. Check that Volume is above 0 %")


def test_the_spotify_link_lives_on_alerts_with_the_widgets_hint(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "alerts")
    link = "https://open.spotify.com/playlist/37i9dQZF1DX8Uebhn9wzrS"
    assert _named(root, "row_spotify")
    _panel(window).setSpotify(link)
    wait_until(qapp, lambda: _prefs(window).get("default_spotify_url") == link)
    assert _state(window)["spotifyHint"].startswith("Plays when a block starts if the alarm sound is Spotify")


# Focus timer


@pytest.mark.parametrize(
    ("preset", "work", "rest", "long_rest"),
    [("short", 15, 15, 30), ("standard", 30, 15, 30), ("long", 45, 15, 30)],
)
def test_a_timer_preset_saves_all_four_lengths_and_shows_chosen(
    qapp: QApplication, window: NativeWindow, preset: str, work: int, rest: int, long_rest: int
) -> None:
    _open_settings(qapp, window, "focus")
    other = "long" if preset != "long" else "short"
    _panel(window).setTimerPreset(other)
    wait_until(qapp, lambda: _state(window)["timerPreset"] == other)
    _panel(window).setTimerPreset(preset)
    wait_until(qapp, lambda: _state(window)["timerPreset"] == preset)
    prefs = _prefs(window)
    assert (prefs.get("timer_work_min"), prefs.get("timer_break_min"), prefs.get("timer_long_break_min")) == (
        work,
        rest,
        long_rest,
    )
    assert prefs.get("timer_long_break_every") == 4


def test_custom_shows_a_slider_for_each_length_with_the_saved_values(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "focus")
    _save(qapp, window, {"timer_work_min": 50, "timer_break_min": 10, "timer_long_break_min": 20})
    state = _state(window)
    assert state["timerPreset"] == "custom"
    assert (state["timerWork"], state["timerBreak"], state["timerLong"], state["timerEvery"]) == (
        50,
        10,
        20,
        4,
    )
    for key in ("timerWork", "timerBreak", "timerLong", "timerEvery"):
        assert _named(root, key), key


def test_a_saved_25_5_timer_shows_as_custom_with_its_own_lengths(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "focus")
    _save(qapp, window, {"timer_work_min": 25, "timer_break_min": 5})
    state = _state(window)
    assert (state["timerPreset"], state["timerWork"], state["timerBreak"]) == ("custom", 25, 5)


def test_choosing_custom_changes_nothing_saved(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "focus")
    before = {
        key: _prefs(window).get(key) for key in ("timer_work_min", "timer_break_min", "timer_long_break_min")
    }
    _panel(window).setTimerPreset("custom")
    _pump(qapp)
    assert _state(window)["timerPreset"] == "custom"
    assert {key: _prefs(window).get(key) for key in before} == before


@pytest.mark.parametrize(
    ("key", "field", "ok", "bad"),
    [
        ("work", "timer_work_min", 180, (0, 181)),
        ("break", "timer_break_min", 60, (0, 61)),
        ("long", "timer_long_break_min", 120, (0, 121)),
        ("every", "timer_long_break_every", 12, (1, 13)),
    ],
)
def test_a_custom_length_saves_up_to_the_backend_limit_and_refuses_past_it(
    qapp: QApplication, window: NativeWindow, key: str, field: str, ok: int, bad: tuple[int, int]
) -> None:
    _open_settings(qapp, window, "focus")
    _panel(window).setTimerLength(key, ok)
    wait_until(qapp, lambda: _prefs(window).get(field) == ok)
    for value in bad:
        _panel(window).setTimerLength(key, value)
        _pump(qapp)
        assert _prefs(window).get(field) == ok, value
        assert _state(window)["notice"] == "Could not save that."


def test_splitting_rounds_lengths_to_the_grid_says_so_and_then_steps_in_fifteens(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "focus")
    _save(qapp, window, {"timer_work_min": 44, "timer_break_min": 14})
    _panel(window).setAutoSplit(True)
    wait_until(qapp, lambda: _prefs(window).get("auto_split_pomodoro") is True)
    prefs = _prefs(window)
    assert (prefs["timer_work_min"], prefs["timer_break_min"]) == (45, 15)
    state = _state(window)
    assert state["timerNote"] == (
        "Focus lengths were rounded to 15 minutes so FlexWeek can split them into sessions and breaks."
    )
    assert (state["timerStep"], state["timerFrom"]) == (15, 15)
    _panel(window).setTimerLength("work", 40)
    _pump(qapp)
    assert _prefs(window)["timer_work_min"] == 45
    _panel(window).setTimerLength("work", 60)
    wait_until(qapp, lambda: _prefs(window)["timer_work_min"] == 60)
    _panel(window).setAutoSplit(False)
    wait_until(qapp, lambda: not _prefs(window).get("auto_split_pomodoro"))
    assert _state(window)["timerStep"] == 1


def test_mark_homework_finished_saves_its_field(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "focus")
    assert _state(window)["autoComplete"] is False
    _panel(window).setAutoComplete(True)
    wait_until(qapp, lambda: _prefs(window).get("focus_auto_complete") is True)
    assert _state(window)["autoComplete"] is True


# Planning hours


def test_study_hours_are_a_draft_until_saved_then_they_round_trip(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "planning")
    panel = _panel(window)
    panel.addWorkPreset("After school")
    panel.setWorkSubject(0, "Maths")
    assert _state(window)["studyDirty"] is True
    assert not _prefs(window).get("work_windows")
    panel.saveStudyHours()
    wait_until(qapp, lambda: bool(_prefs(window).get("work_windows")))
    assert _prefs(window)["work_windows"] == [
        {"days": [0, 1, 2, 3, 4], "start": "15:30", "end": "18:00", "subject": "Maths"}
    ]
    wait_until(qapp, lambda: _state(window)["studyDirty"] is False)
    assert _state(window)["workWindows"][0]["start"] == "3:30 PM"


def test_study_hours_with_an_end_before_the_start_are_not_saved(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "planning")
    panel = _panel(window)
    panel.addWorkPreset("After school")
    panel.setWorkEnd(0, "3 pm")
    panel.saveStudyHours()
    _pump(qapp)
    assert _state(window)["studyError"] == "End needs to be later than Start (3:30 PM)."
    assert not _prefs(window).get("work_windows")


def test_protected_times_save_and_a_removed_one_stays_removed(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "planning")
    panel = _panel(window)
    panel.addProtected()
    panel.setProtectedKind(0, "meal")
    panel.setProtectedStart(0, "6 pm")
    panel.setProtectedEnd(0, "7 pm")
    panel.setProtectedTitle(0, "Dinner")
    panel.saveStudyHours()
    wait_until(qapp, lambda: bool(_prefs(window).get("protected")))
    assert _prefs(window)["protected"] == [
        {"days": [0, 1, 2, 3, 4], "kind": "meal", "start": "18:00", "duration_min": 60, "title": "Dinner"}
    ]
    wait_until(qapp, lambda: _state(window)["studyDirty"] is False)
    panel.removeProtected(0)
    panel.saveStudyHours()
    wait_until(qapp, lambda: not _prefs(window).get("protected"))


def test_undo_changes_puts_the_saved_study_hours_back(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "planning")
    panel = _panel(window)
    panel.addWorkCustom()
    assert len(_state(window)["workWindows"]) == 1
    panel.discardStudyHours()
    assert _state(window)["workWindows"] == [] and _state(window)["studyDirty"] is False


def test_saving_study_hours_keeps_the_cutoff_row_value(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "planning")
    _panel(window).setCutoff("21:00")
    wait_until(qapp, lambda: _prefs(window).get("day_cutoff") == "21:00")
    _panel(window).addWorkCustom()
    _panel(window).saveStudyHours()
    wait_until(qapp, lambda: bool(_prefs(window).get("work_windows")))
    assert _prefs(window).get("day_cutoff") == "21:00"


def test_school_hours_save_the_usual_school_every_week(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "planning")
    panel = _panel(window)
    assert _state(window)["schoolDays"] == [0, 1, 2, 3, 4]
    panel.setSchoolStart("9 am")
    panel.setSchoolEnd("3 pm")
    panel.toggleSchoolDay(4)
    assert _state(window)["schoolDirty"] is True
    panel.saveSchoolHours()
    wait_until(qapp, lambda: any(item.get("id") == "school" for item in window.session.repeats))
    school = next(item for item in window.session.repeats if item.get("id") == "school")
    assert (school["days"], school["start"], school["duration_min"]) == ([0, 1, 2, 3], "09:00", 360)


def test_school_hours_with_an_end_before_the_start_are_refused(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "planning")
    panel = _panel(window)
    panel.setSchoolEnd("7 am")
    panel.saveSchoolHours()
    assert _state(window)["schoolError"] == "End needs to be later than Start (8:00 AM)."
    assert not any(item.get("id") == "school" for item in window.session.repeats)


# Look


def test_the_accent_saves_and_same_as_preset_gives_the_presets_own_colours(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "look")
    bridge = _bridge(window)
    state = _state(window)
    assert state["accent"] == "default"
    assert [item["value"] for item in state["accentChoices"]][0] == "default"
    assert state["accentChoices"][0]["label"] == "Same as preset"
    own = scheme("Slate", "light", "std")["primary"]
    assert bridge.property("theme")["primary"] == own
    _panel(window).setAccent("sea")
    wait_until(qapp, lambda: _prefs(window).get("accent") == "sea")
    wait_until(qapp, lambda: bridge.property("theme")["primary"] != own)
    theme = bridge.property("theme")
    assert contrast(theme["inkPrimary"], theme["primary"]) >= 4.5
    _panel(window).setAccent("default")
    wait_until(qapp, lambda: not _prefs(window).get("accent") or _prefs(window)["accent"] == "default")
    wait_until(qapp, lambda: bridge.property("theme")["primary"] == own)
    _panel(window).setAccent("neon")
    _pump(qapp)
    assert not _prefs(window).get("accent") or _prefs(window)["accent"] == "default"


def test_the_accent_on_category_chips_paints_every_category_in_the_accent(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "look")
    bridge = _bridge(window)
    assert _state(window)["accentChips"] is False
    assert (
        bridge.property("theme")["classes"]["class"]["bar"]
        != bridge.property("theme")["classes"]["exercise"]["bar"]
    )
    _panel(window).setAccentChips(True)
    wait_until(qapp, lambda: _prefs(window).get("accent_chips") is True)
    wait_until(
        qapp,
        lambda: bridge.property("theme")["classes"]["class"]["bar"] == bridge.property("theme")["primary"],
    )
    bars = {cat: row["bar"] for cat, row in bridge.property("theme")["classes"].items()}
    assert set(bars.values()) == {bridge.property("theme")["primary"]}


def test_the_font_choice_is_saved_in_the_look_file_and_dresses_the_theme(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "look")
    bridge = _bridge(window)
    assert _state(window)["font"] == "sans"
    for choice, body, heading in (
        ("serif", "Inter", "Newsreader"),
        ("mono", "JetBrains Mono", "JetBrains Mono"),
        ("sans", "Inter", "Inter"),
    ):
        _panel(window).setFont(choice)
        wait_until(qapp, lambda choice=choice: _material_file().get("font") == choice)
        theme = bridge.property("theme")
        assert (theme["fontFamily"], theme["headingFamily"]) == (body, heading)
        assert _state(window)["font"] == choice
    _panel(window).setFont("comic")
    _pump(qapp)
    assert _material_file().get("font") == "sans"


def test_a_presets_font_and_corners_are_defaults_the_students_choice_wins(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "look")
    bridge = _bridge(window)
    _panel(window).setPreset("Terminal")
    wait_until(qapp, lambda: _material_file().get("preset") == "Terminal")
    theme = bridge.property("theme")
    assert (theme["fontFamily"], theme.get("corner")) == ("JetBrains Mono", 0)
    assert _state(window)["font"] == "mono"
    _panel(window).setFont("sans")
    wait_until(qapp, lambda: bridge.property("theme")["fontFamily"] == "Inter")
    assert bridge.property("theme").get("corner") == 0


@pytest.mark.parametrize(
    ("preset", "dark", "surface"),
    [
        ("High contrast", True, "#000000"),
        ("Paper", False, "#f7f0e1"),
        ("Ink", True, "#1c1b19"),
        ("Terminal", True, "#0d1117"),
    ],
)
def test_the_new_presets_apply_in_their_own_mode_whatever_mode_is_chosen(
    qapp: QApplication, window: NativeWindow, preset: str, dark: bool, surface: str
) -> None:
    _open_settings(qapp, window, "look")
    bridge = _bridge(window)
    _panel(window).setMode("dark" if not dark else "light")
    _panel(window).setPreset(preset)
    wait_until(qapp, lambda: _material_file().get("preset") == preset)
    wait_until(qapp, lambda: bridge.property("theme")["surface"] == surface)
    assert bridge.property("dark") is dark
    assert [item["name"] for item in _state(window)["swatches"]][-4:] == [
        "High contrast",
        "Paper",
        "Ink",
        "Terminal",
    ]
    assert _state(window)["oneMode"] == ("dark" if dark else "light")


@pytest.mark.parametrize(
    ("preset", "shown", "other"),
    [
        ("Ink", "Dark", "Light"),
        ("Terminal", "Dark", "Light"),
        ("High contrast", "Dark", "Light"),
        ("Paper", "Light", "Dark"),
    ],
)
def test_a_one_mode_preset_shows_the_mode_in_use_and_cannot_pick_another(
    qapp: QApplication, window: NativeWindow, preset: str, shown: str, other: str
) -> None:
    root = _open_settings(qapp, window, "look")
    _panel(window).setMode("system")
    _panel(window).setPreset(preset)
    wait_until(qapp, lambda: _material_file().get("preset") == preset)
    _pump(qapp, 10)
    seg = _named(root, "mode")[0]
    assert str(seg.property("current")) == shown.lower(), "the highlighted choice is the mode in use"
    by_label = {c["label"]: c["enabled"] for c in seg.property("choices").toVariant()}
    assert by_label == {"Auto": False, "Light": shown == "Light", "Dark": shown == "Dark"}
    _click_segment(qapp, window, seg, other)
    _pump(qapp, 10)
    assert _material_file().get("mode") == "system", "the disabled choice does nothing"
    _panel(window).setPreset(_state(window)["swatches"][0]["name"])
    wait_until(qapp, lambda: not _state(window)["oneMode"])
    _pump(qapp, 10)
    assert all(c["enabled"] for c in seg.property("choices").toVariant()), "a two-mode preset keeps all three"


def test_a_click_on_a_group_title_row_is_not_a_control(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "alerts")
    assert _named(root, "header_reminders") and _named(root, "header_all alerts")
    _click_segment(qapp, window, _named(root, "reminder")[0], "10m")
    wait_until(qapp, lambda: _prefs(window).get("reminder_lead_min") == 10)
