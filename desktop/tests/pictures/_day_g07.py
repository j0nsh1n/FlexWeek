"""The Bento day as pictures. The aggregator collects SCREENS."""

from __future__ import annotations

from desktop.native.window import NativeWindow
from desktop.tests.day.support_designs import THURSDAY, at, locked, seed_week, show_design
from desktop.tests.pictures.screen import Screen

BENTO = ("desktop/native/layouts/bento.py", "desktop/native/hours", "desktop/native/layouts/base.py")


def bento_day(window: NativeWindow) -> object:
    at(15, 40)
    seed_week(window)
    return show_design(window, "bento", surface="day", iso_day=THURSDAY)






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
]
