"""Material 3 Settings, the Focus, Alerts and This computer pages: each control writes its preference
and the app reacts."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

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
    _texts,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811


def test_the_focus_section_writes_audio_the_link_and_pomodoro(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "focus")
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


def test_the_alerts_section_writes_the_reminder_lead(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "alerts")
    _click_segment(qapp, window, _named(root, "reminder")[0], "10m")
    wait_until(qapp, lambda: _prefs(window).get("reminder_lead_min") == 10)
    assert _prefs(window).get("reminders_enabled", True) is True
    _click_segment(qapp, window, _named(root, "reminder")[0], "Off")
    wait_until(qapp, lambda: _prefs(window).get("reminders_enabled") is False)
    _click_segment(qapp, window, _named(root, "reminder")[0], "15m")
    wait_until(qapp, lambda: _prefs(window).get("reminders_enabled") is True)
    assert _prefs(window).get("reminder_lead_min") == 15


def test_a_custom_saved_reminder_lead_stays_visible_and_is_not_rewritten_on_open(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = window.session
    session.save_preferences({"reminders_enabled": True, "reminder_lead_min": 17})
    wait_until(qapp, lambda: _prefs(window).get("reminder_lead_min") == 17)
    writes: list[dict] = []
    real = session.save_preferences

    def wrapped(updates: dict, then=None) -> bool:
        writes.append(dict(updates))
        return real(updates, then)

    monkeypatch.setattr(session, "save_preferences", wrapped)
    root = _open_settings(qapp, window, "alerts")
    assert _panel(window).property("state")["reminder"] == "17"
    assert _prefs(window).get("reminder_lead_min") == 17
    assert writes == []
    labels = [str(item.property("text")) for item in _texts(_named(root, "reminder")[0])]
    assert "17m" in labels
    assert "Off" in labels and "5m" in labels and "10m" in labels and "15m" in labels

    _click_segment(qapp, window, _named(root, "reminder")[0], "Off")
    wait_until(qapp, lambda: _prefs(window).get("reminders_enabled") is False)
    assert _prefs(window).get("reminder_lead_min") == 17

    _click_segment(qapp, window, _named(root, "reminder")[0], "10m")
    wait_until(qapp, lambda: _prefs(window).get("reminder_lead_min") == 10)
    assert _prefs(window).get("reminders_enabled") is True


def test_this_computer_login_motion_and_shortcuts(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    applied: list[bool] = []
    monkeypatch.setattr(window, "_apply_start_at_login", applied.append)
    root = _open_settings(qapp, window, "computer")
    bridge = _bridge(window)
    quick = window._material_page._quick
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
    _click(qapp, window, _named(root, "row_account")[0])
    _click(qapp, window, _named(root, "row_setup")[0])
    _click(qapp, window, _named(root, "row_updates")[0])
    assert heard == ["account", "setup", "updates"]
    _click(qapp, window, _named(root, "row_pair")[0])
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "ABCD-1234")
    assert "ABCD-1234" in str(_named(root, "row_pair")[0].property("subtitle"))
