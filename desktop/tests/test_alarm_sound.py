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
    from PySide6.QtWidgets import QApplication, QPushButton

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
    # The whole refusal, not a substring of the host in it: a substring check here reads to a
    # scanner as URL sanitisation, and it is a placeholder, not a guard.
    assert dialog.alarm_spotify.placeholderText() == "Use an https://open.spotify.com share link."


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


def test_a_ringing_alarm_is_big_enough_to_notice(qapp: Any) -> None:
    """It came up 209px wide, narrower than the notification it replaces. An alarm is the one thing
    in the app meant to interrupt, so it is the one thing that must not be easy to miss."""
    from desktop.native.settings import ALARM_BUTTON_HEIGHT, AlarmRingDialog

    dialog = AlarmRingDialog(None, {"name": "Wake up", "time": "06:45", "sound": "chime"}, "")
    dialog.show()
    qapp.processEvents()
    dialog.adjustSize()
    qapp.processEvents()
    assert dialog.width() >= 380
    for name in ("alarmSnooze", "alarmDismiss"):
        button = dialog.findChild(QPushButton, name)
        assert button is not None and button.height() >= ALARM_BUTTON_HEIGHT, name
    dialog.close()


def test_the_snooze_button_says_how_long_it_snoozes_for(qapp: Any) -> None:
    from desktop.native.remind import ALARM_SNOOZE_MIN
    from desktop.native.settings import AlarmRingDialog

    dialog = AlarmRingDialog(None, {"name": "Wake up", "time": "06:45"}, "")
    button = dialog.findChild(QPushButton, "alarmSnooze")
    assert button is not None and str(ALARM_SNOOZE_MIN) in button.text()


def test_auto_split_with_off_grid_lengths_is_caught_before_the_save(
    qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The server refuses this combination, so a dialog that closed on it lost the save with an
    error the student could not act on from the week screen."""
    from PySide6.QtWidgets import QMessageBox

    dialog = prefs_dialog(qapp, timer_work_min=25)
    dialog.auto_split.setChecked(True)
    dialog.work.setValue(25)
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel)
    )
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted


def test_agreeing_to_round_puts_the_lengths_on_the_grid_and_saves(
    qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    dialog = prefs_dialog(qapp)
    dialog.auto_split.setChecked(True)
    dialog.work.setValue(25)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dialog.accept()
    assert dialog.updates()["timer_work_min"] % 15 == 0
    assert dialog.result() == dialog.DialogCode.Accepted


def test_off_grid_lengths_are_fine_when_splitting_is_off(qapp: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing rounds the timers when the student is not splitting, and they are never asked to."""
    from PySide6.QtWidgets import QMessageBox

    asked: list[object] = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(
            lambda *a, **k: asked.append(a) or QMessageBox.StandardButton.Cancel  # noqa: FBT003
        ),
    )
    dialog = prefs_dialog(qapp)
    dialog.auto_split.setChecked(False)
    dialog.work.setValue(25)
    dialog.accept()
    assert asked == []
    assert dialog.updates()["timer_work_min"] == 25
    assert dialog.result() == dialog.DialogCode.Accepted


def test_release_notes_are_readable_rather_than_raw_markdown(qapp: Any) -> None:
    """GitHub release bodies are Markdown and a QLabel shows it raw, so "## What changed" and
    "- Alarms make a sound" would appear with their markers."""
    from desktop.native.settings import _first_lines

    notes = "## What changed\n\n- Alarms make a sound.\n* Splitting works.\n**Bold** matters.\n---\n"
    shown = _first_lines(notes)
    assert "##" not in shown
    assert "**" not in shown
    assert shown.splitlines()[0] == "What changed"
    assert shown.splitlines()[1].startswith("•")
    assert "---" not in shown


def test_the_notes_preview_stops_rather_than_filling_the_screen(qapp: Any) -> None:
    from desktop.native.settings import _first_lines

    assert len(_first_lines("\n".join(f"line {n}" for n in range(50))).splitlines()) == 6


def test_the_update_dialog_does_nothing_until_a_button_is_pressed(qapp: Any) -> None:
    """An updater that installs on its own is an updater that restarts the app mid-homework."""
    from desktop.native.settings import UpdateDialog

    update = {"version": "9.9.9", "asset": "a", "url": "u", "checksum_url": "c", "notes": ""}
    dialog = UpdateDialog(None, update, "0.13.0")
    assert dialog.choice == "later"
    assert dialog.skip_this is False
    dialog.findChild(QPushButton, "updateSkip").click()
    assert dialog.skip_this is True
