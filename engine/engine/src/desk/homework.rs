//! Homework edits from `desktop/native/controller.py` `add_homework` (956-1033),
//! `_fix_session` (1035-1041) and `_touch` (906-929).

use serde_json::{Map, Value, json};

use super::planning;
use crate::model;
use crate::stored::{truthy, type_name};
use crate::validate::{assignment_content, time_block};

const JS_INT_MAX: i64 = (1_i64 << 53) - 1;

const ASSIGNMENT_FIELDS: &[&str] = &[
    "id",
    "title",
    "course",
    "category",
    "priority",
    "energy",
    "spotify_url",
    "due",
    "estimate_min",
    "spread",
    "focus_minutes",
    "focus_sessions",
    "completed",
    "completed_at",
    "notes",
    "links",
    "checklist",
    "revision",
];

pub struct HomeworkEdit {
    pub blocks: Vec<Value>,
    pub assignment: Value,
    pub label: String,
    pub lost: Vec<Value>,
}

pub fn edit_homework(
    blocks: &[Value],
    assignments: &Map<String, Value>,
    week_start: &str,
    assignment: &Value,
    days: Option<&[i64]>,
    spread: bool,
    new_session_id: &str,
    today: &str,
    now_minute: i64,
) -> Result<HomeworkEdit, String> {
    let mut payload = payload_from(assignment)?;
    let known = payload
        .get("id")
        .and_then(Value::as_str)
        .and_then(|id| assignments.get(id))
        .cloned();
    if let Some(known) = &known {
        for key in ["revision", "focus_minutes", "focus_sessions"] {
            payload.insert(key.to_string(), or_zero(known.get(key)));
        }
    }
    let revision = checked_revision(&payload.shift_remove("revision").unwrap_or(json!(0)))?;
    let content = assignment_content(&Value::Object(payload))?;
    let mut body_map = match content.to_value() {
        Value::Object(map) => map,
        other => {
            return Err(format!(
                "'{}' object has no attribute 'get'",
                type_name(&other)
            ));
        }
    };
    body_map.insert("revision".into(), json!(revision));
    if let Some(known) = &known {
        body_map.insert("session_weeks".into(), copied_weeks(known));
    }
    let body = Value::Object(body_map);
    let body_id = body.get("id").cloned().unwrap_or(Value::Null);

    let sessions: Vec<&Value> = blocks
        .iter()
        .filter(|block| block.get("assignment_id") == Some(&body_id))
        .collect();
    let whole = !spread
        && sessions.len() == 1
        && known.is_some()
        && sessions[0].get("duration_min")
            == known.as_ref().and_then(|item| item.get("estimate_min"));

    let mut out = Vec::new();
    for block in blocks {
        if block.get("assignment_id") != Some(&body_id) {
            out.push(block.clone());
            continue;
        }
        if spread && !truthy(block.get("completed")) {
            continue;
        }
        let Some(mut session) = block.as_object().cloned() else {
            return Err(format!(
                "'{}' object has no attribute 'get'",
                type_name(block)
            ));
        };
        copy_field(&mut session, &body, "title");
        if whole && let Some(estimate) = body.get("estimate_min") {
            session.insert("duration_min".into(), estimate.clone());
        }
        copy_field(&mut session, &body, "priority");
        copy_field(&mut session, &body, "energy");
        if let Some(category) = body.get("category")
            && !category.is_null()
        {
            session.insert("category".into(), category.clone());
        }
        if let Some(days) = days
            && sessions.len() == 1
            && !truthy(session.get("start"))
        {
            session.insert("days".into(), json!(days));
        }
        if let Some(fixed_at) = assignment.get("fixed_at")
            && !truthy(session.get("completed"))
        {
            fix_session(&mut session, fixed_at)?;
        }
        out.push(dump_session(session)?);
    }
    if sessions.is_empty() && !spread {
        out.push(new_session(
            &body,
            &body_id,
            assignment,
            days,
            week_start,
            new_session_id,
        )?);
    }

    let finished = truthy(body.get("completed"));
    let title = match body.get("title") {
        Some(Value::String(text)) => text.clone(),
        _ => String::new(),
    };
    let mut label = format!(
        "{}{title}",
        if known.is_some() {
            "editing "
        } else {
            "adding "
        }
    );
    if known
        .as_ref()
        .is_some_and(|item| finished != truthy(item.get("completed")))
    {
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
            let one_day = fields
                .get("days")
                .and_then(Value::as_array)
                .is_some_and(|days| days.len() == 1);
            if finished
                && fields.get("kind") == Some(&json!("flexible"))
                && truthy(fields.get("start"))
                && one_day
            {
                let day = fields
                    .get("days")
                    .and_then(Value::as_array)
                    .and_then(|days| days.first())
                    .cloned()
                    .unwrap_or(Value::Null);
                fields.insert("completed_day".into(), day);
            } else if !finished {
                fields.shift_remove("completed_day");
            }
        }
    }

    let mut table = assignments.clone();
    if let Some(id) = body_id.as_str() {
        table.insert(id.to_string(), body.clone());
    }
    let overdue = overdue_ids(&table, today, now_minute)?;
    let mut keep = Vec::new();
    let mut after_deadline = Vec::new();
    for block in &out {
        let link = block.get("assignment_id").and_then(Value::as_str);
        if link == body_id.as_str()
            && let Some(id) = block.get("id")
        {
            keep.push(id.clone());
        }
        if truthy(block.get("start"))
            && link.is_some_and(|id| overdue.iter().any(|item| item == id))
            && let Some(id) = block.get("id")
        {
            after_deadline.push(id.clone());
        }
    }
    let (settled, lost) = planning::settle_placements_after_deadline(
        &Value::Array(out),
        &Value::Object(table),
        week_start,
        &Value::Array(keep),
        true,
        &Value::Array(after_deadline),
    )
    .map_err(|err| err.message)?;
    let cleared = planning::clear_stale_pins(&settled).map_err(|err| err.message)?;
    Ok(HomeworkEdit {
        blocks: cleared,
        assignment: body,
        label,
        lost,
    })
}

fn payload_from(assignment: &Value) -> Result<Map<String, Value>, String> {
    let source = assignment.as_object().ok_or_else(|| {
        format!(
            "'{}' object has no attribute 'items'",
            type_name(assignment)
        )
    })?;
    let mut payload = Map::new();
    for key in ASSIGNMENT_FIELDS {
        if let Some(value) = source.get(*key) {
            payload.insert((*key).to_string(), value.clone());
        }
    }
    if !payload.contains_key("revision") {
        payload.insert("revision".into(), json!(0));
    }
    Ok(payload)
}

fn or_zero(value: Option<&Value>) -> Value {
    if truthy(value) {
        value.cloned().unwrap_or(json!(0))
    } else {
        json!(0)
    }
}

fn checked_revision(value: &Value) -> Result<i64, String> {
    let Some(number) = value.as_i64() else {
        if value.as_f64().is_some() {
            return Err(
                "Input should be a valid integer, got a number with a fractional part".into(),
            );
        }
        return Err("Input should be a valid integer".into());
    };
    if number < 0 {
        return Err("Input should be greater than or equal to 0".into());
    }
    if number > JS_INT_MAX {
        return Err(format!(
            "Input should be less than or equal to {JS_INT_MAX}"
        ));
    }
    Ok(number)
}

fn copied_weeks(known: &Value) -> Value {
    match known.get("session_weeks") {
        Some(Value::Array(items)) if !items.is_empty() => Value::Array(items.clone()),
        _ => json!([]),
    }
}

fn copy_field(session: &mut Map<String, Value>, body: &Value, key: &str) {
    if let Some(value) = body.get(key) {
        session.insert(key.to_string(), value.clone());
    }
}

fn fix_session(session: &mut Map<String, Value>, fixed_at: &Value) -> Result<(), String> {
    if fixed_at.is_null() {
        session.shift_remove("pinned");
        return Ok(());
    }
    let fields = fixed_at
        .as_object()
        .ok_or_else(|| format!("'{}' object is not subscriptable", type_name(fixed_at)))?;
    let start = fields
        .get("start")
        .cloned()
        .ok_or_else(|| "'start'".to_string())?;
    let day = fields
        .get("day")
        .cloned()
        .ok_or_else(|| "'day'".to_string())?;
    session.insert("start".into(), start);
    session.insert("days".into(), json!([day]));
    session.insert("pinned".into(), json!(true));
    Ok(())
}

fn dump_session(session: Map<String, Value>) -> Result<Value, String> {
    Ok(time_block(&Value::Object(session))?.to_value())
}

fn new_session(
    body: &Value,
    body_id: &Value,
    assignment: &Value,
    days: Option<&[i64]>,
    week_start: &str,
    new_session_id: &str,
) -> Result<Value, String> {
    let mut session = Map::new();
    session.insert("id".into(), json!(new_session_id));
    copy_field(&mut session, body, "title");
    session.insert("kind".into(), json!("flexible"));
    if let Some(estimate) = body.get("estimate_min") {
        session.insert("duration_min".into(), estimate.clone());
    }
    let day_list = match days {
        Some(given) => Value::Array(given.iter().copied().map(Value::from).collect()),
        None => {
            let due = body.get("due").cloned().unwrap_or(Value::Null);
            let listed = planning::session_days(week_start, &due).map_err(|err| err.message)?;
            Value::Array(listed.into_iter().map(Value::from).collect())
        }
    };
    session.insert("days".into(), day_list);
    copy_field(&mut session, body, "priority");
    copy_field(&mut session, body, "energy");
    session.insert("assignment_id".into(), body_id.clone());
    session.insert(
        "category".into(),
        body.get("category").cloned().unwrap_or(Value::Null),
    );
    if let Some(fixed_at) = assignment.get("fixed_at")
        && truthy(Some(fixed_at))
    {
        fix_session(&mut session, fixed_at)?;
    }
    dump_session(session)
}

fn overdue_ids(
    assignments: &Map<String, Value>,
    today: &str,
    now_minute: i64,
) -> Result<Vec<String>, String> {
    let today_day = model::iso_day(today).map_err(|err| err.message)?;
    let mut ids = Vec::new();
    for (key, item) in assignments {
        if !truthy(item.get("due")) || truthy(item.get("completed")) {
            continue;
        }
        let Some(due) = item.get("due").and_then(Value::as_str) else {
            return Err(
                "must be YYYY-MM-DD or YYYY-MM-DDTHH:MM with no seconds or timezone".into(),
            );
        };
        let (due_day, due_minute) = model::parse_due(due).map_err(|err| err.message)?;
        if (due_day, due_minute) <= (today_day, now_minute) {
            ids.push(key.clone());
        }
    }
    Ok(ids)
}
