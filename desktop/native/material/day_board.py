"""What the Material Day and My day screens say about one day.

The screens share this. It reads occurrences the week model already resolved.
It does not touch the session, the clock setting, or the network. The caller
sets the 12-hour or 24-hour clock first, and says whether this day is today.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from desktop.native.material.theme import EVENT_CATEGORY, paint_for_category
from desktop.native.weekmodel import due_label, length_label, range_label

# The mockup's category bars. ListRow keeps its own fill and paints this on the edge.
BARS = {
    "school": {"light": "#7C6CD6", "dark": "#9B8CF0"},
    "sports": {"light": "#2E9E63", "dark": "#5CCB8F"},
    "study": {"light": "#C2528E", "dark": "#E58ABB"},
    "homework": {"light": "#C98A2B", "dark": "#E8B268"},
}
ICONS = {
    "school": "school",
    "sports": "schedule",
    "study": "edit_note",
    "homework": "edit_note",
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
    ring_count: int
    ring_caption: str
    ring_share: float
    up_next: tuple[DayRow, ...]
    done: tuple[DayRow, ...]
    focus_block_id: str
    focus_day: int


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
) -> DayBoard:
    """Up next, Done, the free-time card, and the ring for one day.

    `when` is `today`, `past`, or `future`. The free-time card is the gap from
    `minute` to the next block that still occupies time, and only on today
    while nudges are on. A finished homework block does not occupy that gap.
    """
    ordered = tuple(sorted(items, key=lambda item: (int(item.start), str(item.title))))
    up = tuple(item for item in ordered if not _settled(item) and not _clock_past(item, minute, when))
    finished = tuple(item for item in ordered if item not in up)
    gap = _gap(ordered, minute, when, nudges)
    focus = next((item for item in up if item.work and item.assignment_id), None)
    total = len(ordered)
    count = len(up)
    return DayBoard(
        left_line=_left_line(count, when == "today"),
        left_count=count,
        show_now=gap is not None,
        now_title="" if gap is None else f"Free time before {gap.title}",
        now_minutes=0 if gap is None else int(gap.start) - minute,
        now_line="" if gap is None else f"{length_label(int(gap.start) - minute)} left",
        ring_count=count,
        ring_caption="thing left" if count == 1 else "things left",
        ring_share=0.0 if total == 0 else (total - count) / total,
        up_next=tuple(_row(item, on, mode, dim=False, finish=True) for item in up),
        done=tuple(_row(item, on, mode, dim=dim, finish=False) for item in finished),
        focus_block_id="" if focus is None else str(focus.block_id),
        focus_day=-1 if focus is None else int(focus.day),
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


def _slack_words(item: object) -> str:
    raw = getattr(item, "slack_words", "")
    if callable(raw):
        raw = raw()
    return str(raw or "")


def _left_line(count: int, today: bool) -> str:
    if count == 0:
        return "Nothing left today" if today else "Nothing left"
    noun = "thing" if count == 1 else "things"
    tail = "today" if today else ""
    return f"{count} {noun} left" + (f" {tail}" if tail else "")


def _row(item: object, on: date, mode: str, *, dim: bool, finish: bool) -> DayRow:
    role = EVENT_CATEGORY.get(str(item.category or ""))
    scheme = mode if mode in ("light", "dark") else "light"
    words = _slack_words(item)
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
        bar=BARS[role][scheme] if role else "",
        fill=fill,
        ink=ink,
        tag=words if show_tag else "",
        tag_kind=kind if show_tag else "",
        can_finish=bool(finish and item.work and item.assignment_id),
        assignment_id=str(item.assignment_id or ""),
        dim=dim,
    )
