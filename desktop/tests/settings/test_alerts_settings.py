"""Settings > Alerts: reminders first, with their switch on top and their controls greyed while it is
off; alarms as their own group, each saying when it rings; one sound dropdown; plain words."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QWidget

from desktop.native.settings import SettingsPage
from desktop.tests.settings.support_alerts import WEEKDAYS, page, pages  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


def test_reminders_and_alarms_are_the_two_groups_and_the_switch_says_what_it_does(
    qapp: QApplication, pages: Callable[..., SettingsPage]
) -> None:
    # Where each sits (switch on top, controls under it, alarms last) is the picture settings.alerts_page.
    dialog = pages()
    shown = page(dialog).findChildren(QLabel, "prefsHeading")
    headings = {label.text() for label in shown if label.isVisible()}
    assert {"Reminders", "Alarms"} <= headings
    assert dialog.reminders.text() == "Remind me before each block starts"


def test_the_reminder_controls_are_greyed_while_reminders_are_off(
    qapp: QApplication, pages: Callable[..., SettingsPage]
) -> None:
    dialog = pages(reminders_enabled=False)
    controls = [dialog.lead, dialog.reminder_sound, dialog.alarm_tone, dialog.play_tone, dialog.dnd_override]
    assert [widget.isEnabled() for widget in controls] == [False] * len(controls)
    dialog.reminders.setChecked(True)
    assert [widget.isEnabled() for widget in controls] == [True] * len(controls)
    assert dialog.alarm_name.isEnabled() and dialog.volume.isEnabled(), "alarms do not depend on reminders"


def test_one_sound_dropdown_outside_the_new_alarm_and_play_uses_it_at_the_volume_in_the_box(
    qapp: QApplication, pages: Callable[..., SettingsPage]
) -> None:
    """There were two, both saying Chime: the sound, and a second one beside the volume for the Test
    button. Play plays the sound that is chosen, at the volume in the box."""
    dialog = pages(alert_volume=35, alarm_tone="low")
    combos = {box.objectName() for box in page(dialog).findChildren(QComboBox)}
    assert combos == {"prefAlarmTone", "alarmSound"}
    played: list = []
    dialog._tone_bell.once = lambda tone, volume: played.append((tone, volume)) or True
    dialog.volume.setValue(45)
    dialog.play_tone.click()
    assert played == [("low", 45)]


def test_a_sound_that_cannot_play_says_why(qapp: QApplication, pages: Callable[..., SettingsPage]) -> None:
    dialog = pages()
    dialog._tone_bell.once = lambda _tone, _volume: False
    dialog.play_tone.click()
    assert dialog.save_state.text() == (
        "No sound played. Check that Volume is above 0 % and that your speakers or headphones are "
        "connected and not muted, then press Play again."
    )


@pytest.mark.parametrize(
    ("days", "words"),
    [
        (WEEKDAYS, "Wake up · Chime\nRings at 07:00, Monday to Friday"),
        ([5, 6], "Wake up · Chime\nRings at 07:00, Saturday and Sunday"),
        (list(range(7)), "Wake up · Chime\nRings at 07:00, every day"),
        ([0, 2, 4], "Wake up · Chime\nRings at 07:00, Mon, Wed and Fri"),
        ([3], "Wake up · Chime\nRings at 07:00, Thursday"),
    ],
)
def test_each_alarm_says_when_it_rings(
    qapp: QApplication, pages: Callable[..., SettingsPage], days: list[int], words: str
) -> None:
    alarm = {"id": "a", "name": "Wake up", "time": "07:00", "days": days, "enabled": True, "sound": "chime"}
    dialog = pages(alarms=[alarm])
    assert dialog.alarm_list.item(0).text() == words
    assert dialog.alarm_empty.isHidden()


def test_no_alarms_says_so(qapp: QApplication, pages: Callable[..., SettingsPage]) -> None:
    dialog = pages()
    assert not dialog.alarm_empty.isHidden() and dialog.alarm_empty.text() == "No alarms yet."
    assert dialog.alarm_list.isHidden()


def test_the_words_say_what_each_setting_does(qapp: QApplication, pages: Callable[..., SettingsPage]) -> None:
    dialog = pages()
    # "80%", as it is written, not "80 %".
    assert dialog.volume.suffix() == "%"
    assert dialog.tray.text() == "Keep running when I close the window"
    assert dialog.findChild(QLabel, "prefTrayNote").text() == (
        "FlexWeek waits in the tray, so reminders and alarms still come."
    )
    assert dialog.dnd_override.text() == "Leave reminders on screen"
    dnd_note = dialog.findChild(QLabel, "prefDndNote").text()
    assert dnd_note == "Each one stays in the window until you press Got it."
    assert dialog.block_song_note.text() == (
        "When a block starts and the alarm sound is Spotify, the Spotify link in Settings plays. Dismiss"
        " or snooze it as you would an alarm."
    )


def test_a_new_alarm_starts_at_seven_names_its_spotify_field_and_offers_remove_only_with_alarms(
    qapp: QApplication, pages: Callable[..., SettingsPage]
) -> None:
    """A new alarm started at 00:00, its Spotify field had no label, and Remove alarm showed with no
    alarm to remove."""
    dialog = pages()
    assert dialog.alarm_time.time().toString("HH:mm") == "07:00"
    form = dialog.alarm_spotify.parentWidget().layout()
    label = form.labelForField(dialog.alarm_spotify)
    assert isinstance(label, QLabel) and label.text() == "Spotify link" and label.isVisible()
    assert dialog.remove_alarm.isHidden(), "nothing to remove yet"
    dialog.alarm_name.setText("Wake up")
    dialog.findChild(QWidget, "addAlarm").click()
    assert [alarm["time"] for alarm in dialog.updates()["alarms"]] == ["07:00"]
    assert not dialog.remove_alarm.isHidden()
    dialog.alarm_list.setCurrentRow(0)
    dialog.remove_alarm.click()
    assert dialog.remove_alarm.isHidden()


def test_alarm_rows_take_focus_and_select_the_row_remove_will_take(
    qapp: QApplication, pages: Callable[..., SettingsPage]
) -> None:
    """Tab and the arrow keys gave no focus or selection on alarm rows. How the row is outlined is the
    picture settings.alerts_alarm_row."""
    alarm = {
        "id": "a",
        "name": "Wake up",
        "time": "07:00",
        "days": WEEKDAYS,
        "enabled": True,
        "sound": "chime",
    }
    dialog = pages(alarms=[alarm])
    dialog._dress()
    dialog.alarm_list.setFocus()
    assert dialog.alarm_list.hasFocus()
    assert dialog.alarm_list.currentRow() == 0
    assert dialog.alarm_list.item(0).isSelected()
    QTest.keyClick(dialog.alarm_list, Qt.Key.Key_Down)
    assert dialog.alarm_list.currentRow() == 0 and dialog.alarm_list.item(0).isSelected()
