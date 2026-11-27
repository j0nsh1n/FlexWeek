"""What the Material Day and My day screens say about one day.

The screens share this. The engine builds the board from occurrences the week model already
resolved; this file hands the occurrences over and wraps the answer in the dataclasses the bridge
and the tests read. It does not touch the session, the clock setting, or the network. The caller
sets the 12-hour or 24-hour clock first, and says whether this day is today.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import flexweek_engine  # type: ignore[import-untyped]

# The settings screen is another lane. These are the names it can arrive under.
NUDGE_KEYS = tuple(flexweek_engine.VIEWS_DAY_NUDGE_KEYS)
DIM_KEYS = tuple(flexweek_engine.VIEWS_DAY_DIM_KEYS)


@dataclass(frozen=True)
class DayRow:
    title: str
    subtitle: str
    icon: str
    bar: str
    fill: str
    ink: str
    tag: str
    tag_kind: str
    can_finish: bool
    assignment_id: str
    dim: bool


@dataclass(frozen=True)
class DayBoard:
    left_line: str
    left_count: int
    show_now: bool
    now_title: str
    now_minutes: int
    now_line: str
    # A fixed block such as Soccer is on: the card names it and what is next, and starts nothing.
    now_busy: bool
    ring_count: int
    ring_caption: str
    ring_share: float
    up_next: tuple[DayRow, ...]
    done: tuple[DayRow, ...]
    focus_block_id: str
    focus_day: int
    # The homework Start focus opens, which the card names on its button.
    focus_title: str


def read_flag(preferences: object, keys: tuple[str, ...], default: bool) -> bool:
    """A bool preference. A missing key, or a value that is not a bool, keeps `default`."""
    return bool(flexweek_engine.views_day_read_flag(preferences, list(keys), default))


def board_from(data: dict) -> DayBoard:
    """The engine's board, as the dataclasses the bridge and the tests read."""
    rows = {name: tuple(DayRow(**row) for row in data[name]) for name in ("up_next", "done")}
    return DayBoard(**{**data, **rows})


def board_for(
    items: Sequence[object],
    *,
    minute: int,
    when: str,
    nudges: bool,
    dim: bool,
    mode: str,
    on: date,
    now: datetime | None = None,
    missed: frozenset[str] = frozenset(),
    unplaced: int = 0,
    unplaced_words: tuple[str, str] | None = None,
) -> DayBoard:
    """Up next, Done, the Now card, and the ring for one day.

    `when` is `today`, `past`, or `future`. The Now card shows only on today
    while nudges are on. `missed` is the ids the planner calls missed: those sessions stay under
    Up next. Slack uses `now` when the caller has the real clock; otherwise the viewed day's
    `minute`. `unplaced` is how many homework items due today still have no time, and
    `unplaced_words` is the week model's (title, line) for them.
    """
    answer = flexweek_engine.views_day_board_for(
        items, minute, when, nudges, dim, mode, on, now, missed, unplaced, unplaced_words
    )
    return board_from(json.loads(answer))
