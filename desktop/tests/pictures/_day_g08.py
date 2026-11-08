"""The Clay deck, Retro desktop and Timeline days as pictures: what the old layout tests asserted about
where things sit, how big they are, their colours and what fits. The aggregator collects SCREENS."""

from __future__ import annotations

from collections.abc import Callable

from desktop.native import motion
from desktop.native.window import NativeWindow
from desktop.tests.day.support_designs import FRIDAY, at, locked, seed_week, show_design
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

CLAY = ("desktop/native/layouts/clay.py", "desktop/native/hours", "desktop/native/layouts/base.py")
RETRO = ("desktop/native/layouts/retro.py", "desktop/native/hours", "desktop/native/layouts/base.py")
TIMELINE = ("desktop/native/layouts/timeline.py", "desktop/native/hours", "desktop/native/layouts/base.py")
LOOKS = ("desktop/native/look.py", "desktop/native/tokens.py", "desktop/native/layouts/registry.py")


def on_day(
    name: str,
    *,
    clock: tuple[int, int] = (13, 40),
    extra: tuple[dict, ...] = (),
    size: tuple[int, int] | None = None,
    **options: str,
) -> Callable[[NativeWindow], object]:
    """Window on `name`'s Day for Thursday, with the seeded week at `clock`."""

    def prepare(window: NativeWindow) -> object:
        at(*clock)
        seed_week(window, shared=False, extra=extra)
        if size is not None:
            window.resize(*size)
        return show_design(window, name, surface="day", **options)

    return prepare


# Wednesday's evening, which is on the card beside Thursday's when Day is open: the second session of the
# essay, as homework, whose name was drawn past the window's edge once.
ESSAY_ON_WEDNESDAY = (locked("essay-2", "Essay-2", "assignments", "19:00", 60, [2]),)


def clay_day_slide(window: NativeWindow, *, last: bool) -> object:
    """Day's row part-way (or at the end of) its slide from Thursday to Friday, under Normal motion."""
    at(13, 40)
    seed_week(window, shared=False)
    motion.apply_ui_effects("normal")
    view = show_design(window, "clay", surface="day")
    window.session.open_day(FRIDAY)
    window._on_week()
    row = view.row
    wait_until(None, lambda: row._snaps is not None, what="the row starting to slide")
    row._slide.pause()
    if last:
        row._on_clock(float(row._slide.duration()))
    else:
        row._slid(0.3)
    row.repaint()
    return row


SCREENS: list[Screen] = [
    Screen(
        id="day.clay_day_card",
        area="day",
        prepare=on_day("clay", extra=ESSAY_ON_WEDNESDAY),
        checks=(
            "Day opens the card in front 800 px wide at 1280 wide, with its summary to the right of the "
            "hours (the summary's left edge is right of the hours' scroll area). The neighbours narrow to "
            "the room beside the open card, whole inside the window, at least 140 px wide, at 70 % of "
            "the open card's height, 32 px from it on both sides. The fade at the row's ends stays off "
            "the cards in view (the two neighbours). Wednesday's homework (Essay-2) is written with its "
            "name inside the row, not as a pink bar whose name lies past the window's left edge."
        ),
        sources=CLAY,
        main=True,
    ),
    Screen(
        id="day.clay_slide_midway",
        area="day",
        prepare=lambda window: clay_day_slide(window, last=False),
        checks=(
            "Part-way into Day's slide to Friday each moving picture of a card is scaled by one factor "
            "on both sides (its words are not stretched) and clipped to its card's own rectangle."
        ),
        sources=CLAY,
    ),
    Screen(
        id="day.clay_slide_last_frame",
        area="day",
        prepare=lambda window: clay_day_slide(window, last=True),
        checks=(
            "At the last frame of Day's slide the row already looks as it does once landed, with the new "
            "day's hours and summary and not the hours where the last day left them: no hour, heading or "
            "card is in another place (the biggest difference in any colour channel stays under 16 apart "
            "from antialiasing at the arrows' and cards' edges)."
        ),
        sources=CLAY,
    ),
    Screen(
        id="day.retro_day_window",
        area="day",
        prepare=on_day("retro", size=(1150, 768)),
        checks=(
            "Day opens Week.exe on one live column at 1280 by 820 and at 1150 by 768 with Large text; "
            "the not-placed chip in Notepad has its bottom right corner inside the window (not past "
            "its right or bottom edge)."
        ),
        sources=RETRO,
        main=True,
    ),
    Screen(
        id="day.timeline_day_page",
        area="day",
        prepare=on_day("timeline", extra=(locked("quiz", "Quiz", "extra", "18:00", 30, [3]),)),
        checks=(
            "Day is one page of hours on the left and its notes on the facing page: the hours end left of "
            "the page's middle and the notes start right of it. The paper shows under the hours and "
            "behind the notes; the gutter is plain paper either side of the fold line (3, 8 and 14 px "
            "away) with the fold line itself kept, in the middle of the paper. At 45 px an hour a half "
            "hour is written smaller in the caption size rather than left as a coloured bar: Dinner and "
            "its times 18:00–18:30 fit inside its block. Two blocks at one time (Dinner and Quiz) go half "
            "width side by side, equal in width. Blocks are filled with their category colour."
        ),
        sources=TIMELINE,
        main=True,
    ),
    Screen(
        id="day.timeline_now_pill",
        area="day",
        prepare=on_day(
            "timeline",
            clock=(10, 5),
            extra=(locked("school-all", "School", "class", "08:00", 390, [0, 1, 2, 3, 4, 5, 6]),),
        ),
        checks=(
            "At 10:05 with School on the day the time now is on a pill that covers no hour label (10:00 "
            "included) and no part of School, and the line for now crosses today's column in the now "
            "colour."
        ),
        sources=TIMELINE,
    ),
]
