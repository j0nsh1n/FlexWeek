"""Study hours and School hours drafts: the rules of the Widgets dialogs (AvailabilityDialog,
SchoolHoursDialog), checked without Qt. Expected values come from those rules: times sit on the 15-minute
grid, an end must be later than its start, protected times may not overlap on a shared day, and at most
21 of each."""

from __future__ import annotations

import pytest

from desktop.native.material.bridge_hours import SchoolHours, StudyHours, grid_clock
from desktop.native.weekmodel import set_clock_24h


@pytest.fixture(autouse=True)
def twelve_hour_clock():
    """The messages write times as the clock does; a new account's clock is 12-hour."""
    set_clock_24h(False)
    yield
    set_clock_24h(False)


def test_typed_times_land_on_the_fifteen_minute_grid() -> None:
    assert grid_clock("4 pm") == "16:00"
    assert grid_clock("16:07") == "16:00"
    assert grid_clock("16:29") == "16:15"
    assert grid_clock("8:30") == "08:30"
    assert grid_clock("not a time") is None


def test_an_end_of_the_day_is_24_00_and_a_start_is_not() -> None:
    assert grid_clock("24:00", end=True) == "24:00"
    study = StudyHours()
    study.add_window()
    study.set_time(study.windows, 0, "start", "24:00")
    assert study.error == "Type a time such as 4 pm or 16:00."
    assert study.windows[0]["start"] == "16:00"


def test_saved_study_hours_load_and_come_back_the_same() -> None:
    saved = {
        "work_windows": [{"days": [0, 2], "start": "15:30", "end": "18:00", "subject": "Maths"}],
        "protected": [{"days": [1], "kind": "meal", "start": "12:00", "duration_min": 45, "title": "Lunch"}],
    }
    study = StudyHours()
    study.load(saved)
    assert not study.dirty
    assert study.saved_windows() == saved["work_windows"]
    assert study.saved_protected() == saved["protected"]


def test_an_end_that_is_not_after_its_start_is_refused_in_the_dialogs_words() -> None:
    study = StudyHours()
    study.add_window({"days": [0], "start": "15:30", "end": "18:00"})
    study.set_time(study.windows, 0, "end", "3 pm")
    assert study.problem() == "End needs to be later than Start (3:30 PM)."


def test_protected_times_may_not_overlap_on_a_shared_day() -> None:
    study = StudyHours()
    study.add_protected()
    study.add_protected()
    study.set_time(study.protected_rows, 0, "start", "5 pm")
    study.set_time(study.protected_rows, 0, "end", "6 pm")
    study.set_time(study.protected_rows, 1, "start", "5:30 pm")
    study.set_time(study.protected_rows, 1, "end", "6:30 pm")
    assert study.problem() == "That overlaps protected time already on Monday."
    for day in range(5):
        study.toggle_day(study.protected_rows, 1, day)
    study.toggle_day(study.protected_rows, 1, 5)
    assert study.protected_rows[1]["days"] == [5]
    assert study.problem() == ""


def test_a_row_with_no_day_is_refused() -> None:
    study = StudyHours()
    study.add_window({"days": [3], "start": "16:00", "end": "17:00"})
    study.toggle_day(study.windows, 0, 3)
    assert study.problem() == "Pick at least one day."


def test_there_is_room_for_21_sets_of_study_hours_and_no_more() -> None:
    study = StudyHours()
    for _ in range(21):
        study.add_window()
    assert len(study.windows) == 21 and study.error == ""
    study.add_window()
    assert len(study.windows) == 21
    assert study.error == "Up to 21 sets of study hours."


def test_there_is_room_for_21_protected_times_and_no_more() -> None:
    study = StudyHours()
    for _ in range(21):
        study.add_protected()
    study.add_protected()
    assert len(study.protected_rows) == 21
    assert study.error == "Up to 21 protected times."


def test_school_hours_start_as_monday_to_friday_eight_to_three_as_setup_offers() -> None:
    """Setup's School card says 8:00 to 3:00 PM; a School made in Settings starts the same."""
    fresh = SchoolHours()
    school = SchoolHours()
    school.load(None)
    for hours in (fresh, school):
        assert (hours.days, hours.start, hours.end, hours.minutes()) == (
            [0, 1, 2, 3, 4],
            "08:00",
            "15:00",
            420,
        )


def test_school_hours_load_the_usual_school_and_refuse_an_end_before_the_start() -> None:
    school = SchoolHours()
    school.load({"id": "school", "days": [0, 1], "start": "09:00", "duration_min": 300})
    assert (school.days, school.start, school.end) == ([0, 1], "09:00", "14:00")
    school.set_time("end", "8 am")
    assert school.problem() == "End needs to be later than Start (9:00 AM)."


def test_no_school_day_ticked_is_allowed_and_means_no_school() -> None:
    school = SchoolHours()
    school.load({"id": "school", "days": [2], "start": "09:00", "duration_min": 300})
    school.toggle_day(2)
    assert school.days == [] and school.problem() == ""
