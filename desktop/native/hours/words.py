"""What a block says about itself in words: its times, its length, what became of it and the tags Plan
and the deadline give it. No drawing, so the Widgets canvas and Material's lists share one wording."""

from __future__ import annotations

from datetime import date

from desktop.native.weekmodel import Occurrence, length_label, range_label


def plan_placed(item: Occurrence) -> bool:
    """Homework that Plan placed and nobody has moved since. A hand move or a chosen time pins it, and
    a finished or missed session has nothing left for Plan to place (N11)."""
    return item.work and not item.pinned and not item.done and not item.missed


def tag_words(history: str, placed_by_plan: bool) -> tuple[str, ...]:
    """Pill labels on a block, in order: Overdue, Left from last week, Placed by Plan."""
    tags: list[str] = []
    if history == "Overdue":
        tags.append("Overdue")
    if history == "Left from last week":
        tags.append("Left from last week")
    if placed_by_plan:
        tags.append("Placed by Plan")
    return tuple(tags)


def length_words(minutes: int, done: bool, missed: bool) -> str:
    """Its length, then what became of it: "1 h", "1 h · Missed"."""
    words = length_label(minutes)
    for flag, word in ((done, "Finished"), (missed, "Missed")):
        if flag:
            words += f" · {word}"
    return words


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
    for tag in tag_words(history, placed_by_plan):
        if tag.startswith("Overdue") and history_due:
            try:
                due = date.fromisoformat(history_due[:10])
                tag = f"{tag}, was due {due.strftime('%a')} {due.day} {due.strftime('%b')}"
            except ValueError:
                pass
        words += f" · {tag}"
    return words + " · Pinned" if pinned and not done else words


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
    return tail_words(
        f"{range_label(start, end)} · {length_words(end - start, done, missed)}",
        done=done,
        pinned=pinned,
        history=history,
        history_due=history_due,
        placed_by_plan=placed_by_plan,
    )
