# ruff: noqa: F811
"""The focus options in Settings: the sounds on offer, the default Spotify link, and the 15-minute
rounding of the lengths while homework is being split."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from desktop.native.settings import FOCUS_AUDIO_NOTE  # noqa: E402
from desktop.tests.sheets.support_settings import prefs_dialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-settings-focus-options-test"])


def test_focus_offers_every_sound_and_saves_the_one_chosen(qapp: QApplication) -> None:
    page = prefs_dialog(focus_audio="rain")
    try:
        offered = [page.focus_audio.itemData(index) for index in range(page.focus_audio.count())]
        assert offered == ["off", "rain", "lo-fi", "white-noise", "spotify"]
        note = page.findChild(QLabel, "prefFocusAudioNote")
        assert isinstance(note, QLabel) and note.text() == FOCUS_AUDIO_NOTE
        assert page.updates()["focus_audio"] == "rain"
        for choice in ("lo-fi", "white-noise", "spotify", "off"):
            page.focus_audio.setCurrentIndex(page.focus_audio.findData(choice))
            assert page.updates()["focus_audio"] == choice
    finally:
        page.close()


def test_a_bad_default_spotify_link_is_not_saved_and_says_why(qapp: QApplication) -> None:
    kept = "https://open.spotify.com/playlist/37i9dQZF1DX8NTLI2TtZa6"
    dialog = prefs_dialog(default_spotify_url=kept)
    dialog.spotify.setText("my study mix")
    dialog.spotify.editingFinished.emit()
    assert dialog.updates()["default_spotify_url"] == kept
    assert dialog.save_state.text() == "That link was not saved. Use an https://open.spotify.com link."


def test_turning_on_splitting_rounds_the_lengths_and_says_so(qapp: QApplication) -> None:
    """The server refuses splitting with lengths off the 15-minute grid. With no OK to ask at, turning
    splitting on is the moment: 25 becomes 30, the dialog says why, and the lengths step in 15s."""
    dialog = prefs_dialog(timer_work_min=25)
    dialog.auto_split.setChecked(True)
    assert dialog.work.value() == 30
    assert dialog.work.singleStep() == 15
    assert dialog.save_state.text() == "Focus lengths rounded to 15 minutes, which splitting needs."
    assert dialog.updates()["timer_work_min"] == 30


def test_a_half_typed_length_is_saved_rounded_while_splitting(qapp: QApplication) -> None:
    """"4" on the way to "45" can be what a pause saves, so it is saved on the grid, and leaving the
    box puts it there too."""
    dialog = prefs_dialog(auto_split_pomodoro=True, timer_work_min=30)
    dialog.work.setValue(4)
    assert dialog.updates()["timer_work_min"] == 15
    dialog.work.editingFinished.emit()
    assert dialog.work.value() == 15


def test_closing_settings_rounds_a_length_typed_while_splitting(qapp: QApplication) -> None:
    dialog = prefs_dialog(auto_split_pomodoro=True, timer_work_min=30)
    dialog.work.setValue(40)
    dialog.close_page()
    assert dialog.work.value() == 45


def test_off_grid_lengths_are_fine_when_splitting_is_off(qapp: QApplication) -> None:
    """Nothing rounds the timers when the student is not splitting, not even closing Settings."""
    dialog = prefs_dialog()
    dialog.auto_split.setChecked(False)
    dialog.work.setValue(25)
    dialog.close_page()
    assert dialog.work.value() == 25
    assert dialog.updates()["timer_work_min"] == 25
