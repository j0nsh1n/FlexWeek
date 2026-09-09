from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

BlockKind = Literal["locked", "flexible"]
Priority = Literal[1, 2, 3, 4]
Energy = Literal["high", "medium", "low"]
SlackStatus = Literal["ok", "tight", "danger"]
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
    category: str | None = Field(
        default=None,
        max_length=32,
        exclude_if=lambda value: value is None,
    )
    completed: bool = Field(
        default=False,
        exclude_if=lambda value: value is False,
    )
    missed_days: list[int] = Field(
        default_factory=list,
        max_length=7,
        exclude_if=lambda value: not value,
    )

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

    @field_validator("missed_days")
    @classmethod
    def missed_days_in_week(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value) or any(day < 0 or day > 6 for day in value):
            raise ValueError("missed_days must be unique values in 0..6")
        return value

    @model_validator(mode="after")
    def missed_occurrences_belong_to_locked_block(self) -> TimeBlock:
        if self.missed_days and self.kind != "locked":
            raise ValueError("only locked blocks can have missed days")
        if not set(self.missed_days).issubset(self.days):
            raise ValueError("missed days must be occurrences of the block")
        return self


class Move(BaseModel):
    block_id: str
    reason: ReasonCode
    from_day: int | None = Field(default=None, ge=0, le=6)
    from_start: str | None = None
    to_day: int | None = Field(default=None, ge=0, le=6)
    to_start: str | None = None


class Explanation(BaseModel):
    block_id: str
    message: str
    reason: ReasonCode | None = None
    slack_min: int | None = Field(default=None, ge=0)
    slack_status: SlackStatus | None = None


class SolveTrace(BaseModel):
    placed: list[TimeBlock]
    unplaced: list[TimeBlock]
    moves: list[Move]
    explanations: list[Explanation]
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


class RecoveryRequest(BaseModel):
    missed_block_id: str = Field(min_length=1, max_length=80)
    missed_day: int = Field(ge=0, le=6)
    previous_placed: list[TimeBlock] = Field(max_length=100)

    @field_validator("previous_placed")
    @classmethod
    def previous_ids_are_unique(cls, blocks: list[TimeBlock]) -> list[TimeBlock]:
        if len({block.id for block in blocks}) != len(blocks):
            raise ValueError("previous placement ids must be unique")
        return blocks


class SolveRequest(WeekRequest):
    recover: RecoveryRequest | None = None

    @model_validator(mode="after")
    def missed_occurrence_exists(self) -> SolveRequest:
        if self.recover is None:
            return self
        matches = [block for block in self.blocks if block.id == self.recover.missed_block_id]
        if (
            not matches
            or matches[0].kind != "locked"
            or self.recover.missed_day not in matches[0].days
            or self.recover.missed_day in matches[0].missed_days
        ):
            raise ValueError("missed occurrence must identify a locked block on that day")
        return self
