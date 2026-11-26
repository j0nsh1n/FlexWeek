//! Unfinished homework lists, planner demand counts and "Plan into this week" preparation (P4
//! group 5, slice 5C): the pure decisions behind `desktop/native/controller.py`'s count and
//! unfinished methods. The window keeps one-shot flags (`consume_unfinished`), provisional edit
//! rollback, `solve` dispatch and `did_these`.

use std::collections::{BTreeMap, HashSet};

use flexweek_engine::desk::{calendar, clipboard, grid, planning, reuse, weekmodel};
use flexweek_engine::stored::truthy;
use flexweek_engine::{model, plan, time};
use serde_json::{Map, Value, json};

pub const WEEK_OVER: &str = "That week is over. Open this week or a later one, then plan again.";
pub const ALREADY_FULLY_PLANNED: &str = "There's no time left to plan for this homework.";
pub const ALREADY_HAS_TIME: &str = "There's no time left to plan for this homework.";

/// A local clock reading passed in explicitly so every count and cutoff stays pure.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ClockNow<'a> {
    pub today: &'a str,
    pub hour: i64,
    pub minute: i64,
    pub second: i64,
    pub microsecond: i64,
}

impl<'a> ClockNow<'a> {
    pub fn at(today: &'a str, hour: i64, minute: i64) -> Self {
        Self {
            today,
            hour,
            minute,
            second: 0,
            microsecond: 0,
        }
    }
}

/// A stored Monday is `is_week_start`, which is what the week save checks and
/// which includes 1999-12-27. A week shown from another weekday is any
/// supported calendar date. Either one may be opened; 2100-01-04 is neither.
fn accepted_week_start(week_start: &str) -> bool {
    time::is_week_start(week_start) || time::is_calendar_date(week_start)
}

fn validate_clock(now: &ClockNow<'_>) -> Result<(), String> {
    // The clock is any real date; only deadlines are held to 2000..2099.
    if time::week_start_on(now.today, 0).is_err() {
        return Err(format!("today must be YYYY-MM-DD, got {:?}", now.today));
    }
    if !(0..=23).contains(&now.hour) {
        return Err(format!("hour must be 0..=23, got {}", now.hour));
    }
    if !(0..=59).contains(&now.minute) {
        return Err(format!("minute must be 0..=59, got {}", now.minute));
    }
    if !(0..=59).contains(&now.second) {
        return Err(format!("second must be 0..=59, got {}", now.second));
    }
    if !(0..=999_999).contains(&now.microsecond) {
        return Err(format!(
            "microsecond must be 0..=999999, got {}",
            now.microsecond
        ));
    }
    Ok(())
}

/// Every block row, and every saved-week row, must carry a text id before any date branch reads them.
fn check_blocks(blocks: &[Value], basis: &[Value]) -> Result<(), String> {
    for block in blocks.iter().chain(basis) {
        block_id(block)?;
    }
    Ok(())
}

fn screen_now(week_start: &str, now: &ClockNow<'_>) -> Result<Option<Value>, String> {
    Ok(
        planning::screen_point(week_start, now.today, now.hour, now.minute)
            .map_err(|err| err.message)?
            .map(|(day, minute)| json!([day, minute])),
    )
}

pub fn overdue_ids(
    assignments: &Map<String, Value>,
    now: &ClockNow<'_>,
) -> Result<Vec<String>, String> {
    // Match Python's `(now.date(), now.hour * 60 + now.minute)` so 23:59 is still before END_OF_DAY_MIN (1440).
    // ISO dates of four digits sort as text, so the clock date needs no deadline-range parse.
    let moment = (now.today, now.hour * 60 + now.minute);
    let mut ids = Vec::new();
    for (key, item) in assignments {
        if truthy(item.get("completed")) {
            continue;
        }
        let Some(due) = item
            .get("due")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
        else {
            continue;
        };
        let (due_day, due_minute) = model::parse_due(due).map_err(|err| err.message)?;
        if (due_day.to_string().as_str(), due_minute) <= moment {
            ids.push(key.clone());
        }
    }
    Ok(ids)
}

fn block_id(block: &Value) -> Result<&str, String> {
    block
        .get("id")
        .and_then(Value::as_str)
        .ok_or_else(|| "block is missing a text id".to_string())
}

fn pinned_past_minutes_in_ended_week(
    blocks: &[Value],
    open_week: &[Value],
) -> Result<BTreeMap<String, i64>, String> {
    let mut kept = HashSet::with_capacity(open_week.len());
    for block in open_week {
        kept.insert(block_id(block)?);
    }
    let mut pinned = BTreeMap::new();
    for block in blocks {
        let Some(homework) = block
            .get("assignment_id")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
        else {
            continue;
        };
        if truthy(block.get("start")) && !kept.contains(block_id(block)?) {
            let duration = block
                .get("duration_min")
                .and_then(Value::as_i64)
                .unwrap_or(0);
            *pinned.entry(homework.to_string()).or_insert(0) += duration;
        }
    }
    Ok(pinned)
}

fn missed_minutes_in_ended_week(
    blocks: &[Value],
    open_week: &[Value],
) -> Result<BTreeMap<String, i64>, String> {
    let mut had_time = HashSet::new();
    for block in blocks {
        if truthy(block.get("start")) {
            had_time.insert(block_id(block)?);
        }
    }
    let mut missed = BTreeMap::new();
    for block in open_week {
        let Some(homework) = block
            .get("assignment_id")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
        else {
            continue;
        };
        if had_time.contains(block_id(block)?) && !truthy(block.get("start")) {
            let duration = block
                .get("duration_min")
                .and_then(Value::as_i64)
                .unwrap_or(0);
            *missed.entry(homework.to_string()).or_insert(0) += duration;
        }
    }
    Ok(missed)
}

/// Inputs for [`homework_counts`]: one week snapshot, its server count basis and the clock.
pub struct HomeworkCountsInput<'a> {
    pub week_start: &'a str,
    pub first_weekday: u32,
    pub blocks: &'a [Value],
    pub assignments: &'a Map<String, Value>,
    pub assignments_basis: &'a [Value],
    pub now: ClockNow<'a>,
}

/// One assignment's waiting, uncovered, missed and pinned-past minutes for the open week.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HomeworkNeed {
    pub assignment_id: String,
    pub title: Value,
    pub minutes: i64,
    pub waiting_min: i64,
    pub uncovered_min: i64,
    pub missed_min: Option<i64>,
    pub pinned_min: Option<i64>,
    pub period: String,
}

impl HomeworkNeed {
    /// The shape `homework_time_needed()` exposes: `missed_min` and `pinned_min` appear only when set.
    pub fn to_needed_json(&self) -> Value {
        let mut fields = Map::new();
        fields.insert("assignment_id".into(), json!(self.assignment_id));
        fields.insert("title".into(), self.title.clone());
        fields.insert("minutes".into(), json!(self.minutes));
        fields.insert("period".into(), json!(self.period));
        if let Some(missed) = self.missed_min {
            fields.insert("missed_min".into(), json!(missed));
        }
        if let Some(pinned) = self.pinned_min {
            fields.insert("pinned_min".into(), json!(pinned));
        }
        Value::Object(fields)
    }

    /// The shape `_time_split()` exposes.
    pub fn to_part_json(&self) -> Value {
        json!({
            "assignment_id": self.assignment_id,
            "title": self.title,
            "minutes": self.minutes,
            "waiting_min": self.waiting_min,
            "uncovered_min": self.uncovered_min,
            "period": self.period,
        })
    }
}

/// Drawer remainder entry: homework with minutes that no session holds (outside ended-week pins).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HomeworkRemainder {
    pub title: Value,
    pub minutes: i64,
    pub assignment_id: String,
}

/// Per-assignment minutes computed once against the open week and basis.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AssignmentMinutes {
    pub done_sessions_min: i64,
    pub done_time_min: i64,
    pub uncovered_min: i64,
    pub remaining_min: i64,
    pub overdue: bool,
}

/// Unified planner and drawer counts for one week snapshot.
#[derive(Debug, Clone, PartialEq)]
pub struct HomeworkCounts {
    pub open_week: Vec<Value>,
    pub missed_block_ids: Vec<String>,
    pub missed_minutes: BTreeMap<String, i64>,
    pub pinned_past_minutes: BTreeMap<String, i64>,
    pub items: Vec<HomeworkNeed>,
    pub plan_can_place: bool,
    pub remainders: Vec<HomeworkRemainder>,
    pub open_count: i64,
    pub waiting_only_count: i64,
    pub overdue_assignment_ids: Vec<String>,
    pub per_assignment: BTreeMap<String, AssignmentMinutes>,
}

impl HomeworkCounts {
    pub fn to_json(&self) -> Value {
        let needed: Vec<Value> = self
            .items
            .iter()
            .map(HomeworkNeed::to_needed_json)
            .collect();
        let parts: Vec<Value> = self.items.iter().map(HomeworkNeed::to_part_json).collect();
        let remainders: Vec<Value> = self
            .remainders
            .iter()
            .map(|row| json!([row.title, row.minutes, row.assignment_id]))
            .collect();
        let mut per_assignment = Map::new();
        for (id, counts) in &self.per_assignment {
            per_assignment.insert(
                id.clone(),
                json!({
                    "done_sessions_min": counts.done_sessions_min,
                    "done_time_min": counts.done_time_min,
                    "uncovered_min": counts.uncovered_min,
                    "remaining_min": counts.remaining_min,
                    "overdue": counts.overdue,
                }),
            );
        }
        json!({
            "open_week": self.open_week,
            "missed_block_ids": self.missed_block_ids,
            "missed_minutes": self.missed_minutes,
            "pinned_past_minutes": self.pinned_past_minutes,
            "needed": needed,
            "parts": parts,
            "plan_can_place": self.plan_can_place,
            "remainders": remainders,
            "open_count": self.open_count,
            "waiting_only_count": self.waiting_only_count,
            "overdue_assignment_ids": self.overdue_assignment_ids,
            "per_assignment": Value::Object(per_assignment),
        })
    }
}

/// Compute every homework demand, missed, pinned-past, done-time and overdue count from one read of
/// the open week and clock.
pub fn homework_counts(input: HomeworkCountsInput<'_>) -> Result<HomeworkCounts, String> {
    validate_clock(&input.now)?;
    check_blocks(input.blocks, input.assignments_basis)?;
    if !accepted_week_start(input.week_start) {
        return Err("week_start must be a date written YYYY-MM-DD".to_string());
    }
    let now_point = screen_now(input.week_start, &input.now)?;
    let assignments_val = Value::Object(input.assignments.clone());
    let open_week = planning::without_missed_times(
        input.blocks,
        &assignments_val,
        input.assignments_basis,
        now_point.as_ref(),
    )
    .map_err(|err| err.message)?;
    let missed_raw = planning::missed_session_ids(
        input.blocks,
        &assignments_val,
        input.assignments_basis,
        now_point.as_ref(),
    )
    .map_err(|err| err.message)?;
    let mut missed_block_ids = Vec::with_capacity(missed_raw.len());
    for id in missed_raw {
        let Some(text) = id.as_str() else {
            return Err("missed session id is not text".to_string());
        };
        missed_block_ids.push(text.to_string());
    }

    let today_week =
        time::week_start_on(input.now.today, input.first_weekday).map_err(|err| err.message)?;
    let week_is_over = !input.week_start.is_empty() && today_week.as_str() > input.week_start;
    let (missed_minutes, pinned_past_minutes) = if week_is_over {
        (
            missed_minutes_in_ended_week(input.blocks, &open_week)?,
            pinned_past_minutes_in_ended_week(input.blocks, &open_week)?,
        )
    } else {
        (BTreeMap::new(), BTreeMap::new())
    };

    let raw_parts = planning::time_still_needed_parts(
        input.assignments,
        &open_week,
        input.week_start,
        input.assignments_basis,
    )
    .map_err(|err| err.message)?;

    let mut items = Vec::with_capacity(raw_parts.len());
    let mut plan_can_place = false;
    let mut remainders = Vec::new();
    let mut open_count = 0;
    let mut waiting_only_count = 0;

    for part in raw_parts {
        let assignment_id = part
            .get("assignment_id")
            .and_then(Value::as_str)
            .ok_or_else(|| "time_still_needed_parts item missing assignment_id".to_string())?
            .to_string();
        let title = part.get("title").cloned().unwrap_or(Value::Null);
        let minutes = part.get("minutes").and_then(Value::as_i64).unwrap_or(0);
        let waiting_min = part.get("waiting_min").and_then(Value::as_i64).unwrap_or(0);
        let uncovered_min = part
            .get("uncovered_min")
            .and_then(Value::as_i64)
            .unwrap_or(0);
        let period = part
            .get("period")
            .and_then(Value::as_str)
            .unwrap_or("later")
            .to_string();

        let missed_val = missed_minutes.get(&assignment_id).copied().unwrap_or(0);
        let missed_min = (missed_val != 0).then_some(missed_val);
        let pinned_val = pinned_past_minutes
            .get(&assignment_id)
            .copied()
            .unwrap_or(0);
        let pinned_min = (pinned_val != 0).then(|| pinned_val.min(minutes - missed_val));

        if waiting_min != 0 || planning::floor_slot(uncovered_min) > 0 {
            plan_can_place = true;
        }
        if waiting_min > 0 {
            open_count += 1;
            if uncovered_min == 0 {
                waiting_only_count += 1;
            }
        }
        if uncovered_min > pinned_val {
            remainders.push(HomeworkRemainder {
                title: title.clone(),
                minutes: uncovered_min - pinned_val,
                assignment_id: assignment_id.clone(),
            });
        }

        items.push(HomeworkNeed {
            assignment_id,
            title,
            minutes,
            waiting_min,
            uncovered_min,
            missed_min,
            pinned_min,
            period,
        });
    }

    let overdue_assignment_ids = overdue_ids(input.assignments, &input.now)?;
    let overdue_set: HashSet<&str> = overdue_assignment_ids.iter().map(String::as_str).collect();

    let open_week_val = Value::Array(open_week.clone());
    let saved_val = Value::Array(input.assignments_basis.to_vec());
    let mut per_assignment = BTreeMap::new();
    for (key, assignment) in input.assignments {
        let id_val = assignment.get("id").cloned().unwrap_or(Value::Null);
        let done_sessions_min =
            planning::credited_done_minutes(assignment, &id_val, &open_week_val, &saved_val)
                .map_err(|err| err.message)?;
        let focus = assignment
            .get("focus_minutes")
            .and_then(Value::as_i64)
            .unwrap_or(0);
        // Reuse the same credited session minutes with focus time for done time.
        let done_time_min = plan::done_time(focus, done_sessions_min);
        let uncovered_min =
            planning::uncovered_homework_minutes(assignment, &open_week_val, &saved_val)
                .map_err(|err| err.message)?;
        let remaining_min = planning::floor_slot(uncovered_min);
        per_assignment.insert(
            key.clone(),
            AssignmentMinutes {
                done_sessions_min,
                done_time_min,
                uncovered_min,
                remaining_min,
                overdue: overdue_set.contains(key.as_str()),
            },
        );
    }

    Ok(HomeworkCounts {
        open_week,
        missed_block_ids,
        missed_minutes,
        pinned_past_minutes,
        items,
        plan_can_place,
        remainders,
        open_count,
        waiting_only_count,
        overdue_assignment_ids,
        per_assignment,
    })
}

/// Inputs for [`unfinished_items`] and [`left_unfinished_items`].
pub struct UnfinishedInput<'a> {
    pub week_start: &'a str,
    pub first_weekday: u32,
    pub blocks: &'a [Value],
    pub assignments: &'a Map<String, Value>,
    pub assignments_basis: &'a [Value],
    pub saved_weeks: &'a [String],
    pub stored_parts: &'a [Value],
    pub now: ClockNow<'a>,
}

/// Unfinished homework for the shown week: "Left from last week" shows only on the shown week that
/// holds today; overdue homework shows on every week.
pub fn unfinished_items(input: UnfinishedInput<'_>) -> Result<Vec<Value>, String> {
    validate_clock(&input.now)?;
    check_blocks(input.blocks, input.assignments_basis)?;
    if !accepted_week_start(input.week_start) {
        return Err("week_start must be a date written YYYY-MM-DD".to_string());
    }
    let today_week =
        time::week_start_on(input.now.today, input.first_weekday).map_err(|err| err.message)?;
    let here = input.week_start == today_week;
    let first_part = if here && input.stored_parts.len() == 2 {
        let Some(blocks) = input.stored_parts[0].get("blocks").filter(|v| v.is_array()) else {
            return Err("the first stored part has no blocks list".to_string());
        };
        blocks.clone()
    } else {
        Value::Array(Vec::new())
    };
    let now_point = screen_now(input.week_start, &input.now)?;
    let assignments_val = Value::Object(input.assignments.clone());
    let open_week = planning::without_missed_times(
        input.blocks,
        &assignments_val,
        input.assignments_basis,
        now_point.as_ref(),
    )
    .map_err(|err| err.message)?;
    let moment = model::clock_moment(input.now.today, input.now.hour, input.now.minute)
        .map_err(|err| err.message)?;
    let saved_weeks = Value::Array(input.saved_weeks.iter().map(|s| json!(s)).collect());
    let items = clipboard::left_over_items_at(
        &assignments_val,
        &saved_weeks,
        &today_week,
        moment,
        &Value::Array(open_week),
        &Value::Array(input.assignments_basis.to_vec()),
        &first_part,
    )
    .map_err(|err| err.message)?;
    Ok(items
        .into_iter()
        .filter(|item| {
            here || item.get("left_over_state").and_then(Value::as_str) == Some("overdue")
        })
        .collect())
}

/// Only the items left from an earlier week (matches `NativeSession.left_unfinished`).
pub fn left_unfinished_items(input: UnfinishedInput<'_>) -> Result<Vec<Value>, String> {
    Ok(unfinished_items(input)?
        .into_iter()
        .filter(|item| {
            item.get("left_over_state").and_then(Value::as_str) == Some("left_from_last_week")
        })
        .collect())
}

fn too_short_message(item: Option<&Value>, left_min: i64) -> String {
    let Some(item) = item else {
        return String::new();
    };
    if left_min <= 0 {
        return String::new();
    }
    let title = item
        .get("title")
        .and_then(Value::as_str)
        .filter(|text| !text.is_empty())
        .unwrap_or("This homework");
    format!(
        "{title} has {} left. Plan needs at least 15 minutes.",
        weekmodel::length_label(left_min)
    )
}

/// Inputs for [`unfinished_preview`], the single-homework preview builder (`plan_unfinished`).
pub struct UnfinishedPreviewInput<'a> {
    pub week_start: &'a str,
    pub blocks: &'a [Value],
    pub assignments: &'a Map<String, Value>,
    pub assignments_basis: &'a [Value],
    pub assignment_id: &'a str,
    pub now: ClockNow<'a>,
    /// Date used by `first_plannable_day(week_start)` (wall clock today in the desktop window).
    pub plannable_today: &'a str,
}

#[derive(Debug, Clone, PartialEq)]
pub enum UnfinishedPreview {
    Say(String),
    Rows(Vec<Value>),
}

impl UnfinishedPreview {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "say": words }),
            Self::Rows(rows) => json!({ "rows": rows }),
        }
    }
}

/// Build the single preview row for planning one unfinished homework, or explain why nothing can be
/// added (under 15 minutes left, or already fully planned).
pub fn unfinished_preview(
    input: UnfinishedPreviewInput<'_>,
    block_id_str: &str,
) -> Result<UnfinishedPreview, String> {
    validate_clock(&input.now)?;
    check_blocks(input.blocks, input.assignments_basis)?;
    if !accepted_week_start(input.week_start) {
        return Err("week_start must be a date written YYYY-MM-DD".to_string());
    }
    // Wall-clock today may be any real date, like the session clock.
    if time::week_start_on(input.plannable_today, 0).is_err() {
        return Err(format!(
            "plannable_today must be YYYY-MM-DD, got {:?}",
            input.plannable_today
        ));
    }
    let now_point = screen_now(input.week_start, &input.now)?;
    let assignments_val = Value::Object(input.assignments.clone());
    let open_week = planning::without_missed_times(
        input.blocks,
        &assignments_val,
        input.assignments_basis,
        now_point.as_ref(),
    )
    .map_err(|err| err.message)?;
    let open_week_val = Value::Array(open_week);
    let saved_val = Value::Array(input.assignments_basis.to_vec());

    let item = input.assignments.get(input.assignment_id);
    let left_min = match item {
        Some(found) => planning::uncovered_homework_minutes(found, &open_week_val, &saved_val)
            .map_err(|err| err.message)?,
        None => 0,
    };
    let minutes = planning::floor_slot(left_min);
    let Some(item) = item.filter(|_| minutes >= 15) else {
        let short = too_short_message(item, left_min);
        let words = if short.is_empty() {
            ALREADY_FULLY_PLANNED.to_string()
        } else {
            short
        };
        return Ok(UnfinishedPreview::Say(words));
    };

    let due_day = grid::due_day_of(item.get("due").unwrap_or(&Value::Null), input.week_start)
        .map_err(|err| err.message)?;
    let first_day = grid::first_plannable_day(input.week_start, input.plannable_today)
        .map_err(|err| err.message)?;
    let days = calendar::days_through(due_day, first_day);
    let block_days = if days.is_empty() { vec![0] } else { days };
    let day = block_days[0];
    let mut block = reuse::copied_homework_block(item, day, minutes, block_id_str)
        .map_err(|err| err.message)?;
    if let Some(fields) = block.as_object_mut() {
        fields.insert("days".into(), json!(block_days));
    }
    let row = json!({
        "week_start": input.week_start,
        "day": day,
        "fixed": false,
        "block": block,
        "group_id": block_id_str,
        "checked": true,
        "invalid": "",
        "original_duration": minutes,
    });
    Ok(UnfinishedPreview::Rows(vec![row]))
}

/// Inputs for [`plan_unfinished`] ("Plan into this week", `NativeSession.plan_left`).
pub struct UnfinishedPlanInput<'a> {
    pub week_start: &'a str,
    pub blocks: &'a [Value],
    pub assignments: &'a Map<String, Value>,
    pub assignments_basis: &'a [Value],
    pub assignment_ids: &'a [String],
    pub now: ClockNow<'a>,
}

/// Result of preparing unfinished or overdue homework for a solve run.
#[derive(Debug, Clone, PartialEq)]
pub enum UnfinishedPlan {
    /// Nothing to solve: show these words instead.
    Say(String),
    /// Provisional blocks (with any new sessions appended), newly created block IDs, and separate
    /// ordinary vs. overdue solve targets (disjoint; their union is `targets`).
    Ready {
        blocks: Vec<Value>,
        made: Vec<String>,
        ordinary_targets: Vec<String>,
        overdue_targets: Vec<String>,
    },
}

impl UnfinishedPlan {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Say(words) => json!({ "say": words }),
            Self::Ready {
                blocks,
                made,
                ordinary_targets,
                overdue_targets,
            } => {
                let mut targets =
                    Vec::with_capacity(ordinary_targets.len() + overdue_targets.len());
                targets.extend(ordinary_targets.iter().cloned());
                targets.extend(overdue_targets.iter().cloned());
                json!({
                    "blocks": blocks,
                    "made": made,
                    "ordinary_targets": ordinary_targets,
                    "overdue_targets": overdue_targets,
                    "targets": targets,
                })
            }
        }
    }
}

fn push_unique(list: &mut Vec<String>, seen: &mut HashSet<String>, id: String) {
    if seen.insert(id.clone()) {
        list.push(id);
    }
}

/// Prepare provisional blocks and solve targets for "Plan into this week" (`plan_left`).
///
/// Ordinary targets collect waiting, missed and newly created sessions for non-overdue homework;
/// overdue targets collect all non-completed, non-pinned-past sessions and newly created sessions
/// for overdue homework. Pinned past sessions stay out of both target lists while their minutes
/// remain uncovered so a new session is created for them.
pub fn plan_unfinished(
    input: UnfinishedPlanInput<'_>,
    ids: &mut impl Iterator<Item = String>,
) -> Result<UnfinishedPlan, String> {
    validate_clock(&input.now)?;
    check_blocks(input.blocks, input.assignments_basis)?;
    if !accepted_week_start(input.week_start) {
        return Err("week_start must be a date written YYYY-MM-DD".to_string());
    }
    let start = planning::plan_start_at(
        input.week_start,
        input.now.today,
        input.now.hour,
        input.now.minute,
        input.now.second,
        input.now.microsecond,
    )
    .map_err(|err| err.message)?;
    if start.is_some_and(|(day, _)| day > 6) {
        return Ok(UnfinishedPlan::Say(WEEK_OVER.to_string()));
    }
    let first_day = start.map_or(0, |(day, _)| day);

    let overdue_list = overdue_ids(input.assignments, &input.now)?;
    let overdue: HashSet<&str> = overdue_list.iter().map(String::as_str).collect();

    let now_point = screen_now(input.week_start, &input.now)?;
    let assignments_val = Value::Object(input.assignments.clone());
    let mut open_blocks = planning::without_missed_times(
        input.blocks,
        &assignments_val,
        input.assignments_basis,
        now_point.as_ref(),
    )
    .map_err(|err| err.message)?;
    let missed_raw = planning::missed_session_ids(
        input.blocks,
        &assignments_val,
        input.assignments_basis,
        now_point.as_ref(),
    )
    .map_err(|err| err.message)?;

    let mut missed_id_set = HashSet::with_capacity(missed_raw.len());
    for id in &missed_raw {
        let Some(text) = id.as_str() else {
            return Err("missed session id is not text".to_string());
        };
        missed_id_set.insert(text.to_string());
    }

    let mut timeless = HashSet::new();
    for block in &open_blocks {
        if !truthy(block.get("start")) {
            timeless.insert(block_id(block)?.to_string());
        }
    }
    let mut missed = HashSet::new();
    let mut pinned_past = HashSet::new();
    for block in input.blocks {
        let id = block_id(block)?;
        if truthy(block.get("start")) && timeless.contains(id) {
            missed.insert(id.to_string());
        }
        if truthy(block.get("pinned")) && missed_id_set.contains(id) {
            pinned_past.insert(id.to_string());
        }
    }

    let saved_val = Value::Array(input.assignments_basis.to_vec());
    let mut blocks = input.blocks.to_vec();
    let mut made = Vec::new();
    let mut made_seen = HashSet::new();
    let mut ordinary_targets = Vec::new();
    let mut ordinary_seen = HashSet::new();
    let mut overdue_targets = Vec::new();
    let mut overdue_seen = HashSet::new();
    let mut short = String::new();

    for assignment_id in input.assignment_ids {
        let Some(item) = input.assignments.get(assignment_id) else {
            continue;
        };
        if truthy(item.get("completed")) {
            continue;
        }
        let late = overdue.contains(assignment_id.as_str());
        for block in &blocks {
            let matches_assignment =
                block.get("assignment_id").and_then(Value::as_str) == Some(assignment_id.as_str());
            let id = block_id(block)?;
            if !matches_assignment || truthy(block.get("completed")) || pinned_past.contains(id) {
                continue;
            }
            if truthy(block.get("start")) && !late && !missed.contains(id) {
                continue;
            }
            if late {
                push_unique(&mut overdue_targets, &mut overdue_seen, id.to_string());
            } else {
                push_unique(&mut ordinary_targets, &mut ordinary_seen, id.to_string());
            }
        }

        let open_val = Value::Array(open_blocks.clone());
        let left_min = planning::uncovered_homework_minutes(item, &open_val, &saved_val)
            .map_err(|err| err.message)?;
        let minutes = planning::floor_slot(left_min);
        if minutes < 15 {
            if short.is_empty() {
                short = too_short_message(Some(item), left_min);
            }
            continue;
        }

        let days = if late {
            (first_day..7).collect()
        } else {
            let due_day =
                grid::due_day_of(item.get("due").unwrap_or(&Value::Null), input.week_start)
                    .map_err(|err| err.message)?;
            calendar::days_through(due_day, first_day)
        };
        let block_days = if days.is_empty() { vec![0] } else { days };
        let new_id = ids
            .next()
            .ok_or_else(|| "not enough block ids for unfinished homework".to_string())?;
        let mut block = reuse::copied_homework_block(item, block_days[0], minutes, &new_id)
            .map_err(|err| err.message)?;
        if let Some(fields) = block.as_object_mut() {
            fields.insert("days".into(), json!(block_days));
        }
        blocks.push(block.clone());
        // A newly added session has no start, so it appears unchanged in the open week if the same
        // assignment id repeats later in the list.
        open_blocks.push(block);
        push_unique(&mut made, &mut made_seen, new_id.clone());
        if late {
            push_unique(&mut overdue_targets, &mut overdue_seen, new_id);
        } else {
            push_unique(&mut ordinary_targets, &mut ordinary_seen, new_id);
        }
    }

    if ordinary_targets.is_empty() && overdue_targets.is_empty() {
        let words = if short.is_empty() {
            ALREADY_HAS_TIME.to_string()
        } else {
            short
        };
        return Ok(UnfinishedPlan::Say(words));
    }

    Ok(UnfinishedPlan::Ready {
        blocks,
        made,
        ordinary_targets,
        overdue_targets,
    })
}
