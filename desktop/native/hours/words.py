"""What a block says about itself in words: its times, its length, what became of it and the tags Plan
and the deadline give it. No drawing, so the Widgets canvas and Material's lists share one wording."""

from __future__ import annotations

import flexweek_engine  # type: ignore[import-untyped]

from desktop.native.weekmodel import Occurrence


def plan_placed(item: Occurrence) -> bool:
    """Homework that Plan placed and nobody has moved since. A hand move or a chosen time pins it, and
    a finished or missed session has nothing left for Plan to place (N11)."""
    return bool(flexweek_engine.hours_plan_placed(item.work, item.pinned, item.done, item.missed))


def tag_words(history: str, placed_by_plan: bool) -> tuple[str, ...]:
    """Pill labels on a block, in order: Overdue, Left from last week, Placed by Plan."""
    return tuple(flexweek_engine.hours_tag_words(history, placed_by_plan))


def length_words(minutes: int, done: bool, missed: bool) -> str:
    """Its length, then what became of it: "1 h", "1 h · Missed"."""
    return str(flexweek_engine.hours_length_words(minutes, done, missed))


def tail_words(
    words: str,
    *,
    done: bool,
    pinned: bool,
    history: str,
    history_due: str | None,
    placed_by_plan: bool,
) -> str:
    """`words` followed by the block's tags and Pinned, each after a dot."""
    return str(
        flexweek_engine.hours_tail_words(words, done, pinned, history, history_due, placed_by_plan)
    )


def detail_words(
    start: int,
    end: int,
    *,
    done: bool = False,
    missed: bool = False,
    pinned: bool = False,
    history: str = "",
    history_due: str | None = None,
    placed_by_plan: bool = False,
) -> str:
    """Everything a block says under its name, on one line, for a screen reader and the tests."""
    return str(
        flexweek_engine.hours_detail_words(
            start, end, done, missed, pinned, history, history_due, placed_by_plan
        )
    )
