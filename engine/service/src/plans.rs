//! The Plan button, as `backend/app.py`'s `POST /api/solve` answers it: the request is checked as
//! `SolveRequest` checks it, sessions take their homework's due times, the account's study hours and planning
//! settings shape where things may go (moved onto the right days for a week shown from another weekday),
//! and the engine's planner places the open blocks; "I missed this" and "running late" ask it to plan again
//! around the change. Nothing is saved.

use std::path::Path;

use flexweek_engine::time::{is_calendar_date, is_week_start};
use flexweek_engine::validate::{time_block, week_request, whole_number};
use flexweek_engine::{shown, solver};
use serde_json::{Map, Value, json};

use crate::accounts::INVALID_INPUT;
use crate::blocks::{BlockRefused, Checked, refuse};
use crate::{Refusal, ServiceError, ServiceResult};

/// "I missed this": the locked block and the day it was missed, and the plan shown before.
#[derive(Clone, Debug)]
pub struct Recover {
    pub missed_block_id: String,
    pub missed_day: i64,
    pub previous_placed: Vec<Value>,
}

/// "Running late" on a day: how late, from when, the plan shown before, and the time it is now.
#[derive(Clone, Debug)]
pub struct Late {
    pub day: i64,
    pub minutes: i64,
    pub from_start: String,
    pub previous_placed: Vec<Value>,
    pub now_floor: Option<(i64, i64)>,
}

/// A Plan request as `SolveRequest` reads it.
#[derive(Clone, Debug)]
pub struct PlanRequest {
    pub blocks: Vec<Value>,
    pub recover: Option<Recover>,
    pub running_late: Option<Late>,
    pub week_start: Option<String>,
    pub now_floor: Option<(i64, i64)>,
}

impl PlanRequest {
    /// The request as `SolveRequest.model_dump(mode="json")` writes it, for the parity test.
    pub fn to_value(&self) -> Value {
        let floor = |floor: Option<(i64, i64)>| floor.map_or(Value::Null, |(a, b)| json!([a, b]));
        json!({
            "blocks": self.blocks,
            "recover": self.recover.as_ref().map(|recover| json!({
                "missed_block_id": recover.missed_block_id,
                "missed_day": recover.missed_day,
                "previous_placed": recover.previous_placed,
            })),
            "running_late": self.running_late.as_ref().map(|late| json!({
                "day": late.day,
                "minutes": late.minutes,
                "from_start": late.from_start,
                "previous_placed": late.previous_placed,
                "now_floor": floor(late.now_floor),
            })),
            "week_start": self.week_start,
            "now_floor": floor(self.now_floor),
        })
    }
}

fn int_in(value: Option<&Value>, low: i128, high: i128) -> Option<i64> {
    value
        .and_then(whole_number)
        .filter(|int| (low..=high).contains(int))
        .map(|int| int as i64)
}

/// `tuple[int, int] | None`: null, or a list of exactly two whole numbers.
fn floor_of(value: Option<&Value>) -> Checked<Option<(i64, i64)>> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Array(items)) if items.len() == 2 => {
            let read = |item: &Value| whole_number(item).and_then(|int| i64::try_from(int).ok());
            match (read(&items[0]), read(&items[1])) {
                (Some(day), Some(minute)) => Ok(Some((day, minute))),
                _ => refuse("now_floor must be two whole numbers"),
            }
        }
        Some(_) => refuse("now_floor must be two whole numbers"),
    }
}

/// `list[TimeBlock]` of at most 100 with unique ids, written as the model writes them.
fn previous_of(value: Option<&Value>) -> Checked<Vec<Value>> {
    let Some(Value::Array(items)) = value else {
        return refuse("previous_placed must be a list");
    };
    if items.len() > 100 {
        return refuse("previous_placed holds at most 100 blocks");
    }
    let mut ids = std::collections::BTreeSet::new();
    let mut blocks = Vec::with_capacity(items.len());
    for item in items {
        let block = time_block(item).map_err(BlockRefused)?;
        if !ids.insert(block.id.clone()) {
            return refuse("previous placement ids must be unique");
        }
        blocks.push(block.to_value());
    }
    Ok(blocks)
}

fn recover_of(value: &Value) -> Checked<Recover> {
    let Value::Object(fields) = value else {
        return refuse("recover must be an object");
    };
    let missed_block_id = match fields.get("missed_block_id") {
        Some(Value::String(id)) if (1..=80).contains(&id.chars().count()) => id.clone(),
        _ => return refuse("missed_block_id must be text of 1 to 80 characters"),
    };
    let Some(missed_day) = int_in(fields.get("missed_day"), 0, 6) else {
        return refuse("missed_day must be 0 to 6");
    };
    let previous_placed = previous_of(fields.get("previous_placed"))?;
    Ok(Recover {
        missed_block_id,
        missed_day,
        previous_placed,
    })
}

fn late_of(value: &Value) -> Checked<Late> {
    let Value::Object(fields) = value else {
        return refuse("running_late must be an object");
    };
    let known = [
        "day",
        "minutes",
        "from_start",
        "previous_placed",
        "now_floor",
    ];
    if let Some(extra) = fields.keys().find(|key| !known.contains(&key.as_str())) {
        return refuse(format!("running_late does not take {extra}"));
    }
    let Some(day) = int_in(fields.get("day"), 0, 6) else {
        return refuse("day must be 0 to 6");
    };
    // Literal[15, 30, 60]: true and 30.0 read as numbers, text does not.
    let minutes = match fields.get("minutes") {
        Some(value @ (Value::Bool(_) | Value::Number(_))) => whole_number(value),
        _ => None,
    };
    let minutes = match minutes {
        Some(minutes @ (15 | 30 | 60)) => minutes as i64,
        _ => return refuse("minutes must be 15, 30 or 60"),
    };
    let from_start = match fields.get("from_start") {
        Some(Value::String(text)) if text.chars().count() == 5 => text.clone(),
        _ => return refuse("from_start must be HH:MM"),
    };
    let on_grid = crate::preferences::grid_minutes(&from_start)
        .is_some_and(|at| flexweek_engine::time::start_fits_day(at) && at % 15 == 0);
    if !on_grid {
        return refuse("from_start must be on the 00:00-24:00 grid");
    }
    let previous_placed = previous_of(fields.get("previous_placed"))?;
    let now_floor = floor_of(fields.get("now_floor"))?;
    Ok(Late {
        day,
        minutes,
        from_start,
        previous_placed,
        now_floor,
    })
}

/// A Plan request as `SolveRequest` reads it (unknown fields at the top and in `recover` are ignored, as
/// the model ignores them).
pub fn check_plan_request(given: &Value) -> Checked<PlanRequest> {
    let Value::Object(fields) = given else {
        return refuse("a plan request must be an object");
    };
    let Some(blocks) = fields.get("blocks") else {
        return refuse("blocks is required");
    };
    let checked = week_request(&json!({ "blocks": blocks })).map_err(BlockRefused)?;
    let recover = match fields.get("recover") {
        None | Some(Value::Null) => None,
        Some(value) => Some(recover_of(value)?),
    };
    let running_late = match fields.get("running_late") {
        None | Some(Value::Null) => None,
        Some(value) => Some(late_of(value)?),
    };
    let week_start = match fields.get("week_start") {
        None | Some(Value::Null) => None,
        Some(Value::String(day)) if is_week_start(day) || is_calendar_date(day) => {
            Some(day.clone())
        }
        Some(_) => return refuse("week_start must be a Monday or a calendar date"),
    };
    let now_floor = floor_of(fields.get("now_floor"))?;
    if week_start.is_none()
        && checked
            .blocks
            .iter()
            .any(|block| block.assignment_id.is_some())
    {
        return refuse("week_start is required when a block has assignment_id");
    }
    if recover.is_some() && running_late.is_some() {
        return refuse("recover and running_late cannot both be set");
    }
    if let Some(recover) = &recover {
        let found = checked
            .blocks
            .iter()
            .find(|block| block.id == recover.missed_block_id);
        let fits = found.is_some_and(|block| {
            block.kind == "locked"
                && block.days.contains(&recover.missed_day)
                && !block.missed_days.contains(&recover.missed_day)
        });
        if !fits {
            return refuse("missed occurrence must identify a locked block on that day");
        }
    }
    Ok(PlanRequest {
        blocks: checked
            .blocks
            .iter()
            .map(|block| block.to_value())
            .collect(),
        recover,
        running_late,
        week_start,
        now_floor,
    })
}

fn invalid() -> ServiceError {
    Refusal::Invalid(INVALID_INPUT.to_string()).into()
}

/// The stored study hours, protected times and planning settings, as the planner takes them: (time already
/// taken per day, work windows, settings). Windows are read as the app's models read them.
fn planning_inputs(
    availability: Option<&str>,
    preferences: Option<&str>,
) -> ServiceResult<(Vec<u128>, Value, Option<Value>)> {
    let found = flexweek_store::solve_availability(availability, |kind, items| {
        let read: fn(&Value) -> Checked<Value> = match kind {
            "protected" => crate::preferences::protected_window,
            "study" => crate::preferences::study_window,
            _ => crate::preferences::work_window,
        };
        items
            .as_array()
            .map(|items| items.iter().map(read).collect::<Checked<Vec<_>>>())
            .unwrap_or_else(|| Ok(Vec::new()))
            .map(Value::Array)
    })
    .map_err(|relay| match relay {
        flexweek_store::Relay::Store(error) => ServiceError::from(error),
        flexweek_store::Relay::Caller(refused) => {
            ServiceError::Broken(format!("stored study hours no longer read: {}", refused.0))
        }
    })?;
    let work = found
        .work
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .map(crate::preferences::work_window)
        .collect::<Checked<Vec<_>>>()
        .map_err(|refused| ServiceError::Broken(format!("a work window: {}", refused.0)))?;
    let rules =
        match preferences {
            Some(text) => Some(serde_json::from_str(text).map_err(|error| {
                flexweek_store::StoreError::Json {
                    text: text.to_string(),
                    error,
                }
            })?),
            None => None,
        };
    Ok((found.occupancy, Value::Array(work), rules))
}

fn engine_blocks(blocks: &[Value]) -> ServiceResult<Vec<solver::TimeBlock>> {
    blocks
        .iter()
        .map(|block| solver::block_from_value(block).map_err(ServiceError::from))
        .collect()
}

/// Plans the week from the Plan request, as `POST /api/solve` answers; `elapsed_ms` is how long the
/// request has run so far, for the planner's 150 ms budget. Nothing is saved.
pub fn plan(
    path: &Path,
    user_id: i64,
    given: &Value,
    elapsed_ms: &dyn Fn() -> f64,
) -> ServiceResult<Value> {
    let request = check_plan_request(given).map_err(|_| invalid())?;
    let ids: Vec<String> = request
        .blocks
        .iter()
        .filter_map(|block| block.get("assignment_id").and_then(Value::as_str))
        .map(str::to_string)
        .collect::<std::collections::BTreeSet<_>>()
        .into_iter()
        .collect();
    let (owned, availability, preferences) = crate::with_db(path, |conn| {
        let owned = if ids.is_empty() {
            Map::new()
        } else {
            let (all_own, rows) = flexweek_store::own_assignment_rows(conn, user_id, &ids)?;
            if !all_own {
                return Err(
                    Refusal::Invalid(crate::week_saves::ASSIGNMENT_UNKNOWN.to_string()).into(),
                );
            }
            let mut owned = Map::new();
            for (id, body, _) in rows {
                let body: Value = serde_json::from_str(&body).map_err(|error| {
                    flexweek_store::StoreError::Json {
                        text: body.clone(),
                        error,
                    }
                })?;
                owned.insert(id, body);
            }
            owned
        };
        let availability = flexweek_store::availability_json(conn, user_id)?;
        let preferences = flexweek_store::preference_row(conn, user_id)?;
        Ok((owned, availability, preferences))
    })?;
    let (mut occupancy, mut work, mut rules) =
        planning_inputs(availability.as_deref(), preferences.as_deref())?;
    if let Some(week_start) = &request.week_start
        && !is_week_start(week_start)
        && is_calendar_date(week_start)
    {
        // A week on screen from another day than Monday: each weekday's hours and the weekend go on the
        // days that weekday falls on.
        occupancy = shown::occupancy_on_shown_week(week_start, &occupancy)?;
        let windows = work.as_array().cloned().unwrap_or_default();
        work = Value::Array(
            shown::windows_on_shown_week(week_start, &windows)?
                .iter()
                .map(crate::preferences::work_window)
                .collect::<Checked<Vec<_>>>()
                .map_err(|refused| ServiceError::Broken(refused.0))?,
        );
        rules = match rules {
            Some(found) => Some(shown::rules_on_shown_week(week_start, &found)?),
            None => match shown::rules_on_shown_week(week_start, &Value::Null)? {
                Value::Null => None,
                found => Some(found),
            },
        };
    }
    let mut blocks = request.blocks.clone();
    let mut deadlines = Value::Null;
    let mut slack = Value::Null;
    if !ids.is_empty() {
        let week_start = request.week_start.as_deref().unwrap_or_default();
        let owned: std::collections::BTreeMap<String, Value> = owned.into_iter().collect();
        let (keep, found_deadlines, found_slack) =
            flexweek_engine::plan::prepare_solve(&blocks, week_start, &owned)?;
        blocks = keep
            .iter()
            .map(|block| {
                time_block(block)
                    .map(|checked| checked.to_value())
                    .map_err(|why| ServiceError::Broken(format!("a planned block: {why}")))
            })
            .collect::<ServiceResult<_>>()?;
        deadlines = Value::Object(
            found_deadlines
                .into_iter()
                .map(|(key, at)| {
                    (
                        key,
                        at.map_or(Value::Null, |(day, minute)| json!([day, minute])),
                    )
                })
                .collect(),
        );
        slack = Value::Object(
            found_slack
                .into_iter()
                .map(|(key, (day, minute))| (key, json!([day, minute])))
                .collect(),
        );
    }
    let overrides = solver::overrides_from(
        (!deadlines.is_null()).then_some(&deadlines),
        (!slack.is_null()).then_some(&slack),
    );
    let planned = engine_blocks(&blocks)?;
    let windows: Vec<solver::WorkWindow> = work
        .as_array()
        .map(|items| items.iter().map(solver::work_window_from_value).collect())
        .unwrap_or_default();
    let rules = rules
        .as_ref()
        .map(solver::plan_rules_from_value)
        .unwrap_or_default();
    let trace = if let Some(recover) = &request.recover {
        solver::reschedule_after_miss(
            &planned,
            &recover.missed_block_id,
            recover.missed_day,
            &engine_blocks(&recover.previous_placed)?,
            Some(&occupancy),
            Some(&windows),
            Some(&overrides),
            solver::SOLVE_BUDGET_MS,
            elapsed_ms,
            rules,
        )?
    } else if let Some(late) = &request.running_late {
        solver::reschedule_running_late(
            &planned,
            late.day,
            late.minutes,
            &late.from_start,
            &engine_blocks(&late.previous_placed)?,
            Some(&occupancy),
            Some(&windows),
            Some(&overrides),
            late.now_floor,
            solver::SOLVE_BUDGET_MS,
            elapsed_ms,
            rules,
        )?
    } else {
        solver::solve_with_rules(
            &planned,
            Some(&occupancy),
            Some(&windows),
            Some(&overrides),
            request.now_floor,
            solver::SOLVE_BUDGET_MS,
            elapsed_ms,
            rules,
        )?
    };
    written_trace(solver::trace_to_value(&trace))
}

/// The planner's answer as `SolveTrace.model_validate(...).model_dump()` writes it: placed and unplaced
/// blocks and the work windows written out in full by their models.
fn written_trace(mut trace: Value) -> ServiceResult<Value> {
    let Some(fields) = trace.as_object_mut() else {
        return Err(ServiceError::Broken(
            "the planner answered no object".into(),
        ));
    };
    for list in ["placed", "unplaced"] {
        if let Some(Value::Array(items)) = fields.get_mut(list) {
            for item in items.iter_mut() {
                *item = time_block(item)
                    .map(|block| block.to_value())
                    .map_err(|why| ServiceError::Broken(format!("a planned block: {why}")))?;
            }
        }
    }
    if let Some(Value::Array(items)) = fields.get_mut("work_windows") {
        for item in items.iter_mut() {
            *item = crate::preferences::work_window(item)
                .map_err(|refused| ServiceError::Broken(format!("a work window: {}", refused.0)))?;
        }
    }
    Ok(trace)
}
