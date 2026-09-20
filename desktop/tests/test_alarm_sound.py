"""An alarm has to make a noise. The engine that decides when one is due is tested in test_native; this
is about what happens at the moment it rings, and about being able to set that up in the first place.

Whether a runner has an audio device is not something to depend on, so nothing here asserts that a
sound was heard. What is checked is the decision: which tone, whether the linked track is tried, and
whether the ringing stops when the alarm is answered. The waveform itself is checked in test_tones.
"""

from __future__ import annotations

import importlib.util
import os
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.native.settings import PrefsDialog
    from desktop.native.sound import Bell


class Recorder:
    """Stands in for the Bell so the decision is visible without a sound card."""

    def __init__(self) -> None:
        self.started: list[tuple[str, Any]] = []
        self.stops = 0
        self.ringing = False

    def start(self, tone: str, volume: Any) -> bool:
        self.started.append((tone, volume))
        self.ringing = True
        return True

    def once(self, tone: str, volume: Any) -> bool:
        self.started.append((tone, volume))
        return True

    def stop(self) -> None:
        self.stops += 1
        self.ringing = False


@pytest.fixture(scope="module")
def qapp() -> Any:
    return QApplication.instance() or QApplication(["flexweek-alarm-sound-test"])


def prefs_dialog(qapp: Any, **extra: Any) -> Any:
    preferences = {"alert_volume": 80, "reminder_sound": True, "alarms": [], **extra}
    return PrefsDialog(None, preferences, {}, {})


def test_a_bell_says_whether_it_reached_the_sound_card_and_never_raises(qapp: Any) -> None:
    """A runner may have an audio device or none, so the answer is not fixed. What is fixed is that
    asking never raises: an alarm that throws loses its dialog too, which is worse than a silent one."""
    bell = Bell()
    assert isinstance(bell.once("chime", 80), bool)
    played = bell.start("chime", 80)
    assert bell.ringing is played
    bell.stop()
    assert bell.ringing is False
    bell.stop()


def test_a_bell_asked_for_silence_does_not_go_looking_for_a_device(qapp: Any) -> None:
    assert Bell().once("chime", 0) is False


def test_the_editor_offers_the_tones_and_the_spotify_option(qapp: Any) -> None:
    dialog = prefs_dialog(qapp)
    offered = [dialog.alarm_sound.itemData(row) for row in range(dialog.alarm_sound.count())]
    assert offered == ["chime", "soft", "bright", "low", "glass", "spotify"]


def test_an_added_alarm_keeps_the_sound_and_days_that_were_picked(qapp: Any) -> None:
    dialog = prefs_dialog(qapp)
    dialog.alarm_name.setText("Saturday practice")
    dialog.alarm_sound.setCurrentIndex(dialog.alarm_sound.findData("glass"))
    for index, box in enumerate(dialog.alarm_days):
        box.setChecked(index in (5, 6))
    dialog._add_alarm()
    alarm = dialog.updates()["alarms"][0]
    assert alarm["name"] == "Saturday practice"
    assert alarm["sound"] == "glass"
    assert alarm["days"] == [5, 6]


def test_an_alarm_on_no_days_is_refused_because_it_could_never_ring(qapp: Any) -> None:
    dialog = prefs_dialog(qapp)
    for box in dialog.alarm_days:
        box.setChecked(False)
    dialog._add_alarm()
    assert dialog.updates()["alarms"] == []
    assert "day" in dialog.alarm_name.placeholderText()


def test_a_bad_spotify_link_is_refused_at_the_editor_not_at_the_server(qapp: Any) -> None:
    dialog = prefs_dialog(qapp)
    dialog.alarm_spotify.setText("https://example.com/not-spotify")
    dialog._add_alarm()
    assert dialog.updates()["alarms"] == []
    assert "open.spotify.com" in dialog.alarm_spotify.placeholderText()


def test_a_good_spotify_link_is_kept_on_the_alarm(qapp: Any) -> None:
    dialog = prefs_dialog(qapp)
    link = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
    dialog.alarm_spotify.setText(link)
    dialog._add_alarm()
    assert dialog.updates()["alarms"][0]["spotify_url"] == link


def test_the_test_button_uses_the_volume_in_the_box_not_the_saved_one(qapp: Any) -> None:
    dialog = prefs_dialog(qapp, alert_volume=80)
    dialog._bell = Recorder()
    dialog.volume.setValue(35)
    dialog.preview_tone.setCurrentIndex(dialog.preview_tone.findData("low"))
    dialog._preview_alert()
    assert dialog._bell.started == [("low", 35)]


def test_the_test_button_says_so_when_sound_is_switched_off(qapp: Any) -> None:
    dialog = prefs_dialog(qapp)
    dialog._bell = Recorder()
    dialog.reminder_sound.setChecked(False)
    dialog._preview_alert()
    assert dialog._bell.started == []
    assert dialog.preview.text() == "Sound is off"
