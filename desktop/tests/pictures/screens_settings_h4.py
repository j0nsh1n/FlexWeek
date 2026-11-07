"""Pictures of Settings > Alerts, the reminders and More menu sheets, School hours and the look notice.

Each screen carries the looks checks the code tests of these pages used to make (contrast, cut-off
labels, positions, sizes), so the reviewer judges them on the picture."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import sanitize_look
from desktop.native.widgets import SchoolHoursDialog
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.settings.support_alerts import WEEKDAYS, settings_page
from desktop.tests.settings.support_more import add, due_in
from desktop.tests.waiting import wait_until

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


def _school_hours_dialog(window: NativeWindow) -> object:
    dialog = SchoolHoursDialog(window, None)
    dialog.times.end.set_minutes(7 * 60)
    dialog.accept()
    dialog.show()
    return dialog


def _more_count(window: NativeWindow, homework: list[tuple[str, str, int, int]]) -> object:
    """The classic week with School and the given homework (key, title, minutes, days into the week it
    is due), none of it placed, so the count on More shows what is left."""
    app = QApplication.instance()
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._apply_appearance()
    window.session.set_view("week")
    window.resize(1280, 860)
    window.show()
    window.session.add_block({"id": "school", "title": "School", "kind": "locked", "start": "08:00",
                              "duration_min": 390, "days": [0, 1, 2, 3, 4]})
    for key, title, minutes, days in homework:
        add(window, key, title, minutes, due_in(window, days))
    window.session.save()
    wait_until(app, lambda: not window.session.busy and not window.session.dirty)
    window._on_week()
    wait_until(app, lambda: window.planner.currentWidget() is window.week_table)
    return window._top_bar


def _more_count_none(window: NativeWindow) -> object:
    return _more_count(window, [])


def _more_count_two(window: NativeWindow) -> object:
    return _more_count(window, [("history", "History", 120, 9), ("bio", "Bio", 60, 5)])


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
    Screen(
        id="settings.school_hours_dialog",
        area="settings",
        prepare=_school_hours_dialog,
        checks=(
            "School hours with an End before the Start shows the error 'End needs to be later than Start"
            " (08:00).' and the dialog stays open. Save is the one filled button, Cancel is quiet (an"
            " outline or plain text), and the error is readable and not hidden behind the buttons."
        ),
        sources=("desktop/native/widgets.py",),
    ),
    Screen(
        id="settings.more_count_none",
        area="settings",
        prepare=_more_count_none,
        checks=(
            "The top bar of a week with nothing left to plan: no count on More and no bar above the week."
            " Its height, More's size and where the week starts are the baseline for"
            " settings.more_count_two, which must match them to the pixel."
        ),
        sources=("desktop/native/window.py", "desktop/native/look.py"),
    ),
    Screen(
        id="settings.more_count_two",
        area="settings",
        prepare=_more_count_two,
        checks=(
            "With two homework items still needing a time the count is a pill over More's corner and"
            " nothing else moved: the top bar has the same height, More the same size and the week starts"
            " at the same place as in settings.more_count_none (0 px difference). The pill's fill reads at"
            " least 3 to 1 against the bar and its number at least 4.5 to 1 against the pill, in Light,"
            " Dark and High contrast."
        ),
        sources=("desktop/native/window.py", "desktop/native/look.py"),
        main=True,
    ),
]
