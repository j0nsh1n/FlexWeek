"""The Add and Edit fixed time sheet: what the student typed, and what saving it means.

The rules and words are the Widgets sheet's. Start and End are what a student knows; the
length is worked out from them. A start that moves takes the end with it until End has
been set by hand.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import ValidationError

from backend import clock as wall_clock
from backend.models import TimeBlock, WeekRequest
from backend.slots import SLOT_MIN, hhmm_to_minutes
from desktop.native.calendar import (
    CATEGORIES,
    DAY_FULL,
    DAYS,
    date_for_day,
    is_series,
    is_setup_block,
    is_standing_block,
    monday_of,
    past_problem,
    span_clash,
)
from desktop.native.remind import clock_parts
from desktop.native.weekmodel import clock_text, end_after_start_words, length_label
from desktop.native.widgets import (
    BLOCK_PROBLEMS,
    REPEAT_NOTE,
    _block_problem,
    _preset_locked,
    day_range_and_words,
    guess_locked_category,
)

STEPS = ("What", "When", "Category")
PROMPTS = ("What is it?", "When is it?", "What category is it?")
DAY_END = 24 * 60
# Until's list runs this many days from the block's first day: half a year of weeks.
UNTIL_DAYS_AHEAD = 182


def _clock(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


class BlockDraft:
    """One open Add or Edit fixed time sheet."""

    def __init__(
        self,
        session: Any,
        block: dict | None = None,
        *,
        day: int = 0,
        start: str = "16:00",
        category: str | None = None,
        occurrence_day: int | None = None,
        length: int | None = None,
    ) -> None:
        self.session = session
        self.now = datetime.fromtimestamp(session.now_ms() / 1000)
        self.existing = block is not None
        self.original = (
            deepcopy(block) if block is not None else _preset_locked(category, day, start, length or 60)
        )
        if block is None and length is not None:
            # A time picked on the grid keeps its own day, start and length over a category's preset.
            self.original.update(days=[day], start=start, duration_min=length)
        self.occurrence_day = occurrence_day
        self.step: int | None = None if self.existing else 0
        original = self.original
        self.title: str = original["title"]
        self.days: list[int] = sorted(original["days"])
        self.start: int = hhmm_to_minutes(original.get("start") or start)
        self.length: int = int(original["duration_min"])
        self.end: int = min(self.start + self.length, DAY_END)
        self.end_by_hand = False
        self.category: str | None = original.get("category") or category
        self.guessing = not self.existing and not self.category
        if self.guessing:
            self.category = guess_locked_category(_clock(self.start))
        self.series = self.existing and is_series(original)
        self.scope = "occurrence" if self.series and occurrence_day is not None else "series"
        self.series_days: list[int] | None = None
        if self.scope == "occurrence":
            self.series_days = list(self.days)
            self.days = [occurrence_day] if occurrence_day is not None else self.days
        self.missed = occurrence_day in (original.get("missed_days") or [])
        # Setup owns the repeat of School and its activities, so they get no switch.
        self.owns_repeat = bool(self.existing and is_setup_block(original))
        self.was_weekly = bool(self.existing and (is_standing_block(original) and not self.owns_repeat))
        self.was_until: str = (original.get("until") or "") if self.was_weekly else ""
        self.weekly: bool = self.was_weekly
        self.until: str = self.was_until
        self.until_problem = ""
        self.moved = ""
        self.title_problem = ""
        self.days_problem = ""
        self.time_problem = ""
        self.error = ""
        self._opened_as = self._picture()

    def _picture(self) -> tuple:
        return (
            self.title,
            tuple(self.days),
            self.start,
            self.end,
            self.category,
            self.scope,
            self.missed,
            self.weekly,
            self.until,
        )

    def dirty(self) -> bool:
        return self._picture() != self._opened_as

    # Edits ------------------------------------------------------------------------------

    def set(self, name: str, value: Any) -> None:
        self.error = ""
        if name == "title":
            self.title = str(value)
            self.title_problem = ""
        elif name == "start":
            self._move_start(hhmm_to_minutes(str(value)))
        elif name == "end":
            self.end = int(value)
            self.end_by_hand = True
            self.moved = ""
            self.time_problem = ""
            if self.end > self.start:
                self.length = self.end - self.start
        elif name == "category":
            self.category = str(value) or None
            self.guessing = False
        elif name == "scope":
            self._set_scope("occurrence" if value == "occurrence" else "series")
        elif name == "missed":
            self.missed = bool(value)
        elif name == "repeats":
            self.weekly = bool(value)
            self.until_problem = ""
        elif name == "until":
            self.until = str(value)
            self.until_problem = ""

    def toggle_day(self, day: int) -> None:
        if self.scope == "occurrence" and self.occurrence_day is not None:
            return
        self.error = ""
        self.days_problem = ""
        days = set(self.days)
        days.symmetric_difference_update({day})
        self.days = sorted(days)

    def _move_start(self, minute: int) -> None:
        """A start that moves takes the end with it, so the length stays, up to the end of the day. Once
        End was set here it is the student's and stays."""
        before = self.start
        self.start = minute
        self.time_problem = ""
        if self.guessing:
            self.category = guess_locked_category(_clock(minute))
        if self.end_by_hand:
            self.moved = ""
            return
        end = min(minute + self.length, DAY_END)
        kept = end - minute
        self.moved = ""
        if (end != self.end or kept < self.length) and minute != before:
            self.moved = self._moved_sentence(end, kept)
        self.end = end

    def _moved_sentence(self, end: int, kept: int) -> str:
        end_words = clock_text(end)
        if end == DAY_END and kept < self.length:
            return (
                f"End moved to the end of the day ({end_words}). "
                f"It's now {length_label(kept)}, not {length_label(self.length)}."
            )
        return f"End moved to {end_words} to keep it {length_label(kept)}."

    def _set_scope(self, scope: str) -> None:
        if self.occurrence_day is None or not self.series:
            return
        if scope == "occurrence" and self.scope != "occurrence":
            self.series_days = list(self.days)
            self.days = [self.occurrence_day]
        elif scope == "series" and self.scope == "occurrence":
            self.days = sorted(self.series_days or self.original["days"])
            self.series_days = None
        self.scope = scope

    # Steps ------------------------------------------------------------------------------

    def back(self) -> None:
        if self.step:
            self.step -= 1

    def goto(self, index: int) -> None:
        if self.step is not None and 0 <= index < self.step:
            self.step = index

    def advance(self) -> bool:
        """Next on the first two steps. True when the sheet is on its last step and Add is next."""
        if self.step is None or self.step >= 2:
            return True
        if self.step == 0 and not self.title.strip():
            self.title_problem = BLOCK_PROBLEMS["title"]
            return False
        if self.step == 1:
            problem = self._time_problem()
            if problem:
                self.time_problem = problem
                return False
            if not self.days:
                self.days_problem = BLOCK_PROBLEMS["days"]
                return False
            if self._until_refused():
                return False
        self.step += 1
        return False

    # The answer -------------------------------------------------------------------------

    def _span(self) -> int:
        return self.end - self.start

    def _span_problem(self) -> str:
        return end_after_start_words(clock_text(self.start)) if self._span() <= 0 else ""

    def _past_problem(self) -> str:
        """A start or day the student just chose that is already over. A series keeps a start it already
        had, so School can still be edited after Monday."""
        week = self.session.week_start
        if not isinstance(week, str):
            return ""
        clock = clock_parts(self.session.now_ms())
        now_iso, now_min = clock["iso"], int(clock["minute"])
        chosen = self.days
        original_days = set(self.original.get("days") or [])
        original_start = self.original.get("start") or ""
        if not self.existing:
            for day in chosen:
                past = past_problem(week, day, self.start, now_iso, now_min)
                if past:
                    return past
            return ""
        single = len(chosen) == 1
        for day in chosen:
            added = day not in original_days
            moved = single and day in original_days and _clock(self.start) != original_start
            if not added and not moved:
                continue
            past = past_problem(week, day, self.start, now_iso, now_min)
            if past:
                return past
        return ""

    def repeat_shown(self) -> bool:
        """The switch is for a fixed time of its own, not School or a Setup activity, and not for one day of
        a series (that day alone would repeat)."""
        return self.original.get("kind") == "locked" and not self.owns_repeat and self.scope == "series"

    def weekly_arg(self) -> bool | None:
        """What the switch says, or None when this sheet has none to say."""
        return self.weekly if self.repeat_shown() else None

    def repeat_changed(self) -> bool:
        """The switch or Until changed what stands in later weeks, which Undo does not take back."""
        if not self.repeat_shown():
            return False
        return self.weekly != self.was_weekly or (self.weekly and self.until != self.was_until)

    def _until_refused(self) -> bool:
        """True with the engine's reason under the Until field when the date is before the first day."""
        if not (self.repeat_shown() and self.weekly and self.until):
            return False
        problem = self.session.weekly_problem({"days": list(self.days)}, self.until)
        self.until_problem = problem or ""
        if problem and self.step is not None:
            self.step = 1
        return bool(problem)

    def _until_options(self) -> list[dict]:
        week = self.session.week_start
        if not isinstance(week, str):
            return [{"value": "", "label": "No end"}]
        first = date.fromisoformat(week) + timedelta(days=min(self.days or [0]))
        days = {first + timedelta(days=offset) for offset in range(UNTIL_DAYS_AHEAD)}
        if self.until:
            days.add(date.fromisoformat(self.until))
        options = [{"value": "", "label": "No end"}]
        for day in sorted(days):
            words = f"{DAYS[day.weekday()]} {day.day} {day.strftime('%b')}"
            if day.year != self.now.year:
                words += f" {day.year}"
            options.append({"value": day.isoformat(), "label": words})
        return options

    def _time_problem(self) -> str:
        return self._span_problem() or self._past_problem()

    def clash(self) -> str:
        """The words for another block sitting at this time. Both show, so it is a note. Material draws
        them overlapped, one a step over the other (Jonathan, 2026-11-08), not side by side."""
        if self._span() <= 0:
            return ""
        for day in self.days:
            found = span_clash(self.session.blocks, self.original["id"], day, self.start, self.end)
            if found:
                return f"{found} is at that time too. Both will show, one slightly over the other."
        return ""

    def candidate(self) -> dict | None:
        """The block as typed, or None with the reason on the field it belongs to."""
        if not self.title.strip():
            self.title_problem = BLOCK_PROBLEMS["title"]
            self.step = 0 if self.step is not None else None
            return None
        problem = self._time_problem()
        if problem:
            self.time_problem = problem
            self.step = 1 if self.step is not None else None
            return None
        made = deepcopy(self.original)
        made.update(
            title=self.title.strip(),
            days=list(self.days),
            start=_clock(self.start),
            duration_min=self._span(),
            category=self.category,
        )
        if self.existing and self.occurrence_day is not None:
            restored = None if self.missed else self.occurrence_day
            made["missed_days"] = [
                day for day in made.get("missed_days", []) if day in made["days"] and day != restored
            ]
        else:
            made["missed_days"] = [day for day in made.get("missed_days", []) if day in made["days"]]
        if made["kind"] != "locked":
            self.error = "Use the homework editor for flexible work."
            return None
        if self.scope == "occurrence" and self.series_days is not None:
            made["days"] = sorted(self.series_days)
        if self._until_refused():
            return None
        try:
            WeekRequest(blocks=[TimeBlock.model_validate(made)])
        except ValidationError as error:
            message = _block_problem(error)
            if message == BLOCK_PROBLEMS["title"]:
                self.title_problem = message
                self.step = 0 if self.step is not None else None
            elif message == BLOCK_PROBLEMS["days"]:
                self.days_problem = message
                self.step = 1 if self.step is not None else None
            else:
                self.error = message
            return None
        return made

    def recover_missed(self) -> bool:
        return (
            self.existing
            and self.occurrence_day is not None
            and self.missed
            and self.occurrence_day not in (self.original.get("missed_days") or [])
        )

    # Delete -----------------------------------------------------------------------------

    def delete_question(self) -> dict:
        """What Delete asks, with the answers that apply. A block from Setup, or a weekly fixed time, is in
        every week, so those offer this week only, or this week and later."""
        name = self.original.get("title") or "this fixed time"
        occurrence = self.scope == "occurrence" and self.occurrence_day is not None
        week = self.session.week_start
        if occurrence:
            if not isinstance(week, str):
                week = monday_of(wall_clock.today().isoformat())
            stamp = date.fromisoformat(date_for_day(week, self.occurrence_day))
            question = (
                f"Delete {name} on {DAY_FULL[self.occurrence_day]} {stamp.day} {stamp.strftime('%b')} only?"
            )
        else:
            question = (
                f"Delete {name} on every {day_range_and_words(self.original.get('days') or [])} this week?"
            )
        if is_standing_block(self.original):
            answers = [{"id": "stay", "label": "Cancel", "kind": "text"}]
            if occurrence:
                answers.append({"id": "day", "label": "This day only", "kind": "tonal"})
            answers.append({"id": "week", "label": "This week only", "kind": "tonal"})
            answers.append({"id": "every", "label": "This week and later", "kind": "filled"})
            return {
                "id": "delete-block",
                "title": f"Delete {name}?",
                "body": question + " Earlier weeks keep it. This week and later can't be undone.",
                "answers": answers,
            }
        return {
            "id": "delete-block",
            "title": "Delete fixed time",
            "body": question + " You can undo this.",
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text"},
                {"id": "delete", "label": "Delete", "kind": "filled"},
            ],
        }

    def edit_question(self) -> dict:
        """What saving asks for a block that repeats every week and was changed in some other way: this
        week only, or this week and every week after. Delete asks it in the same words."""
        name = self.original.get("title") or "this fixed time"
        return {
            "id": "edit-block",
            "title": f"Change {name}?",
            "body": (
                f"Change {name} for this week only, or for this week and every week after? "
                "Earlier weeks keep it. This week and later can't be undone."
            ),
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text"},
                {"id": "week", "label": "This week only", "kind": "tonal"},
                {"id": "every", "label": "This week and later", "kind": "filled"},
            ],
        }

    # What the sheet shows ---------------------------------------------------------------

    def _scope_choices(self) -> list[dict]:
        days = (
            (self.series_days if self.scope == "occurrence" and self.series_days is not None else self.days)
            or self.original.get("days")
            or []
        )
        return [
            {"value": "occurrence", "label": "This day only"},
            {"value": "series", "label": f"Every {day_range_and_words(days)}"},
        ]

    def form(self) -> dict:
        step = self.step
        week = self.session.week_start
        monday = date.fromisoformat(week) if week else None
        span = self._span()
        problem = self._span_problem()
        if problem:
            line = problem
        elif self.moved:
            line = self.moved
        else:
            line = length_label(span)
        done = (
            self.title.strip(),
            f"{day_range_and_words(self.days)}, {clock_text(self.start)}",
        )
        crumbs = [
            {
                "label": ("✓ " if step is not None and index < step else f"{index + 1}. ") + name,
                "done": step is not None and index < step,
                "on": index == step,
                "summary": done[index] if step is not None and index < step and index < 2 else "",
            }
            for index, name in enumerate(STEPS)
        ]
        locked = self.scope == "occurrence" and self.occurrence_day is not None
        # A time off the quarter hour (the plain look's 5-minute drag makes them) is listed too, in order, so
        # the field can show it and Up and Down step from it instead of from the top of the list.
        starts = sorted({*range(0, DAY_END, SLOT_MIN), self._opened_as[2], self.start})
        ends = sorted({*range(SLOT_MIN, DAY_END + 1, SLOT_MIN), self._opened_as[3], self.end})
        start_options = [{"value": _clock(m), "label": clock_text(m)} for m in starts]
        end_options = [{"value": m, "label": clock_text(m)} for m in ends]
        categories = [{"value": "", "label": "None"}] + [
            {"value": key, "label": info["label"]} for key, info in CATEGORIES.items()
        ]
        if self.category and self.category not in CATEGORIES:
            categories.append({"value": self.category, "label": self.category})
        return {
            "kind": "block",
            "mode": "edit" if self.existing else "add",
            "heading": "Edit fixed time" if self.existing else "Add fixed time",
            "step": -1 if step is None else step,
            "crumbs": crumbs if step is not None else [],
            "prompt": PROMPTS[step] if step is not None else "",
            "title": self.title,
            "titleProblem": self.title_problem,
            "days": [
                {
                    "value": index,
                    "label": DAYS[index],
                    "date": (monday + timedelta(days=index)).day if monday else 0,
                    "on": index in self.days,
                }
                for index in range(7)
            ],
            "daysLocked": locked,
            "daysProblem": self.days_problem,
            "repeatNote": "" if locked else REPEAT_NOTE,
            "showScope": bool(self.series and self.occurrence_day is not None),
            "scopeChoices": self._scope_choices(),
            "scope": self.scope,
            "seriesNote": (
                "Changes apply to every selected day in this series."
                if self.existing
                and len(self.original.get("days") or []) > 1
                and not (self.series and self.occurrence_day is not None)
                else ""
            ),
            "start": _clock(self.start),
            "startOptions": start_options,
            "end": self.end,
            "endOptions": end_options,
            "durationLine": line,
            "durationIsProblem": bool(problem),
            "timeProblem": self.time_problem,
            "clash": self.clash(),
            "category": self.category or "",
            "categoryOptions": categories,
            "missed": self.missed,
            "showMissed": bool(self.existing and self.occurrence_day is not None),
            "repeatShown": self.repeat_shown(),
            "repeatLabel": "Repeats every week",
            "repeats": self.weekly,
            "untilShown": bool(self.repeat_shown() and self.weekly),
            "untilLabel": "Until",
            "until": self.until,
            "untilOptions": self._until_options() if self.repeat_shown() and self.weekly else [],
            "untilProblem": self.until_problem,
            "missedLabel": (
                "I missed it"
                if self.occurrence_day is None
                else f"I missed it on {DAY_FULL[self.occurrence_day]}"
            ),
            "error": self.error,
            "canBack": bool(step),
            "primary": "Add" if step is not None and step >= 2 else ("Save" if self.existing else "Next"),
            "last": step is None or step >= 2,
            "canDelete": self.existing,
        }
