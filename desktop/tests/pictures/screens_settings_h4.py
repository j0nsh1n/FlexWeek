"""Pictures of the reminders and More menu sheets, School hours, Help and About.

Each screen carries the looks checks the code tests of these pages used to make (contrast, cut-off
labels, positions, sizes), so the reviewer judges them on the picture."""

from __future__ import annotations

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from desktop.native.look import sanitize_look
from desktop.native.settings import AboutDialog, HelpDialog
from desktop.native.widgets import SchoolHoursDialog
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still


def _large_text(window: NativeWindow) -> None:
    knobs = {**(window._look.get("knobs") or {}), "text": "large"}
    window._look = sanitize_look({**window._look, "knobs": knobs})
    window._apply_appearance()


def _school_hours_dialog(window: NativeWindow) -> object:
    dialog = SchoolHoursDialog(window, None)
    dialog.times.end.set_minutes(7 * 60)
    dialog.accept()
    dialog.show()
    return dialog








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


def _about_dialog(window: NativeWindow) -> object:
    wait_until(QApplication.instance(), lambda: window.session.storage_info is not None)
    folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    dialog = AboutDialog(window, window.session.storage_info, folder)
    dialog.show()
    QApplication.processEvents()
    still(dialog)
    return dialog




SCREENS: list[Screen] = [
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
        id="settings.about_dialog",
        area="settings",
        prepare=_about_dialog,
        checks=(
            "About FlexWeek shows the FlexWeek logo beside the product name at 56 px wide, the version,"
            " what FlexWeek is, where the week is saved, and an 'Open folder' button; nothing is cut"
            " off."
        ),
        sources=("desktop/native/settings.py",),
    ),
]
