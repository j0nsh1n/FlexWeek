//! `--upgrade-check`: what this program finds of a 1.x install, so the upgrade test can compare it with
//! what it seeded there (2.0.0 plan, upgrade.md sections 4 to 6). It only reads: the database is opened
//! read-only, so checking renews no session and changes no revision.

use std::path::Path;

use flexweek_platform::folders::{WEEK_STARTS, default_session_file, kept_week_start};
use rusqlite::{Connection, OpenFlags, OptionalExtension, params};
use serde_json::{Map, Value, json};

fn read_json(path: &Path) -> Option<Value> {
    serde_json::from_str(&std::fs::read_to_string(path).ok()?).ok()
}

/// The kept session's token, read as the desktop reads it (`desktop/native/kept.py`).
fn kept_token(file: &Path) -> Option<String> {
    let token = read_json(file)?.get("token")?.as_str()?.to_string();
    let fits = (20..=128).contains(&token.len())
        && token
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'-');
    fits.then_some(token)
}

fn count(conn: &Connection, table: &str, user_id: i64) -> rusqlite::Result<Option<i64>> {
    let exists: bool = conn.query_row(
        "SELECT count(*) > 0 FROM sqlite_master WHERE type = 'table' AND name = ?1",
        params![table],
        |row| row.get(0),
    )?;
    if !exists {
        return Ok(None);
    }
    let live = if table == "sync_peer" {
        " AND revoked = 0"
    } else {
        ""
    };
    conn.query_row(
        &format!("SELECT count(*) FROM {table} WHERE user_id = ?1{live}"),
        params![user_id],
        |row| row.get(0),
    )
    .map(Some)
}

/// The account the kept session opens at `now` (unix seconds), and what it holds.
fn account(database: &Path, token: Option<&str>, now: i64) -> rusqlite::Result<Value> {
    let conn = Connection::open_with_flags(database, OpenFlags::SQLITE_OPEN_READ_ONLY)?;
    let Some(token) = token else {
        return Ok(Value::Null);
    };
    let found: Option<(i64, String)> = conn
        .query_row(
            "SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE token_hash = ?1 AND expires > ?2",
            params![flexweek_store::digest(token), now],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .optional()?;
    let Some((user_id, username)) = found else {
        return Ok(Value::Null);
    };
    let mut held = Map::new();
    held.insert("username".into(), json!(username));
    for (name, table) in [
        ("weeks", "weeks"),
        ("homework", "assignments"),
        ("routines", "routines"),
        ("restore_points", "restore_points"),
        ("standing_blocks", "standing_blocks"),
        ("phones", "sync_peer"),
    ] {
        held.insert(name.into(), json!(count(&conn, table, user_id)?));
    }
    let alarms: Option<String> = conn
        .query_row(
            "SELECT alarms_json FROM preferences WHERE user_id = ?1",
            params![user_id],
            |row| row.get(0),
        )
        .optional()?;
    let alarms = alarms
        .and_then(|text| serde_json::from_str::<Value>(&text).ok())
        .and_then(|list| list.as_array().map(Vec::len));
    held.insert("alarms".into(), json!(alarms));
    Ok(Value::Object(held))
}

/// The `Exec=` command of the login entry in `config_dir/autostart`, if there is one.
fn login_command(config_dir: &Path) -> Option<String> {
    let entry = std::fs::read_to_string(config_dir.join("autostart/flexweek.desktop")).ok()?;
    entry
        .lines()
        .find_map(|line| line.strip_prefix("Exec="))
        .map(str::to_string)
}

/// What a 1.x install left in `data_dir` (and the login entry under `config_dir`), as a JSON report.
/// `now` is unix seconds, for whether the kept session is still open.
pub fn report(data_dir: &Path, config_dir: &Path, now: i64) -> Value {
    let database = data_dir.join("flexweek.db");
    let session_file = default_session_file(data_dir, &database, false);
    let token = kept_token(&session_file);
    let account = if database.exists() {
        account(&database, token.as_deref(), now)
            .unwrap_or_else(|error| json!({ "error": error.to_string() }))
    } else {
        Value::Null
    };
    let look = read_json(&data_dir.join("flexweek-look.json"));
    let look_keys: Option<Vec<String>> = look
        .as_ref()
        .and_then(Value::as_object)
        .map(|fields| fields.keys().cloned().collect());
    let preset = look
        .as_ref()
        .and_then(|look| look.pointer("/material/preset"))
        .cloned();
    json!({
        "data_dir": data_dir.to_string_lossy(),
        "database": database.exists(),
        "kept_session_file": session_file.to_string_lossy(),
        "kept_session": token.is_some(),
        "account": account,
        "look_preset": preset,
        "look_keys": look_keys,
        "week_starts_on": WEEK_STARTS[kept_week_start(data_dir) as usize],
        "device_key": data_dir.join("sync/device.key").is_file(),
        "login_command": login_command(config_dir),
    })
}
