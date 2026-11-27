"""Focus timer math. Wall-clock phases, persist payloads and credit rules. No Qt."""

from __future__ import annotations

import json
from typing import Any

import flexweek_engine  # type: ignore[import-untyped]
from flexweek_engine import ESTIMATE_MAX_MIN

from desktop.native.wire import plain

FOCUS_PHASES = ("work", "break", "long_break", "ended")
FOCUS_PHASE_LABEL = {
    "work": "Focus session",
    "break": "Break",
    "long_break": "Long break",
    "ended": "Session finished",
}
MAX_ESTIMATE_MIN = ESTIMATE_MAX_MIN
MAX_FOCUS_MINUTES = 71400
MAX_FOCUS_SESSIONS = 9999
MORE_TIME_CHOICES = (15, 30, 45, 60, 90, 120, 180, 240)
DEFAULT_TIMERS = {
    "timer_work_min": 30,
    "timer_break_min": 15,
    "timer_long_break_min": 30,
    "timer_long_break_every": 4,
}


def phase_duration_ms(phase: str, prefs: dict | None) -> int:
    return int(flexweek_engine.focus_phase_ms(json.dumps(phase), json.dumps(prefs)))


def work_minutes(state: dict | None, prefs: dict | None) -> int:
    return int(flexweek_engine.focus_work_minutes(json.dumps(state), json.dumps(prefs)))


def phase_total_ms(state: dict, prefs: dict | None) -> int:
    return int(flexweek_engine.focus_phase_total_ms(json.dumps(state), json.dumps(prefs)))


def format_countdown(milliseconds: int) -> str:
    return str(flexweek_engine.focus_countdown(milliseconds))


def remaining_ms(state: dict, now_ms: int) -> int:
    return int(flexweek_engine.focus_remaining(json.dumps(state), now_ms))


def focus_now(state: dict | None) -> str:
    """What the timer is doing, for a page that only says so: "" when none runs or its session has
    ended, else "focusing", "paused" or "break"."""
    return str(flexweek_engine.focus_now(json.dumps(state)))


def more_time_choices(estimate_min: int) -> list[int]:
    return list(flexweek_engine.focus_more_time(estimate_min))


def persist_payload(state: dict | None) -> dict | None:
    raw = flexweek_engine.focus_persist(json.dumps(state))
    return None if raw is None else json.loads(raw)


def restore_state(saved: dict | None, *, assignments: dict, blocks: list[dict], now_ms: int) -> dict | None:
    raw = flexweek_engine.focus_restore(plain(saved), json.dumps(assignments), json.dumps(blocks), now_ms)
    return None if raw is None else json.loads(raw)


def begin_state(target: dict, prefs: dict | None, now_ms: int) -> dict:
    return json.loads(flexweek_engine.focus_begin(json.dumps(target), json.dumps(prefs), now_ms))


def pause_state(state: dict, now_ms: int) -> dict:
    return json.loads(flexweek_engine.focus_pause(json.dumps(state), now_ms))


def set_phase(state: dict, phase: str, prefs: dict | None, now_ms: int) -> dict:
    return json.loads(
        flexweek_engine.focus_set_phase(json.dumps(state), json.dumps(phase), json.dumps(prefs), now_ms)
    )


def break_phase(cycles: int, prefs: dict | None) -> str:
    return str(flexweek_engine.focus_break_phase(cycles, json.dumps(prefs)))


def credit_target(state: dict, assignment: dict | None, block: dict | None, work_min: int) -> dict | None:
    """Return the mutated homework or block after one completed work phase. None if nothing to credit."""
    raw = flexweek_engine.focus_credit(
        json.dumps(state), json.dumps(assignment), json.dumps(block), work_min
    )
    return None if raw is None else json.loads(raw)


def focus_candidates(
    blocks: list[dict], assignments: dict, trace: dict | None, week_start: str, now: str
) -> list[dict]:
    return json.loads(
        flexweek_engine.focus_candidates(
            json.dumps(blocks), json.dumps(assignments), json.dumps(trace), week_start, now
        )
    )


def quick_focus_homework(
    blocks: list[dict], assignments: dict, trace: dict | None, week_start: str, now: str
) -> dict | None:
    return json.loads(
        flexweek_engine.focus_quick_homework(
            json.dumps(blocks), json.dumps(assignments), json.dumps(trace), week_start, now
        )
    )


def now_and_next(blocks: list[dict], day: int, minute: int) -> dict:
    return json.loads(flexweek_engine.focus_now_next(json.dumps(blocks), json.dumps(day), minute))


def now_next_line(result: dict, minute: int) -> str:
    return str(flexweek_engine.focus_now_next_line(json.dumps(result), minute))


def _decide(name: str, **args: object) -> Any:
    """One of the session's focus decisions, made in Rust from the arguments as JSON."""
    ask = getattr(flexweek_engine, f"session_focus_{name}")
    return json.loads(ask(json.dumps(args)))


def start_target(
    *,
    block_id: str | None,
    day: int | None,
    quick: bool,
    week_start: str,
    assignments: dict,
    blocks: list[dict],
    trace: dict | None,
    overdue: list[str],
) -> dict:
    """`{"target": ...}` for what a start would time, or `{"refuse": words}` when nothing can start."""
    found: dict = _decide(
        "start_target",
        block_id=block_id,
        day=day,
        quick=quick,
        week_start=week_start,
        assignments=assignments,
        blocks=blocks,
        trace=trace,
        overdue=overdue,
    )
    return found


def start_decision(running: dict | None, target: dict, replace: bool) -> str:
    """Starting what is already going is "same", another start "ask"s to replace it, else "begin"."""
    return str(_decide("start_decision", focus=running, target=target, replace=replace))


def elapsed_minutes(state: dict | None, week_start: str, prefs: dict | None, now_ms: int) -> int:
    return int(_decide("elapsed_min", focus=state, week_start=week_start, prefs=prefs, now_ms=now_ms))


def tick_step(state: dict | None, *, credits_waiting: bool, busy: bool, now_ms: int) -> dict:
    """`credit` (credit the sessions waiting first) and `action`: "none", "ended" or "changed"."""
    step: dict = _decide(
        "tick_step", focus=state, credits_waiting=credits_waiting, busy=busy, now_ms=now_ms
    )
    return step


def advance_begin(state: dict | None, *, focus_busy: bool, completed: bool) -> dict:
    """`go` (there is a timer to move) and `credit` (credit the work phase that just ended first)."""
    begun: dict = _decide("advance_begin", focus=state, focus_busy=focus_busy, completed=completed)
    return begun


def advance_plan(
    state: dict, *, completed: bool, assignment_known: bool, prefs: dict | None, now_ms: int
) -> dict:
    """The timer's `state` after a phase, the `alert` to tell and whether it goes out first
    (`alert_first`), and the `cycles` when a work phase was left."""
    plan: dict = _decide(
        "advance_plan",
        focus=state,
        completed=completed,
        assignment_known=assignment_known,
        prefs=prefs,
        now_ms=now_ms,
    )
    return plan


def enter_phase(state: dict, phase: str, prefs: dict | None, now_ms: int) -> dict:
    """The timer's `state` in a phase and the `alert` that announces it."""
    entered: dict = _decide("enter_phase", state=state, phase=phase, prefs=prefs, now_ms=now_ms)
    return entered


def credit_plan(
    state: dict, *, week_start: str, assignments: dict, blocks: list[dict], work_min: int
) -> dict:
    """Where a credit goes: `to` ("assignment" or "block") with the `updated` item, a `say`, or a `skip`."""
    plan: dict = _decide(
        "credit_plan",
        state=state,
        week_start=week_start,
        assignments=assignments,
        blocks=blocks,
        work_min=work_min,
    )
    return plan


def auto_complete_plan(
    state: dict,
    *,
    prefs: dict | None,
    material_owns: bool,
    week_start: str,
    assignments: dict,
    blocks: list[dict],
) -> dict:
    """The `block` to mark Done and the homework to complete (`complete_homework`), each or null."""
    plan: dict = _decide(
        "auto_complete_plan",
        state=state,
        prefs=prefs,
        material_owns=material_owns,
        week_start=week_start,
        assignments=assignments,
        blocks=blocks,
    )
    return plan


def mutes_alerts(state: dict | None, prefs: dict | None, material_owns: bool) -> bool:
    return bool(_decide("mutes_alerts", focus=state, prefs=prefs, material_owns=material_owns))


def alerts_held(
    kinds: list, state: dict | None, prefs: dict | None, material_owns: bool
) -> list[bool]:
    """For each notice, by its kind, whether focus keeps it back."""
    held: list[bool] = _decide(
        "hold_alerts", kinds=kinds, focus=state, prefs=prefs, material_owns=material_owns
    )["hold"]
    return held


def drop_missing(state: dict | None, week_start: str, blocks: list[dict], announce: bool) -> dict:
    """`drop` (the timer's block is gone) and the words to `say`, or null."""
    found: dict = _decide(
        "drop_missing", focus=state, week_start=week_start, blocks=blocks, announce=announce
    )
    return found


def rebase_state(state: dict | None, first_weekday: int) -> dict | None:
    """The timer in the week from the new first day, keeping its date; None when it has no week."""
    return _decide("rebase", focus=state, first_weekday=first_weekday)["state"]


def scheduled_blocks_of(blocks: list[dict], trace: dict | None) -> list[dict]:
    """Locked blocks and timed flexible ones, or each placed row laid over the block it names."""
    shown: list[dict] = _decide("scheduled_blocks", blocks=blocks, trace=trace)
    return shown


def restore_decision(
    saved: dict | None, *, assignments: dict, blocks: list[dict], prefs: dict | None, now_ms: int
) -> dict:
    """What a saved timer becomes: drop, active, advance_work, or paused_work."""
    # A saved timer can hold NaN or a lone surrogate. `plain` is the form the decision drops;
    # `json.dumps` would raise before that decision ran.
    decision: dict = json.loads(
        flexweek_engine.session_focus_restore_decision(
            plain(
                {
                    "saved": saved,
                    "assignments": assignments,
                    "blocks": blocks,
                    "prefs": prefs,
                    "now_ms": now_ms,
                }
            )
        )
    )
    return decision


def focus_spotify_decision(prefs: dict | None, link: str) -> dict:
    """skip, say (no link), or open with the link."""
    decision: dict = _decide("focus_spotify_decision", prefs=prefs, link=link)
    return decision


def focus_spotify_open_failed() -> str:
    return str(_decide("focus_spotify_open_failed"))


def start_allowed(signed_in: bool, busy: bool, focus_busy: bool) -> bool:
    return bool(_decide("start_allowed", signed_in=signed_in, busy=busy, focus_busy=focus_busy))


def toggle_pause_decision(state: dict | None, *, focus_busy: bool, busy: bool, now_ms: int) -> dict:
    decision: dict = _decide(
        "toggle_pause_decision", focus=state, focus_busy=focus_busy, busy=busy, now_ms=now_ms
    )
    return decision


def end_early_decision(state: dict | None, week_start: str, prefs: dict | None, now_ms: int) -> dict:
    decision: dict = _decide(
        "end_early_decision", focus=state, week_start=week_start, prefs=prefs, now_ms=now_ms
    )
    return decision


def credit_enqueue_decision(
    state: dict | None, *, prefs: dict | None, minutes: int | None, finished: bool, busy: bool
) -> dict:
    decision: dict = _decide(
        "credit_enqueue_decision",
        focus=state,
        prefs=prefs,
        minutes=minutes,
        finished=finished,
        busy=busy,
    )
    return decision


def apply_credit_blocks(blocks: list[dict], to: str, updated: dict) -> dict:
    applied: dict = _decide("apply_credit_blocks", blocks=blocks, to=to, updated=updated)
    return applied


def apply_auto_complete_blocks(blocks: list[dict], done: dict | None) -> dict:
    applied: dict = _decide("apply_auto_complete_blocks", blocks=blocks, done=done)
    return applied


def split_held(
    notices: list[dict], state: dict | None, prefs: dict | None, material_owns: bool
) -> dict:
    split: dict = _decide(
        "split_held", notices=notices, focus=state, prefs=prefs, material_owns=material_owns
    )
    return split


def release_held(held: list[dict], state: dict | None, prefs: dict | None, material_owns: bool) -> bool:
    return bool(
        _decide("release_held", held=held, focus=state, prefs=prefs, material_owns=material_owns)
    )


def finish_focused_plan(
    state: dict | None,
    *,
    busy: bool,
    focus_busy: bool,
    week_start: str,
    blocks: list[dict],
    assignments: dict,
) -> dict:
    plan: dict = _decide(
        "finish_focused_plan",
        focus=state,
        busy=busy,
        focus_busy=focus_busy,
        week_start=week_start,
        blocks=blocks,
        assignments=assignments,
    )
    return plan


def finish_after_load(
    *,
    waiting: bool,
    pending: str | None,
    load_ok: bool,
    state: dict | None,
    busy: bool,
    focus_busy: bool,
    week_start: str,
    blocks: list[dict],
    assignments: dict,
) -> dict:
    plan: dict = _decide(
        "finish_after_load",
        waiting=waiting,
        pending=pending,
        load_ok=load_ok,
        focus=state,
        busy=busy,
        focus_busy=focus_busy,
        week_start=week_start,
        blocks=blocks,
        assignments=assignments,
    )
    return plan


def finish_intent_on_request(*, waiting: bool, pending: str | None, requested: str | None) -> str:
    return str(
        _decide(
            "finish_intent_on_request", waiting=waiting, pending=pending, requested=requested
        )
    )


def restart_finished_plan(
    state: dict | None, *, busy: bool, focus_busy: bool, prefs: dict | None, now_ms: int
) -> dict:
    plan: dict = _decide(
        "restart_finished_plan",
        focus=state,
        busy=busy,
        focus_busy=focus_busy,
        prefs=prefs,
        now_ms=now_ms,
    )
    return plan


def add_focus_time_plan(
    state: dict | None,
    *,
    busy: bool,
    focus_busy: bool,
    assignments: dict,
    minutes: int,
    prefs: dict | None,
    now_ms: int,
) -> dict:
    plan: dict = _decide(
        "add_focus_time_plan",
        focus=state,
        busy=busy,
        focus_busy=focus_busy,
        assignments=assignments,
        minutes=minutes,
        prefs=prefs,
        now_ms=now_ms,
    )
    return plan


def take_break_plan(state: dict | None, *, focus_busy: bool, prefs: dict | None, now_ms: int) -> dict:
    plan: dict = _decide(
        "take_break_plan", focus=state, focus_busy=focus_busy, prefs=prefs, now_ms=now_ms
    )
    return plan
