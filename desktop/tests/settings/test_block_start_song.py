"""The song a block plays at its start: the Settings Spotify link when the alarm sound is Spotify,
through a stand-in Spotify app (no test reaches the real one). A link stored on the block itself is
not played."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native import spotify
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.settings.support_reminders import (
    OTHER,
    OTHER_ADDRESS,
    PRACTICE_NOTICE,
    TRACK,
    TRACK_ADDRESS,
    SpotifyApp,
    add_practice,
    answer_alarm,
    at,
    choose,
    tick,
    with_stand_ins,
)
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture()
def spotify_app(monkeypatch: pytest.MonkeyPatch) -> SpotifyApp:
    player = SpotifyApp()
    monkeypatch.setattr(spotify, "system_remote", lambda: player)
    return player


@pytest.fixture()
def window(open_light: Callable[..., NativeWindow], spotify_app: SpotifyApp) -> NativeWindow:
    """A new account past setup, opened after the stand-in Spotify app is in place."""
    return with_stand_ins(open_light(size=(1280, 860)))


def test_a_stored_block_link_does_not_play_at_the_start(
    qapp: QApplication, window: NativeWindow, spotify_app: SpotifyApp
) -> None:
    """The link stays on the block for a phone that still reads it. This desktop does not play it."""
    at(18, 30)
    choose(qapp, window, reminder_lead_min=10)
    add_practice(qapp, window, spotify_url=TRACK)
    tick(qapp, window, 35)
    assert window._tray_icon.shown == [PRACTICE_NOTICE]
    rang: list = []
    window.session.alarm_due.connect(rang.append)
    for minute in range(36, 55):
        tick(qapp, window, minute)
    assert rang == [] and spotify_app.asked == []
    practice = next(block for block in window.session.blocks if block["id"] == "practice")
    assert practice["spotify_url"] == TRACK


def test_a_snoozed_block_song_plays_again_five_minutes_later(
    qapp: QApplication, window: NativeWindow, spotify_app: SpotifyApp
) -> None:
    at(18, 44)
    choose(qapp, window, alarm_tone="spotify", default_spotify_url=OTHER)
    add_practice(qapp, window, spotify_url=TRACK)
    tick(qapp, window, 44)
    heard: list = []
    answer_alarm(window, "alarmSnooze", heard)
    tick(qapp, window, 45)
    assert len(heard) == 1 and spotify_app.paused == 1
    for minute in range(46, 50):
        tick(qapp, window, minute)
    assert spotify_app.asked == [OTHER_ADDRESS]
    answer_alarm(window, "alarmDismiss", heard)
    tick(qapp, window, 50)
    assert len(heard) == 2 and spotify_app.asked == [OTHER_ADDRESS, OTHER_ADDRESS]
    assert spotify_app.paused == 2
    for minute in range(51, 58):
        tick(qapp, window, minute)
    assert spotify_app.asked == [OTHER_ADDRESS, OTHER_ADDRESS]


def test_a_block_without_a_link_plays_nothing_at_its_start(
    qapp: QApplication, window: NativeWindow, spotify_app: SpotifyApp
) -> None:
    at(18, 30)
    choose(qapp, window, reminder_lead_min=10)
    add_practice(qapp, window)
    rang: list = []
    window.session.alarm_due.connect(rang.append)
    for minute in range(30, 50):
        tick(qapp, window, minute)
    assert rang == [] and window._bell.started == [] and spotify_app.asked == []
    assert window._tray_icon.shown == [PRACTICE_NOTICE]


def test_a_block_without_a_link_plays_the_settings_link_when_the_sound_is_spotify(
    qapp: QApplication, window: NativeWindow, spotify_app: SpotifyApp
) -> None:
    at(18, 30)
    choose(qapp, window, reminder_lead_min=10, alarm_tone="spotify", default_spotify_url=TRACK)
    add_practice(qapp, window)
    tick(qapp, window, 35)
    assert window._tray_icon.shown == [PRACTICE_NOTICE]
    assert window._bell.once_rung == ["chime"], "the reminder before the start stays Chime"
    assert spotify_app.asked == []
    heard: list = []
    answer_alarm(window, "alarmDismiss", heard)
    tick(qapp, window, 45)
    assert heard and heard[0][:2] == ["Guitar practice", "6:45 PM · Starting now"]
    assert spotify_app.asked == [TRACK_ADDRESS]
    assert spotify_app.paused == 1, "dismissing stops the song"
    assert window._tray_icon.shown == [PRACTICE_NOTICE], "one notice"


def test_a_block_link_does_not_beat_the_settings_link(
    qapp: QApplication, window: NativeWindow, spotify_app: SpotifyApp
) -> None:
    at(18, 44)
    choose(qapp, window, alarm_tone="spotify", default_spotify_url=OTHER)
    add_practice(qapp, window, spotify_url=TRACK)
    answer_alarm(window, "alarmDismiss", [])
    tick(qapp, window, 45)
    assert spotify_app.asked == [OTHER_ADDRESS]


def test_a_soft_sound_and_focus_off_do_not_play_a_saved_link_when_a_block_starts(
    qapp: QApplication, window: NativeWindow, spotify_app: SpotifyApp
) -> None:
    """A link saved for Focus stays quiet at a block start when the alarm sound is Soft and focus is Off."""
    at(18, 44)
    choose(qapp, window, alarm_tone="soft", default_spotify_url=TRACK)
    assert (window.session.preferences or {}).get("focus_audio", "off") == "off"
    add_practice(qapp, window, spotify_url=OTHER)
    heard: list = []
    answer_alarm(window, "alarmDismiss", heard)
    for minute in range(44, 55):
        tick(qapp, window, minute)
    assert heard == [] and spotify_app.asked == []


def test_a_start_the_poll_reaches_a_few_minutes_late_still_plays_its_song(
    qapp: QApplication, window: NativeWindow, spotify_app: SpotifyApp
) -> None:
    at(18, 51)
    choose(qapp, window, reminder_lead_min=10, alarm_tone="spotify", default_spotify_url=TRACK)
    add_practice(qapp, window, spotify_url=OTHER)
    heard: list = []
    answer_alarm(window, "alarmDismiss", heard)
    tick(qapp, window, 51)
    assert heard and spotify_app.asked == [TRACK_ADDRESS]
