//! View-model and screen state for Month cells and the Material Month bridge (`hours/month_cells.py`
//! and `material/bridge_month.py`, P5-M1).
//!
//! Pure over values passed in by the caller: nothing here reads a clock, draws an id, or touches
//! the operating system.

use std::collections::HashMap;

use flexweek_engine::desk::datetext::{day_long, day_of};
use flexweek_engine::desk::grid::month_for_view;
use flexweek_engine::desk::weekmodel::{clock_label, hhmm_text, length_label, set_clock_24h};
use flexweek_engine::model::due_is_timed;
use flexweek_engine::stored::{add_days, truthy};
use flexweek_engine::time::{month_grid_from, weekday_order};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use serde_json::{Map, Value, json};

use crate::views::theme::event_category;

pub const LOAD_CAP: i64 = 180;
pub const LOAD_WORDS: &str = "Show study time per date";
pub const SESSION_CATEGORY: &str = "assignments";
pub const HOMEWORK_CATEGORIES: [&str; 2] = ["homework", "assignments"];
pub const WEEKDAYS: [&str; 7] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
pub const ROLES: [&str; 8] = [
    "iso",
    "day",
    "inMonth",
    "today",
    "chipsJson",
    "plannedShare",
    "completedShare",
    "accessName",
];

/// One occurrence from an open (saved or unsaved) week overlaid onto the month grid.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OpenOccurrence {
    pub block_id: String,
    pub title: String,
    pub category: String,
    pub day: i64,
    pub start: i64,
    pub end: i64,
    pub done: bool,
    pub history: String,
}

/// One open week keyed by its start ISO date, in overlay order (later entries win on overlap).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OpenWeek {
    pub week_start: String,
    pub occurrences: Vec<OpenOccurrence>,
}

/// One line in a month date cell: a scheduled block at its time, or homework due that day.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MonthChip {
    pub key: String,
    pub title: String,
    pub category: String,
    pub block_id: Option<String>,
    pub start: Option<i64>,
    pub minutes: i64,
    pub due: bool,
    pub due_time: Option<String>,
    pub done: bool,
    pub late: bool,
    pub history: String,
}

impl MonthChip {
    pub fn carried(&self) -> bool {
        chip_carried(self.block_id.as_deref(), self.start, self.due)
    }

    pub fn flag(&self) -> EngineResult<String> {
        chip_flag(&self.history, self.due, self.late, self.due_time.as_deref())
    }

    pub fn words(&self) -> EngineResult<String> {
        chip_words(
            &self.title,
            self.start,
            self.due,
            self.late,
            self.due_time.as_deref(),
            &self.history,
        )
    }

    pub fn to_json(&self) -> Value {
        json!({
            "key": self.key,
            "title": self.title,
            "category": self.category,
            "block_id": self.block_id,
            "start": self.start,
            "minutes": self.minutes,
            "due": self.due,
            "due_time": self.due_time,
            "done": self.done,
            "late": self.late,
            "history": self.history,
        })
    }
}

/// One date cell in the month grid, with its chips and homework study-minute totals.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MonthCell {
    pub iso: String,
    pub in_month: bool,
    pub today: bool,
    pub chips: Vec<MonthChip>,
    pub planned_min: i64,
    pub completed_min: i64,
}

impl MonthCell {
    pub fn day_number(&self) -> EngineResult<i64> {
        day_number(&self.iso)
    }

    pub fn to_json(&self) -> Value {
        json!({
            "iso": self.iso,
            "in_month": self.in_month,
            "today": self.today,
            "chips": self.chips.iter().map(MonthChip::to_json).collect::<Vec<_>>(),
            "planned_min": self.planned_min,
            "completed_min": self.completed_min,
        })
    }
}

/// Decision produced before reading open weeks for `read_cells` or `MonthView::reload`.
#[derive(Clone, Debug, PartialEq)]
pub struct ReadPlan {
    pub clock_24h: Option<bool>,
    pub ready: bool,
    pub chosen_month: Option<String>,
    pub chosen_snapshot: Value,
    pub include_built_week: bool,
    pub weekday_names: Vec<String>,
}

/// Decision for `MonthBridge::activate`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ActivatePlan {
    pub open_month: bool,
    pub reload: bool,
}

/// Decision for `MonthBridge::_shift`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ShiftPlan {
    pub open_month: bool,
    pub amount: i64,
}

pub fn is_homework_category(category: &str) -> bool {
    HOMEWORK_CATEGORIES.contains(&category)
}

/// A block with a time can be carried to another date. A deadline cannot.
pub fn chip_carried(block_id: Option<&str>, start: Option<i64>, due: bool) -> bool {
    block_id.is_some() && start.is_some() && !due
}

/// The state word shown before a deadline or a carried block.
pub fn chip_flag(
    history: &str,
    due: bool,
    late: bool,
    due_time: Option<&str>,
) -> EngineResult<String> {
    if !history.is_empty() {
        return Ok(history.to_string());
    }
    if !due {
        return Ok(String::new());
    }
    if late {
        return Ok("Overdue".to_string());
    }
    match due_time.filter(|text| !text.is_empty()) {
        Some(hhmm) => Ok(format!("Due {}", hhmm_text(hhmm)?)),
        None => Ok("Due".to_string()),
    }
}

/// Full text shown on one month chip.
pub fn chip_words(
    title: &str,
    start: Option<i64>,
    due: bool,
    late: bool,
    due_time: Option<&str>,
    history: &str,
) -> EngineResult<String> {
    let flag = chip_flag(history, due, late, due_time)?;
    if due || !history.is_empty() {
        if !history.is_empty() && !due {
            return Ok(format!(
                "{flag} {} {title}",
                clock_label(start.unwrap_or(0))
            ));
        }
        return Ok(format!("{flag} {title}"));
    }
    Ok(format!("{} {title}", clock_label(start.unwrap_or(0))))
}

/// Day-of-month number from an ISO date string (`"2026-11-05"` -> `5`).
pub fn day_number(iso: &str) -> EngineResult<i64> {
    let tail = iso
        .get(8..)
        .ok_or_else(|| EngineError::value(format!("invalid ISO date: {iso}")))?;
    tail.trim()
        .parse::<i64>()
        .map_err(|_| EngineError::value(format!("invalid ISO date: {iso}")))
}

fn json_str(value: &Value) -> String {
    match value {
        Value::String(text) => text.clone(),
        Value::Bool(true) => "True".to_string(),
        Value::Bool(false) => "False".to_string(),
        Value::Null => "None".to_string(),
        Value::Number(num) => num.to_string(),
        other => other.to_string(),
    }
}

fn truthy_str(value: Option<&Value>) -> Option<String> {
    if !truthy(value) {
        return None;
    }
    value.map(json_str)
}

fn json_int_or_zero(value: Option<&Value>) -> EngineResult<i64> {
    if !truthy(value) {
        return Ok(0);
    }
    match value.expect("truthy value is Some") {
        Value::Bool(flag) => Ok(i64::from(*flag)),
        Value::Number(num) => {
            if let Some(int_val) = num.as_i64() {
                Ok(int_val)
            } else if let Some(float_val) = num.as_f64() {
                Ok(float_val as i64)
            } else {
                Err(EngineError::value(format!(
                    "duration_min out of range: {num}"
                )))
            }
        }
        Value::String(text) => text
            .trim()
            .parse::<i64>()
            .map_err(|_| EngineError::value(format!("invalid integer: {text}"))),
        other => Err(EngineError {
            kind: ErrorKind::Type,
            message: format!("expected integer duration_min, got {other}"),
        }),
    }
}

fn parse_start_minutes(start: &str) -> EngineResult<Option<i64>> {
    if start.chars().count() != 5 {
        return Ok(None);
    }
    let chars: Vec<char> = start.chars().collect();
    let hour_text: String = chars[0..2].iter().collect();
    let min_text: String = chars[3..5].iter().collect();
    let hours = hour_text
        .trim()
        .parse::<i64>()
        .map_err(|_| EngineError::value(format!("invalid start hour in {start}")))?;
    let mins = min_text
        .trim()
        .parse::<i64>()
        .map_err(|_| EngineError::value(format!("invalid start minute in {start}")))?;
    Ok(Some(hours * 60 + mins))
}

fn month_last_iso(month: &str) -> EngineResult<(String, String)> {
    let first = day_of(&format!("{month}-01"))?;
    let first_iso = first.to_string();
    let year: i32 = first_iso[0..4]
        .parse()
        .map_err(|_| EngineError::value(format!("invalid month: {month}")))?;
    let month_num: u32 = first_iso[5..7]
        .parse()
        .map_err(|_| EngineError::value(format!("invalid month: {month}")))?;
    let last_iso = if year == 9999 && month_num == 12 {
        "9999-12-31".to_string()
    } else {
        let next_year = year + i32::from(month_num == 12);
        let next_month = if month_num == 12 { 1 } else { month_num + 1 };
        let next_first = day_of(&format!("{next_year:04}-{next_month:02}-01"))?;
        add_days(next_first, -1)?.to_string()
    };
    Ok((first_iso, last_iso))
}

/// The dates of a month reply, each with its chips and study-minute sums.
///
/// `open_weeks` are the weeks the student currently has open, saved or not, keyed by their start
/// date: a date in one of them is read from it, and any other date is read from `snapshot`.
pub fn month_cells(
    snapshot: &Value,
    open_weeks: &[OpenWeek],
    today_iso: &str,
    month: Option<&str>,
    first_weekday: u32,
) -> EngineResult<Vec<MonthCell>> {
    let snapshot_obj: Map<String, Value> = match snapshot {
        Value::Null => Map::new(),
        Value::Object(map) => map.clone(),
        _ => {
            return Err(EngineError::value(
                "month snapshot must be a JSON object or null",
            ));
        }
    };

    let mut deadlines: HashMap<String, &Map<String, Value>> = HashMap::new();
    for field in ["deadlines", "overdue"] {
        if let Some(list) = snapshot_obj.get(field)
            && !list.is_null()
        {
            let items = list
                .as_array()
                .ok_or_else(|| EngineError::value(format!("snapshot.{field} must be a list")))?;
            for item in items {
                let obj = item.as_object().ok_or_else(|| {
                    EngineError::value(format!("snapshot.{field} entry must be an object"))
                })?;
                if let Some(id_text) = truthy_str(obj.get("id")) {
                    deadlines.insert(id_text, obj);
                }
            }
        }
    }

    let mut open_days: HashMap<String, Vec<&OpenOccurrence>> = HashMap::new();
    for week in open_weeks {
        let monday = day_of(&week.week_start)?;
        for offset in 0..7_i64 {
            let day_iso = add_days(monday, offset)?.to_string();
            let items: Vec<&OpenOccurrence> = week
                .occurrences
                .iter()
                .filter(|item| item.day == offset)
                .collect();
            open_days.insert(day_iso, items);
        }
    }

    let mut days: Map<String, Value> = Map::new();
    if let Some(raw_days) = snapshot_obj.get("days")
        && !raw_days.is_null()
    {
        let items = raw_days
            .as_array()
            .ok_or_else(|| EngineError::value("snapshot.days must be a list"))?;
        for day in items {
            let obj = day
                .as_object()
                .ok_or_else(|| EngineError::value("each snapshot day must be an object"))?;
            let iso = obj
                .get("date")
                .map(json_str)
                .ok_or_else(|| EngineError::value("snapshot day missing 'date'"))?;
            days.insert(iso, Value::Object(obj.clone()));
        }
    }

    let mut resolved_month = truthy_str(snapshot_obj.get("month"))
        .or_else(|| month.filter(|text| !text.is_empty()).map(str::to_string))
        .unwrap_or_default();
    if resolved_month.is_empty() && !days.is_empty() {
        let picked_iso = days
            .iter()
            .find(|(_, day)| truthy(day.as_object().and_then(|map| map.get("in_month"))))
            .or_else(|| days.iter().next())
            .map(|(iso, _)| iso.as_str())
            .unwrap_or("");
        resolved_month = picked_iso.chars().take(7).collect();
    }

    let ordered_days: Vec<Map<String, Value>> = if !resolved_month.is_empty() {
        let (first_iso, last_iso) = month_last_iso(&resolved_month)?;
        let (display_start_iso, display_end_iso) =
            month_grid_from(&first_iso, &last_iso, first_weekday)?;
        let mut current = day_of(&display_start_iso)?;
        let display_end = day_of(&display_end_iso)?;
        let mut out = Vec::new();
        while current <= display_end {
            let iso = current.to_string();
            if let Some(Value::Object(existing)) = days.get(&iso) {
                out.push(existing.clone());
            } else {
                let mut blank = Map::new();
                blank.insert("date".to_string(), Value::String(iso.clone()));
                blank.insert(
                    "in_month".to_string(),
                    Value::Bool(iso.get(5..7) == first_iso.get(5..7)),
                );
                out.push(blank);
            }
            if current == display_end {
                break;
            }
            current = add_days(current, 1)?;
        }
        out
    } else {
        days.values()
            .filter_map(|value| value.as_object().cloned())
            .collect()
    };

    let mut cells = Vec::with_capacity(ordered_days.len());
    for day in ordered_days {
        let iso = day
            .get("date")
            .map(json_str)
            .ok_or_else(|| EngineError::value("day entry missing 'date'"))?;
        let mut chips: Vec<MonthChip> = Vec::new();
        if let Some(due_ids) = day.get("due_ids")
            && !due_ids.is_null()
        {
            let list = due_ids
                .as_array()
                .ok_or_else(|| EngineError::value("day.due_ids must be a list"))?;
            for aid_val in list {
                let aid = json_str(aid_val);
                let found = deadlines.get(&aid).copied();
                let due = found
                    .and_then(|item| truthy_str(item.get("due")))
                    .unwrap_or_default();
                let due_time = if !due.is_empty() && due_is_timed(&due) {
                    Some(due.chars().skip(11).take(5).collect())
                } else {
                    None
                };
                let done = truthy(found.and_then(|item| item.get("completed")));
                let title = found
                    .and_then(|item| truthy_str(item.get("title")))
                    .unwrap_or_else(|| aid.clone());
                let category = found
                    .and_then(|item| truthy_str(item.get("category")))
                    .unwrap_or_else(|| "assignments".to_string());
                chips.push(MonthChip {
                    key: format!("due:{aid}"),
                    title,
                    category,
                    block_id: None,
                    start: None,
                    minutes: 0,
                    due: true,
                    due_time,
                    done,
                    late: iso.as_str() < today_iso && !done,
                    history: String::new(),
                });
            }
        }

        let mut blocks: Vec<MonthChip> = Vec::new();
        if let Some(open_items) = open_days.get(&iso) {
            for item in open_items {
                blocks.push(MonthChip {
                    key: format!("block:{}", item.block_id),
                    title: item.title.clone(),
                    category: item.category.clone(),
                    block_id: Some(item.block_id.clone()),
                    start: Some(item.start),
                    minutes: item.end - item.start,
                    due: false,
                    due_time: None,
                    done: item.done,
                    late: false,
                    history: item.history.clone(),
                });
            }
        } else if let Some(raw_blocks) = day.get("blocks")
            && !raw_blocks.is_null()
        {
            let list = raw_blocks
                .as_array()
                .ok_or_else(|| EngineError::value("day.blocks must be a list"))?;
            for item in list {
                let obj = item
                    .as_object()
                    .ok_or_else(|| EngineError::value("block entry must be an object"))?;
                let start_text = truthy_str(obj.get("start")).unwrap_or_default();
                let Some(start_min) = parse_start_minutes(&start_text)? else {
                    continue;
                };
                let id_text = obj
                    .get("id")
                    .map(json_str)
                    .ok_or_else(|| EngineError::value("block entry missing 'id'"))?;
                let title = truthy_str(obj.get("title")).unwrap_or_else(|| "Untitled".to_string());
                // A homework session is saved with no category unless the student picked one.
                let category = truthy_str(obj.get("category")).unwrap_or_else(|| {
                    if truthy(obj.get("assignment_id")) {
                        SESSION_CATEGORY.to_string()
                    } else {
                        String::new()
                    }
                });
                let minutes = json_int_or_zero(obj.get("duration_min"))?;
                let done = truthy(obj.get("completed"));
                let history = truthy_str(obj.get("history")).unwrap_or_default();
                blocks.push(MonthChip {
                    key: format!("block:{id_text}"),
                    title,
                    category,
                    block_id: Some(id_text),
                    start: Some(start_min),
                    minutes,
                    due: false,
                    due_time: None,
                    done,
                    late: false,
                    history,
                });
            }
        }

        blocks.sort_by(|left, right| {
            (left.start.unwrap_or(0), left.title.as_str())
                .cmp(&(right.start.unwrap_or(0), right.title.as_str()))
        });
        let planned: i64 = blocks
            .iter()
            .filter(|block| is_homework_category(&block.category))
            .map(|block| block.minutes)
            .sum();
        let completed: i64 = blocks
            .iter()
            .filter(|block| is_homework_category(&block.category) && block.done)
            .map(|block| block.minutes)
            .sum();
        chips.extend(blocks);
        cells.push(MonthCell {
            in_month: truthy(day.get("in_month")),
            today: iso == today_iso,
            iso,
            chips,
            planned_min: planned,
            completed_min: completed,
        });
    }

    Ok(cells)
}

/// The week's short day names starting from `first_weekday` (0 Monday to 6 Sunday).
pub fn weekday_names(first_weekday: u32) -> EngineResult<Vec<String>> {
    let order = weekday_order(first_weekday)?;
    Ok(order
        .into_iter()
        .map(|day| WEEKDAYS[day as usize].to_string())
        .collect())
}

/// One row of the date bar, matching the Widgets date pane.
pub fn pane_line(chip: &MonthChip) -> EngineResult<String> {
    if chip.due || !chip.history.is_empty() {
        return chip.words();
    }
    let when = clock_label(chip.start.unwrap_or(0));
    let length = if chip.minutes != 0 {
        format!(" · {}", length_label(chip.minutes))
    } else {
        String::new()
    };
    let mark = if is_homework_category(&chip.category) && chip.done {
        "✓ "
    } else {
        ""
    };
    Ok(format!("{mark}{when} {}{length}", chip.title))
}

/// Study-time fill fraction for a date cell, capped at `LOAD_CAP` (180 min).
pub fn study_share(minutes: i64) -> f64 {
    if minutes <= 0 {
        return 0.0;
    }
    ((minutes as f64) / (LOAD_CAP as f64)).min(1.0)
}

/// Visual chip kind (`"overdue"`, `"due"`, or `"plain"`).
pub fn chip_kind(due: bool, late: bool) -> &'static str {
    if late {
        return "overdue";
    }
    if due {
        return "due";
    }
    "plain"
}

/// Long date heading for the date bar (`"Thursday 5 November"`), never showing a year.
pub fn heading(iso: &str) -> EngineResult<String> {
    let day = day_of(iso)?;
    Ok(day_long(day, day))
}

/// Accessible cell name (`"Saturday 31 October, not in this month"`, `"Monday 2 November, today"`).
pub fn access_name(iso: &str, today: bool, in_month: bool) -> EngineResult<String> {
    let mut words = heading(iso)?;
    if today {
        words.push_str(", today");
    }
    if !in_month {
        words.push_str(", not in this month");
    }
    Ok(words)
}

/// One QML row dict built from a `MonthCell`.
pub fn cell_row(cell: &MonthCell) -> EngineResult<Map<String, Value>> {
    let mut chips = Vec::with_capacity(cell.chips.len());
    let mut chip_texts = Vec::with_capacity(cell.chips.len());
    let mut lines = Vec::with_capacity(cell.chips.len() + 1);
    for chip in &cell.chips {
        let text = chip.words()?;
        chips.push(json!({
            "text": text,
            "kind": chip_kind(chip.due, chip.late),
            "category": event_category(&chip.category),
        }));
        chip_texts.push(Value::String(text));
        lines.push(Value::String(pane_line(chip)?));
    }
    if lines.is_empty() {
        lines.push(Value::String("Nothing planned".to_string()));
    }
    if cell.planned_min != 0 || cell.completed_min != 0 {
        let planned = if cell.planned_min != 0 {
            length_label(cell.planned_min)
        } else {
            "0".to_string()
        };
        let done = if cell.completed_min != 0 {
            length_label(cell.completed_min)
        } else {
            "0".to_string()
        };
        lines.push(Value::String(format!(
            "{planned} homework planned · {done} completed"
        )));
    }
    let chips_json = Value::Array(chips).to_string();
    let mut row = Map::new();
    row.insert("iso".to_string(), Value::String(cell.iso.clone()));
    row.insert("day".to_string(), Value::from(cell.day_number()?));
    row.insert("inMonth".to_string(), Value::Bool(cell.in_month));
    row.insert("today".to_string(), Value::Bool(cell.today));
    row.insert("chipsJson".to_string(), Value::String(chips_json));
    row.insert("chipTexts".to_string(), Value::Array(chip_texts));
    row.insert("lines".to_string(), Value::Array(lines));
    row.insert("heading".to_string(), Value::String(heading(&cell.iso)?));
    row.insert("plannedMin".to_string(), Value::from(cell.planned_min));
    row.insert("completedMin".to_string(), Value::from(cell.completed_min));
    row.insert(
        "plannedShare".to_string(),
        Value::from(study_share(cell.planned_min)),
    );
    row.insert(
        "completedShare".to_string(),
        Value::from(study_share(cell.completed_min)),
    );
    row.insert(
        "accessName".to_string(),
        Value::String(access_name(&cell.iso, cell.today, cell.in_month)?),
    );
    Ok(row)
}

/// Projects a full cell row down to the roles the Qt `Rows` list model exposes to QML.
pub fn date_model_row(row: &Map<String, Value>) -> Map<String, Value> {
    let mut projected = Map::with_capacity(ROLES.len());
    for key in ROLES {
        if let Some(value) = row.get(key) {
            projected.insert(key.to_string(), value.clone());
        }
    }
    projected
}

/// First phase of `read_cells` and `MonthView::reload`: resolves clock, month, snapshot match,
/// and whether open weeks should be queried.
#[allow(clippy::too_many_arguments)]
pub fn prepare_read(
    signed_in: bool,
    prefs: &Value,
    month: Option<&str>,
    selected_month: Option<&str>,
    snapshot: &Value,
    month_data: &Value,
    week_start: Option<&str>,
    first_weekday: u32,
) -> EngineResult<ReadPlan> {
    let names = weekday_names(first_weekday)?;
    if !signed_in {
        return Ok(ReadPlan {
            clock_24h: None,
            ready: false,
            chosen_month: None,
            chosen_snapshot: Value::Null,
            include_built_week: false,
            weekday_names: names,
        });
    }
    let clock_24h = truthy(prefs.as_object().and_then(|map| map.get("clock_24h")));
    set_clock_24h(clock_24h);
    let chosen_month = month
        .filter(|text| !text.is_empty())
        .or_else(|| selected_month.filter(|text| !text.is_empty()))
        .map(str::to_string);
    let mut chosen_snapshot = if !snapshot.is_null() {
        snapshot.clone()
    } else {
        month_data.clone()
    };
    if !chosen_snapshot.is_null() && chosen_month.is_some() {
        let snap_month = chosen_snapshot
            .as_object()
            .and_then(|map| map.get("month"))
            .and_then(Value::as_str);
        if snap_month != chosen_month.as_deref() {
            chosen_snapshot = Value::Null;
        }
    }
    let ready = !(chosen_snapshot.is_null() && chosen_month.is_none());
    let include_built_week = ready && week_start.is_some_and(|text| !text.is_empty());
    Ok(ReadPlan {
        clock_24h: Some(clock_24h),
        ready,
        chosen_month,
        chosen_snapshot,
        include_built_week,
        weekday_names: names,
    })
}

/// Builds QML cell row dicts from a resolved snapshot, open weeks, and date/weekday inputs.
pub fn build_rows(
    snapshot: &Value,
    open_weeks: &[OpenWeek],
    today_iso: &str,
    month: Option<&str>,
    first_weekday: u32,
) -> EngineResult<Vec<Value>> {
    let cells = month_cells(snapshot, open_weeks, today_iso, month, first_weekday)?;
    let mut rows = Vec::with_capacity(cells.len());
    for cell in &cells {
        rows.push(Value::Object(cell_row(cell)?));
    }
    Ok(rows)
}

/// The first day of the month on view: the month the Go to date picker opens on.
pub fn picker_anchor(selected_month: Option<&str>, today_iso: &str) -> String {
    let month = match selected_month.filter(|text| !text.is_empty()) {
        Some(text) => text.to_string(),
        None => today_iso.chars().take(7).collect(),
    };
    format!("{month}-01")
}

/// Target `"YYYY-MM"` for a picked date in Go to date, or `None` when invalid or signed out.
pub fn go_to_date_month(iso: &str, signed_in: bool) -> Option<String> {
    if !signed_in {
        return None;
    }
    let picked = day_of(iso).ok()?;
    Some(picked.to_string().chars().take(7).collect())
}

/// Target `"YYYY-MM"` for Month's T key, clamped to the supported month range.
pub fn today_month(signed_in: bool, today_iso: &str) -> Option<String> {
    signed_in.then(|| month_for_view(today_iso))
}

/// Decides what `MonthBridge::activate` should do when the shell opens the Month screen.
pub fn activate_plan(signed_in: bool, planner_view: &str) -> ActivatePlan {
    if !signed_in {
        return ActivatePlan {
            open_month: false,
            reload: false,
        };
    }
    if planner_view != "month" {
        return ActivatePlan {
            open_month: true,
            reload: false,
        };
    }
    ActivatePlan {
        open_month: false,
        reload: true,
    }
}

/// Decides what `MonthBridge::_shift` should call on the session.
pub fn shift_plan(signed_in: bool, planner_view: &str, amount: i64) -> Option<ShiftPlan> {
    if !signed_in {
        return None;
    }
    Some(ShiftPlan {
        open_month: planner_view != "month",
        amount,
    })
}

/// Stateful view-model backing `desktop/native/material/bridge_month.py::MonthBridge`.
#[derive(Clone, Debug)]
pub struct MonthView {
    pub cell_rows: Vec<Value>,
    pub date_rows: Vec<Value>,
    pub weekday_names: Vec<String>,
    pub selected: String,
    pub heading: String,
    pub lines: Vec<String>,
    pub show_study: bool,
    pub clock_24h: bool,
    pending_month: Option<String>,
    pending_snapshot: Value,
    pending_first_weekday: u32,
}

impl Default for MonthView {
    fn default() -> Self {
        Self::new()
    }
}

impl MonthView {
    pub fn new() -> Self {
        Self {
            cell_rows: Vec::new(),
            date_rows: Vec::new(),
            weekday_names: Vec::new(),
            selected: String::new(),
            heading: String::new(),
            lines: Vec::new(),
            show_study: false,
            clock_24h: true,
            pending_month: None,
            pending_snapshot: Value::Null,
            pending_first_weekday: 0,
        }
    }

    pub fn snapshot(&self) -> Value {
        json!({
            "cellRows": self.cell_rows,
            "dateRows": self.date_rows,
            "weekdayNames": self.weekday_names,
            "selectedIso": self.selected,
            "heading": self.heading,
            "barOpen": !self.selected.is_empty(),
            "lines": self.lines,
            "showStudyTime": self.show_study,
        })
    }

    /// First phase of `MonthBridge::reload`.
    pub fn prepare_reload(
        &mut self,
        signed_in: bool,
        prefs: &Value,
        selected_month: Option<&str>,
        month_data: &Value,
        week_start: Option<&str>,
        first_weekday: u32,
    ) -> EngineResult<ReadPlan> {
        let plan = prepare_read(
            signed_in,
            prefs,
            None,
            selected_month,
            &Value::Null,
            month_data,
            week_start,
            first_weekday,
        )?;
        self.weekday_names = plan.weekday_names.clone();
        if let Some(clock) = plan.clock_24h {
            self.clock_24h = clock;
        }
        if !plan.ready {
            self.cell_rows.clear();
            self.date_rows.clear();
            self.selected.clear();
            self.heading.clear();
            self.lines.clear();
            self.pending_month = None;
            self.pending_snapshot = Value::Null;
            self.pending_first_weekday = first_weekday;
        } else {
            self.pending_month = plan.chosen_month.clone();
            self.pending_snapshot = plan.chosen_snapshot.clone();
            self.pending_first_weekday = first_weekday;
        }
        Ok(plan)
    }

    /// Second phase of `MonthBridge::reload`: builds rows, drops selection if it left the grid,
    /// and updates the date bar.
    pub fn finish_reload(&mut self, open_weeks: &[OpenWeek], today_iso: &str) -> EngineResult<()> {
        set_clock_24h(self.clock_24h);
        let cells = month_cells(
            &self.pending_snapshot,
            open_weeks,
            today_iso,
            self.pending_month.as_deref(),
            self.pending_first_weekday,
        )?;
        let mut rows = Vec::with_capacity(cells.len());
        let mut dates = Vec::with_capacity(cells.len());
        for cell in &cells {
            let full = cell_row(cell)?;
            let projected = date_model_row(&full);
            rows.push(Value::Object(full));
            dates.push(Value::Object(projected));
        }
        self.cell_rows = rows;
        self.date_rows = dates;
        if !self.selected.is_empty() && !self.has_date(&self.selected) {
            self.selected.clear();
        }
        self.fill_bar();
        Ok(())
    }

    fn has_date(&self, iso: &str) -> bool {
        self.cell_rows.iter().any(|row| {
            row.as_object()
                .and_then(|map| map.get("iso"))
                .and_then(Value::as_str)
                == Some(iso)
        })
    }

    fn fill_bar(&mut self) {
        let found = self.cell_rows.iter().find(|row| {
            row.as_object()
                .and_then(|map| map.get("iso"))
                .and_then(Value::as_str)
                == Some(self.selected.as_str())
        });
        let Some(row) = found.and_then(Value::as_object) else {
            self.heading.clear();
            self.lines.clear();
            return;
        };
        self.heading = row
            .get("heading")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        self.lines = row
            .get("lines")
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default();
    }

    /// Toggles selection for `iso`. Returns `false` when `iso` is not in the current grid.
    pub fn select_date(&mut self, iso: &str) -> bool {
        if iso == self.selected {
            self.selected.clear();
        } else if self.has_date(iso) {
            self.selected = iso.to_string();
        } else {
            return false;
        }
        self.fill_bar();
        true
    }

    /// Closes the date bar if open. Returns `false` when already closed.
    pub fn close_date(&mut self) -> bool {
        if self.selected.is_empty() {
            return false;
        }
        self.selected.clear();
        self.fill_bar();
        true
    }

    /// Returns the currently selected ISO date for `openDay`, or `None` if nothing is selected.
    pub fn open_day_target(&self) -> Option<String> {
        (!self.selected.is_empty()).then(|| self.selected.clone())
    }

    /// Toggles the study-time overlay switch. Returns `true` when the value changed.
    pub fn set_show_study_time(&mut self, on: bool) -> bool {
        if self.show_study == on {
            return false;
        }
        self.show_study = on;
        true
    }
}
