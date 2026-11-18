"""Choices and wording that Settings and the account setup both show."""

from __future__ import annotations

from desktop.native.calendar import DAY_FULL

SPORT_FALLBACK = "Sport or club"
ALARM_TONE_LABELS = {"spotify": "A Spotify song or playlist"}
ALARM_NOTE = "An alarm rings at its time on the days you pick, until you dismiss or snooze it."
# Said above the choice, where it can wrap: as the choice's label it was wider than the page at large text.
DRAG_STEP_QUESTION = "When you drag a block, it moves in steps of this length."
DRAG_STEP_CHOICES = ((5, "5 minutes (more control)"), (15, "15 minutes (quarter hours)"))
PLANNING_STYLES = (
    ("auto", "Plan it for me as I add it", "New homework gets a time straight away."),
    (
        "suggest",
        "Plan when I press Plan my homework",
        "Homework waits in a list until you ask. This is how FlexWeek has always worked.",
    ),
    ("manual", "I'll drag it onto the calendar myself", "The planning button becomes Suggest times."),
)
SPOTIFY_LINK_HINT = (
    "Plays when a block starts if the alarm sound is Spotify, and when focus is set to Spotify."
)
SPOTIFY_TONE_REST = (
    "It plays in your Spotify app, and stopping the alarm stops it. Reminders before a block and the"
    " end of a focus session play Chime. Without the Spotify app, the link opens and Chime rings too."
)
SPOTIFY_TONE_NOTE = f"{SPOTIFY_LINK_HINT} {SPOTIFY_TONE_REST}"

# Wording the Material Settings pages share with the Widgets pages (copied from settings.py and
# widgets.py; the Widgets originals go with the Widgets styles).
STUDY_HOURS_LINE = "Choose when FlexWeek may plan homework, including hours kept for one class."
SCHOOL_HOURS_NOTE = "The days and times you're at school, so nothing is planned then."
NO_SCHOOL_DAYS = "No school days picked means no school on the calendar."
NO_STUDY_HOURS = "No study hours yet, so homework can go at any time of day."
NO_PROTECTED = "Nothing protected yet. Add practice, family time or a job."
PROTECTED_WORDS = {"downtime": "Downtime", "commute": "Commute", "meal": "Meal"}
DND_NOTE = "Each one stays in the window until you press Got it."
TRAY_NOTE = "FlexWeek waits in the tray, so reminders and alarms still come."
BLOCK_SONG_NOTE = (
    "When a block starts and the alarm sound is Spotify, the Spotify link in Settings plays. Dismiss or"
    " snooze it as you would an alarm."
)
FOCUS_AUDIO_NOTE = (
    "Rain, Lo-Fi and White noise play inside FlexWeek and pause with the timer. Spotify opens the link"
    " from Alerts when focus starts."
)
NO_SOUND = (
    "No sound played. Check that Volume is above 0 % and that your speakers or headphones are connected"
    " and not muted, then press Play again."
)
SPLIT_ROUNDED = "Focus lengths rounded to {step} minutes, which splitting needs."


def ring_days(days: list[int]) -> str:
    """The days an alarm rings, as a student would say them."""
    chosen = sorted(set(days))
    if chosen == list(range(7)):
        return "every day"
    if chosen == [0, 1, 2, 3, 4]:
        return "Monday to Friday"
    if chosen == [5, 6]:
        return "Saturday and Sunday"
    if not chosen:
        return "no days"
    if len(chosen) == 1:
        return DAY_FULL[chosen[0]]
    short = [DAY_FULL[day][:3] for day in chosen]
    return ", ".join(short[:-1]) + " and " + short[-1]
