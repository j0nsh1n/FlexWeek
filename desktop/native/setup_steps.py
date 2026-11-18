"""The order of the setup steps, their wording and limits, and the small rules the answers follow."""

from __future__ import annotations

from datetime import date, timedelta

from backend import clock as wall_clock
from backend.slots import hhmm_to_minutes
from desktop.native.weekmodel import clock_text, hhmm_text
from desktop.native.widgets import (
    DAYS,
)

STYLE, LOOK, COLOURS, WEEK, HOMEWORK, REMINDERS, FIRST, DONE = range(8)
# The rail names six steps. Style has two more pages behind it for a student who builds their own.
RAIL = (
    ("Style", (STYLE, LOOK, COLOURS)),
    ("Your week", (WEEK,)),
    ("Homework time", (HOMEWORK,)),
    ("Reminders and alarm", (REMINDERS,)),
    ("First homework", (FIRST,)),
    ("Done", (DONE,)),
)
LOOK_STEPS = (STYLE, LOOK, COLOURS)
TITLES = {
    STYLE: "Start from a style",
    LOOK: "How do you want to see your week?",
    COLOURS: "Colours and size",
    WEEK: "Your week",
    HOMEWORK: "How should homework get a time?",
    REMINDERS: "Reminders and your alarm sound",
    FIRST: "What homework is due first?",
    DONE: "You're set",
}
NOTES = {
    STYLE: "Each sets the view, the colours and the text size together. Change any of it later in Settings.",
    LOOK: "Each one shows the same week its own way.",
    COLOURS: "The picture follows what you pick.",
    WEEK: "FlexWeek works around fixed times. Skip anything you don't have.",
    HOMEWORK: "You can change this any time in Settings, under Planning.",
    REMINDERS: (
        "Pick the sound for reminders, alarms and the end of a focus session. Spotify plays for an alarm."
        " A block starts with the Spotify link from Settings when the alarm sound is Spotify. The rest"
        " play Chime."
    ),
    FIRST: "Add up to three. You can add the rest any time.",
    DONE: "Everything here is also in Settings. Run setup again from Settings, under This computer.",
}
NEXT_LABEL, FINISH_LABEL = "Next", "Open my week"
SKIP_STEP_LABEL, SKIP_ALL_LABEL = "Skip this step", "Skip setup"
OWN_LOOK_LABEL = "Choose my own look instead"

MAX_ACTIVITIES = 8
MAX_FIRST_HOMEWORK = 3

PENDING, CURRENT, FINISHED, SKIPPED = "pending", "current", "finished", "skipped"
# What the side list says of each step's state, as the step's accessible description.
RAIL_STATES = {CURRENT: "Current step", FINISHED: "Done", SKIPPED: "Skipped", PENDING: ""}


def days_label(days: list[int]) -> str:
    """Mon–Fri for a run of days, Tue, Thu for the rest."""
    ordered = sorted(set(days))
    if len(ordered) == 7:
        return "every day"
    if len(ordered) > 2 and ordered == list(range(ordered[0], ordered[-1] + 1)):
        return f"{DAYS[ordered[0]]}–{DAYS[ordered[-1]]}"
    return ", ".join(DAYS[day] for day in ordered)


def span_label(start: str, minutes: int) -> str:
    return f"{hhmm_text(start)}–{clock_text(hhmm_to_minutes(start) + minutes)}"


SPORT_WORDS = frozenset(
    {
        "soccer",
        "football",
        "basketball",
        "swim",
        "swimming",
        "track",
        "tennis",
        "volleyball",
        "baseball",
        "hockey",
        "lacrosse",
        "softball",
        "golf",
        "wrestling",
        "cheer",
        "cheerleading",
        "rugby",
        "gym",
    }
)


def activity_category_for(title: str) -> str:
    words = {part.strip(".,!?").lower() for part in title.split() if part.strip(".,!?")}
    return "exercise" if words & SPORT_WORDS else "extra"


def next_school_day(school_days: list[int], today: date | None = None) -> str:
    """The first day after today that is a school day, as the day first homework is most likely due:
    the default of Sunday was a day with no school. With no school days picked, tomorrow."""
    today = today or wall_clock.today()
    for ahead in range(1, 8):
        day = today + timedelta(days=ahead)
        if not school_days or day.weekday() in school_days:
            return day.isoformat()
    return (today + timedelta(days=1)).isoformat()
