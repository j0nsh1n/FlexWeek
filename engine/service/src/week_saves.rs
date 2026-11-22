//! Saving the Week screen, as `backend/app.py`'s `PUT /api/week` does it: the save is checked as
//! `SavedWeek` checks it, old-style deadline blocks become homework, the week may only name this account's
//! homework, sessions take their homework's title and colours, and the week is written at the revision the
//! window last saw (another window's save in between is refused). The answer is the week as the student
//! sees it, with the School and activities standing in it.

use std::path::Path;

use flexweek_engine::snapshot::canonical;
use flexweek_engine::time::is_week_start;
use flexweek_engine::validate::{assignment_content, time_block, week_request, whole_number};
use flexweek_store::{self as store, Adopted, Relay, StoreError, WeekSave};
use serde_json::{Map, Value, json};

use crate::accounts::INVALID_INPUT;
use crate::blocks::{BlockRefused, Checked, refuse};
use crate::{Refusal, ServiceError, ServiceResult, with_db};

pub const ASSIGNMENT_UNKNOWN: &str = "assignment_id must name an assignment of this account";
pub const ASSIGNMENT_LIMIT: &str = "An account holds at most 1000 assignments";
pub const WEEK_CONFLICT: &str = "This week changed in another window. Reload before saving.";
const MAX_ASSIGNMENTS: i64 = 1000;
const REVISION_MAX: i128 = (1 << 53) - 1;
/// How many repeat edits one request may carry, as `backend/app.py`'s `MAX_REPEAT_CHANGES`.
const MAX_REPEAT_CHANGES: usize = 2 * flexweek_engine::repeats::MAX_REPEATS;

/// A week save as `SavedWeek` reads it: (Monday, blocks as written, revision).
pub fn check_saved_week(given: &Value) -> Checked<(String, Vec<Value>, i64)> {
    let Value::Object(fields) = given else {
        return refuse("a week save must be an object");
    };
    if let Some(extra) = fields
        .keys()
        .find(|key| !["blocks", "week_start", "revision"].contains(&key.as_str()))
    {
        return refuse(format!("a week save does not take {extra}"));
    }
    let Some(blocks) = fields.get("blocks") else {
        return refuse("blocks is required");
    };
    let checked = week_request(&json!({ "blocks": blocks })).map_err(BlockRefused)?;
    let week_start = match fields.get("week_start") {
        Some(Value::String(text)) if is_week_start(text) => text.clone(),
        _ => return refuse("week_start must be a Monday"),
    };
    let revision = match fields.get("revision").and_then(whole_number) {
        Some(revision) if (0..=REVISION_MAX).contains(&revision) => revision as i64,
        _ => return refuse("revision must be a whole number from 0"),
    };
    let blocks = checked
        .blocks
        .iter()
        .map(|block| block.to_value())
        .collect();
    Ok((week_start, blocks, revision))
}

fn invalid() -> ServiceError {
    Refusal::Invalid(INVALID_INPUT.to_string()).into()
}

/// Every block written out again, as the route's `TimeBlock.model_validate` does after each step.
pub(crate) fn written(blocks: Vec<Value>) -> ServiceResult<Vec<Value>> {
    blocks
        .iter()
        .map(|block| {
            time_block(block)
                .map(|checked| checked.to_value())
                .map_err(|why| {
                    ServiceError::Broken(format!("a saved block no longer reads: {why}"))
                })
        })
        .collect()
}

/// The new homework an old-style deadline block becomes, written as a homework save writes it.
fn encode_new_homework(body: &Value) -> Result<String, String> {
    assignment_content(body).map(|content| canonical(&content.to_value()))
}

/// Saves the week from `{"week_start", "blocks", "revision"}` and answers it as `PUT /api/week` does.
pub fn save_week(path: &Path, user_id: i64, given: &Value) -> ServiceResult<Value> {
    let (week_start, blocks, revision) = check_saved_week(given).map_err(|_| invalid())?;
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        let (blocks, revision) = write_week(conn, user_id, &week_start, blocks, revision)?;
        let shown = store::week_with_standing(
            conn,
            user_id,
            &week_start,
            &Value::Array(blocks).to_string(),
        )?;
        let shown: Value = serde_json::from_str(&shown).map_err(|error| StoreError::Json {
            text: shown.clone(),
            error,
        })?;
        Ok(json!({ "week_start": week_start, "blocks": shown, "revision": revision }))
    })
}

/// One stored week written inside the caller's transaction, as the app's routes write it: old-style deadline
/// blocks become homework, the week may only name this account's homework, sessions take their homework's
/// title and colours, and the row is written at `revision`. Answers the blocks as stored and the new revision.
pub(crate) fn write_week(
    conn: &store::Connection,
    user_id: i64,
    week_start: &str,
    blocks: Vec<Value>,
    revision: i64,
) -> ServiceResult<(Vec<Value>, i64)> {
    let adopted = store::adopt_legacy_deadlines(
        conn,
        user_id,
        week_start,
        &Value::Array(blocks),
        MAX_ASSIGNMENTS,
        encode_new_homework,
    )
    .map_err(|relay| match relay {
        Relay::Store(error) => ServiceError::from(error),
        Relay::Caller(why) => ServiceError::Broken(format!("a deadline's homework: {why}")),
    })?;
    let incoming = match adopted {
        Adopted::OverLimit => {
            return Err(Refusal::Invalid(ASSIGNMENT_LIMIT.to_string()).into());
        }
        Adopted::Blocks(blocks) => written(blocks)?,
    };
    let ids: Vec<String> = incoming
        .iter()
        .filter_map(|block| block.get("assignment_id").and_then(Value::as_str))
        .filter(|id| !id.is_empty())
        .map(str::to_string)
        .collect::<std::collections::BTreeSet<_>>()
        .into_iter()
        .collect();
    let (owned, rows) = store::own_assignment_rows(conn, user_id, &ids)?;
    if !owned {
        return Err(Refusal::Invalid(ASSIGNMENT_UNKNOWN.to_string()).into());
    }
    let mut homework = Map::new();
    for (id, body, _) in rows {
        let body: Value = serde_json::from_str(&body).map_err(|error| StoreError::Json {
            text: body.clone(),
            error,
        })?;
        homework.insert(id, body);
    }
    let rewritten = store::rewrite_blocks(&Value::Array(incoming), &Value::Object(homework))
        .map_err(StoreError::Engine)?;
    let blocks = written(rewritten)?;
    let encoded = canonical(&Value::Array(blocks.clone()));
    let saved = match store::save_week(conn, user_id, week_start, &encoded, revision) {
        Ok(saved) => saved,
        Err(error @ StoreError::RepeatedBlockId(_)) => {
            return Err(Refusal::Invalid(error.to_string()).into());
        }
        Err(error) => return Err(error.into()),
    };
    match saved {
        WeekSave::Ready(revision) => Ok((blocks, revision)),
        WeekSave::Conflict => Err(Refusal::Conflict(WEEK_CONFLICT.to_string()).into()),
    }
}

/// The later weeks a set of repeat edits would reach that have their own edit, as
/// `POST /api/repeat-edits` answers from `{"repeats": [...]}`: nothing is written.
pub fn preview_repeat_edits(path: &Path, user_id: i64, given: &Value) -> ServiceResult<Value> {
    let Value::Object(fields) = given else {
        return Err(invalid());
    };
    let repeats = match fields.get("repeats") {
        Some(Value::Array(items))
            if fields.len() == 1
                && items.len() <= MAX_REPEAT_CHANGES
                && items.iter().all(Value::is_object) =>
        {
            Value::Array(items.clone())
        }
        _ => return Err(invalid()),
    };
    let intents = flexweek_engine::repeats::parse_intents(&repeats)
        .map_err(|why| ServiceError::from(Refusal::Invalid(why)))?;
    let found = with_db(path, |conn| {
        store::preview_edited_weeks(conn, user_id, &intents).map_err(|failure| match failure {
            store::RepeatsFailure::Refused(why) => Refusal::Invalid(why).into(),
            store::RepeatsFailure::Store(error) => error.into(),
        })
    })?;
    // The route answered the canonical text read back, so its keys come out sorted.
    let text = canonical(&found);
    Ok(serde_json::from_str(&text).map_err(|error| StoreError::Json { text, error })?)
}

#[cfg(test)]
mod tests {
    use super::*;
    use flexweek_testkit::TestDb;

    fn school(title: &str) -> Value {
        json!({
            "id": "school", "title": title, "kind": "locked", "duration_min": 390,
            "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "School",
        })
    }

    /// The store's guard, for a week whose doubled id gets past the request check (a week on screen split
    /// back into its stored weeks): the save is refused in the student's words and nothing is written.
    #[test]
    fn a_week_that_reaches_the_store_with_a_doubled_id_is_refused_in_words_and_writes_nothing() {
        let db = TestDb::new("doubled-id");
        let user = db.account("alice");
        let blocks = written(vec![school("School"), school("School again")]).unwrap();
        let refused = with_db(&db.path, |conn| {
            store::begin_immediate(conn)?;
            write_week(conn, user, "2026-09-14", blocks, 0)
        });
        match refused {
            Err(ServiceError::Refused(Refusal::Invalid(words))) => assert_eq!(
                words,
                r#"Two blocks in this week share the id "school". Each block needs its own id."#
            ),
            other => panic!("not refused in words: {other:?}"),
        }
        let rows: i64 = with_db(&db.path, |conn| {
            Ok(conn
                .query_row("SELECT count(*) FROM weeks", [], |row| row.get(0))
                .unwrap())
        })
        .unwrap();
        assert_eq!(rows, 0);
    }
}
