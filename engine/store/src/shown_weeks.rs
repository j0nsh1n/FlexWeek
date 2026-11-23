//! Weeks as the app shows them: a stored (Monday) week with the School and activities standing in it and
//! its homework sessions brought up to date, and a week shown from another weekday put together from the two
//! stored weeks it covers. Both the week answer and the one change function read weeks through here.

use std::collections::BTreeSet;

use flexweek_engine::shown::compose_shown_week_due;
use flexweek_engine::validate::time_block;
use rusqlite::Connection;
use serde_json::{Map, Value, json};

use crate::{
    Relay, StoreError, StoreResult, load_assignment_rows, read_week, rewrite_stored_blocks,
    standing_blocks, week_with_standing,
};

pub fn parsed_blocks(text: &str) -> StoreResult<Vec<Value>> {
    serde_json::from_str(text).map_err(|error| StoreError::Json {
        text: text.to_string(),
        error,
    })
}

/// The homework the blocks name, by id, as stored for this account.
pub fn homework_of(
    conn: &Connection,
    user_id: i64,
    blocks: &[Value],
) -> StoreResult<Map<String, Value>> {
    let ids: Vec<String> = blocks
        .iter()
        .filter_map(|block| block.get("assignment_id").and_then(Value::as_str))
        .filter(|id| !id.is_empty())
        .map(str::to_string)
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let mut owned = Map::new();
    for (id, body, _) in load_assignment_rows(conn, user_id, &ids)? {
        let body: Value = serde_json::from_str(&body).map_err(|error| StoreError::Json {
            text: body.clone(),
            error,
        })?;
        owned.insert(id, body);
    }
    Ok(owned)
}

fn check_block(value: &Value) -> Result<Value, String> {
    time_block(value).map(|block| block.to_value())
}

fn broken(why: String) -> StoreError {
    StoreError::Broken(format!("a stored block no longer reads as a block: {why}"))
}

/// Sessions brought up to date from their homework, each written as a block is written.
pub fn rewritten(blocks: Vec<Value>, owned: &Map<String, Value>) -> StoreResult<Vec<Value>> {
    rewrite_stored_blocks(
        &Value::Array(blocks),
        &Value::Object(owned.clone()),
        check_block,
    )
    .map_err(|error| match error {
        Relay::Store(error) => error,
        Relay::Caller(why) => broken(why),
    })
}

fn written(blocks: Vec<Value>) -> StoreResult<Vec<Value>> {
    blocks
        .iter()
        .map(|block| check_block(block).map_err(broken))
        .collect()
}

fn stored_with_standing(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> StoreResult<(Vec<Value>, i64)> {
    let row = read_week(conn, user_id, week_start)?;
    let stored = row.as_ref().map_or("[]", |(blocks, _)| blocks.as_str());
    let merged = parsed_blocks(&week_with_standing(conn, user_id, week_start, stored)?)?;
    Ok((merged, row.map_or(0, |(_, revision)| revision)))
}

/// A stored week as the week answer gives it, every block written out in full, and its revision.
pub fn seen_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> StoreResult<(Vec<Value>, i64)> {
    let (merged, revision) = stored_with_standing(conn, user_id, week_start)?;
    let owned = homework_of(conn, user_id, &merged)?;
    Ok((written(rewritten(merged, &owned)?)?, revision))
}

/// A stored week as saved, without the blocks standing in it, and its revision.
fn stored_part(conn: &Connection, user_id: i64, week_start: &str) -> StoreResult<Value> {
    let row = read_week(conn, user_id, week_start)?;
    let blocks = match &row {
        Some((text, _)) => parsed_blocks(text)?,
        None => Vec::new(),
    };
    let owned = homework_of(conn, user_id, &blocks)?;
    let saved = written(rewritten(blocks, &owned)?)?;
    Ok(json!({ "week_start": week_start, "blocks": saved, "revision": row.map_or(0, |(_, r)| r) }))
}

/// A stored (Monday) week as `GET /api/week` answers it.
pub fn monday_week(conn: &Connection, user_id: i64, week_start: &str) -> StoreResult<Value> {
    let (merged, revision) = stored_with_standing(conn, user_id, week_start)?;
    let owned = homework_of(conn, user_id, &merged)?;
    let repeats = standing_blocks(conn, user_id, week_start)?;
    let mut answer = Map::new();
    answer.insert("week_start".into(), Value::from(week_start));
    answer.insert("blocks".into(), Value::Array(rewritten(merged, &owned)?));
    answer.insert("revision".into(), Value::from(revision));
    if !repeats.is_empty() {
        answer.insert("repeats".into(), Value::Array(repeats));
    }
    Ok(Value::Object(answer))
}

/// A week shown from another weekday, from the two stored weeks it covers, with both as saved for Undo.
/// `between` runs just before the second stored week is read as saved, so a test can commit there.
pub fn shown_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
    (first, second): (&str, &str),
    between: impl FnOnce(),
) -> StoreResult<Value> {
    let (first_blocks, first_revision) = seen_week(conn, user_id, first)?;
    let (second_blocks, second_revision) = seen_week(conn, user_id, second)?;
    let both: Vec<Value> = first_blocks.iter().chain(&second_blocks).cloned().collect();
    let homework = homework_of(conn, user_id, &both)?;
    let blocks = compose_shown_week_due(week_start, &first_blocks, &second_blocks, &homework)?;
    let repeats = standing_blocks(conn, user_id, second)?;
    let mut answer = Map::new();
    answer.insert("week_start".into(), Value::from(week_start));
    answer.insert("blocks".into(), Value::Array(blocks));
    answer.insert("revision".into(), json!([first_revision, second_revision]));
    let first_part = stored_part(conn, user_id, first)?;
    between();
    answer.insert(
        "stored".into(),
        json!([first_part, stored_part(conn, user_id, second)?]),
    );
    if !repeats.is_empty() {
        answer.insert("repeats".into(), Value::Array(repeats));
    }
    Ok(Value::Object(answer))
}
