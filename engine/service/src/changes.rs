//! The app's one save for an action that touches several things at once, as `backend/app.py`'s
//! `POST /api/changes` does it: homework saved and deleted, weeks written (a Monday is one stored week; a
//! week on screen from another day covers two), School and Setup's activities changed from a week on, and
//! a restore point made first when the save asks for one. All of it commits together or not at all, and a
//! save sent again with its operation id gets the first answer back.

use std::path::Path;

use flexweek_engine::time::{is_calendar_date, is_week_start};
use flexweek_engine::validate::{assignment_content, week_request, whole_number};
use flexweek_store::{self as store};
use serde_json::{Map, Value, json};

use crate::accounts::INVALID_INPUT;
use crate::blocks::{BlockRefused, Checked, refuse};
use crate::{Refusal, ServiceError, ServiceResult, with_db};

const REVISION_MAX: i128 = (1 << 53) - 1;
/// One save can stop every repeat and add as many new ones (`backend/app.py`'s `MAX_REPEAT_CHANGES`).
const MAX_REPEAT_CHANGES: usize = 2 * flexweek_engine::repeats::MAX_REPEATS;

/// A week the save writes, as `ChangedWeek` reads it.
#[derive(Debug, Clone)]
pub struct ChangedWeek {
    pub week_start: String,
    pub blocks: Vec<Value>,
    /// One revision for a Monday; a week on screen from another day names the two stored weeks it covers.
    pub revision: Revision,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Revision {
    Stored(i64),
    Shown(i64, i64),
}

/// A homework the save writes (`assignment` set) or deletes, as `AssignmentChange` reads it.
#[derive(Debug, Clone)]
pub struct HomeworkChange {
    pub id: String,
    pub assignment: Option<Value>,
    pub revision: i64,
}

/// The save as `ChangesRequest` reads it.
#[derive(Debug, Clone)]
pub struct ChangesRequest {
    pub weeks: Vec<ChangedWeek>,
    pub assignments: Vec<HomeworkChange>,
    pub operation_id: Option<String>,
    pub snapshot_label: Option<String>,
    pub repeats: Option<Vec<Value>>,
}

impl ChangesRequest {
    /// The request as `ChangesRequest.model_dump()` writes it; its digest keys the remembered answer.
    pub fn to_value(&self) -> Value {
        let weeks: Vec<Value> = self
            .weeks
            .iter()
            .map(|week| {
                let revision = match week.revision {
                    Revision::Stored(revision) => json!(revision),
                    Revision::Shown(first, second) => json!([first, second]),
                };
                json!({ "blocks": week.blocks, "week_start": week.week_start, "revision": revision })
            })
            .collect();
        let assignments: Vec<Value> = self
            .assignments
            .iter()
            .map(|change| {
                json!({ "id": change.id, "assignment": change.assignment, "revision": change.revision })
            })
            .collect();
        json!({
            "weeks": weeks,
            "assignments": assignments,
            "operation_id": self.operation_id,
            "snapshot_label": self.snapshot_label,
            "repeats": self.repeats,
        })
    }
}

fn object<'a>(value: &'a Value, what: &str) -> Checked<&'a Map<String, Value>> {
    match value {
        Value::Object(fields) => Ok(fields),
        _ => refuse(format!("{what} must be an object")),
    }
}

fn only(fields: &Map<String, Value>, allowed: &[&str], what: &str) -> Checked<()> {
    match fields.keys().find(|key| !allowed.contains(&key.as_str())) {
        Some(extra) => refuse(format!("{what} does not take {extra}")),
        None => Ok(()),
    }
}

fn revision(value: &Value) -> Checked<i64> {
    match whole_number(value) {
        Some(revision) if (0..=REVISION_MAX).contains(&revision) => Ok(revision as i64),
        _ => refuse("revision must be a whole number from 0"),
    }
}

/// `str | None` of 1 to 80 characters; missing is None.
fn short_text(fields: &Map<String, Value>, name: &str) -> Checked<Option<String>> {
    match fields.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) if (1..=80).contains(&text.chars().count()) => {
            Ok(Some(text.clone()))
        }
        _ => refuse(format!("{name} must be 1 to 80 characters")),
    }
}

/// A list field that defaults to empty.
fn items<'a>(fields: &'a Map<String, Value>, name: &str) -> Checked<&'a [Value]> {
    match fields.get(name) {
        None => Ok(&[]),
        Some(Value::Array(items)) => Ok(items),
        _ => refuse(format!("{name} must be a list")),
    }
}

const SHOWN_WEEK_RULE: &str =
    "a week from another day names the revisions of the two stored weeks it covers";

fn changed_week(value: &Value) -> Checked<ChangedWeek> {
    let fields = object(value, "a changed week")?;
    only(
        fields,
        &["blocks", "week_start", "revision"],
        "a changed week",
    )?;
    let Some(blocks) = fields.get("blocks") else {
        return refuse("blocks is required");
    };
    let checked = week_request(&json!({ "blocks": blocks })).map_err(BlockRefused)?;
    let week_start = match fields.get("week_start") {
        Some(Value::String(text)) => text.clone(),
        _ => return refuse("week_start is required"),
    };
    // `Revision | list[Revision]`: a list is read item by item; anything else as one revision.
    let given = match fields.get("revision") {
        Some(Value::Array(items)) => Err(items),
        Some(other) => Ok(revision(other)?),
        None => return refuse("revision is required"),
    };
    let revision = match given {
        Ok(one) if is_week_start(&week_start) => Revision::Stored(one),
        Err(items) if !is_week_start(&week_start) && is_calendar_date(&week_start) => {
            let read = items.iter().map(revision).collect::<Checked<Vec<i64>>>()?;
            match read[..] {
                [first, second] => Revision::Shown(first, second),
                _ => return refuse(SHOWN_WEEK_RULE),
            }
        }
        _ => return refuse(SHOWN_WEEK_RULE),
    };
    Ok(ChangedWeek {
        week_start,
        blocks: checked
            .blocks
            .iter()
            .map(|block| block.to_value())
            .collect(),
        revision,
    })
}

fn homework_change(value: &Value) -> Checked<HomeworkChange> {
    let fields = object(value, "a homework change")?;
    only(
        fields,
        &["id", "assignment", "revision"],
        "a homework change",
    )?;
    let id = match fields.get("id") {
        Some(Value::String(id)) if (1..=80).contains(&id.chars().count()) => id.clone(),
        _ => return refuse("id must be 1 to 80 characters"),
    };
    let assignment = match fields.get("assignment") {
        None => return refuse("assignment is required"),
        Some(Value::Null) => None,
        Some(body) => Some(assignment_content(body).map_err(BlockRefused)?.to_value()),
    };
    let Some(given) = fields.get("revision") else {
        return refuse("revision is required");
    };
    Ok(HomeworkChange {
        id,
        assignment,
        revision: revision(given)?,
    })
}

/// The save as `ChangesRequest` reads it, or why the app would refuse it.
pub fn check_changes(given: &Value) -> Checked<ChangesRequest> {
    let fields = object(given, "a save")?;
    only(
        fields,
        &[
            "weeks",
            "assignments",
            "operation_id",
            "snapshot_label",
            "repeats",
        ],
        "a save",
    )?;
    let weeks = items(fields, "weeks")?
        .iter()
        .map(changed_week)
        .collect::<Checked<Vec<_>>>()?;
    let assignments = items(fields, "assignments")?
        .iter()
        .map(homework_change)
        .collect::<Checked<Vec<_>>>()?;
    let operation_id = short_text(fields, "operation_id")?;
    let snapshot_label = short_text(fields, "snapshot_label")?;
    let repeats = match fields.get("repeats") {
        None | Some(Value::Null) => None,
        Some(Value::Array(items))
            if items.len() <= MAX_REPEAT_CHANGES && items.iter().all(Value::is_object) =>
        {
            Some(items.clone())
        }
        _ => return refuse("repeats must be a list of changes"),
    };
    Ok(ChangesRequest {
        weeks,
        assignments,
        operation_id,
        snapshot_label,
        repeats,
    })
}

/// The save as the store's one change function takes it.
fn store_input(request: &ChangesRequest) -> store::ApplyInput {
    store::ApplyInput {
        weeks: request
            .weeks
            .iter()
            .map(|week| store::WeekInput {
                week_start: week.week_start.clone(),
                blocks: week.blocks.clone(),
                revision: match week.revision {
                    Revision::Stored(revision) => store::Revision::Stored(revision),
                    Revision::Shown(first, second) => store::Revision::Shown(first, second),
                },
            })
            .collect(),
        assignments: request
            .assignments
            .iter()
            .map(|change| store::AssignmentInput {
                id: change.id.clone(),
                assignment: change.assignment.clone(),
                revision: change.revision,
            })
            .collect(),
        operation_id: request.operation_id.clone(),
        snapshot_label: request.snapshot_label.clone(),
        repeats: request.repeats.clone(),
        argument_digest: None,
    }
}

/// Saves `given` as `POST /api/changes` does and answers it. `token` names a restore point made first, at
/// `now`, when the save asks for one.
pub fn apply_changes(
    path: &Path,
    user_id: i64,
    given: &Value,
    token: &str,
    now: &str,
) -> ServiceResult<Value> {
    let request = check_changes(given)
        .map_err(|_| ServiceError::from(Refusal::Invalid(INVALID_INPUT.to_string())))?;
    let input = store_input(&request);
    let clock = store::ApplyClock {
        now: now.to_string(),
        restore_token: token.to_string(),
    };
    with_db(path, |conn| {
        Ok(store::apply(conn, user_id, &input, &clock)?)
    })
}
