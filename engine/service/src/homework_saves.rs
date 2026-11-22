//! Saving a homework from the Homework list, as `backend/app.py`'s `PUT /api/assignments/{id}` does it:
//! the save is checked as `Assignment` checks it, written with keys sorted and non-ASCII escaped, kept at
//! the revision the window last saw (another window's save in between is refused), and at most 1,000 per
//! account.

use std::path::Path;

use flexweek_engine::plan;
use flexweek_engine::snapshot::canonical;
use flexweek_engine::validate::{assignment_content, whole_number};
use flexweek_store::{self as store, AssignmentSave};
use serde_json::{Map, Value};

use crate::accounts::INVALID_INPUT;
use crate::blocks::{BlockRefused, Checked, refuse};
use crate::week_saves::ASSIGNMENT_LIMIT;
use crate::{Refusal, ServiceResult, with_db};

pub const ASSIGNMENT_CONFLICT: &str =
    "This assignment changed in another window. Reload before saving.";
pub const ID_MISMATCH: &str = "assignment id in the path and body must match";
const MAX_ASSIGNMENTS: i64 = 1000;
const REVISION_MAX: i128 = (1 << 53) - 1;

/// A homework save as `Assignment` reads it: the homework as written, and the revision it was made from.
pub fn check_homework(given: &Value) -> Checked<(Value, i64)> {
    let Value::Object(fields) = given else {
        return refuse("a homework save must be an object");
    };
    let revision = match fields.get("revision").and_then(whole_number) {
        Some(revision) if (0..=REVISION_MAX).contains(&revision) => revision as i64,
        _ => return refuse("revision must be a whole number from 0"),
    };
    let content: Map<String, Value> = fields
        .iter()
        .filter(|(key, _)| key.as_str() != "revision")
        .map(|(key, value)| (key.clone(), value.clone()))
        .collect();
    let checked = assignment_content(&Value::Object(content)).map_err(BlockRefused)?;
    Ok((checked.to_value(), revision))
}

/// Saves the homework `id` from the request body and answers it with its new revision.
pub fn save_homework(path: &Path, user_id: i64, id: &str, given: &Value) -> ServiceResult<Value> {
    save_homework_up_to(path, user_id, id, given, MAX_ASSIGNMENTS)
}

/// `save_homework` with another limit on how many homework an account holds, so a test can reach it.
pub fn save_homework_up_to(
    path: &Path,
    user_id: i64,
    id: &str,
    given: &Value,
    limit: i64,
) -> ServiceResult<Value> {
    let (content, revision) = check_homework(given)
        .map_err(|_| crate::ServiceError::from(Refusal::Invalid(INVALID_INPUT.to_string())))?;
    if content["id"] != id {
        return Err(Refusal::Invalid(ID_MISMATCH.to_string()).into());
    }
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        let stored = write_homework(conn, user_id, id, &content, revision, limit)?;
        let mut answer = content.clone();
        if let Value::Object(fields) = &mut answer {
            fields.insert("revision".into(), Value::from(stored));
        }
        Ok(answer)
    })
}

/// A checked homework written inside the caller's transaction at `revision`; answers its new revision.
pub(crate) fn write_homework(
    conn: &store::Connection,
    user_id: i64,
    id: &str,
    content: &Value,
    revision: i64,
    limit: i64,
) -> ServiceResult<i64> {
    match store::save_assignment(conn, user_id, id, &canonical(content), revision, limit)? {
        AssignmentSave::Conflict => Err(Refusal::Conflict(ASSIGNMENT_CONFLICT.to_string()).into()),
        AssignmentSave::OverLimit => Err(Refusal::Invalid(ASSIGNMENT_LIMIT.to_string()).into()),
        AssignmentSave::Ready(stored) => Ok(stored),
    }
}

pub const SPREAD_DONE: &str = "completed assignments cannot be spread";

/// A "spread it out" request as `SpreadRequest` reads it: (session length, first day).
pub fn check_spread(given: &Value) -> Checked<(i64, String)> {
    let Value::Object(fields) = given else {
        return refuse("a spread request must be an object");
    };
    if let Some(extra) = fields
        .keys()
        .find(|key| !["session_min", "from_date"].contains(&key.as_str()))
    {
        return refuse(format!("a spread request does not take {extra}"));
    }
    let minutes = match fields.get("session_min").and_then(whole_number) {
        Some(minutes) if (15..=180).contains(&minutes) && minutes % 15 == 0 => minutes as i64,
        _ => return refuse("session_min must be a multiple of 15 from 15 to 180"),
    };
    let from = match fields.get("from_date") {
        Some(Value::String(day)) if flexweek_engine::time::is_calendar_date(day) => day.clone(),
        _ => return refuse("from_date must be YYYY-MM-DD between 2000-01-01 and 2099-12-31"),
    };
    Ok((minutes, from))
}

/// The sessions "spread it out" would add for the homework `id`, as `POST /api/assignments/{id}/spread`
/// answers: nothing is saved.
pub fn spread_preview(path: &Path, user_id: i64, id: &str, given: &Value) -> ServiceResult<Value> {
    let (session_min, from_date) = check_spread(given)
        .map_err(|_| crate::ServiceError::from(Refusal::Invalid(INVALID_INPUT.to_string())))?;
    let (body, weeks) = with_db(path, |conn| {
        let Some(body) = store::assignment_body(conn, user_id, id)? else {
            return Err(Refusal::NotFound(crate::records::HOMEWORK_UNKNOWN.to_string()).into());
        };
        let mut weeks = Vec::new();
        for (start, text) in store::list_account_weeks(conn, user_id)? {
            weeks.push((start, crate::weeks::parsed(&text)?));
        }
        Ok((body, weeks))
    })?;
    let body: Value = serde_json::from_str(&body).map_err(|error| store::StoreError::Json {
        text: body.clone(),
        error,
    })?;
    if body["completed"].as_bool().unwrap_or(false) {
        return Err(Refusal::Invalid(SPREAD_DONE.to_string()).into());
    }
    let number = |name: &str| body[name].as_i64().unwrap_or(0);
    let planned = plan::planned_minutes_by_id(&weeks, "2000-01-01", None);
    let done = plan::done_minutes_by_id(&weeks);
    let held = plan::held_dates_by_id(&weeks, "2000-01-01");
    let (sessions, remaining) = plan::spread_sessions_around(
        number("estimate_min"),
        number("focus_minutes"),
        done.get(id).copied().unwrap_or(0),
        planned.get(id).copied().unwrap_or(0),
        body["due"].as_str().unwrap_or(""),
        session_min,
        &from_date,
        held.get(id).map(Vec::as_slice).unwrap_or(&[]),
    )?;
    Ok(serde_json::json!({
        "assignment_id": id,
        "session_min": session_min,
        "remaining_min": remaining,
        "sessions": sessions,
    }))
}
