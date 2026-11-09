"""The rules a TimeBlock keeps before the engine sees it: lengths, days, pinned and finished blocks.
What the solver does with finished and pinned blocks is tested in engine/engine/tests/test_completed.rs
and test_solver.rs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.models import TimeBlock


def test_a_blocks_length_is_any_positive_minute() -> None:
    assert TimeBlock(id="short", title="Short", kind="locked", duration_min=7, days=[0], start="17:37")
    with pytest.raises(ValidationError):
        TimeBlock(id="bad", title="Bad", kind="flexible", duration_min=0, days=[0])


def test_days_must_be_in_week() -> None:
    with pytest.raises(ValidationError):
        TimeBlock(
            id="bad",
            title="Bad",
            kind="locked",
            duration_min=15,
            days=[7],
            start="08:00",
        )


@pytest.mark.parametrize(
    "block",
    [
        {"kind": "locked", "start": "08:00", "days": [0]},
        {"kind": "flexible", "start": None, "days": [0]},
        {"kind": "flexible", "start": "15:00", "days": [0, 1]},
    ],
)
def test_pinned_is_refused_where_it_means_nothing(block: dict) -> None:
    with pytest.raises(ValueError, match="pinned"):
        TimeBlock(id="x", title="X", duration_min=60, pinned=True, **block)


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "locked"},
        {"completed": False},
        {"start": None},
        {"completed_day": 3},
    ],
)
def test_completed_day_requires_a_matching_finished_flexible_placement(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "id": "done",
        "title": "Done",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0, 1, 2],
        "start": "09:00",
        "completed": True,
        "completed_day": 1,
    }
    values.update(changes)
    with pytest.raises(ValidationError, match="completed_day"):
        TimeBlock.model_validate(values)
