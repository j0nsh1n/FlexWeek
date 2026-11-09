"""The Bento and Mission control days as pictures. The aggregator collects SCREENS."""

from __future__ import annotations

from collections.abc import Callable

from desktop.native.window import NativeWindow
from desktop.tests.day.support_designs import FRIDAY, THURSDAY, at, locked, seed_week, show_design
from desktop.tests.pictures.screen import Screen

BENTO = ("desktop/native/layouts/bento.py", "desktop/native/hours", "desktop/native/layouts/base.py")
MISSION = ("desktop/native/layouts/mission.py", "desktop/native/hours", "desktop/native/layouts/base.py")


def bento_day(window: NativeWindow) -> object:
    at(15, 40)
    seed_week(window)
    return show_design(window, "bento", surface="day", iso_day=THURSDAY)


def mission_day(clock: tuple[int, int], size: tuple[int, int] | None, *extra: dict) -> Callable[..., object]:
    def prepare(window: NativeWindow) -> object:
        at(*clock)
        seed_week(window, extra=extra)
        if size is not None:
            window.resize(*size)
        return show_design(window, "mission", surface="day", iso_day=THURSDAY)

    return prepare


def mission_day_friday(window: NativeWindow) -> object:
    at(13, 40)
    seed_week(window)
    return show_design(window, "mission", surface="day", iso_day=FRIDAY)


SOCCER = locked("soccer", "Soccer practice", "exercise", "16:00", 90, [1, 3])
PIANO = locked("piano", "Piano", "extra", "19:00", 30, [3])
WALK = locked("walk", "Walk", "exercise", "21:00", 30, [3])
QUIZ = locked("quiz", "Quiz", "class", "18:00", 60, [3])

SCREENS: list[Screen] = [
    Screen(
        id="day.bento_day",
        area="day",
        prepare=bento_day,
        checks=(
            "On Day the tiles stay beside the hero in a small window (the Not placed yet chip's centre "
            "is right of the hero title's centre). With the Today hero, the first homework not placed yet "
            "stays fully in sight beside the hours and the hours keep at least 88 px of height."
        ),
        sources=BENTO,
        main=True,
    ),
    Screen(
        id="day.mission_day",
        area="day",
        prepare=mission_day((13, 40), None, QUIZ),
        checks=(
            "Two blocks at one time (Dinner and the quiz, both at 18:00) take separate rows in the day's "
            "lane: their boxes do not overlap."
        ),
        sources=MISSION,
        main=True,
    ),
    Screen(
        id="day.mission_day_cards",
        area="day",
        prepare=mission_day((15, 40), (1280, 744), SOCCER),
        checks=(
            "At 1280 by 744 with four things still to come, the Up next card shows its first rows whole "
            "and never the next one cut at its foot; its head still counts all four."
        ),
        sources=MISSION,
    ),
    Screen(
        id="day.mission_day_more_row",
        area="day",
        prepare=mission_day((15, 40), (1280, 800), SOCCER, PIANO, WALK),
        checks=(
            "At 1280 by 800 Up next (six rows) and Free time left (five) each show three whole rows, then "
            "an 'and N more' row in the room of a row: as tall as the last row, straight after it (its top "
            "one pixel below the last row's bottom), inside the card's rows area."
        ),
        sources=MISSION,
    ),
    Screen(
        id="day.mission_day_friday",
        area="day",
        prepare=mission_day_friday,
        checks="Another day's lanes open through the evening to 22:30 with no Up next or Free time card.",
        sources=MISSION,
    ),
]
