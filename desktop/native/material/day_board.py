"""What the Material Day and My day screens say about one day.

The screens share this. It reads occurrences the week model already resolved.
It does not touch the session, the clock setting, or the network. The caller
sets the 12-hour or 24-hour clock first, and says whether this day is today.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from desktop.native.material.theme import EVENT_CATEGORY, bar_for_category, paint_for_category
from desktop.native.weekmodel import clock_text, due_label, length_label, range_label, slack_words_for

ICONS = {
    "class": "school",
    "exercise": "schedule",
    "extra": "schedule",
    "study": "edit_note",
    "assignments": "edit_note",
}
TAG_KINDS = {
    "Tight": "tight",
    "Plenty of time": "plenty",
    "Cutting it close": "cutting",
}
# The settings screen is another lane. These are the names it can arrive under.
NUDGE_KEYS = ("free_time_nudges", "nudges")
DIM_KEYS = ("dim_completed", "dim")


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
    if not isinstance(preferences, dict):
        return default
    for key in keys:
        if key in preferences and isinstance(preferences[key], bool):
            return preferences[key]
    return default


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
) -> DayBoard:
    """Up next, Done, the Now card, and the ring for one day.

    `when` is `today`, `past`, or `future`. The Now card shows only on today
    while nudges are on. It names homework that is happening at `minute`, with
    its time left; while a fixed block is on, that block, when it ends and what
    is next; otherwise it gives the free time from `minute` to the next block
    that still occupies time, and that block. A finished homework block does
    not occupy that gap.
    `missed` is the ids the planner calls missed: those sessions stay under Up next.
    Slack uses `now` when the caller has the real clock; otherwise the viewed
    day's `minute`.
    """
    ordered = tuple(sorted(items, key=lambda item: (int(item.start), str(item.title))))
    # A session the planner calls missed is still to do, so it stays under Up next though its time went by.
    up = tuple(
        item
        for item in ordered
        if not _settled(item) and (item.block_id in missed or not _clock_past(item, minute, when))
    )
    ahead = tuple(item for item in up if not _clock_past(item, minute, when))
    finished = tuple(item for item in ordered if item not in up)
    gap = _gap(ordered, minute, when, nudges)
    focus = next((item for item in ahead if item.work and item.assignment_id), None)
    doing = _doing(ahead, minute, when, nudges)
    busy = None if doing is not None else _busy(ordered, minute, when, nudges)
    after = None if busy is None else _next_after(ordered, minute)
    total = len(ordered)
    count = len(up)
    moment = now if now is not None else datetime.combine(on, datetime.min.time()) + timedelta(minutes=minute)
    return DayBoard(
        left_line=_left_line(count, when == "today"),
        left_count=count,
        show_now=doing is not None or busy is not None or gap is not None,
        now_title=_busy_title(busy) if busy is not None else _now_title(doing, gap, minute),
        now_minutes=int(busy.end) - minute if busy is not None else _now_minutes(doing, gap, minute),
        now_line=_next_line(after) if busy is not None else _now_line(doing, gap, minute),
        now_busy=busy is not None,
        ring_count=count,
        ring_caption="thing left" if count == 1 else "things left",
        ring_share=0.0 if total == 0 else (total - count) / total,
        up_next=tuple(_row(item, on, moment, mode, dim=False, finish=True) for item in up),
        done=tuple(_row(item, on, moment, mode, dim=dim, finish=False) for item in finished),
        focus_block_id="" if focus is None else str(focus.block_id),
        focus_day=-1 if focus is None else int(focus.day),
        focus_title="" if focus is None else str(focus.title),
    )


def _settled(item: object) -> bool:
    return bool(item.done or item.missed)


def _live(item: object) -> bool:
    return not (item.work and _settled(item))


def _clock_past(item: object, minute: int, when: str) -> bool:
    if when == "past":
        return True
    if when == "future":
        return False
    return int(item.end) <= minute


def _gap(items: Sequence[object], minute: int, when: str, nudges: bool) -> object | None:
    if not nudges or when != "today":
        return None
    if any(_live(item) and int(item.start) <= minute < int(item.end) for item in items):
        return None
    return next((item for item in items if _live(item) and int(item.start) > minute), None)


def _doing(up: Sequence[object], minute: int, when: str, nudges: bool) -> object | None:
    if not nudges or when != "today":
        return None
    homework = (item for item in up if item.work and item.assignment_id)
    return next((item for item in homework if int(item.start) <= minute < int(item.end)), None)


def _busy(items: Sequence[object], minute: int, when: str, nudges: bool) -> object | None:
    """The fixed block on at `minute`. Where several are, the one that ends last, so the card says when the
    student is actually free (Jonathan, 2026-11-09)."""
    if not nudges or when != "today":
        return None
    on = [item for item in items if not item.work and int(item.start) <= minute < int(item.end)]
    return max(on, key=lambda item: int(item.end), default=None)


def _next_after(items: Sequence[object], minute: int) -> object | None:
    return next((item for item in items if _live(item) and int(item.start) > minute), None)


def _busy_title(busy: object) -> str:
    return f"{busy.title} until {clock_text(int(busy.end))}"


def _next_line(after: object | None) -> str:
    return "" if after is None else f"Next: {after.title} at {clock_text(int(after.start))}"


def _now_minutes(doing: object | None, gap: object | None, minute: int) -> int:
    if doing is not None:
        return int(doing.end) - minute
    return 0 if gap is None else int(gap.start) - minute


def _now_title(doing: object | None, gap: object | None, minute: int) -> str:
    if doing is not None:
        return str(doing.title)
    if gap is None:
        return ""
    return f"Free for {length_label(int(gap.start) - minute)}"


def _now_line(doing: object | None, gap: object | None, minute: int) -> str:
    if doing is not None:
        return f"{length_label(int(doing.end) - minute)} left"
    if gap is None:
        return ""
    return f"Next: {gap.title} at {clock_text(int(gap.start))}"


def _slack_words(item: object, now: datetime) -> str:
    words = getattr(item, "slack_words", None)
    if callable(words):
        return str(words(now))
    return slack_words_for(getattr(item, "slack", None), getattr(item, "due", None), now)


def _left_line(count: int, today: bool) -> str:
    if count == 0:
        return "Nothing left today" if today else "Nothing left"
    noun = "thing" if count == 1 else "things"
    tail = "today" if today else ""
    return f"{count} {noun} left" + (f" {tail}" if tail else "")


def _row(item: object, on: date, now: datetime, mode: str, *, dim: bool, finish: bool) -> DayRow:
    role = EVENT_CATEGORY.get(str(item.category or ""))
    scheme = mode if mode in ("light", "dark") else "light"
    words = _slack_words(item, now)
    kind = TAG_KINDS.get(words, "plain" if words else "")
    parts = [range_label(int(item.start), int(item.end))]
    if item.pinned:
        parts.append("Pinned")
    due = item.due
    if due:
        label = due_label(str(due), on)
        if label:
            parts.append(f"Due {label}")
    show_tag = finish and kind != ""
    fill, ink = paint_for_category(str(item.category or ""), scheme)
    return DayRow(
        title=str(item.title),
        subtitle=" · ".join(parts),
        icon=ICONS.get(role or "", "schedule"),
        # ListRow keeps its own fill and paints the class colour on the edge.
        bar=bar_for_category(str(item.category or "")),
        fill=fill,
        ink=ink,
        tag=words if show_tag else "",
        tag_kind=kind if show_tag else "",
        can_finish=bool(finish and item.work and item.assignment_id),
        assignment_id=str(item.assignment_id or ""),
        dim=dim,
    )
