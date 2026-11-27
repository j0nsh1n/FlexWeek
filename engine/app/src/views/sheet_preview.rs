//! Paste and duplicate preview: which rows are ticked, and the words beside a fixed time.
//!
//! The clock and the save callable stay in Python. This holds the copied rows and the rules.

use flexweek_engine::desk::calendar::DAYS;
use flexweek_engine::desk::clipboard::{preview_conflict_message, row_conflict};
use flexweek_engine::desk::weekmodel::hhmm_text;
use flexweek_engine::stored::{py_int, py_str, truthy, type_name};
use flexweek_engine::time::{
    DAY_END_MIN, DAY_START_MIN, SLOT_MIN, hhmm_to_minutes, minutes_to_hhmm,
};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use serde_json::{Map, Value, json};

pub const NONE_CHOSEN: &str = "Select at least one item before saving.";

/// What a time says when another block is already there: it is allowed, and both are drawn.
pub fn beside_words(clash: &str) -> String {
    format!("{clash} is at that time too. Both will stay visible and overlap slightly.")
}

#[derive(Clone, Debug, PartialEq)]
pub struct PreviewDraft {
    title: String,
    summary: String,
    confirm: String,
    rows: Vec<Value>,
}

impl PreviewDraft {
    pub fn open(input: &Value) -> EngineResult<Self> {
        let map = object(input)?;
        let mut draft = Self {
            title: text_field(map, "title")?,
            summary: text_field(map, "summary")?,
            confirm: text_field(map, "confirm")?,
            rows: iterate(req(map, "rows")?)?,
        };
        draft.settle();
        Ok(draft)
    }

    /// Untick rows the preview already knows it cannot save. Only the first settle does this.
    fn settle(&mut self) {
        for row in &mut self.rows {
            if get(row, "invalid").ok().is_some_and(|value| truthy(value)) {
                let _ = set_field(row, "checked", Value::Bool(false));
            }
        }
    }

    pub fn rows(&self) -> &[Value] {
        &self.rows
    }

    pub fn can_save(&self) -> bool {
        self.rows
            .iter()
            .any(|row| get(row, "checked").ok().is_some_and(|value| truthy(value)))
    }

    pub fn check(&mut self, index: i64, checked: bool) -> EngineResult<()> {
        let Some(row) = row_mut(&mut self.rows, index) else {
            return Ok(());
        };
        if !truthy(get(row, "invalid")?) {
            set_field(row, "checked", Value::Bool(checked))?;
        }
        Ok(())
    }

    pub fn set_day(&mut self, index: i64, day: i64, existing: &Value) -> EngineResult<()> {
        if day < 0 || day >= i64::try_from(DAYS.len()).unwrap_or(0) {
            return Ok(());
        }
        if row_mut(&mut self.rows, index).is_none() {
            return Ok(());
        }
        {
            let row = &mut self.rows[index as usize];
            set_field(row, "day", Value::from(day))?;
            let block = block_mut(row)?;
            set_field(block, "days", json!([day]))?;
        }
        self.touch(index, existing)
    }

    pub fn set_start(&mut self, index: i64, start: &str, existing: &Value) -> EngineResult<()> {
        if row_mut(&mut self.rows, index).is_none() {
            return Ok(());
        }
        {
            let row = &mut self.rows[index as usize];
            let block = block_mut(row)?;
            set_field(block, "start", Value::String(start.to_string()))?;
            set_field(row, "invalid", Value::String(String::new()))?;
        }
        self.touch(index, existing)
    }

    pub fn set_duration(
        &mut self,
        index: i64,
        minutes: &Value,
        existing: &Value,
    ) -> EngineResult<()> {
        let minutes = py_int(minutes)?;
        if row_mut(&mut self.rows, index).is_none() {
            return Ok(());
        }
        {
            let row = &mut self.rows[index as usize];
            let block = block_mut(row)?;
            set_field(block, "duration_min", Value::from(minutes))?;
        }
        self.touch(index, existing)
    }

    fn touch(&mut self, index: i64, existing: &Value) -> EngineResult<()> {
        let rows = Value::Array(self.rows.clone());
        let row = &self.rows[index as usize];
        let conflict = row_conflict(row, &rows, existing, Some(index as usize))?;
        if !conflict.as_ref().is_some_and(|title| truthy(Some(title))) {
            set_field(&mut self.rows[index as usize], "checked", Value::Bool(true))?;
        }
        Ok(())
    }

    pub fn form(&mut self, existing: &Value) -> EngineResult<Value> {
        let mut rows = Vec::with_capacity(self.rows.len());
        for index in 0..self.rows.len() {
            rows.push(self.row_form(index, existing)?);
        }
        let can_save = self.can_save();
        Ok(json!({
            "kind": "preview",
            "heading": self.title,
            "intro": self.summary,
            "confirm": self.confirm,
            "rows": rows,
            "canSave": can_save,
            "whyOff": if can_save { "" } else { NONE_CHOSEN },
        }))
    }

    fn row_form(&mut self, index: usize, existing: &Value) -> EngineResult<Value> {
        let rows = Value::Array(self.rows.clone());
        let row = &self.rows[index];
        let skip = Some(index);
        let conflict = row_conflict(row, &rows, existing, skip)?;
        let invalid = truthy(get(row, "invalid")?);
        let beside = conflict.as_ref().is_some_and(|title| truthy(Some(title))) && !invalid;
        let detail = if let Some(title) = conflict.as_ref().filter(|_| beside) {
            Value::String(beside_words(&py_str(title)))
        } else {
            preview_conflict_message(row, &rows, existing, skip)?
        };
        let block = get(row, "block")?.ok_or_else(|| EngineError::key("block"))?;
        let mut form = Map::new();
        form.insert("index".into(), Value::from(index));
        form.insert(
            "title".into(),
            get(block, "title")?
                .ok_or_else(|| EngineError::key("title"))?
                .clone(),
        );
        form.insert("checked".into(), Value::Bool(truthy(get(row, "checked")?)));
        form.insert("invalid".into(), Value::Bool(invalid));
        form.insert("detail".into(), detail);
        form.insert("fixed".into(), Value::Bool(truthy(get(row, "fixed")?)));
        if truthy(get(row, "fixed")?) {
            self.fixed_fields(index, &mut form)?;
        }
        Ok(Value::Object(form))
    }

    fn fixed_fields(&mut self, index: usize, form: &mut Map<String, Value>) -> EngineResult<()> {
        let duration = {
            let block = block_of(&self.rows[index])?;
            py_int(req(block, "duration_min")?)?
        };
        let current = self.current_start(index)?;
        let last = DAY_END_MIN - duration;
        let mut starts = std::collections::BTreeSet::from([current.clone()]);
        let mut minute = DAY_START_MIN;
        while minute <= last {
            starts.insert(minutes_to_hhmm(minute));
            minute += SLOT_MIN;
        }
        let room = DAY_END_MIN - hhmm_to_minutes(&current)?;
        let maximum = {
            let row = &self.rows[index];
            let offered = match get(row, "original_duration")? {
                Some(value) if truthy(Some(value)) => py_int(value)?,
                _ => duration,
            };
            room.min(offered)
        };
        let mut lengths = std::collections::BTreeSet::new();
        let mut slot = SLOT_MIN;
        while slot <= maximum {
            lengths.insert(slot);
            slot += SLOT_MIN;
        }
        if duration <= maximum {
            lengths.insert(duration);
        }
        let day = req(object(&self.rows[index])?, "day")?.clone();
        let day_options: Vec<Value> = DAYS
            .iter()
            .enumerate()
            .map(|(number, name)| json!({"value": number, "label": name}))
            .collect();
        let start_options: Vec<Value> = starts
            .iter()
            .map(|value| hhmm_text(value).map(|label| json!({"value": value, "label": label})))
            .collect::<EngineResult<_>>()?;
        let duration_options: Vec<Value> = lengths
            .iter()
            .map(|minutes| json!({"value": minutes, "label": minutes.to_string()}))
            .collect();
        form.insert("day".into(), day);
        form.insert("dayOptions".into(), Value::Array(day_options));
        form.insert("start".into(), Value::String(current));
        form.insert("startOptions".into(), Value::Array(start_options));
        form.insert("duration".into(), Value::from(duration.min(maximum)));
        form.insert("durationOptions".into(), Value::Array(duration_options));
        Ok(())
    }

    /// A missing start is written back, as the sheet did when it read the row to draw the field.
    fn current_start(&mut self, index: usize) -> EngineResult<String> {
        let block = block_mut(&mut self.rows[index])?;
        let current = match get(block, "start")? {
            Some(value) if truthy(Some(value)) => py_str(value),
            _ => minutes_to_hhmm(DAY_START_MIN),
        };
        set_field(block, "start", Value::String(current.clone()))?;
        Ok(current)
    }

    pub fn to_value(&self) -> Value {
        json!({
            "title": self.title,
            "summary": self.summary,
            "confirm": self.confirm,
            "rows": self.rows,
        })
    }

    pub fn from_value(value: &Value) -> EngineResult<Self> {
        let map = object(value)?;
        Ok(Self {
            title: text_field(map, "title")?,
            summary: text_field(map, "summary")?,
            confirm: text_field(map, "confirm")?,
            rows: iterate(req(map, "rows")?)?,
        })
    }
}

fn row_mut(rows: &mut [Value], index: i64) -> Option<&mut Value> {
    let index = usize::try_from(index).ok()?;
    rows.get_mut(index)
}

fn object(value: &Value) -> EngineResult<&Map<String, Value>> {
    value.as_object().ok_or_else(|| EngineError {
        kind: flexweek_engine::ErrorKind::Attribute,
        message: format!("'{}' object has no attribute 'get'", kind_name(value)),
    })
}

fn object_mut(value: &mut Value) -> EngineResult<&mut Map<String, Value>> {
    if !value.is_object() {
        return Err(EngineError {
            kind: flexweek_engine::ErrorKind::Attribute,
            message: format!("'{}' object has no attribute 'get'", kind_name(value)),
        });
    }
    Ok(value.as_object_mut().expect("object"))
}

fn req<'a>(map: &'a Map<String, Value>, key: &str) -> EngineResult<&'a Value> {
    map.get(key).ok_or_else(|| EngineError::key(key))
}

fn text_field(map: &Map<String, Value>, key: &str) -> EngineResult<String> {
    match req(map, key)? {
        Value::String(text) => Ok(text.clone()),
        other => Err(EngineError {
            kind: flexweek_engine::ErrorKind::Type,
            message: format!("{} must be text, not '{}'", key, kind_name(other)),
        }),
    }
}

fn block_of(row: &Value) -> EngineResult<&Map<String, Value>> {
    object(req(object(row)?, "block")?)
}

fn block_mut(row: &mut Value) -> EngineResult<&mut Value> {
    let map = object_mut(row)?;
    if !map.contains_key("block") {
        return Err(EngineError::key("block"));
    }
    Ok(map.get_mut("block").expect("block"))
}

/// `value.get(key)`. Only a dict has `get`.
fn get<'a>(value: &'a Value, key: &str) -> EngineResult<Option<&'a Value>> {
    match value {
        Value::Object(map) => Ok(map.get(key)),
        other => Err(EngineError {
            kind: ErrorKind::Attribute,
            message: format!("'{}' object has no attribute 'get'", type_name(other)),
        }),
    }
}

/// `for item in value`.
fn iterate(value: &Value) -> EngineResult<Vec<Value>> {
    match value {
        Value::Array(items) => Ok(items.clone()),
        Value::String(text) => Ok(text.chars().map(|ch| Value::from(ch.to_string())).collect()),
        Value::Object(map) => Ok(map.keys().cloned().map(Value::String).collect()),
        other => Err(EngineError {
            kind: ErrorKind::Type,
            message: format!("'{}' object is not iterable", type_name(other)),
        }),
    }
}

fn set_field(value: &mut Value, key: &str, field: Value) -> EngineResult<()> {
    object_mut(value)?.insert(key.to_string(), field);
    Ok(())
}

fn kind_name(value: &Value) -> &'static str {
    match value {
        Value::Null => "NoneType",
        Value::Bool(_) => "bool",
        Value::Number(number) if number.to_string().contains(['.', 'e', 'E']) => "float",
        Value::Number(_) => "int",
        Value::String(_) => "str",
        Value::Array(_) => "list",
        Value::Object(_) => "dict",
    }
}
