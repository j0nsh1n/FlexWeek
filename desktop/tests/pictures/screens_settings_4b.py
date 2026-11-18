"""Pictures of Material 3 alarms (1.5.0 step 4b): the Alarms group in Alerts, the add and edit sheet, and the
screen an alarm rings on."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.day.support_layouts_window import SPOTIFY_TRACK
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

SOURCES = (
    "desktop/native/material/qml/settings",
    "desktop/native/material/qml/sheets",
    "desktop/native/material/bridge_alarms.py",
    "desktop/native/material/bridge_sheets.py",
    "desktop/native/material/theme.py",
    "desktop/native/material/tokens.json",
)

ALARMS = [
    {
        "id": "wake",
        "name": "Wake up",
        "time": "06:45",
        "days": [0, 1, 2, 3, 4],
        "enabled": True,
        "sound": "glass",
        "spotify_url": None,
    },
    {
        "id": "practice",
        "name": "Practice reminder",
        "time": "16:30",
        "days": [1, 3],
        "enabled": True,
        "sound": "spotify",
        "spotify_url": SPOTIFY_TRACK,
    },
    {
        "id": "weekend",
        "name": "Long run",
        "time": "09:00",
        "days": [5, 6],
        "enabled": False,
        "sound": "chime",
        "spotify_url": None,
    },
]


def _alerts_with_alarms(window: NativeWindow):
    from desktop.tests.settings.support_material_settings import _prefs, _pump
    from desktop.tests.sheets.support_material_settings import open_settings

    qapp = QApplication.instance()
    root = open_settings(qapp, window, "alerts")
    window.session.save_preferences({"alarms": ALARMS})
    wait_until(qapp, lambda: len(_prefs(window).get("alarms") or []) == len(ALARMS))
    _pump(qapp, 20)
    return root


def _alarms_group(window: NativeWindow) -> object:
    from desktop.tests.settings.support_material_settings import _flick_to, _named, _pump

    root = _alerts_with_alarms(window)
    _flick_to(_named(root, "note_alarmNote")[0])
    _pump(QApplication.instance(), 10)
    return None


def _edit_sheet(window: NativeWindow) -> object:
    from desktop.tests.settings.support_material_settings import _bridge, _pump

    _alerts_with_alarms(window)
    _bridge(window).sheets.openAlarm("practice")
    _pump(QApplication.instance(), 20)
    return None


def _new_sheet_with_problems(window: NativeWindow) -> object:
    from desktop.tests.settings.support_material_settings import _bridge, _pump

    _alerts_with_alarms(window)
    sheets = _bridge(window).sheets
    sheets.openAlarm("")
    for day in range(5):
        sheets.toggleAlarmDay(day)
    sheets.setAlarmText("link", "https://example.org/song")
    sheets.saveAlarm()
    _pump(QApplication.instance(), 20)
    return None


def _ring(window: NativeWindow, *, spotify: bool) -> object:
    from desktop.tests.settings.support_material_settings import _pump

    _alerts_with_alarms(window)
    alarm = {"id": "wake", "name": "Wake up", "time": "06:45", "sound": "glass"}
    if spotify:
        alarm = {"id": "practice", "name": "Practice reminder", "time": "16:30", "sound": "spotify"}
        alarm["spotify_url"] = SPOTIFY_TRACK
    window.session._enqueue_alarm(alarm)
    _pump(QApplication.instance(), 20)
    if spotify:
        window._spotify_heard("Playing: Eye of the Tiger")
        _pump(QApplication.instance(), 10)
    return None


SCREENS: list[Screen] = [
    Screen(
        id="settings.m3_alarms_group",
        area="settings",
        prepare=_alarms_group,
        checks=(
            "Alerts scrolled to Alarms: a note, three alarms (one with Spotify, one off) with Edit, "
            "and New alarm."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_alarm_edit",
        area="sheets",
        prepare=_edit_sheet,
        checks=(
            "Edit alarm: name, hour and minute, seven day pills, sound, Spotify link, the on switch, "
            "Delete, Cancel, Save."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_alarm_new_problems",
        area="sheets",
        prepare=_new_sheet_with_problems,
        checks=(
            "New alarm with no day picked and a link that is not Spotify's: the days refusal shows in the "
            "error colour (the link is checked once a day is picked)."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_alarm_ring",
        area="sheets",
        prepare=lambda window: _ring(window, spotify=False),
        checks="An alarm ringing: its name and time, Snooze 5 minutes and Dismiss, over a dimmed window.",
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.m3_alarm_ring_spotify",
        area="sheets",
        prepare=lambda window: _ring(window, spotify=True),
        checks="A Spotify alarm ringing: Open in Spotify, what is playing, Snooze and Dismiss.",
        sources=SOURCES,
        styles=("material",),
    ),
]
