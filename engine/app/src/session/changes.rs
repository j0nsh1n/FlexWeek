//! Build a changes request from the draft and decide how to send it. The window owns the draft,
//! holds the built request for retries, and applies the answer.

use std::collections::BTreeMap;

use flexweek_engine::desk::history::{revision_after_deletes, same_value};
use flexweek_engine::repeats::{Intent, intents_between};
use flexweek_engine::shown::stored_weeks;
use flexweek_engine::validate::{ASSIGNMENT_FIELDS, whole_number};
use flexweek_engine::{EngineError, EngineResult};
use flexweek_service::{blocks, homework_saves};
use serde_json::{Map, Value, json};

pub fn assignment_write(id: &str, item: Option<&Value>, revision: i64) -> EngineResult<Value> {
    let assignment = item
        .map(|item| {
            let fields = object(item, "homework")?;
            let content = fields
                .iter()
                .filter(|(key, _)| {
                    key.as_str() == "revision" || ASSIGNMENT_FIELDS.contains(&key.as_str())
                })
                .map(|(key, value)| (key.clone(), value.clone()))
                .collect();
            homework_saves::check_homework(&Value::Object(content))
                .map(|(body, _)| body)
                .map_err(|error| EngineError::value(error.0))
        })
        .transpose()?;
    Ok(json!({"id": id, "assignment": assignment, "revision": revision}))
}

pub fn week_write(week_start: &str, rows: &[Value], revision: &Value) -> EngineResult<Value> {
    check_revision(revision)?;
    let blocks = rows
        .iter()
        .map(|row| blocks::check_block(row).map_err(|error| EngineError::value(error.0)))
        .collect::<EngineResult<Vec<_>>>()?;
    Ok(json!({"week_start": week_start, "blocks": blocks, "revision": revision}))
}

pub struct SaveDraft<'a> {
    pub week_start: &'a str,
    pub blocks: &'a [Value],
    pub revision: &'a Value,
    pub committed_blocks: &'a [Value],
    pub assignments: &'a Map<String, Value>,
    pub committed_assignments: &'a Map<String, Value>,
    pub dirty_assignments: &'a [String],
    pub travel_weeks: &'a [Value],
    pub undo: bool,
    pub stored_parts: &'a [Value],
    pub saved_repeats: &'a [Value],
    pub repeats: &'a [Value],
    pub queued_repeats: &'a [Value],
}

fn object<'a>(value: &'a Value, name: &str) -> EngineResult<&'a Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| EngineError::value(format!("{name} must be an object")))
}

fn date_of(value: &Value) -> EngineResult<&str> {
    value["week_start"]
        .as_str()
        .ok_or_else(|| EngineError::value("week_start must be text"))
}

fn rows<'a>(value: &'a Value, key: &str) -> EngineResult<&'a [Value]> {
    value[key]
        .as_array()
        .map(Vec::as_slice)
        .ok_or_else(|| EngineError::value(format!("{key} must be a list")))
}

fn check_revision(revision: &Value) -> EngineResult<()> {
    if revision.is_i64()
        || matches!(revision.as_array().map(Vec::as_slice), Some([first, second]) if first.is_i64() && second.is_i64())
    {
        Ok(())
    } else {
        Err(EngineError::value(
            "revision must be an integer or two stored-week revisions",
        ))
    }
}

fn assignment_revision(source: Option<&Value>) -> EngineResult<i64> {
    match source.and_then(|item| item.get("revision")) {
        None | Some(Value::Null) => Ok(0),
        Some(Value::String(text)) if text.is_empty() => Ok(0),
        Some(value) => whole_number(value)
            .and_then(|number| i64::try_from(number).ok())
            .ok_or_else(|| EngineError::value("assignment revision must be a whole number")),
    }
}

/// The request kept until acknowledgment, including any local navigation metadata.
pub fn freeze_save(
    draft: &SaveDraft<'_>,
    operation_id: &str,
    snapshot_label: Option<&str>,
) -> EngineResult<Value> {
    let mut dirty: Vec<&String> = draft.dirty_assignments.iter().collect();
    dirty.sort_unstable();
    let mut assignments = Vec::with_capacity(dirty.len());
    let mut deleted = Vec::new();
    for id in dirty {
        let item = draft.assignments.get(id);
        let source = item.or_else(|| draft.committed_assignments.get(id));
        let revision = assignment_revision(source)?;
        assignments.push(assignment_write(id, item, revision)?);
        if item.is_none() {
            deleted.push(id.clone());
        }
    }

    let mut extra = Vec::new();
    for week in draft.travel_weeks {
        let date = date_of(week)?;
        if date != draft.week_start {
            extra.push((date, week));
        }
    }
    let traveling = !extra.is_empty();
    check_revision(draft.revision)?;
    let revision = if traveling {
        draft.revision.clone()
    } else {
        revision_after_deletes(draft.committed_blocks, draft.revision, &deleted)?
    };
    let mut weeks = vec![week_write(draft.week_start, draft.blocks, &revision)?];
    if traveling {
        let mut live = BTreeMap::new();
        for part in draft.stored_parts {
            live.insert(date_of(part)?, part);
        }
        let side = if draft.undo { "before" } else { "after" };
        for (date, week) in extra {
            let revision = if let Some(part) = live.get(date) {
                check_revision(&part["revision"])?;
                revision_after_deletes(rows(part, "blocks")?, &part["revision"], &deleted)?
            } else {
                week["revision"].clone()
            };
            weeks.push(week_write(date, rows(week, side)?, &revision)?);
        }
    }

    let mut request =
        json!({"weeks": weeks, "assignments": assignments, "operation_id": operation_id});
    if traveling {
        request["stay"] = json!(true);
    } else {
        let repeats = if draft.queued_repeats.is_empty() {
            intents_between(draft.saved_repeats, draft.repeats, draft.week_start)
                .iter()
                .map(Intent::to_value)
                .collect()
        } else {
            draft.queued_repeats.to_vec()
        };
        if !repeats.is_empty() {
            request["repeats"] = Value::Array(repeats);
        }
    }
    if let Some(label) = snapshot_label.filter(|label| !label.is_empty()) {
        request["snapshot_label"] = json!(label);
    }
    Ok(request)
}

/// Python's dict equality ignores key order. A retry with the same request keeps the original ID,
/// even if the store already received it and only its reply was lost.
pub fn retry_needs_new_id(previous: &Value, rebuilt: &Value) -> bool {
    !same_value(previous, rebuilt)
}

/// The wire body and the week to open afterward. `written` is in the host's set iteration order.
pub fn prepare_post(
    mut request: Map<String, Value>,
    written: &[String],
    week_start: &str,
    shifted_week: bool,
) -> EngineResult<(Value, Option<String>)> {
    let stay = match request.shift_remove("stay") {
        None | Some(Value::Null) => false,
        Some(Value::Bool(stay)) => stay,
        _ => return Err(EngineError::value("stay must be a boolean")),
    };
    let shown_parts = if shifted_week {
        stored_weeks(week_start)?
    } else {
        Vec::new()
    };
    let keeps_week = stay
        || written
            .iter()
            .any(|week| week == week_start || shown_parts.contains(week));
    let destination = if keeps_week {
        None
    } else {
        written.first().cloned()
    };
    Ok((Value::Object(request), destination))
}

#[derive(Debug, PartialEq, Eq)]
pub enum SaveFailureKind {
    Unreachable,
    Conflict,
    Refused,
}

#[derive(Debug, PartialEq, Eq)]
pub struct SaveFailure {
    pub kind: SaveFailureKind,
    pub words: String,
}

pub fn classify_failure(status: i64, message: &str) -> SaveFailure {
    let kind = match status {
        0 => SaveFailureKind::Unreachable,
        409 => SaveFailureKind::Conflict,
        _ => SaveFailureKind::Refused,
    };
    let words = if kind == SaveFailureKind::Unreachable {
        "Not saved: FlexWeek can't be reached. Your changes are still here. Choose Retry save."
            .into()
    } else {
        format!("Not saved. {message}")
    };
    SaveFailure { kind, words }
}
