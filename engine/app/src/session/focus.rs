//! The focus timer's decisions (P4 group 6; the focus block of `desktop/native/controller.py`). Each
//! function takes one JSON object of arguments and answers one JSON value, so the Python window and a
//! Rust one ask the same way. The session keeps the timer, the credits waiting and the held notices, and
//! applies what comes back; the timer's own arithmetic stays in the engine (`desk::focus`). The clock and
//! the preferences are always passed in.

use std::collections::BTreeMap;

use flexweek_engine::desk::{focus as timer, grid};
use flexweek_engine::time::week_start_on;
use flexweek_engine::{EngineError, EngineResult};
use serde_json::{Value, json};

const PLACE_FIRST: &str = "Give an unfinished homework session a time before starting focus.";
const HOMEWORK_NOT_LOADED: &str = "This homework did not load, so the focus time was not counted. \
Reload the week and try again.";
const TIMER_STOPPED: &str =
    "Schedule restored. The focus timer stopped because its homework session no longer exists.";
const BREAK_ENDED: &str = "The break ended while FlexWeek was closed. Press Resume to focus again.";
const SPOTIFY_MISSING: &str = "Focus started without Spotify. Add a link under Settings > Alerts.";
const SPOTIFY_FAILED: &str = "Focus started without Spotify because the app didn't open.";
const MORE_TIME: &str = "Choose how much more time it needs.";

/// A shared null, since a borrowed `Value::Null` temporary would not live long enough.
static NULL: Value = Value::Null;

/// Python's truth of a value, which the session's rules lean on (`state.get("x") or ...`).
fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(flag) => *flag,
        Value::Number(number) => number.as_f64().is_some_and(|found| found != 0.0),
        Value::String(text) => !text.is_empty(),
        Value::Array(items) => !items.is_empty(),
        Value::Object(fields) => !fields.is_empty(),
    }
}

/// `int(value or 0)`.
fn whole(value: &Value) -> i64 {
    match value {
        Value::Number(number) => number
            .as_i64()
            .or_else(|| number.as_f64().map(|float| float as i64))
            .unwrap_or(0),
        _ => 0,
    }
}

fn text_of(value: &Value) -> String {
    match value {
        Value::String(text) => text.clone(),
        other => other.to_string(),
    }
}

fn now_of(args: &Value) -> EngineResult<i64> {
    args["now_ms"]
        .as_i64()
        .ok_or_else(|| EngineError::value("now_ms is a whole number"))
}

fn object_of(state: &Value) -> EngineResult<Value> {
    if state.is_object() {
        Ok(state.clone())
    } else {
        Err(EngineError::value("the focus timer is an object"))
    }
}

fn find_by_id<'a>(items: &'a Value, id: &Value) -> Option<&'a Value> {
    if id.is_null() {
        return None;
    }
    items.as_array()?.iter().find(|item| item["id"] == *id)
}

fn is_whole(value: &Value) -> bool {
    value.is_i64() || value.is_u64()
}

fn notice(title: &str, body: Value, tone: &str) -> Value {
    json!({ "title": title, "body": body, "kind": "focus", "tone": tone })
}

/// Starting the homework (or block) whose timer is already going is going back to it, not a replace.
fn same_timer(running: &Value, target: &Value) -> bool {
    if running["phase"] == "ended" {
        return false;
    }
    let homework = &target["assignmentId"];
    if truthy(homework) {
        return *homework == running["assignmentId"];
    }
    let block = &target["blockId"];
    truthy(block) && *block == running["blockId"]
}

/// What a start would time. `{"target": {...}}`, or `{"refuse": words}` when there is nothing to start.
/// Arguments: `block_id`, `day`, `quick`, `week_start`, `assignments` (by id), `blocks`, `trace`,
/// `overdue` (ids of homework past its due time; only the title uses them).
pub fn start_target(args: &Value) -> EngineResult<Value> {
    let week = args["week_start"].clone();
    if truthy(&args["quick"]) {
        return Ok(json!({ "target": {
            "weekStart": week,
            "blockId": null,
            "assignmentId": null,
            "day": null,
            "start": null,
            "title": "Quick focus",
        }}));
    }
    let (block_id, day) = (&args["block_id"], &args["day"]);
    let homework = match block_id.as_str() {
        Some(id) if day.is_null() => args["assignments"].get(id),
        _ => None,
    };
    if let Some(assignment) = homework {
        let overdue = args["overdue"]
            .as_array()
            .is_some_and(|ids| ids.contains(block_id));
        let title = if overdue {
            json!(format!("{}, overdue", text_of(&assignment["title"])))
        } else {
            assignment["title"].clone()
        };
        return Ok(json!({ "target": {
            "weekStart": week,
            "blockId": null,
            "assignmentId": block_id,
            "day": null,
            "start": null,
            "title": title,
        }}));
    }
    let refused = || -> EngineResult<Value> { Ok(json!({ "refuse": PLACE_FIRST })) };
    let Some(block) = find_by_id(&args["blocks"], block_id) else {
        return refused();
    };
    if truthy(&block["completed"]) || block["pomodoro_role"] == "break" {
        return refused();
    }
    let mut placed = truthy(&block["start"]).then_some(block);
    if placed.is_none() && truthy(&args["trace"]) {
        let on_day = |item: &Value| {
            day.is_null()
                || item["days"]
                    .as_array()
                    .is_some_and(|days| days.contains(day))
        };
        placed = args["trace"]["placed"].as_array().and_then(|list| {
            list.iter()
                .find(|item| item["id"] == *block_id && on_day(item))
        });
    }
    let Some(placed) = placed.filter(|item| truthy(&item["start"])) else {
        return refused();
    };
    let first_day = placed["days"]
        .as_array()
        .and_then(|days| days.first())
        .cloned()
        .unwrap_or_else(|| day.clone());
    Ok(json!({ "target": {
        "weekStart": week,
        "blockId": block["id"],
        "assignmentId": block["assignment_id"],
        "day": first_day,
        "start": placed["start"],
        "title": block["title"],
    }}))
}

/// What a start does with the timer already going: `"same"` (go back to it), `"ask"` (the student must
/// agree to replace it) or `"begin"`. Arguments: `focus`, `target`, `replace`.
pub fn start_decision(args: &Value) -> EngineResult<Value> {
    let running = &args["focus"];
    let decision = if running.is_null() || truthy(&args["replace"]) {
        "begin"
    } else if same_timer(running, &args["target"]) {
        "same"
    } else {
        "ask"
    };
    Ok(json!(decision))
}

/// Whole minutes of the work session running or paused, which are credited only when it ends. A homework
/// is credited whichever week is open; a block, only from its own week. Arguments: `focus`, `week_start`,
/// `prefs`, `now_ms`.
pub fn elapsed_min(args: &Value) -> EngineResult<Value> {
    let state = &args["focus"];
    if state.is_null() || state["phase"] != "work" {
        return Ok(json!(0));
    }
    if !truthy(&state["assignmentId"]) && state["weekStart"] != args["week_start"] {
        return Ok(json!(0));
    }
    let now = now_of(args)?;
    let spent = timer::phase_total_ms(state, &args["prefs"])? - timer::remaining_ms(state, now)?;
    Ok(json!(
        i64::try_from(spent.max(0) / 60_000).unwrap_or(i64::MAX)
    ))
}

/// What one tick of the clock means: `credit` (credits waited on a save, which is over, go in first) and
/// `action`, one of `"none"`, `"ended"` (the running phase ran out) and `"changed"` (still running).
/// Arguments: `focus`, `credits_waiting`, `busy`, `now_ms`.
pub fn tick_step(args: &Value) -> EngineResult<Value> {
    let credit = truthy(&args["credits_waiting"]) && !truthy(&args["busy"]);
    let state = &args["focus"];
    let action = if state.is_null() || !truthy(&state["running"]) {
        "none"
    } else if whole(&state["endsAt"]) <= now_of(args)? {
        "ended"
    } else {
        "changed"
    };
    Ok(json!({ "credit": credit, "action": action }))
}

/// Before a phase moves on: `go` says whether there is a timer to move, and `credit` whether the work
/// phase that just ended is credited first. The session credits, then asks for the plan with the timer
/// it holds by then, since a credit can end the timer. Arguments: `focus`, `focus_busy`, `completed`.
pub fn advance_begin(args: &Value) -> EngineResult<Value> {
    let state = &args["focus"];
    let go = !state.is_null() && !truthy(&args["focus_busy"]) && state["phase"] != "ended";
    let credit = go && state["phase"] == "work" && truthy(&args["completed"]);
    Ok(json!({ "go": go, "credit": credit }))
}

/// Where the timer goes next. `state` is the new timer, `alert` the notice to tell, and `alert_first`
/// says whether the notice goes out before the new timer is kept (a new phase) or after (the homework's
/// session finished). `cycles` is present when a work phase was left. Arguments: `focus`, `completed`,
/// `assignment_known` (the timer's homework is among the week's), `prefs`, `now_ms`.
pub fn advance_plan(args: &Value) -> EngineResult<Value> {
    let mut state = object_of(&args["focus"])?;
    let (prefs, now) = (&args["prefs"], now_of(args)?);
    let completed = truthy(&args["completed"]);
    if state["phase"] != "work" {
        return entered(&state, "work", prefs, now);
    }
    let cycles = whole(&state["cycles"])
        .checked_add(i64::from(completed))
        .ok_or_else(|| EngineError::value("cycles is too large"))?;
    state["cycles"] = json!(cycles);
    if completed && truthy(&state["assignmentId"]) && truthy(&args["assignment_known"]) {
        state["phase"] = json!("ended");
        state["running"] = json!(false);
        state["remainingMs"] = json!(0);
        let alert = notice("Focus session finished", state["title"].clone(), "soft");
        return Ok(json!({
            "state": state,
            "cycles": cycles,
            "alert": alert,
            "alert_first": false,
        }));
    }
    let mut plan = entered(&state, timer::break_phase(cycles, prefs)?, prefs, now)?;
    plan["cycles"] = json!(cycles);
    Ok(plan)
}

fn entered(state: &Value, phase: &str, prefs: &Value, now: i64) -> EngineResult<Value> {
    let moved = timer::set_phase(state, &json!(phase), prefs, now)?;
    let label = match phase {
        "work" => "Focus session",
        "break" => "Break",
        "long_break" => "Long break",
        "ended" => "Session finished",
        _ => "Focus",
    };
    let body = if truthy(&moved["title"]) {
        moved["title"].clone()
    } else {
        json!("")
    };
    // Bright going into work, soft going into a break, as the web's setFocusPhase does.
    let tone = if phase == "work" { "bright" } else { "soft" };
    Ok(json!({ "state": moved, "alert": notice(label, body, tone), "alert_first": true }))
}

/// Moves to a phase and names the notice that announces it. Arguments: `state`, `phase`, `prefs`, `now_ms`.
pub fn enter_phase(args: &Value) -> EngineResult<Value> {
    let phase = args["phase"]
        .as_str()
        .ok_or_else(|| EngineError::value("phase is text"))?;
    entered(&args["state"], phase, &args["prefs"], now_of(args)?)
}

/// Where a credit goes: `{"to": "assignment" | "block", "updated": ...}` (the homework or block with the
/// session and minutes added), `{"say": words}` (a homework that is not loaded) or `{"skip": true}`.
/// Arguments: `state` (the timer as it was when the phase ended), `week_start`, `assignments` (by id),
/// `blocks`, `work_min`.
pub fn credit_plan(args: &Value) -> EngineResult<Value> {
    let state = &args["state"];
    let work_min = args["work_min"]
        .as_i64()
        .ok_or_else(|| EngineError::value("work_min is a whole number"))?;
    if truthy(&state["assignmentId"]) {
        let assignment = state["assignmentId"]
            .as_str()
            .and_then(|id| args["assignments"].get(id))
            .unwrap_or(&NULL);
        return Ok(
            match timer::credit_target(state, assignment, &Value::Null, work_min)? {
                Some(updated) => json!({ "to": "assignment", "updated": updated }),
                None => json!({ "say": HOMEWORK_NOT_LOADED }),
            },
        );
    }
    if state["weekStart"] != args["week_start"] {
        return Ok(json!({ "skip": true }));
    }
    let block = find_by_id(&args["blocks"], &state["blockId"]).unwrap_or(&NULL);
    Ok(
        match timer::credit_target(state, &Value::Null, block, work_min)? {
            Some(updated) => json!({ "to": "block", "updated": updated }),
            None => json!({ "skip": true }),
        },
    )
}

/// What finishing a session completes, when Auto-complete is on: `block` (`{id, start, completed_day}` to
/// mark Done; nothing else is) and `complete_homework` (the homework's id, only when that was its last
/// unfinished work session). Arguments: `state`, `prefs`, `material_owns`, `week_start`, `assignments`
/// (by id), `blocks` (as they are after the credit).
pub fn auto_complete_plan(args: &Value) -> EngineResult<Value> {
    let nothing = json!({ "block": null, "complete_homework": null });
    let (state, prefs) = (&args["state"], &args["prefs"]);
    if !truthy(&args["material_owns"]) || !truthy(&prefs["focus_auto_complete"]) {
        return Ok(nothing);
    }
    let block = if truthy(&state["blockId"]) && state["weekStart"] == args["week_start"] {
        find_by_id(&args["blocks"], &state["blockId"])
    } else {
        None
    };
    let day = &state["day"];
    let marked = block.filter(|item| {
        !truthy(&item["completed"])
            && item["kind"] == "flexible"
            && truthy(&state["start"])
            && is_whole(day)
            && item["days"]
                .as_array()
                .is_some_and(|days| days.contains(day))
    });
    let done = marked_block(marked, state);
    let own = &state["assignmentId"];
    let assignment_id = if truthy(own) {
        own
    } else {
        block.map_or(&NULL, |item| &item["assignment_id"])
    };
    let open = assignment_id
        .as_str()
        .filter(|id| !id.is_empty())
        .filter(|id| {
            args["assignments"]
                .get(*id)
                .is_some_and(|item| !item.is_null() && !truthy(&item["completed"]))
        });
    let Some(id) = open else {
        return Ok(json!({ "block": done, "complete_homework": null }));
    };
    // The block marked Done above no longer counts as left.
    let left = args["blocks"].as_array().is_some_and(|items| {
        items.iter().any(|item| {
            item["assignment_id"] == *assignment_id
                && !truthy(&item["completed"])
                && item["pomodoro_role"] != "break"
                && marked.is_none_or(|finished| item["id"] != finished["id"])
        })
    });
    let finished = if left { Value::Null } else { json!(id) };
    Ok(json!({ "block": done, "complete_homework": finished }))
}

fn marked_block(marked: Option<&Value>, state: &Value) -> Value {
    match marked {
        Some(item) => json!({
            "id": item["id"],
            "start": state["start"],
            "completed_day": state["day"],
        }),
        None => Value::Null,
    }
}

/// Whether focus holds reminders back: the Material screens own the rules, Auto-mute is on (it is, until
/// the student turns it off) and a work phase is under way, running or paused.
fn mutes(args: &Value) -> bool {
    let wanted = args["prefs"].get("focus_auto_mute").is_none_or(truthy);
    truthy(&args["material_owns"]) && wanted && args["focus"]["phase"] == "work"
}

/// Arguments: `focus`, `prefs`, `material_owns`.
pub fn mutes_alerts(args: &Value) -> EngineResult<Value> {
    Ok(json!(mutes(args)))
}

/// Which notices to keep back, as a flag for each in order: while focus mutes, every one that is not
/// about focus. Focus's own always show. Arguments: `kinds` (each notice's kind), `focus`, `prefs`,
/// `material_owns`.
pub fn hold_alerts(args: &Value) -> EngineResult<Value> {
    let muting = mutes(args);
    let kinds = args["kinds"].as_array().cloned().unwrap_or_default();
    let hold: Vec<bool> = kinds.iter().map(|kind| muting && kind != "focus").collect();
    Ok(json!({ "hold": hold }))
}

/// After a reload or a restore: whether the timer's block is gone, so the timer stops, and the words to
/// say if the restore is the one being announced. Arguments: `focus`, `week_start`, `blocks`, `announce`.
pub fn drop_missing(args: &Value) -> EngineResult<Value> {
    let state = &args["focus"];
    let keep = json!({ "drop": false, "say": null });
    if state.is_null() || !truthy(&state["blockId"]) || state["weekStart"] != args["week_start"] {
        return Ok(keep);
    }
    let exists = args["blocks"].as_array().is_some_and(|items| {
        items.iter().any(|item| {
            item["id"] == state["blockId"]
                && (!truthy(&state["assignmentId"])
                    || item["assignment_id"] == state["assignmentId"])
        })
    });
    if exists {
        return Ok(keep);
    }
    let say = if truthy(&args["announce"]) {
        json!(TIMER_STOPPED)
    } else {
        Value::Null
    };
    Ok(json!({ "drop": true, "say": say }))
}

/// The timer names its week and day: when the first day of the week changes, keep its date, in the week
/// from the new first day. `{"state": moved}`, or `{"state": null}` when there is no timer to move.
/// Arguments: `focus`, `first_weekday` (0 Monday to 6 Sunday).
pub fn rebase(args: &Value) -> EngineResult<Value> {
    let state = &args["focus"];
    if state.is_null() || !truthy(&state["weekStart"]) {
        return Ok(json!({ "state": null }));
    }
    let mut moved = object_of(state)?;
    let start = state["weekStart"]
        .as_str()
        .ok_or_else(|| EngineError::value("weekStart is text"))?;
    let first = args["first_weekday"]
        .as_u64()
        .and_then(|day| u32::try_from(day).ok())
        .ok_or_else(|| EngineError::value("first_weekday is a whole number"))?;
    let day = &state["day"];
    let anchor = if is_whole(day) {
        grid::date_for_day(start, day)?
    } else {
        start.to_string()
    };
    let week = week_start_on(&anchor, first)?;
    moved["weekStart"] = json!(week);
    if is_whole(day) {
        moved["day"] = json!(grid::due_day_of(&json!(anchor), &week)?);
    }
    Ok(json!({ "state": moved }))
}

/// `isinstance(value, int)`, and a bool is one.
fn py_whole(value: &Value) -> Option<i64> {
    match value {
        Value::Bool(flag) => Some(i64::from(*flag)),
        Value::Number(number) if !number.to_string().contains(['.', 'e', 'E']) => number.as_i64(),
        _ => None,
    }
}

fn py_is_int(value: &Value) -> bool {
    py_whole(value).is_some()
}

/// `int(value or 0)`. A truthy value that is not a whole number is refused.
fn whole_or_zero(value: &Value) -> EngineResult<i64> {
    if !truthy(value) {
        return Ok(0);
    }
    py_whole(value).ok_or_else(|| EngineError::value("a whole number is required"))
}

fn json_int(value: i128) -> EngineResult<Value> {
    i64::try_from(value)
        .map(|number| json!(number))
        .map_err(|_| EngineError::overflow("integer too large for the engine"))
}

fn field_or_null(state: &Value, key: &str) -> Value {
    state.get(key).cloned().unwrap_or(Value::Null)
}

/// The blocks the week shows: with no trace, the locked blocks and the flexible ones that have a
/// time; with a trace, each placed row over the block it names (days and start from the placement).
/// Arguments: `blocks`, `trace`.
pub fn scheduled_blocks(args: &Value) -> EngineResult<Value> {
    let blocks = args["blocks"]
        .as_array()
        .ok_or_else(|| EngineError::value("blocks is a list"))?;
    if !truthy(&args["trace"]) {
        let shown: Vec<&Value> = blocks
            .iter()
            .filter(|block| {
                block["kind"] == "locked"
                    || (block["kind"] == "flexible" && truthy(&block["start"]))
            })
            .collect();
        return Ok(json!(shown));
    }
    // A number or a list has no placements. Python's `trace.get` refused it; returning
    // nothing would hide that the trace was the wrong shape.
    if !args["trace"].is_object() {
        return Err(EngineError::value("trace is an object"));
    }
    let placed = match args["trace"].get("placed") {
        None | Some(Value::Null) => &NULL,
        Some(value) => value,
    };
    let placed: &[Value] = if truthy(placed) {
        placed
            .as_array()
            .ok_or_else(|| EngineError::value("placed is a list"))?
    } else {
        &[]
    };
    let mut merged = Vec::with_capacity(placed.len());
    for row in placed {
        let id = &row["id"];
        let source = blocks.iter().rev().find(|block| block["id"] == *id);
        let Some(source) = source else {
            merged.push(row.clone());
            continue;
        };
        let mut item = source.clone();
        item["days"] = listed_days(&row["days"], &source["days"])?;
        item["start"] = field_or_null(row, "start");
        merged.push(item);
    }
    Ok(json!(merged))
}

/// `placed.days or source.days or []`, as a new list.
fn listed_days(placed: &Value, source: &Value) -> EngineResult<Value> {
    let chosen = if truthy(placed) {
        placed
    } else if truthy(source) {
        source
    } else {
        &NULL
    };
    match chosen {
        Value::Null => Ok(json!([])),
        Value::Array(items) => Ok(json!(items)),
        _ => Err(EngineError::value("days is a list")),
    }
}

/// What a saved timer becomes when the week opens. `drop` forgets the save. `active` keeps `state`.
/// `advance_work` keeps it and the session then completes the work phase. `paused_work` is a break
/// that ran out while FlexWeek was closed: `state` is the restored break, `paused` is that timer
/// put back on work and paused, and `say` is the sentence the student sees.
/// Arguments: `saved`, `assignments`, `blocks`, `prefs`, `now_ms`.
pub fn restore_decision(args: &Value) -> EngineResult<Value> {
    // `plain` writes NaN as a one-key object and a lone surrogate as a private-use character.
    // Reading either as a timer would raise; a save that cannot be read is forgotten.
    if saved_is_corrupt(&args["saved"]) {
        return Ok(json!({ "action": "drop" }));
    }
    let now = now_of(args)?;
    let Some(mut state) =
        timer::restore_state(&args["saved"], &args["assignments"], &args["blocks"], now)?
    else {
        return Ok(json!({ "action": "drop" }));
    };
    // Crediting happens after this answer. A session that is not this homework's must not
    // be counted first and dropped afterwards.
    if !session_belongs_to_assignment(&state, &args["blocks"]) {
        return Ok(json!({ "action": "drop" }));
    }
    let expired = state.get("expired").is_some_and(truthy);
    if let Some(fields) = state.as_object_mut() {
        fields.shift_remove("expired");
    }
    if !expired {
        return Ok(json!({ "action": "active", "state": state }));
    }
    if state["phase"] == "work" {
        return Ok(json!({ "action": "advance_work", "state": state }));
    }
    // An ended timer is over. A past end is not a break that ran out while FlexWeek was closed.
    if state["phase"] == "ended" {
        return Ok(json!({ "action": "active", "state": state }));
    }
    let mut paused = timer::set_phase(&state, &json!("work"), &args["prefs"], now)?;
    paused["running"] = json!(false);
    let remaining = timer::remaining_ms(&paused, now)?;
    paused["remainingMs"] = json_int(remaining)?;
    Ok(json!({
        "action": "paused_work",
        "state": state,
        "paused": paused,
        "say": BREAK_ENDED,
    }))
}

/// Whether starting focus may open Spotify. `skip`, `say` (no link), or `open` with the link.
/// Arguments: `prefs`, `link`.
pub fn focus_spotify_decision(args: &Value) -> EngineResult<Value> {
    let prefs = &args["prefs"];
    // None is no preferences. A truthy value that is not a dict has no `get`, so it is refused
    // rather than treated as "not Spotify".
    if truthy(prefs) && !prefs.is_object() {
        return Err(EngineError::value("prefs is an object"));
    }
    let audio = if prefs.is_object() {
        prefs.get("focus_audio").unwrap_or(&NULL)
    } else {
        &NULL
    };
    if audio != "spotify" {
        return Ok(json!({ "action": "skip" }));
    }
    if !truthy(&args["link"]) {
        return Ok(json!({ "action": "say", "say": SPOTIFY_MISSING }));
    }
    Ok(json!({ "action": "open", "link": args["link"] }))
}

/// The sentence when the Spotify app does not open. Focus still carries on.
pub fn focus_spotify_open_failed(_args: &Value) -> EngineResult<Value> {
    Ok(json!(SPOTIFY_FAILED))
}

/// A signed-in session that is not busy and not already moving the timer may start one.
/// Arguments: `signed_in`, `busy`, `focus_busy`.
pub fn start_allowed(args: &Value) -> EngineResult<Value> {
    let allowed =
        truthy(&args["signed_in"]) && !truthy(&args["busy"]) && !truthy(&args["focus_busy"]);
    Ok(json!(allowed))
}

/// Pause or resume, or `ignore` when there is nothing to toggle.
/// Arguments: `focus`, `focus_busy`, `busy`, `now_ms`.
pub fn toggle_pause_decision(args: &Value) -> EngineResult<Value> {
    let state = &args["focus"];
    if state.is_null()
        || truthy(&args["focus_busy"])
        || truthy(&args["busy"])
        || state["phase"] == "ended"
    {
        return Ok(json!({ "action": "ignore" }));
    }
    let paused = timer::pause_state(state, now_of(args)?)?;
    Ok(json!({ "action": "apply", "state": paused }))
}

/// Whether End session credits the minutes already worked. `minutes` is that count; `credit` is
/// whether it is at least one. Arguments: `focus`, `week_start`, `prefs`, `now_ms`.
pub fn end_early_decision(args: &Value) -> EngineResult<Value> {
    let minutes = elapsed_min(args)?;
    let credit = minutes.as_i64().is_some_and(|count| count > 0);
    Ok(json!({ "credit": credit, "minutes": minutes }))
}

/// Where one finished phase's minutes go while a save may be replacing the homework: `ignore`,
/// `enqueue` (keep the credit until the save lands) or `apply` now.
/// Arguments: `focus`, `prefs`, `minutes` (null uses the phase's own length), `finished`, `busy`.
pub fn credit_enqueue_decision(args: &Value) -> EngineResult<Value> {
    let state = &args["focus"];
    if state.is_null() || !(truthy(&state["blockId"]) || truthy(&state["assignmentId"])) {
        return Ok(json!({ "action": "ignore" }));
    }
    let work_min = if args["minutes"].is_null() {
        json_int(timer::work_minutes(state, &args["prefs"])?)?
    } else {
        json_int(
            args["minutes"]
                .as_i64()
                .ok_or_else(|| EngineError::value("minutes is a whole number"))?
                .into(),
        )?
    };
    let credit = json!({
        "state": state,
        "work_min": work_min,
        "finished": truthy(&args["finished"]),
    });
    let action = if truthy(&args["busy"]) {
        "enqueue"
    } else {
        "apply"
    };
    Ok(json!({ "action": action, "credit": credit }))
}

/// The credit written onto the open week: the homework, or the blocks with that one block replaced.
/// Arguments: `to` ("assignment" or "block"), `updated`, `blocks`.
pub fn apply_credit_blocks(args: &Value) -> EngineResult<Value> {
    if args["to"] == "assignment" {
        return Ok(json!({ "homework": args["updated"], "blocks": null }));
    }
    let updated = &args["updated"];
    let mut blocks = args["blocks"]
        .as_array()
        .cloned()
        .ok_or_else(|| EngineError::value("blocks is a list"))?;
    for block in &mut blocks {
        if block["id"] == updated["id"] {
            *block = updated.clone();
        }
    }
    Ok(json!({ "homework": null, "blocks": blocks }))
}

/// The blocks after Auto-complete marks the one session Done. `changed` is false when there is
/// nothing to mark. Arguments: `blocks`, `done` (`{id, start, completed_day}` or null).
pub fn apply_auto_complete_blocks(args: &Value) -> EngineResult<Value> {
    if args["done"].is_null() {
        return Ok(json!({ "changed": false, "blocks": null }));
    }
    let done = &args["done"];
    let mut blocks = args["blocks"]
        .as_array()
        .cloned()
        .ok_or_else(|| EngineError::value("blocks is a list"))?;
    for block in &mut blocks {
        if block["id"] == done["id"] {
            block["start"] = done["start"].clone();
            block["completed"] = json!(true);
            block["completed_day"] = done["completed_day"].clone();
        }
    }
    Ok(json!({ "changed": true, "blocks": blocks }))
}

/// Split notices into those focus keeps back and those to show now.
/// Arguments: `notices`, `focus`, `prefs`, `material_owns`.
pub fn split_held(args: &Value) -> EngineResult<Value> {
    // A string would be walked one character at a time and then fail. An empty split would hide that.
    let notices = args["notices"]
        .as_array()
        .cloned()
        .ok_or_else(|| EngineError::value("notices is a list"))?;
    let muting = mutes(args);
    let mut show = Vec::new();
    let mut hold = Vec::new();
    for item in notices {
        let kind = item.get("kind").unwrap_or(&NULL);
        if muting && kind != "focus" {
            hold.push(item);
        } else {
            show.push(item);
        }
    }
    Ok(json!({ "show": show, "hold": hold }))
}

/// Whether the notices kept during focus can be shown now.
/// Arguments: `held` (the kept list), `focus`, `prefs`, `material_owns`.
pub fn release_held(args: &Value) -> EngineResult<Value> {
    Ok(json!(truthy(&args["held"]) && !mutes(args)))
}

/// A private-use character in the range `plain` uses for a lone surrogate.
fn mapped_surrogate(ch: char) -> bool {
    ('\u{10F800}'..='\u{10FFFF}').contains(&ch)
}

/// NaN, infinity, or a lone surrogate anywhere in a saved timer. Those are not values a timer holds.
fn saved_is_corrupt(value: &Value) -> bool {
    if flexweek_engine::stored::nonfinite(value).is_some() {
        return true;
    }
    match value {
        Value::String(text) => text.chars().any(mapped_surrogate),
        Value::Array(items) => items.iter().any(saved_is_corrupt),
        Value::Object(map) => map
            .iter()
            .any(|(key, item)| key.chars().any(mapped_surrogate) || saved_is_corrupt(item)),
        _ => false,
    }
}

fn ended_blocked(state: &Value, busy: bool, focus_busy: bool, check_busy: bool) -> bool {
    state.is_null() || state["phase"] != "ended" || focus_busy || (check_busy && busy)
}

fn holds_day(block: &Value, day: &Value) -> EngineResult<bool> {
    if !py_is_int(day) {
        return Ok(false);
    }
    let days = block.get("days").unwrap_or(&NULL);
    let days = if truthy(days) { days } else { &NULL };
    match days {
        Value::Null => Ok(false),
        Value::Array(items) => Ok(items.iter().any(|item| py_whole(item) == py_whole(day))),
        _ => Err(EngineError::value("days is a list")),
    }
}

/// The open week's blocks after Mark finished writes the session it ran, when that session is a
/// flexible block of this week.
fn finished_blocks(blocks: &Value, state: &Value) -> EngineResult<Value> {
    let mut blocks = blocks
        .as_array()
        .cloned()
        .ok_or_else(|| EngineError::value("blocks is a list"))?;
    let Some(index) = blocks
        .iter()
        .position(|item| item["id"] == state["blockId"])
    else {
        return Ok(json!(blocks));
    };
    if blocks[index]["kind"] != "flexible" {
        return Ok(json!(blocks));
    }
    if truthy(&state["start"]) && holds_day(&blocks[index], &state["day"])? {
        // A finished day is only valid on a finished block. The homework check refuses a
        // finished day written onto a session that is still open.
        blocks[index]["start"] = state["start"].clone();
        blocks[index]["completed"] = json!(true);
        blocks[index]["completed_day"] = state["day"].clone();
    } else if !py_is_int(&blocks[index]["completed_day"]) {
        blocks[index]["start"] = Value::Null;
    }
    Ok(json!(blocks))
}

fn assignment_known(assignments: &Value, id: &Value) -> bool {
    let Some(key) = id.as_str().filter(|text| !text.is_empty()) else {
        return false;
    };
    assignments
        .as_object()
        .is_some_and(|map| map.contains_key(key))
}

/// Mark finished on a timer that has ended. `ignore` does nothing. `finish` is the block list and
/// the homework to complete, on the week already open. `load_then_finish` names the timer's week:
/// one press opens it, and the finish waits until that load lands (`finish_after_load`).
/// Arguments: `focus`, `busy`, `focus_busy`, `week_start`, `blocks`, `assignments`.
pub fn finish_focused_plan(args: &Value) -> EngineResult<Value> {
    let state = &args["focus"];
    if ended_blocked(
        state,
        truthy(&args["busy"]),
        truthy(&args["focus_busy"]),
        true,
    ) {
        return Ok(json!({ "action": "ignore" }));
    }
    let assignment_id = &state["assignmentId"];
    if !assignment_known(&args["assignments"], assignment_id) {
        return Ok(json!({ "action": "ignore" }));
    }
    if state["weekStart"] != args["week_start"] {
        // Opening the week used to return before the homework was marked, so the student pressed
        // again. The press now waits for that week and finishes once, as it would have there.
        return Ok(json!({ "action": "load_then_finish", "week": state["weekStart"] }));
    }
    Ok(json!({
        "action": "finish",
        "blocks": finished_blocks(&args["blocks"], state)?,
        "assignment_id": assignment_id,
    }))
}

/// What a pending Mark finished does once a week load ends. `none` when nothing is waiting.
/// `drop` when the load failed, or the week that landed is not the timer's (the student went
/// elsewhere). Otherwise the same answer as pressing Mark finished on that week.
/// Arguments: `waiting`, `pending` (the week the press named), `load_ok`, and the same fields as
/// `finish_focused_plan` with `week_start` the week now open.
pub fn finish_after_load(args: &Value) -> EngineResult<Value> {
    if !truthy(&args["waiting"]) {
        return Ok(json!({ "action": "none" }));
    }
    if !truthy(&args["load_ok"]) || args["week_start"] != args["pending"] {
        return Ok(json!({ "action": "drop" }));
    }
    finish_focused_plan(args)
}

/// A navigation while Mark finished is waiting for its week. `keep` when this request is that
/// week (or nothing is waiting); `drop` when the student asked for a different week first.
/// Arguments: `waiting`, `pending`, `requested`.
pub fn finish_intent_on_request(args: &Value) -> EngineResult<Value> {
    let action = if !truthy(&args["waiting"]) || args["requested"] == args["pending"] {
        "keep"
    } else {
        "drop"
    };
    Ok(json!(action))
}

/// Start again on a timer that has run out: `ignore`, or `begin` with the new work phase.
/// Arguments: `focus`, `busy`, `focus_busy`, `prefs`, `now_ms`.
pub fn restart_finished_plan(args: &Value) -> EngineResult<Value> {
    let state = &args["focus"];
    if ended_blocked(
        state,
        truthy(&args["busy"]),
        truthy(&args["focus_busy"]),
        true,
    ) {
        return Ok(json!({ "action": "ignore" }));
    }
    let target = json!({
        "weekStart": field_or_null(state, "weekStart"),
        "blockId": field_or_null(state, "blockId"),
        "assignmentId": field_or_null(state, "assignmentId"),
        "day": field_or_null(state, "day"),
        "start": field_or_null(state, "start"),
        "title": field_or_null(state, "title"),
    });
    let begun = timer::begin_state(&target, &args["prefs"], now_of(args)?)?;
    Ok(json!({ "action": "begin", "state": begun }))
}

fn refuse_more_time() -> Value {
    json!({ "action": "refuse", "say": MORE_TIME })
}

/// More time on a finished timer: `ignore`, `refuse` (the minutes are not one of the choices), or
/// `apply` with the homework, the break the timer enters, its notice and the history label.
/// Arguments: `focus`, `busy`, `focus_busy`, `assignments`, `minutes`, `prefs`, `now_ms`.
pub fn add_focus_time_plan(args: &Value) -> EngineResult<Value> {
    let state = &args["focus"];
    if ended_blocked(
        state,
        truthy(&args["busy"]),
        truthy(&args["focus_busy"]),
        true,
    ) {
        return Ok(json!({ "action": "ignore" }));
    }
    let Some(assignment) = state["assignmentId"]
        .as_str()
        .and_then(|id| args["assignments"].get(id))
        .filter(|item| !item.is_null())
    else {
        return Ok(refuse_more_time());
    };
    let minutes = args["minutes"]
        .as_i64()
        .ok_or_else(|| EngineError::value("minutes is a whole number"))?;
    let estimate = match assignment.get("estimate_min") {
        Some(value) if truthy(value) => {
            py_whole(value).ok_or_else(|| EngineError::value("estimate_min is a whole number"))?
        }
        _ => 0,
    };
    if !timer::more_time_choices(estimate).contains(&minutes) {
        return Ok(refuse_more_time());
    }
    let base = match assignment.get("estimate_min") {
        Some(value) => {
            py_whole(value).ok_or_else(|| EngineError::value("estimate_min is a whole number"))?
        }
        None => return Err(EngineError::key("estimate_min")),
    };
    let sum = base
        .checked_add(minutes)
        .ok_or_else(|| EngineError::overflow("integer too large for the engine"))?;
    let title = assignment
        .get("title")
        .and_then(Value::as_str)
        .ok_or_else(|| EngineError::key("title"))?;
    let mut homework = assignment.clone();
    homework["estimate_min"] = json!(sum);
    let now = now_of(args)?;
    let phase = timer::break_phase(whole_or_zero(&state["cycles"])?, &args["prefs"])?;
    let moved = entered(state, phase, &args["prefs"], now)?;
    Ok(json!({
        "action": "apply",
        "homework": homework,
        "state": moved["state"],
        "alert": moved["alert"],
        "history_label": format!("adding time to {title}"),
    }))
}

/// A break after a finished timer, without adding time. Busy does not block it.
/// `ignore`, or `apply` with the timer and the notice. Arguments: `focus`, `focus_busy`, `prefs`,
/// `now_ms`.
pub fn take_break_plan(args: &Value) -> EngineResult<Value> {
    let state = &args["focus"];
    if ended_blocked(state, false, truthy(&args["focus_busy"]), false) {
        return Ok(json!({ "action": "ignore" }));
    }
    let now = now_of(args)?;
    let phase = timer::break_phase(whole_or_zero(&state["cycles"])?, &args["prefs"])?;
    let moved = entered(state, phase, &args["prefs"], now)?;
    Ok(json!({
        "action": "apply",
        "state": moved["state"],
        "alert": moved["alert"],
    }))
}

const KEPT_FORMAT: i64 = 1;
/// A few accounts' timers fit under this. Anything larger is not read.
const FOCUS_FILE_MAX_BYTES: usize = 64 * 1024;
/// Lengths the preferences screen stores (`engine/service/src/preferences.rs`).
const WORK_MIN_RANGE: std::ops::RangeInclusive<i64> = 1..=180;
const BREAK_MIN_RANGE: std::ops::RangeInclusive<i64> = 1..=60;
const LONG_BREAK_MIN_RANGE: std::ops::RangeInclusive<i64> = 1..=120;

/// Read a focus-timer file. `text` is the file, or null when there is no file.
/// A file this build cannot trust answers no timers, not an error. `sealed` is
/// set when the format is a newer one and the file must be left on disk.
/// Arguments: `text`.
pub fn load_kept(args: &Value) -> EngineResult<Value> {
    let Some(text) = args.get("text") else {
        return Ok(empty_entries());
    };
    if text.is_null() {
        return Ok(empty_entries());
    }
    let Some(text) = text.as_str() else {
        return Err(EngineError::value("text is text or null"));
    };
    let (kept, sealed) = read_kept_file(text);
    Ok(entries_value(kept, sealed))
}

/// Store one account's timer into the kept entries, or remove it when the timer is null.
/// What is stored is the same shape a later read accepts. A timer outside that shape
/// is not written.
/// Arguments: `entries`, `account_id`, `state`.
pub fn merge_kept(args: &Value) -> EngineResult<Value> {
    let mut kept = read_entries(args)?;
    let id = account_id_of(args)?;
    let state = args
        .get("state")
        .ok_or_else(|| EngineError::value("state is an object or null"))?;
    match timer::persist_payload(state)? {
        Some(payload) => match strict_payload(&payload) {
            Some(clean) => {
                kept.insert(id, clean);
            }
            None => {
                kept.remove(&id);
            }
        },
        None => {
            kept.remove(&id);
        }
    }
    Ok(entries_value(kept, false))
}

/// Drop one account from the kept entries. An account that is not there stays absent.
/// `changed` is false when the account had no entry, so the file can be left as it is.
/// Arguments: `entries`, `account_id`.
pub fn remove_kept(args: &Value) -> EngineResult<Value> {
    let mut kept = read_entries(args)?;
    let changed = kept.remove(&account_id_of(args)?).is_some();
    let mut answer = entries_value(kept, false);
    answer["changed"] = json!(changed);
    Ok(answer)
}

/// The focus-timer file for these entries: format 1, accounts in id order.
/// An entry this build would not read back is left out.
/// Arguments: `entries`.
pub fn kept_text(args: &Value) -> EngineResult<Value> {
    let kept = read_entries(args)?;
    let mut accounts = serde_json::Map::new();
    for (id, payload) in kept {
        if let Some(clean) = strict_payload(&payload) {
            accounts.insert(id.to_string(), clean);
        }
    }
    let file = json!({ "format": KEPT_FORMAT, "accounts": Value::Object(accounts) });
    Ok(json!({ "text": file.to_string() }))
}

fn empty_entries() -> Value {
    json!({ "entries": [] })
}

fn entries_value(kept: BTreeMap<i64, Value>, sealed: bool) -> Value {
    let entries: Vec<Value> = kept
        .into_iter()
        .map(|(id, payload)| json!({ "account_id": id, "payload": payload }))
        .collect();
    if sealed {
        json!({ "entries": entries, "sealed": true })
    } else {
        json!({ "entries": entries })
    }
}

fn read_kept_file(text: &str) -> (BTreeMap<i64, Value>, bool) {
    if text.len() > FOCUS_FILE_MAX_BYTES {
        return (BTreeMap::new(), false);
    }
    let Ok(file) = serde_json::from_str::<Value>(text) else {
        return (BTreeMap::new(), false);
    };
    let Some(file) = file.as_object() else {
        return (BTreeMap::new(), false);
    };
    if newer_format(file.get("format")) {
        return (BTreeMap::new(), true);
    }
    if file.get("format").and_then(Value::as_i64) != Some(KEPT_FORMAT) {
        return (BTreeMap::new(), false);
    }
    let Some(accounts) = file.get("accounts").and_then(Value::as_object) else {
        return (BTreeMap::new(), false);
    };
    let mut kept = BTreeMap::new();
    for (key, payload) in accounts {
        let Some(id) = canonical_account_key(key) else {
            continue;
        };
        if let Some(clean) = strict_payload(payload) {
            kept.insert(id, clean);
        }
    }
    (kept, false)
}

/// A whole-number format other than the one this build writes is a newer file.
fn newer_format(format: Option<&Value>) -> bool {
    match format {
        Some(Value::Number(number)) => number.as_i64().is_some_and(|found| found != KEPT_FORMAT),
        _ => false,
    }
}

fn canonical_account_key(key: &str) -> Option<i64> {
    let Ok(id) = key.parse::<i64>() else {
        return None;
    };
    (id.to_string() == key).then_some(id)
}

/// The session named on the timer is that homework's session. A timer with no session,
/// or no homework, has nothing to cross.
fn session_belongs_to_assignment(state: &Value, blocks: &Value) -> bool {
    let assignment = &state["assignmentId"];
    let block_id = &state["blockId"];
    if !truthy(assignment) || !truthy(block_id) {
        return true;
    }
    let Some(items) = blocks.as_array() else {
        return false;
    };
    // Only a session seen on the open week with another homework is refused. A timer from
    // another week (Sunday night, reopened Monday) is not on this week's blocks at all; it
    // is kept as before, and drop_missing judges it once its own week is open.
    match items.iter().find(|item| item.get("id") == Some(block_id)) {
        Some(item) => item.get("assignment_id") == Some(assignment),
        None => true,
    }
}

/// The timer rebuilt from the fields the app writes. Extra fields are dropped. A field
/// outside the range the app writes drops the whole timer.
fn strict_payload(payload: &Value) -> Option<Value> {
    if !payload.is_object() || saved_is_corrupt(payload) {
        return None;
    }
    if !optional_range(payload, "breakMin", &BREAK_MIN_RANGE)
        || !optional_range(payload, "longBreakMin", &LONG_BREAK_MIN_RANGE)
        || !optional_range(payload, "startedAt", &(0..=i64::MAX))
    {
        return None;
    }
    let phase = payload.get("phase").and_then(Value::as_str)?;
    if !timer::FOCUS_PHASES.contains(&phase) {
        return None;
    }
    let cycles = payload.get("cycles").and_then(Value::as_i64)?;
    if !(0..=timer::MAX_FOCUS_SESSIONS).contains(&i128::from(cycles)) {
        return None;
    }
    let week = payload
        .get("weekStart")
        .and_then(Value::as_str)
        .filter(|text| flexweek_engine::time::is_week_start(text))?;
    let ends = optional_millis(payload, "endsAt")?;
    let remaining = optional_millis(payload, "remainingMs")?;
    if ends.is_none() && remaining.is_none() {
        return None;
    }
    let work_min = optional_work_min(payload)?;
    let mut clean = serde_json::Map::new();
    clean.insert(
        "assignmentId".into(),
        text_or_null(payload, "assignmentId")?,
    );
    clean.insert("sessionId".into(), text_or_null(payload, "sessionId")?);
    clean.insert("weekStart".into(), json!(week));
    clean.insert("day".into(), kept_day(payload)?);
    clean.insert("start".into(), text_or_null(payload, "start")?);
    clean.insert("phase".into(), json!(phase));
    clean.insert("cycles".into(), json!(cycles));
    clean.insert("endsAt".into(), millis_or_null(ends));
    clean.insert("remainingMs".into(), millis_or_null(remaining));
    if let Some(minutes) = work_min {
        clean.insert("workMin".into(), json!(minutes));
    }
    Some(Value::Object(clean))
}

fn text_or_null(payload: &Value, key: &str) -> Option<Value> {
    match payload.get(key) {
        None | Some(Value::Null) => Some(Value::Null),
        Some(Value::String(text)) => Some(json!(text)),
        Some(_) => None,
    }
}

fn kept_day(payload: &Value) -> Option<Value> {
    match payload.get("day") {
        None | Some(Value::Null) => Some(Value::Null),
        Some(Value::Number(number)) => {
            let day = number.as_i64()?;
            (0..=6).contains(&day).then(|| json!(day))
        }
        Some(_) => None,
    }
}

fn optional_work_min(payload: &Value) -> Option<Option<i64>> {
    match payload.get("workMin") {
        None | Some(Value::Null) => Some(None),
        Some(Value::Number(number)) => {
            let minutes = number.as_i64()?;
            WORK_MIN_RANGE.contains(&minutes).then_some(Some(minutes))
        }
        Some(_) => None,
    }
}

fn optional_millis(payload: &Value, key: &str) -> Option<Option<i64>> {
    match payload.get(key) {
        None | Some(Value::Null) => Some(None),
        Some(Value::Number(number)) => {
            let number = number.as_i64()?;
            (number >= 0).then_some(Some(number))
        }
        Some(_) => None,
    }
}

fn millis_or_null(value: Option<i64>) -> Value {
    match value {
        Some(number) => json!(number),
        None => Value::Null,
    }
}

fn optional_range(payload: &Value, key: &str, range: &std::ops::RangeInclusive<i64>) -> bool {
    match payload.get(key) {
        None | Some(Value::Null) => true,
        Some(Value::Number(number)) => number.as_i64().is_some_and(|found| range.contains(&found)),
        Some(_) => false,
    }
}

fn read_entries(args: &Value) -> EngineResult<BTreeMap<i64, Value>> {
    let items = args
        .get("entries")
        .and_then(Value::as_array)
        .ok_or_else(|| EngineError::value("entries is a list"))?;
    let mut kept = BTreeMap::new();
    for item in items {
        let item = item
            .as_object()
            .ok_or_else(|| EngineError::value("an entry is an object"))?;
        let id = item
            .get("account_id")
            .and_then(Value::as_i64)
            .ok_or_else(|| EngineError::value("account_id is a whole number"))?;
        let payload = item
            .get("payload")
            .filter(|value| value.is_object())
            .cloned()
            .ok_or_else(|| EngineError::value("payload is an object"))?;
        kept.insert(id, payload);
    }
    Ok(kept)
}

fn account_id_of(args: &Value) -> EngineResult<i64> {
    args.get("account_id")
        .and_then(Value::as_i64)
        .ok_or_else(|| EngineError::value("account_id is a whole number"))
}
