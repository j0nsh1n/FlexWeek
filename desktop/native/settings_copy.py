"""Choices and wording that Settings and the account setup both show."""

from __future__ import annotations

SPORT_FALLBACK = "Sport or club"
ALARM_TONE_LABELS = {"spotify": "A Spotify song or playlist"}
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
