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

/// The app keeps 20 restore points (`MAX_RESTORE_POINTS`). The assistant keeps at most this many
/// of its own, so a busy assistant never pushes out the student's points.
pub const ASSISTANT_POINTS: i64 = 10;

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
    conn.execute(
        "DELETE FROM restore_points WHERE user_id = ?1 AND id LIKE 'rp-assistant-%' AND id != ?2
        AND seq NOT IN (
            SELECT seq FROM restore_points WHERE user_id = ?1 AND id LIKE 'rp-assistant-%'
            AND id != ?2 ORDER BY seq DESC LIMIT ?3
        )",
        (user_id, keep.unwrap_or(""), ASSISTANT_POINTS - 1),
    )
    .map_err(|error| session::storage_sentence(flexweek_store::StoreError::from(error)))?;
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
