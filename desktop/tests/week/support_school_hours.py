"""School hours as the Add menu of the Widgets week ran them, for the tests of what saving a School
change asks and does. The menu is gone; the form (`SchoolHoursDialog`) and the window's standing-change
save (`_save_standing`, which also Material's Settings and Setup use) are what these tests exercise."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QDialog

from backend.slots import hhmm_to_minutes, minutes_to_hhmm
from desktop.native.calendar import SETUP_SCHOOL_ID, this_week_line
from desktop.native.weekmodel import hhmm_text
from desktop.native.widgets import SchoolHoursDialog
from desktop.native.window import NativeWindow


def school_hours(window: NativeWindow, run: Callable[[SchoolHoursDialog], QDialog.DialogCode]) -> None:
    """Open the form on the usual School and this week's line, let `run` fill it in and answer it, then
    save what it made from this week on, saying so as the window does."""
    repeats = window.session.repeats
    school = next((item for item in repeats if item["id"] == SETUP_SCHOOL_ID), None)
    clock_24h = (window.session.preferences or {}).get("clock_24h") is True
    line = (
        this_week_line(window.session.blocks, [school], clock_24h, window.session.week_start)
        if school is not None
        else None
    )
    dialog = SchoolHoursDialog(window, school, this_week=line)
    if run(dialog) != QDialog.DialogCode.Accepted:
        return
    made = dialog.block()
    if made is not None:
        after = [made if item["id"] == SETUP_SCHOOL_ID else item for item in repeats]
        if school is None:
            after = [made, *repeats]
        start = hhmm_text(made["start"])
        end = hhmm_text(minutes_to_hhmm(hhmm_to_minutes(made["start"]) + made["duration_min"]))
        window._save_standing(
            after,
            "editing School hours",
            lambda: window._set_notice(f"School now {start}–{end} every week", "", None),
        )
    elif school is not None:
        window._delete_block(school, "series", None, every_week=True)
