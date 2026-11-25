//! The focus timer's decisions (P4 group 6; the focus block of `desktop/native/controller.py`). Each
//! function takes one JSON object of arguments and answers one JSON value, so the Python window and a
//! Rust one ask the same way. The session keeps the timer, the credits waiting and the held notices, and
//! applies what comes back; the timer's own arithmetic stays in the engine (`desk::focus`). The clock and
//! the preferences are always passed in.

use flexweek_engine::desk::{focus as timer, grid};
use flexweek_engine::time::week_start_on;
use flexweek_engine::{EngineError, EngineResult};
use serde_json::{Value, json};

const PLACE_FIRST: &str = "Place a work block that isn't finished before starting focus.";
const HOMEWORK_NOT_LOADED: &str = "This homework did not load, so the focus time was not counted. \
Reload the week and try again.";
const TIMER_STOPPED: &str = "Schedule restored. The previous focus timer was stopped because \
its session no longer exists.";

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
            day.is_null() || item["days"].as_array().is_some_and(|days| days.contains(day))
        };
        placed = args["trace"]["placed"]
            .as_array()
            .and_then(|list| list.iter().find(|item| item["id"] == *block_id && on_day(item)));
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
    Ok(json!(i64::try_from(spent.max(0) / 60_000).unwrap_or(i64::MAX)))
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
    let cycles = whole(&state["cycles"]) + i64::from(completed);
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
            && item["days"].as_array().is_some_and(|days| days.contains(day))
    });
    let done = marked_block(marked, state);
    let own = &state["assignmentId"];
    let assignment_id = if truthy(own) {
        own
    } else {
        block.map_or(&NULL, |item| &item["assignment_id"])
    };
    let open = assignment_id.as_str().filter(|id| !id.is_empty()).filter(|id| {
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
    let hold: Vec<bool> = kinds
        .iter()
        .map(|kind| muting && kind != "focus")
        .collect();
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
