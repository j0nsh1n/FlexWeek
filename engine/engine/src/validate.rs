//! `backend/models.py` `TimeBlock`, `WeekRequest`, `AssignmentContent` and `Routine`.
//! Refusal words are the pydantic 2.13 field sentences and the `ValueError` text in that file.

use serde_json::{Map, Value};

use crate::error::EngineResult;
use crate::model;
use crate::time::span_fits_day;

const JS_INT_MAX: i64 = (1_i64 << 53) - 1;
const DAY_NAMES: [&str; 7] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
];

#[derive(Clone, Debug, PartialEq)]
pub struct TimeBlock {
    pub id: String,
    pub title: String,
    pub kind: String,
    pub duration_min: i64,
    pub days: Vec<i64>,
    pub priority: i64,
    pub energy: String,
    pub earliest: Option<String>,
    pub latest: Option<String>,
    pub start: Option<String>,
    pub course: Option<String>,
    pub category: Option<String>,
    pub completed: bool,
    pub completed_day: Option<i64>,
    pub missed_days: Vec<i64>,
    pub spotify_url: Option<String>,
    pub focus_sessions: i64,
    pub focus_minutes: i64,
    pub pomodoro_parent_id: Option<String>,
    pub pomodoro_role: Option<String>,
    pub pomodoro_index: Option<i64>,
    pub pinned: bool,
    pub prefer_earliest: bool,
    pub assignment_id: Option<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct WeekRequest {
    pub blocks: Vec<TimeBlock>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct AssignmentLink {
    pub label: String,
    pub url: String,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ChecklistItem {
    pub id: String,
    pub text: String,
    pub done: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub struct AssignmentContent {
    pub id: String,
    pub title: String,
    pub course: Option<String>,
    pub category: Option<String>,
    pub priority: i64,
    pub energy: String,
    pub spotify_url: Option<String>,
    pub due: String,
    pub estimate_min: i64,
    pub spread: String,
    pub focus_minutes: i64,
    pub focus_sessions: i64,
    pub completed: bool,
    pub completed_at: Option<String>,
    pub notes: String,
    pub links: Vec<AssignmentLink>,
    pub checklist: Vec<ChecklistItem>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct RoutineBlock {
    pub template_id: String,
    pub title: String,
    pub days: Vec<i64>,
    pub start: String,
    pub duration_min: i64,
    pub category: Option<String>,
    pub course: Option<String>,
    pub priority: i64,
    pub energy: String,
    pub spotify_url: Option<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Routine {
    pub id: String,
    pub name: String,
    pub blocks: Vec<RoutineBlock>,
    pub revision: i64,
}

pub fn time_block(value: &Value) -> Result<TimeBlock, String> {
    let map = object(value, "TimeBlock")?;
    let block = TimeBlock {
        id: req_str(map, "id", 1, 80)?,
        title: req_str(map, "title", 1, 80)?,
        kind: req_literal(map, "kind", &["locked", "flexible"])?,
        duration_min: req_bounded_int(map, "duration_min", Some(0), None, Some(7140))?,
        days: days_of(map, "days", false)?,
        priority: literal_default(map, "priority", 3, &[1, 2, 3, 4])?,
        energy: literal_str_default(map, "energy", "medium", &["high", "medium", "low"])?,
        earliest: opt_str(map, "earliest", 40)?,
        latest: opt_str(map, "latest", 40)?,
        start: opt_str(map, "start", 5)?,
        course: opt_str(map, "course", 40)?,
        category: opt_str(map, "category", 32)?,
        completed: bool_default(map, "completed", false)?,
        completed_day: opt_int(map, "completed_day", Some(0), Some(6))?,
        missed_days: missed_days_of(map)?,
        spotify_url: spotify_of(map)?,
        focus_sessions: int_default(map, "focus_sessions", 0, None, Some(0), Some(9999))?,
        focus_minutes: int_default(map, "focus_minutes", 0, None, Some(0), Some(71400))?,
        pomodoro_parent_id: opt_str_bounds(map, "pomodoro_parent_id", 1, 80)?,
        pomodoro_role: opt_literal(map, "pomodoro_role", &["work", "break"])?,
        pomodoro_index: opt_int(map, "pomodoro_index", Some(1), Some(999))?,
        pinned: bool_default(map, "pinned", false)?,
        prefer_earliest: bool_default(map, "prefer_earliest", false)?,
        assignment_id: opt_str_bounds(map, "assignment_id", 1, 80)?,
    };
    block_state(&block)?;
    Ok(block)
}

pub fn week_request(value: &Value) -> Result<WeekRequest, String> {
    let map = object(value, "WeekRequest")?;
    let blocks = match map.get("blocks") {
        None => return Err("Field required".into()),
        Some(value) => block_list(value)?,
    };
    week_rules(&blocks)?;
    Ok(WeekRequest { blocks })
}

pub fn assignment_content(value: &Value) -> Result<AssignmentContent, String> {
    let map = object(value, "AssignmentContent")?;
    let title = req_str(map, "title", 1, 80)?;
    if title.trim().is_empty() {
        return Err("title required".into());
    }
    let item = AssignmentContent {
        id: req_str(map, "id", 1, 80)?,
        title,
        course: opt_str(map, "course", 40)?,
        category: opt_str(map, "category", 32)?,
        priority: literal_default(map, "priority", 3, &[1, 2, 3, 4])?,
        energy: literal_str_default(map, "energy", "medium", &["high", "medium", "low"])?,
        spotify_url: spotify_of(map)?,
        due: required_due(map)?,
        estimate_min: estimate_of(map)?,
        spread: literal_str_default(map, "spread", "one", &["one", "spread"])?,
        focus_minutes: int_default(map, "focus_minutes", 0, None, Some(0), Some(71400))?,
        focus_sessions: int_default(map, "focus_sessions", 0, None, Some(0), Some(9999))?,
        completed: bool_default(map, "completed", false)?,
        completed_at: completed_at_of(map)?,
        notes: notes_of(map)?,
        links: links_of(map)?,
        checklist: checklist_of(map)?,
    };
    forbid_extra(
        map,
        &[
            "id",
            "title",
            "course",
            "category",
            "priority",
            "energy",
            "spotify_url",
            "due",
            "estimate_min",
            "spread",
            "focus_minutes",
            "focus_sessions",
            "completed",
            "completed_at",
            "notes",
            "links",
            "checklist",
        ],
    )?;
    if item.completed && item.completed_at.is_none() {
        return Err("completed_at is required when completed".into());
    }
    if !item.completed && item.completed_at.is_some() {
        return Err("completed_at must be null when not completed".into());
    }
    if has_dup_str(
        &item
            .checklist
            .iter()
            .map(|item| item.id.as_str())
            .collect::<Vec<_>>(),
    ) {
        return Err("checklist ids must be unique".into());
    }
    Ok(item)
}

pub fn routine(value: &Value) -> Result<Routine, String> {
    let map = object(value, "Routine")?;
    let name = req_str(map, "name", 1, 80)?;
    if name.trim().is_empty() {
        return Err("name required".into());
    }
    let blocks = routine_blocks(map)?;
    let routine = Routine {
        id: req_str(map, "id", 1, 80)?,
        name,
        blocks,
        revision: req_bounded_int(map, "revision", None, Some(0), Some(JS_INT_MAX))?,
    };
    forbid_extra(map, &["id", "name", "blocks", "revision"])?;
    routine_overlap(&routine.blocks)?;
    Ok(routine)
}

pub fn encode_json(value: &Value) -> String {
    serde_json::to_string(&sorted(value)).unwrap_or_default()
}

impl TimeBlock {
    pub fn to_value(&self) -> Value {
        let mut map = Map::new();
        put_str(&mut map, "id", &self.id);
        put_str(&mut map, "title", &self.title);
        put_str(&mut map, "kind", &self.kind);
        put_i64(&mut map, "duration_min", self.duration_min);
        put_ints(&mut map, "days", &self.days);
        put_i64(&mut map, "priority", self.priority);
        put_str(&mut map, "energy", &self.energy);
        put_null_str(&mut map, "earliest", &self.earliest);
        put_null_str(&mut map, "latest", &self.latest);
        put_null_str(&mut map, "start", &self.start);
        put_null_str(&mut map, "course", &self.course);
        put_some_str(&mut map, "category", &self.category);
        if self.completed {
            put_bool(&mut map, "completed", true);
        }
        if let Some(day) = self.completed_day {
            put_i64(&mut map, "completed_day", day);
        }
        if !self.missed_days.is_empty() {
            put_ints(&mut map, "missed_days", &self.missed_days);
        }
        put_some_str(&mut map, "spotify_url", &self.spotify_url);
        if self.focus_sessions != 0 {
            put_i64(&mut map, "focus_sessions", self.focus_sessions);
        }
        if self.focus_minutes != 0 {
            put_i64(&mut map, "focus_minutes", self.focus_minutes);
        }
        put_some_str(&mut map, "pomodoro_parent_id", &self.pomodoro_parent_id);
        put_some_str(&mut map, "pomodoro_role", &self.pomodoro_role);
        if let Some(index) = self.pomodoro_index {
            put_i64(&mut map, "pomodoro_index", index);
        }
        if self.pinned {
            put_bool(&mut map, "pinned", true);
        }
        if self.prefer_earliest {
            put_bool(&mut map, "prefer_earliest", true);
        }
        put_some_str(&mut map, "assignment_id", &self.assignment_id);
        Value::Object(map)
    }
}

impl AssignmentContent {
    pub fn to_value(&self) -> Value {
        let mut map = Map::new();
        put_str(&mut map, "id", &self.id);
        put_str(&mut map, "title", &self.title);
        put_null_str(&mut map, "course", &self.course);
        put_null_str(&mut map, "category", &self.category);
        put_i64(&mut map, "priority", self.priority);
        put_str(&mut map, "energy", &self.energy);
        put_null_str(&mut map, "spotify_url", &self.spotify_url);
        put_str(&mut map, "due", &self.due);
        put_i64(&mut map, "estimate_min", self.estimate_min);
        if self.spread != "one" {
            put_str(&mut map, "spread", &self.spread);
        }
        put_i64(&mut map, "focus_minutes", self.focus_minutes);
        put_i64(&mut map, "focus_sessions", self.focus_sessions);
        put_bool(&mut map, "completed", self.completed);
        put_null_str(&mut map, "completed_at", &self.completed_at);
        if !self.notes.is_empty() {
            put_str(&mut map, "notes", &self.notes);
        }
        if !self.links.is_empty() {
            let links = self
                .links
                .iter()
                .map(|link| {
                    let mut item = Map::new();
                    put_str(&mut item, "label", &link.label);
                    put_str(&mut item, "url", &link.url);
                    Value::Object(item)
                })
                .collect();
            map.insert("links".into(), Value::Array(links));
        }
        if !self.checklist.is_empty() {
            let items = self
                .checklist
                .iter()
                .map(|item| {
                    let mut row = Map::new();
                    put_str(&mut row, "id", &item.id);
                    put_str(&mut row, "text", &item.text);
                    put_bool(&mut row, "done", item.done);
                    Value::Object(row)
                })
                .collect();
            map.insert("checklist".into(), Value::Array(items));
        }
        Value::Object(map)
    }
}

fn block_state(block: &TimeBlock) -> Result<(), String> {
    if block.pinned && (block.kind != "flexible" || block.start.is_none() || block.days.len() != 1)
    {
        return Err("pinned requires a flexible block with a start on one day".into());
    }
    if !block.missed_days.is_empty() && block.kind != "locked" {
        return Err("only locked blocks can have missed days".into());
    }
    if block
        .missed_days
        .iter()
        .any(|day| !block.days.contains(day))
    {
        return Err("missed days must be occurrences of the block".into());
    }
    if let Some(day) = block.completed_day
        && (block.kind != "flexible"
            || !block.completed
            || block.start.is_none()
            || !block.days.contains(&day))
    {
        return Err(
            "completed_day requires a completed flexible block with a start on a candidate day"
                .into(),
        );
    }
    if block.assignment_id.is_some() {
        if block.latest.is_some() {
            return Err("a session cannot carry latest".into());
        }
        if block.focus_minutes != 0 || block.focus_sessions != 0 {
            return Err("session focus must be 0".into());
        }
        if block.kind == "flexible" {
            return Ok(());
        }
        if block.kind == "locked" && block.pomodoro_role.as_deref() == Some("work") {
            return Ok(());
        }
        return Err(
            "assignment_id is only valid on a work session or a pomodoro work chunk".into(),
        );
    }
    Ok(())
}

fn block_list(value: &Value) -> Result<Vec<TimeBlock>, String> {
    let items = value
        .as_array()
        .ok_or_else(|| "Input should be a valid list".to_string())?;
    let mut blocks = Vec::with_capacity(items.len());
    for item in items {
        blocks.push(time_block(item)?);
    }
    list_bounds(blocks.len(), None, Some(100))?;
    Ok(blocks)
}

fn week_rules(blocks: &[TimeBlock]) -> Result<(), String> {
    let mut ids = Vec::new();
    for block in blocks {
        if ids.contains(&block.id.as_str()) {
            return Err("block ids must be unique".into());
        }
        ids.push(block.id.as_str());
    }
    for block in blocks {
        if block.title.trim().is_empty() || has_dup(&block.days) {
            return Err("title and unique days required".into());
        }
        if block.kind == "locked" && block.start.as_deref().unwrap_or("").is_empty() {
            return Err("locked blocks need a start".into());
        }
        if let Some(start) = &block.start {
            let Some(minutes) = hhmm_minutes(start) else {
                return Err("invalid start time".into());
            };
            if !span_fits_day(minutes, block.duration_min) {
                return Err("block must fit between 00:00 and 24:00".into());
            }
        }
        for bound in [&block.earliest, &block.latest].into_iter().flatten() {
            if !is_deadline(bound) {
                return Err("invalid deadline or earliest time".into());
            }
        }
    }
    if blocks.iter().any(|block| {
        block
            .pomodoro_parent_id
            .as_deref()
            .is_some_and(|parent| ids.contains(&parent))
    }) {
        return Err("a pomodoro parent cannot be stored with the chunks split from it".into());
    }
    Ok(())
}

fn days_of(map: &Map<String, Value>, key: &str, unique: bool) -> Result<Vec<i64>, String> {
    let days = match map.get(key) {
        None => return Err("Field required".into()),
        Some(value) => int_list(value, Some(1), Some(7))?,
    };
    let bad_range = days.iter().any(|day| !(0..=6).contains(day));
    if unique {
        if bad_range || has_dup(&days) {
            return Err("days must be unique values in 0..6".into());
        }
    } else if bad_range {
        return Err("days must be in 0..6 (Mon..Sun)".into());
    }
    Ok(days)
}

fn missed_days_of(map: &Map<String, Value>) -> Result<Vec<i64>, String> {
    let days = match map.get("missed_days") {
        None => return Ok(Vec::new()),
        Some(value) => int_list(value, None, Some(7))?,
    };
    if days.iter().any(|day| !(0..=6).contains(day)) || has_dup(&days) {
        return Err("missed_days must be unique values in 0..6".into());
    }
    Ok(days)
}

fn spotify_of(map: &Map<String, Value>) -> Result<Option<String>, String> {
    let Some(text) = opt_str(map, "spotify_url", 500)? else {
        return Ok(None);
    };
    engine(model::valid_spotify_url(Some(&text)))
}

fn required_due(map: &Map<String, Value>) -> Result<String, String> {
    match map.get("due") {
        None => Err("Field required".into()),
        Some(Value::String(text)) => engine(model::valid_due(text)),
        Some(_) => Err("Input should be a valid string".into()),
    }
}

fn estimate_of(map: &Map<String, Value>) -> Result<i64, String> {
    let estimate = match map.get("estimate_min") {
        None => return Err("Field required".into()),
        Some(value) => as_i64(value)?,
    };
    int_bounds(estimate, None, None, Some(model::ESTIMATE_MAX_MIN))?;
    if estimate <= 0 || estimate % 15 != 0 {
        return Err("estimate_min must be a positive multiple of 15".into());
    }
    Ok(estimate)
}

fn completed_at_of(map: &Map<String, Value>) -> Result<Option<String>, String> {
    match map.get("completed_at") {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) => engine(model::valid_naive_stamp(text)).map(Some),
        Some(_) => Err("Input should be a valid string".into()),
    }
}

fn notes_of(map: &Map<String, Value>) -> Result<String, String> {
    match map.get("notes") {
        None | Some(Value::Null) => Ok(String::new()),
        Some(Value::String(text)) => {
            string_bounds(text, 0, 4000)?;
            Ok(text.clone())
        }
        Some(_) => Err("Input should be a valid string".into()),
    }
}

fn links_of(map: &Map<String, Value>) -> Result<Vec<AssignmentLink>, String> {
    let Some(value) = map.get("links") else {
        return Ok(Vec::new());
    };
    let items = value
        .as_array()
        .ok_or_else(|| "Input should be a valid list".to_string())?;
    let mut links = Vec::with_capacity(items.len());
    for item in items {
        links.push(link_of(item)?);
    }
    list_bounds(links.len(), None, Some(20))?;
    Ok(links)
}

fn link_of(value: &Value) -> Result<AssignmentLink, String> {
    let map = object(value, "AssignmentLink")?;
    let label = req_str(map, "label", 1, 80)?;
    if label.trim().is_empty() {
        return Err("link label required".into());
    }
    let url = req_str(map, "url", 1, 500)?;
    engine(model::valid_http_url(&url))?;
    forbid_extra(map, &["label", "url"])?;
    Ok(AssignmentLink { label, url })
}

fn checklist_of(map: &Map<String, Value>) -> Result<Vec<ChecklistItem>, String> {
    let Some(value) = map.get("checklist") else {
        return Ok(Vec::new());
    };
    let items = value
        .as_array()
        .ok_or_else(|| "Input should be a valid list".to_string())?;
    let mut rows = Vec::with_capacity(items.len());
    for item in items {
        rows.push(check_item(item)?);
    }
    list_bounds(rows.len(), None, Some(40))?;
    Ok(rows)
}

fn check_item(value: &Value) -> Result<ChecklistItem, String> {
    let map = object(value, "ChecklistItem")?;
    let text = req_str(map, "text", 1, 80)?;
    if text.trim().is_empty() {
        return Err("checklist text required".into());
    }
    let item = ChecklistItem {
        id: req_str(map, "id", 1, 80)?,
        text,
        done: bool_default(map, "done", false)?,
    };
    forbid_extra(map, &["id", "text", "done"])?;
    Ok(item)
}

fn routine_blocks(map: &Map<String, Value>) -> Result<Vec<RoutineBlock>, String> {
    let Some(value) = map.get("blocks") else {
        return Err("Field required".into());
    };
    let items = value
        .as_array()
        .ok_or_else(|| "Input should be a valid list".to_string())?;
    let mut blocks = Vec::with_capacity(items.len());
    for item in items {
        blocks.push(routine_block(item)?);
    }
    list_bounds(blocks.len(), None, Some(100))?;
    let ids: Vec<&str> = blocks
        .iter()
        .map(|block| block.template_id.as_str())
        .collect();
    if has_dup_str(&ids) {
        return Err("template ids must be unique".into());
    }
    Ok(blocks)
}

fn routine_block(value: &Value) -> Result<RoutineBlock, String> {
    let map = object(value, "RoutineBlock")?;
    let title = req_str(map, "title", 1, 80)?;
    if title.trim().is_empty() {
        return Err("title required".into());
    }
    let start = req_str(map, "start", 1, 80)?;
    if hhmm_minutes(&start).is_none() {
        return Err("invalid start time".into());
    }
    let block = RoutineBlock {
        template_id: req_str(map, "template_id", 1, 80)?,
        title,
        days: days_of(map, "days", true)?,
        start,
        duration_min: req_bounded_int(map, "duration_min", Some(0), None, Some(7140))?,
        category: opt_str(map, "category", 32)?,
        course: opt_str(map, "course", 40)?,
        priority: literal_default(map, "priority", 3, &[1, 2, 3, 4])?,
        energy: literal_str_default(map, "energy", "medium", &["high", "medium", "low"])?,
        spotify_url: spotify_of(map)?,
    };
    forbid_extra(
        map,
        &[
            "template_id",
            "title",
            "days",
            "start",
            "duration_min",
            "category",
            "course",
            "priority",
            "energy",
            "spotify_url",
        ],
    )?;
    let Some(minutes) = hhmm_minutes(&block.start) else {
        return Err("invalid start time".into());
    };
    if !span_fits_day(minutes, block.duration_min) {
        return Err("block must fit between 00:00 and 24:00".into());
    }
    Ok(block)
}

fn routine_overlap(blocks: &[RoutineBlock]) -> Result<(), String> {
    for day in 0..7 {
        let mut intervals = Vec::new();
        for block in blocks {
            if !block.days.contains(&day) {
                continue;
            }
            let Some(start) = hhmm_minutes(&block.start) else {
                continue;
            };
            let end = start + block.duration_min;
            if intervals
                .iter()
                .any(|(other_start, other_end)| start < *other_end && *other_start < end)
            {
                return Err("routine blocks overlap".into());
            }
            intervals.push((start, end));
        }
    }
    Ok(())
}

fn object<'a>(value: &'a Value, class_name: &str) -> Result<&'a Map<String, Value>, String> {
    value
        .as_object()
        .ok_or_else(|| format!("Input should be a valid dictionary or instance of {class_name}"))
}

fn req_str(map: &Map<String, Value>, key: &str, min: usize, max: usize) -> Result<String, String> {
    match map.get(key) {
        None => Err("Field required".into()),
        Some(Value::String(text)) => {
            string_bounds(text, min, max)?;
            Ok(text.clone())
        }
        Some(_) => Err("Input should be a valid string".into()),
    }
}

fn opt_str(map: &Map<String, Value>, key: &str, max: usize) -> Result<Option<String>, String> {
    opt_str_bounds(map, key, 0, max)
}

fn opt_str_bounds(
    map: &Map<String, Value>,
    key: &str,
    min: usize,
    max: usize,
) -> Result<Option<String>, String> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) => {
            string_bounds(text, min, max)?;
            Ok(Some(text.clone()))
        }
        Some(_) => Err("Input should be a valid string".into()),
    }
}

fn string_bounds(text: &str, min: usize, max: usize) -> Result<(), String> {
    let count = text.chars().count();
    if count < min {
        return Err(format!(
            "String should have at least {min} character{}",
            plural(min)
        ));
    }
    if count > max {
        return Err(format!(
            "String should have at most {max} character{}",
            plural(max)
        ));
    }
    Ok(())
}

fn plural(count: usize) -> &'static str {
    if count == 1 { "" } else { "s" }
}

fn list_bounds(len: usize, min: Option<usize>, max: Option<usize>) -> Result<(), String> {
    if let Some(min) = min
        && len < min
    {
        return Err(format!(
            "List should have at least {min} item{} after validation, not {len}",
            plural(min)
        ));
    }
    if let Some(max) = max
        && len > max
    {
        return Err(format!(
            "List should have at most {max} item{} after validation, not {len}",
            plural(max)
        ));
    }
    Ok(())
}

fn as_i64(value: &Value) -> Result<i64, String> {
    let Some(number) = value.as_number() else {
        return Err("Input should be a valid integer".into());
    };
    if let Some(int) = number.as_i64() {
        return Ok(int);
    }
    if number.as_u64().is_some() {
        return Err(format!(
            "Input should be less than or equal to {JS_INT_MAX}"
        ));
    }
    Err("Input should be a valid integer, got a number with a fractional part".into())
}

fn int_bounds(value: i64, gt: Option<i64>, ge: Option<i64>, le: Option<i64>) -> Result<(), String> {
    if let Some(gt) = gt
        && value <= gt
    {
        return Err(format!("Input should be greater than {gt}"));
    }
    if let Some(ge) = ge
        && value < ge
    {
        return Err(format!("Input should be greater than or equal to {ge}"));
    }
    if let Some(le) = le
        && value > le
    {
        return Err(format!("Input should be less than or equal to {le}"));
    }
    Ok(())
}

fn req_bounded_int(
    map: &Map<String, Value>,
    key: &str,
    gt: Option<i64>,
    ge: Option<i64>,
    le: Option<i64>,
) -> Result<i64, String> {
    match map.get(key) {
        None => Err("Field required".into()),
        Some(value) => {
            let int = as_i64(value)?;
            int_bounds(int, gt, ge, le)?;
            Ok(int)
        }
    }
}

fn int_default(
    map: &Map<String, Value>,
    key: &str,
    default: i64,
    gt: Option<i64>,
    ge: Option<i64>,
    le: Option<i64>,
) -> Result<i64, String> {
    match map.get(key) {
        None => Ok(default),
        Some(value) => {
            let int = as_i64(value)?;
            int_bounds(int, gt, ge, le)?;
            Ok(int)
        }
    }
}

fn opt_int(
    map: &Map<String, Value>,
    key: &str,
    ge: Option<i64>,
    le: Option<i64>,
) -> Result<Option<i64>, String> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => {
            let int = as_i64(value)?;
            int_bounds(int, None, ge, le)?;
            Ok(Some(int))
        }
    }
}

fn int_list(value: &Value, min: Option<usize>, max: Option<usize>) -> Result<Vec<i64>, String> {
    let Some(items) = value.as_array() else {
        return Err("Input should be a valid list".into());
    };
    let mut numbers = Vec::with_capacity(items.len());
    for item in items {
        numbers.push(as_i64(item)?);
    }
    list_bounds(numbers.len(), min, max)?;
    Ok(numbers)
}

fn bool_default(map: &Map<String, Value>, key: &str, default: bool) -> Result<bool, String> {
    match map.get(key) {
        None => Ok(default),
        Some(Value::Bool(value)) => Ok(*value),
        Some(_) => Err("Input should be a valid boolean".into()),
    }
}

fn literal_default(
    map: &Map<String, Value>,
    key: &str,
    default: i64,
    options: &[i64],
) -> Result<i64, String> {
    match map.get(key) {
        None => Ok(default),
        Some(value) => literal_i64(value, options),
    }
}

fn literal_i64(value: &Value, options: &[i64]) -> Result<i64, String> {
    let expected = join_or(
        &options
            .iter()
            .map(|number| number.to_string())
            .collect::<Vec<_>>(),
    );
    let Ok(int) = value
        .as_i64()
        .ok_or_else(|| format!("Input should be {expected}"))
    else {
        return Err(format!("Input should be {expected}"));
    };
    if options.contains(&int) {
        Ok(int)
    } else {
        Err(format!("Input should be {expected}"))
    }
}

fn literal_str_default(
    map: &Map<String, Value>,
    key: &str,
    default: &str,
    options: &[&str],
) -> Result<String, String> {
    match map.get(key) {
        None => Ok(default.to_string()),
        Some(value) => literal_str(value, options),
    }
}

fn req_literal(map: &Map<String, Value>, key: &str, options: &[&str]) -> Result<String, String> {
    match map.get(key) {
        None => Err("Field required".into()),
        Some(value) => literal_str(value, options),
    }
}

fn opt_literal(
    map: &Map<String, Value>,
    key: &str,
    options: &[&str],
) -> Result<Option<String>, String> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => literal_str(value, options).map(Some),
    }
}

fn literal_str(value: &Value, options: &[&str]) -> Result<String, String> {
    let expected = join_or(
        &options
            .iter()
            .map(|text| format!("'{text}'"))
            .collect::<Vec<_>>(),
    );
    let Some(text) = value.as_str() else {
        return Err(format!("Input should be {expected}"));
    };
    if options.contains(&text) {
        Ok(text.to_string())
    } else {
        Err(format!("Input should be {expected}"))
    }
}

fn join_or(parts: &[String]) -> String {
    let Some((last, head)) = parts.split_last() else {
        return String::new();
    };
    if head.is_empty() {
        return last.clone();
    }
    if head.len() == 1 {
        return format!("{} or {last}", head[0]);
    }
    format!("{} or {last}", head.join(", "))
}

fn forbid_extra(map: &Map<String, Value>, allowed: &[&str]) -> Result<(), String> {
    if map.keys().any(|key| !allowed.contains(&key.as_str())) {
        return Err("Extra inputs are not permitted".into());
    }
    Ok(())
}

fn has_dup(days: &[i64]) -> bool {
    days.iter()
        .enumerate()
        .any(|(index, day)| days[..index].contains(day))
}

fn has_dup_str(ids: &[&str]) -> bool {
    ids.iter()
        .enumerate()
        .any(|(index, id)| ids[..index].contains(id))
}

fn hhmm_minutes(value: &str) -> Option<i64> {
    let bytes = value.as_bytes();
    if bytes.len() != 5 || bytes[2] != b':' {
        return None;
    }
    if !bytes
        .iter()
        .enumerate()
        .all(|(index, byte)| index == 2 || byte.is_ascii_digit())
    {
        return None;
    }
    let hour: i64 = value[0..2].parse().ok()?;
    let minute: i64 = value[3..5].parse().ok()?;
    if hour > 23 || minute > 59 {
        return None;
    }
    Some(hour * 60 + minute)
}

fn is_deadline(value: &str) -> bool {
    let clock = match value.split_once(' ') {
        Some((day, rest)) => {
            if !DAY_NAMES.contains(&day) {
                return false;
            }
            rest
        }
        None => value,
    };
    hhmm_minutes(clock).is_some()
}

fn engine<T>(result: EngineResult<T>) -> Result<T, String> {
    result.map_err(|error| error.message)
}

fn put_str(map: &mut Map<String, Value>, key: &str, value: &str) {
    map.insert(key.to_string(), Value::String(value.to_string()));
}

fn put_some_str(map: &mut Map<String, Value>, key: &str, value: &Option<String>) {
    if let Some(text) = value {
        put_str(map, key, text);
    }
}

fn put_null_str(map: &mut Map<String, Value>, key: &str, value: &Option<String>) {
    match value {
        Some(text) => put_str(map, key, text),
        None => {
            map.insert(key.to_string(), Value::Null);
        }
    }
}

fn put_i64(map: &mut Map<String, Value>, key: &str, value: i64) {
    map.insert(key.to_string(), Value::from(value));
}

fn put_bool(map: &mut Map<String, Value>, key: &str, value: bool) {
    map.insert(key.to_string(), Value::Bool(value));
}

fn put_ints(map: &mut Map<String, Value>, key: &str, values: &[i64]) {
    map.insert(
        key.to_string(),
        Value::Array(values.iter().copied().map(Value::from).collect()),
    );
}

fn sorted(value: &Value) -> Value {
    match value {
        Value::Array(items) => Value::Array(items.iter().map(sorted).collect()),
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            let mut ordered = Map::new();
            for key in keys {
                ordered.insert(key.clone(), sorted(&map[key]));
            }
            Value::Object(ordered)
        }
        other => other.clone(),
    }
}
