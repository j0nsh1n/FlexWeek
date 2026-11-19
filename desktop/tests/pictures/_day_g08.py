"""The Clay deck, Retro desktop and Timeline days as pictures: what the old layout tests asserted about
where things sit, how big they are, their colours and what fits. The aggregator collects SCREENS."""

from __future__ import annotations

from collections.abc import Callable

from desktop.native.window import NativeWindow
from desktop.tests.day.support_designs import at, locked, seed_week, show_design
from desktop.tests.pictures.screen import Screen

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






SCREENS: list[Screen] = [
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
