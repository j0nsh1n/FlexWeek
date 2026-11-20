"""The Add and Edit fixed time sheet: what the student typed, and what saving it means.

The rules and words are the Widgets sheet's. Start and End are what a student knows; the
length is worked out from them. A start that moves takes the end with it until End has
been set by hand.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from backend import clock as wall_clock
from backend.models import TimeBlock, WeekRequest
from backend.slots import hhmm_to_minutes
from desktop.native.calendar import (
    CATEGORIES,
    block_family,
    date_for_day,
    day_full_names,
    day_short,
    is_series,
    is_setup_block,
    is_standing_block,
    monday_of,
    past_problem,
    span_clash,
    until_problem,
)
from desktop.native.hours.geometry import DEFAULT_DRAG_STEP, drag_step
from desktop.native.remind import clock_parts
from desktop.native.sheet_rules import (
    BLOCK_PROBLEMS,
    REPEAT_NOTE,
    _block_problem,
    _preset_locked,
    day_range_and_words,
    first_day_changed,
    full_day_name,
    guess_locked_category,
    moved_across_months,
    moved_day_names,
    moved_days_note,
    same_weekday,
    short_day_name,
    turn_days_keeping_weekdays,
)
from desktop.native.weekmodel import clock_text, end_after_start_words, length_label

STEPS = ("What", "When", "Category")
PROMPTS = ("What is it?", "When is it?", "What category is it?")
DAY_END = 24 * 60
WEEKLY_PREFIX = "weekly-"


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
        # A time drawn on the grid gave the day: the student chose it, the app did not.
        self._drawn = block is None and length is not None
        self.original = (
            deepcopy(block)
            if block is not None
            else _preset_locked(category, day, start, length or 60, session.week_start or "")
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
        # A fixed time the student made repeat is a standing row: its Until and the switch come from the
        # repeat in the session, never from the week's copy.
        self.standing = self.existing and is_standing_block(original)
        self.family = block_family(original["id"]) if self.existing else ""
        self.show_repeat = not (self.existing and is_setup_block(original))
        self.weekly = self.standing and self.family.startswith(WEEKLY_PREFIX)
        self.repeat: dict | None = None
        self.until: str | None = None
        if self.weekly:
            self.repeat = deepcopy(next((r for r in session.repeats if r["id"] == self.family), None))
            self.until = (self.repeat or {}).get("until") or None
        self.moved = ""
        self.title_problem = ""
        self.days_problem = ""
        self.time_problem = ""
        self.until_problem_text = ""
        self.error = ""
        self._opened_as = self._picture()
        # The open week the day numbers count from.
        self._days_week = session.week_start or ""
        # The ticks the last turn moved, as new day to the old "Monday 2" label, with the one-line
        # note naming the move. Cleared when the student touches the row.
        self._moved_from: dict[int, str] = {}
        # The new name of a tick that moved into another month, for the spoken name of its chip.
        self._moved_to: dict[int, str] = {}
        self._moved_note = ""
        # Whether the student ticked or unticked a day: a row they handled is theirs, even if it ended
        # on the days it opened with.
        self._days_touched = False

    def follow_week(self, fresh_days: list[int]) -> None:
        """A new sheet kept after Esc and opened again in a week that starts on another day: the days the
        student ticked keep their weekdays, and the ticks whose date changed are remembered, so the row
        can mark them until the student touches it. A row the student never handled is still what the app
        put there when the sheet opened: it is picked again for this week, `fresh_days` as a fresh sheet
        has them, with no mark."""
        week = self.session.week_start or ""
        title, opened_days, *rest = self._opened_as
        if first_day_changed(self._days_week, week) and not self._drawn and not self._days_touched:
            self.days = sorted(fresh_days)
            self._opened_as = (title, tuple(self.days), *rest)
            self._days_week = week
            self._moved_from = {}
            self._moved_to = {}
            self._moved_note = ""
            return

        def turned(days: Any) -> list[int]:
            return sorted(same_weekday(day, self._days_week, week) for day in days)

        turned_days, moved = turn_days_keeping_weekdays(self.days, self._days_week, week)
        from_week = self._days_week
        names = {new: moved_day_names(old, from_week, new, week) for old, new in moved}
        self._moved_from = {new: old_name for new, (old_name, _) in names.items()}
        self._moved_to = {
            new: names[new][1] for old, new in moved if moved_across_months(old, from_week, new, week)
        }
        self._moved_note = moved_days_note(list(names.values()))
        self.days = turned_days
        self._opened_as = (title, tuple(turned(opened_days)), *rest)
        self._days_week = week

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
        elif name == "repeat" and self.show_repeat:
            self.weekly = bool(value)
            self.until_problem_text = ""
            if not self.weekly:
                self.until = None
        elif name == "until" and self.weekly:
            self.until = str(value) or None
            self.until_problem_text = ""

    def toggle_day(self, day: int) -> None:
        if self.scope == "occurrence" and self.occurrence_day is not None:
            return
        self.error = ""
        self.days_problem = ""
        self._moved_from = {}
        self._moved_to = {}
        self._moved_note = ""
        self._days_touched = True
        days = set(self.days)
        days.symmetric_difference_update({day})
        self.days = sorted(days)

    def use_picked(self, day: int, start: str, length: int) -> None:
        """A kept new sheet opened again from a time picked on the grid: the picked day, start and length
        replace the kept ones, as a fresh sheet opened there would have them."""
        self.error = ""
        self.days = [day]
        self.days_problem = ""
        self._days_touched = True
        self._drawn = True
        self._moved_from = {}
        self._moved_to = {}
        self._moved_note = ""
        self.end_by_hand = False
        self.length = length
        self._move_start(hhmm_to_minutes(start))
        self.moved = ""

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
            problem = self._until_problem(self._series_days_now())
            if problem:
                self.until_problem_text = problem
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
                past = past_problem("locked", week, day, self.start, now_iso, now_min, DEFAULT_DRAG_STEP)
                if past:
                    return past
            return ""
        single = len(chosen) == 1
        for day in chosen:
            added = day not in original_days
            moved = single and day in original_days and _clock(self.start) != original_start
            if not added and not moved:
                continue
            past = past_problem("locked", week, day, self.start, now_iso, now_min, DEFAULT_DRAG_STEP)
            if past:
                return past
        return ""

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
        problem = self._until_problem(made["days"])
        if problem:
            self.until_problem_text = problem
            self.step = 1 if self.step is not None else None
            return None
        return made

    def _until_problem(self, days: list[int]) -> str:
        """The sentence for an Until the repeat cannot use, from the engine. None with the switch off."""
        if not (self.weekly and self.until):
            return ""
        week = self.session.week_start
        if not isinstance(week, str):
            return ""
        probe = {"id": "weekly-probe", "days": sorted(days), "until": self.until}
        return until_problem(probe, week, wall_clock.today().isoformat()) or ""

    # What saving means -------------------------------------------------------------------

    def _week_to_monday(self, days: list[int]) -> list[int]:
        """Repeats count their days from Monday; the open week counts from its first day."""
        first = int(getattr(self.session, "first_weekday", 0) or 0)
        return sorted((first + day) % 7 for day in days)

    def _changed_fields(self) -> set[str]:
        """What the student changed on the sheet since it opened, by the names the repeat uses."""
        opened = self._opened_as
        title, days, start, end, category, _scope, missed, weekly, until = opened
        changed = set()
        if self.title.strip() != title.strip():
            changed.add("title")
        if tuple(self.days) != tuple(days):
            changed.add("days")
        if self.start != start:
            changed.add("start")
        if self.end != end:
            changed.add("end")
        if self.category != category:
            changed.add("category")
        if self.missed != missed:
            changed.add("missed")
        if self.weekly != weekly:
            changed.add("weekly")
        if self.until != until:
            changed.add("until")
        return changed

    def _repeat_body(self, made: dict, base: dict | None, changed: set[str]) -> dict:
        """The repeat as it stands from this week on. A new one takes every field of the sheet; an edited
        one starts from the repeat the session holds, never from the week's copy, and takes only what the
        student changed."""
        if base is None:
            body = deepcopy(made)
            body.pop("missed_days", None)
            body["days"] = self._week_to_monday(self.days)
            body["id"] = WEEKLY_PREFIX + (str(made["id"]) if self.existing else str(uuid4()))
        else:
            body = deepcopy(base)
            if "title" in changed:
                body["title"] = made["title"]
            if "days" in changed:
                # Only the days the student ticked or unticked change: the week's copy may lack days its
                # Until (or this week's own edit) hid, and those stay as the repeat has them.
                opened = set(self._week_to_monday(list(self._opened_as[1])))
                now = set(self._week_to_monday(self.days))
                body["days"] = sorted((set(body.get("days") or []) - (opened - now)) | (now - opened))
            if "start" in changed or "end" in changed:
                body["start"] = made["start"]
                body["duration_min"] = made["duration_min"]
            if "category" in changed:
                body["category"] = made["category"]
        if self.until:
            body["until"] = self.until
        else:
            body.pop("until", None)
        return TimeBlock.model_validate(body).model_dump(mode="json")

    def save_plan(self, made: dict) -> dict:
        """How this save goes. `kind` is plain (today's path), add (a new repeat), make (this fixed time
        becomes a repeat), later (the repeat changes from this week on), ask (this week only, or this
        week and later), or stop (the repeat ends after this week). `repeat` is the body for add, make
        and later; `changed` says what the student changed."""
        changed = self._changed_fields()
        if not self.show_repeat:
            return {"kind": "plain", "changed": changed}
        if not self.existing:
            if not self.weekly:
                return {"kind": "plain", "changed": changed}
            return {"kind": "add", "repeat": self._repeat_body(made, None, changed), "changed": changed}
        if not self.weekly:
            return {"kind": "stop" if self.standing else "plain", "changed": changed}
        if not self.standing:
            return {"kind": "make", "repeat": self._repeat_body(made, None, changed), "changed": changed}
        if self.repeat is None:
            return {"kind": "plain", "changed": changed}
        if self.scope == "occurrence" and self.occurrence_day is not None:
            # One day is this week only; the switch and Until are not shown there.
            return {"kind": "plain", "changed": changed}
        body = self._repeat_body(made, self.repeat, changed)
        if changed <= {"weekly", "until"}:
            return {"kind": "later", "repeat": body, "changed": changed}
        return {"kind": "ask", "repeat": body, "changed": changed}

    def recover_missed(self) -> bool:
        return (
            self.existing
            and self.occurrence_day is not None
            and self.missed
            and self.occurrence_day not in (self.original.get("missed_days") or [])
        )

    # Delete -----------------------------------------------------------------------------

    def delete_question(self) -> dict:
        """What Delete asks, with the answers that apply. A block from Setup is in every week, so those
        offer this week only, or this week and later."""
        name = self.original.get("title") or "this fixed time"
        occurrence = self.scope == "occurrence" and self.occurrence_day is not None
        week = self.session.week_start
        if occurrence:
            if not isinstance(week, str):
                week = monday_of(wall_clock.today().isoformat())
            stamp = date.fromisoformat(date_for_day(week, self.occurrence_day))
            day_name = day_full_names(week)[self.occurrence_day]
            question = f"Delete {name} on {day_name} {stamp.day} {stamp.strftime('%b')} only?"
        else:
            days = day_range_and_words(self.original.get("days") or [], self._week())
            question = f"Delete {name} on every {days} this week?"
        if is_standing_block(self.original):
            answers = [{"id": "stay", "label": "Cancel", "kind": "text"}]
            cards = []
            if occurrence:
                answers.append({"id": "day", "label": "This day only", "kind": "tonal"})
                cards.append(
                    {
                        "id": "day",
                        "title": f"Just {day_name} {stamp.day} {stamp.strftime('%b')}",
                        "line": f"Other days this week and other weeks keep {name}. You can undo this.",
                    }
                )
            answers.append({"id": "week", "label": "This week only", "kind": "tonal"})
            answers.append({"id": "every", "label": "This week and later", "kind": "danger"})
            cards.append(
                {
                    "id": "week",
                    "title": "This week only",
                    "line": f"Other weeks keep {name}. You can undo this.",
                }
            )
            cards.append(
                {
                    "id": "every",
                    "title": "This week and every week after",
                    "line": f"Earlier weeks keep {name}. Undo also takes back anything changed after it.",
                }
            )
            return {
                "id": "delete-block",
                "title": f"Delete {name}?",
                "body": "",
                "answers": answers,
                "cards": cards,
                "confirm": "Delete",
            }
        return {
            "id": "delete-block",
            "title": "Delete fixed time",
            "body": question + " You can undo this.",
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text"},
                {"id": "delete", "label": "Delete", "kind": "danger"},
            ],
        }

    def save_question(self) -> dict:
        """What a change to a weekly fixed time asks: this week only, or this week and later."""
        name = self.title.strip() or self.original.get("title") or "this fixed time"
        return {
            "id": "block-save",
            "title": f"Change {name}?",
            "body": "",
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text"},
                {"id": "week", "label": "This week only", "kind": "tonal"},
                {"id": "later", "label": "This week and later", "kind": "tonal"},
            ],
            "cards": [
                {
                    "id": "week",
                    "title": "This week only",
                    "line": f"Other weeks keep {name} as it was.",
                },
                {
                    "id": "later",
                    "title": "This week and every week after",
                    "line": f"Earlier weeks keep {name} as it was.",
                },
            ],
            "confirm": "Save",
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
            {"value": "series", "label": f"Every {day_range_and_words(days, self._week())}"},
        ]

    def _series_days_now(self) -> list[int]:
        return (
            self.series_days if self.scope == "occurrence" and self.series_days is not None else self.days
        )

    def _until_label(self) -> str:
        if not self.until:
            return "No end"
        try:
            return day_short(self.until, wall_clock.today())
        except (ValueError, TypeError):
            return self.until

    def _week(self) -> str:
        """The first day of the open week, whose days a block's `days` count; "" with none."""
        week = self.session.week_start
        return week if isinstance(week, str) else ""

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
            f"{day_range_and_words(self.days, self._week())}, {clock_text(self.start)}",
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
        # A time off the step (a block made before the step changed) is listed too, in order, so the field
        # can show it and Up and Down step from it instead of from the top of the list.
        every = drag_step((self.session.preferences or {}).get("drag_step_min"))
        starts = sorted({*range(0, DAY_END, every), self._opened_as[2], self.start})
        ends = sorted({*range(every, DAY_END + 1, every), self._opened_as[3], self.end})
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
                    "label": short_day_name(self._week(), index),
                    "date": (monday + timedelta(days=index)).day if monday else 0,
                    "on": index in self.days,
                    "moved": index in self._moved_from,
                    "movedFrom": self._moved_from.get(index, ""),
                    "movedTo": self._moved_to.get(index, ""),
                }
                for index in range(7)
            ],
            "daysLocked": locked,
            "daysProblem": self.days_problem,
            "movedNote": self._moved_note,
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
            "missedLabel": (
                "I missed it"
                if self.occurrence_day is None
                else f"I missed it on {full_day_name(self._week(), self.occurrence_day)}"
            ),
            # A one-day sheet changes that day only; the repeat is changed from the whole series.
            "showRepeat": self.show_repeat and not locked,
            "repeat": self.weekly,
            "until": self.until or "",
            "untilLabel": self._until_label(),
            "todayIso": wall_clock.today().isoformat(),
            "untilProblem": self.until_problem_text or self._until_problem(self._series_days_now()),
            "error": self.error,
            "canBack": bool(step),
            "primary": "Add" if step is not None and step >= 2 else ("Save" if self.existing else "Next"),
            "last": step is None or step >= 2,
            "canDelete": self.existing,
        }
