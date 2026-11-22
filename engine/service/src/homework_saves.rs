//! Saving a homework from the Homework list, as `backend/app.py`'s `PUT /api/assignments/{id}` does it:
//! the save is checked as `Assignment` checks it, written with keys sorted and non-ASCII escaped, kept at
//! the revision the window last saw (another window's save in between is refused), and at most 1,000 per
//! account.

use std::path::Path;

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
    let encoded = canonical(&content);
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        match store::save_assignment(conn, user_id, id, &encoded, revision, limit)? {
            AssignmentSave::Conflict => {
                Err(Refusal::Conflict(ASSIGNMENT_CONFLICT.to_string()).into())
            }
            AssignmentSave::OverLimit => Err(Refusal::Invalid(ASSIGNMENT_LIMIT.to_string()).into()),
            AssignmentSave::Ready(stored) => {
                let mut answer = content.clone();
                if let Value::Object(fields) = &mut answer {
                    fields.insert("revision".into(), Value::from(stored));
                }
                Ok(answer)
            }
        }
    })
}
