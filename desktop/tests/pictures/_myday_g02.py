"""Pictures of My day's two screens, One thing and Day dial, on the demo's Thursday (School, Soccer
and the History essay) at the demo's sizes, with the layout checks the old test_myday_100.py made in
code. The sizes in the checks are the demo's tiers: 1024x640, 1280x800 and 1440x900.

Drawn in Today's app only (the screens do not change with the main design), on the 12-hour clock the
demo is written in.
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

CLOCK_12 = {"clock_24h": False}
SCHOOL = locked("school", "School", [0, 1, 2, 3, 4], "08:00", 390)
SOCCER = locked("soccer", "Soccer", [3], "16:00", 90, "exercise")
DEMO_FIXED = [SCHOOL, SOCCER]
DEMO_WORK = [
    homework("bio", "Biology reading", 60, "17:00", day=2),
    homework("essay", "History essay", 60, "19:00"),
    homework("poster", "Science poster", 60),
    homework("math", "Math worksheet", 60),
]
SIX_AFTER_SCHOOL = [
    SCHOOL,
    *(
        locked(name, name.title(), [3], start, 30)
        for name, start in (
            ("first", "14:30"),
            ("second", "15:00"),
            ("third", "15:30"),
            ("fourth", "16:00"),
            ("fifth", "16:30"),
            ("sixth", "17:00"),
        )
    ),
]
ONE_ROW = (
    "The four actions (Homework finished, Start focus, Running late, Back to planning) sit on one "
    "row: their centres share one line. "
)
ONE_LINE = "is on one line: it does not wrap and its label is as wide as its own text, so nothing is cut."

SCREENS: list[Screen] = [
    Screen(
        id="myday.one_thing_demo_evening",
        area="myday",
        prepare=prepare_day("one", "19:10", DEMO_FIXED, DEMO_WORK, prefs=CLOCK_12),
        checks=(
            "The ring is the demo's size for the window: 440 px at 1440 wide, 320 px at 1280 wide, "
            "and at 1024 wide 280 px (200 px at Large text). "
            + ONE_ROW
            + "The waiting line's strip is 36 px high."
        ),
        sources=ONE_THING_SOURCES,
        main=True,
        styles=STYLES,
    ),
    Screen(
        id="myday.one_thing_demo_afternoon",
        area="myday",
        prepare=prepare_day("one", "15:40", DEMO_FIXED, DEMO_WORK, prefs=CLOCK_12),
        checks=(
            "At 15:40 Soccer is next and the History essay is the one Then row; its time '7:00 PM' "
            + ONE_LINE
            + " The right column runs, top to bottom: the Then list, the action row, the evening line "
            "('Free from 8 PM until 10 PM'), then the day bar with its day letters under it."
        ),
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="myday.one_thing_then_list_scrolls",
        area="myday",
        prepare=prepare_day("one", "13:00", SIX_AFTER_SCHOOL, [], prefs=CLOCK_12),
        checks=(
            "With six things left after School the Then list shows four rows and scrolls for the rest: "
            "the fourth row ends inside the list's viewport, the list's content is taller than the "
            "viewport, and the list is at most 220 px high."
        ),
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="myday.one_thing_other_week",
        area="myday",
        prepare=prepare_day("one", "15:40", DEMO_FIXED, DEMO_WORK, prefs=CLOCK_12, weeks_on=1),
        checks=(
            "In another week the notice 'Go back to planning and open this week to see today.' "
            + ONE_LINE
            + " The list under it is headed 'Then', not 'Later today'."
        ),
        sources=ONE_THING_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="myday.dial_demo_afternoon",
        area="myday",
        prepare=prepare_day("dial", "15:40", DEMO_FIXED, DEMO_WORK, prefs=CLOCK_12),
        checks=(
            "The list's times '8 AM–2:30 PM', '4–5:30 PM' and '7–8 PM' each "
            + ONE_LINE
            + " The face is 320 px wide. The waiting strip is 36 px high. Running late and Back to "
            "planning sit on one row. Every row has its segment on the ring."
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="myday.dial_demo_evening",
        area="myday",
        prepare=prepare_day("dial", "19:10", DEMO_FIXED, DEMO_WORK, prefs=CLOCK_12),
        checks=ONE_ROW + "The face is 320 px wide and the list's times are on one line.",
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
    Screen(
        id="myday.dial_other_week",
        area="myday",
        prepare=prepare_day("dial", "15:40", DEMO_FIXED, DEMO_WORK, prefs=CLOCK_12, weeks_on=1),
        checks=(
            "In another week the notice 'Not this week — Go back to planning and open this week to see "
            "today.' " + ONE_LINE
        ),
        sources=DIAL_SOURCES,
        styles=STYLES,
    ),
]
