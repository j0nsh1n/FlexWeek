"""The hours' scale and where they open: what every surface that shows hours shares, with no drawing."""

from __future__ import annotations

from dataclasses import dataclass

import flexweek_engine  # type: ignore[import-untyped]

from desktop.native.weekmodel import WeekModel

# Hours with neither now nor a block to show open at 08:00.
OPENS = int(flexweek_engine.HOURS_OPENS)


@dataclass(frozen=True)
class Scale:
    """The pixels an hour a surface offers, smallest first, and the one it opens at."""

    key: str
    levels: tuple[int, ...]
    default: int

    def __post_init__(self) -> None:
        flexweek_engine.hours_scale_check(self.key)

    def nearest(self, px: object) -> int:
        return int(flexweek_engine.hours_scale_nearest(list(self.levels), self.default, px))

    def step(self, px: int, by: int) -> int:
        return int(flexweek_engine.hours_scale_step(list(self.levels), self.default, px, by))


def opening_minute(week: WeekModel, today: int | None, now: int | None, day: int | None = None) -> int:
    """Where hours open: now, on today or on this week; otherwise the first block of the day shown,
    or of the week; otherwise the start of a school day."""
    # Only what the day shown needs: a week that is built for one day has no occurrences to read.
    if day is None:
        starts = [item.start for item in week.occurrences]
        return int(flexweek_engine.hours_opening_minute(today, now, None, starts, None))
    day_starts = [item.start for item in week.on_day(day)]
    return int(flexweek_engine.hours_opening_minute(today, now, day, [], day_starts))


def short_length(minutes: int) -> str:
    """A length where room is short: "1h 30m", "45 min", "2h". Spaces around h made "2 h 15" look
    like a time of day."""
    return str(flexweek_engine.hours_short_length(minutes))


# Below this width the week gives up a column rather than make the student scroll sideways to Run plan.
NARROW_WIDTH = int(flexweek_engine.HOURS_NARROW_WIDTH)


def sanitize_zoom(raw: object) -> dict[str, int]:
    """The remembered levels, whatever the file on disk says."""
    return dict(flexweek_engine.hours_sanitize_zoom(raw))
