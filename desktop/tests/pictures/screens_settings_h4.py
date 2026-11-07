"""Pictures of Settings > Alerts, the reminders and More menu sheets, School hours and the look notice.

Each screen carries the looks checks the code tests of these pages used to make (contrast, cut-off
labels, positions, sizes), so the reviewer judges them on the picture."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import sanitize_look
from desktop.native.settings import HelpDialog
from desktop.native.widgets import SchoolHoursDialog
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.settings.support_alerts import WEEKDAYS, settings_page
from desktop.tests.settings.support_more import add, due_in
from desktop.tests.settings.support_new_looks_notice import NOTICE, become_an_old_account
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still

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


def _help(window: NativeWindow, width: int, height: int, *, large: bool) -> object:
    if large:
        _large_text(window)
    window.resize(width, height)
    dialog = HelpDialog(window)
    dialog.show()
    QApplication.processEvents()
    still(dialog)
    return dialog


def _help_sheet(window: NativeWindow) -> object:
    return _help(window, 1280, 800, large=False)


def _help_sheet_large_text(window: NativeWindow) -> object:
    return _help(window, 1280, 800, large=True)


def _help_scrolling_sheet(window: NativeWindow) -> object:
    return _help(window, 1280, 500, large=False)


def _help_fade_edge(window: NativeWindow) -> object:
    return _help(window, 1280, 560, large=True)


def _new_looks_notice(window: NativeWindow) -> object:
    window.resize(1280, 800)
    become_an_old_account(window)
    window._on_week()
    QApplication.processEvents()
    return window


def _ordinary_toast(window: NativeWindow) -> object:
    window.toast.show_message("Placed 1 homework block.", "Undo", lambda: None)
    QApplication.processEvents()
    return window.toast


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
    Screen(
        id="settings.help_sheet",
        area="settings",
        prepare=_help_sheet,
        checks=(
            "Help is a list sheet 600 px wide. The four screens (Day, Week, Month, My day) sit two by two,"
            " all above the shortcuts. Each shortcut is on one line: its keys at one height and not"
            " squeezed, and the words beside them break no more than one line per 12 characters ('Day,"
            " Week, Month' is not split to 'Day, Week,' and 'Month'; 'Ctrl+Y or Ctrl+Shift+Z' is on one"
            " line). The shortcuts sit on the sheet's own colour, with no box around them. Every line is"
            " shown whole."
        ),
        sources=("desktop/native/settings.py", "desktop/native/widgets.py"),
        main=True,
    ),
    Screen(
        id="settings.help_sheet_large_text",
        area="settings",
        prepare=_help_sheet_large_text,
        checks=(
            "At Large text Help is the 600 px sheet grown by the body text's ratio (as every sheet is) and"
            " it fits inside its window. Every line is shown whole: no wrapped line is taller than its"
            " room and no label is cut at the right of the scroll area. The screens are still two by two"
            " above the shortcuts, each shortcut on one line, 'Day, Week, Month' not split a word or two"
            " per line. No box is drawn around the words: the area just inside the scroll area is the"
            " sheet's own colour, the same as its margin."
        ),
        sources=("desktop/native/settings.py", "desktop/native/widgets.py", "desktop/native/look.py"),
    ),
    Screen(
        id="settings.help_scrolling_sheet",
        area="settings",
        prepare=_help_scrolling_sheet,
        checks=(
            "In a window 500 px tall Help is taller than its room and scrolls under the app's thin bar,"
            " not the system's thick one. The words take the scroll area's whole width (no thick bar"
            " taking width from them) and the thin bar lies beside the cards, not over them: the cards'"
            " right edge is left of the bar."
        ),
        sources=("desktop/native/settings.py", "desktop/native/widgets.py"),
    ),
    Screen(
        id="settings.help_fade_edge",
        area="settings",
        prepare=_help_fade_edge,
        checks=(
            "At Large text in a window 560 px tall Help scrolls and, at its top, shows a fade only at the"
            " bottom edge. The fade spans the scroll area's full width and ends at its last row, where it"
            " is all but opaque (at least 240 of 255) and exactly the sheet's own colour, so the words"
            " fade into the sheet they sit on."
        ),
        sources=("desktop/native/settings.py",),
    ),
    Screen(
        id="settings.new_looks_notice",
        area="settings",
        prepare=_new_looks_notice,
        checks=(
            f"The one-time notice '{NOTICE}' with its 'Choose a look' action and the x is a card of the"
            " look, not the dark toast: the card colour is the look's panel colour, it has a 1 px edge in"
            " the look's hairline colour and 8 px rounded corners (not the sheet's 16 px). The message,"
            " the 'Choose a look' action (in the accent) and the x each reach at least 4.5 to 1 on the"
            " card, in Light, Dark and High contrast. The week behind it has not moved or shrunk: the"
            " planner has the same position and size as in settings.more_count_none."
        ),
        sources=("desktop/native/window.py", "desktop/native/look.py", "desktop/native/widgets.py"),
        main=True,
    ),
    Screen(
        id="settings.ordinary_toast",
        area="settings",
        prepare=_ordinary_toast,
        checks=(
            "An ordinary toast ('Placed 1 homework block.' with Undo) keeps its own colours, not the"
            " notice card's: its words are the toast's text colour and Undo its action colour, both"
            " reading on the toast's background."
        ),
        sources=("desktop/native/window.py", "desktop/native/look.py", "desktop/native/widgets.py"),
    ),
]
