"""Material 3 Settings, the Focus, Alerts and This computer pages: each control writes its preference
and the app reacts."""

from __future__ import annotations

import re

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from backend import clock as wall_clock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import quick_of
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


def test_the_focus_section_writes_audio_and_the_link(
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


def test_this_computer_login_and_shortcuts(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    applied: list[bool] = []
    monkeypatch.setattr(window, "_apply_start_at_login", applied.append)
    root = _open_settings(qapp, window, "computer")
    bridge = _bridge(window)
    quick = quick_of(window)
    _click(qapp, window, _named(root, "startAtLogin")[0])
    wait_until(qapp, lambda: _prefs(window).get("start_at_login") is True)
    assert applied == [True]

    assert bridge.property("reduceMotion") is False
    assert _named(root, "reduceMotion") == [], "the switch is now Animations, in Look"

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


def test_this_computer_shows_a_switch_for_the_number_keys_and_one_for_the_letter_keys(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "computer")
    bridge = _bridge(window)
    numbers, letters = _named(root, "row_shortcuts")[0], _named(root, "row_letters")[0]
    assert "1 to 5" in str(numbers.property("subtitle"))
    for key in ("P", "Z", "F"):
        assert key in str(letters.property("subtitle")).split(), key
    assert bridge.property("shortcuts") is True and bridge.property("letterKeys") is False
    assert _named(root, "letters")[0].property("checked") is False, "the letter switch starts off"

    _click(qapp, window, _named(root, "letters")[0])
    wait_until(qapp, lambda: bridge.property("letterKeys") is True)
    assert _material_file()["letters"] is True
    assert _material_file()["shortcuts"] is True, "the number switch was not touched"

    _click(qapp, window, _named(root, "shortcuts")[0])
    wait_until(qapp, lambda: bridge.property("shortcuts") is False)
    assert _material_file()["shortcuts"] is False
    assert _material_file()["letters"] is True, "the letter switch was not touched"

    _click(qapp, window, _named(root, "letters")[0])
    wait_until(qapp, lambda: bridge.property("letterKeys") is False)
    assert _material_file()["letters"] is False


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
    assert _named(root, "row_pair") == [], "pairing lives in Phone & sync"
    root = _open_settings(qapp, window, "sync")
    _click(qapp, window, _named(root, "row_pair")[0])
    wait_until(qapp, lambda: _panel(window).property("state")["pairCode"] == "ABCD-1234")
    assert _panel(window).property("state")["pairOpen"] is True
    assert _named(root, "pairingDialog")[0].property("visible") is True
    assert str(_named(root, "pairingCodeText")[0].property("text")) == "ABCD-1234"
    assert "ABCD-1234" in str(_named(root, "row_pair")[0].property("subtitle"))
    _panel(window).closePairing()
    _pump(qapp)
    assert _named(root, "pairingDialog")[0].property("visible") is False


def test_an_open_pairing_code_says_how_long_it_lasts_that_it_works_once_its_tries_and_its_problems(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phone & sync opens the pairing dialog with countdown, tries, copy/restart and closes on problem."""
    status: dict = {}
    monkeypatch.setattr(
        window.session, "begin_pairing", lambda done: done({"display_code": "1234 5678"}, None) or True
    )
    monkeypatch.setattr(window.session, "pairing_status", lambda: dict(status))
    root = _open_settings(qapp, window, "sync")
    row = _named(root, "row_pair")[0]

    def subtitle() -> str:
        _pump(qapp, 5)
        return str(row.property("subtitle"))

    status.update(state="waiting", expires_at_ms=wall_clock.now_ms() + 300_500, tries_left=3)
    _click(qapp, window, row)
    wait_until(qapp, lambda: "1234 5678" in subtitle())
    words = subtitle()
    assert re.search(r"Code works for (5:00|4:59)\. 3 tries left\. It works once\.", words), words
    assert _named(root, "pairingDialog")[0].property("visible") is True
    assert "3 tries left." in str(_named(root, "pairingStatus")[0].property("text"))
    _panel(window).copyPairCode()
    assert _panel(window).property("state")["pairCopied"] is True
    status.update(tries_left=1)
    _panel(window)._pair_tick()
    assert "1 try left." in subtitle()
    _panel(window).closePairing()
    _pump(qapp)
    assert _named(root, "pairingDialog")[0].property("visible") is False

    for state, problem in (
        ("expired", "That code has expired. Start a new one."),
        ("too_many_tries", "Too many wrong tries. Start a new code."),
        ("idle", "That code is no longer open. Start a new one."),
    ):
        status.clear()
        status.update(state="waiting", expires_at_ms=wall_clock.now_ms() + 60_000, tries_left=3)
        _click(qapp, window, row)
        wait_until(qapp, lambda: "1234 5678" in subtitle())
        status.clear()
        status.update(state=state)
        _panel(window)._pair_tick()
        assert _panel(window).property("state")["pairError"] == problem, state
        assert _panel(window).property("state")["pairOpen"] is False, state
        assert subtitle() == "Show a code to link a phone.", state
        assert problem in str(_named(root, "row_pairError")[0].property("subtitle")), state
