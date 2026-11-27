//! Add and Edit fixed time: what the student typed, and what saving it means.
//!
//! The clock, the fresh id and the live session lists stay in Python. This holds the sheet.

use std::collections::BTreeSet;

use flexweek_engine::desk::blocks::until_problem;
use flexweek_engine::desk::calendar::{CATEGORIES, is_series_checked};
use flexweek_engine::desk::datetext::{day_of, day_short};
use flexweek_engine::desk::grid::{
    self, WEEKLY_PREFIX, date_for_day, is_setup_block, is_standing_block, past_problem, span_clash,
};
use flexweek_engine::desk::weekmodel::{clock_text, length_label};
use flexweek_engine::shown::family_id;
use flexweek_engine::stored::{self, dict, int_or_zero, py_int, py_str, truthy, type_name};
use flexweek_engine::time::{DAY_END_MIN, hhmm_to_minutes};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use flexweek_service::blocks::check_block;
use serde_json::{Map, Value, json};

use super::hours::{DEFAULT_DRAG_STEP, drag_step};
use super::sheet_preview::beside_words;
use super::sheet_rules::{
    REPEAT_NOTE, day_range_and_words, first_day_changed, full_day_name, guess_locked_category,
    moved_across_months, moved_day_names, moved_days_note, preset_locked, same_weekday,
    short_day_name, turn_days_keeping_weekdays,
};
use crate::session::sheet_check::{BLOCK_DAYS_PROBLEM, BLOCK_TITLE_PROBLEM, block_sheet_problem};

const STEPS: [&str; 3] = ["What", "When", "Category"];
const PROMPTS: [&str; 3] = ["What is it?", "When is it?", "What category is it?"];
const DAY_END: i64 = DAY_END_MIN;

// English `%b`. `datetext` keeps this table private, and Delete must not follow the computer's locale.
const MONTHS_SHORT: [&str; 12] = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/// What the sheet reads from the session on this call. Python fills it; nothing here reads a clock.
#[derive(Clone, Debug)]
pub struct SheetClock {
    pub week_start: Value,
    pub blocks: Value,
    pub preferences: Value,
    pub repeats: Value,
    pub first_weekday: Value,
    pub today: String,
    pub now_iso: String,
    pub now_minute: i64,
}

impl SheetClock {
    pub fn from_value(value: &Value) -> EngineResult<Self> {
        let map = as_map(value)?;
        Ok(Self {
            week_start: need(map, "week_start")?.clone(),
            blocks: need(map, "blocks")?.clone(),
            preferences: need(map, "preferences")?.clone(),
            repeats: need(map, "repeats")?.clone(),
            first_weekday: need(map, "first_weekday")?.clone(),
            today: text_field(map, "today")?,
            now_iso: text_field(map, "now_iso")?,
            now_minute: py_int(need(map, "now_minute")?)?,
        })
    }
}

#[derive(Clone, Debug)]
struct Picture {
    title: String,
    days: Vec<i64>,
    start: i64,
    end: i64,
    category: Option<String>,
    scope: String,
    missed: bool,
    weekly: bool,
    until: Option<String>,
}

#[derive(Clone, Debug)]
pub struct BlockDraft {
    existing: bool,
    drawn: bool,
    original: Value,
    occurrence_day: Option<i64>,
    step: Option<i64>,
    title: String,
    days: Vec<i64>,
    start: i64,
    length: i64,
    end: i64,
    end_by_hand: bool,
    category: Option<String>,
    guessing: bool,
    series: bool,
    scope: String,
    series_days: Option<Vec<i64>>,
    missed: bool,
    standing: bool,
    family: String,
    show_repeat: bool,
    weekly: bool,
    repeat: Option<Value>,
    until: Option<String>,
    moved: String,
    title_problem: String,
    days_problem: String,
    time_problem: String,
    until_problem_text: String,
    error: String,
    opened: Picture,
    days_week: Value,
    moved_from: Vec<(i64, String)>,
    moved_to: Vec<(i64, String)>,
    moved_note: String,
    days_touched: bool,
}

impl BlockDraft {
    pub fn open(spec: &Value, clock: &SheetClock) -> EngineResult<Self> {
        let map = as_map(spec)?;
        let block = match py_get(spec, "block")? {
            None | Some(Value::Null) => None,
            Some(value) => Some(value.clone()),
        };
        let day = match py_get(spec, "day")? {
            None | Some(Value::Null) => 0,
            Some(value) => py_int(value)?,
        };
        let start_arg = match py_get(spec, "start")? {
            Some(Value::String(text)) => text.clone(),
            None | Some(Value::Null) => "16:00".to_string(),
            Some(other) => {
                return Err(type_error(format!(
                    "start must be text, not '{}'",
                    type_name(other)
                )));
            }
        };
        let category_arg = match py_get(spec, "category")? {
            Some(value) if truthy(Some(value)) => Some(py_str(value)),
            _ => None,
        };
        let occurrence_day = match py_get(spec, "occurrence_day")? {
            None | Some(Value::Null) => None,
            Some(value) => Some(py_int(value)?),
        };
        let length_arg = match py_get(spec, "length")? {
            None | Some(Value::Null) => None,
            Some(value) => Some(py_int(value)?),
        };
        let existing = block.is_some();
        let drawn = block.is_none() && length_arg.is_some();
        let mut original = if let Some(block) = block {
            block
        } else {
            let fresh_id = text_field(map, "id")?;
            let preset_length = match length_arg {
                Some(length) if length != 0 => length,
                _ => 60,
            };
            let week = match &clock.week_start {
                Value::String(text) if !text.is_empty() => text.clone(),
                _ => String::new(),
            };
            preset_locked(&json!({
                "id": fresh_id,
                "category": category_arg.clone(),
                "day": day,
                "start": start_arg,
                "duration_min": preset_length,
                "week_start": week,
            }))?
        };
        if drawn {
            let length = length_arg.unwrap_or(0);
            let fields = object_mut(&mut original)?;
            fields.insert("days".into(), json!([day]));
            fields.insert("start".into(), Value::from(start_arg.clone()));
            fields.insert("duration_min".into(), Value::from(length));
        }
        let title = py_str(require(&original, "title")?);
        let active = active_days_of(&original)?;
        let start_text = match py_get(&original, "start")? {
            Some(value) if truthy(Some(value)) => py_str(value),
            _ => start_arg,
        };
        let start = hhmm_to_minutes(&start_text)?;
        let length = py_int(require(&original, "duration_min")?)?;
        let end = (start + length).min(DAY_END);
        let mut category = match py_get(&original, "category")? {
            Some(value) if truthy(Some(value)) => Some(py_str(value)),
            _ => category_arg,
        };
        let guessing = !existing && category.is_none();
        if guessing {
            category = Some(guess_locked_category(&store_clock(start))?);
        }
        let mut probe = original.clone();
        object_mut(&mut probe)?.insert("days".into(), json!(active));
        let series = if existing {
            is_series_checked(&probe)?
        } else {
            false
        };
        let scope = if series && occurrence_day.is_some() {
            "occurrence"
        } else {
            "series"
        };
        let (series_days, days) = if scope == "occurrence" {
            (Some(active.clone()), vec![occurrence_day.unwrap_or(0)])
        } else {
            (None, active)
        };
        let missed = missed_flag(&original, occurrence_day)?;
        let standing = if existing {
            is_standing_block(&original)?
        } else {
            false
        };
        let family = if existing {
            family_id(&py_str(require(&original, "id")?)).to_string()
        } else {
            String::new()
        };
        let show_repeat = if existing {
            !is_setup_block(&original)?
        } else {
            true
        };
        let weekly = standing && family.starts_with(WEEKLY_PREFIX);
        let repeat = if weekly {
            find_repeat(&clock.repeats, &family)?
        } else {
            None
        };
        let until = until_of(repeat.as_ref())?;
        let mut draft = Self {
            existing,
            drawn,
            original,
            occurrence_day,
            step: if existing { None } else { Some(0) },
            title,
            days,
            start,
            length,
            end,
            end_by_hand: false,
            category,
            guessing,
            series,
            scope: scope.to_string(),
            series_days,
            missed,
            standing,
            family,
            show_repeat,
            weekly,
            repeat,
            until,
            moved: String::new(),
            title_problem: String::new(),
            days_problem: String::new(),
            time_problem: String::new(),
            until_problem_text: String::new(),
            error: String::new(),
            opened: Picture {
                title: String::new(),
                days: Vec::new(),
                start: 0,
                end: 0,
                category: None,
                scope: String::new(),
                missed: false,
                weekly: false,
                until: None,
            },
            days_week: week_value(&clock.week_start),
            moved_from: Vec::new(),
            moved_to: Vec::new(),
            moved_note: String::new(),
            days_touched: false,
        };
        draft.opened = draft.picture();
        Ok(draft)
    }

    pub fn dirty(&self) -> bool {
        !same_picture(&self.picture(), &self.opened)
    }

    pub fn set(&mut self, name: &str, value: &Value) -> EngineResult<()> {
        self.error.clear();
        match name {
            "title" => {
                self.title = py_str(value);
                self.title_problem.clear();
            }
            "start" => self.move_start(hhmm_to_minutes(&py_str(value))?)?,
            "end" => {
                self.end = py_int(value)?;
                self.end_by_hand = true;
                self.moved.clear();
                self.time_problem.clear();
                if self.end > self.start {
                    self.length = self.end - self.start;
                }
            }
            "category" => {
                let text = py_str(value);
                self.category = if text.is_empty() { None } else { Some(text) };
                self.guessing = false;
            }
            "scope" => {
                let scope = if eq(value, &Value::from("occurrence")) {
                    "occurrence"
                } else {
                    "series"
                };
                self.set_scope(scope)?;
            }
            "missed" => self.missed = truthy(Some(value)),
            "repeat" if self.show_repeat => {
                self.weekly = truthy(Some(value));
                self.until_problem_text.clear();
                if !self.weekly {
                    self.until = None;
                }
            }
            "until" if self.weekly => {
                let text = py_str(value);
                self.until = if text.is_empty() { None } else { Some(text) };
                self.until_problem_text.clear();
            }
            _ => {}
        }
        Ok(())
    }

    pub fn toggle_day(&mut self, day: &Value) -> EngineResult<()> {
        if self.scope == "occurrence" && self.occurrence_day.is_some() {
            return Ok(());
        }
        let day = py_int(day)?;
        self.error.clear();
        self.days_problem.clear();
        self.clear_moves();
        self.days_touched = true;
        let mut days: Vec<i64> = Vec::new();
        for held in &self.days {
            if !days.contains(held) {
                days.push(*held);
            }
        }
        if let Some(index) = days.iter().position(|held| *held == day) {
            days.remove(index);
        } else {
            days.push(day);
        }
        days.sort();
        self.days = days;
        Ok(())
    }

    pub fn use_picked(&mut self, day: i64, start: &str, length: i64) -> EngineResult<()> {
        self.error.clear();
        self.days = vec![day];
        self.days_problem.clear();
        self.days_touched = true;
        self.drawn = true;
        self.clear_moves();
        self.end_by_hand = false;
        self.length = length;
        self.move_start(hhmm_to_minutes(start)?)?;
        // A grid reopen shows the picked time, not the sentence the move just wrote.
        self.moved.clear();
        Ok(())
    }

    pub fn follow_week(&mut self, fresh_days: &[Value], clock: &SheetClock) -> EngineResult<()> {
        let week = week_value(&clock.week_start);
        let into_week = week_text(&week)?;
        let from_text = week_text(&self.days_week)?;
        if first_day_changed(&from_text, &into_week)? && !self.drawn && !self.days_touched {
            let fresh = sorted_ints(ints_of(fresh_days)?);
            self.days = fresh.clone();
            self.opened.days = fresh;
            self.days_week = week;
            self.clear_moves();
            return Ok(());
        }
        let (turned, moved) = turn_days_keeping_weekdays(&self.days, &from_text, &into_week)?;
        let mut names: Vec<(i64, (String, String))> = Vec::new();
        for (old, new) in &moved {
            let pair = moved_day_names(*old, &from_text, *new, &into_week)?;
            upsert_pair(&mut names, *new, pair);
        }
        self.moved_from = names
            .iter()
            .map(|(new, (old_name, _))| (*new, old_name.clone()))
            .collect();
        self.moved_to.clear();
        for (old, new) in &moved {
            if moved_across_months(*old, &from_text, *new, &into_week)? {
                let new_name = names
                    .iter()
                    .find(|(day, _)| day == new)
                    .map(|(_, (_, name))| name.clone())
                    .unwrap_or_default();
                upsert_text(&mut self.moved_to, *new, new_name);
            }
        }
        let pairs: Vec<(String, String)> = names.into_iter().map(|(_, pair)| pair).collect();
        self.moved_note = moved_days_note(&pairs);
        self.days = turned;
        let mut opened = Vec::new();
        for day in &self.opened.days {
            opened.push(same_weekday(*day, &from_text, &into_week)?);
        }
        opened.sort();
        self.opened.days = opened;
        self.days_week = week;
        Ok(())
    }

    pub fn back(&mut self) {
        if let Some(step) = self.step
            && step != 0
        {
            self.step = Some(step - 1);
        }
    }

    pub fn goto(&mut self, index: i64) {
        if let Some(step) = self.step
            && (0..step).contains(&index)
        {
            self.step = Some(index);
        }
    }

    pub fn advance(&mut self, clock: &SheetClock) -> EngineResult<bool> {
        if self.step.is_none() || self.step.is_some_and(|step| step >= 2) {
            return Ok(true);
        }
        if self.step == Some(0) && python_strip(&self.title).is_empty() {
            self.title_problem = BLOCK_TITLE_PROBLEM.to_string();
            return Ok(false);
        }
        if self.step == Some(1) {
            if let Some(problem) = self.time_problem(clock)? {
                self.time_problem = problem;
                return Ok(false);
            }
            if self.days.is_empty() {
                self.days_problem = BLOCK_DAYS_PROBLEM.to_string();
                return Ok(false);
            }
            let problem = self.until_text(clock, &self.series_days_now())?;
            if !problem.is_empty() {
                self.until_problem_text = problem;
                return Ok(false);
            }
        }
        if let Some(step) = self.step {
            self.step = Some(step + 1);
        }
        Ok(false)
    }

    pub fn candidate(&mut self, clock: &SheetClock) -> EngineResult<Option<Value>> {
        if python_strip(&self.title).is_empty() {
            self.title_problem = BLOCK_TITLE_PROBLEM.to_string();
            self.step = self.step.map(|_| 0);
            return Ok(None);
        }
        if let Some(problem) = self.time_problem(clock)? {
            self.time_problem = problem;
            self.step = self.step.map(|_| 1);
            return Ok(None);
        }
        let mut made = object_owned(&self.original)?;
        made.insert("title".into(), Value::from(python_strip(&self.title)));
        made.insert("days".into(), json!(self.days));
        made.insert("start".into(), Value::from(store_clock(self.start)));
        made.insert("duration_min".into(), Value::from(self.span()));
        made.insert(
            "category".into(),
            self.category
                .clone()
                .map(Value::from)
                .unwrap_or(Value::Null),
        );
        let current_days = json!(self.days);
        let missed_source = match made.get("missed_days") {
            None => Vec::new(),
            Some(value) => iterate(value)?,
        };
        let restored = self
            .occurrence_day
            .filter(|_| !self.missed)
            .map(Value::from);
        let filtered = if self.existing && self.occurrence_day.is_some() {
            filter_missed(&missed_source, &current_days, restored.as_ref())?
        } else {
            filter_missed(&missed_source, &current_days, None)?
        };
        made.insert("missed_days".into(), Value::Array(filtered));
        let kind = made
            .get("kind")
            .ok_or_else(|| EngineError::key("kind"))?
            .clone();
        if !eq(&kind, &Value::from("locked")) {
            self.error = "Use the homework editor for homework sessions.".to_string();
            return Ok(None);
        }
        if self.scope == "occurrence"
            && let Some(series_days) = &self.series_days
        {
            let mut days = series_days.clone();
            days.sort();
            made.insert("days".into(), json!(days));
        }
        let empty = made
            .get("days")
            .and_then(Value::as_array)
            .is_some_and(Vec::is_empty);
        if empty {
            self.days_problem = BLOCK_DAYS_PROBLEM.to_string();
            self.step = self.step.map(|_| 1);
            return Ok(None);
        }
        if made.contains_key("removed_days") {
            let ticked = made.get("days").cloned().unwrap_or_else(|| json!([]));
            let removed = iterate(made.get("removed_days").unwrap_or(&Value::Null))?;
            let mut kept = Vec::new();
            for day in removed {
                if !contains(&ticked, &day)? {
                    kept.push(day);
                }
            }
            let mut union = unique_values(iterate(&ticked)?);
            for day in &kept {
                if !union.iter().any(|held| eq(held, day)) {
                    union.push(day.clone());
                }
            }
            let sorted = sorted_values(union)?;
            made.insert("days".into(), Value::Array(sorted));
            if kept.is_empty() {
                made.shift_remove("removed_days");
            } else {
                made.insert("removed_days".into(), Value::Array(kept));
            }
        }
        let made = Value::Object(made);
        if let Some((field, message)) = block_sheet_problem(&made) {
            if field == "title" {
                self.title_problem = message;
                self.step = self.step.map(|_| 0);
            } else if field == "days" {
                self.days_problem = message;
                self.step = self.step.map(|_| 1);
            } else {
                self.error = message;
            }
            return Ok(None);
        }
        let problem = self.until_text(clock, &self.series_days_now())?;
        if !problem.is_empty() {
            self.until_problem_text = problem;
            self.step = self.step.map(|_| 1);
            return Ok(None);
        }
        Ok(Some(made))
    }

    pub fn clash(&self, blocks: &Value) -> EngineResult<String> {
        if self.span() <= 0 {
            return Ok(String::new());
        }
        let id = require(&self.original, "id")?.clone();
        for day in &self.days {
            if let Some(title) = span_clash(blocks, &id, &Value::from(*day), self.start, self.end)?
                && !title.is_empty()
            {
                return Ok(beside_words(&title));
            }
        }
        Ok(String::new())
    }

    pub fn stopped_one_off(&self, made: &Value) -> EngineResult<Option<Value>> {
        let removed = match py_get(made, "removed_days")? {
            Some(value) if truthy(Some(value)) => value.clone(),
            _ => json!([]),
        };
        let days = match py_get(made, "days")? {
            Some(value) if truthy(Some(value)) => iterate(value)?,
            _ => Vec::new(),
        };
        let mut kept = Vec::new();
        for day in days {
            if !contains(&removed, &day)? {
                kept.push(day);
            }
        }
        if kept.is_empty() {
            return Ok(None);
        }
        let mut alone = object_owned(made)?;
        alone.shift_remove("until");
        alone.shift_remove("removed_days");
        let skip = WEEKLY_PREFIX.len();
        let id = self.family.get(skip..).unwrap_or("").to_string();
        alone.insert("id".into(), Value::from(id));
        alone.insert("days".into(), Value::Array(kept.clone()));
        if let Some(missed) = alone.get("missed_days").cloned() {
            let mut still = Vec::new();
            for day in iterate(&missed)? {
                if contains(&Value::Array(kept.clone()), &day)? {
                    still.push(day);
                }
            }
            alone.insert("missed_days".into(), Value::Array(still));
        }
        Ok(Some(Value::Object(alone)))
    }

    pub fn save_plan(
        &self,
        made: &Value,
        clock: &SheetClock,
        fresh_id: &str,
    ) -> EngineResult<Value> {
        let changed = self.changed_names();
        let changed_value = Value::from(
            changed
                .iter()
                .map(|name| Value::from(*name))
                .collect::<Vec<_>>(),
        );
        if !self.show_repeat {
            return Ok(json!({"kind": "plain", "changed": changed_value}));
        }
        if !self.existing {
            if !self.weekly {
                return Ok(json!({"kind": "plain", "changed": changed_value}));
            }
            let repeat = self.repeat_body(made, None, &changed, clock, fresh_id)?;
            return Ok(json!({"kind": "add", "repeat": repeat, "changed": changed_value}));
        }
        if !self.weekly {
            let kind = if self.standing { "stop" } else { "plain" };
            return Ok(json!({"kind": kind, "changed": changed_value}));
        }
        if !self.standing {
            let repeat = self.repeat_body(made, None, &changed, clock, fresh_id)?;
            return Ok(json!({"kind": "make", "repeat": repeat, "changed": changed_value}));
        }
        if self.repeat.is_none() {
            return Ok(json!({"kind": "plain", "changed": changed_value}));
        }
        if self.scope == "occurrence" && self.occurrence_day.is_some() {
            return Ok(json!({"kind": "plain", "changed": changed_value}));
        }
        let repeat = self.repeat_body(made, self.repeat.as_ref(), &changed, clock, fresh_id)?;
        if changed
            .iter()
            .all(|name| *name == "weekly" || *name == "until")
        {
            return Ok(json!({"kind": "later", "repeat": repeat, "changed": changed_value}));
        }
        Ok(json!({"kind": "ask", "repeat": repeat, "changed": changed_value}))
    }

    pub fn recover_missed(&self) -> EngineResult<bool> {
        if !(self.existing && self.occurrence_day.is_some() && self.missed) {
            return Ok(false);
        }
        let day = Value::from(self.occurrence_day.unwrap_or(0));
        let missed = match py_get(&self.original, "missed_days")? {
            Some(value) if truthy(Some(value)) => value.clone(),
            _ => json!([]),
        };
        Ok(!contains(&missed, &day)?)
    }

    pub fn delete_question(&self, clock: &SheetClock) -> EngineResult<Value> {
        let name = shown_name(&self.original, None)?;
        let occurrence = self.scope == "occurrence" && self.occurrence_day.is_some();
        let stamp = if occurrence {
            Some(self.occurrence_stamp(clock)?)
        } else {
            None
        };
        let question = if let Some(stamp) = &stamp {
            format!(
                "Delete {name} on {} {} {} only?",
                stamp.day_name, stamp.day, stamp.month
            )
        } else {
            let days = day_range_and_words(&self.active_days()?, &shown_week(&clock.week_start))?;
            format!("Delete {name} on every {days} this week?")
        };
        if is_standing_block(&self.original)? {
            let mut answers = vec![json!({"id": "stay", "label": "Cancel", "kind": "text"})];
            let mut cards = Vec::new();
            if let Some(stamp) = &stamp {
                answers.push(json!({"id": "day", "label": "This day only", "kind": "tonal"}));
                cards.push(json!({
                    "id": "day",
                    "title": format!("Just {} {} {}", stamp.day_name, stamp.day, stamp.month),
                    "line": format!("Other days this week and other weeks keep {name}. You can undo this."),
                }));
            }
            answers.push(json!({"id": "week", "label": "This week only", "kind": "tonal"}));
            answers.push(json!({"id": "every", "label": "This week and later", "kind": "danger"}));
            cards.push(json!({
                "id": "week",
                "title": "This week only",
                "line": format!("Other weeks keep {name}. You can undo this."),
            }));
            cards.push(json!({
                "id": "every",
                "title": "This week and every week after",
                "line": format!("Earlier weeks keep {name}. Undo also takes back anything changed after it."),
            }));
            return Ok(json!({
                "id": "delete-block",
                "title": format!("Delete {name}?"),
                "body": "",
                "answers": answers,
                "cards": cards,
                "confirm": "Delete",
            }));
        }
        Ok(json!({
            "id": "delete-block",
            "title": "Delete fixed time",
            "body": format!("{question} You can undo this."),
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text"},
                {"id": "delete", "label": "Delete", "kind": "danger"},
            ],
        }))
    }

    pub fn save_question(&self) -> EngineResult<Value> {
        let name = shown_name(&self.original, Some(python_strip(&self.title)))?;
        Ok(json!({
            "id": "block-save",
            "title": format!("Change {name}?"),
            "body": "",
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text"},
                {"id": "week", "label": "This week only", "kind": "tonal"},
                {"id": "later", "label": "This week and later", "kind": "tonal"},
            ],
            "cards": [
                {
                    "id": "week",
                    "title": "This week only",
                    "line": format!("Other weeks keep {name} as it was."),
                },
                {
                    "id": "later",
                    "title": "This week and every week after",
                    "line": format!("Earlier weeks keep {name} as it was."),
                },
            ],
            "confirm": "Save",
        }))
    }

    pub fn form(&self, clock: &SheetClock) -> EngineResult<Value> {
        let step = self.step;
        let span = self.span();
        let problem = self.span_problem();
        let line = if !problem.is_empty() {
            problem.clone()
        } else if !self.moved.is_empty() {
            self.moved.clone()
        } else {
            length_label(span)
        };
        let week = shown_week(&clock.week_start);
        let done = [
            python_strip(&self.title).to_string(),
            format!(
                "{}, {}",
                day_range_and_words(&self.days, &week)?,
                clock_text(self.start)
            ),
        ];
        let mut crumbs = Vec::new();
        if step.is_some() {
            for (index, name) in STEPS.iter().enumerate() {
                let index = i64::try_from(index).unwrap_or(0);
                let done_step = step.is_some_and(|step| index < step);
                let label = if done_step {
                    format!("\u{2713} {name}")
                } else {
                    format!("{}. {name}", index + 1)
                };
                let summary = if done_step && index < 2 {
                    done[index as usize].clone()
                } else {
                    String::new()
                };
                crumbs.push(json!({
                    "label": label,
                    "done": done_step,
                    "on": step == Some(index),
                    "summary": summary,
                }));
            }
        }
        let locked = self.scope == "occurrence" && self.occurrence_day.is_some();
        let every = chosen_step(&clock.preferences)?;
        let mut starts = BTreeSet::new();
        let mut minute = 0;
        while minute < DAY_END {
            starts.insert(minute);
            minute += every;
        }
        starts.insert(self.opened.start);
        starts.insert(self.start);
        let mut ends = BTreeSet::new();
        minute = every;
        while minute <= DAY_END {
            ends.insert(minute);
            minute += every;
        }
        ends.insert(self.opened.end);
        ends.insert(self.end);
        let start_options: Vec<Value> = starts
            .iter()
            .map(|minute| json!({"value": store_clock(*minute), "label": clock_text(*minute)}))
            .collect();
        let end_options: Vec<Value> = ends
            .iter()
            .map(|minute| json!({"value": minute, "label": clock_text(*minute)}))
            .collect();
        let mut categories = vec![json!({"value": "", "label": "None"})];
        for (key, info) in &CATEGORIES {
            categories.push(json!({"value": *key, "label": info.label}));
        }
        if let Some(category) = &self.category
            && !CATEGORIES.iter().any(|(key, _)| *key == category)
        {
            categories.push(json!({"value": category, "label": category}));
        }
        let chip_week = chip_week(&clock.week_start)?;
        let mut days = Vec::new();
        for index in 0..7 {
            let date = match &chip_week {
                Some(week) => month_day(&date_for_day(week, &Value::from(index))?)?,
                None => 0,
            };
            days.push(json!({
                "value": index,
                "label": short_day_name(&week, index)?,
                "date": date,
                "on": self.days.contains(&index),
                "moved": self.moved_from.iter().any(|(day, _)| *day == index),
                "movedFrom": moved_text(&self.moved_from, index),
                "movedTo": moved_text(&self.moved_to, index),
            }));
        }
        let scope_days = self.scope_choice_days()?;
        let missed_label = match self.occurrence_day {
            None => "I missed it".to_string(),
            Some(day) => format!("I missed it on {}", full_day_name(&week, day)?),
        };
        let until_problem = if self.until_problem_text.is_empty() {
            self.until_text(clock, &self.series_days_now())?
        } else {
            self.until_problem_text.clone()
        };
        Ok(json!({
            "kind": "block",
            "mode": if self.existing { "edit" } else { "add" },
            "heading": if self.existing { "Edit fixed time" } else { "Add fixed time" },
            "step": step.unwrap_or(-1),
            "crumbs": crumbs,
            "prompt": step.and_then(|step| PROMPTS.get(step as usize).copied()).unwrap_or(""),
            "title": self.title,
            "titleProblem": self.title_problem,
            "days": days,
            "daysLocked": locked,
            "daysProblem": self.days_problem,
            "movedNote": self.moved_note,
            "repeatNote": if locked { "" } else { REPEAT_NOTE },
            "showScope": self.series && self.occurrence_day.is_some(),
            "scopeChoices": [
                {"value": "occurrence", "label": "This day only"},
                {"value": "series", "label": format!("Every {}", day_range_and_words(&scope_days, &week)?)},
            ],
            "scope": self.scope,
            "seriesNote": self.series_note()?,
            "start": store_clock(self.start),
            "startOptions": start_options,
            "end": self.end,
            "endOptions": end_options,
            "durationLine": line,
            "durationIsProblem": !problem.is_empty(),
            "timeProblem": self.time_problem,
            "clash": self.clash(&clock.blocks)?,
            "category": self.category.clone().unwrap_or_default(),
            "categoryOptions": categories,
            "missed": self.missed,
            "showMissed": self.existing && self.occurrence_day.is_some(),
            "missedLabel": missed_label,
            "showRepeat": self.show_repeat && !locked,
            "repeat": self.weekly,
            "until": self.until.clone().unwrap_or_default(),
            "untilLabel": self.until_label(&clock.today)?,
            "todayIso": clock.today,
            "untilProblem": until_problem,
            "error": self.error,
            "canBack": self.step.is_some_and(|step| step != 0),
            "primary": if step.is_some_and(|step| step >= 2) {
                "Add"
            } else if self.existing {
                "Save"
            } else {
                "Next"
            },
            "last": step.is_none_or(|step| step >= 2),
            "canDelete": self.existing,
        }))
    }

    pub fn to_value(&self) -> Value {
        json!({
            "existing": self.existing,
            "drawn": self.drawn,
            "original": self.original,
            "occurrence_day": self.occurrence_day,
            "step": self.step,
            "title": self.title,
            "days": self.days,
            "start": self.start,
            "length": self.length,
            "end": self.end,
            "end_by_hand": self.end_by_hand,
            "category": self.category,
            "guessing": self.guessing,
            "series": self.series,
            "scope": self.scope,
            "series_days": self.series_days,
            "missed": self.missed,
            "standing": self.standing,
            "family": self.family,
            "show_repeat": self.show_repeat,
            "weekly": self.weekly,
            "repeat": self.repeat,
            "until": self.until,
            "moved": self.moved,
            "title_problem": self.title_problem,
            "days_problem": self.days_problem,
            "time_problem": self.time_problem,
            "until_problem_text": self.until_problem_text,
            "error": self.error,
            "opened": picture_value(&self.opened),
            "days_week": self.days_week,
            "moved_from": pair_values(&self.moved_from),
            "moved_to": pair_values(&self.moved_to),
            "moved_note": self.moved_note,
            "days_touched": self.days_touched,
        })
    }

    pub fn from_value(value: &Value) -> EngineResult<Self> {
        let map = as_map(value)?;
        Ok(Self {
            existing: bool_field(map, "existing")?,
            drawn: bool_field(map, "drawn")?,
            original: need(map, "original")?.clone(),
            occurrence_day: opt_int(map, "occurrence_day")?,
            step: opt_int(map, "step")?,
            title: text_field(map, "title")?,
            days: ints_of(
                need(map, "days")?
                    .as_array()
                    .ok_or_else(|| EngineError::key("days"))?,
            )?,
            start: py_int(need(map, "start")?)?,
            length: py_int(need(map, "length")?)?,
            end: py_int(need(map, "end")?)?,
            end_by_hand: bool_field(map, "end_by_hand")?,
            category: opt_text(map, "category")?,
            guessing: bool_field(map, "guessing")?,
            series: bool_field(map, "series")?,
            scope: text_field(map, "scope")?,
            series_days: opt_days(map, "series_days")?,
            missed: bool_field(map, "missed")?,
            standing: bool_field(map, "standing")?,
            family: text_field(map, "family")?,
            show_repeat: bool_field(map, "show_repeat")?,
            weekly: bool_field(map, "weekly")?,
            repeat: opt_clone(map, "repeat")?,
            until: opt_text(map, "until")?,
            moved: text_field(map, "moved")?,
            title_problem: text_field(map, "title_problem")?,
            days_problem: text_field(map, "days_problem")?,
            time_problem: text_field(map, "time_problem")?,
            until_problem_text: text_field(map, "until_problem_text")?,
            error: text_field(map, "error")?,
            opened: picture_from(need(map, "opened")?)?,
            days_week: need(map, "days_week")?.clone(),
            moved_from: pairs_from(need(map, "moved_from")?)?,
            moved_to: pairs_from(need(map, "moved_to")?)?,
            moved_note: text_field(map, "moved_note")?,
            days_touched: bool_field(map, "days_touched")?,
        })
    }

    fn picture(&self) -> Picture {
        Picture {
            title: self.title.clone(),
            days: self.days.clone(),
            start: self.start,
            end: self.end,
            category: self.category.clone(),
            scope: self.scope.clone(),
            missed: self.missed,
            weekly: self.weekly,
            until: self.until.clone(),
        }
    }

    fn move_start(&mut self, minute: i64) -> EngineResult<()> {
        let before = self.start;
        let old_end = self.end;
        self.start = minute;
        self.time_problem.clear();
        if self.guessing {
            self.category = Some(guess_locked_category(&store_clock(minute))?);
        }
        if self.end_by_hand {
            self.moved.clear();
            return Ok(());
        }
        let end = (minute + self.length).min(DAY_END);
        let kept = end - minute;
        self.moved.clear();
        if (end != old_end || kept < self.length) && minute != before {
            self.moved = moved_sentence(end, kept, self.length);
        }
        self.end = end;
        Ok(())
    }

    fn set_scope(&mut self, scope: &str) -> EngineResult<()> {
        if self.occurrence_day.is_none() || !self.series {
            return Ok(());
        }
        if scope == "occurrence" && self.scope != "occurrence" {
            self.series_days = Some(self.days.clone());
            self.days = vec![self.occurrence_day.unwrap_or(0)];
        } else if scope == "series" && self.scope == "occurrence" {
            let mut days = match self
                .series_days
                .as_ref()
                .filter(|stored| !stored.is_empty())
            {
                Some(stored) => stored.clone(),
                None => self.active_days()?,
            };
            days.sort();
            self.days = days;
            self.series_days = None;
        }
        self.scope = scope.to_string();
        Ok(())
    }

    fn span(&self) -> i64 {
        self.end - self.start
    }

    fn span_problem(&self) -> String {
        if self.span() <= 0 {
            format!(
                "End needs to be later than Start ({}).",
                clock_text(self.start)
            )
        } else {
            String::new()
        }
    }

    fn time_problem(&self, clock: &SheetClock) -> EngineResult<Option<String>> {
        let span = self.span_problem();
        if !span.is_empty() {
            return Ok(Some(span));
        }
        self.past_text(clock)
    }

    fn past_text(&self, clock: &SheetClock) -> EngineResult<Option<String>> {
        let Some(week) = string_week(&clock.week_start) else {
            return Ok(None);
        };
        let original_days = optional_day_numbers(&self.original, "days")?;
        let original_start = match py_get(&self.original, "start")? {
            Some(value) if truthy(Some(value)) => py_str(value),
            _ => String::new(),
        };
        let chosen = self.days.clone();
        let single = chosen.len() == 1;
        for day in chosen {
            let added = !original_days.contains(&day);
            let moved =
                single && original_days.contains(&day) && store_clock(self.start) != original_start;
            if self.existing && !added && !moved {
                continue;
            }
            if let Some(problem) = past_problem(
                "locked",
                &week,
                day,
                self.start,
                &clock.now_iso,
                clock.now_minute,
                DEFAULT_DRAG_STEP,
            )? {
                return Ok(Some(problem));
            }
        }
        Ok(None)
    }

    fn active_days(&self) -> EngineResult<Vec<i64>> {
        active_days_of(&self.original)
    }

    fn series_days_now(&self) -> Vec<i64> {
        if self.scope == "occurrence"
            && let Some(days) = &self.series_days
        {
            return days.clone();
        }
        self.days.clone()
    }

    fn scope_choice_days(&self) -> EngineResult<Vec<i64>> {
        let chosen = self.series_days_now();
        if chosen.is_empty() {
            self.active_days()
        } else {
            Ok(chosen)
        }
    }

    fn series_note(&self) -> EngineResult<String> {
        let active = self.active_days()?;
        let covered = self.series && self.occurrence_day.is_some();
        if self.existing && active.len() > 1 && !covered {
            Ok("Changes apply to every selected day in this series.".to_string())
        } else {
            Ok(String::new())
        }
    }

    fn until_text(&self, clock: &SheetClock, days: &[i64]) -> EngineResult<String> {
        if self.weekly
            && self.until.as_ref().is_some_and(|text| !text.is_empty())
            && let Some(week) = string_week(&clock.week_start)
        {
            let mut sorted = days.to_vec();
            sorted.sort();
            let probe = json!({
                "id": "weekly-probe",
                "days": sorted,
                "until": self.until,
            });
            return Ok(until_problem(&probe, &week, &clock.today)?.unwrap_or_default());
        }
        Ok(String::new())
    }

    fn until_label(&self, today: &str) -> EngineResult<String> {
        let Some(until) = &self.until else {
            return Ok("No end".to_string());
        };
        if until.is_empty() {
            return Ok("No end".to_string());
        }
        match (day_of(until), day_of(today)) {
            (Ok(until_day), Ok(today_day)) => Ok(day_short(until_day, today_day)),
            _ => Ok(until.clone()),
        }
    }

    fn changed_names(&self) -> Vec<&'static str> {
        let mut changed = Vec::new();
        if python_strip(&self.title) != python_strip(&self.opened.title) {
            changed.push("title");
        }
        if self.days != self.opened.days {
            changed.push("days");
        }
        if self.start != self.opened.start {
            changed.push("start");
        }
        if self.end != self.opened.end {
            changed.push("end");
        }
        if self.category != self.opened.category {
            changed.push("category");
        }
        if self.missed != self.opened.missed {
            changed.push("missed");
        }
        if self.weekly != self.opened.weekly {
            changed.push("weekly");
        }
        if self.until != self.opened.until {
            changed.push("until");
        }
        changed
    }

    fn repeat_body(
        &self,
        made: &Value,
        base: Option<&Value>,
        changed: &[&str],
        clock: &SheetClock,
        fresh_id: &str,
    ) -> EngineResult<Value> {
        let mut body = if let Some(base) = base {
            base.clone()
        } else {
            let mut copied = object_owned(made)?;
            copied.shift_remove("missed_days");
            copied.shift_remove("removed_days");
            let days = week_to_monday(&self.days, &clock.first_weekday)?;
            copied.insert("days".into(), json!(days));
            let id = if self.existing {
                py_str(require(made, "id")?)
            } else {
                fresh_id.to_string()
            };
            copied.insert("id".into(), Value::from(format!("{WEEKLY_PREFIX}{id}")));
            Value::Object(copied)
        };
        if base.is_some() {
            let fields = object_mut(&mut body)?;
            if changed.contains(&"title") {
                fields.insert("title".into(), require(made, "title")?.clone());
            }
            if changed.contains(&"days") {
                let opened = week_to_monday(&self.opened.days, &clock.first_weekday)?;
                let now = week_to_monday(&self.days, &clock.first_weekday)?;
                let current = match fields.get("days") {
                    Some(value) if truthy(Some(value)) => ints_of(&iterate(value)?)?,
                    _ => Vec::new(),
                };
                let opened_set: BTreeSet<i64> = opened.into_iter().collect();
                let now_set: BTreeSet<i64> = now.into_iter().collect();
                let removed: BTreeSet<i64> = opened_set.difference(&now_set).copied().collect();
                let added: BTreeSet<i64> = now_set.difference(&opened_set).copied().collect();
                let mut next: BTreeSet<i64> = current.into_iter().collect();
                next.retain(|day| !removed.contains(day));
                next.extend(added);
                fields.insert("days".into(), json!(next.into_iter().collect::<Vec<_>>()));
            }
            if changed.contains(&"start") || changed.contains(&"end") {
                fields.insert("start".into(), require(made, "start")?.clone());
                fields.insert(
                    "duration_min".into(),
                    require(made, "duration_min")?.clone(),
                );
            }
            if changed.contains(&"category") {
                fields.insert(
                    "category".into(),
                    py_get(made, "category")?.cloned().unwrap_or(Value::Null),
                );
            }
        }
        if let Some(until) = &self.until {
            object_mut(&mut body)?.insert("until".into(), Value::from(until.clone()));
        } else if let Value::Object(fields) = &mut body {
            fields.shift_remove("until");
        }
        check_block(&body).map_err(|refused| EngineError::value(refused.0))
    }

    fn occurrence_stamp(&self, clock: &SheetClock) -> EngineResult<Stamp> {
        let day = self.occurrence_day.unwrap_or(0);
        let week = match &clock.week_start {
            Value::String(text) => text.clone(),
            _ => grid::monday_of(&clock.today)?,
        };
        let iso = date_for_day(&week, &Value::from(day))?;
        Ok(Stamp {
            day_name: full_day_name(&week, day)?,
            day: month_day(&iso)?,
            month: month_short(&iso)?.to_string(),
        })
    }

    fn clear_moves(&mut self) {
        self.moved_from.clear();
        self.moved_to.clear();
        self.moved_note.clear();
    }
}

struct Stamp {
    day_name: String,
    day: i64,
    month: String,
}

fn moved_sentence(end: i64, kept: i64, length: i64) -> String {
    let end_words = clock_text(end);
    if end == DAY_END && kept < length {
        format!(
            "End moved to the end of the day ({end_words}). It's now {}, not {}.",
            length_label(kept),
            length_label(length)
        )
    } else {
        format!(
            "End moved to {end_words} to keep it {}.",
            length_label(kept)
        )
    }
}

fn store_clock(minute: i64) -> String {
    format!("{:02}:{:02}", minute.div_euclid(60), minute.rem_euclid(60))
}

/// `str.strip()` with no argument: Unicode white space and the four separator controls.
fn python_strip(text: &str) -> &str {
    text.trim_matches(|ch: char| ch.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&ch))
}

fn active_days_of(original: &Value) -> EngineResult<Vec<i64>> {
    let days = ints_of(&iterate(require(original, "days")?)?)?;
    let removed = optional_day_numbers(original, "removed_days")?;
    let mut kept = Vec::new();
    for day in days {
        if !removed.contains(&day) {
            kept.push(day);
        }
    }
    kept.sort();
    Ok(kept)
}

fn optional_day_numbers(value: &Value, key: &str) -> EngineResult<Vec<i64>> {
    match py_get(value, key)? {
        Some(item) if truthy(Some(item)) => ints_of(&iterate(item)?),
        _ => Ok(Vec::new()),
    }
}

fn missed_flag(original: &Value, occurrence: Option<i64>) -> EngineResult<bool> {
    let missed = match py_get(original, "missed_days")? {
        Some(value) if truthy(Some(value)) => value.clone(),
        _ => json!([]),
    };
    let needle = match occurrence {
        Some(day) => Value::from(day),
        None => Value::Null,
    };
    contains(&missed, &needle)
}

fn find_repeat(repeats: &Value, family: &str) -> EngineResult<Option<Value>> {
    for repeat in iterate(repeats)? {
        if eq(require(&repeat, "id")?, &Value::from(family)) {
            return Ok(Some(repeat));
        }
    }
    Ok(None)
}

fn until_of(repeat: Option<&Value>) -> EngineResult<Option<String>> {
    let Some(repeat) = repeat else {
        return Ok(None);
    };
    match py_get(repeat, "until")? {
        Some(value) if truthy(Some(value)) => Ok(Some(py_str(value))),
        _ => Ok(None),
    }
}

fn week_to_monday(days: &[i64], first_weekday: &Value) -> EngineResult<Vec<i64>> {
    let first = int_or_zero(Some(first_weekday))?;
    let mut turned: Vec<i64> = days.iter().map(|day| (first + day).rem_euclid(7)).collect();
    turned.sort();
    Ok(turned)
}

fn chosen_step(preferences: &Value) -> EngineResult<i64> {
    // A JSON number with a decimal point is a float, and Python's `int` check rejects it.
    if !truthy(Some(preferences)) {
        return Ok(DEFAULT_DRAG_STEP);
    }
    let chosen = match dict(preferences)?.get("drag_step_min") {
        Some(chosen) if is_json_int(chosen) => Some(py_int(chosen)?),
        _ => None,
    };
    Ok(drag_step(chosen))
}

fn is_json_int(value: &Value) -> bool {
    match value {
        Value::Number(number) => !number.to_string().contains(['.', 'e', 'E']),
        _ => false,
    }
}

fn week_value(week_start: &Value) -> Value {
    if truthy(Some(week_start)) {
        week_start.clone()
    } else {
        Value::from("")
    }
}

fn week_text(week: &Value) -> EngineResult<String> {
    match week {
        Value::String(text) => Ok(text.clone()),
        other => Err(type_error(format!(
            "fromisoformat: argument must be str, not '{}'",
            type_name(other)
        ))),
    }
}

fn shown_week(week_start: &Value) -> String {
    match week_start {
        Value::String(text) => text.clone(),
        _ => String::new(),
    }
}

fn string_week(week_start: &Value) -> Option<String> {
    match week_start {
        Value::String(text) => Some(text.clone()),
        _ => None,
    }
}

fn chip_week(week_start: &Value) -> EngineResult<Option<String>> {
    if !truthy(Some(week_start)) {
        return Ok(None);
    }
    match week_start {
        Value::String(text) => Ok(Some(text.clone())),
        other => Err(type_error(format!(
            "fromisoformat: argument must be str, not '{}'",
            type_name(other)
        ))),
    }
}

fn month_day(iso: &str) -> EngineResult<i64> {
    iso.get(8..10)
        .and_then(|text| text.parse().ok())
        .ok_or_else(|| EngineError::value(format!("Invalid isoformat string: {iso}")))
}

fn month_short(iso: &str) -> EngineResult<&'static str> {
    let month = iso
        .get(5..7)
        .and_then(|text| text.parse::<usize>().ok())
        .ok_or_else(|| EngineError::value(format!("Invalid isoformat string: {iso}")))?;
    MONTHS_SHORT
        .get(month.wrapping_sub(1))
        .copied()
        .ok_or_else(|| EngineError::value(format!("Invalid isoformat string: {iso}")))
}

fn shown_name(original: &Value, preferred: Option<&str>) -> EngineResult<String> {
    if let Some(text) = preferred
        && !text.is_empty()
    {
        return Ok(text.to_string());
    }
    match py_get(original, "title")? {
        Some(value) if truthy(Some(value)) => Ok(py_str(value)),
        _ => Ok("this fixed time".to_string()),
    }
}

fn filter_missed(
    missed: &[Value],
    days: &Value,
    restored: Option<&Value>,
) -> EngineResult<Vec<Value>> {
    let mut kept = Vec::new();
    for day in missed {
        if !contains(days, day)? {
            continue;
        }
        if restored.is_some_and(|restored| eq(day, restored)) {
            continue;
        }
        kept.push(day.clone());
    }
    Ok(kept)
}

fn same_picture(left: &Picture, right: &Picture) -> bool {
    left.title == right.title
        && left.days == right.days
        && left.start == right.start
        && left.end == right.end
        && left.category == right.category
        && left.scope == right.scope
        && left.missed == right.missed
        && left.weekly == right.weekly
        && left.until == right.until
}

fn picture_value(picture: &Picture) -> Value {
    json!({
        "title": picture.title,
        "days": picture.days,
        "start": picture.start,
        "end": picture.end,
        "category": picture.category,
        "scope": picture.scope,
        "missed": picture.missed,
        "weekly": picture.weekly,
        "until": picture.until,
    })
}

fn picture_from(value: &Value) -> EngineResult<Picture> {
    let map = as_map(value)?;
    Ok(Picture {
        title: text_field(map, "title")?,
        days: ints_of(
            need(map, "days")?
                .as_array()
                .ok_or_else(|| EngineError::key("days"))?,
        )?,
        start: py_int(need(map, "start")?)?,
        end: py_int(need(map, "end")?)?,
        category: opt_text(map, "category")?,
        scope: text_field(map, "scope")?,
        missed: bool_field(map, "missed")?,
        weekly: bool_field(map, "weekly")?,
        until: opt_text(map, "until")?,
    })
}

fn pair_values(pairs: &[(i64, String)]) -> Value {
    Value::Array(pairs.iter().map(|(day, text)| json!([day, text])).collect())
}

fn pairs_from(value: &Value) -> EngineResult<Vec<(i64, String)>> {
    let mut pairs = Vec::new();
    for item in iterate(value)? {
        let Some(pair) = item.as_array() else {
            return Err(type_error("a moved day must be a pair"));
        };
        if pair.len() != 2 {
            return Err(type_error("a moved day must be a pair"));
        }
        let Some(text) = pair[1].as_str() else {
            return Err(type_error("a moved name must be text"));
        };
        pairs.push((py_int(&pair[0])?, text.to_string()));
    }
    Ok(pairs)
}

fn ints_of(days: &[Value]) -> EngineResult<Vec<i64>> {
    days.iter().map(py_int).collect()
}

fn sorted_ints(mut days: Vec<i64>) -> Vec<i64> {
    days.sort();
    days
}

fn unique_values(days: Vec<Value>) -> Vec<Value> {
    let mut unique = Vec::new();
    for day in days {
        if !unique.iter().any(|held| eq(held, &day)) {
            unique.push(day);
        }
    }
    unique
}

fn sorted_values(days: Vec<Value>) -> EngineResult<Vec<Value>> {
    let mut keyed = Vec::new();
    for (index, day) in days.into_iter().enumerate() {
        keyed.push((py_int(&day)?, index, day));
    }
    keyed.sort_by(|left, right| left.0.cmp(&right.0).then(left.1.cmp(&right.1)));
    Ok(keyed.into_iter().map(|(_, _, day)| day).collect())
}

fn upsert_pair(rows: &mut Vec<(i64, (String, String))>, key: i64, value: (String, String)) {
    if let Some(found) = rows.iter_mut().find(|(held, _)| *held == key) {
        found.1 = value;
    } else {
        rows.push((key, value));
    }
}

fn upsert_text(rows: &mut Vec<(i64, String)>, key: i64, value: String) {
    if let Some(found) = rows.iter_mut().find(|(held, _)| *held == key) {
        found.1 = value;
    } else {
        rows.push((key, value));
    }
}

fn moved_text(rows: &[(i64, String)], day: i64) -> &str {
    rows.iter()
        .find(|(held, _)| *held == day)
        .map(|(_, text)| text.as_str())
        .unwrap_or("")
}

fn as_map(value: &Value) -> EngineResult<&Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| stored::attribute_error(value, "get"))
}

fn object_mut(value: &mut Value) -> EngineResult<&mut Map<String, Value>> {
    if !value.is_object() {
        let message = format!("'{}' object has no attribute 'get'", type_name(value));
        return Err(EngineError {
            kind: ErrorKind::Attribute,
            message,
        });
    }
    Ok(value.as_object_mut().expect("object"))
}

fn object_owned(value: &Value) -> EngineResult<Map<String, Value>> {
    value
        .as_object()
        .cloned()
        .ok_or_else(|| stored::attribute_error(value, "get"))
}

fn need<'a>(map: &'a Map<String, Value>, key: &str) -> EngineResult<&'a Value> {
    map.get(key).ok_or_else(|| EngineError::key(key))
}

fn require<'a>(value: &'a Value, key: &str) -> EngineResult<&'a Value> {
    match py_get(value, key)? {
        Some(item) => Ok(item),
        None => Err(EngineError::key(key)),
    }
}

fn text_field(map: &Map<String, Value>, key: &str) -> EngineResult<String> {
    match need(map, key)? {
        Value::String(text) => Ok(text.clone()),
        other => Err(type_error(format!(
            "{key} must be text, not '{}'",
            type_name(other)
        ))),
    }
}

fn bool_field(map: &Map<String, Value>, key: &str) -> EngineResult<bool> {
    match need(map, key)? {
        Value::Bool(flag) => Ok(*flag),
        other => Err(type_error(format!(
            "{key} must be true or false, not '{}'",
            type_name(other)
        ))),
    }
}

fn opt_text(map: &Map<String, Value>, key: &str) -> EngineResult<Option<String>> {
    match need(map, key)? {
        Value::Null => Ok(None),
        Value::String(text) => Ok(Some(text.clone())),
        other => Err(type_error(format!(
            "{key} must be text, not '{}'",
            type_name(other)
        ))),
    }
}

fn opt_int(map: &Map<String, Value>, key: &str) -> EngineResult<Option<i64>> {
    match need(map, key)? {
        Value::Null => Ok(None),
        value => Ok(Some(py_int(value)?)),
    }
}

fn opt_days(map: &Map<String, Value>, key: &str) -> EngineResult<Option<Vec<i64>>> {
    match need(map, key)? {
        Value::Null => Ok(None),
        Value::Array(items) => Ok(Some(ints_of(items)?)),
        other => Err(type_error(format!(
            "{key} must be a list, not '{}'",
            type_name(other)
        ))),
    }
}

fn opt_clone(map: &Map<String, Value>, key: &str) -> EngineResult<Option<Value>> {
    match need(map, key)? {
        Value::Null => Ok(None),
        value => Ok(Some(value.clone())),
    }
}

fn type_error(message: impl Into<String>) -> EngineError {
    EngineError {
        kind: ErrorKind::Type,
        message: message.into(),
    }
}

/// `value.get(key)`. Only a dict has `get`.
fn py_get<'a>(value: &'a Value, key: &str) -> EngineResult<Option<&'a Value>> {
    Ok(dict(value)?.get(key))
}

/// `for item in value`: a list's items, a string's characters, a dict's keys.
fn iterate(value: &Value) -> EngineResult<Vec<Value>> {
    match value {
        Value::Array(items) => Ok(items.clone()),
        Value::String(text) => Ok(text.chars().map(|ch| Value::from(ch.to_string())).collect()),
        Value::Object(map) => Ok(map.keys().cloned().map(Value::String).collect()),
        other => Err(type_error(format!(
            "'{}' object is not iterable",
            type_name(other)
        ))),
    }
}

/// `item in container` for the lists this sheet walks.
fn contains(container: &Value, item: &Value) -> EngineResult<bool> {
    match container {
        Value::Array(items) => Ok(items.iter().any(|held| eq(held, item))),
        Value::String(text) => match item {
            Value::String(part) => Ok(text.contains(part.as_str())),
            other => Err(type_error(format!(
                "'in <string>' requires string as left operand, not {}",
                type_name(other)
            ))),
        },
        Value::Object(map) => match item {
            Value::String(key) => Ok(map.contains_key(key)),
            other => Err(type_error(format!(
                "unhashable type: '{}'",
                type_name(other)
            ))),
        },
        other => Err(type_error(format!(
            "argument of type '{}' is not a container or iterable",
            type_name(other)
        ))),
    }
}

/// Python `==`, including `True == 1` and `1 == 1.0`.
fn eq(left: &Value, right: &Value) -> bool {
    match (as_number(left), as_number(right)) {
        (Some(left), Some(right)) => numbers_equal(left, right),
        (Some(_), None) | (None, Some(_)) => false,
        (None, None) => match (left, right) {
            (Value::Null, Value::Null) => true,
            (Value::String(left), Value::String(right)) => left == right,
            (Value::Array(left), Value::Array(right)) => {
                left.len() == right.len()
                    && left.iter().zip(right).all(|(left, right)| eq(left, right))
            }
            (Value::Object(left), Value::Object(right)) => {
                left.len() == right.len()
                    && left
                        .iter()
                        .all(|(key, value)| right.get(key).is_some_and(|other| eq(value, other)))
            }
            _ => false,
        },
    }
}

enum Num {
    Int(i128),
    Big(String),
    Float(f64),
}

fn as_number(value: &Value) -> Option<Num> {
    if let Some(float) = stored::nonfinite(value) {
        return Some(Num::Float(float));
    }
    match value {
        Value::Bool(flag) => Some(Num::Int(i128::from(*flag))),
        Value::Number(number) => {
            let text = number.to_string();
            if text.contains(['.', 'e', 'E']) {
                Some(Num::Float(text.parse().unwrap_or(f64::NAN)))
            } else {
                Some(text.parse::<i128>().map_or(Num::Big(text), Num::Int))
            }
        }
        _ => None,
    }
}

fn numbers_equal(left: Num, right: Num) -> bool {
    match (left, right) {
        (Num::Int(left), Num::Int(right)) => left == right,
        (Num::Big(left), Num::Big(right)) => left == right,
        (Num::Float(left), Num::Float(right)) => left == right,
        (Num::Int(left), Num::Float(right)) | (Num::Float(right), Num::Int(left)) => {
            (left as f64) == right
        }
        (Num::Big(left), Num::Float(right)) | (Num::Float(right), Num::Big(left)) => {
            left.parse::<f64>().is_ok_and(|left| left == right)
        }
        _ => false,
    }
}
