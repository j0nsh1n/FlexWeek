//! Week rows. Python still encodes the block list and maps a conflict to HTTP.

use std::collections::HashSet;

use rusqlite::{Connection, OptionalExtension, params};

use crate::{StoreError, StoreResult, defer_write};

#[derive(Debug, PartialEq, Eq)]
pub enum WeekSave {
    Ready(i64),
    Conflict,
}

pub fn list_account_weeks(conn: &Connection, user_id: i64) -> StoreResult<Vec<(String, String)>> {
    let mut stmt = conn.prepare("SELECT week_start, blocks FROM weeks WHERE user_id = ?1")?;
    let rows = stmt
        .query_map(params![user_id], |row| Ok((row.get(0)?, row.get(1)?)))?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(rows)
}

/// The first id that a block list uses twice. Text that is not a list of blocks has none to repeat.
pub(crate) fn repeated_block_id(encoded: &str) -> Option<String> {
    let blocks: Vec<serde_json::Value> = serde_json::from_str(encoded).ok()?;
    let mut seen = HashSet::new();
    blocks
        .iter()
        .filter_map(|block| block.get("id")?.as_str())
        .find(|id| !seen.insert(*id))
        .map(str::to_string)
}

/// Missing row is stored text `"[]"` at revision 0, so an empty save does not insert. A list that
/// repeats a block id is refused before anything is read or written.
pub fn save_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
    encoded: &str,
    revision: i64,
) -> StoreResult<WeekSave> {
    if let Some(id) = repeated_block_id(encoded) {
        return Err(StoreError::RepeatedBlockId(id));
    }
    let stored: Option<(String, i64)> = conn
        .query_row(
            "SELECT blocks, revision FROM weeks WHERE user_id = ?1 AND week_start = ?2",
            params![user_id, week_start],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .optional()?;
    let (stored_blocks, stored_revision) = stored.unwrap_or_else(|| ("[]".to_string(), 0));
    if encoded == stored_blocks {
        return Ok(WeekSave::Ready(stored_revision));
    }
    if revision != stored_revision {
        return Ok(WeekSave::Conflict);
    }
    defer_write(
        conn,
        "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 1)
        ON CONFLICT(user_id, week_start)
        DO UPDATE SET blocks = excluded.blocks, revision = revision + 1",
        params![user_id, week_start, encoded],
    )?;
    Ok(WeekSave::Ready(revision + 1))
}

/// `(blocks, revision)`; None for a week nobody has saved.
pub fn read_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> StoreResult<Option<(String, i64)>> {
    Ok(conn
        .query_row(
            "SELECT blocks, revision FROM weeks WHERE user_id = ?1 AND week_start = ?2",
            params![user_id, week_start],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .optional()?)
}

pub fn week_blocks(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> StoreResult<Option<String>> {
    Ok(conn
        .query_row(
            "SELECT blocks FROM weeks WHERE user_id = ?1 AND week_start = ?2",
            params![user_id, week_start],
            |row| row.get(0),
        )
        .optional()?)
}

pub fn week_starts(conn: &Connection, user_id: i64) -> StoreResult<Vec<String>> {
    let mut stmt =
        conn.prepare("SELECT week_start FROM weeks WHERE user_id = ?1 ORDER BY week_start")?;
    let rows = stmt
        .query_map(params![user_id], |row| row.get(0))?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(rows)
}
