"""The Bento weeks as pictures: what the old layout tests asserted about where
things sit, how big they are, their colours and what fits. The aggregator collects SCREENS."""

from __future__ import annotations

from collections.abc import Callable

from desktop.native.window import NativeWindow
from desktop.tests.day.support_designs import at, locked, seed_week, show_design
from desktop.tests.pictures.screen import Screen

BENTO = ("desktop/native/layouts/bento.py", "desktop/native/hours", "desktop/native/layouts/base.py")
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
]
