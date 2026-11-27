//! View-model and navigation state for the Material Week screen (`bridge_week.py`, P5-W1).
//!
//! Pure over values passed in by the caller: nothing here reads a clock, draws an id, or touches
//! the operating system. `occurrence_row` and `overlapped` are shared with the Day screen.

use std::collections::{HashMap, HashSet};

use flexweek_engine::desk::datetext::day_of;
use flexweek_engine::desk::weekmodel::{
    clock_label, due_in_minutes, due_label_text, length_label, range_label, set_clock_24h,
    short_clock,
};
use flexweek_engine::shown::{day_names, shown_columns};
use flexweek_engine::stored::{add_days, truthy};
use flexweek_engine::{EngineError, EngineResult};
use serde_json::{Map, Value, json};

use crate::session::plan::homework_time_sentence;
use crate::views::hours::{DEFAULT_DRAG_STEP, drag_step, snap};
use crate::views::theme::{event_category, paint_for_category};

pub const EVERYTHING_TIMED: &str = "Everything has a time.";
pub const DANGER_SLACK_MIN: i64 = 60;
pub const TIGHT_SLACK_MIN: i64 = 3 * 60;
pub const DAY_MIN: i64 = 24 * 60;
pub const PLAN_WINDOW_S: f64 = 30.0;
pub const FRESH_S: f64 = 1.0;
pub const WEEKEND_SAVE_FAILED: &str = "Couldn't save the weekend setting. Try again.";

pub const SLACK_DANGER: (&str, &str) = ("Cutting it close", "cutting");
pub const SLACK_TIGHT: (&str, &str) = ("Tight", "tight");
pub const SLACK_OK: (&str, &str) = ("Plenty of time", "plenty");
pub const SLACK_PLAIN: (&str, &str) = ("", "plain");

/// One occurrence passed into `occurrence_row` or `WeekView::finish_reload`.
#[derive(Clone, Debug)]
pub struct OccurrenceInput {
    pub block_id: String,
    pub title: String,
    pub category: String,
    pub day: i64,
    pub start: i64,
    pub end: i64,
    pub work: bool,
    pub done: bool,
    pub assignment_id: String,
}

/// One waiting homework card passed into `WeekView::finish_reload`.
#[derive(Clone, Debug)]
pub struct WaitingInput {
    pub block_id: String,
    pub title: String,
    pub minutes: i64,
    pub assignment_id: String,
    pub due: Option<String>,
    pub reason: String,
}

/// One uncovered homework remainder `(title, minutes, homework_id)`.
#[derive(Clone, Debug)]
pub struct UncoveredInput {
    pub title: String,
    pub minutes: i64,
    pub assignment_id: Value,
}

/// Inputs for `WeekView::finish_reload` once signed in with a non-empty `week_start`.
pub struct ReloadInput<'a> {
    pub mode: &'a str,
    pub occurrences: &'a [OccurrenceInput],
    pub waiting: &'a [WaitingInput],
    pub missed: &'a HashSet<String>,
    pub needed: &'a [Value],
    pub plan_can_place: bool,
    pub uncovered: &'a [UncoveredInput],
    pub unfinished: &'a [Value],
    pub today_iso: &'a str,
    pub clock_minute: i64,
    pub steady_ms: i64,
    pub fresh_s: f64,
}

/// Action plan for dropping a drawer card or moving a block on the grid.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MovePlan {
    pub start: i64,
    pub end: i64,
    pub judge: bool,
}

/// Action plan for toggling homework completion.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ToggleDonePlan {
    pub finished: bool,
    pub notice: String,
}

/// Optimistic weekend toggle update.
#[derive(Clone, Debug, PartialEq)]
pub struct WeekendTogglePlan {
    pub ticket: u64,
    pub wanted: bool,
    pub preferences: Value,
}

/// Rollback payload when saving `show_weekends` fails for the active ticket.
#[derive(Clone, Debug, PartialEq)]
pub struct WeekendRollback {
    pub preferences: Value,
    pub message: &'static str,
}

/// Explicit-boolean preference reader: only a JSON boolean overrides `default`.
pub fn bool_pref(prefs: &Value, key: &str, default: bool) -> bool {
    prefs
        .as_object()
        .and_then(|map| map.get(key))
        .and_then(Value::as_bool)
        .unwrap_or(default)
}

/// One QML block row from a week occurrence. Day and Week share this shape.
// The four boolean display flags match the shared Day/Week bridge signature.
#[allow(clippy::fn_params_excessive_bools)]
pub fn occurrence_row(
    item: &OccurrenceInput,
    mode: &str,
    dim: bool,
    gone: bool,
    fresh: bool,
    missed: bool,
) -> EngineResult<Map<String, Value>> {
    let (fill, ink) = paint_for_category(&item.category, mode)?;
    let mut row = Map::new();
    row.insert("title".to_string(), Value::String(item.title.clone()));
    row.insert("day".to_string(), Value::from(item.day));
    row.insert("start".to_string(), Value::from(item.start));
    row.insert("end".to_string(), Value::from(item.end));
    row.insert("fill".to_string(), Value::String(fill));
    row.insert("ink".to_string(), Value::String(ink.to_string()));
    row.insert(
        "category".to_string(),
        Value::String(event_category(&item.category).to_string()),
    );
    row.insert(
        "detail".to_string(),
        Value::String(range_label(item.start, item.end)),
    );
    row.insert(
        "detailStart".to_string(),
        Value::String(short_clock(item.start)),
    );
    // A session the planner calls missed is still to do, so it is not dimmed as over.
    row.insert(
        "past".to_string(),
        Value::Bool(dim && (item.done || (gone && !missed))),
    );
    row.insert("blockId".to_string(), Value::String(item.block_id.clone()));
    row.insert(
        "assignmentId".to_string(),
        Value::String(item.assignment_id.clone()),
    );
    row.insert(
        "homework".to_string(),
        Value::Bool(item.work && !item.assignment_id.is_empty()),
    );
    row.insert("done".to_string(), Value::Bool(item.done));
    row.insert("fresh".to_string(), Value::Bool(fresh));
    row.insert("indent".to_string(), Value::from(0));
    row.insert("under".to_string(), Value::Array(Vec::new()));
    Ok(row)
}

fn req_row_int(row: &Map<String, Value>, key: &str) -> EngineResult<i64> {
    row.get(key)
        .and_then(Value::as_i64)
        .ok_or_else(|| EngineError::value(format!("row.{key} must be an integer")))
}

/// Items that share time overlap instead of splitting the lane.
///
/// Sorts stably by `(day, start, start - end)` (longer first on a tie), then computes `indent`
/// (one past the deepest covered earlier item) and `under` (indices in the sorted list).
pub fn overlapped(rows: Vec<Value>) -> EngineResult<Vec<Value>> {
    let mut entries: Vec<(i64, i64, i64, Map<String, Value>)> = Vec::with_capacity(rows.len());
    for row in rows {
        let Value::Object(map) = row else {
            return Err(EngineError::value("each row must be a JSON object"));
        };
        let day = req_row_int(&map, "day")?;
        let start = req_row_int(&map, "start")?;
        let end = req_row_int(&map, "end")?;
        entries.push((day, start, end, map));
    }
    entries.sort_by_key(|(day, start, end, _)| (*day, *start, *start - *end));
    let mut indents: Vec<i64> = Vec::with_capacity(entries.len());
    let mut out: Vec<Value> = Vec::with_capacity(entries.len());
    for at in 0..entries.len() {
        let (day, start, _, _) = &entries[at];
        let mut under: Vec<Value> = Vec::new();
        let mut deepest: i64 = 0;
        for (place, (other_day, _, other_end, _)) in entries[..at].iter().enumerate() {
            if other_day == day && other_end > start {
                under.push(Value::from(place as i64));
                deepest = deepest.max(indents[place] + 1);
            }
        }
        indents.push(deepest);
        let mut map = entries[at].3.clone();
        map.insert("indent".to_string(), Value::from(deepest));
        map.insert("under".to_string(), Value::Array(under));
        out.push(Value::Object(map));
    }
    Ok(out)
}

/// How much room waiting homework has before it is due. No deadline, no tag.
pub fn tag_for(
    due: Option<&str>,
    minutes: i64,
    today_iso: &str,
    clock_minute: i64,
) -> EngineResult<(&'static str, &'static str)> {
    let Some(due) = due.filter(|text| !text.is_empty()) else {
        return Ok(SLACK_PLAIN);
    };
    let today = day_of(today_iso)?;
    let Some(due_in) = due_in_minutes(due, today, clock_minute) else {
        return Ok(SLACK_OK);
    };
    let room = due_in - minutes;
    if room <= DANGER_SLACK_MIN {
        return Ok(SLACK_DANGER);
    }
    if room <= TIGHT_SLACK_MIN || (0..DAY_MIN).contains(&due_in) {
        return Ok(SLACK_TIGHT);
    }
    Ok(SLACK_OK)
}

/// The line above the week: `"N overdue · N left from last week"`, or empty when nothing is left.
pub fn left_line(unfinished: &[Value]) -> String {
    let overdue = unfinished
        .iter()
        .filter(|item| {
            item.as_object()
                .and_then(|map| map.get("left_over_state"))
                .and_then(Value::as_str)
                == Some("overdue")
        })
        .count();
    let carried = unfinished.len() - overdue;
    let mut parts = Vec::new();
    if overdue > 0 {
        parts.push(format!("{overdue} overdue"));
    }
    if carried > 0 {
        parts.push(format!("{carried} left from last week"));
    }
    parts.join(" · ")
}

/// The plan button's label: manual planners ask for ideas (`Suggest times`).
pub fn plan_label(prefs: &Value) -> &'static str {
    if prefs
        .as_object()
        .and_then(|map| map.get("planning_style"))
        .and_then(Value::as_str)
        == Some("manual")
    {
        "Suggest times"
    } else {
        "Plan my homework"
    }
}

/// Returns `Some(day)` when `day >= 0`, else `None` (Qt's `-1` sentinel for no day).
pub fn optional_day(day: i64) -> Option<i64> {
    (day >= 0).then_some(day)
}

/// True when something is on the clipboard and no save is in flight.
pub fn has_copied(has_clipboard: bool, busy: bool) -> bool {
    has_clipboard && !busy
}

/// Parses an ISO calendar date string (Python `date.fromisoformat` syntax) to `YYYY-MM-DD`, or `None`.
pub fn parse_iso_date(iso: &str) -> Option<String> {
    day_of(iso).ok().map(|date| date.to_string())
}

/// Returns the problem message when `judge_hand_move` refused the move, else `None`.
pub fn hand_move_problem(answer: &Value) -> EngineResult<Option<String>> {
    let map = answer
        .as_object()
        .ok_or_else(|| EngineError::value("hand move answer must be a JSON object"))?;
    let moved = truthy(map.get("moved"));
    if moved {
        return Ok(None);
    }
    let problem = map
        .get("problem")
        .and_then(Value::as_str)
        .ok_or_else(|| EngineError::value("hand move answer missing string 'problem'"))?;
    Ok(Some(problem.to_string()))
}

/// Keep each number attached to its `h` or `min` unit with a non-breaking space.
pub fn non_breaking_length(minutes: i64) -> String {
    length_label(minutes)
        .replace(" h", "\u{00a0}h")
        .replace(" min", "\u{00a0}min")
}

fn day_number(date: &impl std::fmt::Display) -> EngineResult<u32> {
    let text = date.to_string();
    text.get(8..10)
        .and_then(|part| part.parse::<u32>().ok())
        .ok_or_else(|| EngineError::value(format!("unexpected date format: {text}")))
}

fn secs_to_ms(seconds: f64) -> i64 {
    (seconds * 1000.0).round() as i64
}

fn hour_labels_now() -> Vec<String> {
    (0..24).map(|hour| clock_label(hour * 60)).collect()
}

fn push_unique(seen: &mut Vec<Value>, candidate: Value) {
    if !seen.contains(&candidate) {
        seen.push(candidate);
    }
}

fn block_id_matches(block: &Value, block_id: &str) -> bool {
    block
        .as_object()
        .and_then(|map| map.get("id"))
        .and_then(Value::as_str)
        == Some(block_id)
}

fn block_duration(block: &Value) -> i64 {
    block
        .as_object()
        .and_then(|map| map.get("duration_min"))
        .and_then(|value| match value {
            Value::Number(num) => num.as_i64(),
            Value::Bool(flag) => Some(i64::from(*flag)),
            _ => None,
        })
        .unwrap_or(0)
}

/// Queued rapid week-navigation state machine.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct WeekNavState {
    pub target_week: Option<String>,
    pub loading_week: Option<String>,
}

impl WeekNavState {
    pub fn picker_anchor(&self, week_start: &str) -> String {
        if let Some(target) = self.target_week.as_deref().filter(|text| !text.is_empty()) {
            return target.to_string();
        }
        week_start.to_string()
    }

    pub fn shift_target(&self, days: i64, week_start: &str) -> EngineResult<Option<String>> {
        let base = self
            .target_week
            .as_deref()
            .filter(|text| !text.is_empty())
            .or((!week_start.is_empty()).then_some(week_start));
        let Some(base) = base else {
            return Ok(None);
        };
        let shifted = add_days(day_of(base)?, days)?;
        Ok(Some(shifted.to_string()))
    }

    pub fn load_target(&mut self, target: String, busy: bool) -> bool {
        self.target_week = Some(target);
        !busy
    }

    pub fn begin_flush(&mut self, week_start: &str, busy: bool) -> Option<String> {
        if busy {
            return None;
        }
        let target = self
            .target_week
            .as_deref()
            .filter(|text| !text.is_empty())?
            .to_string();
        if target == week_start {
            self.target_week = None;
            return None;
        }
        self.loading_week = Some(target.clone());
        Some(target)
    }

    pub fn finish_flush(&mut self, busy: bool) {
        if !busy {
            self.loading_week = None;
            self.target_week = None;
        }
    }

    pub fn settle_navigation(&mut self, week_start: &str, busy: bool) -> bool {
        let finished = self.loading_week.take();
        if finished.is_some() && self.target_week == finished {
            self.target_week = None;
        }
        if self.target_week.as_deref() == Some(week_start) {
            self.target_week = None;
        }
        self.target_week
            .as_deref()
            .is_some_and(|text| !text.is_empty())
            && !busy
    }

    pub fn on_account_changed(&mut self) {
        self.target_week = None;
        self.loading_week = None;
    }
}

/// Complete Material Week view-model and interaction state.
#[derive(Clone, Debug)]
pub struct WeekView {
    pub block_rows: Vec<Value>,
    pub homework_rows: Vec<Value>,
    pub day_rows: Vec<Value>,
    pub day_headers: Vec<String>,
    pub hour_labels: Vec<String>,
    pub time_words: String,
    pub all_timed: bool,
    pub can_plan: bool,
    pub listed_count: i64,
    pub leftover_words: String,
    pub left_words: String,
    pub now_day: i64,
    pub now_column: i64,
    pub now_minute: i64,
    pub columns: i64,
    pub shown_days: Vec<i64>,
    pub drag_step: i64,
    pub clock_24h: bool,
    dim_completed: bool,
    pending_week_start: String,
    week_key: String,
    seen: HashSet<(String, i64)>,
    fresh_until: HashMap<(String, i64), i64>,
    done_after_save: String,
    said_plan_ms: Option<i64>,
    pub nav: WeekNavState,
    weekend_save: u64,
    weekend_previous: Option<Value>,
}

impl Default for WeekView {
    fn default() -> Self {
        Self::new()
    }
}

impl WeekView {
    pub fn new() -> Self {
        Self {
            block_rows: Vec::new(),
            homework_rows: Vec::new(),
            day_rows: Vec::new(),
            day_headers: Vec::new(),
            hour_labels: hour_labels_now(),
            time_words: EVERYTHING_TIMED.to_string(),
            all_timed: true,
            can_plan: false,
            listed_count: 0,
            leftover_words: String::new(),
            left_words: String::new(),
            now_day: -1,
            now_column: -1,
            now_minute: 0,
            columns: 7,
            shown_days: (0..7).collect(),
            drag_step: DEFAULT_DRAG_STEP,
            clock_24h: true,
            dim_completed: true,
            pending_week_start: String::new(),
            week_key: String::new(),
            seen: HashSet::new(),
            fresh_until: HashMap::new(),
            done_after_save: String::new(),
            said_plan_ms: None,
            nav: WeekNavState::default(),
            weekend_save: 0,
            weekend_previous: None,
        }
    }

    /// First phase of `reload`: reads preferences and account/week presence.
    ///
    /// Returns `false` when signed out or `week_start` is empty (clearing grid/drawer fields and
    /// `seen` so the caller does not query session week data), or `true` when the caller should
    /// follow with `finish_reload`.
    pub fn prepare_reload(
        &mut self,
        prefs: &Value,
        week_start: Option<&str>,
        signed_in: bool,
    ) -> EngineResult<bool> {
        let clock_24h = truthy(prefs.as_object().and_then(|map| map.get("clock_24h")));
        self.clock_24h = clock_24h;
        set_clock_24h(clock_24h);
        self.hour_labels = hour_labels_now();
        let weekends = bool_pref(prefs, "show_weekends", true);
        let start_day = week_start.unwrap_or("");
        self.shown_days = if !start_day.is_empty() {
            shown_columns(start_day, weekends)?
        } else {
            (0..7).collect()
        };
        self.columns = self.shown_days.len() as i64;
        let step_val = prefs
            .as_object()
            .and_then(|map| map.get("drag_step_min"))
            .and_then(Value::as_i64);
        self.drag_step = drag_step(step_val);
        self.dim_completed = bool_pref(prefs, "dim_completed", true);
        self.now_day = -1;
        self.now_column = -1;
        self.now_minute = 0;

        if !signed_in || start_day.is_empty() {
            self.block_rows.clear();
            self.homework_rows.clear();
            self.day_rows.clear();
            self.day_headers.clear();
            self.leftover_words.clear();
            self.listed_count = 0;
            self.left_words.clear();
            self.seen.clear();
            self.pending_week_start.clear();
            return Ok(false);
        }
        self.pending_week_start = start_day.to_string();
        Ok(true)
    }

    /// Second phase of `reload`: builds day headers, overlapped block rows, homework drawer rows,
    /// leftover lines, and fresh-landing state.
    pub fn finish_reload(&mut self, input: ReloadInput<'_>) -> EngineResult<()> {
        let week_start = self.pending_week_start.clone();
        let start = day_of(&week_start)?;
        let today = day_of(input.today_iso)?;
        let offset = (today - start).num_days();
        if (0..=6).contains(&offset) {
            self.now_day = offset;
            self.now_minute = input.clock_minute;
            if let Some(column) = self.shown_days.iter().position(|&day| day == offset) {
                self.now_column = column as i64;
            }
        }

        let names = day_names(&week_start, false)?;
        let mut day_rows = Vec::with_capacity(self.shown_days.len());
        let mut day_headers = Vec::with_capacity(self.shown_days.len());
        for &index in &self.shown_days {
            let day_date = add_days(start, index)?;
            let number = day_number(&day_date)?;
            let name = names[index as usize];
            let label = format!("{name} {number}");
            day_headers.push(label.clone());
            day_rows.push(json!({
                "label": label,
                "name": name,
                "date": number.to_string(),
                "today": index == self.now_day,
                "day": index,
            }));
        }

        let mut keys: HashSet<(String, i64)> = HashSet::new();
        let fresh_ok = self.week_key == week_start && !self.seen.is_empty();
        let fresh_ms = secs_to_ms(input.fresh_s);
        let mut block_rows: Vec<Value> = Vec::new();
        for item in input.occurrences {
            let Some(column) = self.shown_days.iter().position(|&day| day == item.day) else {
                continue;
            };
            // A week that ended is all past, a week ahead has nothing past, this week goes by the clock.
            let gone = if offset > 6 {
                true
            } else if offset < 0 {
                false
            } else {
                item.day < offset || (item.day == offset && item.end <= self.now_minute)
            };
            let key = (item.block_id.clone(), item.day);
            keys.insert(key.clone());
            if fresh_ok && !self.seen.contains(&key) {
                self.fresh_until
                    .insert(key.clone(), input.steady_ms + fresh_ms);
            }
            let fresh = self
                .fresh_until
                .get(&key)
                .is_some_and(|&until| until > input.steady_ms);
            let mut row = occurrence_row(
                item,
                input.mode,
                self.dim_completed,
                gone,
                fresh,
                input.missed.contains(&item.block_id),
            )?;
            row.insert("column".to_string(), Value::from(column as i64));
            block_rows.push(Value::Object(row));
        }

        let mut homework_rows: Vec<Value> = Vec::with_capacity(input.waiting.len());
        let mut listed_ids: Vec<Value> = Vec::new();
        for item in input.waiting {
            let (tag, kind) = tag_for(
                item.due.as_deref(),
                item.minutes,
                input.today_iso,
                input.clock_minute,
            )?;
            let mut parts: Vec<String> = Vec::new();
            if let Some(due) = item.due.as_deref().filter(|text| !text.is_empty()) {
                parts.push(format!("Due {}", due_label_text(Some(due), today)?));
            }
            parts.push(non_breaking_length(item.minutes));
            let key_id = if !item.assignment_id.is_empty() {
                item.assignment_id.clone()
            } else {
                item.block_id.clone()
            };
            push_unique(&mut listed_ids, Value::String(key_id));
            homework_rows.push(json!({
                "title": item.title,
                "minutes": item.minutes,
                "blockId": item.block_id,
                "assignmentId": item.assignment_id,
                "detail": parts.join(" · "),
                "tag": tag,
                "tagKind": kind,
                "reason": item.reason,
            }));
        }

        self.time_words = homework_time_sentence(&[], input.needed).map_err(EngineError::value)?;
        self.all_timed = input.needed.is_empty();
        // A card the drawer lists is something Plan places, even a task that is not homework.
        self.can_plan = !homework_rows.is_empty() || input.plan_can_place;

        let mut leftover_lines: Vec<String> = Vec::new();
        for item in input.uncovered {
            push_unique(&mut listed_ids, item.assignment_id.clone());
            leftover_lines.push(format!(
                "{} · {} with no time",
                item.title,
                length_label(item.minutes)
            ));
        }
        for item in input.needed {
            let Some(map) = item.as_object() else {
                continue;
            };
            let has_missed = truthy(map.get("missed_min"));
            let has_pinned = truthy(map.get("pinned_min"));
            if !has_missed && !has_pinned {
                continue;
            }
            if let Some(assignment_id) = map.get("assignment_id") {
                push_unique(&mut listed_ids, assignment_id.clone());
            }
            let title = map.get("title").and_then(Value::as_str).unwrap_or_default();
            for (key, words) in [
                ("missed_min", "missed"),
                ("pinned_min", "pinned, in the past"),
            ] {
                if let Some(value) = map.get(key)
                    && truthy(Some(value))
                {
                    let minutes = value.as_i64().unwrap_or(0);
                    leftover_lines.push(format!("{title} · {} {words}", length_label(minutes)));
                }
            }
        }

        self.listed_count = listed_ids.len() as i64;
        self.leftover_words = leftover_lines.join("\n");
        self.left_words = left_line(input.unfinished);
        self.week_key = week_start;
        self.seen = keys;
        self.fresh_until.retain(|_, until| *until > input.steady_ms);
        self.block_rows = overlapped(block_rows)?;
        self.homework_rows = homework_rows;
        self.day_rows = day_rows;
        self.day_headers = day_headers;
        Ok(())
    }

    /// Snapshot of every property `WeekBridge` exposes to QML.
    pub fn snapshot(&self) -> Value {
        json!({
            "blockRows": self.block_rows,
            "homeworkRows": self.homework_rows,
            "dayRows": self.day_rows,
            "dayHeaders": self.day_headers,
            "hourLabels": self.hour_labels,
            "timeWords": self.time_words,
            "allTimed": self.all_timed,
            "canPlan": self.can_plan,
            "listedCount": self.listed_count,
            "leftoverWords": self.leftover_words,
            "leftWords": self.left_words,
            "nowDay": self.now_day,
            "nowColumn": self.now_column,
            "nowMinute": self.now_minute,
            "columns": self.columns,
            "shownDays": self.shown_days,
            "dragStep": self.drag_step,
        })
    }

    /// Records the start of a "Plan my homework" run when planning is allowed.
    pub fn begin_plan(&mut self, steady_ms: i64) -> bool {
        if !self.can_plan {
            return false;
        }
        self.said_plan_ms = Some(steady_ms);
        true
    }

    /// Decides whether a session status line finishes a recently requested plan.
    pub fn on_status(&mut self, message: &str, steady_ms: i64, plan_window_s: f64) -> bool {
        if self.said_plan_ms.is_none() || message.is_empty() || message.ends_with('…') {
            return false;
        }
        let asked = self.said_plan_ms.take().unwrap_or(0);
        steady_ms - asked < secs_to_ms(plan_window_s)
    }

    /// Clears the pending plan-status window when `planned` fires.
    pub fn on_planned(&mut self) {
        self.said_plan_ms = None;
    }

    /// Consumes the pending toggle-done notice once the save settles.
    pub fn on_save_finished(&mut self, ok: bool) -> Option<String> {
        let words = std::mem::take(&mut self.done_after_save);
        (ok && !words.is_empty()).then_some(words)
    }

    /// Validates and snaps a drawer-card drop onto `day` at minute `start`.
    pub fn place_homework_plan(
        &self,
        blocks: &[Value],
        block_id: &str,
        day: i64,
        start: i64,
        busy: bool,
    ) -> EngineResult<Option<MovePlan>> {
        let Some(block) = blocks.iter().find(|item| block_id_matches(item, block_id)) else {
            return Ok(None);
        };
        if !self.shown_days.contains(&day) {
            return Ok(None);
        }
        let length = block_duration(block);
        if length <= 0 {
            return Ok(None);
        }
        let snapped = snap(start as f64, self.drag_step)?;
        let clamped = snapped.min(DAY_MIN - length).max(0);
        Ok(Some(MovePlan {
            start: clamped,
            end: clamped + length,
            judge: !busy,
        }))
    }

    /// Validates a direct grid move or resize on any day `0..=6`.
    pub fn move_block_plan(
        &self,
        blocks: &[Value],
        block_id: &str,
        day: i64,
        start: i64,
        end: i64,
        busy: bool,
    ) -> Option<MovePlan> {
        blocks
            .iter()
            .find(|item| block_id_matches(item, block_id))?;
        // Day moves a block on a day the week hides too, so any day of the week is taken here.
        if !(0..=6).contains(&day) || end <= start {
            return None;
        }
        Some(MovePlan {
            start,
            end,
            judge: !busy,
        })
    }

    /// Picks the target block id for "Place now" / Enter on a card (unstarted sessions first)
    /// and opens the plan-status window when a non-empty target is found.
    pub fn plan_one_target(
        &mut self,
        blocks: &[Value],
        identifier: &str,
        steady_ms: i64,
    ) -> Option<String> {
        let mut ordered: Vec<&Value> = blocks.iter().collect();
        ordered.sort_by_key(|item| {
            item.as_object()
                .map(|map| truthy(map.get("start")))
                .unwrap_or(false)
        });
        let target = ordered.into_iter().find_map(|block| {
            let map = block.as_object()?;
            let id = map.get("id").and_then(Value::as_str)?;
            let assignment_id = map.get("assignment_id").and_then(Value::as_str);
            if id == identifier || assignment_id == Some(identifier) {
                Some(id.to_string())
            } else {
                None
            }
        })?;
        if target.is_empty() {
            return None;
        }
        self.said_plan_ms = Some(steady_ms);
        Some(target)
    }

    /// Computes the next completion state and post-save notice for `toggleDone`.
    pub fn toggle_done_plan(
        &self,
        assignments: &Value,
        assignment_id: &str,
        busy: bool,
    ) -> Option<ToggleDonePlan> {
        if busy {
            return None;
        }
        let item = assignments
            .as_object()
            .and_then(|map| map.get(assignment_id))?
            .as_object()?;
        let title = item
            .get("title")
            .and_then(Value::as_str)
            .filter(|text| !text.is_empty())
            .unwrap_or("Homework");
        let finished = !truthy(item.get("completed"));
        let notice = if finished {
            format!("Finished {title}.")
        } else {
            format!("{title} is back.")
        };
        Some(ToggleDonePlan { finished, notice })
    }

    /// Remembers the toggle-done notice when the save went asynchronous.
    pub fn record_done_after_save(&mut self, words: String, busy: bool) {
        if busy {
            self.done_after_save = words;
        }
    }

    /// Applies an optimistic `show_weekends` flip and issues a rollback ticket.
    pub fn toggle_weekends_start(&mut self, prefs: &Value) -> WeekendTogglePlan {
        let mut next = prefs.as_object().cloned().unwrap_or_default();
        let current = bool_pref(&Value::Object(next.clone()), "show_weekends", true);
        let wanted = !current;
        self.weekend_previous = next.get("show_weekends").cloned();
        self.weekend_save += 1;
        let ticket = self.weekend_save;
        next.insert("show_weekends".to_string(), Value::Bool(wanted));
        WeekendTogglePlan {
            ticket,
            wanted,
            preferences: Value::Object(next),
        }
    }

    /// Restores the prior `show_weekends` preference if the active ticket failed to save.
    pub fn toggle_weekends_finish(
        &self,
        ticket: u64,
        ok: bool,
        latest_prefs: &Value,
    ) -> Option<WeekendRollback> {
        if ok || ticket != self.weekend_save {
            return None;
        }
        let mut restored = latest_prefs.as_object().cloned().unwrap_or_default();
        match &self.weekend_previous {
            Some(previous) => {
                restored.insert("show_weekends".to_string(), previous.clone());
            }
            None => {
                restored.shift_remove("show_weekends");
            }
        }
        Some(WeekendRollback {
            preferences: Value::Object(restored),
            message: WEEKEND_SAVE_FAILED,
        })
    }
}
