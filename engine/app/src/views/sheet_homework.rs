//! The Add and Edit homework sheet: what the student typed, and what saving it means.
//!
//! Moved from `desktop/native/material/sheet_homework.py`. The words and rules are the Widgets
//! sheet's, so the same input gets the same answer in either surface. Nothing here reads a clock,
//! draws an id or asks the operating system: the caller passes the clock reading, fresh ids and what
//! the open session knows (`Env`) in.

use flexweek_engine::desk::calendar::DAYS;
use flexweek_engine::desk::datetext::day_of;
use flexweek_engine::desk::grid::{
    date_for_day, monday_of, past_problem, span_problem, sunday_due,
};
use flexweek_engine::desk::planning::due_point;
use flexweek_engine::desk::weekmodel::{clock_text, due_label_text, hhmm_text, length_label};
use flexweek_engine::model::{ESTIMATE_MAX_MIN, parse_due};
use flexweek_engine::plan::{
    SPREAD_MIN, parse_moment, spread_session_min, spread_sessions, unplanned_minutes,
};
use flexweek_engine::shown::day_names;
use flexweek_engine::stored::{py_int, py_str, truthy};
use flexweek_engine::time::{SLOT_MIN, hhmm_to_minutes};
use flexweek_engine::{EngineError, EngineResult};
use serde_json::{Map, Value, json};

use crate::session::sheet_check::homework_sheet_problem;
use crate::session::views::today_column;
use crate::views::hours::drag_step;
use crate::views::sheet_rules::{
    DUE_PASSED, ESTIMATE_LONG, ESTIMATE_SHORT, SLOT_HINT, first_day_changed, moved_across_months,
    moved_day_names, moved_days_note, same_weekday, spread_words, today_from_words,
    turn_days_keeping_weekdays,
};

pub const STEPS: [&str; 3] = ["What", "When", "How long"];
pub const PROMPTS: [&str; 3] = ["What is it?", "When is it due?", "How long will it take?"];
pub const TITLE_PROBLEM: &str = "Give the homework a title.";
pub const TYPES: [(i64, &str); 4] = [
    (1, "Test prep"),
    (2, "Quiz prep"),
    (3, "Everyday homework"),
    (4, "Reading"),
];
pub const ENERGIES: [(&str, &str); 3] = [
    ("high", "Morning"),
    ("medium", "Afternoon"),
    ("low", "Evening"),
];
pub const WHEN_CHOICES: [(&str, &str); 2] = [
    ("plan", "FlexWeek picks the time"),
    ("fixed", "Choose a time myself"),
];
pub const SPREAD_CHOICES: [(&str, &str); 2] =
    [("one", "In one go"), ("spread", "Spread over days")];
pub const DAYS_AHEAD: i64 = 28;
pub const QUICK_LENGTHS: [i64; 5] = [15, 30, 45, 60, 90];
const LINKS_MAX: usize = 20;
const CHECKS_MAX: usize = 40;
const FLEX_CATEGORIES: [&str; 2] = ["assignments", "study"];
// Both flexible categories preset an hour.
const PRESET_MIN: i64 = 60;
const MONTHS: [&str; 12] = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/// The session's figure for the minutes of a homework ticked done, by the homework's id.
pub type DoneFor<'a> = &'a dyn Fn(&Value) -> EngineResult<i64>;

/// What the open session knows that the sheet judges against. Passed in on every call, because a
/// sheet kept after Esc outlives the week it was built in.
pub struct Env<'a> {
    pub week_start: Option<&'a str>,
    pub blocks: &'a [Value],
    pub preferences: &'a Value,
    pub selected_day: &'a str,
    /// Minutes of this homework ticked done. Called only when a spread needs the figure.
    pub done_minutes_for: Option<DoneFor<'a>>,
}

#[derive(Default)]
pub struct OpenOptions {
    pub category: Option<String>,
    pub due: Option<String>,
    pub when: Option<String>,
    pub when_day: Option<i64>,
    pub when_time: Option<String>,
    pub day: Option<i64>,
    pub start_min: Option<i64>,
    pub end_min: Option<i64>,
    pub estimate_min: Option<i64>,
}

#[derive(Clone, PartialEq)]
struct Picture {
    title: String,
    due_date: String,
    due_time: String,
    estimate_text: String,
    when: String,
    when_day: i64,
    when_time: String,
    spread: String,
    course: String,
    priority: i64,
    energy: String,
    notes: String,
    completed: bool,
    links: Vec<(String, String)>,
    checklist: Vec<(String, bool)>,
}

pub struct HomeworkDraft {
    stamp: String,
    today: String,
    minute_now: i64,
    existing: bool,
    day_given: bool,
    day_touched: bool,
    original: Map<String, Value>,
    step: Option<i64>,
    title: String,
    due_date: String,
    due_time: String,
    estimate_text: String,
    spread: String,
    completed: bool,
    course: String,
    priority: i64,
    energy: String,
    notes: String,
    links: Vec<Value>,
    checklist: Vec<Value>,
    link_label: String,
    link_url: String,
    check_text: String,
    details_open: bool,
    placed: Option<(i64, String)>,
    spread_out: bool,
    when: String,
    when_day: i64,
    when_time: String,
    pinned_session: bool,
    title_problem: String,
    due_problem: String,
    when_problem: String,
    estimate_problem: String,
    error: String,
    details_error: String,
    opened_as: Picture,
    days_week: String,
    moved_from: String,
    moved_to: String,
    moved_note: String,
}

fn type_error(message: impl Into<String>) -> EngineError {
    EngineError {
        kind: flexweek_engine::ErrorKind::Type,
        message: message.into(),
    }
}

fn required<'a>(map: &'a Map<String, Value>, key: &str) -> EngineResult<&'a Value> {
    map.get(key).ok_or_else(|| EngineError::key(key))
}

fn text_of(value: &Value, what: &str) -> EngineResult<String> {
    value
        .as_str()
        .map(str::to_string)
        .ok_or_else(|| type_error(format!("{what} must be text")))
}

fn text_or(map: &Map<String, Value>, key: &str, default: &str) -> String {
    match map.get(key) {
        Some(Value::Null) | None => default.to_string(),
        Some(value) => py_str(value),
    }
}

fn hhmm(minute: i64) -> String {
    format!("{:02}:{:02}", minute.div_euclid(60), minute.rem_euclid(60))
}

fn name_at<T: Clone>(names: &[T], index: i64) -> EngineResult<T> {
    let len = i64::try_from(names.len()).unwrap_or(i64::MAX);
    let at = if index < 0 { index + len } else { index };
    usize::try_from(at)
        .ok()
        .and_then(|found| names.get(found))
        .cloned()
        .ok_or_else(|| EngineError::index("tuple index out of range"))
}

fn civil(iso: &str) -> EngineResult<(i64, usize, i64)> {
    let text = day_of(iso)?.to_string();
    let part = |from: usize, to: usize| {
        text.get(from..to)
            .and_then(|digits| digits.parse::<i64>().ok())
            .ok_or_else(|| EngineError::value(format!("Invalid isoformat string: {iso:?}")))
    };
    let month = usize::try_from(part(5, 7)?).unwrap_or(1);
    Ok((part(0, 4)?, month, part(8, 10)?))
}

fn day_number(iso: &str) -> EngineResult<i64> {
    Ok(civil(iso)?.2)
}

/// Monday is 0, as `date.weekday()` counts.
fn weekday_of(iso: &str) -> EngineResult<usize> {
    const OFFSETS: [i64; 12] = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4];
    let (year, month, day) = civil(iso)?;
    let year = if month < 3 { year - 1 } else { year };
    let sunday_first = (year + year / 4 - year / 100 + year / 400 + OFFSETS[month - 1] + day) % 7;
    Ok(usize::try_from((sunday_first + 6) % 7).unwrap_or(0))
}

fn normal(iso: &str) -> EngineResult<String> {
    Ok(day_of(iso)?.to_string())
}

fn add_days(iso: &str, count: i64) -> EngineResult<String> {
    date_for_day(iso, &json!(count))
}

fn quarter_hours_of(step: i64) -> EngineResult<Vec<Value>> {
    if step <= 0 {
        return Err(EngineError::value("range() arg 3 must not be zero"));
    }
    let mut marks = Vec::new();
    let mut minute = 0;
    while minute < 24 * 60 {
        marks.push(json!({"value": hhmm(minute), "label": clock_text(minute)}));
        minute += step;
    }
    Ok(marks)
}

/// Every mark of the day's time step (quarter hours on 15), as the clock is written.
pub fn quarter_hours(step: i64) -> EngineResult<Value> {
    Ok(Value::Array(quarter_hours_of(step)?))
}

fn pairs(rows: &[(&str, &str)]) -> Value {
    Value::Array(
        rows.iter()
            .map(|(value, label)| json!({"value": value, "label": label}))
            .collect(),
    )
}

fn drag_step_of(env: &Env) -> i64 {
    let chosen = env
        .preferences
        .get("drag_step_min")
        .filter(|value| value.is_i64())
        .and_then(Value::as_i64);
    drag_step(chosen)
}

fn today_column_of(today: &str, env: &Env) -> EngineResult<Option<i64>> {
    match env.week_start {
        Some(week) if !week.is_empty() => Ok(today_column(today, week)),
        _ => Ok(Some(i64::try_from(weekday_of(today)?).unwrap_or(0))),
    }
}

fn open_sessions_of<'a>(env: &'a Env, id: &Value) -> Vec<&'a Value> {
    env.blocks
        .iter()
        .filter(|block| block.get("assignment_id") == Some(id) && !truthy(block.get("completed")))
        .collect()
}

fn first_day_of(block: &Value) -> EngineResult<i64> {
    let days = block.get("days").ok_or_else(|| EngineError::key("days"))?;
    let first = days
        .as_array()
        .and_then(|list| list.first())
        .ok_or_else(|| EngineError::index("list index out of range"))?;
    py_int(first)
}

impl HomeworkDraft {
    /// A new sheet. `fresh_id` becomes the id of a new homework; an edit keeps its own.
    pub fn open(
        env: &Env,
        stamp: &str,
        fresh_id: &str,
        assignment: Option<&Value>,
        options: &OpenOptions,
    ) -> EngineResult<Self> {
        let (today, minute_now) = clock_of(stamp)?;
        let existing = assignment.is_some();
        let day_given = options.when_day.is_some() || options.day.is_some();
        let category = match options.category.as_deref() {
            Some(found) if FLEX_CATEGORIES.contains(&found) => found.to_string(),
            _ => "assignments".to_string(),
        };
        let when_day = options.when_day.or(options.day);
        let when_time = match (&options.when_time, options.start_min) {
            (None, Some(start)) => Some(hhmm(start)),
            (given, _) => given.clone(),
        };
        let estimate_min = match (options.estimate_min, options.start_min, options.end_min) {
            (None, Some(start), Some(end)) => Some(end - start),
            (given, _, _) => given,
        };
        let pins = when_day.is_some() || when_time.is_some() || options.start_min.is_some();
        let when = match &options.when {
            None if pins => Some("fixed".to_string()),
            given => given.clone(),
        };
        let week_open = env.week_start.filter(|week| !week.is_empty());
        let due = match (&options.due, week_open) {
            (None, Some(week)) if when_day.is_some() => Some(sunday_due(week)?),
            (given, _) => given.clone(),
        };
        let original = match assignment {
            Some(found) => found
                .as_object()
                .cloned()
                .ok_or_else(|| type_error("an assignment must be an object"))?,
            None => {
                let tomorrow = add_days(&today, 1)?;
                let due = due
                    .filter(|text| !text.is_empty())
                    .unwrap_or_else(|| format!("{tomorrow}T23:59"));
                let estimate = estimate_min.unwrap_or(PRESET_MIN);
                let mut made = Map::new();
                made.insert("id".into(), json!(fresh_id));
                made.insert("title".into(), json!(""));
                made.insert("due".into(), json!(due));
                made.insert("estimate_min".into(), json!(estimate));
                made.insert("category".into(), json!(category));
                made.insert("revision".into(), json!(0));
                made.insert("notes".into(), json!(""));
                made.insert("links".into(), json!([]));
                made.insert("checklist".into(), json!([]));
                made.insert("completed".into(), json!(false));
                made.insert("completed_at".into(), Value::Null);
                made
            }
        };
        let due_text = py_str(required(&original, "due")?);
        let due_chars: Vec<char> = due_text.chars().collect();
        let clock: String = due_chars.iter().skip(11).take(5).collect();
        let due_time = if due_chars.len() >= 16 && clock != "23:59" {
            clock
        } else {
            String::new()
        };
        let title = text_of(required(&original, "title")?, "title")?;
        let links = list_of(&original, "links");
        let checklist = list_of(&original, "checklist");
        let course = text_or(&original, "course", "");
        let notes = text_or(&original, "notes", "");
        let id = required(&original, "id")?.clone();
        let sessions = open_sessions_of(env, &id);
        let pinned = sessions
            .iter()
            .find(|item| truthy(item.get("pinned")) && truthy(item.get("start")))
            .copied();
        let placed = match pinned {
            Some(block) => Some((
                first_day_of(block)?,
                text_of(required_in(block, "start")?, "start")?,
            )),
            None => None,
        };
        let mut this = Self {
            stamp: stamp.to_string(),
            today,
            minute_now,
            existing,
            day_given,
            day_touched: false,
            step: if existing { None } else { Some(0) },
            title,
            due_date: due_chars.iter().take(10).collect(),
            due_time,
            estimate_text: py_str(required(&original, "estimate_min")?),
            spread: text_or(&original, "spread", "one"),
            completed: truthy(original.get("completed")),
            details_open: !course.is_empty()
                || !notes.is_empty()
                || !links.is_empty()
                || !checklist.is_empty(),
            course,
            priority: original.get("priority").map_or(Ok(3), py_int)?,
            energy: text_or(&original, "energy", "medium"),
            notes,
            links,
            checklist,
            link_label: String::new(),
            link_url: String::new(),
            check_text: String::new(),
            spread_out: sessions.len() > 1,
            pinned_session: pinned.is_some(),
            placed,
            when: String::new(),
            when_day: 0,
            when_time: String::new(),
            title_problem: String::new(),
            due_problem: String::new(),
            when_problem: String::new(),
            estimate_problem: String::new(),
            error: String::new(),
            details_error: String::new(),
            opened_as: Picture::blank(),
            days_week: env.week_start.unwrap_or_default().to_string(),
            moved_from: String::new(),
            moved_to: String::new(),
            moved_note: String::new(),
            original,
        };
        let (default_day, default_start) = this.default_placement(env)?;
        let (default_day, default_start) = match &this.placed {
            Some((day, start)) => (*day, hhmm_to_minutes(start)?),
            None => (default_day, default_start),
        };
        this.when = when.unwrap_or_else(|| {
            if this.placed.is_some() {
                "fixed"
            } else {
                "plan"
            }
            .to_string()
        });
        this.when_day = when_day.unwrap_or(default_day);
        this.when_time = when_time.unwrap_or_else(|| hhmm(default_start));
        this.opened_as = this.picture()?;
        Ok(this)
    }

    /// The clock now: a sheet kept while the student was away judges a picked time by the time it is
    /// when it opens again, not by the time it was first built.
    pub fn read_clock(&mut self, stamp: &str) -> EngineResult<()> {
        let (today, minute_now) = clock_of(stamp)?;
        self.stamp = stamp.to_string();
        self.today = today;
        self.minute_now = minute_now;
        Ok(())
    }

    /// A new sheet kept after Esc and opened again in a week that starts on another day: a pinned day
    /// the student picked, and the one it opened with, keep their weekday. A pin whose date changed is
    /// remembered, so the row can name it until the student picks another day. A day still as the app
    /// put it when the sheet opened is picked again for this week, `fresh_day` as a fresh sheet has it,
    /// with no mark.
    pub fn follow_week(&mut self, env: &Env, fresh_day: i64) -> EngineResult<()> {
        let week = env.week_start.unwrap_or_default().to_string();
        let from_week = self.days_week.clone();
        if first_day_changed(&from_week, &week)? && !self.day_given && !self.day_touched {
            self.opened_as.when_day = fresh_day;
            self.when_day = fresh_day;
            self.days_week = week;
            self.moved_from.clear();
            self.moved_to.clear();
            self.moved_note.clear();
            return Ok(());
        }
        let (turned, moved) = turn_days_keeping_weekdays(&[self.when_day], &from_week, &week)?;
        let names = match moved.first() {
            Some((old, new)) => Some(moved_day_names(*old, &from_week, *new, &week)?),
            None => None,
        };
        self.moved_from = names
            .as_ref()
            .map(|pair| pair.0.clone())
            .unwrap_or_default();
        self.moved_to = match (&names, moved.first()) {
            (Some(pair), Some((old, new)))
                if moved_across_months(*old, &from_week, *new, &week)? =>
            {
                pair.1.clone()
            }
            _ => String::new(),
        };
        self.moved_note = match names {
            Some(pair) => moved_days_note(&[pair]),
            None => String::new(),
        };
        self.opened_as.when_day = same_weekday(self.opened_as.when_day, &from_week, &week)?;
        self.when_day = name_at(&turned, 0)?;
        self.days_week = week;
        Ok(())
    }

    fn moved_access(&self) -> String {
        if self.moved_to.is_empty() {
            format!("Day, moved from {}", self.moved_from)
        } else {
            format!("Day, moved from {} to {}", self.moved_from, self.moved_to)
        }
    }

    // What is open ---------------------------------------------------------------------------

    fn open_sessions<'a>(&self, env: &'a Env) -> Vec<&'a Value> {
        let id = self.original.get("id").cloned().unwrap_or(Value::Null);
        open_sessions_of(env, &id)
    }

    /// Today if the week on screen has it, else its first day, at 16:00 or the next quarter hour
    /// after it.
    fn default_placement(&self, env: &Env) -> EngineResult<(i64, i64)> {
        let Some(column) = today_column_of(&self.today, env)? else {
            return Ok((0, 16 * 60));
        };
        let quarter = self.minute_now / 15 * 15 + 15;
        Ok((column, quarter.clamp(16 * 60, 23 * 60 + 45)))
    }

    fn picture(&self) -> EngineResult<Picture> {
        let mut links = Vec::new();
        for item in &self.links {
            let label = py_str(required_in(item, "label")?);
            links.push((label, py_str(required_in(item, "url")?)));
        }
        let mut checklist = Vec::new();
        for item in &self.checklist {
            let text = py_str(required_in(item, "text")?);
            checklist.push((text, truthy(Some(required_in(item, "done")?))));
        }
        Ok(Picture {
            title: self.title.clone(),
            due_date: self.due_date.clone(),
            due_time: self.due_time.clone(),
            estimate_text: self.estimate_text.clone(),
            when: self.when.clone(),
            when_day: self.when_day,
            when_time: self.when_time.clone(),
            spread: self.spread.clone(),
            course: self.course.clone(),
            priority: self.priority,
            energy: self.energy.clone(),
            notes: self.notes.clone(),
            completed: self.completed,
            links,
            checklist,
        })
    }

    /// Whether there is typed work that closing would lose.
    pub fn dirty(&self) -> EngineResult<bool> {
        Ok(self.picture()? != self.opened_as)
    }

    // Values ---------------------------------------------------------------------------------

    pub fn estimate(&self) -> i64 {
        let text = self.estimate_text.trim();
        if !text.is_empty() && text.chars().all(|ch| ch.is_ascii_digit()) {
            return text.parse().unwrap_or(i64::MAX);
        }
        0
    }

    /// The due as the student left it. An old 23:59 that still means the same end of day is kept as
    /// it was stored, so opening and saving changes nothing.
    pub fn chosen_due(&self) -> String {
        let end = "23:59";
        let clock = if self.due_time.is_empty() {
            end
        } else {
            &self.due_time
        };
        let chosen = format!("{}T{clock}", self.due_date);
        let before = self.original.get("due").map(py_str).unwrap_or_default();
        match (parse_due(&chosen), parse_due(&before)) {
            (Ok(now), Ok(then)) if now == then => before,
            _ => chosen,
        }
    }

    fn fixed_at(&self) -> Option<(i64, String)> {
        (self.when == "fixed").then(|| (self.when_day, self.when_time.clone()))
    }

    fn when_changed(&self) -> bool {
        if self.spread_out {
            return false;
        }
        match (self.fixed_at(), &self.placed) {
            (None, placed) => placed.is_some(),
            (Some(_), None) => true,
            (Some(fixed), Some(placed)) => fixed != *placed,
        }
    }

    fn length_problem(&self) -> &'static str {
        let minutes = self.estimate();
        if minutes < SLOT_MIN {
            return ESTIMATE_SHORT;
        }
        if minutes > ESTIMATE_MAX_MIN {
            return ESTIMATE_LONG;
        }
        if minutes % SLOT_MIN != 0 {
            SLOT_HINT
        } else {
            ""
        }
    }

    /// A deadline the student set that is already over. A saved one they did not change is left alone,
    /// and so is finished homework, so old work can still be edited.
    fn due_passed(&self) -> bool {
        if self.completed {
            return false;
        }
        let chosen = self.chosen_due();
        if self.original.get("due") == Some(&Value::String(chosen.clone())) {
            return false;
        }
        let Ok((day, minute)) = parse_due(&chosen) else {
            return false;
        };
        let day = day.to_string();
        (day.as_str(), minute) < (self.today.as_str(), self.minute_now)
    }

    /// The refusal for a pinned time that is already over today, shown as soon as one is picked. A time
    /// the homework already had, or finished homework, is left alone.
    fn past_when_problem(&self, env: &Env) -> EngineResult<String> {
        let (Some((day, start)), Some(week)) = (self.fixed_at(), env.week_start) else {
            return Ok(String::new());
        };
        if self.completed || !self.when_changed() {
            return Ok(String::new());
        }
        let start = hhmm_to_minutes(&start)?;
        let found = past_problem(
            "flexible",
            week,
            day,
            start,
            &self.today,
            self.minute_now,
            drag_step_of(env),
        )?;
        Ok(found.unwrap_or_default())
    }

    fn fixed_problem(&self, env: &Env, fixed: &(i64, String), due: &str) -> EngineResult<String> {
        let Some(week) = env.week_start else {
            return Ok(String::new());
        };
        let start = hhmm_to_minutes(&fixed.1)?;
        if !self.completed {
            let past = past_problem(
                "flexible",
                week,
                fixed.0,
                start,
                &self.today,
                self.minute_now,
                drag_step_of(env),
            )?;
            if let Some(message) = past.filter(|text| !text.is_empty()) {
                return Ok(message);
            }
        }
        let sessions = self.open_sessions(env);
        let length = match sessions.first() {
            Some(first) => py_int(required_in(first, "duration_min")?)?,
            None => self.estimate(),
        };
        let (limit, kind) = match due_point(&json!(due), week)? {
            Some((day, minute)) => (json!([day, minute]), "tuple"),
            None => (Value::Null, "NoneType"),
        };
        let found = span_problem(fixed.0, start, start + length, &limit, kind)?;
        Ok(found
            .unwrap_or_default()
            .replace(", so it stayed where it was", ""))
    }

    // Spread ---------------------------------------------------------------------------------

    pub fn spread_shown(&self) -> bool {
        self.estimate() >= SPREAD_MIN && !self.spread_out && self.when != "fixed"
    }

    /// (session minutes, first date, the sessions a spread would make).
    pub fn spread_figures(&self, env: &Env) -> EngineResult<(i64, String, Vec<Value>)> {
        let due = self.chosen_due();
        let focus = match self.original.get("focus_minutes") {
            Some(found) if truthy(Some(found)) => py_int(found)?,
            _ => 0,
        };
        let id = self.original.get("id").cloned().unwrap_or(Value::Null);
        let done = match env.done_minutes_for {
            Some(done_for) => done_for(&id)?,
            None => 0,
        };
        let remaining = unplanned_minutes(self.estimate(), focus, done, 0);
        let session_min = spread_session_min(remaining);
        let start = self.today.as_str().max(env.selected_day);
        let due_day = parse_due(&due)?.0.to_string();
        let from_date = start.min(due_day.as_str()).to_string();
        let (sessions, _off_grid) = spread_sessions(
            self.estimate(),
            focus,
            done,
            0,
            &due,
            session_min,
            &from_date,
        )?;
        Ok((session_min, from_date, sessions))
    }

    pub fn spread_requested(&self) -> bool {
        self.spread == "spread" && self.spread_shown()
    }

    pub fn spread_plan(&self, env: &Env) -> EngineResult<Value> {
        let (session_min, from_date, _sessions) = self.spread_figures(env)?;
        Ok(json!({"session_min": session_min, "from_date": from_date}))
    }

    // Edits ----------------------------------------------------------------------------------

    /// A kept new sheet opened again from a time picked on the grid: it is pinned to the picked day and
    /// start. The typed words and length stay.
    pub fn use_picked(&mut self, env: &Env, day: i64, start: &str) -> EngineResult<()> {
        self.set(env, "when", &json!("fixed"))?;
        self.set(env, "whenDay", &json!(day))?;
        self.set(env, "whenTime", &json!(start))
    }

    /// One field changed. Words that said it was wrong go when it changes.
    pub fn set(&mut self, env: &Env, name: &str, value: &Value) -> EngineResult<()> {
        match name {
            "title" => {
                self.title = py_str(value);
                self.title_problem.clear();
            }
            "dueDate" => {
                self.due_date = py_str(value);
                self.due_problem.clear();
                self.when_problem.clear();
            }
            "dueTime" => {
                self.due_time = py_str(value);
                self.due_problem.clear();
            }
            "estimate" => {
                self.estimate_text = py_str(value);
                if !self.estimate_problem.is_empty() {
                    self.estimate_problem = self.length_problem().to_string();
                }
            }
            "spread" => {
                self.spread = if value == "spread" { "spread" } else { "one" }.to_string();
            }
            "when" => {
                self.when = if value == "fixed" { "fixed" } else { "plan" }.to_string();
                self.when_problem = self.past_when_problem(env)?;
            }
            "whenDay" => {
                self.when_day = py_int(value)?;
                self.day_touched = true;
                self.moved_from.clear();
                self.moved_to.clear();
                self.moved_note.clear();
                self.when_problem = self.past_when_problem(env)?;
            }
            "whenTime" => {
                self.when_time = py_str(value);
                self.when_problem = self.past_when_problem(env)?;
            }
            "completed" => {
                self.completed = truthy(Some(value));
                self.when_problem = self.past_when_problem(env)?;
            }
            "course" => self.course = py_str(value),
            "priority" => self.priority = py_int(value)?,
            "energy" => self.energy = py_str(value),
            "notes" => self.notes = py_str(value),
            "linkLabel" => self.link_label = py_str(value),
            "linkUrl" => self.link_url = py_str(value),
            "checkText" => self.check_text = py_str(value),
            "detailsOpen" => self.details_open = truthy(Some(value)),
            _ => {}
        }
        self.error.clear();
        Ok(())
    }

    pub fn add_link(&mut self) {
        if self.links.len() >= LINKS_MAX {
            self.details_error = "Up to 20 links.".to_string();
            return;
        }
        let label = self.link_label.trim().to_string();
        let url = self.link_url.trim().to_string();
        if label.is_empty() || url.is_empty() {
            self.details_error =
                "Give the link a name and an address that starts with http:// or https://."
                    .to_string();
            return;
        }
        self.links.push(json!({"label": label, "url": url}));
        self.link_label.clear();
        self.link_url.clear();
        self.details_error.clear();
    }

    pub fn remove_link(&mut self, index: i64) {
        if let Some(at) = in_range(index, self.links.len()) {
            self.links.remove(at);
        }
    }

    /// `fresh_id` is the id of the step, drawn by the caller.
    pub fn add_check(&mut self, fresh_id: &str) {
        if self.checklist.len() >= CHECKS_MAX {
            self.details_error = "Up to 40 steps.".to_string();
            return;
        }
        let text = self.check_text.trim().to_string();
        if text.is_empty() {
            self.details_error = "A checklist step needs text.".to_string();
            return;
        }
        self.checklist
            .push(json!({"id": fresh_id, "text": text, "done": false}));
        self.check_text.clear();
        self.details_error.clear();
    }

    pub fn toggle_check(&mut self, index: i64) {
        let Some(at) = in_range(index, self.checklist.len()) else {
            return;
        };
        if let Some(item) = self.checklist[at].as_object_mut() {
            let done = truthy(item.get("done"));
            item.insert("done".into(), Value::Bool(!done));
        }
    }

    pub fn remove_check(&mut self, index: i64) {
        if let Some(at) = in_range(index, self.checklist.len()) {
            self.checklist.remove(at);
        }
    }

    // Steps ----------------------------------------------------------------------------------

    pub fn back(&mut self) {
        if let Some(step) = self.step.filter(|step| *step != 0) {
            self.step = Some(step - 1);
        }
    }

    /// A crumb that is already done takes the sheet back to that step.
    pub fn goto(&mut self, index: i64) {
        if let Some(step) = self.step
            && 0 <= index
            && index < step
        {
            self.step = Some(index);
        }
    }

    /// Next on the first two steps. True when the sheet is on its last step and Save is next.
    pub fn advance(&mut self, env: &Env) -> EngineResult<bool> {
        let Some(step) = self.step.filter(|step| *step < 2) else {
            return Ok(true);
        };
        if step == 0 && self.title.trim().is_empty() {
            self.title_problem = TITLE_PROBLEM.to_string();
            return Ok(false);
        }
        if step == 1 {
            if self.due_passed() {
                self.due_problem = DUE_PASSED.to_string();
                return Ok(false);
            }
            if let Some(fixed) = self.fixed_at().filter(|_| self.when_changed()) {
                let problem = self.fixed_problem(env, &fixed, &self.chosen_due())?;
                if !problem.is_empty() {
                    self.when_problem = problem;
                    return Ok(false);
                }
            }
        }
        self.step = Some(step + 1);
        Ok(false)
    }

    // The answer -----------------------------------------------------------------------------

    /// The homework as typed, or None with the reason put on the field it belongs to. The step with
    /// the problem is the one the sheet goes back to.
    pub fn candidate(&mut self, env: &Env) -> EngineResult<Option<Value>> {
        let problem = self.length_problem();
        if !problem.is_empty() {
            self.estimate_problem = problem.to_string();
            self.show_step(2);
            return Ok(None);
        }
        if self.due_passed() {
            self.due_problem = DUE_PASSED.to_string();
            self.show_step(1);
            return Ok(None);
        }
        let fixed = self.fixed_at();
        if let Some(pinned) = fixed.as_ref().filter(|_| self.when_changed()) {
            let problem = self.fixed_problem(env, pinned, &self.chosen_due())?;
            if !problem.is_empty() {
                self.when_problem = problem;
                self.show_step(1);
                return Ok(None);
            }
        }
        let mut made = self.original.clone();
        let mut completed_at = match self.original.get("completed_at") {
            Some(found) if self.completed => found.clone(),
            _ => Value::Null,
        };
        if self.completed && !truthy(Some(&completed_at)) {
            completed_at = json!(self.stamp);
        }
        let spread = if self.spread_shown() {
            self.spread.as_str()
        } else {
            "one"
        };
        let course = if self.course.is_empty() {
            Value::Null
        } else {
            json!(self.course)
        };
        for (key, value) in [
            ("title", json!(self.title.trim())),
            ("due", json!(self.chosen_due())),
            ("estimate_min", json!(self.estimate())),
            ("spread", json!(spread)),
            ("course", course),
            ("priority", json!(self.priority)),
            ("energy", json!(self.energy)),
            ("notes", json!(self.notes)),
            ("links", Value::Array(self.links.clone())),
            ("checklist", Value::Array(self.checklist.clone())),
            ("completed", json!(self.completed)),
            ("completed_at", completed_at),
        ] {
            made.insert(key.to_string(), value);
        }
        if self.when_changed() {
            let pinned = fixed.map_or(
                Value::Null,
                |(day, start)| json!({"day": day, "start": start}),
            );
            made.insert("fixed_at".into(), pinned);
        }
        let made = Value::Object(made);
        if let Some((field, message)) = homework_sheet_problem(&made) {
            if field == "title" {
                self.title_problem = message;
                self.show_step(0);
            } else {
                self.error = message;
            }
            return Ok(None);
        }
        Ok(Some(made))
    }

    fn show_step(&mut self, index: i64) {
        if self.step.is_some() {
            self.step = Some(index);
        }
    }

    // What the sheet shows -------------------------------------------------------------------

    fn placed_words(&self, env: &Env) -> EngineResult<String> {
        let mut placed = Vec::new();
        for block in self.open_sessions(env) {
            if truthy(block.get("start")) {
                let start = py_str(required_in(block, "start")?);
                placed.push((first_day_of(block)?, start));
            }
        }
        placed.sort();
        if placed.is_empty() {
            return Ok(String::new());
        }
        let week = match env.week_start.filter(|week| !week.is_empty()) {
            Some(week) => week.to_string(),
            None => monday_of(&self.today)?,
        };
        let shown = day_names(&week, false)?;
        let mut names = Vec::new();
        for (day, _start) in &placed {
            let number = day_number(&add_days(&week, *day)?)?;
            names.push(format!("{} {number}", name_at(&shown, *day)?));
        }
        let planned = match names.split_last() {
            Some((last, rest)) if !rest.is_empty() => {
                format!("Planned {} and {last}", rest.join(", "))
            }
            _ => format!("Planned {}", names[0]),
        };
        let due = self
            .original
            .get("due")
            .filter(|found| truthy(Some(found)))
            .map(py_str);
        let due_bit = match due {
            Some(text) => {
                let day: String = text.chars().take(10).collect();
                let name = DAYS[weekday_of(&day)?];
                format!(" \u{b7} due {name} {}", day_number(&day)?)
            }
            None => String::new(),
        };
        let times = if names.len() > 1 {
            format!(" \u{b7} {} times", names.len())
        } else {
            String::new()
        };
        Ok(format!("{planned}{due_bit}{times}"))
    }

    fn due_options(&self) -> EngineResult<Vec<Value>> {
        let first = normal(&self.today)?;
        let tomorrow = add_days(&first, 1)?;
        let mut days = Vec::new();
        for offset in 0..DAYS_AHEAD {
            days.push(add_days(&first, offset)?);
        }
        if !self.due_date.is_empty() {
            let chosen = normal(&self.due_date)?;
            if !days.contains(&chosen) {
                days.insert(0, chosen);
            }
        }
        let mut options = Vec::new();
        for day in days {
            let (_, month, number) = civil(&day)?;
            let mut words = format!("{} {number} {}", DAYS[weekday_of(&day)?], MONTHS[month - 1]);
            if day == first {
                words = format!("Today \u{b7} {words}");
            } else if day == tomorrow {
                words = format!("Tomorrow \u{b7} {words}");
            }
            options.push(json!({"value": day, "label": words}));
        }
        Ok(options)
    }

    fn now_hint(&self, env: &Env) -> EngineResult<String> {
        let Some((day, _start)) = self.fixed_at() else {
            return Ok(String::new());
        };
        if Some(day) != today_column_of(&self.today, env)? {
            return Ok(String::new());
        }
        Ok(today_from_words(self.minute_now))
    }

    /// Every mark of the time step, less the ones already over when the pinned day is today. A time the
    /// homework already had on that day stays, as does everything for finished homework, as the refusal
    /// allows. A time off the step (a pin made before the step changed) is listed too, in order, so the
    /// field can show it and Up and Down step from it.
    fn pinned_time_options(&self, env: &Env) -> EngineResult<Vec<Value>> {
        let mut options = self.quarter_options(env)?;
        let step = drag_step_of(env);
        let mut own = vec![self.when_time.clone()];
        if let Some((day, start)) = &self.placed
            && *day == self.when_day
            && !own.contains(start)
        {
            own.push(start.clone());
        }
        for found in own {
            if !found.is_empty() && hhmm_to_minutes(&found)? % step != 0 {
                options.push(json!({"value": found, "label": hhmm_text(&found)?}));
            }
        }
        let mut keyed = Vec::new();
        for item in options {
            let value = text_of(required_in(&item, "value")?, "value")?;
            keyed.push((hhmm_to_minutes(&value)?, item));
        }
        keyed.sort_by_key(|(minute, _)| *minute);
        Ok(keyed.into_iter().map(|(_, item)| item).collect())
    }

    fn quarter_options(&self, env: &Env) -> EngineResult<Vec<Value>> {
        let step = drag_step_of(env);
        let options = quarter_hours_of(step)?;
        let today = today_column_of(&self.today, env)?;
        if self.completed || today.is_none() || Some(self.when_day) != today {
            return Ok(options);
        }
        let earliest = -((-self.minute_now).div_euclid(step)) * step;
        if earliest > 24 * 60 - step {
            return Ok(options);
        }
        let saved = self
            .placed
            .as_ref()
            .filter(|(day, _)| *day == self.when_day)
            .map(|(_, start)| start.clone());
        let mut kept = Vec::new();
        for item in options {
            let value = text_of(required_in(&item, "value")?, "value")?;
            if hhmm_to_minutes(&value)? >= earliest || Some(&value) == saved.as_ref() {
                kept.push(item);
            }
        }
        Ok(kept)
    }

    fn due_words(&self) -> String {
        let chosen = self.chosen_due();
        day_of(&self.today)
            .and_then(|today| due_label_text(Some(&chosen), today))
            .unwrap_or_else(|_| self.due_date.clone())
    }

    /// What the sheet shows: every field the QML reads.
    pub fn form(&self, env: &Env) -> EngineResult<Value> {
        let week = env.week_start.filter(|week| !week.is_empty());
        let names: Vec<&str> = match week {
            Some(week) => day_names(week, false)?,
            None => DAYS.to_vec(),
        };
        let mut day_options = Vec::new();
        for index in 0..7_i64 {
            let name = name_at(&names, index)?;
            let label = match week {
                Some(week) => format!("{name} {}", day_number(&add_days(week, index)?)?),
                None => name.to_string(),
            };
            day_options.push(json!({"value": index, "label": label}));
        }
        let step = self.step;
        let fixed = self.fixed_at();
        let mut spread_line = String::new();
        if self.spread_shown() && self.spread == "spread" && self.length_problem().is_empty() {
            let figures = self.spread_figures(env)?;
            spread_line = spread_words(&Value::Array(figures.2), &self.chosen_due(), &self.today)?;
        }
        let summaries = [
            self.title.trim().to_string(),
            format!(
                "due {}, {}",
                self.due_words(),
                if self.when == "plan" {
                    "FlexWeek picks"
                } else {
                    "pinned"
                }
            ),
        ];
        let mut crumbs = Vec::new();
        for (at, name) in STEPS.iter().enumerate() {
            let index = i64::try_from(at).unwrap_or(0);
            let behind = step.is_some_and(|found| index < found);
            let mark = if behind {
                "\u{2713} ".to_string()
            } else {
                format!("{}. ", index + 1)
            };
            let summary = match summaries.get(at) {
                Some(text) if behind => text.clone(),
                _ => String::new(),
            };
            crumbs.push(json!({
                "label": format!("{mark}{name}"),
                "done": behind,
                "on": Some(index) == step,
                "summary": summary,
            }));
        }
        let last = step.is_none_or(|found| found >= 2);
        let step_step = drag_step_of(env);
        let estimate = self.estimate();
        let mut time_options = vec![json!({"value": "", "label": "End of day"})];
        time_options.extend(quarter_hours_of(step_step)?);
        let when_note = match &fixed {
            Some((day, start)) => format!(
                "Pinned to {} at {}. Plan won't move it.",
                name_at(&names, *day)?,
                hhmm_text(start)?
            ),
            None => String::new(),
        };
        let pinned = self.when == "fixed";
        let lengths: Vec<Value> = QUICK_LENGTHS
            .iter()
            .map(|value| json!({"value": value.to_string(), "label": format!("{value} min")}))
            .collect();
        let links: Vec<Value> = self
            .links
            .iter()
            .map(|item| {
                json!({
                    "label": item.get("label").cloned().unwrap_or(Value::Null),
                    "url": item.get("url").cloned().unwrap_or(Value::Null),
                })
            })
            .collect();
        let checklist: Vec<Value> = self
            .checklist
            .iter()
            .map(|item| {
                json!({
                    "text": item.get("text").cloned().unwrap_or(Value::Null),
                    "done": truthy(item.get("done")),
                })
            })
            .collect();
        let mut form = Map::new();
        let mut put = |key: &str, value: Value| {
            form.insert(key.to_string(), value);
        };
        put("kind", json!("homework"));
        put("mode", json!(if self.existing { "edit" } else { "add" }));
        put(
            "heading",
            json!(if self.existing {
                "Edit homework"
            } else {
                "Add homework"
            }),
        );
        put("step", json!(step.unwrap_or(-1)));
        put(
            "crumbs",
            if step.is_some() {
                Value::Array(crumbs)
            } else {
                json!([])
            },
        );
        put(
            "prompt",
            match step {
                Some(found) => json!(name_at(&PROMPTS, found)?),
                None => json!(""),
            },
        );
        put("title", json!(self.title));
        put("titleProblem", json!(self.title_problem));
        put(
            "placedLine",
            json!(if self.existing {
                self.placed_words(env)?
            } else {
                String::new()
            }),
        );
        put("dueDate", json!(self.due_date));
        put("dueTime", json!(self.due_time));
        put("dueOptions", Value::Array(self.due_options()?));
        put("timeOptions", Value::Array(time_options));
        put(
            "pinnedTimeOptions",
            Value::Array(self.pinned_time_options(env)?),
        );
        put("dueProblem", json!(self.due_problem));
        put("whenChoices", pairs(&WHEN_CHOICES));
        put("when", json!(self.when));
        put("whenShown", json!(!self.spread_out));
        put("whenDay", json!(self.when_day));
        put("dayOptions", Value::Array(day_options));
        put("whenTime", json!(self.when_time));
        put("whenNote", json!(when_note));
        put("whenFrom", json!(self.now_hint(env)?));
        // The day row shows only while the homework is pinned, so a move is named only then.
        put(
            "whenMovedNote",
            json!(if pinned {
                self.moved_note.clone()
            } else {
                String::new()
            }),
        );
        put(
            "whenDayAccess",
            json!(if !self.moved_from.is_empty() && pinned {
                self.moved_access()
            } else {
                String::new()
            }),
        );
        put("whenProblem", json!(self.when_problem));
        put("estimate", json!(self.estimate_text));
        put(
            "estimateLabel",
            json!(if estimate != 0 {
                length_label(estimate)
            } else {
                String::new()
            }),
        );
        put("estimateSuffix", json!("min"));
        put("quickLengths", Value::Array(lengths));
        put("estimateProblem", json!(self.estimate_problem));
        put("spreadShown", json!(self.spread_shown()));
        put("spreadChoices", pairs(&SPREAD_CHOICES));
        put("spread", json!(self.spread));
        put("spreadLine", json!(spread_line));
        put("completed", json!(self.completed));
        put("detailsOpen", json!(self.details_open));
        put("course", json!(self.course));
        put("priority", json!(self.priority));
        put(
            "typeOptions",
            Value::Array(
                TYPES
                    .iter()
                    .map(|(value, label)| json!({"value": value, "label": label}))
                    .collect(),
            ),
        );
        put("energy", json!(self.energy));
        put("energyOptions", pairs(&ENERGIES));
        put("notes", json!(self.notes));
        put("links", Value::Array(links));
        put("checklist", Value::Array(checklist));
        put("detailsError", json!(self.details_error));
        put("linkLabel", json!(self.link_label));
        put("linkUrl", json!(self.link_url));
        put("checkText", json!(self.check_text));
        put("error", json!(self.error));
        put("canBack", json!(step.is_some_and(|found| found != 0)));
        put(
            "primary",
            json!(if last || self.existing {
                "Save"
            } else {
                "Next"
            }),
        );
        put("last", json!(last));
        put("canDelete", json!(self.existing));
        put("canUnpin", json!(self.existing && self.pinned_session));
        put("showDetails", json!(last));
        put("showFinished", json!(self.existing));
        Ok(Value::Object(form))
    }

    /// One state field by its Python attribute name, for the screen's tests and bridge.
    pub fn field(&self, name: &str) -> EngineResult<Value> {
        Ok(match name {
            "existing" => json!(self.existing),
            "original" => Value::Object(self.original.clone()),
            "step" => self.step.map_or(Value::Null, |found| json!(found)),
            "title" => json!(self.title),
            "due_date" => json!(self.due_date),
            "due_time" => json!(self.due_time),
            "estimate_text" => json!(self.estimate_text),
            "spread" => json!(self.spread),
            "completed" => json!(self.completed),
            "course" => json!(self.course),
            "priority" => json!(self.priority),
            "energy" => json!(self.energy),
            "notes" => json!(self.notes),
            "links" => Value::Array(self.links.clone()),
            "checklist" => Value::Array(self.checklist.clone()),
            "link_label" => json!(self.link_label),
            "link_url" => json!(self.link_url),
            "check_text" => json!(self.check_text),
            "details_open" => json!(self.details_open),
            "placed" => self
                .placed
                .as_ref()
                .map_or(Value::Null, |(day, start)| json!([day, start])),
            "spread_out" => json!(self.spread_out),
            "when" => json!(self.when),
            "when_day" => json!(self.when_day),
            "when_time" => json!(self.when_time),
            "pinned_session" => json!(self.pinned_session),
            "title_problem" => json!(self.title_problem),
            "due_problem" => json!(self.due_problem),
            "when_problem" => json!(self.when_problem),
            "estimate_problem" => json!(self.estimate_problem),
            "error" => json!(self.error),
            "details_error" => json!(self.details_error),
            "today" => json!(self.today),
            "stamp" => json!(self.stamp),
            other => {
                return Err(EngineError {
                    kind: flexweek_engine::ErrorKind::Attribute,
                    message: format!("'HomeworkDraft' object has no attribute '{other}'"),
                });
            }
        })
    }
}

impl Picture {
    fn blank() -> Self {
        Self {
            title: String::new(),
            due_date: String::new(),
            due_time: String::new(),
            estimate_text: String::new(),
            when: String::new(),
            when_day: 0,
            when_time: String::new(),
            spread: String::new(),
            course: String::new(),
            priority: 0,
            energy: String::new(),
            notes: String::new(),
            completed: false,
            links: Vec::new(),
            checklist: Vec::new(),
        }
    }
}

fn required_in<'a>(item: &'a Value, key: &str) -> EngineResult<&'a Value> {
    item.get(key).ok_or_else(|| EngineError::key(key))
}

fn list_of(map: &Map<String, Value>, key: &str) -> Vec<Value> {
    map.get(key)
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
}

fn in_range(index: i64, len: usize) -> Option<usize> {
    usize::try_from(index).ok().filter(|at| *at < len)
}

/// A clock reading `YYYY-MM-DDTHH:MM` as (the date, the minute of its day).
fn clock_of(stamp: &str) -> EngineResult<(String, i64)> {
    let (day, minute) = parse_moment(stamp)?;
    Ok((day.to_string(), minute))
}
