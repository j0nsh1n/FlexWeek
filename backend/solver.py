from __future__ import annotations

import time

from backend.models import SolveTrace, TimeBlock

SOLVE_BUDGET_MS = 150


def solve(blocks: list[TimeBlock]) -> SolveTrace:
    """Phase 2 replaces this stub. Locked blocks stay; flexible stay unplaced."""
    started = time.perf_counter()
    locked = [block.model_copy() for block in blocks if block.kind == "locked"]
    flexible = [block.model_copy() for block in blocks if block.kind == "flexible"]
    solve_ms = (time.perf_counter() - started) * 1000
    return SolveTrace(
        placed=locked,
        unplaced=flexible,
        moves=[],
        failed_constraints=[],
        solve_ms=solve_ms,
        complete=len(flexible) == 0,
    )
