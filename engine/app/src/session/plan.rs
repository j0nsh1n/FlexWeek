//! Plan, Replan, Place now and Find a new time decisions (P4 group 5A): the pure rules of
//! `desktop/native/controller.py`'s `solve`, `first_placed`, `left_sentence`, `plan_sentence`,
//! `_place_now_sentence` and `_apply_auto_split`. The window keeps the requests, callbacks,
//! early-week traversal, history and saves, and applies what is decided here.

use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

use flexweek_engine::desk::{planning, pomodoro, weekmodel};
use flexweek_engine::shown;
use flexweek_service::blocks::check_block;
use serde_json::{Map, Value, json};

pub const WEEK_OVER: &str =
    "This week is over, so nothing was planned. Plan this week or a later one.";
pub const LEFT_NAMED: usize = 2;

const PLANNING_BUSY: &str = "Planning\u{2026} one moment.";
const WEEK_CONFLICT: &str =
    "This week changed in another window. Choose More > Reload this week, then try again.";
const SAVING_WAIT: &str = "Saving your last change\u{2026} Plan will work in a moment.";

/// Local wall clock read by the host for planning decisions.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PlanClock<'a> {
    pub today_iso: &'a str,
    pub hour: i64,
    pub minute: i64,
    pub second: i64,
    pub microsecond: i64,
}

/// Everything `prepare_plan` needs to decide whether to refuse, fetch earlier weeks, stop empty,
/// or send a `/api/solve` request.
pub struct PlanInput<'a> {
    pub planning: bool,
    pub conflict: bool,
    pub pending_save: bool,
    pub week_start: &'a str,
    pub blocks: &'a [Value],
    pub assignments: &'a Map<String, Value>,
    pub assignments_basis: &'a [Value],
    pub preferences: Option<&'a Value>,
    pub saved_weeks: &'a [String],
    pub split_whole: &'a [String],
    pub clock: PlanClock<'a>,
    pub everything: bool,
    pub only: Option<&'a [String]>,
    pub earliest_first: bool,
    pub prepared_weeks: Option<&'a Map<String, Value>>,
    pub overdue: Option<&'a [String]>,
}

/// What `prepare_plan` decides to do before talking to `/api/solve`.
#[derive(Debug, Clone, PartialEq)]
pub enum PlanPreparation {
    /// Refused before touching selection or the week.
    Blocked {
        message: String,
        replan_after_save: bool,
    },
    /// The shown week has already ended; refused before earlier-week fetches or solving.
    WeekOver { message: String },
    /// Earlier saved weeks must be fetched before planning.
    FetchEarlier { weeks: Vec<String> },
    /// Nothing needs a time from this plan.
    Empty,
    /// Ready to POST `body` to `/api/solve`.
    Ready {
        body: Value,
        targets: Vec<String>,
        prior_updates: Vec<Value>,
        shares: Vec<Value>,
        week: Vec<Value>,
    },
}

impl PlanPreparation {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Blocked {
                message,
                replan_after_save,
            } => json!({
                "kind": "blocked",
                "message": message,
                "replan_after_save": replan_after_save,
            }),
            Self::WeekOver { message } => json!({
                "kind": "week_over",
                "message": message,
            }),
            Self::FetchEarlier { weeks } => json!({
                "kind": "fetch_earlier",
                "weeks": weeks,
            }),
            Self::Empty => json!({
                "kind": "empty",
            }),
            Self::Ready {
                body,
                targets,
                prior_updates,
                shares,
                week,
            } => json!({
                "kind": "ready",
                "body": body,
                "targets": targets,
                "prior_updates": prior_updates,
                "shares": shares,
                "week": week,
            }),
        }
    }
}

/// Everything `apply_plan_answer` needs once `/api/solve` returns a trace.
pub struct PlanAnswerInput<'a> {
    pub original_blocks: &'a [Value],
    pub source_week: &'a [Value],
    pub trace: &'a Value,
    pub targets: &'a [String],
    pub assignments: &'a Map<String, Value>,
    pub assignments_basis: &'a [Value],
    pub week_start: &'a str,
    pub preferences: Option<&'a Value>,
    pub shares: &'a [Value],
    pub needs_time: &'a Map<String, Value>,
    pub clock: PlanClock<'a>,
    pub earliest_first: bool,
    pub overdue: Option<&'a [String]>,
    pub new_left: Option<&'a [String]>,
}

/// The week, trace, counts, notices and change flag produced from `/api/solve`'s answer.
#[derive(Debug, Clone, PartialEq)]
pub struct PlanAnswer {
    pub blocks: Vec<Value>,
    pub trace: Value,
    pub needs_time: Map<String, Value>,
    pub reasons: BTreeMap<String, String>,
    pub plan_remainders: Vec<(String, i64)>,
    pub plan_counts: (i64, i64),
    pub plan_open: i64,
    pub plan_first: Option<(i64, i64)>,
    pub split_count: i64,
    pub split_note: String,
    pub changed: bool,
    pub placed_note: String,
    pub placed_where: String,
}

impl PlanAnswer {
    pub fn to_json(&self) -> Value {
        let remainders: Vec<Value> = self
            .plan_remainders
            .iter()
            .map(|(title, minutes)| json!([title, minutes]))
            .collect();
        let first = self
            .plan_first
            .map(|(day, minute)| json!([day, minute]))
            .unwrap_or(Value::Null);
        json!({
            "blocks": self.blocks,
            "trace": self.trace,
            "needs_time": Value::Object(self.needs_time.clone()),
            "reasons": self.reasons,
            "plan_remainders": remainders,
            "plan_counts": [self.plan_counts.0, self.plan_counts.1],
            "plan_open": self.plan_open,
            "plan_first": first,
            "split_count": self.split_count,
            "split_note": self.split_note,
            "changed": self.changed,
            "placed_note": self.placed_note,
            "placed_where": self.placed_where,
        })
    }
}

/// The result of turning placed homework blocks into focus chunks and breaks.
#[derive(Debug, Clone, PartialEq)]
pub struct AutoSplit {
    pub blocks: Vec<Value>,
    pub count: i64,
    pub note: String,
}

impl AutoSplit {
    pub fn to_json(&self) -> Value {
        json!({
            "blocks": self.blocks,
            "count": self.count,
            "note": self.note,
        })
    }
}

fn truthy(value: Option<&Value>) -> bool {
    match value {
        None | Some(Value::Null) => false,
        Some(Value::Bool(flag)) => *flag,
        Some(Value::Number(number)) => number.as_f64().is_some_and(|n| n != 0.0),
        Some(Value::String(text)) => !text.is_empty(),
        Some(Value::Array(items)) => !items.is_empty(),
        Some(Value::Object(fields)) => !fields.is_empty(),
    }
}

fn block_id(block: &Value) -> Option<&str> {
    block.get("id").and_then(Value::as_str)
}

impl PlanClock<'_> {
    /// The ranges Python's `datetime.time` allows; anything else is refused before arithmetic.
    fn check(&self) -> Result<(), String> {
        let ranges = [
            ("hour", self.hour, 23),
            ("minute", self.minute, 59),
            ("second", self.second, 59),
            ("microsecond", self.microsecond, 999_999),
        ];
        for (name, value, top) in ranges {
            if !(0..=top).contains(&value) {
                return Err(format!("clock {name} must be 0 to {top}, got {value}"));
            }
        }
        Ok(())
    }
}

/// A field that may be missing or null but otherwise must be a string.
fn opt_text<'a>(item: &'a Value, key: &str) -> Result<Option<&'a str>, String> {
    match item.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) => Ok(Some(text.as_str())),
        Some(_) => Err(format!("{key} must be a string or null")),
    }
}

/// A field that may be missing or null but otherwise must be a whole number.
fn opt_int(item: &Value, key: &str) -> Result<Option<i64>, String> {
    match item.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => value
            .as_i64()
            .map(Some)
            .ok_or_else(|| format!("{key} must be a whole number or null")),
    }
}

/// The first day of a block's `days`, which may be missing or null but otherwise must be a list
/// of whole numbers.
fn first_day_of(item: &Value) -> Result<Option<i64>, String> {
    match item.get("days") {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Array(days)) => {
            let mut first = None;
            for day in days {
                let day = day
                    .as_i64()
                    .ok_or_else(|| "days must hold whole numbers".to_string())?;
                first.get_or_insert(day);
            }
            Ok(first)
        }
        Some(_) => Err("days must be a list or null".to_string()),
    }
}

/// The trace's `placed` rows, each checked for the fields the plan reads.
fn placed_rows(trace: &Value) -> Result<&[Value], String> {
    let rows: &[Value] = match trace.get("placed") {
        None | Some(Value::Null) => return Ok(&[]),
        Some(Value::Array(items)) => items.as_slice(),
        Some(_) => return Err("trace placed must be a list".to_string()),
    };
    for row in rows {
        if !row.is_object() {
            return Err("each placed row must be an object".to_string());
        }
        opt_text(row, "id")?;
        opt_text(row, "kind")?;
        opt_text(row, "start")?;
        opt_int(row, "duration_min")?;
        first_day_of(row)?;
    }
    Ok(rows)
}

/// Where the first homework a plan gave a time is, by day and then minute.
pub fn first_placed(trace: &Value, targets: &[String]) -> Result<Option<(i64, i64)>, String> {
    let target_set: HashSet<&str> = targets.iter().map(String::as_str).collect();
    let mut best: Option<(i64, i64)> = None;
    for item in placed_rows(trace)? {
        let Some(id) = block_id(item) else {
            continue;
        };
        if !target_set.contains(id) {
            continue;
        }
        let Some(start) = opt_text(item, "start")?.filter(|text| !text.is_empty()) else {
            continue;
        };
        let Some(day) = first_day_of(item)? else {
            continue;
        };
        let minute = weekmodel::minute_of(start).map_err(|error| error.message)?;
        let minute = i64::try_from(minute).map_err(|_| "start minute out of range".to_string())?;
        let spot = (day, minute);
        if best.is_none_or(|current| spot < current) {
            best = Some(spot);
        }
    }
    Ok(best)
}

/// Homework with minutes the plan could not give a time, each named with its minutes:
/// `" History essay still has 10 min with no time."` Nothing for no homework.
pub fn left_sentence(left: &[(String, i64)]) -> String {
    let mut said = String::new();
    for (title, minutes) in left.iter().take(LEFT_NAMED) {
        said.push_str(&format!(
            " {title} still has {} with no time.",
            weekmodel::length_label(*minutes)
        ));
    }
    if left.len() > LEFT_NAMED {
        said.push_str(&format!(" And {} more.", left.len() - LEFT_NAMED));
    }
    said
}

/// How much homework a plan placed, counting homework only. `waiting` is homework whose sessions
/// found no room; `left` is homework with minutes no session holds, by title and minutes.
pub fn plan_sentence(placed: i64, waiting: i64, left: &[(String, i64)]) -> String {
    let mut said = if placed == 0 {
        "Nothing placed.".to_string()
    } else {
        let suffix = if placed == 1 { "" } else { "s" };
        format!("Placed {placed} homework block{suffix}.")
    };
    if waiting != 0 {
        said.push_str(&format!(" {waiting} with no time yet."));
    }
    said.push_str(&left_sentence(left));
    said
}

/// Where Place now put one block, or that it found no room this week.
pub fn place_now_sentence(block: &Value, week_start: &str) -> Result<String, String> {
    let title = opt_text(block, "title")?
        .filter(|text| !text.is_empty())
        .unwrap_or("this homework");
    let start = opt_text(block, "start")?.filter(|text| !text.is_empty());
    let first_day = first_day_of(block)?;
    let (Some(start), Some(day_index)) = (start, first_day) else {
        return Ok(format!("No free time this week for {title}."));
    };
    let names = shown::day_names(week_start, false).map_err(|error| error.message)?;
    let day = usize::try_from(day_index)
        .ok()
        .and_then(|index| names.get(index))
        .ok_or_else(|| format!("day index {day_index} out of range"))?;
    let time = weekmodel::hhmm_text(start).map_err(|error| error.message)?;
    Ok(format!("Placed {title} on {day} {time}."))
}

/// Turn each placed homework block into focus chunks and breaks when `auto_split_pomodoro` is on.
/// `sources` supplies the pre-inflation work lengths; starts, pins, days and overdue rewrites stay
/// from `blocks`.
pub fn apply_auto_split(
    blocks: &[Value],
    trace: &Value,
    sources: Option<&[Value]>,
    preferences: Option<&Value>,
    next_id: impl FnMut() -> String,
) -> Result<AutoSplit, String> {
    let planned = sources.unwrap_or(blocks);
    let mut work_minutes: HashMap<&str, Value> = HashMap::with_capacity(planned.len());
    for block in planned {
        if let Some(id) = block_id(block) {
            work_minutes.insert(
                id,
                block.get("duration_min").cloned().unwrap_or(Value::Null),
            );
        }
    }
    let mut week = Vec::with_capacity(blocks.len());
    for block in blocks {
        let mut copy = block
            .as_object()
            .cloned()
            .ok_or_else(|| "each block must be an object".to_string())?;
        if let Some(id) = block_id(block)
            && let Some(duration) = work_minutes.get(id)
        {
            copy.insert("duration_min".into(), duration.clone());
        }
        week.push(Value::Object(copy));
    }
    let prefs_val = preferences.cloned().unwrap_or(Value::Null);
    let (split_val, count) =
        pomodoro::split_solved(&Value::Array(week), trace, &prefs_val, next_id)
            .map_err(|error| error.message)?;
    if count == 0 {
        return Ok(AutoSplit {
            blocks: blocks.to_vec(),
            count: 0,
            note: String::new(),
        });
    }
    let split = split_val
        .as_array()
        .cloned()
        .ok_or_else(|| "split_solved returned non-list".to_string())?;
    Ok(AutoSplit {
        blocks: split,
        count,
        note: format!(" Split {count} into focus chunks."),
    })
}

/// Prepare a Plan, Replan, Place now or Find a new time request.
pub fn prepare_plan(input: PlanInput<'_>) -> Result<PlanPreparation, String> {
    if input.planning {
        return Ok(PlanPreparation::Blocked {
            message: PLANNING_BUSY.to_string(),
            replan_after_save: false,
        });
    }
    if input.conflict {
        return Ok(PlanPreparation::Blocked {
            message: WEEK_CONFLICT.to_string(),
            replan_after_save: false,
        });
    }
    if input.pending_save {
        return Ok(PlanPreparation::Blocked {
            message: SAVING_WAIT.to_string(),
            replan_after_save: input.everything,
        });
    }

    input.clock.check()?;
    let start = planning::plan_start_at(
        input.week_start,
        input.clock.today_iso,
        input.clock.hour,
        input.clock.minute,
        input.clock.second,
        input.clock.microsecond,
    )
    .map_err(|error| error.message)?;
    if start.is_some_and(|(day, _)| day > 6) {
        return Ok(PlanPreparation::WeekOver {
            message: WEEK_OVER.to_string(),
        });
    }

    if input.prepared_weeks.is_none() && input.only.is_none() {
        let earlier: Vec<String> = input
            .saved_weeks
            .iter()
            .filter(|week| week.as_str() < input.week_start)
            .cloned()
            .collect();
        if !earlier.is_empty() {
            return Ok(PlanPreparation::FetchEarlier { weeks: earlier });
        }
    }

    let mut prior_input: Vec<Value> = Vec::new();
    if let Some(prepared) = input.prepared_weeks {
        for (week_start, saved) in prepared {
            let mut row = Map::new();
            row.insert("week_start".into(), Value::String(week_start.clone()));
            if let Some(fields) = saved.as_object() {
                for (key, value) in fields {
                    row.insert(key.clone(), value.clone());
                }
            }
            prior_input.push(Value::Object(row));
        }
    }

    let (planning_blocks, prior_updates) = if input.only.is_none() {
        let moved = planning::move_earlier_homework(
            input.blocks,
            &prior_input,
            input.assignments,
            input.week_start,
        )
        .map_err(|error| error.message)?;
        let blocks = moved
            .get("blocks")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let updates = moved
            .get("weeks")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        (blocks, updates)
    } else {
        (input.blocks.to_vec(), Vec::new())
    };

    let mut earlier_blocks: Vec<Value> = Vec::new();
    for week in &prior_input {
        if let Some(blocks) = week.get("blocks").and_then(Value::as_array) {
            for block in blocks {
                if truthy(block.get("start")) && !truthy(block.get("completed")) {
                    earlier_blocks.push(block.clone());
                }
            }
        }
    }

    let now_point = planning::clock_point(
        input.week_start,
        input.clock.today_iso,
        input.clock.hour,
        input.clock.minute,
    )
    .map_err(|error| error.message)?
    .map(|(day, minute)| json!([day, minute]));

    let open_blocks = if input.only.is_some() {
        planning_blocks
    } else {
        planning::open_rest_sessions_at(
            &planning_blocks,
            input.assignments,
            input.week_start,
            &earlier_blocks,
            input.assignments_basis,
            now_point.as_ref(),
        )
        .map_err(|error| error.message)?
    };

    let assignments_val = Value::Object(input.assignments.clone());
    let not_before_val = start.map(|(day, minute)| json!([day, minute]));
    let only_val = input
        .only
        .map(|ids| Value::Array(ids.iter().map(|id| json!(id)).collect()));

    let (mut payload, raw_targets) = planning::solve_request_at(
        &Value::Array(open_blocks.clone()),
        &assignments_val,
        input.week_start,
        input.everything,
        only_val.as_ref(),
        not_before_val.as_ref(),
        false,
        now_point.as_ref(),
        input.assignments_basis,
    )
    .map_err(|error| error.message)?;

    let mut targets: Vec<String> = raw_targets
        .into_iter()
        .filter_map(|item| item.as_str().map(str::to_string))
        .collect();

    // Work due after Sunday gets its fair share of this week; the rest waits for next week's Plan.
    let (first_day, first_minute) = start.unwrap_or((0, 0));
    let raw_windows = input
        .preferences
        .and_then(|prefs| prefs.get("work_windows"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let windows = shown::windows_on_shown_week(input.week_start, &raw_windows)
        .map_err(|error| error.message)?;
    let split_whole_set: HashSet<&str> = input.split_whole.iter().map(String::as_str).collect();
    let share_targets: Vec<String> = targets
        .iter()
        .filter(|id| !split_whole_set.contains(id.as_str()))
        .cloned()
        .collect();
    let basis_val = Value::Array(input.assignments_basis.to_vec());
    let (week, shares) = planning::fair_share(
        &open_blocks,
        input.assignments,
        &basis_val,
        input.week_start,
        first_day,
        first_minute,
        &windows,
        &share_targets,
    )
    .map_err(|error| error.message)?;

    if !shares.is_empty() {
        let kept: HashSet<&str> = week.iter().filter_map(block_id).collect();
        let kept_targets: Vec<Value> = targets
            .iter()
            .filter(|id| kept.contains(id.as_str()))
            .map(|id| json!(id))
            .collect();
        let only_kept = Value::Array(kept_targets);
        let (rebuilt_payload, rebuilt_targets) = planning::solve_request_at(
            &Value::Array(week.clone()),
            &assignments_val,
            input.week_start,
            false,
            Some(&only_kept),
            not_before_val.as_ref(),
            false,
            now_point.as_ref(),
            input.assignments_basis,
        )
        .map_err(|error| error.message)?;
        payload = rebuilt_payload;
        targets = rebuilt_targets
            .into_iter()
            .filter_map(|item| item.as_str().map(str::to_string))
            .collect();
    }

    if input.earliest_first {
        let target_set: HashSet<&str> = targets.iter().map(String::as_str).collect();
        for block in &mut payload {
            if block_id(block).is_some_and(|id| target_set.contains(id))
                && let Some(fields) = block.as_object_mut()
            {
                fields.insert("prefer_earliest".into(), json!(true));
            }
        }
    }

    if targets.is_empty() {
        return Ok(PlanPreparation::Empty);
    }

    if let Some(overdue) = input.overdue
        && !overdue.is_empty()
    {
        // Only the solve copy loses its deadline link. Saved sessions keep their homework ID
        // and the homework keeps its missed deadline.
        let overdue_set: HashSet<&str> = overdue.iter().map(String::as_str).collect();
        let days: Vec<Value> = (first_day..7).map(Value::from).collect();
        for block in &mut payload {
            if block_id(block).is_some_and(|id| overdue_set.contains(id))
                && let Some(fields) = block.as_object_mut()
            {
                fields.insert("assignment_id".into(), Value::Null);
                fields.insert("latest".into(), Value::Null);
                fields.insert("earliest".into(), Value::Null);
                fields.insert("pinned".into(), json!(false));
                fields.insert("prefer_earliest".into(), json!(true));
                fields.insert("days".into(), Value::Array(days.clone()));
            }
        }
    }

    let prefs_val = input.preferences.cloned().unwrap_or(Value::Null);
    let inflated = pomodoro::inflate_for_solve(&Value::Array(payload), &prefs_val)
        .map_err(|error| error.message)?;
    let body = json!({
        "blocks": inflated,
        "week_start": input.week_start,
        "now_floor": not_before_val.unwrap_or(Value::Null),
    });

    Ok(PlanPreparation::Ready {
        body,
        targets,
        prior_updates,
        shares,
        week,
    })
}

fn dump_blocks(blocks: &[Value]) -> Result<Vec<Value>, String> {
    blocks
        .iter()
        .map(|block| check_block(block).map_err(|refused| refused.0))
        .collect()
}

/// Apply `/api/solve`'s trace onto the week, compute pre-split counts and first placement,
/// run focus splitting against the pre-inflation work lengths, and check whether validated
/// blocks changed.
pub fn apply_plan_answer(
    input: PlanAnswerInput<'_>,
    next_id: impl FnMut() -> String,
) -> Result<PlanAnswer, String> {
    input.clock.check()?;
    let trace_obj = input
        .trace
        .as_object()
        .ok_or_else(|| "trace must be an object".to_string())?;
    let raw_placed = placed_rows(input.trace)?;
    let explanations: &[Value] = match trace_obj.get("explanations") {
        None | Some(Value::Null) => &[],
        Some(Value::Array(items)) => items.as_slice(),
        Some(_) => return Err("trace explanations must be a list".to_string()),
    };

    let before = dump_blocks(input.original_blocks)?;

    let targets_val = Value::Array(input.targets.iter().map(|id| json!(id)).collect());
    let assignments_val = Value::Object(input.assignments.clone());
    let mut blocks = planning::apply_plan(
        &Value::Array(input.source_week.to_vec()),
        input.trace,
        Some(&targets_val),
        Some(&assignments_val),
        Some(input.week_start),
    )
    .map_err(|error| error.message)?;

    let overdue_set: HashSet<&str> = input
        .overdue
        .map(|ids| ids.iter().map(String::as_str).collect())
        .unwrap_or_default();
    if !overdue_set.is_empty() {
        let placed_ids: HashSet<&str> = raw_placed
            .iter()
            .filter(|item| truthy(item.get("start")))
            .filter_map(block_id)
            .collect();
        let failed: HashSet<&str> = overdue_set
            .iter()
            .copied()
            .filter(|id| !placed_ids.contains(id))
            .collect();
        let new_left_set: HashSet<&str> = input
            .new_left
            .map(|ids| ids.iter().map(String::as_str).collect())
            .unwrap_or_default();
        let originals: HashMap<&str, &Value> = input
            .original_blocks
            .iter()
            .filter_map(|block| block_id(block).map(|id| (id, block)))
            .collect();
        let mut rolled = Vec::with_capacity(blocks.len());
        for mut block in blocks {
            let id = block_id(&block).unwrap_or_default();
            if failed.contains(id) && new_left_set.contains(id) {
                continue;
            }
            if failed.contains(id) {
                let original = originals
                    .get(id)
                    .ok_or_else(|| format!("missing original block {id:?}"))?;
                block = (*original).clone();
            }
            if let Some(fields) = block.as_object_mut() {
                fields.shift_remove("prefer_earliest");
            }
            rolled.push(block);
        }
        blocks = rolled;
    }

    let sources: HashMap<String, Value> = blocks
        .iter()
        .filter_map(|block| block_id(block).map(|id| (id.to_string(), block.clone())))
        .collect();

    let mut updated_shares: Vec<Value> = Vec::with_capacity(input.shares.len());
    for share in input.shares {
        let mut share_obj = share
            .as_object()
            .cloned()
            .ok_or_else(|| "each share must be an object".to_string())?;
        let assignment_id = share_obj
            .get("assignment_id")
            .cloned()
            .unwrap_or(Value::Null);
        let mut placed_min: i64 = 0;
        let mut placed_days: BTreeSet<i64> = BTreeSet::new();
        for item in raw_placed {
            if !assignment_id.is_null()
                && item.get("assignment_id") == Some(&assignment_id)
                && truthy(item.get("start"))
            {
                placed_min = placed_min
                    .checked_add(opt_int(item, "duration_min")?.unwrap_or(0))
                    .ok_or_else(|| "placed minutes too large".to_string())?;
                if let Some(day) = first_day_of(item)? {
                    placed_days.insert(day);
                }
            }
        }
        let this_week_min = share_obj
            .get("this_week_min")
            .and_then(Value::as_i64)
            .unwrap_or(0);
        let left_min = share_obj
            .get("left_min")
            .and_then(Value::as_i64)
            .unwrap_or(0);
        let total_min = this_week_min
            .checked_add(left_min)
            .ok_or_else(|| "share minutes too large".to_string())?;
        share_obj.insert("this_week_min".into(), json!(placed_min));
        share_obj.insert(
            "left_min".into(),
            json!(total_min.saturating_sub(placed_min).max(0)),
        );
        share_obj.insert(
            "placed_days".into(),
            Value::Array(placed_days.into_iter().map(Value::from).collect()),
        );
        updated_shares.push(Value::Object(share_obj));
    }

    let augmented_placed: Vec<Value> = raw_placed
        .iter()
        .map(|item| {
            let id = block_id(item).unwrap_or_default();
            let replace = (item.get("kind").and_then(Value::as_str) == Some("locked")
                || overdue_set.contains(id))
                && sources.contains_key(id);
            match sources.get(id) {
                Some(source) if replace => source.clone(),
                _ => item.clone(),
            }
        })
        .collect();

    let mut augmented_trace_map = trace_obj.clone();
    augmented_trace_map.insert("week_start".into(), json!(input.week_start));
    augmented_trace_map.insert("shares".into(), Value::Array(updated_shares));
    augmented_trace_map.insert("placed".into(), Value::Array(augmented_placed.clone()));
    let augmented_trace = Value::Object(augmented_trace_map);

    let target_set: HashSet<&str> = input.targets.iter().map(String::as_str).collect();
    let placed_count = augmented_placed
        .iter()
        .filter(|item| {
            block_id(item).is_some_and(|id| target_set.contains(id)) && truthy(item.get("start"))
        })
        .count() as i64;

    // Why each target still has no time is what this plan found, not what an earlier edit said.
    let mut reasons: BTreeMap<String, String> = BTreeMap::new();
    for item in explanations {
        if truthy(item.get("reason"))
            && truthy(item.get("message"))
            && let (Some(id), Some(message)) = (
                item.get("block_id").and_then(Value::as_str),
                item.get("message").and_then(Value::as_str),
            )
        {
            reasons.insert(id.to_string(), message.to_string());
        }
    }
    let mut needs_time = input.needs_time.clone();
    for id in input.targets {
        let has_start = sources
            .get(id.as_str())
            .is_some_and(|block| truthy(block.get("start")));
        if has_start {
            needs_time.shift_remove(id);
        } else if let Some(message) = reasons.get(id) {
            needs_time.insert(id.clone(), Value::String(message.clone()));
        }
    }

    // Counted on the week as this plan left it (pre-split), against the pre-save basis.
    let screen_now = planning::screen_point(
        input.week_start,
        input.clock.today_iso,
        input.clock.hour,
        input.clock.minute,
    )
    .map_err(|error| error.message)?
    .map(|(day, minute)| json!([day, minute]));
    let open_week = planning::without_missed_times(
        &blocks,
        &assignments_val,
        input.assignments_basis,
        screen_now.as_ref(),
    )
    .map_err(|error| error.message)?;
    let (plan_open, waiting_only) = planning::plan_open_counts(
        input.assignments,
        &open_week,
        input.week_start,
        input.assignments_basis,
    )
    .map_err(|error| error.message)?;
    let time_split = planning::time_still_needed_parts(
        input.assignments,
        &open_week,
        input.week_start,
        input.assignments_basis,
    )
    .map_err(|error| error.message)?;
    let mut plan_remainders: Vec<(String, i64)> = Vec::new();
    for item in &time_split {
        if item
            .get("uncovered_min")
            .and_then(Value::as_i64)
            .unwrap_or(0)
            != 0
        {
            let title = item
                .get("title")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string();
            let minutes = item.get("minutes").and_then(Value::as_i64).unwrap_or(0);
            plan_remainders.push((title, minutes));
        }
    }
    let plan_counts = (placed_count, waiting_only);
    let plan_first = first_placed(&augmented_trace, input.targets)?;

    let split = apply_auto_split(
        &blocks,
        &augmented_trace,
        Some(input.source_week),
        input.preferences,
        next_id,
    )?;
    let after = dump_blocks(&split.blocks)?;
    let changed = after != before;
    let final_blocks = if changed {
        split.blocks
    } else {
        input.original_blocks.to_vec()
    };

    let mut placed_note = plan_sentence(placed_count, waiting_only, &plan_remainders);
    let mut placed_where = String::new();
    if input.earliest_first && input.targets.len() == 1 {
        let empty = Value::Object(Map::new());
        let only_block = sources.get(&input.targets[0]).unwrap_or(&empty);
        placed_note = place_now_sentence(only_block, input.week_start)?;
        if truthy(only_block.get("start")) {
            placed_where = placed_note.clone();
        }
    }
    if !split.note.is_empty() {
        placed_note.push_str(&split.note);
    }

    Ok(PlanAnswer {
        blocks: final_blocks,
        trace: augmented_trace,
        needs_time,
        reasons,
        plan_remainders,
        plan_counts,
        plan_open,
        plan_first,
        split_count: split.count,
        split_note: split.note,
        changed,
        placed_note,
        placed_where,
    })
}
