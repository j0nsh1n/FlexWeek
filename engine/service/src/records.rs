//! Restore points made on request, deleting a routine or a homework, and the remembered operations that
//! make a retried request give its first answer, as `backend/app.py`'s routes do them. The caller passes
//! the time and the restore point's random id.

use std::path::Path;

use flexweek_engine::snapshot::canonical;
use flexweek_store::{self as store, AssignmentDelete, Connection, Recall, RoutineDelete};
use serde_json::{Value, json};

use crate::accounts::INVALID_INPUT;
use crate::{Refusal, ServiceResult, with_db};

pub const OPERATION_CONFLICT: &str = "This operation was already used with different data.";
pub const ROUTINE_UNKNOWN: &str = "Routine not found";
pub const ROUTINE_CONFLICT: &str = "This routine changed in another window. Reload before saving.";
pub const HOMEWORK_UNKNOWN: &str = "Assignment not found";
pub const HOMEWORK_CONFLICT: &str =
    "This assignment changed in another window. Reload before saving.";
const MAX_OPERATIONS: i64 = 100;
const MAX_RESTORE_POINTS: i64 = 20;

/// The answer an operation id was first given, refused when the id came back with other data.
pub(crate) fn recall(
    conn: &Connection,
    user_id: i64,
    operation_id: &str,
    digest: &str,
) -> ServiceResult<Option<Value>> {
    match store::recall_operation(conn, user_id, operation_id, digest)? {
        Recall::Missing => Ok(None),
        Recall::Conflict => Err(Refusal::Conflict(OPERATION_CONFLICT.to_string()).into()),
        Recall::Hit(text) => Ok(Some(serde_json::from_str(&text).map_err(|error| {
            store::StoreError::Json {
                text: text.clone(),
                error,
            }
        })?)),
    }
}

pub(crate) fn remember(
    conn: &Connection,
    user_id: i64,
    operation_id: &str,
    digest: &str,
    answer: &Value,
) -> ServiceResult<()> {
    Ok(store::remember_operation(
        conn,
        user_id,
        operation_id,
        digest,
        &canonical(answer),
        MAX_OPERATIONS,
    )?)
}

fn invalid() -> crate::ServiceError {
    Refusal::Invalid(INVALID_INPUT.to_string()).into()
}

/// A restore point of the whole account now, as `POST /api/restore-points` makes it from
/// `{"label", "operation_id"}`.
pub fn create_restore_point(
    path: &Path,
    user_id: i64,
    given: &Value,
    token: &str,
    now: &str,
) -> ServiceResult<Value> {
    let Value::Object(fields) = given else {
        return Err(invalid());
    };
    if fields
        .keys()
        .any(|key| key != "label" && key != "operation_id")
    {
        return Err(invalid());
    }
    let text = |name: &str| match fields.get(name) {
        Some(Value::String(text)) if (1..=80).contains(&text.chars().count()) => Some(text.clone()),
        _ => None,
    };
    let (Some(label), Some(operation_id)) = (text("label"), text("operation_id")) else {
        return Err(invalid());
    };
    if label.trim().is_empty() {
        return Err(invalid());
    }
    let digest = store::payload_digest(&json!({ "label": label, "operation_id": operation_id }));
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        if let Some(first) = recall(conn, user_id, &operation_id, &digest)? {
            return Ok(first);
        }
        let point = store::create_restore_point(
            conn,
            user_id,
            token,
            &label,
            now,
            &[],
            MAX_RESTORE_POINTS,
        )?;
        remember(conn, user_id, &operation_id, &digest, &point)?;
        Ok(point)
    })
}

/// Deletes a routine at its revision, as `DELETE /api/routines/{id}` does; with an operation id a
/// retried delete gives its first answer. `revision` None is one no stored revision can match (a number
/// past 64 bits): the routine is then missing or changed, as the route answered.
pub fn delete_routine(
    path: &Path,
    user_id: i64,
    routine_id: &str,
    revision: Option<i64>,
    operation_id: Option<&str>,
) -> ServiceResult<Value> {
    let digest =
        store::payload_digest(&json!({ "id": routine_id, "revision": revision, "op": "delete" }));
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        if let Some(operation_id) = operation_id
            && let Some(first) = recall(conn, user_id, operation_id, &digest)?
        {
            return Ok(first);
        }
        let answer = match store::delete_routine(conn, user_id, routine_id, revision)? {
            RoutineDelete::Missing => {
                return Err(Refusal::NotFound(ROUTINE_UNKNOWN.to_string()).into());
            }
            RoutineDelete::Conflict => {
                return Err(Refusal::Conflict(ROUTINE_CONFLICT.to_string()).into());
            }
            RoutineDelete::Deleted => json!({ "id": routine_id }),
        };
        if let Some(operation_id) = operation_id {
            remember(conn, user_id, operation_id, &digest, &answer)?;
        }
        Ok(answer)
    })
}

/// Deletes a homework and its sessions at its revision, as `DELETE /api/assignments/{id}` does, and says
/// which weeks changed. `revision` None is one no stored revision can match.
pub fn delete_homework(
    path: &Path,
    user_id: i64,
    id: &str,
    revision: Option<i64>,
) -> ServiceResult<Value> {
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        match store::delete_assignment(conn, user_id, id, revision)? {
            AssignmentDelete::Missing => {
                Err(Refusal::NotFound(HOMEWORK_UNKNOWN.to_string()).into())
            }
            AssignmentDelete::Conflict => {
                Err(Refusal::Conflict(HOMEWORK_CONFLICT.to_string()).into())
            }
            AssignmentDelete::Deleted(text) => Ok(serde_json::from_str(&text).map_err(
                |error| store::StoreError::Json {
                    text: text.clone(),
                    error,
                },
            )?),
        }
    })
}
