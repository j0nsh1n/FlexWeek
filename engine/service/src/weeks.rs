//! Reading weeks as `backend/app.py`'s `GET /api/week` and `GET /api/weeks` answer: a stored (Monday)
//! week with the School and activities standing in it and its homework sessions brought up to date,
//! or a week shown from another weekday, put together from the two stored weeks it covers with both
//! of them as saved, for Undo. The caller resolves "this week" from its clock.

use std::collections::BTreeSet;
use std::path::Path;

use flexweek_engine::shown::{compose_shown_week_due, shown_parts};
use flexweek_engine::time::{is_calendar_date, is_week_start};
use flexweek_store::{self as store, Connection, Relay};
use serde_json::{Map, Value, json};

use crate::blocks::{BlockRefused, check_block};
use crate::{Refusal, ServiceError, ServiceResult, with_db};

pub const WEEK_START_RULE: &str =
    "week_start must be a Monday from 2000-01-03 through 2099-12-28, or 1999-12-27";

fn parsed(text: &str) -> ServiceResult<Vec<Value>> {
    serde_json::from_str(text).map_err(|error| {
        store::StoreError::Json {
            text: text.to_string(),
            error,
        }
        .into()
    })
}

fn homework_of(
    conn: &Connection,
    user_id: i64,
    blocks: &[Value],
) -> ServiceResult<Map<String, Value>> {
    let ids: Vec<String> = blocks
        .iter()
        .filter_map(|block| block.get("assignment_id").and_then(Value::as_str))
        .filter(|id| !id.is_empty())
        .map(str::to_string)
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let mut owned = Map::new();
    for (id, body, _) in store::load_assignment_rows(conn, user_id, &ids)? {
        let body: Value = serde_json::from_str(&body).map_err(|error| store::StoreError::Json {
            text: body.clone(),
            error,
        })?;
        owned.insert(id, body);
    }
    Ok(owned)
}

fn broken(refused: BlockRefused) -> ServiceError {
    ServiceError::Broken(format!(
        "a stored block no longer reads as a block: {}",
        refused.0
    ))
}

/// Sessions brought up to date from their homework, each written as a block is written.
fn rewritten(blocks: Vec<Value>, owned: &Map<String, Value>) -> ServiceResult<Vec<Value>> {
    store::rewrite_stored_blocks(
        &Value::Array(blocks),
        &Value::Object(owned.clone()),
        check_block,
    )
    .map_err(|error| match error {
        Relay::Store(error) => error.into(),
        Relay::Caller(refused) => broken(refused),
    })
}

fn written(blocks: Vec<Value>) -> ServiceResult<Vec<Value>> {
    blocks
        .iter()
        .map(|block| check_block(block).map_err(broken))
        .collect()
}

fn stored_with_standing(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> ServiceResult<(Vec<Value>, i64)> {
    let row = store::read_week(conn, user_id, week_start)?;
    let stored = row.as_ref().map_or("[]", |(blocks, _)| blocks.as_str());
    let merged = parsed(&store::week_with_standing(
        conn, user_id, week_start, stored,
    )?)?;
    Ok((merged, row.map_or(0, |(_, revision)| revision)))
}

/// A stored week as the week answer gives it, every block written out in full, and its revision.
fn seen_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> ServiceResult<(Vec<Value>, i64)> {
    let (merged, revision) = stored_with_standing(conn, user_id, week_start)?;
    let owned = homework_of(conn, user_id, &merged)?;
    Ok((written(rewritten(merged, &owned)?)?, revision))
}

/// A stored week as saved, without the blocks standing in it, and its revision.
fn stored_part(conn: &Connection, user_id: i64, week_start: &str) -> ServiceResult<Value> {
    let row = store::read_week(conn, user_id, week_start)?;
    let blocks = match &row {
        Some((text, _)) => parsed(text)?,
        None => Vec::new(),
    };
    let owned = homework_of(conn, user_id, &blocks)?;
    let saved = written(rewritten(blocks, &owned)?)?;
    Ok(json!({ "week_start": week_start, "blocks": saved, "revision": row.map_or(0, |(_, r)| r) }))
}

fn monday_week(conn: &Connection, user_id: i64, week_start: &str) -> ServiceResult<Value> {
    let (merged, revision) = stored_with_standing(conn, user_id, week_start)?;
    let owned = homework_of(conn, user_id, &merged)?;
    let repeats = store::standing_blocks(conn, user_id, week_start)?;
    let mut answer = Map::new();
    answer.insert("week_start".into(), Value::from(week_start));
    answer.insert("blocks".into(), Value::Array(rewritten(merged, &owned)?));
    answer.insert("revision".into(), Value::from(revision));
    if !repeats.is_empty() {
        answer.insert("repeats".into(), Value::Array(repeats));
    }
    Ok(Value::Object(answer))
}

fn shown_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
    first: &str,
    second: &str,
) -> ServiceResult<Value> {
    let (first_blocks, first_revision) = seen_week(conn, user_id, first)?;
    let (second_blocks, second_revision) = seen_week(conn, user_id, second)?;
    let both: Vec<Value> = first_blocks.iter().chain(&second_blocks).cloned().collect();
    let homework = homework_of(conn, user_id, &both)?;
    let blocks = compose_shown_week_due(week_start, &first_blocks, &second_blocks, &homework)?;
    let repeats = store::standing_blocks(conn, user_id, second)?;
    let mut answer = Map::new();
    answer.insert("week_start".into(), Value::from(week_start));
    answer.insert("blocks".into(), Value::Array(blocks));
    answer.insert("revision".into(), json!([first_revision, second_revision]));
    answer.insert(
        "stored".into(),
        json!([
            stored_part(conn, user_id, first)?,
            stored_part(conn, user_id, second)?
        ]),
    );
    if !repeats.is_empty() {
        answer.insert("repeats".into(), Value::Array(repeats));
    }
    Ok(Value::Object(answer))
}

/// The week from `week_start`: a Monday is one stored week; another calendar day shows the seven days
/// from it, taken from the two stored weeks it covers, read in one snapshot so both come from the same
/// moment. A week nobody saved is empty with revision 0.
pub fn read_week(path: &Path, user_id: i64, week_start: &str) -> ServiceResult<Value> {
    let parts = if is_week_start(week_start) || !is_calendar_date(week_start) {
        None
    } else {
        shown_parts(week_start)?
    };
    if let Some((first, second, _)) = parts {
        return with_db(path, |conn| {
            store::begin(conn)?;
            shown_week(conn, user_id, week_start, &first, &second)
        });
    }
    if !is_week_start(week_start) {
        return Err(Refusal::Invalid(WEEK_START_RULE.to_string()).into());
    }
    with_db(path, |conn| monday_week(conn, user_id, week_start))
}

/// The Mondays of every week the account has saved, oldest first.
pub fn list_weeks(path: &Path, user_id: i64) -> ServiceResult<Value> {
    let weeks = with_db(path, |conn| Ok(store::week_starts(conn, user_id)?))?;
    Ok(json!({ "weeks": weeks }))
}
