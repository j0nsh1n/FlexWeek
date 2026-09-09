from __future__ import annotations

import time

from backend.explain import sentence, slack_sentence
from backend.models import Explanation, Move, ReasonCode, SlackStatus, SolveTrace, TimeBlock
from backend.slots import (
    DAY_END_MIN,
    DAY_START_MIN,
    SLOT_MIN,
    SLOTS_PER_DAY,
    duration_to_slots,
    hhmm_to_minutes,
    occupancy_mask,
    parse_deadline,
    slot_to_hhmm,
)

SOLVE_BUDGET_MS = 150

ENERGY_WINDOW = {
    "high": (6 * 60, 12 * 60),
    "medium": (12 * 60, 17 * 60),
    "low": (17 * 60, 23 * 60),
}
TIGHT_SLACK_MIN = 3 * 60
DANGER_SLACK_MIN = 60


def solve(blocks: list[TimeBlock]) -> SolveTrace:
    """Place flexible blocks around locked ones. Pure and synchronous."""
    started = time.perf_counter()
    locked = _active_locked(blocks)
    every_flexible = [block.model_copy() for block in blocks if block.kind == "flexible"]
    # Finished work is never scheduled again. One that already has a slot spent
    # that time, so it stays on the grid and nothing new is booked over it; one
    # with no slot needs none and is not reported unplaced. Locked blocks are
    # untouched by this, so a completed lesson keeps its place in the week.
    # Only a real placement is spent time: one day, one start. A finished task
    # still listed on several candidate days was done once, and nobody knows on
    # which, so it holds no slot rather than blocking that hour on every day.
    spent = [
        block
        for block in every_flexible
        if block.completed and block.start is not None and len(block.days) == 1
    ]
    flexible = [block for block in every_flexible if not block.completed]

    occ_locked = _locked_occupancy(locked + spent)
    flex_by_id = {block.id: block for block in flexible}
    ids = [block.id for block in flexible]
    deadlines = {block.id: parse_deadline(block.latest, block.days) for block in flexible}
    earliest = {block.id: parse_deadline(block.earliest, block.days) for block in flexible}
    lengths = {block.id: duration_to_slots(block.duration_min) for block in flexible}
    domains0 = {
        block.id: _domain(block, occ_locked, deadlines[block.id], earliest[block.id])
        for block in flexible
    }

    best: dict[str, tuple[int, int]] = {}
    best_score = (-1, 0)
    timed_out = False

    def remaining_ms() -> float:
        return SOLVE_BUDGET_MS - (time.perf_counter() - started) * 1000

    def search(
        occ: list[int],
        domains: dict[str, list[tuple[int, int]]],
        assigned: dict[str, tuple[int, int]],
    ) -> None:
        nonlocal best, best_score, timed_out
        if remaining_ms() <= 0:
            timed_out = True
            return
        score = (len(assigned), -sum(flex_by_id[item].priority for item in assigned))
        if score > best_score:
            best_score = score
            best = dict(assigned)
        if len(assigned) == len(ids):
            return
        live = [item for item in ids if item not in assigned and domains[item]]
        if not live:
            return
        var = min(
            live,
            key=lambda item: (
                len(domains[item]),
                flex_by_id[item].priority,
                deadlines[item] if deadlines[item] is not None else (7, 0),
                item,
            ),
        )
        n = lengths[var]
        for day, slot in _order_values(flex_by_id[var], domains[var]):
            if remaining_ms() <= 0:
                timed_out = True
                return
            mask = occupancy_mask(slot, n)
            new_occ = occ.copy()
            new_occ[day] |= mask
            new_domains = {key: list(vals) for key, vals in domains.items()}
            new_domains[var] = []
            for other, vals in new_domains.items():
                if other == var or other in assigned:
                    continue
                other_n = lengths[other]
                new_domains[other] = [
                    (other_day, other_slot)
                    for other_day, other_slot in vals
                    if other_day != day or (occupancy_mask(other_slot, other_n) & mask) == 0
                ]
            search(new_occ, new_domains, {**assigned, var: (day, slot)})
            if timed_out or len(best) == len(ids):
                return

    search(occ_locked, {key: list(vals) for key, vals in domains0.items()}, {})

    placed_flex: list[TimeBlock] = []
    occ_final = occ_locked.copy()
    for block_id, (day, slot) in best.items():
        placed = flex_by_id[block_id].model_copy()
        placed.start = slot_to_hhmm(slot)
        placed.days = [day]
        placed_flex.append(placed)
        occ_final[day] |= occupancy_mask(slot, lengths[block_id])

    unplaced: list[TimeBlock] = []
    moves: list[Move] = []
    explanations: list[Explanation] = []
    failed: list[ReasonCode] = []
    for block in flexible:
        if block.id in best:
            continue
        reason = _reason_for(block, occ_locked, best, flex_by_id, deadlines, earliest)
        unplaced.append(block.model_copy())
        moves.append(Move(block_id=block.id, reason=reason))
        explanations.append(Explanation(block_id=block.id, reason=reason, message=sentence(reason)))
        if reason not in failed:
            failed.append(reason)

    for block in placed_flex:
        assert block.start is not None
        start_min = hhmm_to_minutes(block.start)
        low, high = ENERGY_WINDOW[block.energy]
        if not low <= start_min < high:
            energy_reason: ReasonCode = "ENERGY_MISMATCH"
            explanations.append(
                Explanation(block_id=block.id, reason=energy_reason, message=sentence(energy_reason))
            )
        deadline = deadlines[block.id]
        if deadline is not None:
            day = block.days[0]
            slack_min = (deadline[0] - day) * 24 * 60 + deadline[1] - start_min - block.duration_min
            status = _slack_status(slack_min)
            explanations.append(
                Explanation(
                    block_id=block.id,
                    message=slack_sentence(slack_min, status),
                    slack_min=slack_min,
                    slack_status=status,
                )
            )

    return SolveTrace(
        placed=locked + spent + placed_flex,
        unplaced=unplaced,
        moves=moves,
        explanations=explanations,
        failed_constraints=failed,
        solve_ms=(time.perf_counter() - started) * 1000,
        complete=len(unplaced) == 0,
    )


def reschedule_after_miss(
    blocks: list[TimeBlock],
    missed_block_id: str,
    missed_day: int,
    previous_placed: list[TimeBlock],
) -> SolveTrace:
    """Mark one locked occurrence missed, solve again, and describe changed flexible placements."""
    updated: list[TimeBlock] = []
    found = False
    for block in blocks:
        copy = block.model_copy(deep=True)
        if copy.id == missed_block_id and copy.kind == "locked" and missed_day in copy.days:
            found = True
            if missed_day not in copy.missed_days:
                copy.missed_days = sorted([*copy.missed_days, missed_day])
        updated.append(copy)
    if not found:
        raise ValueError("missed occurrence must identify a locked block on that day")

    trace = solve(updated)
    before = _flex_positions(previous_placed)
    after = _flex_positions(trace.placed)
    changes: list[Move] = []
    unplaced_moves = {move.block_id: move for move in trace.moves}
    for block in blocks:
        # Finished work is out of the solver, so its slot disappearing is not a
        # reshuffle. Without this it is reported as moved to nowhere.
        if block.kind != "flexible" or block.completed or before.get(block.id) == after.get(block.id):
            continue
        old = before.get(block.id)
        new = after.get(block.id)
        if new is None and block.id in unplaced_moves:
            unplaced_moves[block.id].from_day = old[0] if old else None
            unplaced_moves[block.id].from_start = old[1] if old else None
        else:
            changes.append(
                Move(
                    block_id=block.id,
                    reason="RESHUFFLE_AFTER_MISS",
                    from_day=old[0] if old else None,
                    from_start=old[1] if old else None,
                    to_day=new[0] if new else None,
                    to_start=new[1] if new else None,
                )
            )
        if new is not None:
            trace.explanations.append(
                Explanation(
                    block_id=block.id,
                    reason="RESHUFFLE_AFTER_MISS",
                    message=sentence("RESHUFFLE_AFTER_MISS"),
                )
            )
    trace.moves = changes + trace.moves
    return trace


def _active_locked(blocks: list[TimeBlock]) -> list[TimeBlock]:
    active: list[TimeBlock] = []
    for block in blocks:
        if block.kind != "locked":
            continue
        days = [day for day in block.days if day not in block.missed_days]
        if days:
            active.append(block.model_copy(update={"days": days, "missed_days": []}))
    return active


def _flex_positions(blocks: list[TimeBlock]) -> dict[str, tuple[int, str]]:
    return {
        block.id: (block.days[0], block.start)
        for block in blocks
        if block.kind == "flexible" and block.start is not None and len(block.days) == 1
    }


def _slack_status(slack_min: int) -> SlackStatus:
    if slack_min <= DANGER_SLACK_MIN:
        return "danger"
    if slack_min <= TIGHT_SLACK_MIN:
        return "tight"
    return "ok"


def _locked_occupancy(locked: list[TimeBlock]) -> list[int]:
    occ = [0] * 7
    for block in locked:
        if block.start is None:
            continue
        start_min = hhmm_to_minutes(block.start)
        end_min = start_min + block.duration_min
        if start_min < DAY_START_MIN:
            start_min = DAY_START_MIN
        if start_min >= DAY_END_MIN:
            continue
        offset = start_min - DAY_START_MIN
        slot = offset // SLOT_MIN
        end_offset = min(DAY_END_MIN, end_min) - DAY_START_MIN
        n = min(max(0, end_offset // SLOT_MIN - slot), SLOTS_PER_DAY - slot)
        if n:
            for day in block.days:
                occ[day] |= occupancy_mask(slot, n)
    return occ


def _domain(
    block: TimeBlock,
    occ: list[int],
    deadline: tuple[int, int] | None,
    earliest: tuple[int, int] | None,
) -> list[tuple[int, int]]:
    n = duration_to_slots(block.duration_min)
    out: list[tuple[int, int]] = []
    for day in block.days:
        for slot in range(0, SLOTS_PER_DAY - n + 1):
            start_min = DAY_START_MIN + slot * SLOT_MIN
            end_min = start_min + block.duration_min
            if deadline is not None and (day, end_min) > deadline:
                continue
            if earliest is not None and (day, start_min) < earliest:
                continue
            if occ[day] & occupancy_mask(slot, n):
                continue
            out.append((day, slot))
    return out


def _order_values(block: TimeBlock, values: list[tuple[int, int]]) -> list[tuple[int, int]]:
    low, high = ENERGY_WINDOW[block.energy]

    def key(item: tuple[int, int]) -> tuple[int, int, int]:
        day, slot = item
        start_min = DAY_START_MIN + slot * SLOT_MIN
        match = 0 if low <= start_min < high else 1
        return (match, day, slot)

    return sorted(values, key=key)


def _has_gap(occ_day: int, n: int) -> bool:
    return any(occ_day & occupancy_mask(slot, n) == 0 for slot in range(SLOTS_PER_DAY - n + 1))


def _reason_for(
    block: TimeBlock,
    occ_locked: list[int],
    assigned: dict[str, tuple[int, int]],
    flex_by_id: dict[str, TimeBlock],
    deadlines: dict[str, tuple[int, int] | None],
    earliest: dict[str, tuple[int, int] | None],
) -> ReasonCode:
    deadline = deadlines[block.id]
    earliest_pt = earliest[block.id]
    empty = [0] * 7
    vs_locked = _domain(block, occ_locked, deadline, earliest_pt)
    if vs_locked:
        if any(flex_by_id[item].priority < block.priority for item in assigned):
            return "PRIORITY_PREEMPT"
        return "NO_SLOT_LEFT"

    unconstrained = _domain(block, empty, deadline, earliest_pt)
    if not unconstrained:
        if deadline is not None and _domain(block, empty, None, earliest_pt):
            return "DEADLINE_MISS"
        return "SLEEP_GUARD"

    n = duration_to_slots(block.duration_min)
    if not any(_has_gap(occ_locked[day], n) for day in block.days):
        return "NO_SLOT_LEFT"
    return "LOCKED_OVERLAP"
