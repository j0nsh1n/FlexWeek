"""The clock every test runs on. It starts at START and moves only when a test moves it."""

from __future__ import annotations

from datetime import date, datetime, timedelta

# A Thursday evening (the week of Monday 2 November 2026), local time: the suite passed on the real
# clock on 6 November 2026, and evening is when the most of a school day is already past.
START = datetime(2026, 11, 5, 19, 0)
START_MONDAY = date(2026, 11, 2)


class FakeClock:
    def __init__(self) -> None:
        self._at = START

    def __call__(self) -> float:
        return self._at.timestamp()

    def now(self) -> datetime:
        return self._at

    def today(self) -> date:
        return self._at.date()

    def now_ms(self) -> int:
        return int(self._at.timestamp() * 1000)

    def set(self, moment: datetime) -> None:
        """Local time of day, without a time zone, as the app keeps it."""
        if moment.tzinfo is not None:
            raise ValueError("The fake clock takes local times without a time zone.")
        self._at = moment

    def set_ms(self, ms: int) -> None:
        self._at = datetime.fromtimestamp(ms / 1000)

    def move(self, **amount: float) -> None:
        """Forward (or back, given negative amounts) by timedelta's keywords: hours=2, days=-1."""
        self._at += timedelta(**amount)

    def reset(self) -> None:
        self._at = START


# The one the root conftest.py installs; support code that holds the clock for a test moves this one.
CLOCK = FakeClock()
