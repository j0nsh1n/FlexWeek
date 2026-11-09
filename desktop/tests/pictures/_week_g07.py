"""The Bento and Mission control weeks as pictures: what the old layout tests asserted about where
things sit, how big they are, their colours and what fits. The aggregator collects SCREENS."""

from __future__ import annotations

from collections.abc import Callable

from desktop.native.window import NativeWindow
from desktop.tests.day.support_designs import at, locked, seed_week, show_design
from desktop.tests.pictures.screen import Screen

BENTO = ("desktop/native/layouts/bento.py", "desktop/native/hours", "desktop/native/layouts/base.py")
MISSION = ("desktop/native/layouts/mission.py", "desktop/native/hours", "desktop/native/layouts/base.py")
LOOKS = ("desktop/native/look.py", "desktop/native/tokens.py", "desktop/native/layouts/registry.py")


# The block that comes next after 15:40, with a title too long for its tile.
LONG_NEXT = locked("long", "History essay outline and annotated bibliography", "extra", "16:00", 45, [3])


def bento_week(
    clock: tuple[int, int] = (15, 40),
    size: tuple[int, int] | None = None,
    extra: tuple[dict, ...] = (),
    **options: str,
) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        at(*clock)
        seed_week(window, extra=extra)
        if size is not None:
            window.resize(*size)
        return show_design(window, "bento", **options)

    return prepare


def mission_week(
    clock: tuple[int, int] = (18, 2),
    size: tuple[int, int] | None = None,
    more: tuple[dict, ...] = (),
    **options: str,
) -> Callable[[NativeWindow], object]:
    extra = (
        locked("bell", "Bell", "extra", "18:00", 5, [3]),
        locked("piano", "Piano lesson", "extra", "17:00", 45, [2]),
        locked("chemistry", "Chemistry", "extra", "21:15", 45, [4]),
        locked("paper-round", "Paper round", "extra", "05:00", 45, [3]),
        locked("quiz", "Quiz", "extra", "10:00", 15, [4]),
        *more,
    )

    def prepare(window: NativeWindow) -> object:
        at(*clock)
        seed_week(window, extra=extra)
        if size is not None:
            window.resize(*size)
        return show_design(window, "mission", **options)

    return prepare


def many_homework(window: NativeWindow) -> object:
    at(13, 40)
    seed_week(window)
    for number in range(4):
        window.session.add_homework(
            {"id": f"reading{number}", "title": f"Reading {number}", "due": "2026-11-08T23:59",
             "estimate_min": 30, "revision": 0}
        )
    window.resize(1366, 490)
    return show_design(window, "mission")


def untyped_in_dark(window: NativeWindow) -> object:
    at(15, 40)
    seed_week(window, extra=(locked("plain", "Untyped event", "", "21:00", 60, [3]),))
    return show_design(window, "bento", look="pack:dark-frost")


def bento_look(value: str) -> Callable[[NativeWindow], object]:
    return bento_week(look=value)


BENTO_LOOKS = {
    "indigo": "preset:bento-indigo",
    "high_contrast": "preset:high-contrast",
    "poster": "preset:poster",
    "dark": "pack:dark-frost",
    "light": "pack:light-frost",
    "match_my_look": "your",
}
MISSION_LOOKS = {
    "flight_deck": "preset:flight-deck",
    "high_contrast": "preset:high-contrast",
    "terminal": "preset:terminal",
    "dark": "pack:dark-frost",
    "light": "pack:light-frost",
}

CORNERS = {
    "flight_deck": "#0b0f14",
    "high_contrast": "#000000",
    "terminal": "its own, not one of the others",
    "dark": "#111315",
    "light": "#f7f8fa",
}

SCREENS: list[Screen] = [
    Screen(
        id="week.bento_week",
        area="week",
        prepare=bento_week(),
        checks=(
            "Seven day headers each write the whole day word and the date (Mon 2, never a single letter "
            "and digit such as F 2), at 1024 and 1280 wide and at Normal and Large text, including the "
            "empty weekend columns, and each header sits over its column within 6 px. At 1280 the five "
            "weekday columns are equal in width (within 1 px). The category mark on a block is a 3 px "
            "vertical edge line, not a glyph. The pill that gives the time now sits in the hour gutter to "
            "the left of today's column and covers none of the column (its right edge at least 2 px short "
            "of the column). Blocks that share a column show one title line each, a single block up to "
            "two. Monday's two blocks that share a quarter hour sit side by side."
        ),
        sources=BENTO,
        main=True,
    ),
    Screen(
        id="week.bento_due_rows",
        area="week",
        prepare=bento_week(size=(1150, 768)),
        checks=(
            "Each Due soon row's second line (for example placed Thu 20:00, Not placed) fits whole inside "
            "the tile: the tile never cuts the placed time, at 1280 by 764 and at 1150 by 768 in the "
            "window's own body font (13 pt Inter). All three rows say it the same way, none without the "
            "length the others have."
        ),
        sources=BENTO,
    ),
    Screen(
        id="week.bento_cramped",
        area="week",
        prepare=bento_week(size=(800, 700)),
        checks=(
            "In a narrow window (800 by 700, and 1150 wide with Large text) the tiles sit under the hero, "
            "except Not placed yet, which stays beside the hours (its left edge past the hero's right edge, "
            "its top level with the hero's top). The page does not scroll sideways. At 1024 by 740 the "
            "cards below the window are reached by scrolling the board."
        ),
        sources=BENTO,
    ),
    Screen(
        id="week.bento_today_hero",
        area="week",
        prepare=bento_week(hero="today", extra=(LONG_NEXT,)),
        checks=(
            "With the Today hero, the first homework not placed yet stays fully in sight beside the hours "
            "(its chip not cut by the scroll area or a tile) and the hours have at least 88 px of height, "
            "at 1150 by 568 and 1132 by 484 with Large text, 1132 by 499, 782 by 430 and 460, and 1262 by "
            "711, even when the next block's title is long. The six other day tiles sit around the hero "
            "and a tile lifts only a little under the pointer."
        ),
        sources=BENTO,
    ),
    Screen(
        id="week.bento_untyped_block_dark",
        area="week",
        prepare=untyped_in_dark,
        checks=(
            "In the Dark look (once called Midnight) a block with no category is readable: its fill is "
            "the surface colour and its words are the look's text colour."
        ),
        sources=(*BENTO, *LOOKS),
    ),
    *[
        Screen(
            id=f"week.bento_look_{name}",
            area="week",
            prepare=bento_look(value),
            checks=(
                f"The {name.replace('_', ' ')} colourway paints the hero in words that read: the hero's "
                "words and its muted words keep at least AA text contrast (4.5:1) against the hero. The "
                "hero's fill is the look's hero colour, and the Homework load tile is the surface colour. "
                "For Match my look the hero is the accent colour and its words are the accent's ink."
            ),
            sources=(*BENTO, *LOOKS),
        )
        for name, value in BENTO_LOOKS.items()
    ],
    Screen(
        id="week.mission_week",
        area="week",
        prepare=mission_week(),
        checks=(
            "The week opens at 56 px an hour with 08:00 to 22:00 across the lanes at 1280 wide. A block "
            "stays a filled bar until it would be under 8 px wide (Dinner's half hour is a bar; a five "
            "minute Bell zoomed out is a tick drawn in the category's mark colour). Early and quarter hour "
            "blocks have a bar at least 10 px wide and 14 px tall. The line for now crosses a block it lies "
            "on, goes over the block's colour, stops short of a block's words and of a tick's icon and "
            "resumes on the mark. The pill that gives the time now covers no hour label, at 40 and at 56 px "
            "an hour. A name too long for its block is written beside it where the lane is free, inside "
            "what shows (not past the right edge of the lanes), at most two lines inside its lane. The "
            "midnight hour label is not left of the lanes. School's name fits inside its bar, so nothing is "
            "written before it."
        ),
        sources=MISSION,
        main=True,
    ),
    Screen(
        id="week.mission_now_line_names",
        area="week",
        prepare=mission_week(
            clock=(15, 40), more=(locked("lesson", "Piano lesson", "extra", "15:40", 45, [3]),)
        ),
        checks=(
            "At 15:40 the line for now lies on the Piano lesson's block. The name written beside the block "
            "is not crossed by the line: the line stops short of the name's box (about 2 px clear) and "
            "the name's pixels are the same with and without the line."
        ),
        sources=MISSION,
    ),
    Screen(
        id="week.mission_shared_time",
        area="week",
        prepare=mission_week(clock=(13, 40), size=(1280, 744)),
        checks=(
            "Monday's maths (15:45 to 16:30) shares a quarter hour with the robotics club (15:15 to "
            "16:00). They sit side by side in Monday's lane, and each is as tall as a block alone in its "
            "lane (the lane takes the room of two). Too short for their names, each has its name written "
            "after it, in its own row (some dark ink after each block). Each day's name stays beside its "
            "lane, level with the lane's middle."
        ),
        sources=MISSION,
    ),
    Screen(
        id="week.mission_layout",
        area="week",
        prepare=mission_week(clock=(13, 40)),
        checks=(
            "The deadline table sits beside the lanes at 1280 by 760, and at 1150 by 700 with Large text "
            "(it holds the only handle on homework not placed yet), and goes under them below 924 px (900 "
            "by 700). The four figures sit in one row when wide and fold two over two at 800 by 700; the "
            "page does not scroll sideways."
        ),
        sources=MISSION,
    ),
    Screen(
        id="week.mission_many_homework",
        area="week",
        prepare=many_homework,
        checks=(
            "Seven homework make a table taller than a laptop's short window (1366 by 490). Its rows scroll "
            "inside it, every lane is on screen and the page itself does not scroll."
        ),
        sources=MISSION,
    ),
    *[
        Screen(
            id=f"week.mission_look_{name}",
            area="week",
            prepare=mission_week(clock=(13, 40), look=value),
            checks=(
                "The look repaints the console: the page's top left corner is the look's own background"
                f" colour ({CORNERS[name]}), different from every other look's."
                + (
                    " Flight deck keeps its own colours whichever look and accent the student wears: "
                    "background #0b0f14, surface #121821, accent #7fa8ff, in light and dark."
                    if name == "flight_deck"
                    else ""
                )
            ),
            sources=(*MISSION, *LOOKS),
        )
        for name, value in MISSION_LOOKS.items()
    ],
]
