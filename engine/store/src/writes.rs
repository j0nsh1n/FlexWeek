//! One week, one homework save and one homework delete, inside the caller's transaction, as the app's saves
//! write them. The app's routes and the one change function both write through here, so a rule is written
//! once. Refusals carry their kind and, for a change made elsewhere, the revision now stored.

use flexweek_engine::snapshot::canonical;
use flexweek_engine::validate::{assignment_content, time_block};
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::{Map, Value};

use crate::changes::{ApplyFailure, RefusalKind};
use crate::{
    Adopted, AssignmentDelete, AssignmentSave, Relay, StoreError, WeekSave, adopt_legacy_deadlines,
    delete_assignment, own_assignment_rows, read_week, rewrite_blocks, save_assignment, save_week,
};

pub const ASSIGNMENT_CONFLICT: &str =
    "This assignment changed in another window. Reload before saving.";
pub const ASSIGNMENT_LIMIT: &str = "An account holds at most 1000 assignments";
pub const ASSIGNMENT_UNKNOWN: &str = "assignment_id must name an assignment of this account";
pub const ASSIGNMENT_MISSING: &str = "Assignment not found";
pub const WEEK_CONFLICT: &str = "This week changed in another window. Reload before saving.";
pub const MAX_ASSIGNMENTS: i64 = 1000;

/// Input the save cannot take.
pub(crate) fn refuse(message: &str) -> ApplyFailure {
    ApplyFailure::Refused {
        kind: RefusalKind::Invalid,
        message: message.to_string(),
        current_revision: None,
    }
}

/// Something changed in another window, with the revision now stored when there is one.
pub(crate) fn conflict(message: &str, current_revision: Option<i64>) -> ApplyFailure {
    ApplyFailure::Refused {
        kind: RefusalKind::Conflict,
        message: message.to_string(),
        current_revision,
    }
}

fn parsed(text: &str) -> Result<Value, ApplyFailure> {
    serde_json::from_str(text).map_err(|error| {
        ApplyFailure::Store(StoreError::Json {
            text: text.to_string(),
            error,
        })
    })
}

/// Every block written out again, as a block is written after each step. Blocks the caller had checked
/// already read; one that no longer does came from stored data.
fn written(blocks: Vec<Value>) -> Result<Vec<Value>, ApplyFailure> {
    blocks
        .iter()
        .map(|block| {
            time_block(block)
                .map(|checked| checked.to_value())
                .map_err(|why| {
                    StoreError::Broken(format!("a saved block no longer reads: {why}")).into()
                })
        })
        .collect()
}

/// The new homework an old-style deadline block becomes, written as a homework save writes it.
fn encode_new_homework(body: &Value) -> Result<String, String> {
    assignment_content(body).map(|content| canonical(&content.to_value()))
}

fn stored_week_revision(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> Result<i64, ApplyFailure> {
    Ok(read_week(conn, user_id, week_start)?.map_or(0, |(_, revision)| revision))
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

/// One stored week: old-style deadline blocks become homework, the week may only name this account's
/// homework, sessions take their homework's title and colours, and the row is written at `revision`.
/// Answers the blocks as stored and the new revision.
pub fn write_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
    blocks: Vec<Value>,
    revision: i64,
) -> Result<(Vec<Value>, i64), ApplyFailure> {
    let adopted = adopt_legacy_deadlines(
        conn,
        user_id,
        week_start,
        &Value::Array(blocks),
        MAX_ASSIGNMENTS,
        encode_new_homework,
    )
    .map_err(|relay| match relay {
        Relay::Store(error) => ApplyFailure::from(error),
        Relay::Caller(why) => StoreError::Broken(format!("a deadline's homework: {why}")).into(),
    })?;
    let incoming = match adopted {
        Adopted::OverLimit => return Err(refuse(ASSIGNMENT_LIMIT)),
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
    let (owned, rows) = own_assignment_rows(conn, user_id, &ids)?;
    if !owned {
        return Err(refuse(ASSIGNMENT_UNKNOWN));
    }
    let mut homework = Map::new();
    for (id, body, _) in rows {
        homework.insert(id, parsed(&body)?);
    }
    let rewritten = rewrite_blocks(&Value::Array(incoming), &Value::Object(homework))
        .map_err(StoreError::Engine)?;
    let blocks = written(rewritten)?;
    let encoded = canonical(&Value::Array(blocks.clone()));
    let saved = match save_week(conn, user_id, week_start, &encoded, revision) {
        Ok(saved) => saved,
        Err(error @ StoreError::RepeatedBlockId(_)) => return Err(refuse(&error.to_string())),
        Err(error) => return Err(error.into()),
    };
    match saved {
        WeekSave::Ready(revision) => Ok((blocks, revision)),
        WeekSave::Conflict => Err(conflict(
            WEEK_CONFLICT,
            Some(stored_week_revision(conn, user_id, week_start)?),
        )),
    }
}

/// A checked homework written at `revision`; answers its new revision.
pub fn write_homework(
    conn: &Connection,
    user_id: i64,
    id: &str,
    content: &Value,
    revision: i64,
    limit: i64,
) -> Result<i64, ApplyFailure> {
    match save_assignment(conn, user_id, id, &canonical(content), revision, limit)? {
        AssignmentSave::Ready(stored) => Ok(stored),
        AssignmentSave::Conflict => Err(conflict(
            ASSIGNMENT_CONFLICT,
            assignment_revision(conn, user_id, id)?,
        )),
        AssignmentSave::OverLimit => Err(refuse(ASSIGNMENT_LIMIT)),
    }
}

/// A homework and its sessions deleted at `revision` (None matches no stored revision); answers which
/// weeks changed and the sessions removed from each.
pub fn remove_homework(
    conn: &Connection,
    user_id: i64,
    id: &str,
    revision: Option<i64>,
) -> Result<Value, ApplyFailure> {
    match delete_assignment(conn, user_id, id, revision)? {
        AssignmentDelete::Missing => Err(ApplyFailure::Refused {
            kind: RefusalKind::NotFound,
            message: ASSIGNMENT_MISSING.to_string(),
            current_revision: None,
        }),
        AssignmentDelete::Conflict => Err(conflict(
            ASSIGNMENT_CONFLICT,
            assignment_revision(conn, user_id, id)?,
        )),
        AssignmentDelete::Deleted(text) => parsed(&text),
    }
}
