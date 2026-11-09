"""Pictures of Day dial and One thing, the two day screens a student reaches from My day, with the
looks that the old layout tests (test_layout_dial.py, test_layout_one_thing.py) measured in code.

Both are drawn in Today's app only: neither changes with the main design. The week is the one those
tests used, on the fake clock's Thursday: School 08:00-14:30, Dinner 18:00-18:30, the History essay
18:45-19:45, the Chemistry report 20:00-21:30 and the Science poster with no time yet.
"""

from __future__ import annotations

from desktop.tests.day.support_my_day_screens import (
    DIAL_SOURCES,
    ONE_THING_SOURCES,
    STYLES,
    homework,
    locked,
    prepare_day,
)
from desktop.tests.pictures.screen import Screen

SCHOOL = locked("school", "School", [0, 1, 2, 3, 4], "08:00", 390)
DINNER = locked("dinner", "Dinner", [0, 1, 2, 3, 4, 5, 6], "18:00", 30, "meals")
FIXED = [SCHOOL, DINNER]
WORK = [
    homework("essay", "History essay", 60, "18:45"),
    homework("chem", "Chemistry report", 90, "20:00"),
    homework("poster", "Science poster", 120),
]
LONG_TITLE = "History essay outline and the annotated bibliography"

DIAL_RING = (
    "The ring is the whole day: noon at the top, midnight at the bottom, 06:00 at the left. "
    "What is over is paler than what is still to come. Neighbouring blocks are two degrees apart: "
    "the page shows between School's end at 14:30 and the free time after it, a degree (four minutes) "
    "to either side, and ten minutes away each is solid again. The free time that holds now is split "
    "at now, its elapsed part fainter."
)
DIAL_HAND = (
    "The hand stops at the ring's inner edge: the accent colour inside it and none across the ring. "
    "The time is written under the hub and the hand never crosses it; around midnight the hand points "
    "down and the time moves above the hub. Hour labels sit outside the ring, one every two hours, "
    "and none inside it (at noon the hand points at 12)."
)
DIAL_STRIP = (
    "The week's small dials: each has its day name and date under it, only today's has the hand's "
    "accent hub, and past days are paler (Monday's School arc is the pale fill, Friday's the solid "
    "mark). The strip is how another day is reached, so at Large text it is not sliced by the "
    "scroller and its day names are not cut off by the bottom of the view."
)
DIAL_FIT = (
    "The page never scrolls sideways (no horizontal scroll bar at 1024x640 or 800x560) and the face "
    "is at least 240 px wide."
)
DIAL_BUTTONS = (
    "The buttons are rounded rectangles, not pills: 4 px in from the corner a pill shows the page, "
    "while a 6 px corner is already the button's fill. The main button is at least 30 px high. The "
    "list's scroller keeps the action buttons below the rows."
)
ONE_RING = (
    "The countdown text fits inside the ring: title, line under it and the number (with its unit) are "
    "not wider than the ring's inside, at 1024x640, 1280x800 and 1440x900 and at Large text, and the "
    "title takes two lines at most. The ring's top lines up with the top of the Then list. In a short "
    "window (1366x560) the Then list gives way before the ring gets small: the ring stays 320 px wide."
)

SCREENS: list[Screen] = [
    Screen(
        id="day.dial_between_blocks",
        area="day",
        prepare=prepare_day("dial", "15:40", FIXED, WORK),
        checks=(
            "Between School and Dinner the card says Up next and 2 h 20 min free until 18:00, with "
            "Running late as the one filled button and Back to planning beside it. "
            + DIAL_BUTTONS
            + " "
            + DIAL_RING
            + " "
            + DIAL_HAND
            + " "
            + DIAL_STRIP
            + " "
            + DIAL_FIT
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.dial_during_homework",
        area="day",
        prepare=prepare_day("dial", "19:00", FIXED, WORK),
        checks=(
            "While the History essay is on, the card says Now and 45 min left, and the four actions "
            "(Homework finished filled, Start focus, Running late, Back to planning) stay in one row. "
            "The list reads the day in columns: start, title, length and a tag, with past rows marked "
            "Done and the current row marked Now; a past row is marked, not struck through (a line "
            "through the words made them hard to read). The time and length columns each end at one "
            "right edge. The waiting strip says '1 homework not placed yet' and is 36 px high. "
            + DIAL_STRIP
            + " "
            + DIAL_FIT
        ),
        sources=DIAL_SOURCES,
        main=True,
        styles=STYLES,
    ),
    Screen(
        id="day.dial_twelve_hour_columns",
        area="day",
        prepare=prepare_day(
            "dial",
            "19:00",
            FIXED,
            [*WORK, homework("study", "Study hall", 45, "10:00")],
            prefs={"clock_24h": False},
        ),
        checks=(
            "On the 12-hour clock '10:00 AM' is wider than '8:00 AM'; the time column and the length "
            "column of the list each still end at one right edge, however wide their words are."
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.dial_morning_arcs",
        area="day",
        prepare=prepare_day("dial", "13:40", FIXED, WORK),
        checks=(
            "Names are written along the arcs that fit: School's name is on its arc, Dinner's half "
            "hour is left bare, and the free time already gone is written 'Earlier today'. No name is "
            "wider than the arc it is on. The words are painted on the arc: School's arc differs from "
            "the same arc drawn without words. Every word reads at least 4.5 to 1 against its arc in "
            "light and in dark."
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.dial_empty_day",
        area="day",
        prepare=prepare_day("dial", "13:40", [], []),
        checks=(
            "With nothing planned the card says 'Free until 22:00' and the list says 'Nothing "
            "planned'. The free line is a sentence, so it is at body size and DemiBold, not set in "
            "the title size used for a block that is running. 'Free until 22:00' is written along the "
            "free arc."
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.dial_day_over",
        area="day",
        prepare=prepare_day("dial", "22:30", FIXED, WORK),
        checks=(
            "When the day is over the card says 'Nothing left today' at body size and DemiBold (not "
            "the title size), and the rows of the day are still listed, all marked over."
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.dial_look_night",
        area="day",
        prepare=prepare_day("dial", "15:40", FIXED, WORK, options={"look": "preset:dial-midnight"}),
        checks=(
            "Night is the navy colourway: the page corner is #0b0f1d. The Running late label reads at "
            "least 4.5 to 1 against its fill."
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.dial_look_daylight",
        area="day",
        prepare=prepare_day("dial", "15:40", FIXED, WORK, options={"look": "pack:light-frost"}),
        checks="Daylight is the light colourway: the page corner is #f7f8fa.",
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.dial_look_your",
        area="day",
        prepare=prepare_day("dial", "15:40", FIXED, WORK, options={"look": "your"}),
        checks=(
            "Wearing the student's own look, the page corner is the look's window colour and the "
            "Running late label reads at least 4.5 to 1 against its fill."
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.dial_accent_gold",
        area="day",
        prepare=prepare_day(
            "dial", "15:40", FIXED, WORK, options={"look": "your"}, prefs={"accent": "gold"}
        ),
        checks=(
            "With the gold accent the primary action (Running late) still reads: its label is at least "
            "4.5 to 1 against its fill, in light and in dark."
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.dial_accent_sand_night",
        area="day",
        prepare=prepare_day(
            "dial",
            "15:40",
            FIXED,
            WORK,
            options={"look": "preset:dial-midnight"},
            prefs={"accent": "sand"},
        ),
        checks=(
            "In Night with the sand accent the primary action (Running late) still reads: its label is "
            "at least 4.5 to 1 against its fill, in light and in dark."
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.one_thing_during_school",
        area="day",
        prepare=prepare_day("one", "13:40", FIXED, WORK),
        checks=(
            "During School the ring shows 50 minutes left as 50 sixtieths of the hour, and the Then "
            "list heads itself 'Later today'. The day bar's tick for now is drawn over School's "
            "segment, not hidden under it for as long as School runs. The bar names its hours "
            "(09:00, 12:00, 15:00, 18:00 under it, the first hour inside its left end) and 'Now 13:40' "
            "over the mark, with what the bar is ('Today, 06:00 to 22:00.') over its left end; nothing "
            "is written over 20:00. "
            + ONE_RING
        ),
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.one_thing_during_homework",
        area="day",
        prepare=prepare_day("one", "19:00", FIXED, WORK),
        checks=(
            "The current thing's title is set in pixels, 28 px at Normal text at weight 600, not at the "
            "heading scale's points (the fitting still takes it smaller when a small ring needs it). "
            "The time left ('45 min left') is written under the title, not only as the ring's number. "
            "Homework finished is the one filled button; Start focus, Running late and Back to "
            "planning are text buttons with no edge of their own, so their rim is the screen behind "
            "them. At Large text the 'Back to planning' button is taller than at Normal text. " + ONE_RING
        ),
        sources=ONE_THING_SOURCES,
        main=True,
        styles=STYLES,
    ),
    Screen(
        id="day.one_thing_nothing_counting",
        area="day",
        prepare=prepare_day("one", "21:40", FIXED, WORK),
        checks=(
            "At 21:40 nothing is left before 22:00, so the ring is quiet: no 0 / 15 / 30 / 45 and no "
            "twelve ticks around it (the surroundings are bare where the scale would be, while at "
            "13:40 the countdown's ticks are there), and the line says '20 min free'. 'Nothing else "
            "scheduled today' is written once."
        ),
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.one_thing_day_over",
        area="day",
        prepare=prepare_day("one", "22:30", FIXED, WORK),
        checks=(
            "Once the day is over the ring is quiet and 'Tomorrow starts with School at 08:00' fits "
            "inside it (in the tooltip too when it is too long to write)." + " " + ONE_RING
        ),
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.one_thing_long_title",
        area="day",
        prepare=prepare_day(
            "one",
            "19:00",
            FIXED,
            [homework("essay", LONG_TITLE, 60, "18:45"), WORK[1], WORK[2]],
        ),
        checks=(
            "A long title takes two lines inside the ring and the rest is shortened with an ellipsis, "
            "not cut off or run into the number; the title's height fits its box."
        ),
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.one_thing_look_poster",
        area="day",
        prepare=prepare_day("one", "19:00", FIXED, WORK, options={"look": "preset:one-poster"}),
        checks=(
            "The Poster look repaints the screen (page corner is the Poster window colour) and the "
            "ring counts down in the student's accent, not 0.16's orange #fb923c."
        ),
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.one_thing_look_poster_sea",
        area="day",
        prepare=prepare_day(
            "one",
            "19:00",
            FIXED,
            WORK,
            options={"look": "preset:one-poster"},
            prefs={"accent": "sea"},
        ),
        checks=(
            "With the sea accent the Poster ring counts down in sea, not in the default accent and "
            "not in 0.16's orange #fb923c."
        ),
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.one_thing_look_paper",
        area="day",
        prepare=prepare_day("one", "19:00", FIXED, WORK, options={"look": "preset:one-paper"}),
        checks=(
            "Paper and ink repaints the screen: the page corner is #f7f1e3. Both labels of the shared "
            "rule (the evening line and the waiting line) are in the muted ink, not in #1c1917."
        ),
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="day.one_thing_look_your",
        area="day",
        prepare=prepare_day("one", "19:00", FIXED, WORK, options={"look": "your"}),
        checks="Wearing the student's own look, the page corner is the look's window colour.",
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
]
