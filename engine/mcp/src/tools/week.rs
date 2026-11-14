//! Shown-week helpers shared across MCP read, write, and plan tools.
//!
//! A week starting on Monday maps 1:1 to a stored Monday week; any other `week_start` spans two
//! stored Monday weeks (`first` and `second`) composed and split through `flexweek_engine::shown`.

use flexweek_engine::shown::{compose_shown_week_due, shown_parts, split_shown_week};
use flexweek_engine::time::{is_calendar_date, is_week_start, week_start_on};
use flexweek_store::{Connection, StoreError, WeekInput, load_assignment_rows, read_week};
use rmcp::schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};

use crate::{host, session};

pub(crate) const WEEK_START_RULE: &str =
    "week_start must be a Monday from 2000-01-03 through 2099-12-28, or 1999-12-27";

/// Revision accepted by tools that work on a week: an integer for a Monday stored week, or
/// `[first_revision, second_revision]` for a shown week starting on another day.
#[derive(Clone, Deserialize, Serialize, JsonSchema)]
#[serde(untagged)]
#[schemars(crate = "rmcp::schemars")]
pub(crate) enum RevisionArg {
    One(i64),
    Pair([i64; 2]),
}

/// Resolved target week from `week_start` and the current `first_weekday`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) enum WeekTarget {
    StoredMonday,
    Shown {
        first: String,
        second: String,
        offset: i64,
    },
}

/// Weekday name (`"monday"` .. `"sunday"`) for `week_start`.
pub(crate) fn weekday_name(week_start: &str) -> Result<&'static str, String> {
    let idx = match shown_parts(week_start).map_err(|error| error.message)? {
        None => 0,
        Some((_, _, offset)) => usize::try_from(offset).unwrap_or(0),
    };
    host::WEEK_STARTS
        .get(idx)
        .copied()
        .ok_or_else(|| "invalid weekday".to_string())
}

/// Inserts `"week_starts_on"` into a JSON object that names `week_start`.
pub(crate) fn add_week_starts_on(value: &mut Value, week_start: &str) -> Result<(), String> {
    let day = weekday_name(week_start)?;
    if let Some(fields) = value.as_object_mut() {
        fields.insert("week_starts_on".into(), json!(day));
    }
    Ok(())
}

/// Resolves `week_start` against `first_weekday`.
///
/// A valid Monday stored week (`is_week_start`) is always accepted as `StoredMonday` even when
/// `first_weekday != 0`, keeping older clients working when the computer's week start is another
/// day. Otherwise `week_start` must match `first_weekday` and span two stored weeks.
pub(crate) fn resolve_week(week_start: &str, first_weekday: u32) -> Result<WeekTarget, String> {
    if is_week_start(week_start) {
        return Ok(WeekTarget::StoredMonday);
    }
    if first_weekday == 0 {
        return Err(WEEK_START_RULE.into());
    }
    let day = host::WEEK_STARTS[first_weekday as usize];
    let refusal = || {
        format!(
            "week_start must be a {day} (or a Monday stored week): weeks on this computer start on {day}"
        )
    };
    if !is_calendar_date(week_start) {
        return Err(refusal());
    }
    let starts = week_start_on(week_start, first_weekday).map_err(|_| refusal())?;
    if starts != week_start {
        return Err(refusal());
    }
    let Some((first, second, offset)) = shown_parts(week_start).map_err(|err| err.message)? else {
        return Ok(WeekTarget::StoredMonday);
    };
    if !is_week_start(&first) || !is_week_start(&second) {
        return Err(WEEK_START_RULE.into());
    }
    Ok(WeekTarget::Shown {
        first,
        second,
        offset,
    })
}

/// Resolves an optional `RevisionArg` for a Monday stored week.
pub(crate) fn expect_monday_revision(
    revision: Option<&RevisionArg>,
    fallback: i64,
) -> Result<i64, String> {
    match revision {
        None => Ok(fallback),
        Some(RevisionArg::One(value)) => Ok(*value),
        Some(RevisionArg::Pair(_)) => {
            Err("expected_revision must be an integer for a Monday week".into())
        }
    }
}

/// Resolves an optional `RevisionArg` for a two-week shown week.
pub(crate) fn expect_shown_revision(
    revision: Option<&RevisionArg>,
    fallback: [i64; 2],
) -> Result<[i64; 2], String> {
    match revision {
        None => Ok(fallback),
        Some(RevisionArg::Pair(pair)) => Ok(*pair),
        Some(RevisionArg::One(_)) => Err(
            "expected_revision must be [first_revision, second_revision] for a week not starting on Monday"
                .into(),
        ),
    }
}

/// Stored revision (0 if never saved) of a Monday week.
pub(crate) fn week_revision(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> Result<i64, String> {
    let row = read_week(conn, user_id, week_start).map_err(session::storage_sentence)?;
    Ok(row.map_or(0, |(_, revision)| revision))
}

/// Checks `[first_rev, second_rev]` before saving a shown week. On mismatch, rolls back the open
/// write transaction and returns the standard conflict object with `"current_revision": [r1, r2]`.
pub(crate) fn check_shown_revision(
    conn: &Connection,
    first_rev: i64,
    second_rev: i64,
    expected: [i64; 2],
) -> Result<(), Value> {
    if [first_rev, second_rev] == expected {
        return Ok(());
    }
    let _ = conn.execute_batch("ROLLBACK");
    Err(json!({
        "error": "conflict",
        "current_revision": [first_rev, second_rev],
    }))
}

/// Loads the assignment JSON objects referenced by any block in `first` or `second`.
pub(crate) fn assignment_map_for_blocks(
    conn: &Connection,
    user_id: i64,
    first: &[Value],
    second: &[Value],
) -> Result<Map<String, Value>, String> {
    let ids: Vec<String> = first
        .iter()
        .chain(second)
        .filter_map(|block| block.get("assignment_id").and_then(Value::as_str))
        .map(str::to_string)
        .collect();
    let mut homework = Map::new();
    for (id, body, _) in
        load_assignment_rows(conn, user_id, &ids).map_err(session::storage_sentence)?
    {
        let parsed = serde_json::from_str(&body)
            .map_err(|error| session::storage_sentence(StoreError::Json { text: body, error }))?;
        homework.insert(id, parsed);
    }
    Ok(homework)
}

/// Composes a shown week from its two seen stored weeks using `compose_shown_week_due`.
pub(crate) fn compose_shown_blocks(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
    first: &[Value],
    second: &[Value],
) -> Result<Vec<Value>, String> {
    let homework = assignment_map_for_blocks(conn, user_id, first, second)?;
    compose_shown_week_due(week_start, first, second, &homework).map_err(|error| error.message)
}

/// Splits `shown` back onto `(first, second)` via `flexweek_engine::shown::split_shown_week`,
/// returning `WeekInput` entries only for stored weeks whose blocks changed.
#[allow(clippy::too_many_arguments)]
pub(crate) fn split_shown_inputs(
    week_start: &str,
    shown: &[Value],
    first_start: &str,
    first_seen: &[Value],
    first_rev: i64,
    second_start: &str,
    second_seen: &[Value],
    second_rev: i64,
) -> Result<Vec<WeekInput>, String> {
    let (first_new, second_new) =
        split_shown_week(week_start, shown, first_seen, second_seen).map_err(|err| err.message)?;
    let mut inputs = Vec::new();
    if first_new != first_seen {
        inputs.push(WeekInput {
            week_start: first_start.to_string(),
            blocks: first_new,
            revision: first_rev,
        });
    }
    if second_new != second_seen {
        inputs.push(WeekInput {
            week_start: second_start.to_string(),
            blocks: second_new,
            revision: second_rev,
        });
    }
    Ok(inputs)
}

/// Saves the exact tool reply inside the remembered operation row so retries return identical
/// `[first_rev, second_rev]` revisions, `week_starts_on`, `beside`, and `block_id`.
pub(crate) fn remember_shown_reply(
    conn: &Connection,
    user_id: i64,
    operation_id: &str,
    applied: &Value,
    reply: &Value,
) -> Result<(), String> {
    let mut saved = applied.clone();
    saved["shown_reply"] = reply.clone();
    conn.execute(
        "UPDATE operations SET response = ?1 WHERE user_id = ?2 AND operation_id = ?3",
        (
            flexweek_engine::snapshot::canonical(&saved),
            user_id,
            operation_id,
        ),
    )
    .map_err(|error| session::storage_sentence(StoreError::from(error)))?;
    Ok(())
}
