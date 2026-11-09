# ruff: noqa: F811
"""Setting up an alarm in Settings: the sounds it offers, the days and sound that are kept, what is
refused at the editor instead of at the server, and the Play button. When an alarm rings is
focus/test_alarm_bell.py and focus/test_spotify_alarm.py."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.tests.sheets.support_settings import prefs_dialog  # noqa: E402


class Recorder:
    """Stands in for the Bell so the decision is visible without a sound card."""

    def __init__(self) -> None:
        self.started: list[tuple[str, Any]] = []

    def start(self, tone: str, volume: Any) -> bool:
        self.started.append((tone, volume))
        return True

    def once(self, tone: str, volume: Any) -> bool:
        self.started.append((tone, volume))
        return True

    def stop(self) -> None:
        pass


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-alarm-editor-test"])


def test_the_editor_offers_the_tones_and_the_spotify_option(qapp: QApplication) -> None:
    dialog = prefs_dialog()
    offered = [dialog.alarm_sound.itemData(row) for row in range(dialog.alarm_sound.count())]
    assert offered == ["chime", "soft", "bright", "low", "glass", "spotify"]


def test_an_added_alarm_keeps_the_sound_and_days_that_were_picked(qapp: QApplication) -> None:
    dialog = prefs_dialog()
    dialog.alarm_name.setText("Saturday practice")
    dialog.alarm_sound.setCurrentIndex(dialog.alarm_sound.findData("glass"))
    for index, box in enumerate(dialog.alarm_days):
        box.setChecked(index in (5, 6))
    dialog._add_alarm()
    alarm = dialog.updates()["alarms"][0]
    assert alarm["name"] == "Saturday practice"
    assert alarm["sound"] == "glass"
    assert alarm["days"] == [5, 6]


def test_an_alarm_on_no_days_is_refused_because_it_could_never_ring(qapp: QApplication) -> None:
    dialog = prefs_dialog()
    for box in dialog.alarm_days:
        box.setChecked(False)
    dialog._add_alarm()
    assert dialog.updates()["alarms"] == []
    assert "day" in dialog.alarm_name.placeholderText()


def test_a_bad_spotify_link_is_refused_at_the_editor_not_at_the_server(qapp: QApplication) -> None:
    dialog = prefs_dialog()
    dialog.alarm_spotify.setText("https://example.com/not-spotify")
    dialog._add_alarm()
    assert dialog.updates()["alarms"] == []
    # The whole refusal, not a substring of the host in it: a substring check here reads to a
    # scanner as URL sanitisation, and it is a placeholder, not a guard.
    assert dialog.alarm_spotify.placeholderText() == "Use an https://open.spotify.com share link."


def test_a_good_spotify_link_is_kept_on_the_alarm(qapp: QApplication) -> None:
    dialog = prefs_dialog()
    link = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
    dialog.alarm_spotify.setText(link)
    dialog._add_alarm()
    assert dialog.updates()["alarms"][0]["spotify_url"] == link


def test_play_uses_the_volume_in_the_box_not_the_saved_one(qapp: QApplication) -> None:
    dialog = prefs_dialog(alert_volume=80)
    dialog._tone_bell = Recorder()
    dialog.volume.setValue(35)
    dialog.alarm_tone.setCurrentIndex(dialog.alarm_tone.findData("low"))
    dialog.play_tone.click()
    assert dialog._tone_bell.started == [("low", 35)]
