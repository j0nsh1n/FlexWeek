//! The timer split preview, as `POST /api/timer-split-preview` answers it: the request is checked as
//! `TimerSplitRequest` checks it, then the engine splits the time into work and break segments.

use flexweek_engine::plan::preview_split;
use serde_json::Value;

use crate::accounts::INVALID_INPUT;
use crate::blocks::{Checked, int_field, optional, refuse};
use crate::{Refusal, ServiceError, ServiceResult};

const FIELDS: [&str; 5] = [
    "duration_min",
    "timer_work_min",
    "timer_break_min",
    "timer_long_break_min",
    "timer_long_break_every",
];

/// The checked request: (duration, work, break, long break, long break every).
fn check_split(given: &Value) -> Checked<(Option<i64>, i64, i64, i64, i64)> {
    let Value::Object(fields) = given else {
        return refuse("the request must be an object");
    };
    if let Some(extra) = fields.keys().find(|key| !FIELDS.contains(&key.as_str())) {
        return refuse(format!("the split preview does not take {extra}"));
    }
    let need = |name: &str, low: i128, high: i128| match fields.get(name) {
        Some(value) => int_field(value, name, low, high),
        None => refuse(format!("{name} is required")),
    };
    let duration = optional(fields.get("duration_min"), |value| {
        int_field(value, "duration_min", 15, 7140)
    })?;
    let work = need("timer_work_min", 1, 180)?;
    let rest = need("timer_break_min", 1, 60)?;
    let long_rest = need("timer_long_break_min", 1, 120)?;
    let every = need("timer_long_break_every", 2, 12)?;
    if duration.is_some_and(|minutes| minutes % 15 != 0) {
        return refuse("duration_min must be a multiple of 15");
    }
    Ok((duration, work, rest, long_rest, every))
}

/// The split of `duration_min` into timer segments and the notes on settings moved to the grid; bad
/// input is refused with the one sentence every bad request gets.
pub fn split_preview(given: &Value) -> ServiceResult<Value> {
    let (duration, work, rest, long_rest, every) = check_split(given)
        .map_err(|_| ServiceError::from(Refusal::Invalid(INVALID_INPUT.to_string())))?;
    Ok(preview_split(duration, work, rest, long_rest, every)?)
}
