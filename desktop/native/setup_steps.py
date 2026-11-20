"""The order of the setup steps, their wording and limits, and the small rules the answers follow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from backend import clock as wall_clock
from backend.slots import hhmm_to_minutes
from desktop.native.calendar import DAYS
from desktop.native.weekmodel import clock_text, hhmm_text

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

# Material's setup is three steps over the same step numbers: School hours (WEEK), Study hours (HOMEWORK)
# and Look and alerts (REMINDERS). A saved step past the last one comes from the older five-step flow.
MATERIAL_RAIL = (
    ("School hours", (WEEK,)),
    ("Study hours", (HOMEWORK,)),
    ("Look & alerts", (REMINDERS,)),
)
MATERIAL_LAST = REMINDERS
MATERIAL_TITLES = {
    WEEK: "School hours",
    HOMEWORK: "Homework and study hours",
    REMINDERS: "Reminders and your look",
}
MATERIAL_NOTES = {
    WEEK: "Pick the closest school day. Homework is never planned during these hours.",
    HOMEWORK: "Pick how homework gets a time and when it may be planned. Also in Settings, under Planning.",
    REMINDERS: "Pick when reminders show up and how FlexWeek looks. All of this is also in Settings.",
}
# A school-day card: key, start, end, what it is, tag. Every one is Monday to Friday.
SCHOOL_CARDS = (
    ("8to3", "08:00", "15:00", "Standard school day", "Most common"),
    ("830to315", "08:30", "15:15", "Later morning bell", ""),
    ("9to330", "09:00", "15:30", "Late start", ""),
)
SCHOOL_DAYS_CARD = [0, 1, 2, 3, 4]
SCHOOL_CUSTOM_TITLE = "Different times, sports, or a job…"
SCHOOL_CUSTOM_NOTE = "Pick your own days and times, add sports, clubs or a job, and set when homework stops."
# A study-hours card: key, the work-hours preset it adds (None: none), what it is, tag.
STUDY_CARDS = (
    ("after_school", "After school", "Plan homework in the afternoon before dinner", "Popular"),
    ("evenings", "Evenings", "Keep afternoons free for sports and rest", ""),
    ("anytime", None, "FlexWeek uses any free time outside school", ""),
    ("custom", None, "Set hours for each day or class, and how far a drag moves a block", "More options"),
)
REMINDER_LEADS = (10, 5, 15)
SOUND_CARD_TITLE = "Choose an alarm sound or Spotify link…"
LOOK_MODE_CARDS = (
    ("system", "Same as this computer", "Follows light or dark from your system"),
    ("light", "Light", "A bright page with dark text"),
    ("dark", "Dark", "A dark page that's easy on the eyes at night"),
)
ROW_SIZE_CARDS = (
    ("comfortable", "Comfortable rows", "Roomier hour rows on your week"),
    ("compact", "Compact rows", "Tighter hour rows, so more of your day fits"),
)

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


SETUP_VERSION = 1


@dataclass
class SetupState:
    """What is in place now: setup opens on it, and keeps it up to date as pages are kept."""

    pack: str
    look: dict
    layout: dict
    preferences: dict
    blocks: list[dict]
    week_start: str
    subjects: list[str] = field(default_factory=list)
    # "This week: no School on Wednesday." when the open week differs from the repeats in `blocks`.
    this_week: str | None = None
    first_run: bool = True
    homework: list[str] = field(default_factory=list)
