//! A block as `backend/models.py`'s `TimeBlock` accepts and writes it: every field's type, length and
//! range, the rules between fields, pydantic's lax reading (the text "30" or 30.0 for a whole number,
//! "yes" for true), unknown fields dropped, and the written block with its defaults filled in and its
//! empty extras left out, in the model's field order. `tests/block_parity.rs` holds it to pydantic.

use flexweek_engine::model::valid_spotify_url;
use flexweek_engine::time::is_calendar_date;
use serde_json::{Map, Number, Value};

/// Why a block was refused, for the log; the student sees one sentence for every bad request.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BlockRefused(pub String);

pub(crate) type Checked<T> = Result<T, BlockRefused>;

pub(crate) fn refuse<T>(why: impl Into<String>) -> Checked<T> {
    Err(BlockRefused(why.into()))
}

/// Python's `int(text)` after pydantic strips the text and any ".0" ending: a sign, then digits with
/// single underscores between them.
fn int_from_text(text: &str) -> Option<i128> {
    let trimmed = text.trim_matches(|c: char| c.is_ascii_whitespace());
    let body = match trimmed.split_once('.') {
        Some((whole, zeros)) if !zeros.is_empty() && zeros.chars().all(|c| c == '0') => whole,
        Some(_) => return None,
        None => trimmed,
    };
    let (negative, digits) = match body.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, body.strip_prefix('+').unwrap_or(body)),
    };
    if digits.is_empty()
        || digits.starts_with('_')
        || digits.ends_with('_')
        || digits.contains("__")
    {
        return None;
    }
    let plain: String = digits.chars().filter(|c| *c != '_').collect();
    if !plain.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    let value: i128 = plain.parse().ok()?;
    Some(if negative { -value } else { value })
}

pub(crate) fn whole_number(value: &Value) -> Option<i128> {
    match value {
        Value::Bool(flag) => Some(i128::from(*flag)),
        Value::Number(number) => {
            if let Some(int) = number.as_i64() {
                return Some(i128::from(int));
            }
            if let Some(int) = number.as_u64() {
                return Some(i128::from(int));
            }
            // Text form: arbitrary precision keeps huge integers and floats as written.
            let text = number.to_string();
            if let Some(int) = int_from_text(&text).filter(|_| !text.contains(['e', 'E'])) {
                return Some(int);
            }
            let float = number.as_f64()?;
            (float.is_finite() && float.fract() == 0.0 && float.abs() < 9.2e18)
                .then_some(float as i128)
        }
        Value::String(text) => int_from_text(text),
        _ => None,
    }
}

pub(crate) fn int_field(value: &Value, name: &str, low: i128, high: i128) -> Checked<i64> {
    match whole_number(value) {
        Some(int) if (low..=high).contains(&int) => Ok(int as i64),
        _ => refuse(format!(
            "{name} must be a whole number from {low} to {high}"
        )),
    }
}

pub(crate) fn bool_field(value: &Value, name: &str) -> Checked<bool> {
    let read = match value {
        Value::Bool(flag) => Some(*flag),
        Value::Number(number) => match number.as_f64() {
            Some(0.0) => Some(false),
            Some(1.0) => Some(true),
            _ => None,
        },
        Value::String(text) => match text.to_ascii_lowercase().as_str() {
            "0" | "off" | "f" | "false" | "n" | "no" => Some(false),
            "1" | "on" | "t" | "true" | "y" | "yes" => Some(true),
            _ => None,
        },
        _ => None,
    };
    read.map_or_else(|| refuse(format!("{name} must be true or false")), Ok)
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

fn day_list(value: &Value, name: &str, low: usize, high: usize) -> Checked<Vec<i64>> {
    let Value::Array(items) = value else {
        return refuse(format!("{name} must be a list"));
    };
    if !(low..=high).contains(&items.len()) {
        return refuse(format!("{name} must hold {low} to {high} days"));
    }
    let days = items
        .iter()
        .map(|item| whole_number(item).and_then(|day| i64::try_from(day).ok()))
        .collect::<Option<Vec<i64>>>();
    let Some(days) = days else {
        return refuse(format!("{name} must be whole numbers"));
    };
    if days.iter().any(|day| !(0..=6).contains(day)) {
        return refuse(format!("{name} must be in 0..6 (Mon..Sun)"));
    }
    Ok(days)
}

fn priority(value: Option<&Value>) -> Checked<i64> {
    let Some(value) = value else { return Ok(3) };
    let read = match value {
        Value::Bool(_) | Value::Number(_) => whole_number(value),
        _ => None,
    };
    match read {
        Some(level @ 1..=4) => Ok(level as i64),
        _ => refuse("priority must be 1, 2, 3 or 4"),
    }
}

/// The block as `TimeBlock.model_validate(value).model_dump()` gives it, or why pydantic refuses it.
pub fn check_block(value: &Value) -> Checked<Value> {
    let Value::Object(input) = value else {
        return refuse("a block must be an object");
    };
    let get = |name: &str| input.get(name);
    let required =
        |name: &str| get(name).ok_or_else(|| BlockRefused(format!("{name} is required")));

    let id = text_field(required("id")?, "id", 1, 80)?;
    let title = text_field(required("title")?, "title", 1, 80)?;
    let kind = one_of(required("kind")?, "kind", &["locked", "flexible"])?;
    let duration_min = int_field(required("duration_min")?, "duration_min", 1, 7140)?;
    let days = day_list(required("days")?, "days", 1, 7)?;
    let priority = priority(get("priority"))?;
    let energy = match get("energy") {
        None => "medium".to_string(),
        Some(value) => one_of(value, "energy", &["high", "medium", "low"])?,
    };
    let earliest = optional(get("earliest"), |v| text_field(v, "earliest", 0, 40))?;
    let latest = optional(get("latest"), |v| text_field(v, "latest", 0, 40))?;
    let start = optional(get("start"), |v| text_field(v, "start", 0, 5))?;
    let course = optional(get("course"), |v| text_field(v, "course", 0, 40))?;
    let category = optional(get("category"), |v| text_field(v, "category", 0, 32))?;
    let completed = defaulted(get("completed"), false, |v| bool_field(v, "completed"))?;
    let completed_day = optional(get("completed_day"), |v| {
        int_field(v, "completed_day", 0, 6)
    })?;
    let missed_days = match get("missed_days") {
        None => Vec::new(),
        Some(value) => day_list(value, "missed_days", 0, 7)?,
    };
    let unique: std::collections::BTreeSet<_> = missed_days.iter().collect();
    if unique.len() != missed_days.len() {
        return refuse("missed_days must be unique values in 0..6");
    }
    let spotify_url = match get("spotify_url") {
        None | Some(Value::Null) => None,
        Some(Value::String(text)) if text.chars().count() <= 500 => {
            valid_spotify_url(Some(text)).map_err(|error| BlockRefused(error.message))?
        }
        Some(_) => return refuse("spotify_url must be an open.spotify.com share link"),
    };
    let focus_sessions = defaulted(get("focus_sessions"), 0, |v| {
        int_field(v, "focus_sessions", 0, 9999)
    })?;
    let focus_minutes = defaulted(get("focus_minutes"), 0, |v| {
        int_field(v, "focus_minutes", 0, 71400)
    })?;
    let pomodoro_parent_id = optional(get("pomodoro_parent_id"), |v| {
        text_field(v, "pomodoro_parent_id", 1, 80)
    })?;
    let pomodoro_role = optional(get("pomodoro_role"), |v| {
        one_of(v, "pomodoro_role", &["work", "break"])
    })?;
    let pomodoro_index = optional(get("pomodoro_index"), |v| {
        int_field(v, "pomodoro_index", 1, 999)
    })?;
    let pinned = defaulted(get("pinned"), false, |v| bool_field(v, "pinned"))?;
    let prefer_earliest = defaulted(get("prefer_earliest"), false, |v| {
        bool_field(v, "prefer_earliest")
    })?;
    let keep_whole = defaulted(get("keep_whole"), false, |v| bool_field(v, "keep_whole"))?;
    let assignment_id = optional(get("assignment_id"), |v| {
        text_field(v, "assignment_id", 1, 80)
    })?;
    let until = optional(get("until"), |v| text_field(v, "until", 0, 10))?;
    if until.as_deref().is_some_and(|day| !is_calendar_date(day)) {
        return refuse("until must be a date written YYYY-MM-DD");
    }

    // The rules between fields, in the order the model checks them.
    let flexible = kind == "flexible";
    if pinned && (!flexible || start.is_none() || days.len() != 1) {
        return refuse("pinned requires a flexible block with a start on one day");
    }
    if !missed_days.is_empty() && kind != "locked" {
        return refuse("only locked blocks can have missed days");
    }
    if !missed_days.iter().all(|day| days.contains(day)) {
        return refuse("missed days must be occurrences of the block");
    }
    if let Some(day) = completed_day
        && (!flexible || !completed || start.is_none() || !days.contains(&day))
    {
        return refuse(
            "completed_day requires a completed flexible block with a start on a candidate day",
        );
    }
    if assignment_id.is_some() {
        if latest.is_some() {
            return refuse("a session cannot carry latest");
        }
        if focus_minutes != 0 || focus_sessions != 0 {
            return refuse("session focus must be 0");
        }
        let work_chunk = kind == "locked" && pomodoro_role.as_deref() == Some("work");
        if !flexible && !work_chunk {
            return refuse(
                "assignment_id is only valid on a work session or a pomodoro work chunk",
            );
        }
    }

    let mut out = Map::new();
    let text = |value: Option<String>| value.map_or(Value::Null, Value::String);
    out.insert("id".into(), Value::String(id));
    out.insert("title".into(), Value::String(title));
    out.insert("kind".into(), Value::String(kind));
    out.insert(
        "duration_min".into(),
        Value::Number(Number::from(duration_min)),
    );
    out.insert("days".into(), Value::from(days));
    out.insert("priority".into(), Value::Number(Number::from(priority)));
    out.insert("energy".into(), Value::String(energy));
    out.insert("earliest".into(), text(earliest));
    out.insert("latest".into(), text(latest));
    out.insert("start".into(), text(start));
    out.insert("course".into(), text(course));
    // The rest are left out when empty, as the model's exclude_if rules say.
    if let Some(category) = category {
        out.insert("category".into(), Value::String(category));
    }
    if completed {
        out.insert("completed".into(), Value::Bool(true));
    }
    if let Some(day) = completed_day {
        out.insert("completed_day".into(), Value::from(day));
    }
    if !missed_days.is_empty() {
        out.insert("missed_days".into(), Value::from(missed_days));
    }
    if let Some(url) = spotify_url {
        out.insert("spotify_url".into(), Value::String(url));
    }
    if focus_sessions != 0 {
        out.insert("focus_sessions".into(), Value::from(focus_sessions));
    }
    if focus_minutes != 0 {
        out.insert("focus_minutes".into(), Value::from(focus_minutes));
    }
    if let Some(parent) = pomodoro_parent_id {
        out.insert("pomodoro_parent_id".into(), Value::String(parent));
    }
    if let Some(role) = pomodoro_role {
        out.insert("pomodoro_role".into(), Value::String(role));
    }
    if let Some(index) = pomodoro_index {
        out.insert("pomodoro_index".into(), Value::from(index));
    }
    if pinned {
        out.insert("pinned".into(), Value::Bool(true));
    }
    if prefer_earliest {
        out.insert("prefer_earliest".into(), Value::Bool(true));
    }
    if keep_whole {
        out.insert("keep_whole".into(), Value::Bool(true));
    }
    if let Some(id) = assignment_id {
        out.insert("assignment_id".into(), Value::String(id));
    }
    if let Some(day) = until {
        out.insert("until".into(), Value::String(day));
    }
    Ok(Value::Object(out))
}
