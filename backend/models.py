from __future__ import annotations

import re
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
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=80)
    kind: BlockKind
    duration_min: int = Field(le=7140)
    days: list[int] = Field(min_length=1, max_length=7)
    priority: Priority = 3
    energy: Energy = "medium"
    earliest: str | None = Field(default=None, max_length=40)
    latest: str | None = Field(default=None, max_length=40)
    start: str | None = Field(default=None, max_length=5)
    course: str | None = Field(default=None, max_length=40)

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
    blocks: list[TimeBlock] = Field(max_length=100)

    @field_validator("blocks")
    @classmethod
    def valid_week(cls, blocks: list[TimeBlock]) -> list[TimeBlock]:
        if len({block.id for block in blocks}) != len(blocks):
            raise ValueError("block ids must be unique")
        for block in blocks:
            if not block.title.strip() or len(set(block.days)) != len(block.days):
                raise ValueError("title and unique days required")
            if block.kind == "locked" and not block.start:
                raise ValueError("locked blocks need a start")
            if block.start:
                if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", block.start):
                    raise ValueError("invalid start time")
                hour, minute = map(int, block.start.split(":"))
                start = hour * 60 + minute
                if minute % 15 or start < 360 or start + block.duration_min > 1380:
                    raise ValueError("block must fit the 06:00–23:00 grid")
            for bound in (block.earliest, block.latest):
                if bound and not re.fullmatch(
                    r"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) )?"
                    r"(?:[01]\d|2[0-3]):[0-5]\d",
                    bound,
                ):
                    raise ValueError("invalid deadline or earliest time")
        return blocks
