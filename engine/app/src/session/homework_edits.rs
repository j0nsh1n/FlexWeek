//! What the session decides when homework is saved from the window, finished or reopened, or unpinned (P4
//! slice 4A): the rules of `desktop/native/controller.py`'s `add_homework`, `_fix_session`,
//! `unpin_assignment` and `complete_homework`, moved here with the same words. The window keeps the
//! state: it writes what is decided here, then settles the week (`_touch`), which this module does not.
//!
//! `desk::homework::edit_homework` is not reused. It settles the week itself, copies none of the three
//! server counts, and makes the new session as long as the estimate; the window does none of the three.

use flexweek_engine::desk::planning::{available_homework_minutes, session_days};
use flexweek_engine::stored::truthy;
use flexweek_service::blocks::check_block;
use flexweek_service::homework_saves::check_homework;
use serde_json::{Map, Value, json};

/// The fields a homework save keeps from what the window hands over (the engine's `homework_fields`).
fn homework_fields() -> Vec<&'static str> {
    let mut fields = flexweek_engine::validate::ASSIGNMENT_FIELDS.to_vec();
    fields.push("revision");
    fields
}

/// What `edit_homework` needs: the week as it stands, the homework by id, the block snapshot the server's
/// counts were read with, and what the student changed.
pub struct HomeworkEditInput<'a> {
    pub blocks: &'a [Value],
    pub assignments: &'a Map<String, Value>,
    /// The blocks the server's counts match (`_assignments_basis`), or `None` before the first read.
    pub basis: Option<&'a [Value]>,
    /// The homework as the dialog holds it, `fixed_at` included when the student touched the pin.
    pub assignment: &'a Value,
    pub week_start: &'a str,
    /// The days a lone waiting session may go on, when the caller names them.
    pub days: Option<&'a [i64]>,
    /// Drop every open time and make none, for Spread to write the sessions that replace them.
    pub spread: bool,
    /// The id a new session gets.
    pub new_session_id: &'a str,
}

#[derive(Debug, PartialEq)]
pub struct HomeworkEdit {
    /// The homework to keep, checked, with the server's counts still beside it.
    pub assignment: Value,
    pub blocks: Vec<Value>,
    /// Every session of this homework after the edit: the ones the week settling must leave where they are.
    pub changed_ids: Vec<String>,
    /// The sessions pinned by this edit, whose "needs a time" note the window drops.
    pub pinned_ids: Vec<String>,
    pub label: String,
}

impl HomeworkEdit {
    pub fn to_json(&self) -> Value {
        json!({
            "assignment": self.assignment,
            "blocks": self.blocks,
            "changed": self.changed_ids,
            "pinned": self.pinned_ids,
            "label": self.label,
        })
    }
}

fn not_an_object(value: &Value) -> String {
    format!(
        "'{}' object has no attribute 'get'",
        flexweek_engine::stored::type_name(value)
    )
}

/// Python's `==` for two stored values: 60 and 60.0 are the same number.
fn same(left: Option<&Value>, right: Option<&Value>) -> bool {
    match (left, right) {
        (Some(Value::Number(a)), Some(Value::Number(b))) => a.as_f64() == b.as_f64(),
        _ => left == right,
    }
}

/// `known.get(key) or 0`.
fn or_zero(known: &Value, key: &str) -> Value {
    match known.get(key) {
        found @ Some(_) if truthy(found) => found.cloned().unwrap_or(json!(0)),
        _ => json!(0),
    }
}

/// Pin `session` at the day and start the student chose with "Do it at", or with `Null` let FlexWeek move
/// it again, as "Let FlexWeek pick a time" does. Returns whether a pin was written.
fn fix_session(session: &mut Map<String, Value>, fixed_at: &Value) -> Result<bool, String> {
    if fixed_at.is_null() {
        session.shift_remove("pinned");
        return Ok(false);
    }
    let fields = fixed_at.as_object().ok_or_else(|| {
        format!(
            "'{}' object is not subscriptable",
            flexweek_engine::stored::type_name(fixed_at)
        )
    })?;
    let start = fields.get("start").cloned().ok_or("'start'")?;
    let day = fields.get("day").cloned().ok_or("'day'")?;
    session.insert("start".into(), start);
    session.insert("days".into(), json!([day]));
    session.insert("pinned".into(), json!(true));
    Ok(true)
}

fn checked_session(session: Map<String, Value>) -> Result<Value, String> {
    check_block(&Value::Object(session)).map_err(|refused| refused.0)
}

/// The homework body the window keeps: checked as a save is, the focus counters and revision of the copy
/// already known (a dialog left open across a focus credit holds an older one), and its session weeks and
/// server counts carried over.
fn homework_body(input: &HomeworkEditInput, known: Option<&Value>) -> Result<Value, String> {
    let source = input
        .assignment
        .as_object()
        .ok_or_else(|| not_an_object(input.assignment))?;
    let mut payload = Map::new();
    for key in homework_fields() {
        if let Some(value) = source.get(key) {
            payload.insert(key.to_string(), value.clone());
        }
    }
    if !payload.contains_key("revision") {
        payload.insert("revision".into(), json!(0));
    }
    if let Some(known) = known {
        for key in ["revision", "focus_minutes", "focus_sessions"] {
            payload.insert(key.to_string(), or_zero(known, key));
        }
    }
    let (content, revision) =
        check_homework(&Value::Object(payload)).map_err(|refused| refused.0)?;
    let mut body = match content {
        Value::Object(fields) => fields,
        other => return Err(not_an_object(&other)),
    };
    body.insert("revision".into(), json!(revision));
    if let Some(known) = known {
        let weeks = match known.get("session_weeks") {
            Some(Value::Array(items)) => Value::Array(items.clone()),
            _ => json!([]),
        };
        body.insert("session_weeks".into(), weeks);
        for key in ["planned_min", "unplanned_min", "done_min"] {
            if let Some(value) = known.get(key) {
                body.insert(key.to_string(), value.clone());
            }
        }
    }
    Ok(Value::Object(body))
}

fn new_session(
    input: &HomeworkEditInput,
    body: &Value,
    length: i64,
    pinned: &mut Vec<String>,
) -> Result<Value, String> {
    let days = match input.days {
        Some(given) => json!(given),
        None => json!(session_days(input.week_start, &body["due"]).map_err(|error| error.message)?),
    };
    let mut session = Map::new();
    session.insert("id".into(), json!(input.new_session_id));
    session.insert("title".into(), body["title"].clone());
    session.insert("kind".into(), json!("flexible"));
    session.insert("duration_min".into(), json!(length));
    session.insert("days".into(), days);
    session.insert("priority".into(), body["priority"].clone());
    session.insert("energy".into(), body["energy"].clone());
    session.insert("assignment_id".into(), body["id"].clone());
    session.insert(
        "category".into(),
        body.get("category").cloned().unwrap_or(Value::Null),
    );
    if let Some(fixed_at) = input.assignment.get("fixed_at")
        && truthy(Some(fixed_at))
        && fix_session(&mut session, fixed_at)?
    {
        pinned.push(input.new_session_id.to_string());
    }
    checked_session(session)
}

/// Save `assignment` and keep its sessions in step: the title, priority, energy and category follow it, a
/// lone whole session follows a new estimate, a homework with nothing placed gets a session for what is
/// still to place of it, and finishing or reopening it follows into its sessions.
pub fn edit_homework(input: &HomeworkEditInput) -> Result<HomeworkEdit, String> {
    let known = input
        .assignment
        .get("id")
        .and_then(Value::as_str)
        .and_then(|id| input.assignments.get(id));
    let body = homework_body(input, known)?;
    let body_id = body["id"].clone();
    let linked = |block: &Value| block.get("assignment_id") == Some(&body_id);

    let sessions = input.blocks.iter().filter(|block| linked(block)).count();
    let lone = input.blocks.iter().find(|block| linked(block));
    // A session ticked done keeps its length: it is time done, and done time counts in every count.
    let whole = !input.spread
        && sessions == 1
        && known.is_some()
        && lone.is_some_and(|block| {
            !truthy(block.get("completed"))
                && same(
                    block.get("duration_min"),
                    known.and_then(|item| item.get("estimate_min")),
                )
        });

    let mut pinned = Vec::new();
    let mut out: Vec<Value> = Vec::new();
    for block in input.blocks {
        if !linked(block) {
            out.push(block.clone());
            continue;
        }
        if input.spread && !truthy(block.get("completed")) {
            continue;
        }
        let mut session = block
            .as_object()
            .cloned()
            .ok_or_else(|| not_an_object(block))?;
        session.insert("title".into(), body["title"].clone());
        if whole {
            session.insert("duration_min".into(), body["estimate_min"].clone());
        }
        session.insert("priority".into(), body["priority"].clone());
        session.insert("energy".into(), body["energy"].clone());
        if let Some(category) = body.get("category")
            && !category.is_null()
        {
            session.insert("category".into(), category.clone());
        }
        if let Some(days) = input.days
            && sessions == 1
            && !truthy(session.get("start"))
        {
            session.insert("days".into(), json!(days));
        }
        if let Some(fixed_at) = input.assignment.get("fixed_at")
            && !truthy(session.get("completed"))
            && fix_session(&mut session, fixed_at)?
            && let Some(id) = session.get("id").and_then(Value::as_str)
        {
            pinned.push(id.to_string());
        }
        out.push(checked_session(session)?);
    }

    // A homework already known gets a session for what is still to place of it, by the one count (its done
    // time and later weeks' sessions off), and none when nothing is: a new one gets its estimate.
    let length = match known {
        Some(_) => {
            let basis = input.basis.map_or(Value::Null, |blocks| json!(blocks));
            available_homework_minutes(&body, &Value::Array(out.clone()), &basis)
                .map_err(|error| error.message)?
        }
        None => body["estimate_min"]
            .as_i64()
            .ok_or("'estimate_min' is not a whole number")?,
    };
    if sessions == 0 && !input.spread && length > 0 {
        out.push(new_session(input, &body, length, &mut pinned)?);
    }

    let finished = truthy(body.get("completed"));
    let title = body["title"].as_str().unwrap_or_default();
    let mut label = format!(
        "{}{title}",
        if known.is_some() {
            "editing "
        } else {
            "adding "
        }
    );
    if known.is_some_and(|item| finished != truthy(item.get("completed"))) {
        label = format!(
            "{}{title}",
            if finished { "finishing " } else { "reopening " }
        );
        for session in &mut out {
            if session.get("assignment_id") != Some(&body_id) {
                continue;
            }
            let Some(fields) = session.as_object_mut() else {
                continue;
            };
            fields.insert("completed".into(), Value::Bool(finished));
            let days = fields.get("days").and_then(Value::as_array);
            let one_day = days.is_some_and(|days| days.len() == 1);
            let first = days.and_then(|days| days.first()).cloned();
            if finished
                && fields.get("kind") == Some(&json!("flexible"))
                && truthy(fields.get("start"))
            {
                if one_day {
                    fields.insert("completed_day".into(), first.unwrap_or(Value::Null));
                }
            } else if !finished {
                fields.shift_remove("completed_day");
            }
        }
    }

    let mut changed_ids: Vec<String> = Vec::new();
    for block in out.iter().filter(|block| linked(block)) {
        if let Some(id) = block.get("id").and_then(Value::as_str)
            && !changed_ids.iter().any(|seen| seen == id)
        {
            changed_ids.push(id.to_string());
        }
    }
    Ok(HomeworkEdit {
        assignment: body,
        blocks: out,
        changed_ids,
        pinned_ids: pinned,
        label,
    })
}

/// The blocks with the pin taken off every session of the homework, so FlexWeek may move them again; `None`
/// when none was pinned.
pub fn unpin_homework(blocks: &[Value], assignment_id: &str) -> Option<Vec<Value>> {
    let mut changed = false;
    let after = blocks
        .iter()
        .map(|block| {
            let pinned = block.get("assignment_id").and_then(Value::as_str) == Some(assignment_id)
                && truthy(block.get("pinned"));
            match block.as_object() {
                Some(fields) if pinned => {
                    changed = true;
                    let mut fields = fields.clone();
                    fields.shift_remove("pinned");
                    Value::Object(fields)
                }
                _ => block.clone(),
            }
        })
        .collect();
    changed.then_some(after)
}

/// The homework as it is saved when finished (`completed` true) or reopened: a finished one keeps the stamp
/// it already has, or gets `stamp`; a reopened one has none.
pub fn completed_homework(known: &Value, completed: bool, stamp: &str) -> Result<Value, String> {
    let mut body = known
        .as_object()
        .cloned()
        .ok_or_else(|| not_an_object(known))?;
    let stamped = if completed {
        match body.get("completed_at") {
            Some(kept) if truthy(Some(kept)) => kept.clone(),
            _ => json!(stamp),
        }
    } else {
        Value::Null
    };
    body.insert("completed".into(), Value::Bool(completed));
    body.insert("completed_at".into(), stamped);
    Ok(Value::Object(body))
}
