//! Save, delete and apply routines (`desktop/native/controller.py`'s `save_routine`, `delete_routine`,
//! `apply_routine_rows`, `apply_routine` and the routine list in `_fetch_routines`). The window still
//! draws operation ids, sends the requests and applies what is decided here.

use flexweek_engine::desk::clipboard::{routine_rows, routine_source_blocks, routine_template};
use flexweek_engine::desk::planning::clipboard_fingerprint;
use flexweek_engine::desk::reuse::restore_point_label;
use flexweek_engine::shown::{blocks_by_weekday, routine_on_shown_week};
use flexweek_engine::stored::{self, py_int, py_str, truthy, type_name};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use serde_json::{Map, Value, json};

pub const NAME_A_ROUTINE: &str = "Name the routine and select at least one fixed time.";
pub const CHOOSE_A_WEEKDAY: &str = "Choose at least one weekday to copy.";
pub const NOTHING_TO_ADD: &str = "There's nothing available to add.";
/// What the status line says while the save request is in flight.
pub const SAVING_ROUTINE: &str = "Saving routine\u{2026}";

/// What `save_routine` decides before it asks for an operation id.
#[derive(Debug, Clone, PartialEq)]
pub enum SaveRoutine {
    /// Signed out. The window returns false and says nothing.
    Absent,
    /// Refused. These are the words to say.
    Say(String),
    /// Ready to draw an operation id and build the PUT.
    Ready {
        key: String,
        title: String,
        templates: Vec<Value>,
        /// The body without `id`. The id is `r-` plus the operation id, which does not exist yet.
        body_without_id: Value,
    },
}

impl SaveRoutine {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Ready {
                key,
                title,
                templates,
                body_without_id,
            } => json!({
                "kind": "ready",
                "key": key,
                "title": title,
                "templates": templates,
                "body_without_id": body_without_id,
            }),
        }
    }
}

/// The PUT that stores a routine, once its operation id exists.
#[derive(Debug, Clone, PartialEq)]
pub struct SaveRoutineRequest {
    pub routine_id: String,
    pub method: &'static str,
    pub path: String,
    pub body: Value,
    pub progress: &'static str,
}

impl SaveRoutineRequest {
    pub fn to_json(&self) -> Value {
        json!({
            "routine_id": self.routine_id,
            "method": self.method,
            "path": self.path,
            "body": self.body,
            "progress": self.progress,
        })
    }
}

/// What the save's answer puts in the routine list, and the words that say it landed.
#[derive(Debug, Clone, PartialEq)]
pub struct SavedRoutine {
    pub id: Value,
    pub routine: Value,
    pub say: String,
}

impl SavedRoutine {
    pub fn to_json(&self) -> Value {
        json!({
            "id": self.id,
            "routine": self.routine,
            "say": self.say,
        })
    }
}

/// What `delete_routine` decides before it asks for an operation id.
#[derive(Debug, Clone, PartialEq)]
pub enum DeleteRoutine {
    /// Signed out, or no such routine. The window returns and says nothing.
    Absent,
    Ready {
        key: String,
        revision: Value,
        say: String,
    },
}

impl DeleteRoutine {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Ready { key, revision, say } => json!({
                "kind": "ready",
                "key": key,
                "revision": revision,
                "say": say,
            }),
        }
    }
}

/// What `apply_routine_rows` decides.
#[derive(Debug, Clone, PartialEq)]
pub enum RoutineRows {
    Say(&'static str),
    Rows(Vec<Value>),
}

impl RoutineRows {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Rows(rows) => json!({ "kind": "rows", "rows": rows }),
        }
    }
}

/// What `apply_routine` decides before it confirms the preview.
#[derive(Debug, Clone, PartialEq)]
pub enum ApplyRoutine {
    /// Signed out, or no such routine. The window returns false and says nothing.
    Absent,
    /// Refused. The window says these, in order. A missing weekday selection says the weekday
    /// sentence and then the empty-rows sentence, because applying calls the rows decision first.
    Say(Vec<String>),
    Ready {
        proposals: Vec<Value>,
        key: String,
        label: String,
        snapshot_label: String,
    },
}

impl ApplyRoutine {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({ "kind": "absent" }),
            Self::Say(words) => json!({ "kind": "say", "say": words }),
            Self::Ready {
                proposals,
                key,
                label,
                snapshot_label,
            } => json!({
                "kind": "ready",
                "proposals": proposals,
                "key": key,
                "label": label,
                "snapshot_label": snapshot_label,
            }),
        }
    }
}

/// `urllib.parse.quote(text, safe="")`. UTF-8 bytes outside `A-Za-z0-9_.-~` become uppercase `%XX`.
/// An empty safe set means a slash is encoded, so it cannot end the path segment.
pub fn quote_component(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for byte in text.as_bytes() {
        if is_unreserved(*byte) {
            out.push(*byte as char);
        } else {
            const HEX: &[u8; 16] = b"0123456789ABCDEF";
            out.push('%');
            out.push(HEX[(byte >> 4) as usize] as char);
            out.push(HEX[(byte & 0xf) as usize] as char);
        }
    }
    out
}

fn is_unreserved(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'.' | b'-' | b'~')
}

/// Python's `str.strip` also treats U+001C–U+001F as space. A routine name is stripped before it is
/// judged empty, so a title of only those characters is the same as no title.
fn py_strip(text: &str) -> &str {
    text.trim_matches(|ch: char| {
        ch.is_whitespace() || matches!(ch, '\u{1c}' | '\u{1d}' | '\u{1e}' | '\u{1f}')
    })
}

fn type_error(message: impl Into<String>) -> EngineError {
    EngineError {
        kind: ErrorKind::Type,
        message: message.into(),
    }
}

/// `value[key]` for a string key, with the error Python raises.
fn index<'a>(value: &'a Value, key: &str) -> EngineResult<&'a Value> {
    match value {
        Value::Object(map) => map.get(key).ok_or_else(|| EngineError::key(key)),
        Value::Array(_) => Err(type_error(
            "list indices must be integers or slices, not str",
        )),
        Value::String(_) => Err(type_error("string indices must be integers, not 'str'")),
        other => Err(type_error(format!(
            "'{}' object is not subscriptable",
            type_name(other)
        ))),
    }
}

/// `left + value` when `value` has to be text.
fn concat_text(left: &str, value: &Value) -> EngineResult<String> {
    match value {
        Value::String(text) => Ok(format!("{left}{text}")),
        other => Err(type_error(format!(
            "can only concatenate str (not \"{}\") to str",
            type_name(other)
        ))),
    }
}

fn routine_of<'a>(routines: &'a Value, routine_id: &str) -> EngineResult<Option<&'a Value>> {
    let map = stored::dict(routines)?;
    Ok(match map.get(routine_id) {
        Some(value) if !value.is_null() => Some(value),
        _ => None,
    })
}

/// The fixed times a routine would keep, optionally narrowed to `block_ids` (`None` keeps every one).
fn source_blocks(
    week_start: &str,
    blocks: &[Value],
    block_ids: Option<&[Value]>,
) -> EngineResult<Vec<Value>> {
    let by_weekday = blocks_by_weekday(week_start, blocks)?;
    let mut sources = routine_source_blocks(&Value::Array(by_weekday))?;
    if let Some(allowed) = block_ids {
        let mut kept = Vec::new();
        for block in sources.drain(..) {
            let id = index(&block, "id")?;
            if allowed.iter().any(|item| item == id) {
                kept.push(block);
            }
        }
        sources = kept;
    }
    Ok(sources)
}

/// Whether a routine can be saved, and the key, title and templates when it can.
/// `template_uuids` supplies one id per kept fixed time, in that order. Extras are unused.
pub fn prepare_save_routine(
    account_id: Option<i64>,
    week_start: &str,
    blocks: &[Value],
    name: &str,
    block_ids: Option<&[Value]>,
    template_uuids: &[String],
) -> EngineResult<SaveRoutine> {
    let Some(account_id) = account_id else {
        return Ok(SaveRoutine::Absent);
    };
    let sources = source_blocks(week_start, blocks, block_ids)?;
    let title = py_strip(name);
    if title.is_empty() || sources.is_empty() {
        return Ok(SaveRoutine::Say(NAME_A_ROUTINE.to_string()));
    }
    if template_uuids.len() < sources.len() {
        return Err(EngineError::value(
            "a routine template needs an id for every fixed time",
        ));
    }
    let mut templates = Vec::with_capacity(sources.len());
    for (block, template_id) in sources.iter().zip(template_uuids.iter()) {
        templates.push(routine_template(block, template_id)?);
    }
    let items: Vec<Value> = sources
        .iter()
        .map(|block| json!({ "block": block, "source_day": 0, "scope": "block" }))
        .collect();
    let fingerprint = clipboard_fingerprint(&Value::Array(items))?;
    let key = format!("create-routine|{account_id}|{title}|{fingerprint}");
    let body_without_id = json!({
        "name": title,
        "blocks": templates.clone(),
        "revision": 0,
    });
    Ok(SaveRoutine::Ready {
        key,
        title: title.to_string(),
        templates,
        body_without_id,
    })
}

/// The routine id, path and PUT body. `operation_id` is the attempt id; the routine id is `r-` plus it.
pub fn save_routine_request(
    operation_id: &str,
    title: &str,
    templates: &[Value],
) -> SaveRoutineRequest {
    let routine_id = format!("r-{operation_id}");
    let path = format!("/api/routines/{}", quote_component(&routine_id));
    let body = json!({
        "id": routine_id,
        "name": title,
        "blocks": templates,
        "revision": 0,
    });
    SaveRoutineRequest {
        routine_id,
        method: "PUT",
        path,
        body,
        progress: SAVING_ROUTINE,
    }
}

/// `data.get("routine") or data`, the id it is stored under, and "Saved <name>."
pub fn save_routine_reply(data: &Value) -> EngineResult<SavedRoutine> {
    let fields = stored::dict(data)?;
    let saved = match fields.get("routine") {
        Some(routine) if truthy(Some(routine)) => routine,
        _ => data,
    };
    let id = index(saved, "id")?.clone();
    let name = index(saved, "name")?;
    let say = format!("{}.", concat_text("Saved ", name)?);
    Ok(SavedRoutine {
        id,
        routine: saved.clone(),
        say,
    })
}

/// The delete key, the revision the path will send, and "Deleted <name>." A missing routine says nothing.
pub fn prepare_delete_routine(
    account_id: Option<i64>,
    routines: &Value,
    routine_id: &str,
) -> EngineResult<DeleteRoutine> {
    let Some(account_id) = account_id else {
        return Ok(DeleteRoutine::Absent);
    };
    let Some(routine) = routine_of(routines, routine_id)? else {
        return Ok(DeleteRoutine::Absent);
    };
    let revision = index(routine, "revision")?.clone();
    let name = index(routine, "name")?;
    let say = format!("{}.", concat_text("Deleted ", name)?);
    let key = format!(
        "delete-routine|{account_id}|{routine_id}|{}",
        py_str(&revision)
    );
    Ok(DeleteRoutine::Ready { key, revision, say })
}

/// The DELETE path. `revision` is read with `int`, then written in decimal. Both ids are quoted.
pub fn delete_routine_path(
    routine_id: &str,
    revision: &Value,
    operation_id: &str,
) -> EngineResult<String> {
    let revision = py_int(revision)?;
    Ok(format!(
        "/api/routines/{}?revision={revision}&operation_id={}",
        quote_component(routine_id),
        quote_component(operation_id),
    ))
}

/// The rows a routine would add, or the weekday sentence when the routine is missing or no day is ticked.
pub fn apply_routine_rows_decision(
    routines: &Value,
    routine_id: &str,
    week_start: &str,
    days: &[Value],
) -> EngineResult<RoutineRows> {
    let Some(routine) = routine_of(routines, routine_id)? else {
        return Ok(RoutineRows::Say(CHOOSE_A_WEEKDAY));
    };
    if days.is_empty() {
        return Ok(RoutineRows::Say(CHOOSE_A_WEEKDAY));
    }
    let turned = routine_on_shown_week(week_start, routine)?;
    let rows = routine_rows(&turned, week_start, &Value::Array(days.to_vec()))?;
    Ok(RoutineRows::Rows(rows))
}

/// Whether applying can go ahead. `rows` is `None` when the caller did not pass any, so the rows
/// decision runs first, as `apply_routine` does.
pub fn prepare_apply_routine(
    account_id: Option<i64>,
    routines: &Value,
    routine_id: &str,
    week_start: &str,
    days: &[Value],
    rows: Option<&[Value]>,
) -> EngineResult<ApplyRoutine> {
    let Some(account_id) = account_id else {
        return Ok(ApplyRoutine::Absent);
    };
    let Some(routine) = routine_of(routines, routine_id)? else {
        return Ok(ApplyRoutine::Absent);
    };
    let proposals = match rows {
        Some(given) => given.to_vec(),
        None => match apply_routine_rows_decision(routines, routine_id, week_start, days)? {
            RoutineRows::Say(words) => {
                return Ok(ApplyRoutine::Say(vec![
                    words.to_string(),
                    NOTHING_TO_ADD.to_string(),
                ]));
            }
            RoutineRows::Rows(found) => found,
        },
    };
    if proposals.is_empty() {
        return Ok(ApplyRoutine::Say(vec![NOTHING_TO_ADD.to_string()]));
    }
    let revision = index(routine, "revision")?;
    let name = index(routine, "name")?;
    let day_text = days.iter().map(py_str).collect::<Vec<_>>().join(",");
    let key = format!(
        "routine|{account_id}|{routine_id}|{}|{week_start}|{day_text}",
        py_str(revision)
    );
    let label = format!("{} routine", concat_text("the ", name)?);
    let before = format!("{} to {week_start}", concat_text("Before applying ", name)?);
    Ok(ApplyRoutine::Ready {
        proposals,
        key,
        label,
        snapshot_label: restore_point_label(&before),
    })
}

/// The server's routine list as `{id: routine}`. A missing or empty list is an empty map. Two rows
/// with one id keep the later row.
pub fn routines_from_reply(data: &Value) -> EngineResult<Map<String, Value>> {
    let fields = stored::dict(data)?;
    let list = match fields.get("routines") {
        Some(value) if truthy(Some(value)) => value,
        _ => return Ok(Map::new()),
    };
    let items = match list {
        Value::Array(items) => items.clone(),
        Value::String(text) => text.chars().map(|ch| Value::from(ch.to_string())).collect(),
        Value::Object(map) => map.keys().map(|key| Value::from(key.as_str())).collect(),
        other => {
            return Err(type_error(format!(
                "'{}' object is not iterable",
                type_name(other)
            )));
        }
    };
    let mut routines = Map::new();
    for item in items {
        let id = py_str(index(&item, "id")?);
        routines.insert(id, item);
    }
    Ok(routines)
}
