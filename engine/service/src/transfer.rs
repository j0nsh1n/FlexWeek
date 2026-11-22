//! Account export and import (Settings > Export my account, and Import), as `backend/app.py`'s
//! `POST /api/account-export`, `POST /api/account-import/preview` and `POST /api/account-import` do them.
//! This part reads a backup file as `TransferSnapshot` reads it.

use std::collections::BTreeSet;

use flexweek_engine::model::valid_naive_stamp;
use flexweek_engine::repeats::MAX_REPEATS;
use flexweek_engine::standing::most_standing_at_once;
use flexweek_engine::time::is_week_start;
use flexweek_engine::validate::{assignment_content, routine, time_block, whole_number};
use serde_json::{Map, Value, json};

use crate::blocks::{BlockRefused, Checked, refuse};
use crate::preferences::check_preferences;
use crate::week_saves::check_saved_week;

const REVISION_MAX: i128 = (1 << 53) - 1;
const MAX_TRANSFER_ASSIGNMENTS: usize = 1000;
const MAX_TRANSFER_ROUTINES: usize = 50;
const MAX_STANDING_ROWS: usize = 5000;

fn object<'a>(value: &'a Value, what: &str) -> Checked<&'a Map<String, Value>> {
    match value {
        Value::Object(fields) => Ok(fields),
        _ => refuse(format!("{what} must be an object")),
    }
}

fn only(fields: &Map<String, Value>, allowed: &[&str], what: &str) -> Checked<()> {
    match fields.keys().find(|key| !allowed.contains(&key.as_str())) {
        Some(extra) => refuse(format!("{what} does not take {extra}")),
        None => Ok(()),
    }
}

fn required<'a>(fields: &'a Map<String, Value>, name: &str) -> Checked<&'a Value> {
    match fields.get(name) {
        Some(value) => Ok(value),
        None => refuse(format!("{name} is required")),
    }
}

fn text(value: &Value, name: &str, least: usize, most: usize) -> Checked<String> {
    match value {
        Value::String(text) if (least..=most).contains(&text.chars().count()) => Ok(text.clone()),
        _ => refuse(format!("{name} must be {least} to {most} characters")),
    }
}

fn bounded(value: &Value, name: &str, most: i128) -> Checked<i64> {
    match whole_number(value) {
        Some(number) if (0..=most).contains(&number) => Ok(number as i64),
        _ => refuse(format!("{name} must be a whole number from 0 to {most}")),
    }
}

fn stamp(value: &Value, name: &str) -> Checked<String> {
    let Value::String(text) = value else {
        return refuse(format!("{name} must be text"));
    };
    match valid_naive_stamp(text) {
        Ok(_) => Ok(text.clone()),
        Err(_) => refuse(format!("{name} must be a date and time")),
    }
}

fn list<'a>(value: &'a Value, name: &str, most: Option<usize>) -> Checked<&'a [Value]> {
    match value {
        Value::Array(items) if most.is_none_or(|most| items.len() <= most) => Ok(items),
        _ => refuse(format!("{name} must be a list")),
    }
}

/// `TransferAssignment`: a homework with its id beside it and its revision.
fn transfer_assignment(value: &Value) -> Checked<Value> {
    let fields = object(value, "a homework")?;
    only(fields, &["id", "body", "revision"], "a homework")?;
    let id = text(required(fields, "id")?, "id", 1, 80)?;
    let body = assignment_content(required(fields, "body")?)
        .map_err(BlockRefused)?
        .to_value();
    let revision = bounded(required(fields, "revision")?, "revision", REVISION_MAX)?;
    if body["id"] != id.as_str() {
        return refuse("assignment id and body.id must match");
    }
    Ok(json!({ "id": id, "body": body, "revision": revision }))
}

/// `TransferRoutine`: a routine with when it was made and last changed.
fn transfer_routine(value: &Value) -> Checked<Value> {
    let fields = object(value, "a routine")?;
    let mut plain = fields.clone();
    let created_at = plain.shift_remove("created_at");
    let updated_at = plain.shift_remove("updated_at");
    let mut written = match routine(&Value::Object(plain))
        .map_err(BlockRefused)?
        .to_value()
    {
        Value::Object(written) => written,
        _ => return refuse("a routine must be an object"),
    };
    let (Some(created_at), Some(updated_at)) = (created_at, updated_at) else {
        return refuse("created_at and updated_at are required");
    };
    written.insert(
        "created_at".into(),
        Value::from(stamp(&created_at, "created_at")?),
    );
    written.insert(
        "updated_at".into(),
        Value::from(stamp(&updated_at, "updated_at")?),
    );
    Ok(Value::Object(written))
}

const STANDING_RULE: &str = "Only School, Setup's activities and weekly fixed times stand in every week, \
                             each with a start time and an id of its own";

/// `StandingRow`: a block standing from `from_week` on, or, with no body, stopping there.
fn standing_row(value: &Value) -> Checked<Value> {
    let fields = object(value, "a standing row")?;
    only(
        fields,
        &["id", "from_week", "position", "body"],
        "a standing row",
    )?;
    let id = text(required(fields, "id")?, "id", 1, 80)?;
    let from_week = match required(fields, "from_week")? {
        Value::String(text) if is_week_start(text) => text.clone(),
        _ => return refuse("from_week must be a Monday"),
    };
    let position = bounded(
        required(fields, "position")?,
        "position",
        MAX_REPEATS as i128 - 1,
    )?;
    let body = match required(fields, "body")? {
        Value::Null => Value::Null,
        given => {
            let block = time_block(given).map_err(BlockRefused)?;
            if block.id != id || block.kind != "locked" {
                return refuse(STANDING_RULE);
            }
            block.to_value()
        }
    };
    Ok(json!({ "id": id, "from_week": from_week, "position": position, "body": body }))
}

fn username(value: &Value) -> Checked<String> {
    match value {
        Value::String(name)
            if (3..=32).contains(&name.chars().count())
                && name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') =>
        {
            Ok(name.to_ascii_lowercase())
        }
        _ => refuse("username must be 3 to 32 letters, digits or underscores"),
    }
}

fn unique<'a>(items: impl Iterator<Item = &'a str>, rule: &str) -> Checked<BTreeSet<&'a str>> {
    let mut seen = BTreeSet::new();
    for item in items {
        if !seen.insert(item) {
            return refuse(rule.to_string());
        }
    }
    Ok(seen)
}

/// A backup file as `TransferSnapshot.model_validate(...).model_dump()` gives it, or why the app refuses it.
pub fn check_transfer(given: &Value) -> Checked<Value> {
    let fields = object(given, "a backup file")?;
    only(
        fields,
        &[
            "format",
            "exported_at",
            "username",
            "weeks",
            "assignments",
            "preferences",
            "routines",
            "standing",
        ],
        "a backup file",
    )?;
    // `Literal[3]`: the number 3, written 3 or 3.0; not text, not true.
    let format = required(fields, "format")?;
    if !(format.is_number() && whole_number(format) == Some(3)) {
        return refuse("format must be 3");
    }
    let exported_at = stamp(required(fields, "exported_at")?, "exported_at")?;
    let username = username(required(fields, "username")?)?;
    let mut weeks = Vec::new();
    for week in list(required(fields, "weeks")?, "weeks", None)? {
        let (week_start, blocks, revision) = check_saved_week(week)?;
        weeks.push(json!({ "blocks": blocks, "week_start": week_start, "revision": revision }));
    }
    let assignments = list(
        required(fields, "assignments")?,
        "assignments",
        Some(MAX_TRANSFER_ASSIGNMENTS),
    )?
    .iter()
    .map(transfer_assignment)
    .collect::<Checked<Vec<_>>>()?;
    // Before 0.18.5 a 24-hour clock was left out of the file, and 12-hour is the new default: a file
    // without one is from before.
    let preferences = match required(fields, "preferences")? {
        Value::Object(given) if !given.contains_key("clock_24h") => {
            let mut given = given.clone();
            given.insert("clock_24h".into(), Value::Bool(true));
            check_preferences(&Value::Object(given))?
        }
        given => check_preferences(given)?,
    };
    let routines = list(
        required(fields, "routines")?,
        "routines",
        Some(MAX_TRANSFER_ROUTINES),
    )?
    .iter()
    .map(transfer_routine)
    .collect::<Checked<Vec<_>>>()?;
    let standing = match fields.get("standing") {
        None | Some(Value::Null) => None,
        Some(given) => Some(
            list(given, "standing", Some(MAX_STANDING_ROWS))?
                .iter()
                .map(standing_row)
                .collect::<Checked<Vec<_>>>()?,
        ),
    };
    unique(
        weeks.iter().filter_map(|week| week["week_start"].as_str()),
        "week_start values must be unique",
    )?;
    let owned = unique(
        assignments.iter().filter_map(|item| item["id"].as_str()),
        "assignment ids must be unique",
    )?;
    unique(
        routines.iter().filter_map(|item| item["id"].as_str()),
        "routine ids must be unique",
    )?;
    for week in &weeks {
        for block in week["blocks"].as_array().into_iter().flatten() {
            if let Some(id) = block.get("assignment_id").and_then(Value::as_str)
                && !id.is_empty()
                && !owned.contains(id)
            {
                return refuse("assignment_id must name an assignment in this snapshot");
            }
        }
    }
    if let Some(rows) = &standing
        && !rows.is_empty()
        && most_standing_at_once(rows) > MAX_REPEATS
    {
        return refuse(format!(
            "a file can hold at most {MAX_REPEATS} repeating blocks standing at once"
        ));
    }
    Ok(json!({
        "format": 3,
        "exported_at": exported_at,
        "username": username,
        "weeks": weeks,
        "assignments": assignments,
        "preferences": preferences,
        "routines": routines,
        "standing": standing,
    }))
}
