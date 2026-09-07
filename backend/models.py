from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

BlockKind = Literal["locked", "flexible"]
Priority = Literal[1, 2, 3, 4]
Energy = Literal["high", "medium", "low"]
ReasonCode = Literal[
    "LOCKED_OVERLAP",
    "DEADLINE_MISS",
    "NO_SLOT_LEFT",
    "PRIORITY_PREEMPT",
    "ENERGY_MISMATCH",
    "SLEEP_GUARD",
    "RESHUFFLE_AFTER_MISS",
]


class TimeBlock(BaseModel):
    id: str
    title: str
    kind: BlockKind
    duration_min: int
    days: list[int] = Field(min_length=1)
    priority: Priority = 3
    energy: Energy = "medium"
    earliest: str | None = None
    latest: str | None = None
    start: str | None = None
    course: str | None = None

    @field_validator("duration_min")
    @classmethod
    def duration_is_slot_aligned(cls, value: int) -> int:
        if value <= 0 or value % 15 != 0:
            raise ValueError("duration_min must be a positive multiple of 15")
        return value

    @field_validator("days")
    @classmethod
    def days_in_week(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("days must be in 0..6 (Mon..Sun)")
        return value


class Move(BaseModel):
    block_id: str
    reason: ReasonCode
    from_start: str | None = None
    to_start: str | None = None


class SolveTrace(BaseModel):
    placed: list[TimeBlock]
    unplaced: list[TimeBlock]
    moves: list[Move]
    failed_constraints: list[ReasonCode]
    solve_ms: float
    complete: bool


class WeekRequest(BaseModel):
    blocks: list[TimeBlock]
