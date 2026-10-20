"""Plant a block for a test setup, without the hand-move rule, which refuses a start in the past,
on a day already over, or past the due time."""

from __future__ import annotations

from backend.slots import minutes_to_hhmm
from desktop.native.controller import NativeSession


def put_block(
    session: NativeSession,
    block_id: str,
    day: int,
    start_min: int,
    end_min: int | None = None,
    *,
    pinned: bool | None = None,
) -> None:
    """Set the block's start, day, length and pin state where it lives, and drop it from the
    session's needs-time list. Nothing else runs: no rule, no Undo step. A setup calls it to plant a
    block before the thing the test is about; `pinned` only moves when given."""
    block = next(item for item in session.blocks if item["id"] == block_id)
    block["start"] = minutes_to_hhmm(start_min)
    block["days"] = [day]
    if end_min is not None:
        block["duration_min"] = end_min - start_min
    if pinned is not None:
        block["pinned"] = pinned
    session.needs_time.pop(block_id, None)
