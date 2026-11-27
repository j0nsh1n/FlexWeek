"""Add and Edit fixed time: what the student typed, and what saving it means.

The clock, the fresh id and the live session lists stay here. The sheet's rules are in the engine.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import flexweek_engine  # type: ignore[import-untyped]

from backend import clock as wall_clock
from desktop.native.remind import clock_parts


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
        spec = {
            "block": block,
            "day": day,
            "start": start,
            "category": category,
            "occurrence_day": occurrence_day,
            "length": length,
            "id": str(uuid4()),
        }
        self._state = json.loads(flexweek_engine.block_draft_open(json.dumps(spec), json.dumps(self._bag())))

    def _bag(self) -> dict:
        # One read of the clock. The sheet never asks the operating system itself.
        now_ms = self.session.now_ms()
        parts = clock_parts(now_ms)
        return {
            "week_start": self.session.week_start,
            "blocks": self.session.blocks,
            "preferences": self.session.preferences,
            "repeats": getattr(self.session, "repeats", None),
            "first_weekday": getattr(self.session, "first_weekday", 0),
            "today": wall_clock.today().isoformat(),
            "now_iso": parts["iso"],
            "now_minute": parts["minute"],
        }

    def _replace(self, state: str) -> None:
        self._state = json.loads(state)

    @property
    def original(self) -> dict:
        return self._state["original"]

    @property
    def category(self) -> str | None:
        return self._state["category"]

    @property
    def days(self) -> list:
        return self._state["days"]

    @property
    def scope(self) -> str:
        return self._state["scope"]

    @property
    def family(self) -> str:
        return self._state["family"]

    @property
    def occurrence_day(self) -> int | None:
        return self._state["occurrence_day"]

    @property
    def existing(self) -> bool:
        return self._state["existing"]

    @property
    def error(self) -> str:
        return self._state["error"]

    @error.setter
    def error(self, value: str) -> None:
        self._state["error"] = value

    def follow_week(self, fresh_days: list[int]) -> None:
        """A kept sheet opened in a week that starts on another day."""
        self._replace(
            flexweek_engine.block_draft_follow_week(
                json.dumps(self._state), json.dumps(fresh_days), json.dumps(self._bag())
            )
        )

    def dirty(self) -> bool:
        return flexweek_engine.block_draft_dirty(json.dumps(self._state))

    def set(self, name: str, value: Any) -> None:
        self._replace(flexweek_engine.block_draft_set(json.dumps(self._state), name, json.dumps(value)))

    def toggle_day(self, day: int) -> None:
        self._replace(flexweek_engine.block_draft_toggle_day(json.dumps(self._state), json.dumps(day)))

    def use_picked(self, day: int, start: str, length: int) -> None:
        """A kept new sheet opened again from a time picked on the grid."""
        self._replace(flexweek_engine.block_draft_use_picked(json.dumps(self._state), day, start, length))

    def back(self) -> None:
        self._replace(flexweek_engine.block_draft_back(json.dumps(self._state)))

    def goto(self, index: int) -> None:
        self._replace(flexweek_engine.block_draft_goto(json.dumps(self._state), index))

    def advance(self) -> bool:
        state, done = flexweek_engine.block_draft_advance(json.dumps(self._state), json.dumps(self._bag()))
        self._state = json.loads(state)
        return done

    def candidate(self) -> dict | None:
        state, made = flexweek_engine.block_draft_candidate(json.dumps(self._state), json.dumps(self._bag()))
        self._state = json.loads(state)
        return json.loads(made)

    def clash(self) -> str:
        return flexweek_engine.block_draft_clash(json.dumps(self._state), json.dumps(self.session.blocks))

    def stopped_one_off(self, made: dict) -> dict | None:
        alone = flexweek_engine.block_draft_stopped_one_off(json.dumps(self._state), json.dumps(made))
        return json.loads(alone)

    def save_plan(self, made: dict) -> dict:
        plan = json.loads(
            flexweek_engine.block_draft_save_plan(
                json.dumps(self._state),
                json.dumps(made),
                json.dumps(self._bag()),
                str(uuid4()),
            )
        )
        plan["changed"] = set(plan["changed"])
        return plan

    def recover_missed(self) -> bool:
        return flexweek_engine.block_draft_recover_missed(json.dumps(self._state))

    def delete_question(self) -> dict:
        return json.loads(
            flexweek_engine.block_draft_delete_question(json.dumps(self._state), json.dumps(self._bag()))
        )

    def save_question(self) -> dict:
        return json.loads(flexweek_engine.block_draft_save_question(json.dumps(self._state)))

    def form(self) -> dict:
        return json.loads(flexweek_engine.block_draft_form(json.dumps(self._state), json.dumps(self._bag())))
