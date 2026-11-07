"""The wall clock FlexWeek reads. Everything that asks for today's date or the time of day asks here,
so the tests can set it (the root conftest.py) and no answer depends on when a test happens to run.
How long something took is not the wall clock; that is time.monotonic or QElapsedTimer."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, datetime

_seconds: Callable[[], float] = time.time


def seconds() -> float:
    """Seconds since the Unix epoch."""
    return _seconds()


def now_ms() -> int:
    return int(_seconds() * 1000)


def now() -> datetime:
    """The local time of day, without a time zone, as the app has always kept it."""
    return datetime.fromtimestamp(_seconds())


def today() -> date:
    return now().date()


def use(source: Callable[[], float]) -> Callable[[], float]:
    """Read the time from `source` (seconds since the epoch) from now on; returns the one it replaced."""
    global _seconds
    previous, _seconds = _seconds, source
    return previous
