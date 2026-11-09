"""The Add and Edit homework sheet: what the student typed, and what saving it means.

Nothing here draws. The sheet's QML shows `form()` and sends each edit back through
`set`. The words and the rules are the Widgets sheet's, so the same input gets the
same answer in either surface. Saving goes through NativeSession in the bridge.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from backend.availability import spread_sessions
from backend.models import ESTIMATE_MAX_MIN, Assignment, parse_due
from backend.slots import SLOT_MIN, hhmm_to_minutes
from desktop.native.calendar import (
    CATEGORIES,
    DAYS,
    FLEX_CATEGORIES,
    local_stamp,
    monday_of,
    past_problem,
    span_problem,
    sunday_due,
)
from desktop.native.fields import QUICK_LENGTHS
from desktop.native.reuse import due_point
from desktop.native.weekmodel import clock_text, due_label, hhmm_text, length_label
from desktop.native.widgets import (
    DUE_PASSED,
    ESTIMATE_LONG,
    ESTIMATE_SHORT,
    SLOT_HINT,
    SPREAD_MIN,
    _homework_problem,
    spread_session_min,
    spread_words,
    today_from_words,
)

STEPS = ("What", "When", "How long")
PROMPTS = ("What is it?", "When is it due?", "How long will it take?")
TITLE_PROBLEM = "Give the homework a title."
TYPES = ((1, "Test prep"), (2, "Quiz prep"), (3, "Everyday homework"), (4, "Reading"))
ENERGIES = (("high", "Morning"), ("medium", "Afternoon"), ("low", "Evening"))
WHEN_CHOICES = (("plan", "FlexWeek picks the time"), ("fixed", "Pin to a time"))
SPREAD_CHOICES = (("one", "In one go"), ("spread", "Spread over days"))
DAYS_AHEAD = 28


def quarter_hours(first: int = 0, last: int = 24 * 60 - SLOT_MIN) -> list[dict]:
    """Every quarter hour from `first` to `last`, as the clock is written."""
    return [
        {"value": f"{minute // 60:02d}:{minute % 60:02d}", "label": clock_text(minute)}
        for minute in range(first, last + 1, SLOT_MIN)
    ]


class HomeworkDraft:
    """One open Add or Edit homework sheet."""

    def __init__(
        self,
        session: Any,
        assignment: dict | None = None,
        *,
        category: str | None = None,
        due: str | None = None,
        when: str | None = None,
        when_day: int | None = None,
        when_time: str | None = None,
        day: int | None = None,
        start_min: int | None = None,
        end_min: int | None = None,
        estimate_min: int | None = None,
    ) -> None:
        self.session = session
        self.now = datetime.fromtimestamp(session.now_ms() / 1000)
        self.today = self.now.date().isoformat()
        self.existing = assignment is not None
        if category not in FLEX_CATEGORIES:
            category = "assignments"
        info = CATEGORIES.get(category, {})

        if day is not None and when_day is None:
            when_day = day
        if start_min is not None and when_time is None:
            when_time = f"{start_min // 60:02d}:{start_min % 60:02d}"
        if end_min is not None and start_min is not None and estimate_min is None:
            estimate_min = end_min - start_min
        if when is None and (when_day is not None or when_time is not None or start_min is not None):
            when = "fixed"
        if (
            due is None
            and (when_day is not None or day is not None)
            and session is not None
            and getattr(session, "week_start", None)
        ):
            due = sunday_due(session.week_start)

        if assignment is not None:
            self.original = deepcopy(assignment)
        else:
            tomorrow = (self.now.date() + timedelta(days=1)).isoformat()
            self.original = {
                "id": str(uuid4()),
                "title": "",
                "due": due or f"{tomorrow}T23:59",
                "estimate_min": estimate_min
                if estimate_min is not None
                else (info.get("preset", {}).get("duration_min") or 60),
                "category": category,
                "revision": 0,
                "notes": "",
                "links": [],
                "checklist": [],
                "completed": False,
                "completed_at": None,
            }
        original = self.original
        # Add is What, When, How long. Edit is one page.
        self.step: int | None = None if self.existing else 0
        self.title: str = original["title"]
        due_text = str(original["due"])
        self.due_date: str = due_text[:10]
        self.due_time: str = due_text[11:16] if len(due_text) >= 16 and due_text[11:16] != "23:59" else ""
        self.estimate_text: str = str(original["estimate_min"])
        self.spread: str = original.get("spread", "one")
        self.completed: bool = bool(original.get("completed"))
        self.course: str = original.get("course") or ""
        self.priority: int = int(original.get("priority", 3))
        self.energy: str = original.get("energy", "medium")
        self.notes: str = original.get("notes") or ""
        self.links: list[dict] = deepcopy(original.get("links") or [])
        self.checklist: list[dict] = deepcopy(original.get("checklist") or [])
        self.link_label = ""
        self.link_url = ""
        self.check_text = ""
        self.details_open: bool = bool(self.course or self.notes or self.links or self.checklist)
        sessions = self._open_sessions()
        placed = next((item for item in sessions if item.get("pinned") and item.get("start")), None)
        self.placed: tuple[int, str] | None = (placed["days"][0], placed["start"]) if placed else None
        self.spread_out = len(sessions) > 1
        default_day, default_start = self._default_placement()
        if self.placed:
            default_day, default_start = self.placed[0], hhmm_to_minutes(self.placed[1])
        self.when = when if when is not None else ("fixed" if self.placed else "plan")
        self.when_day = when_day if when_day is not None else default_day
        self.when_time = (
            when_time if when_time is not None else f"{default_start // 60:02d}:{default_start % 60:02d}"
        )
        self.pinned_session = placed is not None
        self.title_problem = ""
        self.due_problem = ""
        self.when_problem = ""
        self.estimate_problem = ""
        self.error = ""
        self.details_error = ""
        self._opened_as = self._picture()

    # What is open -----------------------------------------------------------------------

    def _open_sessions(self) -> list[dict]:
        return [
            block
            for block in self.session.blocks
            if block.get("assignment_id") == self.original["id"] and not block.get("completed")
        ]

    def _default_placement(self) -> tuple[int, int]:
        """Today if the week on screen has it, else Monday, at 16:00 or the next quarter hour after it."""
        week = self.session.week_start
        if week is not None and monday_of(self.today) != week:
            return 0, 16 * 60
        quarter = (self.now.hour * 60 + self.now.minute) // 15 * 15 + 15
        return self.now.weekday(), min(max(16 * 60, quarter), 23 * 60 + 45)

    def _picture(self) -> tuple:
        return (
            self.title,
            self.due_date,
            self.due_time,
            self.estimate_text,
            self.when,
            self.when_day,
            self.when_time,
            self.spread,
            self.course,
            self.priority,
            self.energy,
            self.notes,
            self.completed,
            tuple((item["label"], item["url"]) for item in self.links),
            tuple((item["text"], item["done"]) for item in self.checklist),
        )

    def dirty(self) -> bool:
        """Whether there is typed work that closing would lose."""
        return self._picture() != self._opened_as

    # Values -----------------------------------------------------------------------------

    def estimate(self) -> int:
        text = self.estimate_text.strip()
        return int(text) if text.isdigit() else 0

    def _chosen_due(self) -> str:
        """The due as the student left it. An old 23:59 that still means the same end of day is kept as
        it was stored, so opening and saving changes nothing."""
        chosen = f"{self.due_date}T{self.due_time or '23:59'}"
        before = str(self.original["due"])
        try:
            return before if parse_due(chosen) == parse_due(before) else chosen
        except ValueError:
            return chosen

    def _fixed_at(self) -> dict | None:
        if self.when != "fixed":
            return None
        return {"day": self.when_day, "start": self.when_time}

    def _when_changed(self) -> bool:
        if self.spread_out:
            return False
        fixed = self._fixed_at()
        if fixed is None:
            return self.placed is not None
        return self.placed is None or (fixed["day"], fixed["start"]) != tuple(self.placed)

    def _length_problem(self) -> str:
        minutes = self.estimate()
        if minutes < SLOT_MIN:
            return ESTIMATE_SHORT
        if minutes > ESTIMATE_MAX_MIN:
            return ESTIMATE_LONG
        return SLOT_HINT if minutes % SLOT_MIN else ""

    def _due_passed(self) -> bool:
        """A deadline the student set that is already over. A saved one they did not change is left alone,
        and so is finished homework, so old work can still be edited."""
        if self.completed:
            return False
        chosen = self._chosen_due()
        if chosen == self.original["due"]:
            return False
        try:
            day, minute = parse_due(chosen)
        except ValueError:
            return False
        return (day, minute) < (self.now.date(), self.now.hour * 60 + self.now.minute)

    def _past_when_problem(self) -> str:
        """The refusal for a pinned time that is already over today, shown as soon as one is picked. A time
        the homework already had, or finished homework, is left alone."""
        fixed = self._fixed_at()
        week = self.session.week_start
        if fixed is None or week is None or self.completed or not self._when_changed():
            return ""
        now_minute = self.now.hour * 60 + self.now.minute
        return past_problem(week, fixed["day"], hhmm_to_minutes(fixed["start"]), self.today, now_minute) or ""

    def _fixed_problem(self, fixed: dict, due: str) -> str:
        week = self.session.week_start
        if week is None:
            return ""
        start = hhmm_to_minutes(fixed["start"])
        if not self.completed:
            past = past_problem(week, fixed["day"], start, self.today, self.now.hour * 60 + self.now.minute)
            if past:
                return past
        sessions = self._open_sessions()
        length = int(sessions[0]["duration_min"]) if sessions else self.estimate()
        problem = span_problem([], "", fixed["day"], start, start + length, due_point(due, week))
        return (problem or "").replace(", so it stayed where it was", "")

    # Spread -----------------------------------------------------------------------------

    def spread_shown(self) -> bool:
        return self.estimate() >= SPREAD_MIN and not self.spread_out and self.when != "fixed"

    def _spread_figures(self) -> tuple[int, str, list[dict]]:
        due = self._chosen_due()
        focus = int(self.original.get("focus_minutes") or 0)
        remaining = max(0, self.estimate() - focus)
        session_min = spread_session_min(remaining)
        ahead = str(getattr(self.session, "selected_day", "") or "")
        start = max(self.today, ahead)
        from_date = min(start, parse_due(due)[0].isoformat())
        sessions, _off_grid = spread_sessions(
            estimate_min=self.estimate(),
            focus_minutes=focus,
            planned_min=0,
            due=due,
            session_min=session_min,
            from_date=from_date,
        )
        return session_min, from_date, sessions

    def spread_requested(self) -> bool:
        return self.spread == "spread" and self.spread_shown()

    def spread_plan(self) -> dict:
        session_min, from_date, _sessions = self._spread_figures()
        return {"session_min": session_min, "from_date": from_date}

    # Edits ------------------------------------------------------------------------------

    def set(self, name: str, value: Any) -> None:
        """One field changed. Words that said it was wrong go when it changes."""
        if name == "title":
            self.title = str(value)
            self.title_problem = ""
        elif name == "dueDate":
            self.due_date = str(value)
            self.due_problem = ""
            self.when_problem = ""
        elif name == "dueTime":
            self.due_time = str(value)
            self.due_problem = ""
        elif name == "estimate":
            self.estimate_text = str(value)
            if self.estimate_problem:
                self.estimate_problem = self._length_problem()
        elif name == "spread":
            self.spread = "spread" if value == "spread" else "one"
        elif name == "when":
            self.when = "fixed" if value == "fixed" else "plan"
            self.when_problem = self._past_when_problem()
        elif name == "whenDay":
            self.when_day = int(value)
            self.when_problem = self._past_when_problem()
        elif name == "whenTime":
            self.when_time = str(value)
            self.when_problem = self._past_when_problem()
        elif name == "completed":
            self.completed = bool(value)
        elif name == "course":
            self.course = str(value)
        elif name == "priority":
            self.priority = int(value)
        elif name == "energy":
            self.energy = str(value)
        elif name == "notes":
            self.notes = str(value)
        elif name == "linkLabel":
            self.link_label = str(value)
        elif name == "linkUrl":
            self.link_url = str(value)
        elif name == "checkText":
            self.check_text = str(value)
        elif name == "detailsOpen":
            self.details_open = bool(value)
        self.error = ""

    def add_link(self) -> None:
        if len(self.links) >= 20:
            self.details_error = "Up to 20 links."
            return
        label, url = self.link_label.strip(), self.link_url.strip()
        if not label or not url:
            self.details_error = "A link needs a label and an http(s) address."
            return
        self.links.append({"label": label, "url": url})
        self.link_label = self.link_url = ""
        self.details_error = ""

    def remove_link(self, index: int) -> None:
        if 0 <= index < len(self.links):
            del self.links[index]

    def add_check(self) -> None:
        if len(self.checklist) >= 40:
            self.details_error = "Up to 40 steps."
            return
        text = self.check_text.strip()
        if not text:
            self.details_error = "A checklist step needs text."
            return
        self.checklist.append({"id": str(uuid4()), "text": text, "done": False})
        self.check_text = ""
        self.details_error = ""

    def toggle_check(self, index: int) -> None:
        if 0 <= index < len(self.checklist):
            self.checklist[index]["done"] = not self.checklist[index]["done"]

    def remove_check(self, index: int) -> None:
        if 0 <= index < len(self.checklist):
            del self.checklist[index]

    # Steps ------------------------------------------------------------------------------

    def back(self) -> None:
        if self.step:
            self.step -= 1

    def goto(self, index: int) -> None:
        """A crumb that is already done takes the sheet back to that step."""
        if self.step is not None and 0 <= index < self.step:
            self.step = index

    def advance(self) -> bool:
        """Next on the first two steps. True when the sheet is on its last step and Save is next."""
        if self.step is None or self.step >= 2:
            return True
        if self.step == 0 and not self.title.strip():
            self.title_problem = TITLE_PROBLEM
            return False
        if self.step == 1:
            if self._due_passed():
                self.due_problem = DUE_PASSED
                return False
            fixed = self._fixed_at()
            if fixed is not None and self._when_changed():
                problem = self._fixed_problem(fixed, self._chosen_due())
                if problem:
                    self.when_problem = problem
                    return False
        self.step += 1
        return False

    # The answer -------------------------------------------------------------------------

    def candidate(self) -> dict | None:
        """The homework as typed, or None with the reason put on the field it belongs to. The step with
        the problem is the one the sheet goes back to."""
        problem = self._length_problem()
        if problem:
            self.estimate_problem = problem
            self._show_step(2)
            return None
        if self._due_passed():
            self.due_problem = DUE_PASSED
            self._show_step(1)
            return None
        fixed = self._fixed_at()
        if fixed is not None and self._when_changed():
            problem = self._fixed_problem(fixed, self._chosen_due())
            if problem:
                self.when_problem = problem
                self._show_step(1)
                return None
        made = deepcopy(self.original)
        completed_at = made.get("completed_at") if self.completed else None
        if self.completed and not completed_at:
            completed_at = local_stamp(self.now)
        made.update(
            title=self.title.strip(),
            due=self._chosen_due(),
            estimate_min=self.estimate(),
            spread=self.spread if self.spread_shown() else "one",
            course=self.course or None,
            priority=self.priority,
            energy=self.energy,
            notes=self.notes,
            links=deepcopy(self.links),
            checklist=deepcopy(self.checklist),
            completed=self.completed,
            completed_at=completed_at,
        )
        if self._when_changed():
            made["fixed_at"] = fixed
        try:
            Assignment.model_validate(
                {key: value for key, value in made.items() if key in Assignment.model_fields}
            )
        except ValueError as error:
            message = _homework_problem(error)
            path: tuple[str, ...] = ()
            if isinstance(error, ValidationError) and error.errors():
                path = tuple(str(part) for part in error.errors()[0].get("loc") or ())
            if path and path[0] == "title":
                self.title_problem = message
                self._show_step(0)
            else:
                self.error = message
            return None
        return made

    def _show_step(self, index: int) -> None:
        if self.step is not None:
            self.step = index

    # What the sheet shows ---------------------------------------------------------------

    def _placed_words(self) -> str:
        placed = sorted(
            (block["days"][0], block["start"]) for block in self._open_sessions() if block.get("start")
        )
        if not placed:
            return ""
        week = self.session.week_start or self.today
        monday = date.fromisoformat(monday_of(week))
        names = [f"{DAYS[day]} {(monday + timedelta(days=day)).day}" for day, _start in placed]
        planned = (
            f"Planned {names[0]}" if len(names) == 1 else f"Planned {', '.join(names[:-1])} and {names[-1]}"
        )
        due = str(self.original.get("due") or "")
        due_bit = ""
        if due:
            due_day = date.fromisoformat(due[:10])
            due_bit = f" · due {DAYS[due_day.weekday()]} {due_day.day}"
        times = f" · {len(names)} times" if len(names) > 1 else ""
        return planned + due_bit + times

    def _due_options(self) -> list[dict]:
        first = self.now.date()
        days = [first + timedelta(days=offset) for offset in range(DAYS_AHEAD)]
        chosen = date.fromisoformat(self.due_date) if self.due_date else None
        if chosen is not None and chosen not in days:
            days.insert(0, chosen)
        options = []
        for day in days:
            words = f"{DAYS[day.weekday()]} {day.day} {day.strftime('%b')}"
            if day == first:
                words = f"Today · {words}"
            elif day == first + timedelta(days=1):
                words = f"Tomorrow · {words}"
            options.append({"value": day.isoformat(), "label": words})
        return options

    def _from_now_hint(self) -> str:
        fixed = self._fixed_at()
        week = self.session.week_start
        if fixed is None or monday_of(self.today) != week or fixed["day"] != self.now.weekday():
            return ""
        return today_from_words(self.now.hour * 60 + self.now.minute)

    def form(self) -> dict:
        week = self.session.week_start
        monday = date.fromisoformat(week) if week else None
        day_options = [
            {
                "value": index,
                "label": f"{DAYS[index]} {(monday + timedelta(days=index)).day}" if monday else DAYS[index],
            }
            for index in range(7)
        ]
        step = self.step
        fixed = self._fixed_at()
        spread_line = ""
        if self.spread_shown() and self.spread == "spread" and not self._length_problem():
            spread_line = spread_words(self._spread_figures()[2], self._chosen_due(), self.now.date())
        done = (
            self.title.strip(),
            f"due {self._due_words()}, {'FlexWeek picks' if self.when == 'plan' else 'pinned'}",
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
        last = step is None or step >= 2
        return {
            "kind": "homework",
            "mode": "edit" if self.existing else "add",
            "heading": "Edit homework" if self.existing else "Add homework",
            "step": -1 if step is None else step,
            "crumbs": crumbs if step is not None else [],
            "prompt": PROMPTS[step] if step is not None else "",
            "title": self.title,
            "titleProblem": self.title_problem,
            "placedLine": self._placed_words() if self.existing else "",
            "dueDate": self.due_date,
            "dueTime": self.due_time,
            "dueOptions": self._due_options(),
            "timeOptions": [{"value": "", "label": "End of day"}, *quarter_hours()],
            "pinnedTimeOptions": quarter_hours(),
            "dueProblem": self.due_problem,
            "whenChoices": [{"value": value, "label": label} for value, label in WHEN_CHOICES],
            "when": self.when,
            "whenShown": not self.spread_out,
            "whenDay": self.when_day,
            "dayOptions": day_options,
            "whenTime": self.when_time,
            "whenNote": (
                f"Pinned to {DAYS[fixed['day']]} at {hhmm_text(fixed['start'])}. Plan won't move it."
                if fixed
                else ""
            ),
            "whenFrom": self._from_now_hint(),
            "whenProblem": self.when_problem,
            "estimate": self.estimate_text,
            "estimateLabel": length_label(self.estimate()) if self.estimate() else "",
            "estimateSuffix": "min",
            "quickLengths": [{"value": str(value), "label": f"{value} min"} for value in QUICK_LENGTHS],
            "estimateProblem": self.estimate_problem,
            "spreadShown": self.spread_shown(),
            "spreadChoices": [{"value": value, "label": label} for value, label in SPREAD_CHOICES],
            "spread": self.spread,
            "spreadLine": spread_line,
            "completed": self.completed,
            "detailsOpen": self.details_open,
            "course": self.course,
            "priority": self.priority,
            "typeOptions": [{"value": value, "label": label} for value, label in TYPES],
            "energy": self.energy,
            "energyOptions": [{"value": value, "label": label} for value, label in ENERGIES],
            "notes": self.notes,
            "links": [{"label": item["label"], "url": item["url"]} for item in self.links],
            "checklist": [{"text": item["text"], "done": bool(item["done"])} for item in self.checklist],
            "detailsError": self.details_error,
            "linkLabel": self.link_label,
            "linkUrl": self.link_url,
            "checkText": self.check_text,
            "error": self.error,
            "canBack": bool(step),
            "primary": "Save" if last or self.existing else "Next",
            "last": last,
            "canDelete": self.existing,
            "canUnpin": self.existing and self.pinned_session,
            "showDetails": step is None or step >= 2,
            "showFinished": self.existing,
        }

    def _due_words(self) -> str:
        try:
            return due_label(self._chosen_due(), self.now.date())
        except (ValueError, TypeError):
            return self.due_date
