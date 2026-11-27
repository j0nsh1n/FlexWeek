"""The Add and Edit homework sheet: what the student typed, and what saving it means.

Nothing here draws or decides. The sheet's QML shows `form()` and sends each edit back through
`set`. The state and every rule live in the engine's `HomeworkDraftCore`; this class passes it what
the open session knows (the week on screen, its blocks, the time step, the clock) and a fresh id when
one is needed. Saving goes through NativeSession in the bridge.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

import flexweek_engine  # type: ignore[import-untyped]

from backend.slots import SLOT_MIN

STEPS = tuple(flexweek_engine.VIEWS_HOMEWORK_STEPS)
PROMPTS = tuple(flexweek_engine.VIEWS_HOMEWORK_PROMPTS)
TITLE_PROBLEM = flexweek_engine.VIEWS_HOMEWORK_TITLE_PROBLEM
TYPES = tuple(flexweek_engine.VIEWS_HOMEWORK_TYPES)
ENERGIES = tuple(flexweek_engine.VIEWS_HOMEWORK_ENERGIES)
WHEN_CHOICES = tuple(flexweek_engine.VIEWS_HOMEWORK_WHEN_CHOICES)
SPREAD_CHOICES = tuple(flexweek_engine.VIEWS_HOMEWORK_SPREAD_CHOICES)
DAYS_AHEAD = tuple(flexweek_engine.VIEWS_HOMEWORK_DAYS_AHEAD)


def quarter_hours(step: int = SLOT_MIN) -> list[dict]:
    """Every mark of the day's time step (quarter hours on 15), as the clock is written."""
    return json.loads(flexweek_engine.views_homework_quarter_hours(step))


class HomeworkDraft:
    """One open Add or Edit homework sheet."""

    # Found when an attribute is asked for before __init__ has set it, so `__getattr__` cannot recurse.
    _core: Any = None

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
        options = {
            "category": category,
            "due": due,
            "when": when,
            "when_day": when_day,
            "when_time": when_time,
            "day": day,
            "start_min": start_min,
            "end_min": end_min,
            "estimate_min": estimate_min,
        }
        self._core = flexweek_engine.HomeworkDraftCore(
            self._env(),
            self._stamp(),
            str(uuid4()),
            json.dumps(assignment),
            json.dumps(options),
            getattr(session, "done_minutes_for", None),
        )

    def _stamp(self) -> str:
        """The session clock as a local date and minute, which the engine reads."""
        return datetime.fromtimestamp(self.session.now_ms() / 1000).strftime("%Y-%m-%dT%H:%M")

    def _env(self) -> str:
        """What the open session knows that the sheet is judged against, as the engine reads it."""
        session = self.session
        return json.dumps(
            {
                "week_start": session.week_start,
                "blocks": session.blocks,
                "preferences": session.preferences,
                "selected_day": getattr(session, "selected_day", ""),
            }
        )

    def __getattr__(self, name: str) -> Any:
        """A state field of the sheet (`title`, `step`, `original`, ...) as the engine holds it."""
        return json.loads(self._core.field(name))

    @property
    def now(self) -> datetime:
        return datetime.fromisoformat(json.loads(self._core.field("stamp")))

    def follow_week(self, fresh_day: int) -> None:
        """A new sheet kept after Esc and opened again in a week that starts on another day: a pinned day
        the student picked, and the one it opened with, keep their weekday. A pin whose date changed is
        remembered, so the row can name it until the student picks another day. A day still as the app
        put it when the sheet opened is picked again for this week, `fresh_day` as a fresh sheet has it,
        with no mark."""
        self._core.follow_week(self._env(), fresh_day)

    def dirty(self) -> bool:
        """Whether there is typed work that closing would lose."""
        return self._core.dirty()

    def estimate(self) -> int:
        return self._core.estimate()

    def spread_shown(self) -> bool:
        return self._core.spread_shown()

    def _spread_figures(self) -> tuple[int, str, list[dict]]:
        session_min, from_date, sessions = self._core.spread_figures(self._env())
        return session_min, from_date, json.loads(sessions)

    def spread_requested(self) -> bool:
        return self._core.spread_requested()

    def spread_plan(self) -> dict:
        return json.loads(self._core.spread_plan(self._env()))

    def read_clock(self) -> None:
        """The clock now: a sheet kept while the student was away judges a picked time by the time it is
        when it opens again, not by the time it was first built."""
        self._core.read_clock(self._stamp())

    def use_picked(self, day: int, start: str) -> None:
        """A kept new sheet opened again from a time picked on the grid: it is pinned to the picked day and
        start. The typed words and length stay."""
        self._core.use_picked(self._env(), day, start)

    def set(self, name: str, value: Any) -> None:
        """One field changed. Words that said it was wrong go when it changes."""
        self._core.set(self._env(), name, json.dumps(value))

    def add_link(self) -> None:
        self._core.add_link()

    def remove_link(self, index: int) -> None:
        self._core.remove_link(index)

    def add_check(self) -> None:
        self._core.add_check(str(uuid4()))

    def toggle_check(self, index: int) -> None:
        self._core.toggle_check(index)

    def remove_check(self, index: int) -> None:
        self._core.remove_check(index)

    def back(self) -> None:
        self._core.back()

    def goto(self, index: int) -> None:
        """A crumb that is already done takes the sheet back to that step."""
        self._core.goto(index)

    def advance(self) -> bool:
        """Next on the first two steps. True when the sheet is on its last step and Save is next."""
        return self._core.advance(self._env())

    def candidate(self) -> dict | None:
        """The homework as typed, or None with the reason put on the field it belongs to. The step with
        the problem is the one the sheet goes back to."""
        made = self._core.candidate(self._env())
        if made is None:
            return None
        return json.loads(made)

    def form(self) -> dict:
        """What the sheet shows."""
        return json.loads(self._core.form(self._env()))
