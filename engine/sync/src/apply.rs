use std::collections::HashSet;

use rusqlite::{Connection, OptionalExtension, Transaction, params};
use serde_json::Value;

use flexweek_engine::time;

use crate::{
    ApplyReport, Batch, Record, SyncError, SyncResult, canonical, clock, digest,
    records::allowed_pref,
};

fn bad(record: &Record) -> Option<&'static str> {
    if record.entity.is_empty()
        || record.key.is_empty()
        || record.key.len() > 180
        || record.device_id.is_empty()
        || record.hlc < 0
        || record.seq < 0
    {
        return Some("invalid record header");
    }
    let Some(body) = &record.body else {
        return if record.entity == "account" || record.entity == "pref" {
            Some("account and preferences cannot be deleted")
        } else {
            None
        };
    };
    if canonical(body).len() > 256 * 1024 {
        return Some("record is too large");
    }
    match record.entity.as_str() {
        "account"
            if record.key == "-"
                && only_keys(body, &["account_uuid", "username", "password_hash"])
                && body.get("account_uuid").and_then(Value::as_str).is_some()
                && body
                    .get("username")
                    .and_then(Value::as_str)
                    .is_some_and(|s| !s.is_empty() && within(s, 80))
                && body.get("password_hash").and_then(Value::as_str).is_some() =>
        {
            None
        }
        "assignment"
            if body.as_object().is_some()
                && body.get("id").and_then(Value::as_str) == Some(record.key.as_str())
                && body
                    .get("title")
                    .and_then(Value::as_str)
                    .is_some_and(|s| !s.is_empty() && within(s, 80))
                && body
                    .get("due")
                    .and_then(Value::as_str)
                    .is_some_and(time::is_calendar_date)
                && body
                    .get("estimate_min")
                    .and_then(Value::as_i64)
                    .is_some_and(|n| (15..=1440).contains(&n) && n % 15 == 0)
                && optional_text(body, "course", 40)
                && optional_text(body, "category", 32)
                && optional_text(body, "spotify_url", 500)
                && optional_text(body, "notes", 4000)
                && optional_array(body, "links", 20)
                && optional_array(body, "checklist", 40) =>
        {
            None
        }
        "block"
            if record.key.split_once('/').is_some_and(|(week, id)| {
                time::is_week_start(week)
                    && !id.is_empty()
                    && within(id, 80)
                    && body.get("id").and_then(Value::as_str) == Some(id)
            }) && body.as_object().is_some()
                && body
                    .get("title")
                    .and_then(Value::as_str)
                    .is_some_and(|s| !s.is_empty() && within(s, 80))
                && body
                    .get("kind")
                    .and_then(Value::as_str)
                    .is_some_and(|s| s == "locked" || s == "flexible")
                && body
                    .get("duration_min")
                    .and_then(Value::as_i64)
                    .is_some_and(|n| (1..=7140).contains(&n))
                && body
                    .get("days")
                    .and_then(Value::as_array)
                    .is_some_and(|days| {
                        !days.is_empty()
                            && days.len() <= 7
                            && days
                                .iter()
                                .all(|day| day.as_i64().is_some_and(|n| (0..=6).contains(&n)))
                    })
                && optional_text(body, "course", 40)
                && optional_text(body, "category", 32)
                && optional_text(body, "spotify_url", 500) =>
        {
            None
        }
        "standing"
            if record
                .key
                .rsplit_once('/')
                .is_some_and(|(id, week)| !id.is_empty() && time::is_week_start(week))
                && only_keys(body, &["position", "body"])
                && body.get("position").and_then(Value::as_i64).is_some()
                && body
                    .get("body")
                    .is_some_and(|value| value.is_null() || value.as_object().is_some()) =>
        {
            None
        }
        "routine"
            if only_keys(body, &["name", "body", "created_at", "updated_at"])
                && body
                    .get("name")
                    .and_then(Value::as_str)
                    .is_some_and(|s| !s.is_empty() && within(s, 80))
                && body.get("body").is_some_and(Value::is_object)
                && body.get("created_at").and_then(Value::as_str).is_some()
                && body.get("updated_at").and_then(Value::as_str).is_some() =>
        {
            None
        }
        "pref" if allowed_pref(&record.key) && valid_pref(&record.key, body) => None,
        "recovery" if body.as_object().is_some_and(|obj| obj.is_empty()) => None,
        _ => Some("malformed or unknown record"),
    }
}

fn within(text: &str, max: usize) -> bool {
    text.chars().count() <= max
}

fn only_keys(body: &Value, keys: &[&str]) -> bool {
    body.as_object().is_some_and(|object| {
        object.len() == keys.len() && keys.iter().all(|k| object.contains_key(*k))
    })
}

fn optional_text(body: &Value, key: &str, max: usize) -> bool {
    body.get(key)
        .is_none_or(|value| value.is_null() || value.as_str().is_some_and(|text| within(text, max)))
}

fn optional_array(body: &Value, key: &str, max: usize) -> bool {
    body.get(key)
        .is_none_or(|value| value.as_array().is_some_and(|array| array.len() <= max))
}

fn valid_pref(key: &str, body: &Value) -> bool {
    match key {
        "alarms_json" => body.as_str().is_some_and(|text| {
            serde_json::from_str::<Value>(text).is_ok_and(|value| value.is_array())
        }),
        "availability_json" => body.as_str().is_some_and(|text| {
            serde_json::from_str::<Value>(text).is_ok_and(|value| value.is_object())
        }),
        "reminder_lead_min" => body.as_i64().is_some_and(|n| (0..=120).contains(&n)),
        "reminders_enabled"
        | "reminder_sound"
        | "reminder_dnd_override"
        | "auto_split_pomodoro" => body.as_i64().is_some_and(|n| n == 0 || n == 1),
        _ => body.as_i64().is_some_and(|n| n > 0 && n <= 1_440),
    }
}

fn write_real(tx: &Connection, user_id: i64, record: &Record) -> SyncResult<()> {
    let body = record.body.as_ref();
    match record.entity.as_str() {
        "account" => {
            let Some(body) = body else {
                return Ok(());
            };
            let username = body["username"].as_str().unwrap();
            let password_hash = body["password_hash"].as_str().unwrap();
            tx.execute(
                "UPDATE users SET username=?1, password_hash=?2 WHERE id=?3",
                params![username, password_hash, user_id],
            )?;
        }
        "assignment" => {
            if let Some(body) = body {
                tx.execute("INSERT INTO assignments(user_id, id, body, revision) VALUES (?1, ?2, ?3, 1) ON CONFLICT(user_id, id) DO UPDATE SET body=excluded.body, revision=revision+1", params![user_id, record.key, canonical(body)])?;
            } else {
                tx.execute(
                    "DELETE FROM assignments WHERE user_id=?1 AND id=?2",
                    params![user_id, record.key],
                )?;
            }
        }
        "block" => {
            let (week, id) = record
                .key
                .split_once('/')
                .ok_or_else(|| SyncError::Invalid("bad block key".into()))?;
            let previous: Option<String> = tx
                .query_row(
                    "SELECT blocks FROM weeks WHERE user_id=?1 AND week_start=?2",
                    params![user_id, week],
                    |row| row.get(0),
                )
                .optional()?;
            let previous_missing = previous.is_none();
            let mut blocks: Vec<Value> = previous
                .map(|text| serde_json::from_str(&text))
                .transpose()?
                .unwrap_or_default();
            if previous_missing && body.is_none() {
                return Ok(());
            }
            let mut ids = HashSet::new();
            if !blocks.iter().all(|block| {
                block
                    .get("id")
                    .and_then(Value::as_str)
                    .is_some_and(|id| ids.insert(id.to_string()))
            }) {
                return Err(SyncError::Invalid("week repeats block id".into()));
            }
            let index = blocks
                .iter()
                .position(|block| block.get("id").and_then(Value::as_str) == Some(id));
            match (index, body) {
                (Some(index), Some(body)) => blocks[index] = body.clone(),
                (Some(index), None) => {
                    blocks.remove(index);
                }
                (None, Some(body)) => blocks.push(body.clone()),
                (None, None) => {}
            }
            tx.execute("INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 1) ON CONFLICT(user_id, week_start) DO UPDATE SET blocks=excluded.blocks, revision=revision+1", params![user_id, week, canonical(&Value::Array(blocks))])?;
        }
        "standing" => {
            let (id, week) = record
                .key
                .rsplit_once('/')
                .ok_or_else(|| SyncError::Invalid("bad standing key".into()))?;
            if let Some(body) = body {
                let standing = body
                    .get("body")
                    .filter(|value| !value.is_null())
                    .map(canonical);
                tx.execute("INSERT INTO standing_blocks(user_id, id, from_week, position, body) VALUES (?1, ?2, ?3, ?4, ?5) ON CONFLICT(user_id, id, from_week) DO UPDATE SET position=excluded.position, body=excluded.body", params![user_id, id, week, body["position"].as_i64().unwrap(), standing])?;
            } else {
                tx.execute(
                    "DELETE FROM standing_blocks WHERE user_id=?1 AND id=?2 AND from_week=?3",
                    params![user_id, id, week],
                )?;
            }
        }
        "routine" => {
            if let Some(body) = body {
                tx.execute("INSERT INTO routines(user_id, id, name, body, revision, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, 1, ?5, ?6) ON CONFLICT(user_id, id) DO UPDATE SET name=excluded.name, body=excluded.body, revision=revision+1, created_at=excluded.created_at, updated_at=excluded.updated_at", params![user_id, record.key, body["name"].as_str().unwrap(), canonical(&body["body"]), body["created_at"].as_str().unwrap(), body["updated_at"].as_str().unwrap()])?;
            } else {
                tx.execute(
                    "DELETE FROM routines WHERE user_id=?1 AND id=?2",
                    params![user_id, record.key],
                )?;
            }
        }
        "pref" => {
            if let Some(body) = body {
                tx.execute(
                    "INSERT INTO preferences(user_id) VALUES (?1) ON CONFLICT(user_id) DO NOTHING",
                    [user_id],
                )?;
                let sql = format!("UPDATE preferences SET {}=?1 WHERE user_id=?2", record.key);
                if let Some(number) = body.as_i64() {
                    tx.execute(&sql, params![number, user_id])?;
                } else if let Some(text) = body.as_str() {
                    tx.execute(&sql, params![text, user_id])?;
                }
            }
        }
        "recovery" => {
            if body.is_some() {
                tx.execute(
                    "INSERT OR IGNORE INTO recovery_codes(user_id, code_hash) VALUES (?1, ?2)",
                    params![user_id, record.key],
                )?;
            } else {
                tx.execute(
                    "DELETE FROM recovery_codes WHERE user_id=?1 AND code_hash=?2",
                    params![user_id, record.key],
                )?;
            }
        }
        _ => return Err(SyncError::Invalid("unknown record".into())),
    }
    Ok(())
}

fn quarantine(
    tx: &Transaction<'_>,
    user_id: i64,
    record: &Record,
    reason: &str,
    now_ms: i64,
) -> SyncResult<()> {
    tx.execute("INSERT INTO sync_quarantine(user_id, entity, key, reason, body, at) VALUES (?1, ?2, ?3, ?4, ?5, ?6)", params![user_id, record.entity, record.key, reason, record.to_value().to_string(), now_ms.to_string()])?;
    Ok(())
}

pub fn apply_batch(conn: &mut Connection, batch: &Batch, now_ms: i64) -> SyncResult<ApplyReport> {
    let mut tx = conn.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
    let mut report = ApplyReport::default();
    let mut user_id: Option<i64> = tx
        .query_row(
            "SELECT user_id FROM sync_account WHERE account_uuid=?1",
            [&batch.account_uuid],
            |row| row.get(0),
        )
        .optional()?;
    if let Some(id) = user_id {
        crate::scan::scan_in(&tx, id, now_ms)?;
    }
    if user_id.is_none() {
        let account = batch
            .records
            .iter()
            .find(|record| {
                record.entity == "account"
                    && record.key == "-"
                    && record
                        .body
                        .as_ref()
                        .is_some_and(|body| body["account_uuid"] == batch.account_uuid)
                    && record.hlc >> 16 <= now_ms.saturating_add(clock::MAX_FUTURE_MS)
                    && bad(record).is_none()
            })
            .ok_or_else(|| SyncError::Invalid("first batch has no valid account".into()))?;
        let body = account.body.as_ref().unwrap();
        tx.execute(
            "INSERT INTO users(username, password_hash) VALUES (?1, ?2)",
            params![
                body["username"].as_str().unwrap(),
                body["password_hash"].as_str().unwrap()
            ],
        )?;
        let id = tx.last_insert_rowid();
        tx.execute(
            "INSERT INTO sync_account(user_id, account_uuid) VALUES (?1, ?2)",
            params![id, batch.account_uuid],
        )?;
        user_id = Some(id);
    }
    let local_device: (String, i64, i64) = tx.query_row(
        "SELECT device_id, hlc_last, seq_last FROM sync_device WHERE singleton=1",
        [],
        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
    )?;
    let (device_id, mut hlc_last, mut seq_last) = local_device;
    let id = user_id.unwrap();
    for record in &batch.records {
        let future = record.hlc >> 16 > now_ms.saturating_add(clock::MAX_FUTURE_MS);
        let reason = if future {
            Some("clock is more than 24 hours ahead")
        } else {
            bad(record)
        };
        if let Some(reason) = reason {
            quarantine(&tx, id, record, reason, now_ms)?;
            report.quarantined += 1;
            continue;
        }
        if record.entity == "account"
            && record
                .body
                .as_ref()
                .is_some_and(|body| body["account_uuid"] != batch.account_uuid)
        {
            quarantine(&tx, id, record, "account identity differs", now_ms)?;
            report.quarantined += 1;
            continue;
        }
        let local: Option<(i64, String, bool)> = tx.query_row("SELECT hlc, device_id, deleted FROM sync_record WHERE user_id=?1 AND entity=?2 AND key=?3", params![id, record.entity, record.key], |row| Ok((row.get(0)?, row.get(1)?, row.get::<_, i64>(2)? != 0))).optional()?;
        let remote_deleted = record.body.is_none();
        let wins = local.as_ref().is_none_or(|(stamp, origin, deleted)| {
            (record.entity == "recovery" && remote_deleted && !deleted)
                || ((record.entity != "recovery" || !deleted || remote_deleted)
                    && (record.hlc, record.device_id.as_str()) > (*stamp, origin.as_str()))
        });
        if !wins || record.device_id == device_id {
            report.skipped += 1;
            continue;
        }
        let mut savepoint = tx.savepoint()?;
        match write_real(&savepoint, id, record) {
            Ok(()) => {
                savepoint.commit()?;
            }
            Err(error) => {
                savepoint.rollback()?;
                drop(savepoint);
                quarantine(&tx, id, record, &error.to_string(), now_ms)?;
                report.quarantined += 1;
                continue;
            }
        }
        hlc_last = clock::observe(hlc_last, record.hlc, now_ms)?;
        seq_last += 1;
        let hash = record.body.as_ref().map(digest).unwrap_or_default();
        tx.execute("INSERT INTO sync_record(user_id, entity, key, hlc, device_id, deleted, hash, seq) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8) ON CONFLICT(user_id, entity, key) DO UPDATE SET hlc=excluded.hlc, device_id=excluded.device_id, deleted=excluded.deleted, hash=excluded.hash, seq=excluded.seq", params![id, record.entity, record.key, record.hlc, record.device_id, i64::from(remote_deleted), hash, seq_last])?;
        report.applied += 1;
    }
    tx.execute(
        "UPDATE sync_device SET hlc_last=?1, seq_last=?2 WHERE singleton=1",
        params![hlc_last, seq_last],
    )?;
    report.user_id = Some(id);
    tx.commit()?;
    Ok(report)
}
