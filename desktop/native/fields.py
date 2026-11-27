"""What Material and the session share about typed times and the week's first day: reading a written
clock time, the quick lengths under a homework's time, the computer's week start and its change
notice, and the screen-reader announcement."""

from __future__ import annotations

import json
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import (
    QObject,
    QStandardPaths,
    Signal,
)
from PySide6.QtGui import (
    QAccessible,
    QAccessibleAnnouncementEvent,
)
from PySide6.QtWidgets import QWidget

# The quick lengths under a homework's time, in minutes (5.2 A of 0.17.2).
QUICK_LENGTHS = (15, 30, 45, 60, 90)

# The days the week can start on, Monday first: a name's place is its weekday number (0 Monday to
# 6 Sunday), as a block's `days` count them.
WEEK_STARTS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class WeekStartNotice(QObject):
    """Says the week's first day changed on this computer, so every open screen redraws at once."""

    changed = Signal(str)


_notice: WeekStartNotice | None = None


def week_start_notice() -> WeekStartNotice:
    global _notice
    if _notice is None:
        _notice = WeekStartNotice()
    return _notice


def _week_starts_file() -> Path:
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    return folder / "week-start.json"


def week_starts_on() -> str:
    """Monday, unless this computer was set to another day. Kept per computer, not on the account: the
    stored weeks stay Monday-keyed, and the account's preferences are the engine's fixed list."""
    try:
        value = json.loads(_week_starts_file().read_text(encoding="utf-8")).get("week_starts_on")
    except (OSError, ValueError, AttributeError):
        value = None
    return str(flexweek_engine.hours_accepted_week_start(value))


def week_start_day() -> int:
    """The week's first day as the engine counts days: 0 Monday to 6 Sunday."""
    return int(flexweek_engine.hours_week_start_day(week_starts_on()))


def save_week_starts_on(value: str) -> None:
    if value not in WEEK_STARTS:
        raise ValueError(f"week start must be one of {WEEK_STARTS}, not {value!r}")
    before = week_starts_on()
    path = _week_starts_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"week_starts_on": value}), encoding="utf-8")
    if value != before:
        week_start_notice().changed.emit(value)


def read_clock(text: str, *, end: bool = False, whole: bool = True) -> int | None:
    """The minute of the day `text` writes, or None when it writes no time. The same on either clock:
    "3:15 pm" is 15:15 on the 24-hour one too. An end of the day, 24:00 or 00:00, is 1440, and only an
    end box takes it. `whole` asks for the minutes to be written; an hour alone is "3 pm" or "15"."""
    return flexweek_engine.hours_read_clock(text, end, whole)


def announce(widget: QWidget, words: str, *, assertive: bool = False) -> None:
    """Have a screen reader say `words` now, without moving the keyboard (Qt 6.8's announcements)."""
    event = QAccessibleAnnouncementEvent(widget, words)
    politeness = QAccessible.AnnouncementPoliteness
    event.setPoliteness(politeness.Assertive if assertive else politeness.Polite)
    QAccessible.updateAccessibility(event)
