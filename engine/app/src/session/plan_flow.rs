//! Plan continuation for the desktop window (`desktop/native/controller.py`): what waits for a save
//! or a week read, how a settled edit explains a lost time, and whether Delete or Plan may run.
//! The window still draws, sends requests and applies the ordered steps this returns.

use std::collections::HashSet;

use flexweek_engine::desk::planning::{clear_stale_pins, settle_placements_after_deadline};
use flexweek_engine::shown::stored_weeks;
use flexweek_engine::stored::{self, py_int, py_str, truthy};
use flexweek_engine::{EngineError, ErrorKind};
use serde_json::{Map, Value, json};

use super::unfinished::{self, ClockNow};

pub const UNREACHABLE_PLAN: &str = "Can't reach FlexWeek, so nothing was planned. Try again.";
pub const DELETE_WAIT: &str = "Saving your last change… Try Delete again in a moment.";

/// What one saved plan asked the window to do, in the order `_post_pending` did it.
#[derive(Debug, Clone, PartialEq)]
pub enum PendingStep {
    SayStatus,
    Say,
    InvalidateMonths,
    SpreadNext {
        assignment_id: String,
        session_min: i64,
        from_date: String,
    },
    SolveOnly {
        ids: Vec<String>,
    },
    SolveReplan,
    SaveFinished,
    RepeatsKept {
        notice: String,
    },
    SaveAnswered {
        point_id: String,
        doubled: Vec<Value>,
    },
    EmitPlanned,
    ClearReminderWeek,
    LoadDestination {
        week: String,
    },
    /// Follow the new first day, then these steps only when that follow did not start a read.
    Refollow {
        then: Vec<PendingStep>,
    },
    ReloadOpen,
    RunWaiting,
}

impl PendingStep {
    pub fn to_json(&self) -> Value {
        match self {
            Self::SayStatus => json!({"kind": "say_status"}),
            Self::Say => json!({"kind": "say"}),
            Self::InvalidateMonths => json!({"kind": "invalidate_months"}),
            Self::SpreadNext {
                assignment_id,
                session_min,
                from_date,
            } => json!({
                "kind": "spread_next",
                "assignment_id": assignment_id,
                "session_min": session_min,
                "from_date": from_date,
            }),
            Self::SolveOnly { ids } => json!({"kind": "solve_only", "ids": ids}),
            Self::SolveReplan => json!({"kind": "solve_replan"}),
            Self::SaveFinished => json!({"kind": "save_finished"}),
            Self::RepeatsKept { notice } => json!({"kind": "repeats_kept", "notice": notice}),
            Self::SaveAnswered { point_id, doubled } => json!({
                "kind": "save_answered",
                "point_id": point_id,
                "doubled": doubled,
            }),
            Self::EmitPlanned => json!({"kind": "emit_planned"}),
            Self::ClearReminderWeek => json!({"kind": "clear_reminder_week"}),
            Self::LoadDestination { week } => json!({"kind": "load_destination", "week": week}),
            Self::Refollow { then } => json!({
                "kind": "refollow",
                "then": then.iter().map(Self::to_json).collect::<Vec<_>>(),
            }),
            Self::ReloadOpen => json!({"kind": "reload_open"}),
            Self::RunWaiting => json!({"kind": "run_waiting"}),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SpreadNext {
    pub assignment_id: String,
    pub session_min: i64,
    pub from_date: String,
}

/// The continuation flags the window used to keep on the session. Ordered ids keep the order the
/// window's sets gained them, which is the order a later Plan receives.
#[derive(Debug, Clone, PartialEq)]
pub struct PlanFlow {
    pub plan_after_save: Vec<String>,
    pub plan_after_load: Vec<String>,
    pub split_whole: Vec<String>,
    pub split_planned: Vec<String>,
    pub replan_after_save: bool,
    pub replan_after_load: bool,
    pub spread_after_save: Option<SpreadNext>,
    pub allow_split_pending: Option<String>,
    pub fresh_plan: bool,
    pub seen_unfinished: Vec<String>,
    pub needs_time: Map<String, Value>,
}

impl Default for PlanFlow {
    fn default() -> Self {
        Self {
            plan_after_save: Vec::new(),
            plan_after_load: Vec::new(),
            split_whole: Vec::new(),
            split_planned: Vec::new(),
            replan_after_save: false,
            replan_after_load: false,
            spread_after_save: None,
            allow_split_pending: None,
            fresh_plan: false,
            seen_unfinished: Vec::new(),
            needs_time: Map::new(),
        }
    }
}

impl PlanFlow {
    pub fn post_pending_ok(
        &mut self,
        input: &PostPending,
    ) -> Result<Vec<PendingStep>, EngineError> {
        let planned = truthy(Some(&input.planned));
        let mut steps = Vec::new();
        // `planned` says it, with Undo.
        #[allow(clippy::needless_bool)]
        let say_status = if planned { true } else { false };
        steps.push(if say_status {
            PendingStep::SayStatus
        } else {
            PendingStep::Say
        });
        steps.push(PendingStep::InvalidateMonths);
        if let Some(spread) = self.spread_after_save.take() {
            steps.push(PendingStep::SpreadNext {
                assignment_id: spread.assignment_id,
                session_min: spread.session_min,
                from_date: spread.from_date,
            });
        }
        difference_update(&mut self.split_whole, &self.split_planned);
        self.split_planned.clear();
        let planned_next = std::mem::take(&mut self.plan_after_save);
        let open = truthy(Some(&input.open_week));
        let destination = destination_of(&input.destination)?;
        let reread = destination.is_none() && !input.refollow && !open && input.wrote_open;
        // A new first day opens its week next. A plan started before that read would replace it.
        let following = destination.is_none() && input.refollow;
        if !planned_next.is_empty() && (reread || following) {
            self.plan_after_load = planned_next;
        } else if !planned_next.is_empty() {
            steps.push(PendingStep::SolveOnly { ids: planned_next });
        }
        let replan_next = self.replan_after_save;
        self.replan_after_save = false;
        if replan_next && following {
            self.replan_after_load = true;
        } else if replan_next {
            steps.push(PendingStep::SolveReplan);
        }
        steps.push(PendingStep::SaveFinished);
        if let Some(notice) = notice_of(&input.repeat_notice)? {
            steps.push(PendingStep::RepeatsKept { notice });
        }
        let point_id = point_id_of(&input.point_id)?;
        let doubled = doubled_of(&input.doubled)?;
        if !point_id.is_empty() || !doubled.is_empty() {
            steps.push(PendingStep::SaveAnswered { point_id, doubled });
        }
        if planned {
            steps.push(PendingStep::EmitPlanned);
        }
        // Monday is 0, and the window treats that as no first-day shift, so the reminder week stays.
        if input.first_weekday != 0 {
            steps.push(PendingStep::ClearReminderWeek);
        }
        steps.push(follow_up(
            destination,
            input.refollow,
            open,
            input.wrote_open,
        ));
        Ok(steps)
    }

    /// A refused save drops the plan that was waiting on it. Sessions Allow splitting already made
    /// stay promised: only the plan now being saved is cleared.
    pub fn post_pending_err(&mut self) {
        self.plan_after_save.clear();
        self.split_planned.clear();
        self.replan_after_save = false;
        self.spread_after_save = None;
        self.allow_split_pending = None;
    }

    pub fn plan_after_save(
        &mut self,
        blocks: &[Value],
        assignment_id: &str,
    ) -> Result<(), EngineError> {
        extend_new(
            &mut self.plan_after_save,
            &waiting_block_ids(blocks, assignment_id)?,
        );
        Ok(())
    }

    pub fn plan_waiting_for_load(&mut self) -> Vec<PendingStep> {
        let mut steps = Vec::new();
        let planned = std::mem::take(&mut self.plan_after_load);
        if !planned.is_empty() {
            steps.push(PendingStep::SolveOnly { ids: planned });
        }
        let replan = self.replan_after_load;
        self.replan_after_load = false;
        if replan {
            steps.push(PendingStep::SolveReplan);
        }
        steps
    }

    pub fn solve_apply_commit(
        &mut self,
        input: &SolveCommitInput<'_>,
    ) -> Result<SolveCommit, EngineError> {
        self.needs_time = object_map(&input.needs_time, "needs_time")?;
        self.fresh_plan = true;
        let split_note = &input.split_note;
        let changed = input.changed;
        let computed_dirty = input.dirty || changed || truthy(Some(split_note));
        let history_label = if truthy(Some(split_note)) {
            Some("the focus split".to_string())
        } else if changed {
            Some("planning the week".to_string())
        } else {
            None
        };
        let prior_updates = if changed {
            Some(input.prior_updates.clone())
        } else {
            None
        };
        let step_id = if changed && truthy(Some(&input.prior_updates)) {
            Some(input.step_id.clone())
        } else {
            None
        };
        let assignments_dirty = !input.dirty_assignments.is_empty();
        let clear_plan_step_id = computed_dirty || assignments_dirty;
        let placed_where = if truthy(Some(&input.placed_where)) {
            Some(text_of(&input.placed_where, "placed_where")?)
        } else {
            None
        };
        // apply_plan writes this flag before the window reads it back, so a focus-split note
        // that dirties the record is saved rather than said and dropped.
        let early = !computed_dirty && !assignments_dirty;
        let split_planned = if early {
            None
        } else {
            let next = intersect(input.targets, &self.split_whole);
            self.split_planned = next.clone();
            Some(next)
        };
        Ok(SolveCommit {
            history_label,
            dirty: computed_dirty,
            prior_updates,
            step_id,
            clear_plan_step_id,
            placed_where,
            placed_note: input.placed_note.clone(),
            say: early,
            save: !early,
            plan: changed && !(input.join && input.only_is_some),
            split_planned,
        })
    }

    /// Drop the sessions this attempt added, once the caller knows the plan ticket is still the
    /// live one. An empty left set is the same as no rollback: notes stay as they were.
    pub fn solve_err_rollback(
        &mut self,
        blocks: &[Value],
        new_left: Option<&[String]>,
        dirty_before: &Value,
    ) -> Result<SolveRollback, EngineError> {
        let Some(left) = new_left.filter(|ids| !ids.is_empty()) else {
            return Ok(SolveRollback {
                rollback: false,
                blocks: Vec::new(),
                dirty: Value::Null,
            });
        };
        let mut kept = Vec::new();
        for block in blocks {
            let id = block_id_present(block)?;
            if !left.iter().any(|drop| drop == id) {
                kept.push(block.clone());
            }
        }
        self.needs_time = forget_settled_notes(&kept, &self.needs_time)?;
        Ok(SolveRollback {
            rollback: true,
            blocks: kept,
            dirty: dirty_before.clone(),
        })
    }

    pub fn consume_plan_review(&mut self, trace: Option<&Value>) -> Option<Value> {
        if !self.fresh_plan {
            return None;
        }
        self.fresh_plan = false;
        trace.cloned()
    }

    pub fn consume_unfinished(&mut self, week_start: &str, items: &[Value]) -> Vec<Value> {
        if items.is_empty() || self.seen_unfinished.iter().any(|seen| seen == week_start) {
            return Vec::new();
        }
        insert_new(&mut self.seen_unfinished, week_start.to_string());
        items.to_vec()
    }

    /// Stop the preview and forget the Allow splitting promise. A missing homework or one already
    /// finished has nothing to spread.
    pub fn preview_spread_stop(&mut self, item: Option<&Value>) -> Result<bool, EngineError> {
        let stop = match item {
            None => true,
            Some(item) => {
                let _ = as_object(item, "assignment")?;
                truthy(item.get("completed"))
            }
        };
        if stop {
            self.allow_split_pending = None;
        }
        Ok(stop)
    }

    pub fn confirm_spread_transition(
        &mut self,
        made: &[String],
        plan_ids: &[String],
        phase: SpreadPhase,
    ) {
        match phase {
            SpreadPhase::Stage => {
                extend_new(&mut self.plan_after_save, plan_ids);
                difference_update(&mut self.split_whole, made);
                extend_new(&mut self.split_whole, plan_ids);
            }
            SpreadPhase::Finish { ok } => {
                self.allow_split_pending = None;
                if !ok {
                    difference_update(&mut self.plan_after_save, plan_ids);
                    difference_update(&mut self.split_whole, plan_ids);
                }
            }
        }
    }
}

/// The save answer `_post_pending` reads, plus the two facts the window already computed.
pub struct PostPending {
    pub planned: Value,
    pub open_week: Value,
    pub destination: Value,
    pub repeat_notice: Value,
    pub point_id: Value,
    pub doubled: Value,
    pub refollow: bool,
    pub wrote_open: bool,
    pub first_weekday: i64,
}

pub struct SolveCommitInput<'a> {
    pub needs_time: Value,
    pub split_note: Value,
    pub changed: bool,
    pub placed_note: String,
    pub placed_where: Value,
    pub dirty: bool,
    pub dirty_assignments: &'a [String],
    pub prior_updates: Value,
    pub targets: &'a [String],
    pub join: bool,
    pub only_is_some: bool,
    pub step_id: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct SolveCommit {
    pub history_label: Option<String>,
    pub dirty: bool,
    pub prior_updates: Option<Value>,
    pub step_id: Option<String>,
    pub clear_plan_step_id: bool,
    pub placed_where: Option<String>,
    pub placed_note: String,
    pub say: bool,
    pub save: bool,
    pub plan: bool,
    pub split_planned: Option<Vec<String>>,
}

impl SolveCommit {
    pub fn to_json(&self) -> Value {
        json!({
            "history_label": self.history_label,
            "dirty": self.dirty,
            "prior_updates": self.prior_updates.clone().unwrap_or(Value::Null),
            "step_id": self.step_id,
            "clear_plan_step_id": self.clear_plan_step_id,
            "placed_where": self.placed_where,
            "placed_note": self.placed_note,
            "kind": if self.say { "say" } else { "save" },
            "plan": self.plan,
            "split_planned": self.split_planned,
        })
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct SolveRollback {
    pub rollback: bool,
    pub blocks: Vec<Value>,
    pub dirty: Value,
}

impl SolveRollback {
    pub fn to_json(&self) -> Value {
        json!({
            "rollback": self.rollback,
            "blocks": self.blocks,
            "dirty": self.dirty,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SpreadPhase {
    /// Before `confirm_preview`, so a save that preview starts can still see the promise.
    Stage,
    Finish {
        ok: bool,
    },
}

#[derive(Debug, Clone, PartialEq)]
pub enum DeleteHomework {
    Absent,
    Wait,
    Ready { key: String },
}

impl DeleteHomework {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Absent => json!({"kind": "absent"}),
            Self::Wait => json!({"kind": "wait", "say": DELETE_WAIT}),
            Self::Ready { key } => json!({"kind": "ready", "key": key}),
        }
    }
}

pub struct TouchSettle {
    pub blocks: Vec<Value>,
    pub lost: Vec<Value>,
    pub needs_time: Map<String, Value>,
    pub clear_selection: bool,
}

impl TouchSettle {
    pub fn to_json(&self) -> Value {
        json!({
            "blocks": self.blocks,
            "lost": self.lost,
            "needs_time": self.needs_time,
            "clear_selection": self.clear_selection,
        })
    }
}

/// `(week_start, revision)` pairs the open week is read from. Empty stored parts fall through to
/// the revision list zipped with the Mondays that week covers, strictly.
pub fn stored_week_rows(
    stored_parts: &Value,
    revision: &Value,
    week_start: &str,
) -> Result<Vec<(String, i64)>, EngineError> {
    if truthy(Some(stored_parts)) {
        let parts = list_of(stored_parts, "stored parts")?;
        let mut rows = Vec::new();
        for part in parts {
            let start = subscript(part, "week_start")?;
            let revision = subscript(part, "revision")?;
            rows.push((py_str(start), py_int(revision)?));
        }
        return Ok(rows);
    }
    if let Some(parts) = revision.as_array() {
        let weeks = stored_weeks(week_start)?;
        if weeks.len() != parts.len() {
            let message = if weeks.len() > parts.len() {
                "zip() argument 2 is shorter than argument 1"
            } else {
                "zip() argument 2 is longer than argument 1"
            };
            return Err(EngineError::value(message));
        }
        let mut rows = Vec::new();
        for (week, revision) in weeks.iter().zip(parts) {
            rows.push((week.clone(), py_int(revision)?));
        }
        return Ok(rows);
    }
    Ok(vec![(week_start.to_string(), py_int(revision)?)])
}

pub fn stored_weeks_json(stored_parts: &Value, revision: &Value, week_start: &str) -> Value {
    match stored_week_rows(stored_parts, revision, week_start) {
        Ok(rows) => json!(rows),
        Err(error) => json!({
            "error": error.message,
            "kind": kind_name(error.kind),
        }),
    }
}

pub fn fail_words(planning: bool, status: i64, message: &str) -> String {
    if planning && status == 0 {
        UNREACHABLE_PLAN.to_string()
    } else {
        message.to_string()
    }
}

// One argument per fact the window already holds. Folding them would only rename the same facts.
#[allow(clippy::too_many_arguments)]
pub fn touch_settle(
    blocks: &[Value],
    assignments: &Map<String, Value>,
    homework: &[Value],
    week_start: &str,
    keep: &[String],
    selected_block_id: Option<&str>,
    now: &ClockNow<'_>,
    needs_time: &Map<String, Value>,
) -> Result<TouchSettle, EngineError> {
    let merged = merge_homework(assignments, homework)?;
    let overdue = unfinished::overdue_ids(&merged, now).map_err(EngineError::value)?;
    let overdue_set: HashSet<&str> = overdue.iter().map(String::as_str).collect();
    let mut after_deadline = Vec::new();
    for block in blocks {
        let _ = as_object(block, "block")?;
        let assignment = block.get("assignment_id").and_then(Value::as_str);
        if truthy(block.get("start")) && assignment.is_some_and(|id| overdue_set.contains(id)) {
            after_deadline.push(Value::from(block_id_present(block)?));
        }
    }
    let keep_values: Vec<Value> = keep.iter().cloned().map(Value::from).collect();
    let (settled, lost) = settle_placements_after_deadline(
        &Value::Array(blocks.to_vec()),
        &Value::Object(merged),
        week_start,
        &Value::Array(keep_values),
        true,
        &Value::Array(after_deadline),
    )?;
    let settled_blocks = clear_stale_pins(&settled)?;
    let mut notes = needs_time.clone();
    for note in &lost {
        let id = text_of(subscript(note, "block_id")?, "block_id")?;
        let message = subscript(note, "message")?.clone();
        notes.insert(id, message);
    }
    let notes = forget_settled_notes(&settled_blocks, &notes)?;
    let ids: HashSet<&str> = settled_blocks
        .iter()
        .map(block_id_present)
        .collect::<Result<_, _>>()?;
    // Nothing selected is not a member of the id set, so the window clears the selection then too.
    let clear_selection = selected_block_id.is_none_or(|id| !ids.contains(id));
    Ok(TouchSettle {
        blocks: settled_blocks,
        lost,
        needs_time: notes,
        clear_selection,
    })
}

pub fn forget_settled_notes(
    blocks: &[Value],
    needs_time: &Map<String, Value>,
) -> Result<Map<String, Value>, EngineError> {
    let mut waiting = HashSet::new();
    for block in blocks {
        let _ = as_object(block, "block")?;
        if block.get("kind").and_then(Value::as_str) == Some("flexible")
            && !truthy(block.get("completed"))
            && !truthy(block.get("start"))
        {
            waiting.insert(block_id_present(block)?);
        }
    }
    let mut kept = Map::new();
    for (key, value) in needs_time {
        if waiting.contains(key.as_str()) {
            kept.insert(key.clone(), value.clone());
        }
    }
    Ok(kept)
}

pub fn plan_notes(trace: Option<&Value>, needs_time: &Map<String, Value>) -> Option<Value> {
    if let Some(trace) = trace {
        return Some(trace.clone());
    }
    if needs_time.is_empty() {
        return None;
    }
    let explanations = needs_time
        .iter()
        .map(|(key, value)| json!({"block_id": key, "message": value}))
        .collect::<Vec<_>>();
    Some(json!({"placed": [], "explanations": explanations}))
}

pub fn delete_homework_guard(
    account_id: Option<&Value>,
    assignment_id: &str,
    item: Option<&Value>,
    conflict: bool,
    busy: bool,
    dirty: bool,
    pending_save: &Value,
) -> Result<DeleteHomework, EngineError> {
    if item.is_none() || account_id.is_none() || conflict {
        return Ok(DeleteHomework::Absent);
    }
    if busy || dirty || !pending_save.is_null() {
        return Ok(DeleteHomework::Wait);
    }
    let Some(item) = item else {
        return Ok(DeleteHomework::Absent);
    };
    let _ = as_object(item, "assignment")?;
    let revision = match item.get("revision") {
        Some(value) if truthy(Some(value)) => py_int(value)?,
        _ => 0,
    };
    let Some(account_id) = account_id else {
        return Ok(DeleteHomework::Absent);
    };
    let account = account_text(account_id)?;
    Ok(DeleteHomework::Ready {
        key: format!("delete-homework|{account}|{assignment_id}|{revision}"),
    })
}

pub fn did_these_ids(assignments: &Map<String, Value>, assignment_ids: &[String]) -> Vec<String> {
    assignment_ids
        .iter()
        .filter(|id| assignments.contains_key(id.as_str()))
        .cloned()
        .collect()
}

fn follow_up(
    destination: Option<String>,
    refollow: bool,
    open: bool,
    wrote_open: bool,
) -> PendingStep {
    if let Some(week) = destination {
        return PendingStep::LoadDestination { week };
    }
    let next = if !open && wrote_open {
        PendingStep::ReloadOpen
    } else {
        PendingStep::RunWaiting
    };
    if refollow {
        PendingStep::Refollow { then: vec![next] }
    } else {
        next
    }
}

fn waiting_block_ids(blocks: &[Value], assignment_id: &str) -> Result<Vec<String>, EngineError> {
    let mut ids = Vec::new();
    for block in blocks {
        let _ = as_object(block, "block")?;
        if block.get("assignment_id").and_then(Value::as_str) == Some(assignment_id)
            && !truthy(block.get("start"))
            && !truthy(block.get("completed"))
        {
            ids.push(block_id_present(block)?.to_string());
        }
    }
    Ok(ids)
}

fn merge_homework(
    assignments: &Map<String, Value>,
    homework: &[Value],
) -> Result<Map<String, Value>, EngineError> {
    let mut merged = assignments.clone();
    for item in homework {
        let id = text_of(subscript(item, "id")?, "id")?;
        merged.insert(id, item.clone());
    }
    Ok(merged)
}

fn destination_of(value: &Value) -> Result<Option<String>, EngineError> {
    if value.is_null() {
        return Ok(None);
    }
    Ok(Some(text_of(value, "destination")?))
}

fn notice_of(value: &Value) -> Result<Option<String>, EngineError> {
    if !truthy(Some(value)) {
        return Ok(None);
    }
    Ok(Some(text_of(value, "repeat_notice")?))
}

fn point_id_of(value: &Value) -> Result<String, EngineError> {
    if value.is_null() {
        return Ok(String::new());
    }
    text_of(value, "point_id")
}

fn doubled_of(value: &Value) -> Result<Vec<Value>, EngineError> {
    value
        .as_array()
        .cloned()
        .ok_or_else(|| type_error("doubled must be a list"))
}

fn account_text(value: &Value) -> Result<String, EngineError> {
    match value {
        Value::String(text) => Ok(text.clone()),
        Value::Number(number) => number
            .as_i64()
            .map(|id| id.to_string())
            .ok_or_else(|| EngineError::value("account id is too large")),
        _ => Err(type_error(format!(
            "account id must be text or a number, not '{}'",
            stored::type_name(value)
        ))),
    }
}

fn object_map(value: &Value, what: &str) -> Result<Map<String, Value>, EngineError> {
    value
        .as_object()
        .cloned()
        .ok_or_else(|| type_error(format!("{what} must be an object")))
}

fn as_object<'a>(value: &'a Value, _what: &str) -> Result<&'a Map<String, Value>, EngineError> {
    value.as_object().ok_or_else(|| EngineError {
        kind: ErrorKind::Attribute,
        message: format!(
            "'{}' object has no attribute 'get'",
            stored::type_name(value)
        ),
    })
}

fn list_of<'a>(value: &'a Value, what: &str) -> Result<&'a [Value], EngineError> {
    value
        .as_array()
        .map(Vec::as_slice)
        .ok_or_else(|| type_error(format!("{what} are a list")))
}

fn subscript<'a>(value: &'a Value, key: &str) -> Result<&'a Value, EngineError> {
    match value.as_object() {
        Some(map) => map.get(key).ok_or_else(|| EngineError::key(key)),
        None => Err(type_error(format!(
            "'{}' object is not subscriptable",
            stored::type_name(value)
        ))),
    }
}

fn text_of(value: &Value, what: &str) -> Result<String, EngineError> {
    value
        .as_str()
        .map(str::to_string)
        .ok_or_else(|| type_error(format!("{what} must be text")))
}

fn block_id_present(block: &Value) -> Result<&str, EngineError> {
    subscript(block, "id")?
        .as_str()
        .ok_or_else(|| type_error("block id must be text"))
}

fn insert_new(ids: &mut Vec<String>, id: String) {
    if !ids.iter().any(|have| have == &id) {
        ids.push(id);
    }
}

fn extend_new(ids: &mut Vec<String>, extra: &[String]) {
    for id in extra {
        insert_new(ids, id.clone());
    }
}

fn difference_update(ids: &mut Vec<String>, drop: &[String]) {
    ids.retain(|id| !drop.iter().any(|gone| gone == id));
}

/// Members of `left` that `right` also holds, in `left`'s order.
fn intersect(left: &[String], right: &[String]) -> Vec<String> {
    left.iter()
        .filter(|id| right.iter().any(|have| have == *id))
        .cloned()
        .collect()
}

fn type_error(message: impl Into<String>) -> EngineError {
    EngineError {
        kind: ErrorKind::Type,
        message: message.into(),
    }
}

/// The status line while a delete is in flight. The ellipsis is U+2026, as the other waits are.
pub fn deleting_status(title: &str) -> String {
    format!("Deleting {title}\u{2026}")
}

/// A finished delete clears the reminder week except when Monday is the first day (0), which
/// the window treats as no shift. Same rule as a save's `ClearReminderWeek`.
pub fn delete_clears_reminder_week(deleted: bool, first_weekday: i64) -> bool {
    deleted && first_weekday != 0
}

/// A save does not start while signed out, while the week conflicts, or while a request is busy.
pub fn save_skipped(signed_in: bool, conflict: bool, busy: bool) -> bool {
    !signed_in || conflict || busy
}

/// Retry only a save that is still waiting, and not while that week is in conflict.
pub fn retry_save_goes(pending: bool, conflict: bool) -> bool {
    pending && !conflict
}

fn kind_name(kind: ErrorKind) -> &'static str {
    match kind {
        ErrorKind::Value => "ValueError",
        ErrorKind::Type => "TypeError",
        ErrorKind::Key => "KeyError",
        ErrorKind::Attribute => "AttributeError",
        ErrorKind::Overflow => "OverflowError",
        ErrorKind::Index => "IndexError",
        ErrorKind::Lookup => "LookupError",
        ErrorKind::ZeroDivision => "ZeroDivisionError",
        ErrorKind::Stop => "StopIteration",
        ErrorKind::LookName => "LookNameProblem",
        ErrorKind::KeyRepr => "KeyError",
    }
}
