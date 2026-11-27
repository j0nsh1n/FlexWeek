"""desktop/native/controller.py holds no session decision the engine does not already own.

The same scan as test_wrappers_hold_no_engine_logic.py flags a method. Each flagged method is named
here with why it stays in Python: a Qt signal or timer, the request pipe, a file, the clock, or a
host the window hands in. A method that is not named has to be a thin forwarder.
"""

from __future__ import annotations

import ast
from pathlib import Path

from backend.tests.test_wrappers_hold_no_engine_logic import functions_of

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "desktop" / "native" / "controller.py"

# Outer methods only. A nested reply callback is covered by the method it sits in.
STAYS: dict[str, str] = {
    "_draft_field": "the writable flag picks the setter a fixture uses to edit one draft field",
    "NativeSession.__init__": "wires the Qt client, its signals, and the idle timer",
    "NativeSession._draft_view": "caches a draft field and copies the three lists fixtures edit in place",
    "NativeSession._accept_draft_versions": "drops a cached draft when the Rust session's version moved",
    "NativeSession._flush_fixture_drafts": "writes the edits a fixture made in place back before the next draft command",
    "NativeSession._send_week_effect": "sends one week-effect request and ignores a reply for an older ticket",
    "NativeSession._alive": "a late reply is ignored once a newer request took the ticket",
    "NativeSession._went_idle": "emits busy and arms the idle timer when a credit or a refollow is waiting",
    "NativeSession._credit_when_free": "runs the waiting focus credit only once the request has gone idle",
    "NativeSession.setup_work_windows": "None stays None on the way into and out of the setup queue",
    "NativeSession._drop_other_setup": "a different account does not keep the previous account's unsent setup",
    "NativeSession._clear_local": "signs the memory out and bumps the view tickets so a late reply is ignored",
    "NativeSession.today_iso": "reads the clock the engine stays pure of, as a calendar day",
    "NativeSession._view_world": "packs the signed-in account into the view command, or leaves it out",
    "NativeSession._view_answered": "applies a view reply onto the Qt signals",
    "NativeSession._keep_session": "writes the kept-session file when the student asked to stay signed in",
    "NativeSession.resume": "reads the kept-session file at launch and starts the resume flow",
    "NativeSession._told": "applies an account-flow reply onto the Qt signals",
    "NativeSession.logout": "forgets the kept-session file, then applies the logout reply",
    "NativeSession.load_week": "skips a load while signed out or busy, then requests the week",
    "NativeSession._week_read_failed": "puts the week-load failure on the Qt status line",
    "NativeSession._apply_saved_steps": "applies a save reply's steps and emits the Qt signals they name",
    "NativeSession._sync_service": "the phone-sync host the window handed in, or nothing when it is missing",
    "NativeSession.begin_pairing": "starts pairing on that host",
    "NativeSession._touch": "marks the draft dirty and emits week_changed",
    "NativeSession.add_homework": "applies the engine's homework edit, including the sessions it pinned",
    "NativeSession._time_step": "the drag step the hand-move request passes in, from the open preferences",
    "NativeSession.place_block": "holds a hand move while a save is in flight, then emits hand_placed",
    "NativeSession.keep_setup": "queues the one setup write still waiting",
    "NativeSession.flush_setup": "dispatches the next queued setup step to preferences, study hours, or the week's save",
    "NativeSession._fixed_copy_rows": "makes a fresh id for each block of the week being copied, or none when it has no blocks",
    "NativeSession.copy_last_week_fixed_rows": "fetches last week, then offers the engine's fixed-row copy",
    "NativeSession.move_to_date": "requests each week a move crosses, then commits the engine's batch",
    "NativeSession._block_on_week": "None from a week read stays None on the way into the move",
    "NativeSession._commit_move_to_date": "applies the engine's move batch and says when it refused",
    "NativeSession.delete_homework": "requests the delete and applies the reply for this ticket only",
    "NativeSession.save": "skips a save while signed out, in a conflict, or busy, then sends it with two fresh ids",
    "NativeSession._post_pending": "sends the next queued save and applies the reply for this ticket",
    "NativeSession.retry_save": "sends again only when a refused save is still waiting",
    "NativeSession.solve": "asks the engine to plan, then fetches the earlier week that request names",
    "NativeSession._dump_blocks": "None blocks stay the open week's on the way into a request",
    "NativeSession._fetch_weeks": "ignores a stale weeks reply and keeps an empty list when the body omits them",
    "NativeSession._fetch_routines": "ignores a stale routines reply and keeps an empty list when the body omits them",
    "NativeSession._clock_now": "reads the clock the engine stays pure of",
    "NativeSession._homework_counts": "the open week stands in when the caller passes no blocks or homework",
    "NativeSession.done_minutes_for": "a homework not saved yet has done nothing",
    "NativeSession.paste_destination": "reads the clock for where a paste lands",
    "NativeSession.copy_block": "skips the status line when the caller asked for a silent copy",
    "NativeSession.copy_selected": "says the engine's refusal, otherwise keeps the copied selection",
    "NativeSession.copy_day": "says the engine's refusal, otherwise keeps the copied day",
    "NativeSession.paste_proposals": "says the engine's refusal, otherwise builds the paste preview",
    "NativeSession.duplicate_selected": "says the engine's refusal, otherwise builds the duplicate preview",
    "NativeSession.confirm_preview": "applies the preview only while it is still the one on screen",
    "NativeSession._commit_groups": "requests each week a multi-week edit touches, then commits the engine's batch",
    "NativeSession.save_routine": "says the engine's refusal, otherwise sends the routine",
    "NativeSession.delete_routine": "says the engine's refusal, otherwise sends the delete",
    "NativeSession.week_blocks": "the open week is already here; another week is fetched",
    "NativeSession.apply_routine_rows": "says the engine's refusal, otherwise applies the rows",
    "NativeSession.apply_routine": "prepares the routine with the signed-in account and applies the engine's rows",
    "NativeSession.plan_unfinished": "stamps the clock and says the engine's refusal before planning",
    "NativeSession.plan_left": "does not plan while a save or a conflict is in the way",
    "NativeSession.did_these": "completes each homework the engine named, then saves",
    "NativeSession.recover_missed": "sends the recover request the engine built",
    "NativeSession.preview_running_late": "fetches the base plan, then the late one, for this ticket only",
    "NativeSession.accept_running_late": "applies the engine's late plan, or says its refusal",
    "NativeSession.preview_spread": "shows the spread preview for this ticket only",
    "NativeSession.confirm_spread": "saves only when the preview is still the one shown",
    "NativeSession.save_availability": "sends the study hours the engine accepted",
    "NativeSession.focus_tasks": "reads the clock for the focus list",
    "NativeSession._reset_focus": "writes the cleared timer unless the caller said not to persist it",
    "NativeSession._restore_focus": "puts a saved timer back on the Qt signals",
    "NativeSession.quick_focus_offer": "reads the clock for the quick-focus offer",
    "NativeSession.start_focus": "starts the timer, or asks to replace the one on screen",
    "NativeSession._open_focus_spotify": "opens Spotify in the OS, which the engine does not do",
    "NativeSession.toggle_focus_pause": "applies the engine's pause or resume and emits it",
    "NativeSession.tick_focus": "applies the engine's tick and emits it",
    "NativeSession.advance_focus": "applies the engine's next phase and emits it",
    "NativeSession.credit_focus_session": "queues the credit while a save would wipe it",
    "NativeSession._credit_waiting_sessions": "applies the queued credits once the save has landed",
    "NativeSession._credit_session": "writes the credited homework the engine named, or skips it",
    "NativeSession._material_focus_rules": "asks the window whether Material owns the surface",
    "NativeSession.finish_focused_homework": "loads the timer's week first when it is not the open one",
    "NativeSession._finish_loaded_focus": "finishes only if that load is the one Mark finished asked for",
    "NativeSession.restart_finished_focus": "starts the engine's new session and opens its Spotify link",
    "NativeSession.add_focus_time": "applies the minutes the engine added to the timer",
    "NativeSession.take_focus_break": "applies the break the engine started",
    "NativeSession._request_today_reminders": "asks for today's blocks and ignores a stale reply",
    "NativeSession._emit_cached_today_reminders": "emits the reminder cards already fetched",
    "NativeSession.check_alerts": "rings due alarms on the Qt signal and asks for today's blocks",
    "NativeSession.finish_alarm": "passes the clock when snoozing, then shows the next alarm",
    "NativeSession._resume_preferences": "flushes a queued settings save once the session is idle",
    "NativeSession._flush_preferences": "sends the next settings save and applies the reply for this ticket",
    "NativeSession.preview_timer_split": "shows the engine's split, or its refusal",
    "NativeSession.delete_account": "a signed-out window sends no owner with the delete",
    "NativeSession.create_restore_point": "says the engine's refusal, otherwise sends the backup and merges the reply",
    "NativeSession.preview_restore_point": "shows the restore preview for this ticket only",
    "NativeSession.apply_restore_point": "says the engine's guard, otherwise restores and reloads",
    "NativeSession.export_account": "says the engine's refusal, otherwise requests the snapshot",
    "NativeSession.preview_account_import": "says the engine's refusal, otherwise requests the import preview",
    "NativeSession.apply_account_import": "says the engine's guard, otherwise imports and reloads",
    "NativeSession.import_week_file": "says the engine's refusal, otherwise applies the parsed file and saves",
}


def _defined(tree: ast.AST) -> set[str]:
    found: set[str] = set()

    def scan(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                scan(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.add(f"{prefix}{node.name}")

    if isinstance(tree, ast.Module):
        scan(tree.body, "")
    return found


def _flagged(tree: ast.AST) -> set[str]:
    return {problem.split(":", 1)[0] for problem in functions_of(tree, set())}


def test_controller_holds_no_session_logic() -> None:
    tree = ast.parse(CONTROLLER.read_text(encoding="utf-8"), filename=str(CONTROLLER))
    defined = _defined(tree)
    missing = sorted(name for name in STAYS if name not in defined)
    assert not missing, "STAYS names nothing in controller.py:\n" + "\n".join(missing)
    covered = [
        name
        for name in STAYS
        if any(name.startswith(f"{other}.") for other in STAYS if other != name)
    ]
    assert not covered, "a shorter prefix already covers:\n" + "\n".join(covered)
    flagged = _flagged(tree)
    unused = sorted(
        name
        for name in STAYS
        if not any(item == name or item.startswith(f"{name}.") for item in flagged)
    )
    assert not unused, "nothing flagged needs these:\n" + "\n".join(unused)
    blank = sorted(name for name, why in STAYS.items() if not why.strip())
    assert not blank, "say why these stay:\n" + "\n".join(blank)
    problems = functions_of(tree, set(STAYS))
    assert not problems, "\n".join(problems)
