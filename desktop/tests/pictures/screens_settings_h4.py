"""Pictures of Settings > Alerts, the reminders and More menu sheets, School hours and the look notice.

Each screen carries the looks checks the code tests of these pages used to make (contrast, cut-off
labels, positions, sizes), so the reviewer judges them on the picture."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.look import sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.settings.support_alerts import WEEKDAYS, settings_page

ALARM = {"id": "a", "name": "Wake up", "time": "07:00", "days": WEEKDAYS, "enabled": True, "sound": "chime"}


def _large_text(window: NativeWindow) -> None:
    knobs = {**(window._look.get("knobs") or {}), "text": "large"}
    window._look = sanitize_look({**window._look, "knobs": knobs})
    window._apply_appearance()


def _alerts_page(window: NativeWindow) -> object:
    return settings_page(QApplication.instance(), window, alarms=[ALARM])


def _alerts_spotify_large_text(window: NativeWindow) -> object:
    window.resize(1150, 768)
    window.show()
    _large_text(window)
    return settings_page(QApplication.instance(), window, alarm_tone="spotify")


def _alerts_alarm_row(window: NativeWindow) -> object:
    dialog = settings_page(QApplication.instance(), window, alarms=[ALARM])
    dialog._dress()
    dialog.alarm_list.setFocus()
    return dialog.alarm_list


SCREENS: list[Screen] = [
    Screen(
        id="settings.alerts_page",
        area="settings",
        prepare=_alerts_page,
        checks=(
            "Reminders is the first group and Alarms the second. The switch 'Remind me before each block"
            " starts' is above the lead, reminder sound, alarm sound and 'Leave reminders on screen'"
            " controls, and each of those is above the alarm list."
        ),
        sources=("desktop/native/settings.py",),
        main=True,
    ),
    Screen(
        id="settings.alerts_spotify_large_text",
        area="settings",
        prepare=_alerts_spotify_large_text,
        checks=(
            "At 1150 by 768 with Large text, every box on the page that shows a hint (the Spotify link's"
            " address hint among them) is wide enough for it: the hint is not cut off mid-address, with"
            " at least 24 px to spare beside the words."
        ),
        sources=("desktop/native/settings.py", "desktop/native/look.py"),
    ),
    Screen(
        id="settings.alerts_alarm_row",
        area="settings",
        prepare=_alerts_alarm_row,
        checks=(
            "The alarm list with focus shows its first row selected and outlined (a border in the"
            " list's own colour), so a student sees which alarm Remove will take."
        ),
        sources=("desktop/native/settings.py",),
    ),
]
