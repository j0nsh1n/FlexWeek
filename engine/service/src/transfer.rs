//! Account export and import (Settings > Export my account, and Import), as `backend/app.py`'s
//! `POST /api/account-export`, `POST /api/account-import/preview` and `POST /api/account-import` do them.
//! A backup file is read as `TransferSnapshot` reads it.

use std::collections::BTreeSet;
use std::path::Path;

use flexweek_engine::model::valid_naive_stamp;
use flexweek_engine::repeats::MAX_REPEATS;
use flexweek_engine::snapshot::{canonical, diff_transfer, state_token, transfer_fits};
use flexweek_engine::standing::most_standing_at_once;
use flexweek_engine::time::is_week_start;
use flexweek_engine::validate::{assignment_content, routine, time_block, whole_number};
use flexweek_store::{self as store, Connection, StoreError};
use serde_json::{Map, Value, json};

use crate::accounts::{Account, Asker, INVALID_INPUT, require_password, throttled};
use crate::blocks::{BlockRefused, Checked, refuse};
use crate::preferences::{check_preferences, preferences_on, store_preferences};
use crate::records::{captured, recall, remember};
use crate::week_saves::check_saved_week;
use crate::{Refusal, ServiceError, ServiceResult, with_db};

pub const IMPORT_STALE: &str = "This preview is out of date. Refresh it before importing.";
pub const TRANSFER_TOO_LARGE: &str = "This account is larger than the 256 KiB transfer limit.";
const MAX_RESTORE_POINTS: i64 = 20;

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

fn invalid() -> ServiceError {
    Refusal::Invalid(INVALID_INPUT.to_string()).into()
}

fn parsed(text: &str) -> ServiceResult<Value> {
    serde_json::from_str(text).map_err(|error| {
        StoreError::Json {
            text: text.to_string(),
            error,
        }
        .into()
    })
}

/// The account as a backup file holds it (before the file's own fields): weeks, homework, preferences,
/// routines and the standing week, as `capture_transfer` gives them.
fn capture_transfer(conn: &Connection, user_id: i64) -> ServiceResult<Value> {
    let mut snapshot = captured(conn, user_id)?;
    let routines = store::routine_list(conn, user_id)?["routines"].take();
    let standing = parsed(&store::standing_rows(conn, user_id)?)?;
    if let Some(fields) = snapshot.as_object_mut() {
        fields.insert("preferences".into(), preferences_on(conn, user_id)?);
        fields.insert("routines".into(), routines);
        fields.insert("standing".into(), standing);
    }
    Ok(snapshot)
}

/// A stored 12-hour clock is left off the preferences answer, but a backup file says it: a file without
/// one reads as an export from before 0.18.5.
fn with_clock(snapshot: &mut Value) {
    if let Some(preferences) = snapshot["preferences"].as_object_mut()
        && !preferences.contains_key("clock_24h")
    {
        preferences.insert("clock_24h".into(), Value::Bool(false));
    }
}

/// The account as a backup file, as `POST /api/account-export` answers `{"password"}`: the password is
/// asked again (and counted as a try), and a file too large to import elsewhere is refused.
pub fn export_account(
    path: &Path,
    asker: Asker<'_>,
    account: &Account,
    given: &Value,
    now: &str,
) -> ServiceResult<Value> {
    let password = match given {
        Value::Object(fields) if fields.len() == 1 => match fields.get("password") {
            Some(Value::String(password)) if (12..=128).contains(&password.chars().count()) => {
                password.clone()
            }
            _ => return Err(invalid()),
        },
        _ => return Err(invalid()),
    };
    throttled(path, asker, &account.username)?;
    let captured = with_db(path, |conn| {
        store::begin(conn)?;
        require_password(conn, account.id, &password)?;
        capture_transfer(conn, account.id)
    })?;
    let mut payload = json!({
        "format": 3,
        "exported_at": now,
        "username": account.username,
    });
    if let (Some(fields), Value::Object(captured)) = (payload.as_object_mut(), captured) {
        fields.extend(captured);
    }
    with_clock(&mut payload);
    let mut snapshot = check_transfer(&payload).map_err(|refused| {
        ServiceError::Broken(format!(
            "the account no longer reads as a backup file: {}",
            refused.0
        ))
    })?;
    with_clock(&mut snapshot);
    if !transfer_fits(&snapshot) {
        return Err(Refusal::TooLarge(TRANSFER_TOO_LARGE.to_string()).into());
    }
    Ok(snapshot)
}

/// `{"snapshot": ...}` read as `TransferPreviewRequest`: the file as read.
fn previewed(given: &Value) -> ServiceResult<Value> {
    match given {
        Value::Object(fields) if fields.len() == 1 => match fields.get("snapshot") {
            Some(snapshot) => check_transfer(snapshot).map_err(|_| invalid()),
            None => Err(invalid()),
        },
        _ => Err(invalid()),
    }
}

/// What importing the file would change, as `POST /api/account-import/preview` answers it, with the token
/// that names the account and the file it compared.
pub fn import_preview(path: &Path, user_id: i64, given: &Value) -> ServiceResult<Value> {
    let incoming = previewed(given)?;
    let current = with_db(path, |conn| capture_transfer(conn, user_id))?;
    Ok(json!({
        "state_token": state_token(&json!({ "current": current, "incoming": incoming })),
        "source_username": incoming["username"],
        "changes": diff_transfer(&current, &incoming),
    }))
}

/// `{"snapshot", "state_token", "operation_id"}` read as `TransferApplyRequest`, written as `model_dump()`.
fn import_request(given: &Value) -> Checked<Value> {
    let fields = object(given, "an import")?;
    only(
        fields,
        &["snapshot", "state_token", "operation_id"],
        "an import",
    )?;
    let snapshot = check_transfer(required(fields, "snapshot")?)?;
    let token = text(required(fields, "state_token")?, "state_token", 1, 128)?;
    let operation_id = text(required(fields, "operation_id")?, "operation_id", 1, 80)?;
    Ok(json!({ "snapshot": snapshot, "state_token": token, "operation_id": operation_id }))
}

/// The account replaced by the file, inside the caller's transaction, as `apply_transfer` does it.
fn apply_transfer(conn: &Connection, user_id: i64, snapshot: &Value) -> ServiceResult<Value> {
    store_preferences(conn, user_id, &snapshot["preferences"])?;
    let empty = Vec::new();
    let routines = snapshot["routines"].as_array().unwrap_or(&empty);
    let rows: Vec<Value> = routines
        .iter()
        .map(|routine| {
            json!({
                "id": routine["id"],
                "name": routine["name"],
                "body": canonical(&routine["blocks"]),
                "revision": routine["revision"],
                "created_at": routine["created_at"],
                "updated_at": routine["updated_at"],
            })
        })
        .collect();
    store::replace_routines(conn, user_id, &Value::Array(rows).to_string())?;
    let standing = match &snapshot["standing"] {
        Value::Null => Value::Array(Vec::new()),
        rows => rows.clone(),
    };
    store::replace_standing(conn, user_id, &standing.to_string())?;
    let field = |item: &Value, name: &str| item[name].as_str().unwrap_or_default().to_string();
    let revision = |item: &Value| item["revision"].as_i64().unwrap_or_default();
    let weeks: Vec<(String, String, i64)> = snapshot["weeks"]
        .as_array()
        .unwrap_or(&empty)
        .iter()
        .map(|week| {
            (
                field(week, "week_start"),
                canonical(&week["blocks"]),
                revision(week),
            )
        })
        .collect();
    let assignments: Vec<(String, String, i64)> = snapshot["assignments"]
        .as_array()
        .unwrap_or(&empty)
        .iter()
        .map(|item| (field(item, "id"), canonical(&item["body"]), revision(item)))
        .collect();
    match store::replace_account(conn, user_id, &weeks, &assignments) {
        Ok(()) => {}
        Err(error @ StoreError::RepeatedBlockId(_)) => {
            return Err(Refusal::Invalid(error.to_string()).into());
        }
        Err(error) => return Err(error.into()),
    }
    if snapshot["standing"].is_null() {
        store::adopt_standing(conn, user_id)?;
    }
    Ok(json!({
        "weeks": weeks.iter().map(|(start, _, revision)| json!({ "week_start": start, "revision": revision }))
            .collect::<Vec<_>>(),
        "assignments": assignments.iter().map(|(id, _, revision)| json!({ "id": id, "revision": revision }))
            .collect::<Vec<_>>(),
        "preferences": snapshot["preferences"],
        "routines": snapshot["routines"],
    }))
}

/// Replaces the account with the file, as `POST /api/account-import` does: only when the account is still
/// as the preview saw it, after a restore point named `token` made at `now`, and once per operation id.
pub fn import_account(
    path: &Path,
    user_id: i64,
    given: &Value,
    token: &str,
    now: &str,
) -> ServiceResult<Value> {
    let request = import_request(given).map_err(|_| invalid())?;
    let digest = store::payload_digest(&request);
    let operation_id = request["operation_id"].as_str().unwrap_or_default();
    let incoming = &request["snapshot"];
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        if let Some(first) = recall(conn, user_id, operation_id, &digest)? {
            return Ok(first);
        }
        let current = capture_transfer(conn, user_id)?;
        if request["state_token"]
            != state_token(&json!({ "current": current, "incoming": incoming })).as_str()
        {
            return Err(Refusal::Conflict(IMPORT_STALE.to_string()).into());
        }
        let recovery = store::create_restore_point(
            conn,
            user_id,
            token,
            &format!("Before import — {now}"),
            now,
            &[],
            MAX_RESTORE_POINTS,
        )?;
        let replaced = apply_transfer(conn, user_id, incoming)?;
        let mut result = json!({ "recovery_id": recovery["id"] });
        if let (Some(fields), Value::Object(replaced)) = (result.as_object_mut(), replaced) {
            fields.extend(replaced);
        }
        remember(conn, user_id, operation_id, &digest, &result)?;
        Ok(result)
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use flexweek_testkit::TestDb;

    /// The store's guard, for a file whose doubled block id got past the file check: the import is refused
    /// in the student's words and the account keeps its week. Moved from
    /// backend/tests/test_week_repeated_block_id.py, which reached it by patching the app's code.
    #[test]
    fn a_file_whose_week_reaches_the_store_with_a_doubled_id_is_refused_in_words_and_changes_nothing()
     {
        let db = TestDb::new("transfer-doubled");
        let user = db.account("alice");
        let school = json!({
            "id": "school", "title": "School", "kind": "locked", "duration_min": 390,
            "days": [0, 1, 2, 3, 4], "start": "08:00", "category": "School",
        });
        with_db(&db.path, |conn| {
            Ok(store::save_week(
                conn,
                user,
                "2026-09-14",
                &json!([school]).to_string(),
                0,
            )?)
        })
        .unwrap();
        let snapshot = json!({
            "weeks": [{ "week_start": "2026-09-14", "blocks": [school, school], "revision": 1 }],
            "assignments": [], "routines": [], "standing": [],
            "preferences": preferences_on_new(&db, user),
        });
        let (refused, rows) = with_db(&db.path, |conn| {
            store::begin_immediate(conn)?;
            let refused = apply_transfer(conn, user, &snapshot);
            let rows: String = conn
                .query_row(
                    "SELECT blocks FROM weeks WHERE user_id = ?1",
                    [user],
                    |row| row.get(0),
                )
                .unwrap();
            Ok((refused, rows))
        })
        .unwrap();
        match refused {
            Err(ServiceError::Refused(Refusal::Invalid(words))) => assert_eq!(
                words,
                r#"Two blocks in this week share the id "school". Each block needs its own id."#
            ),
            other => panic!("not refused in words: {other:?}"),
        }
        assert_eq!(rows, json!([school]).to_string());
    }

    fn preferences_on_new(db: &TestDb, user: i64) -> Value {
        with_db(&db.path, |conn| preferences_on(conn, user)).unwrap()
    }
}
