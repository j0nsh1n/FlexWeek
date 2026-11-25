//! Running late, missed-commitment recovery, Allow splitting and Spread preview decisions
//! (FlexWeek 2.0.0, P4 group 5B): the pure rules of `desktop/native/controller.py`'s
//! `spread_ready_sentence`, `_late_summary`, `allow_splitting`, `recover_missed`,
//! `preview_running_late`, `_late_blocks`, `accept_running_late`, `preview_spread` and
//! `confirm_spread`. The window keeps the requests, timers, signals and state writes.

use std::collections::{BTreeSet, HashSet};

use flexweek_engine::desk::clipboard::merge_preview_rows;
use flexweek_engine::desk::datetext::day_of;
use flexweek_engine::desk::focus::{MAX_ESTIMATE_MIN, MAX_FOCUS_MINUTES};
use flexweek_engine::desk::grid::{date_for_day, due_day_in_week};
use flexweek_engine::desk::planning::{
    apply_plan, is_planned, late_from_start, running_late_block,
};
use flexweek_engine::desk::reuse::{
    MAX_WEEK_BLOCKS, copied_homework_block, late_id, running_late_refusal,
};
use flexweek_engine::desk::weekmodel::{due_label_text, length_label};
use flexweek_engine::plan::unplanned_minutes;
use flexweek_engine::stored::truthy;
use flexweek_engine::time::{hhmm_to_minutes, week_start_on};
use flexweek_service::blocks::check_block;
use serde_json::{Map, Value, json};

pub const RECOVER_STATUS: &str = "Replanning after the miss…";
pub const RECOVER_TOUCH_LABEL: &str = "the replan";
pub const LATE_STATUS: &str = "Replanning…";
pub const LATE_INVALID_MINUTES: &str = "Choose 15, 30 or 60 minutes.";
pub const LATE_CAPACITY_REFUSAL: &str =
    "This week already has 100 blocks. Remove one before recording a late start.";
pub const LATE_TOUCH_LABEL: &str = "running late";
pub const SPREAD_ALL_PLANNED: &str = "All of this homework is already focused or planned.";

/// Where a recovery or running-late solve gets its `previous_placed` blocks.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PreviousSource {
    Trace,
    Scheduled,
    BaseSolve,
}

impl PreviousSource {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Trace => "trace",
            Self::Scheduled => "scheduled",
            Self::BaseSolve => "base_solve",
        }
    }
}

/// Spread preview: names the homework and how much is ready before it is due.
pub fn spread_ready_sentence(
    title: &str,
    minutes: i64,
    due: &str,
    today: &str,
) -> Result<String, String> {
    let today_date = day_of(today).map_err(|err| err.message)?;
    let due_text = due_label_text(Some(due), today_date).map_err(|err| err.message)?;
    Ok(format!(
        "{title}: {} ready to add before {due_text}.",
        length_label(minutes)
    ))
}

/// How many tasks a Running late preview moves, in words.
pub fn late_summary(moved: usize) -> String {
    match moved {
        0 => "Nothing needs to move.".to_string(),
        1 => "1 task moves".to_string(),
        count => format!("{count} tasks move"),
    }
}

/// The week as Running late replans it. Homework still waiting for a time stays out, so a late
/// start never places it: Plan places that homework.
pub fn late_blocks(blocks: &[Value]) -> Vec<Value> {
    blocks
        .iter()
        .filter(|block| {
            let flexible = block.get("kind").and_then(Value::as_str) == Some("flexible");
            let has_assignment = truthy(block.get("assignment_id"));
            let has_start = truthy(block.get("start"));
            !(flexible && has_assignment && !has_start)
        })
        .cloned()
        .collect()
}

/// Attempt key shared across retries of the same Spread confirmation.
pub fn spread_key(
    account_id: i64,
    assignment_id: &str,
    from_date: &str,
    session_min: i64,
) -> String {
    format!("spread|{account_id}|{assignment_id}|{from_date}|{session_min}")
}

pub struct AllowSplittingInput<'a> {
    pub assignment: Option<&'a Value>,
    pub done_min: i64,
    pub week_start: &'a str,
    pub today_iso: &'a str,
    pub selected_day: Option<&'a str>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct AllowSplittingPlan {
    pub assignment: Value,
    pub session_min: i64,
    pub from_date: String,
}

impl AllowSplittingPlan {
    pub fn to_json(&self) -> Value {
        json!({
            "assignment": self.assignment,
            "session_min": self.session_min,
            "from_date": self.from_date,
        })
    }
}

/// Decisions for `allow_splitting`: the updated homework (`spread: "spread"`), the session length
/// clamped to 15..=60 on the 15-minute grid, and the start date clamped between today/selected and due.
pub fn prepare_allow_splitting(
    input: AllowSplittingInput<'_>,
) -> Result<Option<AllowSplittingPlan>, String> {
    let Some(assignment) = input.assignment else {
        return Ok(None);
    };
    let Value::Object(fields) = assignment else {
        return Err("assignment must be a JSON object".to_string());
    };
    if truthy(fields.get("completed")) {
        return Ok(None);
    }
    let mut updated = fields.clone();
    updated.insert("spread".into(), json!("spread"));
    let estimate_min = bounded_int(
        updated.get("estimate_min"),
        "estimate_min",
        MAX_ESTIMATE_MIN as i64,
    )?;
    let focus_minutes = bounded_int(
        updated.get("focus_minutes"),
        "focus_minutes",
        MAX_FOCUS_MINUTES as i64,
    )?;
    let remaining = unplanned_minutes(estimate_min, focus_minutes, input.done_min, 0);
    let session_min = (remaining - remaining.rem_euclid(15)).clamp(15, 60);
    let due_raw = match updated.get("due") {
        None | Some(Value::Null) => input.week_start,
        Some(Value::String(text)) if !text.is_empty() => text.as_str(),
        Some(Value::String(_)) => input.week_start,
        Some(_) => return Err("due must be text".to_string()),
    };
    let due: String = due_raw.chars().take(10).collect();
    let anchor = input
        .selected_day
        .filter(|day| !day.is_empty())
        .unwrap_or(input.week_start);
    let earliest = if input.today_iso >= anchor {
        input.today_iso
    } else {
        anchor
    };
    let from_date = if earliest <= due.as_str() {
        earliest.to_string()
    } else {
        due
    };
    Ok(Some(AllowSplittingPlan {
        assignment: Value::Object(updated),
        session_min,
        from_date,
    }))
}

pub struct RecoverInput<'a> {
    pub week_start: &'a str,
    pub blocks: &'a [Value],
    pub trace: Option<&'a Value>,
    pub block_id: &'a str,
    pub day: i64,
}

#[derive(Debug, Clone, PartialEq)]
pub enum RecoverPreparation {
    Ignore,
    SaveOnly,
    Ready {
        status: &'static str,
        previous_source: PreviousSource,
        payload: Value,
    },
    NeedsBase {
        status: &'static str,
        previous_source: PreviousSource,
        base_payload: Value,
    },
}

impl RecoverPreparation {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Ignore => json!({ "kind": "ignore" }),
            Self::SaveOnly => json!({ "kind": "save_only" }),
            Self::Ready {
                status,
                previous_source,
                payload,
            } => json!({
                "kind": "ready",
                "status": status,
                "previous_source": previous_source.as_str(),
                "payload": payload,
            }),
            Self::NeedsBase {
                status,
                previous_source,
                base_payload,
            } => json!({
                "kind": "needs_base",
                "status": status,
                "previous_source": previous_source.as_str(),
                "base_payload": base_payload,
            }),
        }
    }
}

/// Decide what `recover_missed` sends: ignore an invalid target, save an already-missed day, send the
/// recovery solve directly, or ask for a base solve first when nothing is placed yet.
pub fn recover_request(input: RecoverInput<'_>) -> Result<RecoverPreparation, String> {
    let Some(block) = find_block(input.blocks, input.block_id)? else {
        return Ok(RecoverPreparation::Ignore);
    };
    if block.get("kind").and_then(Value::as_str) != Some("locked") {
        return Ok(RecoverPreparation::Ignore);
    }
    let days = int_list(block.get("days"), "days")?;
    if !days.contains(&input.day) {
        return Ok(RecoverPreparation::Ignore);
    }
    let missed = int_list(block.get("missed_days"), "missed_days")?;
    if missed.contains(&input.day) {
        return Ok(RecoverPreparation::SaveOnly);
    }
    let dumped_blocks = dump_blocks(input.blocks)?;
    match choose_previous(input.blocks, input.trace)? {
        (source, Some(previous)) => Ok(RecoverPreparation::Ready {
            status: RECOVER_STATUS,
            previous_source: source,
            payload: json!({
                "week_start": input.week_start,
                "blocks": dumped_blocks,
                "recover": {
                    "missed_block_id": input.block_id,
                    "missed_day": input.day,
                    "previous_placed": previous,
                },
            }),
        }),
        (source, None) => Ok(RecoverPreparation::NeedsBase {
            status: RECOVER_STATUS,
            previous_source: source,
            base_payload: json!({
                "week_start": input.week_start,
                "blocks": dumped_blocks,
            }),
        }),
    }
}

/// Second-step payload for `recover_missed` once the base solve answers.
pub fn recover_payload_from_base(
    week_start: &str,
    blocks: &[Value],
    block_id: &str,
    day: i64,
    base_trace: &Value,
) -> Result<Value, String> {
    let dumped_blocks = dump_blocks(blocks)?;
    let previous = dump_blocks(&trace_placed_list(base_trace)?)?;
    Ok(json!({
        "week_start": week_start,
        "blocks": dumped_blocks,
        "recover": {
            "missed_block_id": block_id,
            "missed_day": day,
            "previous_placed": previous,
        },
    }))
}

pub struct RecoverAnswerInput<'a> {
    pub week_start: &'a str,
    pub blocks: &'a [Value],
    pub assignments: &'a Value,
    pub block_id: &'a str,
    pub day: i64,
    pub trace: &'a Value,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RecoverApplied {
    pub blocks: Vec<Value>,
    pub label: &'static str,
}

impl RecoverApplied {
    pub fn to_json(&self) -> Value {
        json!({
            "blocks": self.blocks,
            "label": self.label,
        })
    }
}

/// Apply the recovery solve answer: mark `day` missed on `block_id` (sorted, unique) and apply the
/// solver's new placements. Returns `None` if the block was removed while the solve was in flight.
pub fn recover_answer(input: RecoverAnswerInput<'_>) -> Result<Option<RecoverApplied>, String> {
    if !input.assignments.is_object() {
        return Err("assignments must be a JSON object".to_string());
    }
    if !input.trace.is_object() {
        return Err("trace must be a JSON object".to_string());
    }
    let mut updated = input.blocks.to_vec();
    let Some(target) = updated
        .iter_mut()
        .find(|item| item.get("id").and_then(Value::as_str) == Some(input.block_id))
    else {
        return Ok(None);
    };
    let Value::Object(fields) = target else {
        return Err("each block must be a JSON object".to_string());
    };
    let mut missed: BTreeSet<i64> = int_list(fields.get("missed_days"), "missed_days")?
        .into_iter()
        .collect();
    missed.insert(input.day);
    fields.insert(
        "missed_days".into(),
        Value::Array(missed.into_iter().map(Value::from).collect()),
    );
    let blocks = apply_plan(
        &Value::Array(updated),
        input.trace,
        None,
        Some(input.assignments),
        Some(input.week_start),
    )
    .map_err(|err| err.message)?;
    Ok(Some(RecoverApplied {
        blocks,
        label: RECOVER_TOUCH_LABEL,
    }))
}

pub struct LateInput<'a> {
    pub week_start: &'a str,
    pub today_iso: &'a str,
    pub now_hour: i64,
    pub now_minute: i64,
    pub minutes: i64,
    pub dirty: bool,
    pub conflict: bool,
    pub blocks: &'a [Value],
    pub trace: Option<&'a Value>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum LatePreparation {
    Refused(String),
    Ready {
        day: i64,
        from_start: String,
        minutes: i64,
        status: &'static str,
        previous_source: PreviousSource,
        payload: Value,
    },
    NeedsBase {
        day: i64,
        from_start: String,
        minutes: i64,
        status: &'static str,
        previous_source: PreviousSource,
        base_payload: Value,
    },
}

impl LatePreparation {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Refused(message) => json!({
                "kind": "refused",
                "message": message,
            }),
            Self::Ready {
                day,
                from_start,
                minutes,
                status,
                previous_source,
                payload,
            } => json!({
                "kind": "ready",
                "day": day,
                "from_start": from_start,
                "minutes": minutes,
                "status": status,
                "previous_source": previous_source.as_str(),
                "payload": payload,
            }),
            Self::NeedsBase {
                day,
                from_start,
                minutes,
                status,
                previous_source,
                base_payload,
            } => json!({
                "kind": "needs_base",
                "day": day,
                "from_start": from_start,
                "minutes": minutes,
                "status": status,
                "previous_source": previous_source.as_str(),
                "base_payload": base_payload,
            }),
        }
    }
}

/// Guard and prepare a Running late preview request: check refusal rules and allowed delay lengths,
/// keep waiting homework out of the late solve, and choose `previous_placed` or a base solve.
pub fn prepare_late(input: LateInput<'_>) -> Result<LatePreparation, String> {
    // The refusal helper reads an unparsable date as "no refusal", so check the plain date first.
    if !plain_date(input.today_iso) {
        return Err("today_iso must be a date as YYYY-MM-DD".to_string());
    }
    if !(0..24).contains(&input.now_hour) || !(0..60).contains(&input.now_minute) {
        return Err("now_hour must be 0..23 and now_minute must be 0..59".to_string());
    }
    if let Some(refusal) = running_late_refusal(
        input.week_start,
        input.today_iso,
        input.dirty,
        input.conflict,
        input.blocks.len() as i64,
    ) {
        return Ok(LatePreparation::Refused(refusal.to_string()));
    }
    if !matches!(input.minutes, 15 | 30 | 60) {
        return Ok(LatePreparation::Refused(LATE_INVALID_MINUTES.to_string()));
    }
    let from_start = late_from_start(input.now_hour * 60 + input.now_minute);
    let day = due_day_in_week(input.today_iso, input.week_start).map_err(|err| err.message)?;
    let from_min = hhmm_to_minutes(&from_start).map_err(|err| err.message)?;
    let late_dumped = dump_blocks(&late_blocks(input.blocks))?;
    match choose_previous(input.blocks, input.trace)? {
        (source, Some(previous)) => Ok(LatePreparation::Ready {
            day,
            from_start: from_start.clone(),
            minutes: input.minutes,
            status: LATE_STATUS,
            previous_source: source,
            payload: json!({
                "week_start": input.week_start,
                "blocks": late_dumped,
                "running_late": {
                    "day": day,
                    "minutes": input.minutes,
                    "from_start": from_start,
                    "now_floor": [day, from_min],
                    "previous_placed": previous,
                },
            }),
        }),
        (source, None) => Ok(LatePreparation::NeedsBase {
            day,
            from_start,
            minutes: input.minutes,
            status: LATE_STATUS,
            previous_source: source,
            base_payload: json!({
                "week_start": input.week_start,
                "blocks": late_dumped,
            }),
        }),
    }
}

/// Second-step payload for `preview_running_late` once the base solve answers.
pub fn late_payload_from_base(
    week_start: &str,
    blocks: &[Value],
    day: i64,
    from_start: &str,
    minutes: i64,
    base_trace: &Value,
) -> Result<Value, String> {
    let from_min = hhmm_to_minutes(from_start).map_err(|err| err.message)?;
    let late_dumped = dump_blocks(&late_blocks(blocks))?;
    let previous = dump_blocks(&trace_placed_list(base_trace)?)?;
    Ok(json!({
        "week_start": week_start,
        "blocks": late_dumped,
        "running_late": {
            "day": day,
            "minutes": minutes,
            "from_start": from_start,
            "now_floor": [day, from_min],
            "previous_placed": previous,
        },
    }))
}

pub struct LateAnswerInput<'a> {
    pub week_start: &'a str,
    pub day: i64,
    pub from_start: &'a str,
    pub minutes: i64,
    pub operation_id: &'a str,
    pub trace: &'a Value,
}

#[derive(Debug, Clone, PartialEq)]
pub struct LatePreview {
    pub preview: Value,
    pub summary: String,
}

impl LatePreview {
    pub fn to_json(&self) -> Value {
        json!({
            "preview": self.preview,
            "summary": self.summary,
        })
    }
}

/// Build the held Running late preview and its summary sentence from a solve answer.
pub fn late_answer(input: LateAnswerInput<'_>) -> Result<LatePreview, String> {
    let Value::Object(trace_fields) = input.trace else {
        return Err("trace must be a JSON object".to_string());
    };
    let moved = match trace_fields.get("moves") {
        None | Some(Value::Null) => 0,
        Some(Value::Array(moves)) => moves.len(),
        Some(_) => return Err("trace.moves must be a list".to_string()),
    };
    let block = running_late_block(
        &json!(input.day),
        input.from_start,
        input.minutes,
        &json!(late_id(input.operation_id)),
    )
    .map_err(|err| err.message)?;
    let preview = json!({
        "trace": input.trace,
        "operation_id": input.operation_id,
        "week_start": input.week_start,
        "block": block,
        "stale": false,
    });
    Ok(LatePreview {
        preview,
        summary: late_summary(moved),
    })
}

pub struct LateAcceptInput<'a> {
    pub preview: Option<&'a Value>,
    pub week_start: &'a str,
    pub blocks: &'a [Value],
    pub assignments: &'a Value,
}

#[derive(Debug, Clone, PartialEq)]
pub enum LateAcceptDecision {
    Ignore,
    Refused(String),
    Accept {
        blocks: Vec<Value>,
        trace: Value,
        operation_id: String,
        label: &'static str,
    },
}

impl LateAcceptDecision {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Ignore => json!({ "kind": "ignore" }),
            Self::Refused(message) => json!({
                "kind": "refused",
                "message": message,
            }),
            Self::Accept {
                blocks,
                trace,
                operation_id,
                label,
            } => json!({
                "kind": "accept",
                "blocks": blocks,
                "trace": trace,
                "operation_id": operation_id,
                "label": label,
            }),
        }
    }
}

/// Validate a held Running late preview (stale, matching week, capacity) and apply its locked block
/// and trace while carrying the original `operation_id`.
pub fn accept_late(input: LateAcceptInput<'_>) -> Result<LateAcceptDecision, String> {
    if !input.assignments.is_object() {
        return Err("assignments must be a JSON object".to_string());
    }
    let Some(preview) = input.preview else {
        return Ok(LateAcceptDecision::Ignore);
    };
    let Value::Object(fields) = preview else {
        return Err("late preview must be a JSON object".to_string());
    };
    if truthy(fields.get("stale"))
        || fields.get("week_start").and_then(Value::as_str) != Some(input.week_start)
    {
        return Ok(LateAcceptDecision::Ignore);
    }
    if input.blocks.len() as i64 >= MAX_WEEK_BLOCKS {
        return Ok(LateAcceptDecision::Refused(
            LATE_CAPACITY_REFUSAL.to_string(),
        ));
    }
    let block = fields
        .get("block")
        .filter(|value| value.is_object())
        .ok_or_else(|| "late preview is missing a block object".to_string())?;
    let trace = fields
        .get("trace")
        .filter(|value| value.is_object())
        .ok_or_else(|| "late preview is missing a trace object".to_string())?;
    let operation_id = fields
        .get("operation_id")
        .and_then(Value::as_str)
        .ok_or_else(|| "late preview is missing operation_id".to_string())?
        .to_string();
    // Validate only: the accepted edit carries the preview block as held, not a rewritten copy.
    check_late_block(&check_block(block).map_err(|refused| refused.0)?)?;
    check_trace_lists(trace)?;
    let mut with_late = Vec::with_capacity(input.blocks.len() + 1);
    with_late.extend(input.blocks.iter().cloned());
    with_late.push(block.clone());
    let blocks = apply_plan(
        &Value::Array(with_late),
        trace,
        None,
        Some(input.assignments),
        Some(input.week_start),
    )
    .map_err(|err| err.message)?;
    Ok(LateAcceptDecision::Accept {
        blocks,
        trace: trace.clone(),
        operation_id,
        label: LATE_TOUCH_LABEL,
    })
}

pub struct SpreadAnswerInput<'a> {
    pub assignment_id: &'a str,
    pub assignment: &'a Value,
    pub data: &'a Value,
    pub from_date: &'a str,
    pub session_min: i64,
    pub today_iso: &'a str,
    pub id_prefix: &'a str,
}

#[derive(Debug, Clone, PartialEq)]
pub enum SpreadPreview {
    Empty { message: String },
    Ready { preview: Value, summary: String },
}

impl SpreadPreview {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Empty { message } => json!({
                "kind": "empty",
                "message": message,
            }),
            Self::Ready { preview, summary } => json!({
                "kind": "ready",
                "preview": preview,
                "summary": summary,
            }),
        }
    }
}

/// Turn a `/api/assignments/{id}/spread` reply into preview rows and student-facing summary words,
/// preserving assignment identity and any leftover minutes that do not fit the 15-minute grid.
pub fn spread_answer(input: SpreadAnswerInput<'_>) -> Result<SpreadPreview, String> {
    let Value::Object(assignment_fields) = input.assignment else {
        return Err("assignment must be a JSON object".to_string());
    };
    let Value::Object(data_fields) = input.data else {
        return Err("spread answer must be a JSON object".to_string());
    };
    let sessions = match data_fields.get("sessions") {
        None | Some(Value::Null) => &[][..],
        Some(Value::Array(items)) => items.as_slice(),
        Some(_) => return Err("sessions must be a list".to_string()),
    };
    let remaining = optional_int(data_fields.get("remaining_min"), "remaining_min")?;
    if sessions.is_empty() {
        let message = if remaining != 0 {
            format!(
                "{} remains, but it doesn't fit the 15-minute planning grid.",
                length_label(remaining)
            )
        } else {
            SPREAD_ALL_PLANNED.to_string()
        };
        return Ok(SpreadPreview::Empty { message });
    }
    let mut rows = Vec::with_capacity(sessions.len());
    let mut total: i64 = 0;
    for (index, session) in sessions.iter().enumerate() {
        let Value::Object(session_fields) = session else {
            return Err("each spread session must be a JSON object".to_string());
        };
        let duration = required_int(session_fields, "duration_min")?;
        let day = first_day(session_fields)?;
        let week_start = required_str(session_fields, "week_start")?;
        total = total
            .checked_add(duration)
            .ok_or_else(|| "total spread duration overflowed".to_string())?;
        let group_id = format!("spread-{}-{index:x}", input.id_prefix);
        let block = copied_homework_block(input.assignment, day, duration, &group_id)
            .map_err(|err| err.message)?;
        rows.push(json!({
            "week_start": week_start,
            "day": day,
            "fixed": false,
            "block": block,
            "group_id": group_id,
            "checked": true,
            "invalid": "",
        }));
    }
    let title = required_str(assignment_fields, "title")?;
    let due = required_str(assignment_fields, "due")?;
    let mut summary = spread_ready_sentence(title, total, due, input.today_iso)?;
    if remaining != 0 {
        summary.push_str(&format!(
            " {} can't fit the 15-minute grid and has not been dropped from the homework total.",
            length_label(remaining)
        ));
    }
    let preview = json!({
        "assignment_id": input.assignment_id,
        "rows": rows,
        "summary": summary,
        "from_date": input.from_date,
        "session_min": input.session_min,
    });
    Ok(SpreadPreview::Ready { preview, summary })
}

pub struct SpreadSelectionInput<'a> {
    pub preview: &'a Value,
    pub assignments: &'a Value,
    pub week_start: &'a str,
    pub first_weekday: u32,
    pub operation_id: &'a str,
    pub allow_split_pending: Option<&'a str>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SplitSelection {
    pub label: String,
    pub made_ids: Vec<String>,
    pub plan_ids: Vec<String>,
}

impl SplitSelection {
    pub fn to_json(&self) -> Value {
        json!({
            "label": self.label,
            "made_ids": self.made_ids,
            "plan_ids": self.plan_ids,
        })
    }
}

/// Map each merged Spread group's stored Monday and day into the shown week (starting on
/// `first_weekday`) to decide the history label, the session IDs made in the open week, and which
/// IDs carry the Allow-splitting plan promise.
pub fn spread_selection(input: SpreadSelectionInput<'_>) -> Result<SplitSelection, String> {
    let Value::Object(preview_fields) = input.preview else {
        return Err("spread preview must be a JSON object".to_string());
    };
    let Value::Object(assignments_map) = input.assignments else {
        return Err("assignments must be a JSON object".to_string());
    };
    let assignment_id = required_str(preview_fields, "assignment_id")?;
    let title = assignments_map
        .get(assignment_id)
        .and_then(|item| item.get("title"))
        .and_then(Value::as_str)
        .unwrap_or("homework");
    let rows = preview_fields
        .get("rows")
        .filter(|value| value.is_array())
        .ok_or_else(|| "spread preview is missing a rows list".to_string())?;
    let groups = merge_preview_rows(rows, input.operation_id).map_err(|err| err.message)?;
    let mut seen = HashSet::new();
    let mut made_ids = Vec::new();
    for group in groups {
        let Value::Object(group_fields) = &group else {
            return Err("merged preview group must be a JSON object".to_string());
        };
        let group_week = required_str(group_fields, "week_start")?;
        let Value::Object(block_fields) = group_fields
            .get("block")
            .ok_or_else(|| "merged preview group is missing block".to_string())?
        else {
            return Err("merged preview block must be a JSON object".to_string());
        };
        let day_value = block_fields
            .get("days")
            .and_then(Value::as_array)
            .and_then(|days| days.first())
            .ok_or_else(|| "merged preview block is missing days".to_string())?;
        // A group is keyed by its stored Monday; the week on screen is the one holding its date.
        let iso_date = date_for_day(group_week, day_value).map_err(|err| err.message)?;
        let shown = week_start_on(&iso_date, input.first_weekday).map_err(|err| err.message)?;
        if shown == input.week_start
            && block_fields.get("assignment_id").and_then(Value::as_str) == Some(assignment_id)
        {
            let id = required_str(block_fields, "id")?.to_string();
            if seen.insert(id.clone()) {
                made_ids.push(id);
            }
        }
    }
    let plan_ids = if input.allow_split_pending == Some(assignment_id) {
        made_ids.clone()
    } else {
        Vec::new()
    };
    Ok(SplitSelection {
        label: format!("spreading {title}"),
        made_ids,
        plan_ids,
    })
}

/// A Running late block is a locked block on real days (0 to 6) with a real HH:MM start.
fn check_late_block(block: &Value) -> Result<(), String> {
    if block.get("kind").and_then(Value::as_str) != Some("locked") {
        return Err("late block must be a locked block".to_string());
    }
    let days = int_list(block.get("days"), "days")?;
    if days.is_empty() || days.iter().any(|day| !(0..=6).contains(day)) {
        return Err("late block days must be a list of days 0 to 6".to_string());
    }
    let Some(start) = block.get("start").and_then(Value::as_str) else {
        return Err("late block start must be an HH:MM time".to_string());
    };
    hhmm_to_minutes(start).map_err(|err| format!("late block start: {}", err.message))?;
    Ok(())
}

/// A held trace's `placed` and `unplaced` must be lists of objects with a text `id`; a placement's
/// `start` is null or a real HH:MM time, its `days` are 0 to 6 and its `duration_min` is positive.
fn check_trace_lists(trace: &Value) -> Result<(), String> {
    for key in ["placed", "unplaced"] {
        let items = match trace.get(key) {
            None | Some(Value::Null) => continue,
            Some(Value::Array(items)) => items,
            Some(_) => return Err(format!("trace.{key} must be a list")),
        };
        for item in items {
            let Value::Object(fields) = item else {
                return Err(format!("each trace.{key} item must be a JSON object"));
            };
            if !fields.get("id").is_some_and(Value::is_string) {
                return Err(format!("each trace.{key} item needs a text id"));
            }
            match fields.get("start") {
                None | Some(Value::Null) => {}
                Some(Value::String(start)) => {
                    hhmm_to_minutes(start)
                        .map_err(|err| format!("trace.{key} start: {}", err.message))?;
                }
                Some(_) => return Err(format!("trace.{key} start must be text")),
            }
            if !matches!(fields.get("duration_min"), None | Some(Value::Null)) {
                match fields.get("duration_min").and_then(Value::as_i64) {
                    None => {
                        return Err(format!("trace.{key} duration_min must be a whole number"));
                    }
                    Some(minutes) if minutes < 1 => {
                        return Err(format!("trace.{key} duration_min must be positive"));
                    }
                    Some(_) => {}
                }
            }
            if int_list(fields.get("days"), "days")?
                .iter()
                .any(|day| !(0..=6).contains(day))
            {
                return Err(format!("trace.{key} days must be 0 to 6"));
            }
        }
    }
    Ok(())
}

fn find_block<'a>(blocks: &'a [Value], block_id: &str) -> Result<Option<&'a Value>, String> {
    for block in blocks {
        if !block.is_object() {
            return Err("each block must be a JSON object".to_string());
        }
        if block.get("id").and_then(Value::as_str) == Some(block_id) {
            return Ok(Some(block));
        }
    }
    Ok(None)
}

fn dump_blocks(blocks: &[Value]) -> Result<Vec<Value>, String> {
    blocks
        .iter()
        .map(|block| check_block(block).map_err(|refused| refused.0))
        .collect()
}

fn trace_placed_list(trace: &Value) -> Result<Vec<Value>, String> {
    let Value::Object(fields) = trace else {
        return Err("trace must be a JSON object".to_string());
    };
    match fields.get("placed") {
        None | Some(Value::Null) => Ok(Vec::new()),
        Some(Value::Array(items)) => Ok(items.clone()),
        Some(_) => Err("trace.placed must be a list".to_string()),
    }
}

fn choose_previous(
    blocks: &[Value],
    trace: Option<&Value>,
) -> Result<(PreviousSource, Option<Vec<Value>>), String> {
    if let Some(trace) = trace
        && !trace.is_null()
    {
        let placed = trace_placed_list(trace)?;
        if !placed.is_empty() {
            return Ok((PreviousSource::Trace, Some(dump_blocks(&placed)?)));
        }
    }
    if blocks
        .iter()
        .any(|block| is_planned(block).unwrap_or(false))
    {
        let scheduled = scheduled_blocks(blocks, trace)?;
        return Ok((PreviousSource::Scheduled, Some(dump_blocks(&scheduled)?)));
    }
    Ok((PreviousSource::BaseSolve, None))
}

/// Mirrors `NativeSession.scheduled_blocks` for the only case `choose_previous` reaches: no
/// placements are held. With no trace (null or empty dict) it returns locked blocks and flexible
/// blocks with a start; a trace with entries but an empty `placed` list means nothing is scheduled.
fn scheduled_blocks(blocks: &[Value], trace: Option<&Value>) -> Result<Vec<Value>, String> {
    match trace {
        None | Some(Value::Null) => {}
        Some(Value::Object(map)) if map.is_empty() => {}
        Some(Value::Object(_)) => return Ok(Vec::new()),
        Some(_) => return Err("trace must be a JSON object".to_string()),
    }
    Ok(blocks
        .iter()
        .filter(|block| {
            let kind = block.get("kind").and_then(Value::as_str);
            kind == Some("locked") || (kind == Some("flexible") && truthy(block.get("start")))
        })
        .cloned()
        .collect())
}

fn int_list(value: Option<&Value>, name: &str) -> Result<Vec<i64>, String> {
    match value {
        None | Some(Value::Null) => Ok(Vec::new()),
        Some(Value::Array(items)) => items
            .iter()
            .map(|item| {
                item.as_i64()
                    .ok_or_else(|| format!("{name} must be a list of whole numbers"))
            })
            .collect(),
        Some(_) => Err(format!("{name} must be a list of whole numbers")),
    }
}

fn optional_int(value: Option<&Value>, name: &str) -> Result<i64, String> {
    match value {
        None | Some(Value::Null) => Ok(0),
        Some(Value::Number(number)) => number
            .as_i64()
            .ok_or_else(|| format!("{name} must be a whole number")),
        Some(_) => Err(format!("{name} must be a whole number")),
    }
}

/// `YYYY-MM-DD` and a real day: not a timestamp, a week date or a date with the dashes left out.
fn plain_date(text: &str) -> bool {
    let shaped = text.len() == 10
        && text.bytes().enumerate().all(|(index, byte)| match index {
            4 | 7 => byte == b'-',
            _ => byte.is_ascii_digit(),
        });
    shaped && day_of(text).is_ok()
}

/// A whole number from 0 to `max`; the minute counts a homework can hold. Anything else is refused
/// before arithmetic can overflow.
fn bounded_int(value: Option<&Value>, name: &str, max: i64) -> Result<i64, String> {
    let number = optional_int(value, name)?;
    if (0..=max).contains(&number) {
        Ok(number)
    } else {
        Err(format!("{name} must be from 0 to {max}"))
    }
}

fn required_int(fields: &Map<String, Value>, name: &str) -> Result<i64, String> {
    fields
        .get(name)
        .and_then(Value::as_i64)
        .ok_or_else(|| format!("{name} must be a whole number"))
}

fn required_str<'a>(fields: &'a Map<String, Value>, name: &str) -> Result<&'a str, String> {
    fields
        .get(name)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("{name} must be text"))
}

fn first_day(fields: &Map<String, Value>) -> Result<i64, String> {
    fields
        .get("days")
        .and_then(Value::as_array)
        .and_then(|days| days.first())
        .and_then(Value::as_i64)
        .ok_or_else(|| "session is missing a numeric first day".to_string())
}
