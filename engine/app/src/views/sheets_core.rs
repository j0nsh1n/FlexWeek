//! Sheet lifecycle, save and delete flows, alarms and the notice bar (P5-S4).
//!
//! The Material sheets bridge keeps its Qt state and its drafts. For each decision it passes the
//! facts it holds as JSON and gets back what to do: a list of steps, or a small answer. A step is
//! `{"on", "call", "args", "kwargs"}`: Python calls `call` on its session, window, bridge, timer,
//! signal or draft (`on`) and does nothing else. A `null` answer means "stop here". Nothing in this
//! file reads a clock, draws an id or asks the operating system; the caller passes today's date.

use flexweek_engine::desk::datetext::{day_of, month_title};
use flexweek_engine::desk::grid::{is_standing_block, sunday_due};
use flexweek_engine::desk::reuse::restore_point_label;
use flexweek_engine::desk::weekmodel::added_words;
use flexweek_engine::shown::{day_names, family_id};
use flexweek_engine::stored::{py_str, truthy};
use flexweek_engine::time::{DAY_END_MIN, DAY_START_MIN, SLOT_MIN};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use serde_json::{Value, json};

use super::hours::{drag_step, next_slot};

pub const NOTHING_UNFINISHED: &str = "None left";
pub const NOTICE_MS: i64 = 10000;
pub const WAIT_SAVE: &str = "Saving your last change… Try Save again in a moment.";
pub const WAIT_DELETE: &str = "Saving your last change… Try Delete again in a moment.";
pub const UNDO_ALSO: &str = "Undo also takes back anything changed after it.";
pub const MAX_NAMED_WEEKS: usize = 3;
pub const SAVED_ALARM: &str = "Saved the alarm.";
pub const DELETED_ALARM: &str = "Deleted the alarm.";
pub const UNPINNED: &str = "FlexWeek can move it again.";
const FLEX_CATEGORIES: [&str; 2] = ["assignments", "study"];
const USUAL_START: &str = "16:00";
const MIN_DRAWN_HOMEWORK_MIN: i64 = 15;

fn type_error(message: impl Into<String>) -> EngineError {
    EngineError {
        kind: ErrorKind::Type,
        message: message.into(),
    }
}

/// The words and the discard prompt Python re-exports under their old names.
pub fn words() -> Value {
    json!({
        "nothing_unfinished": NOTHING_UNFINISHED,
        "notice_ms": NOTICE_MS,
        "wait_save": WAIT_SAVE,
        "wait_delete": WAIT_DELETE,
        "undo_also": UNDO_ALSO,
        "max_named_weeks": MAX_NAMED_WEEKS,
        "saved_alarm": SAVED_ALARM,
        "deleted_alarm": DELETED_ALARM,
        "discard": discard_prompt(),
    })
}

fn discard_prompt() -> Value {
    json!({
        "id": "discard",
        "title": "Discard your changes?",
        "body": "Your changes will be lost.",
        "answers": [
            {"id": "keep", "label": "Keep editing", "kind": "text"},
            {"id": "discard", "label": "Discard", "kind": "danger"},
        ],
    })
}

fn day_year_label(week: &str, today_year: &str) -> EngineResult<String> {
    let day = day_of(week)?;
    let mut parts = week.splitn(3, '-');
    let (year, _, date) = (parts.next(), parts.next(), parts.next());
    let number: u32 = date
        .and_then(|text| text.parse().ok())
        .ok_or_else(|| EngineError::value(format!("Invalid isoformat string: '{week}'")))?;
    let year = year.unwrap_or_default();
    let month = month_title(day, true);
    let month = month.split(' ').next().unwrap_or_default();
    let text = format!("{number} {month}");
    if year == today_year {
        Ok(text)
    } else {
        Ok(format!("{text} {year}"))
    }
}

/// Where a new weekly time sits twice: at most three weeks named, then "and N more".
pub fn doubled_words(name: &str, weeks: &[String], today: &str) -> EngineResult<String> {
    day_of(today)?;
    let today_year = today.split('-').next().unwrap_or_default();
    let named = weeks
        .iter()
        .take(MAX_NAMED_WEEKS)
        .map(|week| day_year_label(week, today_year))
        .collect::<EngineResult<Vec<_>>>()?;
    let listed = if weeks.len() > MAX_NAMED_WEEKS {
        format!(
            "{} and {} more",
            named.join(", "),
            weeks.len() - MAX_NAMED_WEEKS
        )
    } else if let Some((last, rest)) = named.split_last().filter(|(_, rest)| !rest.is_empty()) {
        format!("{} and {last}", rest.join(", "))
    } else {
        named
            .first()
            .cloned()
            .ok_or_else(|| EngineError::index("list index out of range"))?
    };
    let one = weeks.len() == 1;
    Ok(format!(
        "{name} also sits on its own in the {} of {listed}, so it shows twice there. Delete the extra one in {} if you don't want both.",
        if one { "week" } else { "weeks" },
        if one { "that week" } else { "those weeks" },
    ))
}

// Facts ---------------------------------------------------------------------------------------

fn get<'a>(facts: &'a Value, key: &str) -> EngineResult<&'a Value> {
    facts
        .as_object()
        .ok_or_else(|| type_error("sheet facts must be an object"))?
        .get(key)
        .ok_or_else(|| EngineError::value(format!("sheet facts: missing {key}")))
}

fn text<'a>(facts: &'a Value, key: &str) -> EngineResult<&'a str> {
    get(facts, key)?
        .as_str()
        .ok_or_else(|| type_error(format!("sheet facts: {key} must be text")))
}

fn flag(facts: &Value, key: &str) -> EngineResult<bool> {
    get(facts, key)?
        .as_bool()
        .ok_or_else(|| type_error(format!("sheet facts: {key} must be true or false")))
}

fn int(facts: &Value, key: &str) -> EngineResult<i64> {
    let value = get(facts, key)?;
    if value.is_boolean() {
        return Err(type_error(format!(
            "sheet facts: {key} must be a whole number"
        )));
    }
    value
        .as_i64()
        .ok_or_else(|| type_error(format!("sheet facts: {key} must be a whole number")))
}

fn opt_int(facts: &Value, key: &str) -> EngineResult<Option<i64>> {
    match get(facts, key)? {
        Value::Null => Ok(None),
        _ => int(facts, key).map(Some),
    }
}

fn array<'a>(facts: &'a Value, key: &str) -> EngineResult<&'a Vec<Value>> {
    get(facts, key)?
        .as_array()
        .ok_or_else(|| type_error(format!("sheet facts: {key} must be a list")))
}

fn lenient_text<'a>(facts: &'a Value, key: &str) -> EngineResult<Option<&'a str>> {
    Ok(get(facts, key)?.as_str())
}

/// `str(value or default)`.
fn or_default(value: Option<&Value>, default: &str) -> String {
    match value {
        Some(found) if truthy(Some(found)) => py_str(found),
        _ => default.to_string(),
    }
}

// Steps ---------------------------------------------------------------------------------------

fn step(on: &str, call: &str, args: Vec<Value>, kwargs: Value) -> Value {
    json!({"on": on, "call": call, "args": args, "kwargs": kwargs})
}

fn bridge(call: &str) -> Value {
    step("bridge", call, Vec::new(), json!({}))
}

fn bridge_with(call: &str, args: Vec<Value>) -> Value {
    step("bridge", call, args, json!({}))
}

fn session(call: &str, args: Vec<Value>, kwargs: Value) -> Value {
    step("session", call, args, kwargs)
}

fn set(name: &str, value: Value) -> Value {
    step("bridge", "__setattr__", vec![json!(name), value], json!({}))
}

fn say(words: &str, undo: bool) -> Value {
    let kwargs = if undo {
        json!({"undo": true})
    } else {
        json!({})
    };
    step("bridge", "_say", vec![json!(words)], kwargs)
}

fn changed() -> Value {
    step("changed", "emit", Vec::new(), json!({}))
}

fn publish() -> Value {
    bridge("_publish")
}

fn steps(list: Vec<Value>) -> EngineResult<Value> {
    Ok(Value::Array(list))
}

// Decisions -----------------------------------------------------------------------------------

/// Which decision to take. Unknown names and wrong-shaped facts are refused.
pub fn plan(op: &str, facts: &Value) -> EngineResult<Value> {
    match op {
        "active" => active(facts),
        "can_save" => can_save(facts),
        "hold" => hold(facts),
        "open_homework" => open_homework(facts),
        "open_homework_at" => open_homework_at(facts),
        "open_block" => open_block(facts),
        "open_block_at" => open_block_at(facts),
        "new_event_values" => new_event_values(facts),
        "edit_block" => edit_block(facts),
        "ask_delete_block" => ask_delete_block(facts),
        "close" => close(facts),
        "close_sheet" => close_sheet(facts),
        "escape_sheet" => escape_sheet(facts),
        "after_advance" => after_advance(facts),
        "save" => save(facts),
        "save_homework" => save_homework(facts),
        "save_block_route" => save_block_route(facts),
        "answer_save_route" => answer_save_route(facts),
        "repeat_before" => repeat_before(facts),
        "repeat_after" => repeat_after(facts),
        "ticked_back" => ticked_back(facts),
        "block_ids" => block_ids(facts),
        "week_copy_after" => week_copy_after(facts),
        "unpin_gate" => unpin_gate(facts),
        "unpin_done" => unpin_done(facts),
        "remove" => remove(facts),
        "answer" => answer(facts),
        "delete_homework_done" => delete_homework_done(facts),
        "delete_block" => delete_block(facts),
        "delete_block_standing_done" => delete_block_standing_done(facts),
        "alarms" => alarms(facts),
        "open_alarm" => open_alarm(facts),
        "save_alarm_gate" => save_alarm_gate(facts),
        "alarm_full" => alarm_full(facts),
        "alarm_written" => alarm_written(facts),
        "alarm_refused" => alarm_refused(facts),
        "remove_alarm" => remove_alarm(facts),
        "alarms_without" => alarms_without(facts),
        "saved" => saved(facts),
        "busy" => busy(facts),
        "preview_edit" => preview_edit(facts),
        "preview_gate" => preview_gate(facts),
        "say" => say_plan(facts),
        "pause" => pause(facts),
        "resume" => resume(facts),
        "dismiss" => dismiss(facts),
        "undo" => undo(facts),
        "save_answered" => save_answered(facts),
        "doubled" => doubled(facts),
        "refresh" => refresh(facts),
        "form_source" => form_source(facts),
        "note_edge" => note_edge(facts),
        "drag_range" => drag_range(facts),
        "more_source" => more_source(facts),
        other => Err(EngineError::value(format!("unknown sheet plan: {other}"))),
    }
}

pub fn active(facts: &Value) -> EngineResult<Value> {
    let open = !text(facts, "kind")?.is_empty()
        || flag(facts, "more")?
        || flag(facts, "ask_open")?
        || flag(facts, "drag")?;
    Ok(json!(open))
}

pub fn can_save(facts: &Value) -> EngineResult<Value> {
    let free = !flag(facts, "no_session")?
        && !flag(facts, "busy")?
        && !flag(facts, "pending_save")?
        && !flag(facts, "conflict")?;
    Ok(json!(free))
}

/// The wait notice while a write is still in flight; `null` when the write may go ahead.
pub fn hold(facts: &Value) -> EngineResult<Value> {
    if flag(facts, "can_save")? {
        return Ok(Value::Null);
    }
    steps(vec![say(text(facts, "words")?, false), publish()])
}

fn homework_category(armed: Option<&str>) -> &str {
    match armed {
        Some(category) if FLEX_CATEGORIES.contains(&category) => category,
        _ => "assignments",
    }
}

fn clock_text(minutes: i64) -> String {
    format!(
        "{:02}:{:02}",
        minutes.div_euclid(60),
        minutes.rem_euclid(60)
    )
}

pub fn open_homework(facts: &Value) -> EngineResult<Value> {
    if !flag(facts, "account")? {
        return Ok(Value::Null);
    }
    let armed = lenient_text(facts, "armed")?;
    Ok(json!({"category": homework_category(armed)}))
}

pub fn open_homework_at(facts: &Value) -> EngineResult<Value> {
    if !flag(facts, "account")? {
        return Ok(Value::Null);
    }
    let (first, second) = (int(facts, "start_min")?, int(facts, "end_min")?);
    let (start, end) = if first > second {
        (second, first)
    } else {
        (first, second)
    };
    let duration = end - start;
    if duration < MIN_DRAWN_HOMEWORK_MIN {
        return Ok(Value::Null);
    }
    let week_start = get(facts, "week_start")?;
    let due = if truthy(Some(week_start)) {
        json!(sunday_due(&py_str(week_start))?)
    } else {
        Value::Null
    };
    Ok(json!({
        "category": homework_category(lenient_text(facts, "armed")?),
        "day": int(facts, "day")?,
        "start": clock_text(start),
        "duration": duration,
        "due": due,
    }))
}

fn block_category(armed: Option<&str>) -> Value {
    match armed {
        Some(category) if !FLEX_CATEGORIES.contains(&category) => json!(category),
        _ => Value::Null,
    }
}

pub fn open_block(facts: &Value) -> EngineResult<Value> {
    if !flag(facts, "account")? {
        return Ok(Value::Null);
    }
    Ok(json!({"category": block_category(lenient_text(facts, "armed")?)}))
}

pub fn open_block_at(facts: &Value) -> EngineResult<Value> {
    if !flag(facts, "account")? {
        return Ok(Value::Null);
    }
    let (first, second) = (int(facts, "start_min")?, int(facts, "end_min")?);
    let (start, end) = if first <= second {
        (first, second)
    } else {
        (second, first)
    };
    // One step is the shortest block a draw makes, as in the Widgets grid.
    let chosen = get(facts, "preferences")?
        .get("drag_step_min")
        .filter(|value| !value.is_boolean())
        .and_then(Value::as_i64);
    if end - start < drag_step(chosen) {
        return Ok(Value::Null);
    }
    Ok(json!({
        "category": block_category(lenient_text(facts, "armed")?),
        "day": int(facts, "day")?,
        "start": clock_text(start),
        "length": end - start,
    }))
}

/// The next quarter hour still ahead today, or the usual 16:00 on another week.
pub fn new_event_values(facts: &Value) -> EngineResult<Value> {
    let usual = json!([0, USUAL_START]);
    let Some(today) = opt_int(facts, "today_column")? else {
        return Ok(usual);
    };
    let (ahead, slot) = next_slot(
        int(facts, "minute")?,
        DAY_START_MIN,
        DAY_END_MIN - SLOT_MIN,
        SLOT_MIN,
    )?;
    if today + ahead > 6 {
        return Ok(usual);
    }
    Ok(json!([today + ahead, clock_text(slot)]))
}

fn find_block<'a>(blocks: &'a Value, id: &str) -> EngineResult<Option<&'a Value>> {
    match blocks {
        Value::Null => Ok(None),
        Value::Array(items) => Ok(items
            .iter()
            .find(|item| item.get("id").and_then(Value::as_str) == Some(id))),
        _ => Err(type_error("sheet facts: blocks must be a list")),
    }
}

fn occurrence_of(day: i64) -> Value {
    if day >= 0 { json!(day) } else { Value::Null }
}

/// A block on the week: homework opens Edit homework, a fixed time opens Edit fixed time.
pub fn edit_block(facts: &Value) -> EngineResult<Value> {
    let Some(block) = find_block(get(facts, "blocks")?, text(facts, "block_id")?)? else {
        return steps(Vec::new());
    };
    let known = array(facts, "assignment_ids")?;
    let linked = block
        .get("assignment_id")
        .and_then(Value::as_str)
        .filter(|id| !id.is_empty() && known.iter().any(|item| item.as_str() == Some(id)));
    if let Some(id) = linked {
        return steps(vec![bridge_with("editHomework", vec![json!(id)])]);
    }
    if block.get("kind").and_then(Value::as_str) != Some("locked") {
        return steps(Vec::new());
    }
    steps(vec![bridge_with(
        "_edit_block_draft",
        vec![block.clone(), occurrence_of(int(facts, "day")?)],
    )])
}

/// Delete from a fixed time's menu: the Edit sheet's own question, with no sheet behind it.
pub fn ask_delete_block(facts: &Value) -> EngineResult<Value> {
    let Some(block) = find_block(get(facts, "blocks")?, text(facts, "block_id")?)? else {
        return steps(Vec::new());
    };
    if block.get("kind").and_then(Value::as_str) != Some("locked")
        || truthy(block.get("assignment_id"))
    {
        return steps(Vec::new());
    }
    steps(vec![bridge_with(
        "_ask_delete_draft",
        vec![block.clone(), occurrence_of(int(facts, "day")?)],
    )])
}

pub fn close(facts: &Value) -> EngineResult<Value> {
    let kind = text(facts, "kind")?;
    let before = if kind == "update" {
        vec![bridge("_defer_update_finish")]
    } else {
        Vec::new()
    };
    let clear = if kind == "late" && flag(facts, "late_preview")? {
        vec![
            step(
                "session",
                "__setattr__",
                vec![json!("late_preview"), Value::Null],
                json!({}),
            ),
            session("_say", vec![json!("")], json!({})),
        ]
    } else {
        Vec::new()
    };
    Ok(json!({"before": before, "clear": clear}))
}

fn ask_is_open(facts: &Value) -> EngineResult<bool> {
    Ok(truthy(Some(get(facts, "ask")?)))
}

/// Esc, Cancel and a tap on the scrim. A sheet with typed work asks before dropping it.
pub fn close_sheet(facts: &Value) -> EngineResult<Value> {
    if flag(facts, "drag_active")? {
        return steps(vec![bridge("_cancel_drag")]);
    }
    if ask_is_open(facts)? {
        let edited = get(facts, "ask")?.get("id").and_then(Value::as_str) == Some("edited-weeks");
        let dismisses = array(facts, "handlers")?
            .iter()
            .any(|name| name.as_str() == Some("dismiss"));
        let which = if edited && flag(facts, "done")? {
            "done"
        } else if dismisses {
            "dismiss"
        } else {
            "none"
        };
        return steps(vec![bridge_with("_dismiss_ask", vec![json!(which)])]);
    }
    let dirty = match text(facts, "kind")? {
        "homework" => flag(facts, "homework_dirty")?,
        "block" => flag(facts, "block_dirty")?,
        "alarm" => flag(facts, "alarm_dirty")?,
        _ => false,
    };
    if dirty {
        return steps(vec![set("_ask", discard_prompt()), publish()]);
    }
    steps(vec![bridge("_close")])
}

/// Esc. A new Add sheet with typed work closes at once and keeps it for the next Add of its kind;
/// anything else goes through `closeSheet`.
pub fn escape_sheet(facts: &Value) -> EngineResult<Value> {
    let keeps = flag(facts, "has_draft")?
        && !flag(facts, "existing")?
        && flag(facts, "dirty")?
        && !flag(facts, "drag_active")?
        && !ask_is_open(facts)?;
    if !keeps {
        return steps(vec![bridge("closeSheet")]);
    }
    let keep = if text(facts, "kind")? == "homework" {
        "_keep_homework"
    } else {
        "_keep_block"
    };
    steps(vec![bridge(keep), bridge("_close")])
}

pub fn after_advance(facts: &Value) -> EngineResult<Value> {
    steps(vec![bridge(if flag(facts, "done")? {
        "save"
    } else {
        "_publish"
    })])
}

/// Add or Save: the sheet's answer, through the session.
pub fn save(facts: &Value) -> EngineResult<Value> {
    match text(facts, "kind")? {
        "homework" => steps(vec![bridge("_save_homework")]),
        "block" => steps(vec![bridge("_save_block")]),
        _ => steps(Vec::new()),
    }
}

fn title_of(value: Option<&Value>, default: &str) -> String {
    or_default(value, default)
}

pub fn save_homework(facts: &Value) -> EngineResult<Value> {
    let made = get(facts, "made")?;
    let known = get(facts, "known")?;
    let id = made
        .get("id")
        .cloned()
        .ok_or_else(|| EngineError::key("id"))?;
    let title = title_of(made.get("title"), "Homework");
    let completed = truthy(made.get("completed"));
    let known_done = truthy(known.get("completed"));
    let mut list = Vec::new();
    if flag(facts, "spread")? {
        list.push(bridge("_take_spread_plan"));
        list.push(session(
            "add_homework",
            vec![made.clone()],
            json!({"spread": true}),
        ));
        list.push(bridge_with("_spread_after_save", vec![id.clone()]));
        list.push(session("save", Vec::new(), json!({})));
    } else {
        list.push(session("add_homework", vec![made.clone()], json!({})));
        let auto = get(facts, "preferences")?
            .get("planning_style")
            .and_then(Value::as_str)
            == Some("auto");
        if auto && known.is_null() && !completed {
            // Plan it for me as I add it: new homework gets its time once it is saved.
            list.push(session("plan_after_save", vec![id.clone()], json!({})));
        }
        list.push(session("save", Vec::new(), json!({})));
    }
    let words = if completed && !known_done {
        format!("Finished {title}.")
    } else if known.is_null() {
        format!("Added {title}")
    } else {
        format!("Saved {title}")
    };
    list.push(bridge("_close"));
    list.push(say(&words, true));
    steps(list)
}

pub fn save_block_route(facts: &Value) -> EngineResult<Value> {
    Ok(json!(match text(facts, "kind")? {
        "ask" => "ask",
        "plain" => "copy",
        _ => "repeat",
    }))
}

pub fn answer_save_route(facts: &Value) -> EngineResult<Value> {
    Ok(json!(if text(facts, "choice")? == "later" {
        "repeat"
    } else {
        "copy"
    }))
}

fn id_of(item: &Value) -> EngineResult<&Value> {
    item.get("id").ok_or_else(|| EngineError::key("id"))
}

/// The repeats a change to a weekly fixed time leaves, for the window to ask about.
pub fn repeat_before(facts: &Value) -> EngineResult<Value> {
    let kind = text(facts, "kind")?;
    let repeats = array(facts, "repeats")?;
    let body = get(facts, "repeat")?;
    let after: Vec<Value> = match kind {
        "add" | "make" => repeats
            .iter()
            .cloned()
            .chain(std::iter::once(body.clone()))
            .collect(),
        "later" | "ask" => {
            let wanted = body
                .as_object()
                .ok_or_else(|| type_error("'NoneType' object is not subscriptable"))?
                .get("id")
                .ok_or_else(|| EngineError::key("id"))?;
            repeats
                .iter()
                .map(|item| {
                    Ok(if id_of(item)? == wanted {
                        body.clone()
                    } else {
                        item.clone()
                    })
                })
                .collect::<EngineResult<_>>()?
        }
        _ => {
            let family = json!(text(facts, "family")?);
            let mut kept = Vec::new();
            for item in repeats {
                if id_of(item)? != &family {
                    kept.push(item.clone());
                }
            }
            kept
        }
    };
    Ok(json!({
        "after": after,
        "label": format!("changing {}", text(facts, "title")?),
        "stop": kind == "stop",
    }))
}

/// What a weekly change does once the window has answered its question.
pub fn repeat_after(facts: &Value) -> EngineResult<Value> {
    if !flag(facts, "ok")? {
        return Ok(json!({"ticked": false, "then": []}));
    }
    let (kind, name, label) = (
        text(facts, "kind")?,
        text(facts, "title")?,
        text(facts, "label")?,
    );
    let mut list = Vec::new();
    if kind == "make" {
        // The one-off is now the repeat: one Undo step, named for the change.
        list.push(session(
            "delete_block",
            vec![get(facts, "original_id")?.clone()],
            json!({"scope": "series", "label": label}),
        ));
    } else if kind == "stop" {
        let alone = get(facts, "alone")?;
        if !alone.is_null() {
            list.push(session(
                "add_block",
                vec![alone.clone()],
                json!({"scope": "series"}),
            ));
        }
    }
    let said = match kind {
        "add" | "make" => format!("{name} repeats every week from this week on."),
        "stop" => format!("{name} stops repeating after this week."),
        _ => format!("Changed {name} from this week on."),
    };
    list.push(set("_saving_repeat", json!(format!("{said} {UNDO_ALSO}"))));
    list.push(set("_doubled_name", json!(name)));
    list.push(session(
        "save",
        Vec::new(),
        json!({"snapshot_label": restore_point_label(&format!("Before changing {name}"))}),
    ));
    Ok(json!({"ticked": matches!(kind, "later" | "ask"), "then": list}))
}

/// Days the student ticked back on are live this week. Days they left unticked stay removed.
pub fn ticked_back(facts: &Value) -> EngineResult<Value> {
    let listed = |key: &str| -> EngineResult<Vec<Value>> {
        let value = get(facts, key)?;
        Ok(value.as_array().cloned().unwrap_or_default())
    };
    let made = listed("made_removed")?;
    let restored: Vec<Value> = listed("original_removed")?
        .into_iter()
        .filter(|day| !made.contains(day))
        .collect();
    if restored.is_empty() {
        return steps(Vec::new());
    }
    let family = text(facts, "family")?;
    let mut blocks = Vec::new();
    let mut changed_any = false;
    for item in array(facts, "blocks")? {
        let id = or_default(item.get("id"), "");
        if family_id(&id) != family {
            blocks.push(item.clone());
            continue;
        }
        let had = item
            .get("removed_days")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let kept: Vec<Value> = had
            .iter()
            .filter(|day| !restored.contains(day))
            .cloned()
            .collect();
        if kept == had {
            blocks.push(item.clone());
            continue;
        }
        let mut updated = item.clone();
        if let Some(map) = updated.as_object_mut() {
            if kept.is_empty() {
                map.shift_remove("removed_days");
            } else {
                map.insert("removed_days".into(), Value::Array(kept));
            }
        }
        blocks.push(updated);
        changed_any = true;
    }
    if !changed_any {
        return steps(Vec::new());
    }
    steps(vec![session(
        "_touch",
        vec![json!(text(facts, "label")?)],
        json!({"blocks": blocks}),
    )])
}

pub fn block_ids(facts: &Value) -> EngineResult<Value> {
    let mut ids = Vec::new();
    for item in array(facts, "blocks")? {
        ids.push(id_of(item)?.clone());
    }
    Ok(Value::Array(ids))
}

/// A fixed time saved on this week's copy: "This day only" splits the series and gives that day a
/// new id, so a day marked missed is found among the blocks the save added.
pub fn week_copy_after(facts: &Value) -> EngineResult<Value> {
    let made = get(facts, "made")?;
    let made_id = id_of(made)?;
    let title = text(made, "title")?;
    let before = array(facts, "before_ids")?;
    let blocks = array(facts, "blocks")?;
    let recover_missed = flag(facts, "recover")?;
    let occurrence_day = opt_int(facts, "day")?;
    if recover_missed && let Some(day) = occurrence_day {
        let mut holder = None;
        for item in blocks {
            let id = id_of(item)?;
            if (id == made_id || !before.contains(id))
                && array(item, "days").is_ok_and(|days| days.contains(&json!(day)))
            {
                holder = Some(id);
                break;
            }
        }
        if let Some(id) = holder {
            return steps(vec![
                session("recover_missed", vec![id.clone(), json!(day)], json!({})),
                bridge("_close"),
                say(&format!("Saved {title}"), true),
            ]);
        }
    }
    let words = if before.contains(made_id) {
        format!("Saved {title}")
    } else {
        added_words(made, text(facts, "week_start")?)?
    };
    steps(vec![
        session("save", Vec::new(), json!({})),
        bridge("_close"),
        say(&words, true),
    ])
}

pub fn unpin_gate(facts: &Value) -> EngineResult<Value> {
    Ok(if flag(facts, "existing")? {
        json!({})
    } else {
        Value::Null
    })
}

pub fn unpin_done(facts: &Value) -> EngineResult<Value> {
    let mut list = Vec::new();
    if flag(facts, "unpinned")? {
        list.push(session("save", Vec::new(), json!({})));
    }
    list.push(bridge("_close"));
    list.push(say(UNPINNED, true));
    steps(list)
}

fn prompt(id: &str, title: &str, body: &str) -> Value {
    json!({
        "id": id,
        "title": title,
        "body": body,
        "answers": [
            {"id": "stay", "label": "Cancel", "kind": "text"},
            {"id": "delete", "label": "Delete", "kind": "danger"},
        ],
    })
}

/// Delete, on a sheet that is editing something. It asks first.
pub fn remove(facts: &Value) -> EngineResult<Value> {
    if flag(facts, "homework_existing")? {
        let title = title_of(Some(get(facts, "homework_title")?), "this homework");
        let body = format!(
            "Delete {title}? Its times on the calendar go too, in every week. You can undo this."
        );
        return steps(vec![
            set("_ask", prompt("delete-homework", "Delete homework", &body)),
            publish(),
        ]);
    }
    if flag(facts, "block_existing")? && flag(facts, "has_session")? {
        return steps(vec![bridge("_ask_block_delete"), publish()]);
    }
    steps(Vec::new())
}

/// A button on the prompt that is up.
pub fn answer(facts: &Value) -> EngineResult<Value> {
    let asked = get(facts, "ask")?
        .get("id")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let choice = text(facts, "choice")?;
    if asked == "edited-weeks" {
        let said = if matches!(choice, "keep" | "replace" | "from_today") {
            json!(choice)
        } else {
            Value::Null
        };
        return steps(vec![bridge_with("_answer_edited", vec![said])]);
    }
    let mut list = vec![set("_ask", json!({}))];
    if flag(facts, "has_handlers")? {
        list.push(bridge_with("_run_handler", vec![json!(choice)]));
        return steps(list);
    }
    let next = match (asked, choice) {
        ("sign-out", "yes") => bridge("_sign_out_yes"),
        ("sign-out", _) => bridge("_sign_out_no"),
        ("discard", "discard") => bridge("_close"),
        ("delete-homework", "delete") => bridge("_delete_homework"),
        ("delete-block", "delete" | "day" | "week" | "every") => {
            bridge_with("_delete_block", vec![json!(choice)])
        }
        ("block-save", "week" | "later") => bridge_with("_answer_save", vec![json!(choice)]),
        ("delete-alarm", "delete") => bridge("_delete_alarm"),
        ("delete-unfinished", "delete") => bridge_with(
            "_delete_unfinished",
            vec![get(facts, "pending_delete")?.clone()],
        ),
        _ => publish(),
    };
    list.push(next);
    steps(list)
}

pub fn delete_homework_done(facts: &Value) -> EngineResult<Value> {
    if flag(facts, "ok")? {
        let title = title_of(Some(get(facts, "title")?), "this homework");
        return steps(vec![
            bridge("_close"),
            say(&format!("Deleted {title}."), true),
        ]);
    }
    // Saving, or another window changed the week: the sheet stays so nothing typed is lost.
    steps(vec![
        step(
            "bridge",
            "_say",
            vec![get(facts, "message")?.clone()],
            json!({}),
        ),
        publish(),
    ])
}

/// Delete a fixed time. A weekly one deleted "every week" first needs the window's answer, so the
/// plan holds `standing` (what to ask) until then.
pub fn delete_block(facts: &Value) -> EngineResult<Value> {
    let block = get(facts, "block")?;
    let choice = text(facts, "choice")?;
    let title = title_of(block.get("title"), "this fixed time");
    let scope = match choice {
        "day" => "occurrence",
        "week" | "every" => "series",
        _ => text(facts, "scope")?,
    };
    let every_week = choice == "every";
    let day = opt_int(facts, "day")?;
    let id = id_of(block)?;
    if every_week && is_standing_block(block)? {
        let family = json!(family_id(
            id.as_str()
                .ok_or_else(|| type_error("block id must be text"))?
        ));
        let mut after = Vec::new();
        for item in array(facts, "repeats")? {
            if id_of(item)? != &family {
                after.push(item.clone());
            }
        }
        return Ok(json!({
            "standing": {"after": after, "label": format!("deleting {title}"), "title": title},
            "steps": [],
        }));
    }
    let mut list = vec![
        session(
            "delete_block",
            vec![id.clone()],
            json!({"scope": scope, "day": day, "every_week": every_week}),
        ),
        session("save", Vec::new(), json!({})),
        bridge("_close"),
    ];
    if every_week {
        list.push(say(
            &format!("Deleted {title} from this week and every week after."),
            false,
        ));
    } else if let (true, Some(day)) = (scope == "occurrence", day) {
        let names = day_names(text(facts, "week_start")?, true)?;
        let name = usize::try_from(day)
            .ok()
            .and_then(|at| names.get(at))
            .ok_or_else(|| EngineError::index("tuple index out of range"))?;
        list.push(say(
            &format!("Deleted {title} on {name} from this week."),
            true,
        ));
    } else {
        list.push(say(&format!("Deleted {title} from this week."), true));
    }
    Ok(json!({"standing": null, "steps": list}))
}

pub fn delete_block_standing_done(facts: &Value) -> EngineResult<Value> {
    if !flag(facts, "ok")? {
        return steps(Vec::new());
    }
    let title = text(facts, "title")?;
    let words = format!("Deleted {title} from this week and every week after. {UNDO_ALSO}");
    steps(vec![
        session(
            "save",
            Vec::new(),
            json!({"snapshot_label": restore_point_label(&format!("Before deleting {title}"))}),
        ),
        bridge("_close"),
        say(&words, false),
        set("_restore_words", json!(words)),
    ])
}

// Alarms --------------------------------------------------------------------------------------

pub fn alarms(facts: &Value) -> EngineResult<Value> {
    let list = get(facts, "preferences")?
        .get("alarms")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    Ok(Value::Array(list))
}

/// Add (an empty id) or edit an alarm of Settings > Alerts.
pub fn open_alarm(facts: &Value) -> EngineResult<Value> {
    let preferences = get(facts, "preferences")?;
    if !flag(facts, "account")? || preferences.is_null() {
        return steps(Vec::new());
    }
    let list = match alarms(facts)? {
        Value::Array(list) => list,
        _ => Vec::new(),
    };
    let alarm_id = text(facts, "alarm_id")?;
    let found = if alarm_id.is_empty() {
        None
    } else {
        list.iter()
            .find(|item| item.get("id").and_then(Value::as_str) == Some(alarm_id))
    };
    if !alarm_id.is_empty() && found.is_none() {
        return steps(Vec::new());
    }
    let limit = int(facts, "max_alarms")?;
    if found.is_none() && i64::try_from(list.len()).unwrap_or(i64::MAX) >= limit {
        return steps(vec![say(text(facts, "full")?, false)]);
    }
    let tone = or_default(preferences.get("alarm_tone"), "chime");
    let clock_24h = preferences.get("clock_24h") == Some(&json!(true));
    steps(vec![bridge_with(
        "_open_alarm_sheet",
        vec![
            found.cloned().unwrap_or(Value::Null),
            json!(tone),
            json!(clock_24h),
        ],
    )])
}

/// The alarm sheet saves only while it is the sheet that is open.
pub fn save_alarm_gate(facts: &Value) -> EngineResult<Value> {
    Ok(if text(facts, "kind")? == "alarm" {
        json!({"said": SAVED_ALARM})
    } else {
        Value::Null
    })
}

pub fn alarm_full(facts: &Value) -> EngineResult<Value> {
    let count = i64::try_from(array(facts, "alarms")?.len()).unwrap_or(i64::MAX);
    if flag(facts, "existing")? || count < int(facts, "max_alarms")? {
        return Ok(Value::Null);
    }
    steps(vec![
        step(
            "alarm",
            "__setattr__",
            vec![json!("error"), json!(text(facts, "full")?)],
            json!({}),
        ),
        publish(),
    ])
}

fn alarm_not_saved(facts: &Value) -> EngineResult<Vec<Value>> {
    if !flag(facts, "has_alarm")? {
        return Ok(Vec::new());
    }
    Ok(vec![step(
        "alarm",
        "__setattr__",
        vec![json!("error"), json!(text(facts, "not_saved")?)],
        json!({}),
    )])
}

pub fn alarm_written(facts: &Value) -> EngineResult<Value> {
    if flag(facts, "ok")? {
        return steps(vec![bridge("_close"), say(text(facts, "said")?, false)]);
    }
    let mut list = alarm_not_saved(facts)?;
    if !list.is_empty() {
        list.push(publish());
    }
    steps(list)
}

pub fn alarm_refused(facts: &Value) -> EngineResult<Value> {
    if flag(facts, "accepted")? {
        return steps(Vec::new());
    }
    let mut list = alarm_not_saved(facts)?;
    list.push(publish());
    steps(list)
}

/// Delete, on the edit sheet. It asks first.
pub fn remove_alarm(facts: &Value) -> EngineResult<Value> {
    if !flag(facts, "existing")? {
        return steps(Vec::new());
    }
    let name = text(facts, "name")?.trim();
    let name = if name.is_empty() { "this alarm" } else { name };
    let body = format!("Delete {name}? It will not ring again.");
    steps(vec![
        set("_ask", prompt("delete-alarm", "Delete alarm", &body)),
        publish(),
    ])
}

pub fn alarms_without(facts: &Value) -> EngineResult<Value> {
    let id = get(facts, "id")?;
    let left: Vec<Value> = array(facts, "alarms")?
        .iter()
        .filter(|item| item.get("id") != Some(id))
        .cloned()
        .collect();
    Ok(json!({"alarms": left, "said": DELETED_ALARM}))
}

// Saves answering -----------------------------------------------------------------------------

/// The store's answer to a save: the repeat's notice or refusal, the late move waiting for it.
pub fn saved(facts: &Value) -> EngineResult<Value> {
    let (stored, kind) = (flag(facts, "stored")?, text(facts, "kind")?);
    let words = get(facts, "words")?;
    let mut list = Vec::new();
    if truthy(Some(words)) {
        if stored {
            list.push(bridge("_close"));
            list.push(step("bridge", "_say", vec![words.clone()], json!({})));
            list.push(set("_restore_words", words.clone()));
        } else if flag(facts, "has_block")? {
            // The sheet keeps what was typed and the store's sentence; a refused change is taken
            // back, so the week shows what is saved and Save sends a corrected one.
            list.push(session("drop_refused_save", Vec::new(), json!({})));
            list.push(step(
                "block",
                "__setattr__",
                vec![json!("error"), get(facts, "said")?.clone()],
                json!({}),
            ));
            list.push(publish());
        }
    }
    if matches!(kind, "homework" | "block") {
        list.push(publish());
    }
    let waiting = get(facts, "waiting")?;
    if let Value::Array(pair) = waiting {
        let (block_id, message) = match pair.as_slice() {
            [block_id, message] => (block_id, message),
            _ => return Err(EngineError::value("not enough values to unpack")),
        };
        let held = array(facts, "blocks")
            .map(|blocks| blocks.iter().any(|item| item.get("id") == Some(block_id)))?;
        if !stored {
            list.push(set("_late_waiting", Value::Null));
        } else if held {
            list.push(set("_late_waiting", Value::Null));
            list.push(step(
                "bridge",
                "_say",
                vec![message.clone()],
                json!({"undo": true}),
            ));
        }
    }
    steps(list)
}

pub fn busy(facts: &Value) -> EngineResult<Value> {
    if matches!(text(facts, "kind")?, "homework" | "block") {
        return steps(vec![publish()]);
    }
    steps(Vec::new())
}

pub fn preview_edit(facts: &Value) -> EngineResult<Value> {
    let call = text(facts, "call")?;
    if !matches!(call, "check" | "set_day" | "set_start" | "set_duration") {
        return Err(EngineError::value(format!("unknown preview edit: {call}")));
    }
    if text(facts, "kind")? != "preview" || !flag(facts, "has_preview")? {
        return steps(Vec::new());
    }
    steps(vec![
        step("preview", call, array(facts, "args")?.clone(), json!({})),
        publish(),
    ])
}

pub fn preview_gate(facts: &Value) -> EngineResult<Value> {
    Ok(
        if text(facts, "kind")? == "preview" && flag(facts, "can_save")? {
            json!({})
        } else {
            Value::Null
        },
    )
}

// The notice bar ------------------------------------------------------------------------------

fn timer(call: &str, args: Vec<Value>) -> Value {
    step("timer", call, args, json!({}))
}

pub fn say_plan(facts: &Value) -> EngineResult<Value> {
    if !truthy(Some(get(facts, "text")?)) {
        return steps(vec![
            timer("stop", Vec::new()),
            set("_paused", json!(false)),
        ]);
    }
    if flag(facts, "held")? {
        return steps(vec![set("_paused", json!(true)), timer("stop", Vec::new())]);
    }
    steps(vec![
        set("_paused", json!(false)),
        timer("start", vec![json!(NOTICE_MS)]),
    ])
}

pub fn pause(facts: &Value) -> EngineResult<Value> {
    if !flag(facts, "active")? {
        return steps(Vec::new());
    }
    steps(vec![
        set("_remaining_ms", json!(int(facts, "remaining")?.max(0))),
        timer("stop", Vec::new()),
    ])
}

pub fn resume(facts: &Value) -> EngineResult<Value> {
    if !flag(facts, "paused")? {
        return steps(Vec::new());
    }
    let mut list = vec![set("_paused", json!(false))];
    if truthy(Some(get(facts, "notice")?)) {
        list.push(timer(
            "start",
            vec![json!(int(facts, "remaining")?.max(1000))],
        ));
    }
    steps(list)
}

pub fn dismiss(facts: &Value) -> EngineResult<Value> {
    if !truthy(Some(get(facts, "notice")?)) {
        return steps(Vec::new());
    }
    steps(vec![
        set("_notice", json!("")),
        set("_notice_undo", json!(false)),
        set("_notice_restore", json!("")),
        set("_restore_words", json!("")),
        timer("stop", Vec::new()),
        set("_paused", json!(false)),
        set("_held", json!(false)),
        changed(),
    ])
}

pub fn undo(facts: &Value) -> EngineResult<Value> {
    let mut list = Vec::new();
    if flag(facts, "undo")? && flag(facts, "has_session")? {
        let restore = get(facts, "restore")?;
        if truthy(Some(restore)) {
            list.push(session(
                "undo_to_restore_point",
                vec![restore.clone()],
                json!({}),
            ));
        } else {
            list.push(session("undo", Vec::new(), json!({})));
        }
    }
    list.push(bridge("dismissNotice"));
    steps(list)
}

pub fn save_answered(facts: &Value) -> EngineResult<Value> {
    let (point, words) = (get(facts, "point_id")?, get(facts, "restore_words")?);
    let mut list = Vec::new();
    if truthy(Some(point)) && truthy(Some(words)) && get(facts, "notice")? == words {
        list.push(set("_notice_restore", point.clone()));
        list.push(set("_notice_undo", json!(true)));
        list.push(set("_restore_words", json!("")));
        list.push(changed());
    }
    let doubled = get(facts, "doubled")?;
    if truthy(Some(doubled)) {
        let weeks: Vec<Value> = doubled
            .as_array()
            .ok_or_else(|| type_error("sheet facts: doubled must be a list"))?
            .iter()
            .map(|week| json!(py_str(week)))
            .collect();
        list.push(set("_doubled_waiting", Value::Array(weeks)));
        list.push(bridge("_show_doubled"));
    }
    steps(list)
}

/// The doubled-weeks prompt, once no other question is up; it never replaces one.
pub fn doubled(facts: &Value) -> EngineResult<Value> {
    let waiting = get(facts, "weeks")?;
    if waiting.is_null() || ask_is_open(facts)? {
        return steps(Vec::new());
    }
    let weeks: Vec<String> = waiting
        .as_array()
        .ok_or_else(|| type_error("sheet facts: weeks must be a list"))?
        .iter()
        .map(|week| week.as_str().map(str::to_string))
        .collect::<Option<_>>()
        .ok_or_else(|| type_error("sheet facts: weeks must hold text"))?;
    let name = or_default(Some(get(facts, "name")?), "This fixed time");
    let when = if weeks.len() == 1 {
        "a later week"
    } else {
        "later weeks"
    };
    let ask = json!({
        "id": "doubled-weeks",
        "title": format!("{name} is already in {when}"),
        "body": doubled_words(&name, &weeks, text(facts, "today")?)?,
        "answers": [{"id": "ok", "label": "OK", "kind": "tonal"}],
    });
    steps(vec![
        set("_doubled_waiting", Value::Null),
        set("_ask", ask),
        changed(),
    ])
}

pub fn refresh(facts: &Value) -> EngineResult<Value> {
    let shows_session = matches!(
        text(facts, "kind")?,
        "late" | "unfinished" | "weekList" | "routines" | "account" | "restore" | "preview"
    );
    steps(if shows_session {
        vec![publish()]
    } else {
        Vec::new()
    })
}

/// Which bridge method builds the open sheet's form.
pub fn form_source(facts: &Value) -> EngineResult<Value> {
    let has = |key: &str| flag(facts, key);
    let source = match text(facts, "kind")? {
        "homework" if has("homework")? => "_form_homework",
        "block" if has("block")? => "_form_block",
        "late" => "_form_late",
        "unfinished" => "_form_unfinished",
        "weekList" => "_form_week_list",
        "preview" if has("preview")? => "_form_preview",
        "routines" => "_form_routines",
        "alarm" if has("alarm")? => "_form_alarm",
        "help" => "_form_help",
        "about" => "_form_about",
        "update" if has("update")? => "_form_update",
        "account" => "_form_account",
        "restore" => "_form_restore",
        _ => "_form_none",
    };
    Ok(json!(source))
}

/// The moved-day note is said aloud when it appears or changes in a sheet that is already open. A
/// sheet that opens with it is read with the note, and one that clears it says nothing.
pub fn note_edge(facts: &Value) -> EngineResult<Value> {
    let moved = get(facts, "moved")?;
    let when_moved = get(facts, "when_moved")?;
    let note = if truthy(Some(moved)) {
        py_str(moved)
    } else {
        or_default(Some(when_moved), "")
    };
    let mut list = Vec::new();
    let noted = get(facts, "noted")?;
    if !note.is_empty() && noted.as_str().is_some_and(|before| before != note) {
        list.push(bridge_with("_announce", vec![json!(note)]));
    }
    list.push(set("_noted", json!(note)));
    steps(list)
}

pub fn drag_range(facts: &Value) -> EngineResult<Value> {
    let active = flag(facts, "active")?;
    if flag(facts, "current")? == active {
        return steps(Vec::new());
    }
    steps(vec![set("_drag_range_active", json!(active)), changed()])
}

pub fn more_source(facts: &Value) -> EngineResult<Value> {
    Ok(json!(if flag(facts, "more")? {
        "_more_entries"
    } else {
        "_no_entries"
    }))
}
