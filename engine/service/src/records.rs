//! Restore points made on request, deleting a routine or a homework, and the remembered operations that
//! make a retried request give its first answer, as `backend/app.py`'s routes do them. The caller passes
//! the time and the restore point's random id.

use std::path::Path;

use flexweek_engine::snapshot::{canonical, diff_snapshots, state_token};
use flexweek_store::{self as store, Connection, Recall, RoutineDelete};
use serde_json::{Value, json};

use crate::accounts::INVALID_INPUT;
use crate::{Refusal, ServiceError, ServiceResult, with_db};

pub const OPERATION_CONFLICT: &str = "This operation was already used with different data.";
pub const ROUTINE_UNKNOWN: &str = "Routine not found";
pub const ROUTINE_CONFLICT: &str = "This routine changed in another window. Reload before saving.";
pub const HOMEWORK_UNKNOWN: &str = store::writes::ASSIGNMENT_MISSING;
pub const HOMEWORK_CONFLICT: &str = store::writes::ASSIGNMENT_CONFLICT;
pub const RESTORE_UNKNOWN: &str = "Restore point not found";
pub const RESTORE_STALE: &str =
    "This preview is out of date. Preview the saved copy again before restoring.";
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
        remove_homework(conn, user_id, id, revision)
    })
}

/// `delete_homework` inside the caller's transaction.
pub(crate) fn remove_homework(
    conn: &Connection,
    user_id: i64,
    id: &str,
    revision: Option<i64>,
) -> ServiceResult<Value> {
    Ok(store::writes::remove_homework(conn, user_id, id, revision)?)
}

fn parsed(text: &str) -> ServiceResult<Value> {
    serde_json::from_str(text).map_err(|error| {
        store::StoreError::Json {
            text: text.to_string(),
            error,
        }
        .into()
    })
}

/// The account's weeks and homework as a restore point holds them, as `capture_account` gives them.
pub(crate) fn captured(conn: &Connection, user_id: i64) -> ServiceResult<Value> {
    let raw = parsed(&store::capture_account(conn, user_id)?)?;
    let rows = |name: &str| raw[name].as_array().cloned().unwrap_or_default();
    let mut weeks = Vec::new();
    for row in rows("weeks") {
        let blocks = parsed(row["blocks"].as_str().unwrap_or("[]"))?;
        weeks.push(json!({
            "week_start": row["week_start"],
            "blocks": blocks,
            "revision": row["revision"],
        }));
    }
    let mut assignments = Vec::new();
    for row in rows("assignments") {
        let body = parsed(row["body"].as_str().unwrap_or("{}"))?;
        assignments.push(json!({ "id": row["id"], "body": body, "revision": row["revision"] }));
    }
    Ok(json!({ "weeks": weeks, "assignments": assignments }))
}

fn point_body(conn: &Connection, user_id: i64, point_id: &str) -> ServiceResult<(String, Value)> {
    let Some((id, body)) = store::restore_point_body(conn, user_id, point_id)? else {
        return Err(Refusal::NotFound(RESTORE_UNKNOWN.to_string()).into());
    };
    Ok((id, parsed(&body)?))
}

/// What restoring `point_id` would change, and the token that says which account state was compared,
/// as `GET /api/restore-points/{id}/preview` answers. Both are read in one snapshot.
pub fn restore_preview(path: &Path, user_id: i64, point_id: &str) -> ServiceResult<Value> {
    with_db(path, |conn| {
        store::begin(conn)?;
        let (id, stored) = point_body(conn, user_id, point_id)?;
        let current = captured(conn, user_id)?;
        Ok(json!({
            "id": id,
            "state_token": state_token(&current),
            "changes": diff_snapshots(&current, &stored),
        }))
    })
}

/// The restore request `{"state_token", "operation_id"}`, checked as `RestoreApply` checks it.
fn restore_request(given: &Value) -> ServiceResult<(String, String)> {
    let Value::Object(fields) = given else {
        return Err(invalid());
    };
    if fields
        .keys()
        .any(|key| key != "state_token" && key != "operation_id")
    {
        return Err(invalid());
    }
    let text = |name: &str, most: usize| match fields.get(name) {
        Some(Value::String(text)) if (1..=most).contains(&text.chars().count()) => {
            Some(text.clone())
        }
        _ => None,
    };
    match (text("state_token", 128), text("operation_id", 80)) {
        (Some(token), Some(operation_id)) => Ok((token, operation_id)),
        _ => Err(invalid()),
    }
}

fn stored_rows(
    stored: &Value,
    name: &str,
    key: &str,
    body: &str,
) -> ServiceResult<Vec<(String, String, i64)>> {
    let broken = || ServiceError::Broken(format!("a restore point's {name} no longer read"));
    let mut rows = Vec::new();
    for row in stored[name].as_array().ok_or_else(broken)? {
        let id = row[key].as_str().ok_or_else(broken)?.to_string();
        let revision = row["revision"].as_i64().ok_or_else(broken)?;
        rows.push((id, canonical(&row[body]), revision));
    }
    Ok(rows)
}

/// Puts the account back as restore point `point_id` holds it, as `POST /api/restore-points/{id}/restore`
/// does from `{"state_token", "operation_id"}`: refused when the account changed since the preview, a
/// restore point of the account as it was is made first (`token` is its random id, `now` its time), and
/// a retried request gives its first answer.
pub fn restore(
    path: &Path,
    user_id: i64,
    point_id: &str,
    given: &Value,
    token: &str,
    now: &str,
) -> ServiceResult<Value> {
    let (state, operation_id) = restore_request(given)?;
    let digest = store::payload_digest(
        &json!({ "id": point_id, "state_token": state, "operation_id": operation_id }),
    );
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        if let Some(first) = recall(conn, user_id, &operation_id, &digest)? {
            return Ok(first);
        }
        let (_, stored) = point_body(conn, user_id, point_id)?;
        if state != state_token(&captured(conn, user_id)?) {
            return Err(Refusal::Conflict(RESTORE_STALE.to_string()).into());
        }
        let recovery = store::create_restore_point(
            conn,
            user_id,
            token,
            &format!("Before restore \u{2014} {now}"),
            now,
            &[point_id.to_string()],
            MAX_RESTORE_POINTS,
        )?;
        let weeks = stored_rows(&stored, "weeks", "week_start", "blocks")?;
        let assignments = stored_rows(&stored, "assignments", "id", "body")?;
        store::replace_account(conn, user_id, &weeks, &assignments).map_err(
            |error| match error {
                store::StoreError::RepeatedBlockId(_) => {
                    ServiceError::from(Refusal::Invalid(error.to_string()))
                }
                other => other.into(),
            },
        )?;
        // A point made before 0.19.0 has no standing week, so the current one stays.
        if let Some(standing) = stored.get("standing") {
            store::replace_standing(conn, user_id, &standing.to_string())?;
        }
        let answer = json!({
            "id": point_id,
            "recovery_id": recovery["id"],
            "weeks": weeks.iter().map(|(start, _, revision)| json!({ "week_start": start, "revision": revision })).collect::<Vec<_>>(),
            "assignments": assignments.iter().map(|(id, _, revision)| json!({ "id": id, "revision": revision })).collect::<Vec<_>>(),
        });
        remember(conn, user_id, &operation_id, &digest, &answer)?;
        Ok(answer)
    })
}

pub const ROUTINE_LIMIT: &str = "An account holds at most 50 routines";
pub const ROUTINE_ID_MISMATCH: &str = "routine id in the path and body must match";
const MAX_ROUTINES: i64 = 50;

/// Saves the routine `id` from the request body, as `PUT /api/routines/{id}` does: checked as `Routine`
/// checks it, its blocks written with keys sorted and non-ASCII escaped, refused when made from an old
/// revision, at most 50 per account; `now` is the time it is stamped with. The answer is the routine as the
/// Routines screen lists it.
pub fn save_routine(
    path: &Path,
    user_id: i64,
    id: &str,
    given: &Value,
    now: &str,
) -> ServiceResult<Value> {
    let checked = flexweek_engine::validate::routine(given).map_err(|_| invalid())?;
    if checked.id != id {
        return Err(Refusal::Invalid(ROUTINE_ID_MISMATCH.to_string()).into());
    }
    let blocks: Vec<Value> = checked
        .blocks
        .iter()
        .map(|block| block.to_value())
        .collect();
    let body = canonical(&Value::Array(blocks));
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        let write = store::RoutineWrite {
            id,
            name: &checked.name,
            body: &body,
            revision: checked.revision,
            stamp: now,
            max_count: MAX_ROUTINES,
        };
        match store::save_routine(conn, user_id, write)? {
            store::RoutineSave::Conflict => {
                Err(Refusal::Conflict(ROUTINE_CONFLICT.to_string()).into())
            }
            store::RoutineSave::OverLimit => {
                Err(Refusal::Invalid(ROUTINE_LIMIT.to_string()).into())
            }
            store::RoutineSave::Stored(row) => {
                let row = parsed(&row)?;
                let blocks = parsed(row["body"].as_str().unwrap_or("[]"))?;
                Ok(json!({
                    "id": row["id"],
                    "name": row["name"],
                    "blocks": blocks,
                    "revision": row["revision"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }))
            }
        }
    })
}
