//! Saving the Week screen, as `backend/app.py`'s `PUT /api/week` does it: the save is checked as
//! `SavedWeek` checks it, old-style deadline blocks become homework, the week may only name this account's
//! homework, sessions take their homework's title and colours, and the week is written at the revision the
//! window last saw (another window's save in between is refused). The answer is the week as the student
//! sees it, with the School and activities standing in it.

use std::path::Path;

use flexweek_engine::snapshot::canonical;
use flexweek_engine::time::is_week_start;
use flexweek_engine::validate::{week_request, whole_number};
use flexweek_store::{self as store, StoreError};
use serde_json::{Value, json};

use crate::accounts::INVALID_INPUT;
use crate::blocks::{BlockRefused, Checked, refuse};
use crate::{Refusal, ServiceError, ServiceResult, with_db};

pub use flexweek_store::writes::{ASSIGNMENT_LIMIT, ASSIGNMENT_UNKNOWN, WEEK_CONFLICT};
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

/// One stored week written inside the caller's transaction, as the app's routes write it
/// (`flexweek_store::writes::write_week`). Answers the blocks as stored and the new revision.
pub(crate) fn write_week(
    conn: &store::Connection,
    user_id: i64,
    week_start: &str,
    blocks: Vec<Value>,
    revision: i64,
) -> ServiceResult<(Vec<Value>, i64)> {
    Ok(store::writes::write_week(
        conn, user_id, week_start, blocks, revision,
    )?)
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
    use flexweek_engine::validate::time_block;
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
        let blocks: Vec<Value> = [school("School"), school("School again")]
            .iter()
            .map(|block| time_block(block).unwrap().to_value())
            .collect();
        // Counted inside the save's own transaction, before anything is rolled back: a row written and
        // then refused would show here.
        let (refused, rows) = with_db(&db.path, |conn| {
            store::begin_immediate(conn)?;
            let refused = write_week(conn, user, "2026-09-14", blocks, 0);
            let rows: i64 = conn
                .query_row("SELECT count(*) FROM weeks", [], |row| row.get(0))
                .unwrap();
            Ok((refused, rows))
        })
        .unwrap();
        match refused {
            Err(ServiceError::Refused(Refusal::Invalid(words))) => assert_eq!(
                words,
                r#"Two blocks in this week share the id "school". Each block needs its own id."#
            ),
            other => panic!("not refused in words: {other:?}"),
        }
        assert_eq!(rows, 0);
    }
}
