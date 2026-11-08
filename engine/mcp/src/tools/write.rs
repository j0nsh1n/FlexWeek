//! Shared pieces of a write tool: the operation id, the argument digest, and the
//! sentence a stale revision returns.

use flexweek_engine::snapshot::canonical;
use flexweek_store::{ApplyFailure, payload_digest};
use serde_json::{Value, json};

use crate::host;
use crate::session;

pub const REACHES_PHONE: &str = "when FlexWeek is open on this computer with a phone paired";
pub const OPERATION_CONFLICT: &str = "This operation was already used with different data.";

pub fn operation_key(raw: &str) -> Result<String, String> {
    let count = raw.chars().count();
    if count < 8 {
        return Err("String should have at least 8 characters".into());
    }
    if count > 80 {
        return Err("String should have at most 80 characters".into());
    }
    Ok(format!("mcp:{raw}"))
}

pub fn argument_digest(tool: &str, operation_id: &str, arguments: &Value) -> String {
    payload_digest(&json!({
        "arguments": arguments,
        "operation_id": operation_id,
        "tool": tool,
    }))
}

pub fn stable(value: Value) -> Result<Value, String> {
    let text = canonical(&value);
    serde_json::from_str(&text).map_err(|_| session::STORAGE_UNAVAILABLE.to_string())
}

pub fn from_apply(result: Result<Value, ApplyFailure>) -> Result<Value, String> {
    match result {
        Ok(value) => stable(value),
        Err(ApplyFailure::Refused {
            current_revision: Some(current_revision),
            ..
        }) => Ok(json!({
            "error": "conflict",
            "current_revision": current_revision,
        })),
        Err(ApplyFailure::Refused {
            message,
            current_revision: None,
        }) => Err(message),
        Err(ApplyFailure::Store(error)) => Err(session::storage_sentence(error)),
    }
}

/// The app keeps 20 restore points (`MAX_RESTORE_POINTS` in the store), dropping the oldest of any
/// origin. The assistant keeps at most `ASSISTANT_POINTS` of its own and never more than the room the
/// student's points leave under the 20, so the store's prune never reaches a student's point.
pub const ASSISTANT_POINTS: i64 = 10;
const ALL_POINTS: i64 = 20;

fn point_token(operation_id: &str) -> String {
    format!(
        "assistant-{}",
        &flexweek_store::digest(&format!("restore:{operation_id}"))[..16]
    )
}

/// The restore point an assistant write saves first. It comes from the operation id, so a retry
/// names the same point.
pub fn point_id(operation_id: &str) -> String {
    format!("rp-{}", point_token(operation_id))
}

/// Makes room for the restore point the next `apply` saves before it changes anything, and returns
/// its token and label. `keep` is never pruned: the point a restore brings back.
pub fn restore_point_before(
    conn: &flexweek_store::Connection,
    user_id: i64,
    tool: &str,
    operation_id: &str,
    keep: Option<&str>,
    now: &str,
) -> Result<(String, String), String> {
    let storage = |error| session::storage_sentence(flexweek_store::StoreError::from(error));
    let keep = keep.unwrap_or("");
    // The points that stay whatever the assistant prunes (the student's own, and `keep`), and
    // whether `keep` is one of the assistant's.
    let (fixed, kept_assistant): (i64, i64) = conn
        .query_row(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE id LIKE 'rp-assistant-%')
            FROM restore_points WHERE user_id = ?1 AND (id NOT LIKE 'rp-assistant-%' OR id = ?2)",
            (user_id, keep),
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .map_err(storage)?;
    // Room for the assistant's older points, leaving one place for the point about to be saved.
    let room = (ASSISTANT_POINTS - 1 - kept_assistant)
        .min(ALL_POINTS - 1 - fixed)
        .max(0);
    conn.execute(
        "DELETE FROM restore_points WHERE user_id = ?1 AND id LIKE 'rp-assistant-%' AND id != ?2
        AND seq NOT IN (
            SELECT seq FROM restore_points WHERE user_id = ?1 AND id LIKE 'rp-assistant-%'
            AND id != ?2 ORDER BY seq DESC LIMIT ?3
        )",
        (user_id, keep, room),
    )
    .map_err(storage)?;
    Ok((
        point_token(operation_id),
        format!("Before assistant {tool} — {now}"),
    ))
}

pub fn finish(name: &str, result: Result<Value, String>) -> Result<String, String> {
    match result {
        Ok(value) => {
            let class = if value.get("error").is_some() {
                "error"
            } else {
                "ok"
            };
            host::log_line(&format!("{name} {class}"));
            Ok(value.to_string())
        }
        Err(message) => {
            host::log_line(&format!("{name} error"));
            Err(message)
        }
    }
}
