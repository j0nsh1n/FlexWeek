"""School hours as the Add menu of the Widgets week ran them, for the tests of what saving a School
change asks and does. The form is gone; the window's standing-change save (`_save_standing`, which also
Material's Settings and Setup use) is what these tests exercise."""

from __future__ import annotations

from backend.slots import hhmm_to_minutes, minutes_to_hhmm
from desktop.native.calendar import SETUP_SCHOOL_ID
from desktop.native.weekmodel import hhmm_text
from desktop.native.window import NativeWindow


def school_hours(window: NativeWindow, end_min: int) -> None:
    """Change the usual School to end at `end_min`, then save it from this week on, saying so as the
    window does."""
    repeats = window.session.repeats
    school = next(item for item in repeats if item["id"] == SETUP_SCHOOL_ID)
    made = {**school, "duration_min": end_min - hhmm_to_minutes(school["start"])}
    after = [made if item["id"] == SETUP_SCHOOL_ID else item for item in repeats]
    start = hhmm_text(made["start"])
    end = hhmm_text(minutes_to_hhmm(hhmm_to_minutes(made["start"]) + made["duration_min"]))
    window._save_standing(
        after,
        "editing School hours",
        lambda: window._set_notice(f"School now {start}–{end} every week", "", None),
    )
