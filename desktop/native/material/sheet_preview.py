"""The preview sheet: what Paste, Duplicate and the other copies propose, row by row.

The save callable and the live blocks stay here. The row rules are in the engine.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import flexweek_engine  # type: ignore[import-untyped]

NONE_CHOSEN = "Select at least one item before saving."


def beside_words(clash: str) -> str:
    """What a time says when another block is already there: it is allowed, and both are drawn."""
    return flexweek_engine.preview_beside_words(clash)


class PreviewDraft:
    """Rows the student can untick, and for a fixed time move to another day, start or length."""

    def __init__(
        self,
        title: str,
        summary: str,
        rows: list[dict],
        existing: list[dict],
        save: Callable[[list[dict]], None],
        confirm: str = "Save preview",
    ) -> None:
        self.existing = existing
        self.save = save
        self._state = json.loads(
            flexweek_engine.preview_draft_open(
                json.dumps({"title": title, "summary": summary, "confirm": confirm, "rows": rows})
            )
        )

    def _replace(self, state: str) -> None:
        self._state = json.loads(state)

    @property
    def rows(self) -> list:
        return self._state["rows"]

    @property
    def title(self) -> str:
        return self._state["title"]

    @property
    def summary(self) -> str:
        return self._state["summary"]

    @property
    def confirm(self) -> str:
        return self._state["confirm"]

    def can_save(self) -> bool:
        return flexweek_engine.preview_draft_can_save(json.dumps(self._state))

    def check(self, index: int, checked: bool) -> None:
        self._replace(flexweek_engine.preview_draft_check(json.dumps(self._state), index, checked))

    def set_day(self, index: int, day: int) -> None:
        self._replace(
            flexweek_engine.preview_draft_set_day(
                json.dumps(self._state), index, day, json.dumps(self.existing)
            )
        )

    def set_start(self, index: int, start: str) -> None:
        self._replace(
            flexweek_engine.preview_draft_set_start(
                json.dumps(self._state), index, start, json.dumps(self.existing)
            )
        )

    def set_duration(self, index: int, minutes: int) -> None:
        self._replace(
            flexweek_engine.preview_draft_set_duration(
                json.dumps(self._state), index, json.dumps(minutes), json.dumps(self.existing)
            )
        )

    def form(self) -> dict[str, Any]:
        state, form = flexweek_engine.preview_draft_form(json.dumps(self._state), json.dumps(self.existing))
        self._state = json.loads(state)
        return json.loads(form)
