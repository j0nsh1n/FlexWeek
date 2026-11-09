"""What a picture of the app is: the contract between the area test files, which say which screens
there are, and the renderer (scripts/pictures), which draws each one in the fixed setup.

Looks are checked with pictures, not in code (spec.md, Testing structure, rule 6). An area declares
its screens in `desktop/tests/pictures/screens_<area>.py` as a module-level `SCREENS: list[Screen]`;
the renderer finds every such module.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from desktop.native.window import NativeWindow

AREAS = (
    "week",
    "day",
    "month",
    "myday",
    "focus",
    "settings",
    "sheets",
    "setup",
    "account",
    "sync",
    "updater",
    "planner",
)


@dataclass(frozen=True)
class Screen:
    """One screen to photograph.

    `prepare` is given a light window (desktop/tests/light_app.py) that the renderer has already
    opened in the variant being drawn: the style (a Widgets design or Material 3), light or dark,
    the text size and the window size. It puts the window in the state to photograph (adds the
    homework, opens the sheet, moves the clock with backend.tests.fake_clock.CLOCK) and returns the
    widget to photograph, or None for the whole window. It never asserts: what is wrong with a
    picture is the reviewer's call.

    `checks` is what the reviewer judges on this picture, in plain words, taken from the code checks
    the area removed and from spec.md: "every block's title and time fit inside it", "the now line
    passes behind blocks and its dot stays on top".

    `sources` are the product paths (files or folders under desktop/ or backend/) whose change means
    this screen is drawn again for the visual review of that change.

    `main` screens are also drawn in the edge set: 1024x640 with Large text, and High contrast.
    """

    id: str
    area: str
    prepare: Callable[[NativeWindow], object]
    checks: str
    sources: tuple[str, ...]
    main: bool = False
    styles: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.area not in AREAS:
            raise ValueError(f"{self.id}: unknown area {self.area!r}")
        if not self.id.startswith(self.area + "."):
            raise ValueError(f"{self.id}: a screen's id starts with its area")
        if not self.checks.strip() or not self.sources:
            raise ValueError(f"{self.id}: a screen says what to check and what it is drawn from")
