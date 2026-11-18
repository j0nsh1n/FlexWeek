"""The hours' scale and where they open: what every surface that shows hours shares, with no drawing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from desktop.native.weekmodel import WeekModel

KEY = re.compile(r"[a-z]+\.[a-z]+")

# Hours with neither now nor a block to show open at 08:00.
OPENS = 8 * 60


@dataclass(frozen=True)
class Scale:
    """The pixels an hour a surface offers, smallest first, and the one it opens at."""

    key: str
    levels: tuple[int, ...]
    default: int

    def __post_init__(self) -> None:
        if KEY.fullmatch(self.key) is None or len(self.key) > 40:
            raise ValueError(f"{self.key!r} cannot be kept in the look file: use design.surface, a to z")

    def nearest(self, px: object) -> int:
        if not isinstance(px, int) or isinstance(px, bool):
            return self.default
        return min(self.levels, key=lambda level: (abs(level - px), level))

    def step(self, px: int, by: int) -> int:
        at = self.levels.index(self.nearest(px))
        return self.levels[min(max(at + by, 0), len(self.levels) - 1)]


def opening_minute(week: WeekModel, today: int | None, now: int | None, day: int | None = None) -> int:
    """Where hours open: now, on today or on this week; otherwise the first block of the day shown,
    or of the week; otherwise the start of a school day."""
    if today is not None and now is not None and day in (None, today):
        return now
    items = week.occurrences if day is None else week.on_day(day)
    return min((item.start for item in items), default=OPENS)
