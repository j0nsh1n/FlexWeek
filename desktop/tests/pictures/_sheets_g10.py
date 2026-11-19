"""Sheet and notice pictures that came out of test_layouts_window.py (the lead folds this fragment into
screens_sheets.py)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication, QDialog

from desktop.native.look import resolved_palette
from desktop.native.widgets import AvailabilityDialog, HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.day.support_layouts_window import school_week, still
from desktop.tests.pictures.screen import Screen

NOTICE = "Running late: 16:30–17:00 is now locked. 2 moved."






def _opened(call: Callable[[], object]) -> QDialog:
    """The dialog `call` would run with exec, shown instead of run."""
    held: list[QDialog] = []
    original = QDialog.exec

    def show_only(dialog: QDialog) -> int:
        dialog.show()
        QApplication.processEvents()
        dialog.adjustSize()
        QApplication.processEvents()
        held.append(dialog)
        return QDialog.DialogCode.Rejected

    QDialog.exec = show_only
    try:
        call()
    finally:
        QDialog.exec = original
    return held[0]






def _account_sheet(window: NativeWindow) -> object:
    school_week(window)
    return _opened(window._open_account)


def _edit_homework_squeezed(window: NativeWindow) -> object:
    school_week(window)
    edited = HomeworkDialog(window, window.session.assignments["essay"])
    edited.setStyleSheet(window.styleSheet())
    edited.show()
    QApplication.processEvents()
    edited.resize(edited.width(), 10)
    QApplication.processEvents()
    return edited


def _availability_strip(window: NativeWindow) -> object:
    palette = resolved_palette("light-frost", False, None, "sea")
    setup_hours = [
        {"days": [0, 1, 2, 3, 4], "start": "16:00", "end": "21:00"},
        {"days": [5, 6], "start": "10:00", "end": "12:00"},
    ]
    piano = {"days": [1, 3], "start": "17:00", "duration_min": 90, "kind": "downtime"}
    dialog = AvailabilityDialog(
        None,
        {"work_windows": setup_hours, "protected": [piano], "day_cutoff": "22:00"},
        ["Math", "Reading"],
        palette,
    )
    dialog.show()
    dialog.strip.resize(420, dialog.strip.height())
    QApplication.processEvents()
    still(dialog)
    return dialog.strip


SCREENS: list[Screen] = [
    Screen(
        id="sheets.account_fits_a_laptop",
        area="sheets",
        prepare=_account_sheet,
        checks=(
            "Account is a panel, not a window: at most 700 px wide and 768 px high and at least 320 px "
            "wide (it once claimed 1338 px wide). It is opened on a 1366 x 768 laptop."
        ),
        sources=("desktop/native/settings.py",),
    ),
    Screen(
        id="sheets.edit_homework_squeezed_stays_readable",
        area="sheets",
        prepare=_edit_homework_squeezed,
        checks=(
            "The homework editor, forced down to a 10 px high window (as the audit's desktop gave it its "
            "minimum height) and styled by the window, still keeps What (its title) and the buttons row "
            "inside the sheet, and is at least 400 px high. Also check that the Add homework sheet's Due "
            "and Estimated time fields appear inside it when their question is reached, at Light and "
            "Dark frost, 1024 x 768 and 1280 x 800."
        ),
        sources=("desktop/native/widgets.py",),
    ),
    Screen(
        id="sheets.availability_strip",
        area="sheets",
        prepare=_availability_strip,
        checks=(
            "The availability strip with study hours Mon-Fri 16:00-21:00 and Sat/Sun 10:00-12:00, piano "
            "protected time Tue and Thu 17:00-18:30 and a 22:00 cut-off: Monday 17:00 and Saturday 11:00 "
            "are the accent (study hours); Monday 23:00 and Saturday 17:00 are the hairline (just the "
            "track); Tuesday 17:45 is the muted colour (protected time over study hours) and Tuesday "
            "20:00 is the accent again; Sunday 22:00 is the error colour (the cut-off line runs across "
            "every day)."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/work_windows.py"),
    ),
]
