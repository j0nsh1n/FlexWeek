use std::collections::{BTreeMap, HashSet};

use rusqlite::{Connection, OptionalExtension, params};
use serde_json::{Value, json};

use crate::{Batch, SyncError, SyncResult, account_uuid};

#[derive(Clone, Debug, PartialEq)]
pub struct Record {
    pub entity: String,
    pub key: String,
    pub body: Option<Value>,
    pub hlc: i64,
    pub device_id: String,
    pub seq: i64,
}

impl Record {
    pub fn to_value(&self) -> Value {
        json!({"entity": self.entity, "key": self.key, "body": self.body, "hlc": self.hlc, "device_id": self.device_id, "seq": self.seq})
    }

    pub fn from_value(value: &Value) -> SyncResult<Self> {
        let object = value
            .as_object()
            .ok_or_else(|| SyncError::Invalid("record is not an object".into()))?;
        let string = |key: &str| {
            object
                .get(key)
                .and_then(Value::as_str)
                .map(str::to_string)
                .ok_or_else(|| SyncError::Invalid(format!("missing {key}")))
        };
        let number = |key: &str| {
            object
                .get(key)
                .and_then(Value::as_i64)
                .ok_or_else(|| SyncError::Invalid(format!("missing {key}")))
        };
        Ok(Self {
            entity: string("entity")?,
            key: string("key")?,
            body: object.get("body").filter(|body| !body.is_null()).cloned(),
            hlc: number("hlc")?,
            device_id: string("device_id")?,
            seq: number("seq")?,
        })
    }
}

impl Batch {
    pub fn to_value(&self) -> Value {
        json!({"account_uuid": self.account_uuid, "from_device": self.from_device, "records": self.records.iter().map(Record::to_value).collect::<Vec<_>>(), "next_since": self.next_since, "more": self.more})
    }

    pub fn from_value(value: &Value) -> SyncResult<Self> {
        let object = value
            .as_object()
            .ok_or_else(|| SyncError::Invalid("batch is not an object".into()))?;
        let string = |key: &str| {
            object
                .get(key)
                .and_then(Value::as_str)
                .map(str::to_string)
                .ok_or_else(|| SyncError::Invalid(format!("missing {key}")))
        };
        let records = object
            .get("records")
            .and_then(Value::as_array)
            .ok_or_else(|| SyncError::Invalid("missing records".into()))?
            .iter()
            .map(Record::from_value)
            .collect::<SyncResult<Vec<_>>>()?;
        Ok(Self {
            account_uuid: string("account_uuid")?,
            from_device: string("from_device")?,
            records,
            next_since: object
                .get("next_since")
                .and_then(Value::as_i64)
                .ok_or_else(|| SyncError::Invalid("missing next_since".into()))?,
            more: object
                .get("more")
                .and_then(Value::as_bool)
                .ok_or_else(|| SyncError::Invalid("missing more".into()))?,
        })
    }
}

pub(crate) type Live = BTreeMap<(String, String), Value>;

const PREFS: &[&str] = &[
    "reminders_enabled",
    "reminder_lead_min",
    "reminder_sound",
    "reminder_dnd_override",
    "timer_work_min",
    "timer_break_min",
    "timer_long_break_min",
    "timer_long_break_every",
    "auto_split_pomodoro",
    "alarms_json",
    "availability_json",
];

pub(crate) fn allowed_pref(key: &str) -> bool {
    PREFS.contains(&key)
}

pub(crate) fn live(conn: &Connection, user_id: i64) -> SyncResult<Live> {
    let mut out = Live::new();
    let account: Option<(String, String, String)> = conn.query_row(
        "SELECT a.account_uuid, u.username, u.password_hash FROM sync_account a JOIN users u ON u.id = a.user_id WHERE a.user_id = ?1", [user_id],
        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
    ).optional()?;
    if let Some((uuid, username, password_hash)) = account {
        out.insert(
            ("account".into(), "-".into()),
            json!({"account_uuid": uuid, "username": username, "password_hash": password_hash}),
        );
    }
    let mut stmt = conn.prepare("SELECT id, body FROM assignments WHERE user_id = ?1")?;
    for row in stmt.query_map([user_id], |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
    })? {
        let (id, body) = row?;
        out.insert(("assignment".into(), id), serde_json::from_str(&body)?);
    }
    let mut stmt = conn.prepare("SELECT week_start, blocks FROM weeks WHERE user_id = ?1")?;
    for row in stmt.query_map([user_id], |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
    })? {
        let (week, blocks) = row?;
        let blocks: Value = serde_json::from_str(&blocks)?;
        let array = blocks
            .as_array()
            .ok_or_else(|| SyncError::Invalid("week blocks is not an array".into()))?;
        let mut ids = HashSet::new();
        for block in array {
            let id = block
                .get("id")
                .and_then(Value::as_str)
                .ok_or_else(|| SyncError::Invalid("block has no id".into()))?;
            if !ids.insert(id) {
                return Err(SyncError::Invalid("week repeats block id".into()));
            }
            out.insert(("block".into(), format!("{week}/{id}")), block.clone());
        }
    }
    let mut stmt = conn
        .prepare("SELECT id, from_week, position, body FROM standing_blocks WHERE user_id = ?1")?;
    for row in stmt.query_map([user_id], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, i64>(2)?,
            row.get::<_, Option<String>>(3)?,
        ))
    })? {
        let (id, week, position, body) = row?;
        let body = body
            .map(|text| serde_json::from_str::<Value>(&text))
            .transpose()?;
        out.insert(
            ("standing".into(), format!("{id}/{week}")),
            json!({"position": position, "body": body}),
        );
    }
    let mut stmt = conn.prepare(
        "SELECT id, name, body, created_at, updated_at FROM routines WHERE user_id = ?1",
    )?;
    for row in stmt.query_map([user_id], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, String>(2)?,
            row.get::<_, String>(3)?,
            row.get::<_, String>(4)?,
        ))
    })? {
        let (id, name, body, created_at, updated_at) = row?;
        out.insert(("routine".into(), id), json!({"name": name, "body": serde_json::from_str::<Value>(&body)?, "created_at": created_at, "updated_at": updated_at}));
    }
    let mut stmt = conn.prepare("SELECT reminders_enabled, reminder_lead_min, reminder_sound, reminder_dnd_override, timer_work_min, timer_break_min, timer_long_break_min, timer_long_break_every, auto_split_pomodoro, alarms_json, availability_json FROM preferences WHERE user_id = ?1")?;
    let values: Option<Vec<Value>> = stmt
        .query_row([user_id], |row| {
            (0..PREFS.len())
                .map(|index| {
                    if index < 9 {
                        row.get::<_, i64>(index).map(Value::from)
                    } else {
                        row.get::<_, String>(index).map(Value::from)
                    }
                })
                .collect()
        })
        .optional()?;
    if let Some(values) = values {
        for (&key, value) in PREFS.iter().zip(values) {
            out.insert(("pref".into(), key.into()), value);
        }
    }
    let mut stmt = conn.prepare("SELECT code_hash FROM recovery_codes WHERE user_id = ?1")?;
    for hash in stmt.query_map([user_id], |row| row.get::<_, String>(0))? {
        out.insert(("recovery".into(), hash?), json!({}));
    }
    Ok(out)
}

pub fn export_since(
    conn: &Connection,
    user_id: i64,
    since: i64,
    requester_device: &str,
    limit: usize,
) -> SyncResult<Batch> {
    if limit == 0 || limit > 500 {
        return Err(SyncError::Invalid("batch limit must be 1..=500".into()));
    }
    let device_id: String = conn.query_row(
        "SELECT device_id FROM sync_device WHERE singleton = 1",
        [],
        |row| row.get(0),
    )?;
    let live = live(conn, user_id)?;
    let mut stmt = conn.prepare("SELECT entity, key, hlc, device_id, deleted, seq FROM sync_record WHERE user_id = ?1 AND seq > ?2 ORDER BY seq")?;
    let mut records = Vec::new();
    let mut next_since = since;
    let mut more = false;
    let mut bytes = 0usize;
    for row in stmt.query_map(params![user_id, since], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, i64>(2)?,
            row.get::<_, String>(3)?,
            row.get::<_, i64>(4)?,
            row.get::<_, i64>(5)?,
        ))
    })? {
        let (entity, key, hlc, origin, deleted, seq) = row?;
        if origin == requester_device {
            next_since = seq;
            continue;
        }
        let body = if deleted != 0 {
            None
        } else {
            live.get(&(entity.clone(), key.clone())).cloned()
        };
        if deleted == 0 && body.is_none() {
            return Err(SyncError::Invalid("record changed since last scan".into()));
        }
        let record = Record {
            entity,
            key,
            body,
            hlc,
            device_id: origin,
            seq,
        };
        let size = record.to_value().to_string().len();
        if records.len() >= limit || bytes + size > 256 * 1024 {
            more = true;
            break;
        }
        bytes += size;
        next_since = seq;
        records.push(record);
    }
    Ok(Batch {
        account_uuid: account_uuid(conn, user_id)?,
        from_device: device_id,
        records,
        next_since,
        more,
    })
}
