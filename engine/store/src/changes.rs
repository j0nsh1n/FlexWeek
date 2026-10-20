//! `post_changes` (`backend/app.py`). The batch commits in one `BEGIN IMMEDIATE` or not at all.

use flexweek_engine::snapshot::canonical;
use flexweek_engine::validate::time_block;
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::{Map, Value, json};

use crate::{
    Adopted, AssignmentDelete, AssignmentSave, Recall, Relay, StoreError, WeekSave,
    adopt_legacy_deadlines, begin_immediate, create_restore_point, delete_assignment,
    own_assignment_rows, payload_digest, read_week, recall_operation, remember_operation,
    rewrite_blocks, save_assignment, save_week, set_standing, week_with_standing,
};

const MAX_ASSIGNMENTS: i64 = 1000;
const MAX_OPERATIONS: i64 = 100;
const MAX_RESTORE_POINTS: i64 = 20;
const ASSIGNMENT_CONFLICT: &str =
    "This assignment changed in another window. Reload before saving.";
const ASSIGNMENT_LIMIT: &str = "An account holds at most 1000 assignments";
const ASSIGNMENT_UNKNOWN: &str = "assignment_id must name an assignment of this account";
const WEEK_CONFLICT: &str = "This week changed in another window. Reload before saving.";
const OPERATION_CONFLICT: &str = "This operation was already used with different data.";

#[derive(Debug)]
pub struct ApplyClock {
    pub now: String,
    pub restore_token: String,
}

#[derive(Debug)]
pub struct WeekInput {
    pub week_start: String,
    pub blocks: Vec<Value>,
    pub revision: i64,
}

#[derive(Debug)]
pub struct AssignmentInput {
    pub id: String,
    pub assignment: Option<Value>,
    pub revision: i64,
}

#[derive(Debug)]
pub struct StandingInput {
    pub week_start: String,
    pub blocks: Vec<Value>,
}

#[derive(Debug)]
pub struct ApplyInput {
    pub weeks: Vec<WeekInput>,
    pub assignments: Vec<AssignmentInput>,
    pub operation_id: Option<String>,
    pub snapshot_label: Option<String>,
    pub standing: Option<StandingInput>,
}

#[derive(Debug)]
pub enum ApplyFailure {
    Store(StoreError),
    Refused {
        message: String,
        current_revision: Option<i64>,
    },
}

impl From<StoreError> for ApplyFailure {
    fn from(error: StoreError) -> Self {
        Self::Store(error)
    }
}

impl From<flexweek_engine::EngineError> for ApplyFailure {
    fn from(error: flexweek_engine::EngineError) -> Self {
        Self::Store(StoreError::Engine(error))
    }
}

struct WeekOut {
    week_start: String,
    blocks: Value,
    revision: i64,
}

pub fn apply(
    conn: &Connection,
    user_id: i64,
    input: &ApplyInput,
    clock: &ApplyClock,
) -> Result<Value, ApplyFailure> {
    begin_immediate(conn)?;
    match apply_tx(conn, user_id, input, clock) {
        Ok(value) => match conn.execute("COMMIT", []) {
            Ok(_) => Ok(value),
            Err(error) => {
                let _ = conn.execute("ROLLBACK", []);
                Err(StoreError::Sqlite(error).into())
            }
        },
        Err(error) => {
            let _ = conn.execute("ROLLBACK", []);
            Err(error)
        }
    }
}

fn apply_tx(
    conn: &Connection,
    user_id: i64,
    input: &ApplyInput,
    clock: &ApplyClock,
) -> Result<Value, ApplyFailure> {
    let digest = payload_digest(&batch_value(input));
    if let Some(operation_id) = &input.operation_id {
        match recall_operation(conn, user_id, operation_id, &digest)? {
            Recall::Hit(response) => return parse_json(&response),
            Recall::Conflict => return Err(refuse(OPERATION_CONFLICT)),
            Recall::Missing => {}
        }
    }
    if let Some(label) = &input.snapshot_label {
        create_restore_point(
            conn,
            user_id,
            &clock.restore_token,
            label,
            &clock.now,
            &[],
            MAX_RESTORE_POINTS,
        )?;
    }
    let assignments = apply_assignments(conn, user_id, &input.assignments)?;
    let mut weeks = apply_weeks(conn, user_id, &input.weeks)?;
    let standing_changed = apply_standing(conn, user_id, input.standing.as_ref())?;
    for week in &mut weeks {
        let merged = week_with_standing(conn, user_id, &week.week_start, &canonical(&week.blocks))?;
        week.blocks = parse_json(&merged)?;
    }
    let mut result = json!({
        "weeks": weeks.iter().map(week_value).collect::<Vec<_>>(),
        "assignments": assignments,
    });
    if let Some(changed) = standing_changed
        && let Some(object) = result.as_object_mut()
    {
        object.insert("standing_changed_weeks".into(), json!(changed));
    }
    if let Some(operation_id) = &input.operation_id {
        remember_operation(
            conn,
            user_id,
            operation_id,
            &digest,
            &canonical(&result),
            MAX_OPERATIONS,
        )?;
    }
    Ok(result)
}

fn apply_assignments(
    conn: &Connection,
    user_id: i64,
    changes: &[AssignmentInput],
) -> Result<Vec<Value>, ApplyFailure> {
    let mut results = Vec::new();
    let mut deletes = Vec::new();
    for change in changes {
        let Some(body) = &change.assignment else {
            deletes.push(change);
            continue;
        };
        if body.get("id").and_then(Value::as_str) != Some(change.id.as_str()) {
            return Err(refuse("assignment id in the path and body must match"));
        }
        match save_assignment(
            conn,
            user_id,
            &change.id,
            &canonical(body),
            change.revision,
            MAX_ASSIGNMENTS,
        )? {
            AssignmentSave::Ready(revision) => results.push(json!({
                "id": change.id,
                "revision": revision,
                "assignment": body,
            })),
            AssignmentSave::Conflict => {
                return Err(conflict(
                    ASSIGNMENT_CONFLICT,
                    assignment_revision(conn, user_id, &change.id)?,
                ));
            }
            AssignmentSave::OverLimit => return Err(refuse(ASSIGNMENT_LIMIT)),
        }
    }
    for change in deletes {
        results.push(apply_delete(conn, user_id, change)?);
    }
    Ok(results)
}

fn apply_delete(
    conn: &Connection,
    user_id: i64,
    change: &AssignmentInput,
) -> Result<Value, ApplyFailure> {
    match delete_assignment(conn, user_id, &change.id, Some(change.revision))? {
        AssignmentDelete::Missing => Err(refuse("Assignment not found")),
        AssignmentDelete::Conflict => Err(conflict(
            ASSIGNMENT_CONFLICT,
            assignment_revision(conn, user_id, &change.id)?,
        )),
        AssignmentDelete::Deleted(payload) => {
            let deleted = parse_json(&payload)?;
            Ok(json!({
                "id": change.id,
                "revision": change.revision,
                "assignment": Value::Null,
                "changed_weeks": deleted.get("changed_weeks").cloned().unwrap_or(Value::Null),
                "removed_sessions": deleted.get("removed_sessions").cloned().unwrap_or(Value::Null),
            }))
        }
    }
}

fn apply_weeks(
    conn: &Connection,
    user_id: i64,
    weeks: &[WeekInput],
) -> Result<Vec<WeekOut>, ApplyFailure> {
    let mut saved = Vec::with_capacity(weeks.len());
    for week in weeks {
        saved.push(apply_week(conn, user_id, week)?);
    }
    Ok(saved)
}

fn apply_week(conn: &Connection, user_id: i64, week: &WeekInput) -> Result<WeekOut, ApplyFailure> {
    let adopted = match adopt_legacy_deadlines(
        conn,
        user_id,
        &week.week_start,
        &Value::Array(week.blocks.clone()),
        MAX_ASSIGNMENTS,
        |body| Ok::<_, StoreError>(canonical(body)),
    ) {
        Ok(Adopted::OverLimit) => return Err(refuse(ASSIGNMENT_LIMIT)),
        Ok(Adopted::Blocks(blocks)) => blocks,
        Err(Relay::Store(error) | Relay::Caller(error)) => return Err(error.into()),
    };
    let ids = assignment_ids(&adopted);
    let (owned, rows) = own_assignment_rows(conn, user_id, &ids)?;
    if !owned {
        return Err(refuse(ASSIGNMENT_UNKNOWN));
    }
    let mut assignments = Map::new();
    for (id, body, _) in rows {
        assignments.insert(id, parse_json(&body)?);
    }
    let rewritten = rewrite_blocks(&Value::Array(adopted), &Value::Object(assignments))?;
    let mut dumped = Vec::with_capacity(rewritten.len());
    for block in rewritten {
        let parsed = time_block(&block).map_err(|message| refuse(&message))?;
        dumped.push(parsed.to_value());
    }
    let encoded = canonical(&Value::Array(dumped.clone()));
    let revision = match save_week(conn, user_id, &week.week_start, &encoded, week.revision)? {
        WeekSave::Ready(revision) => revision,
        WeekSave::Conflict => {
            return Err(conflict(
                WEEK_CONFLICT,
                Some(stored_week_revision(conn, user_id, &week.week_start)?),
            ));
        }
    };
    Ok(WeekOut {
        week_start: week.week_start.clone(),
        blocks: Value::Array(dumped),
        revision,
    })
}

fn apply_standing(
    conn: &Connection,
    user_id: i64,
    standing: Option<&StandingInput>,
) -> Result<Option<Vec<String>>, ApplyFailure> {
    let Some(standing) = standing else {
        return Ok(None);
    };
    let encoded =
        serde_json::to_string(&Value::Array(standing.blocks.clone())).map_err(|error| {
            ApplyFailure::Store(StoreError::Json {
                text: String::new(),
                error,
            })
        })?;
    Ok(Some(set_standing(
        conn,
        user_id,
        &standing.week_start,
        &encoded,
    )?))
}

fn week_value(week: &WeekOut) -> Value {
    json!({
        "week_start": week.week_start,
        "blocks": week.blocks,
        "revision": week.revision,
    })
}

fn assignment_ids(blocks: &[Value]) -> Vec<String> {
    let mut ids = Vec::new();
    for block in blocks {
        let Some(id) = block.get("assignment_id").and_then(Value::as_str) else {
            continue;
        };
        if id.is_empty() || ids.iter().any(|have| have == id) {
            continue;
        }
        ids.push(id.to_string());
    }
    ids
}

fn batch_value(input: &ApplyInput) -> Value {
    json!({
        "weeks": input.weeks.iter().map(|week| json!({
            "blocks": week.blocks,
            "week_start": week.week_start,
            "revision": week.revision,
        })).collect::<Vec<_>>(),
        "assignments": input.assignments.iter().map(|change| json!({
            "id": change.id,
            "assignment": change.assignment,
            "revision": change.revision,
        })).collect::<Vec<_>>(),
        "operation_id": input.operation_id,
        "snapshot_label": input.snapshot_label,
        "standing": input.standing.as_ref().map(|standing| json!({
            "week_start": standing.week_start,
            "blocks": standing.blocks,
        })),
    })
}

fn assignment_revision(
    conn: &Connection,
    user_id: i64,
    id: &str,
) -> Result<Option<i64>, ApplyFailure> {
    Ok(conn
        .query_row(
            "SELECT revision FROM assignments WHERE user_id = ?1 AND id = ?2",
            params![user_id, id],
            |row| row.get(0),
        )
        .optional()
        .map_err(StoreError::from)?)
}

fn stored_week_revision(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> Result<i64, ApplyFailure> {
    Ok(read_week(conn, user_id, week_start)?
        .map(|(_, revision)| revision)
        .unwrap_or(0))
}

fn parse_json(text: &str) -> Result<Value, ApplyFailure> {
    serde_json::from_str(text).map_err(|error| {
        ApplyFailure::Store(StoreError::Json {
            text: text.to_string(),
            error,
        })
    })
}

fn refuse(message: &str) -> ApplyFailure {
    conflict(message, None)
}

fn conflict(message: &str, current_revision: Option<i64>) -> ApplyFailure {
    ApplyFailure::Refused {
        message: message.to_string(),
        current_revision,
    }
}
