//! A block as `backend/models.py`'s `TimeBlock` accepts and writes it, through the engine's check, and the
//! small readers the preferences and timer checks share: pydantic's lax reading (the text "30" or 30.0 for
//! a whole number, "yes" for true). `tests/block_parity.rs` holds the block check to pydantic.

use flexweek_engine::validate::{time_block, yes_or_no};
use serde_json::Value;

/// Why a block was refused, for the log; the student sees one sentence for every bad request.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BlockRefused(pub String);

pub(crate) type Checked<T> = Result<T, BlockRefused>;

pub(crate) fn refuse<T>(why: impl Into<String>) -> Checked<T> {
    Err(BlockRefused(why.into()))
}

pub(crate) use flexweek_engine::validate::whole_number;

pub(crate) fn int_field(value: &Value, name: &str, low: i128, high: i128) -> Checked<i64> {
    match whole_number(value) {
        Some(int) if (low..=high).contains(&int) => Ok(int as i64),
        _ => refuse(format!(
            "{name} must be a whole number from {low} to {high}"
        )),
    }
}

pub(crate) fn bool_field(value: &Value, name: &str) -> Checked<bool> {
    yes_or_no(value).map_or_else(|| refuse(format!("{name} must be true or false")), Ok)
}

pub(crate) fn text_field(value: &Value, name: &str, low: usize, high: usize) -> Checked<String> {
    match value {
        Value::String(text) if (low..=high).contains(&text.chars().count()) => Ok(text.clone()),
        _ => refuse(format!("{name} must be text of {low} to {high} characters")),
    }
}

pub(crate) fn optional<T>(
    value: Option<&Value>,
    read: impl FnOnce(&Value) -> Checked<T>,
) -> Checked<Option<T>> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(value) => read(value).map(Some),
    }
}

/// A field with a default that cannot be empty: missing takes the default, but null is refused.
pub(crate) fn defaulted<T>(
    value: Option<&Value>,
    default: T,
    read: impl FnOnce(&Value) -> Checked<T>,
) -> Checked<T> {
    match value {
        None => Ok(default),
        Some(value) => read(value),
    }
}

pub(crate) fn one_of(value: &Value, name: &str, allowed: &[&str]) -> Checked<String> {
    match value {
        Value::String(text) if allowed.contains(&text.as_str()) => Ok(text.clone()),
        _ => refuse(format!("{name} must be one of {}", allowed.join(", "))),
    }
}

/// The block as `TimeBlock.model_validate(value).model_dump()` gives it, or why pydantic refuses it: the
/// engine's check, the one rule the desktop and the assistant share (Jonathan, 2026-11-22).
pub fn check_block(value: &Value) -> Checked<Value> {
    time_block(value)
        .map(|block| block.to_value())
        .map_err(BlockRefused)
}
