//! Plan, Replan, Place now and Find a new time decisions (`flexweek_app::session::plan`) for the
//! Python window, with JSON text across. Wrong-shaped JSON is refused with ValueError.

use flexweek_app::session::plan::{
    PlanAnswerInput, PlanClock, PlanInput, WEEK_OVER, apply_auto_split, apply_plan_answer,
    first_placed, left_sentence, place_now_sentence, plan_sentence, prepare_plan,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::{Map, Value};

use crate::desk::fresh_id;
use crate::guard;

fn parse_json(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn as_object<'a>(value: &'a Value, what: &str) -> PyResult<&'a Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| PyValueError::new_err(format!("{what} must be a JSON object")))
}

fn req_field<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a Value> {
    map.get(key)
        .ok_or_else(|| PyValueError::new_err(format!("missing field {key:?}")))
}

fn req_bool(map: &Map<String, Value>, key: &str) -> PyResult<bool> {
    req_field(map, key)?
        .as_bool()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be a boolean")))
}

fn req_str<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a str> {
    req_field(map, key)?
        .as_str()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be a string")))
}

fn req_i64(map: &Map<String, Value>, key: &str) -> PyResult<i64> {
    req_field(map, key)?
        .as_i64()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be an integer")))
}

fn req_array<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a Vec<Value>> {
    req_field(map, key)?
        .as_array()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be a list")))
}

fn req_object<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a Map<String, Value>> {
    req_field(map, key)?
        .as_object()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be an object")))
}

fn opt_object<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<Option<&'a Value>> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(value) if value.is_object() => Ok(Some(value)),
        Some(_) => Err(PyValueError::new_err(format!(
            "{key} must be an object or null"
        ))),
    }
}

fn opt_map_of_objects<'a>(
    map: &'a Map<String, Value>,
    key: &str,
) -> PyResult<Option<&'a Map<String, Value>>> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Object(entries)) => {
            for (week, saved) in entries {
                if !saved.is_object() {
                    return Err(PyValueError::new_err(format!(
                        "{key}[{week:?}] must be an object"
                    )));
                }
            }
            Ok(Some(entries))
        }
        Some(_) => Err(PyValueError::new_err(format!(
            "{key} must be an object or null"
        ))),
    }
}

fn str_list(value: &Value, key: &str) -> PyResult<Vec<String>> {
    let items = value
        .as_array()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be a list of strings")))?;
    items
        .iter()
        .map(|item| {
            item.as_str()
                .map(str::to_string)
                .ok_or_else(|| PyValueError::new_err(format!("{key} must be a list of strings")))
        })
        .collect()
}

fn req_str_list(map: &Map<String, Value>, key: &str) -> PyResult<Vec<String>> {
    str_list(req_field(map, key)?, key)
}

fn opt_str_list(map: &Map<String, Value>, key: &str) -> PyResult<Option<Vec<String>>> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => Ok(Some(str_list(value, key)?)),
    }
}

fn req_clock<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<PlanClock<'a>> {
    let clock = req_object(map, key)?;
    Ok(PlanClock {
        today_iso: req_str(clock, "today_iso")?,
        hour: req_i64(clock, "hour")?,
        minute: req_i64(clock, "minute")?,
        second: req_i64(clock, "second")?,
        microsecond: req_i64(clock, "microsecond")?,
    })
}

/// Prepare a Plan, Replan, Place now or Find a new time request from JSON text.
#[pyfunction]
fn session_prepare_plan(payload: &str) -> PyResult<String> {
    guard(|| {
        let root = parse_json(payload, "plan input")?;
        let map = as_object(&root, "plan input")?;
        let saved_weeks = req_str_list(map, "saved_weeks")?;
        let split_whole = req_str_list(map, "split_whole")?;
        let only = opt_str_list(map, "only")?;
        let overdue = opt_str_list(map, "overdue")?;
        let input = PlanInput {
            planning: req_bool(map, "planning")?,
            conflict: req_bool(map, "conflict")?,
            pending_save: req_bool(map, "pending_save")?,
            week_start: req_str(map, "week_start")?,
            blocks: req_array(map, "blocks")?,
            assignments: req_object(map, "assignments")?,
            assignments_basis: req_array(map, "assignments_basis")?,
            preferences: opt_object(map, "preferences")?,
            saved_weeks: &saved_weeks,
            split_whole: &split_whole,
            clock: req_clock(map, "clock")?,
            everything: req_bool(map, "everything")?,
            only: only.as_deref(),
            earliest_first: req_bool(map, "earliest_first")?,
            prepared_weeks: opt_map_of_objects(map, "prepared_weeks")?,
            overdue: overdue.as_deref(),
        };
        let decision = prepare_plan(input).map_err(PyValueError::new_err)?;
        Ok(decision.to_json().to_string())
    })
}

/// Apply `/api/solve`'s trace onto the week, compute pre-split counts and run focus splitting.
#[pyfunction]
fn session_apply_plan_answer(py: Python<'_>, payload: &str) -> PyResult<String> {
    guard(|| {
        let root = parse_json(payload, "plan answer input")?;
        let map = as_object(&root, "plan answer input")?;
        let targets = req_str_list(map, "targets")?;
        let overdue = opt_str_list(map, "overdue")?;
        let new_left = opt_str_list(map, "new_left")?;
        let trace = req_field(map, "trace")?;
        if !trace.is_object() {
            return Err(PyValueError::new_err("trace must be an object"));
        }
        let input = PlanAnswerInput {
            original_blocks: req_array(map, "original_blocks")?,
            source_week: req_array(map, "source_week")?,
            trace,
            targets: &targets,
            assignments: req_object(map, "assignments")?,
            assignments_basis: req_array(map, "assignments_basis")?,
            week_start: req_str(map, "week_start")?,
            preferences: opt_object(map, "preferences")?,
            shares: req_array(map, "shares")?,
            needs_time: req_object(map, "needs_time")?,
            clock: req_clock(map, "clock")?,
            earliest_first: req_bool(map, "earliest_first")?,
            overdue: overdue.as_deref(),
            new_left: new_left.as_deref(),
        };
        let answer = apply_plan_answer(input, || fresh_id(py)).map_err(PyValueError::new_err)?;
        Ok(answer.to_json().to_string())
    })
}

/// Split placed homework blocks into focus chunks and breaks against pre-inflation source lengths.
#[pyfunction]
fn session_apply_auto_split(
    py: Python<'_>,
    blocks: &str,
    trace: &str,
    sources: &str,
    preferences: &str,
) -> PyResult<String> {
    guard(|| {
        let blocks = parse_json(blocks, "blocks")?;
        let Value::Array(blocks) = blocks else {
            return Err(PyValueError::new_err("blocks must be a list"));
        };
        let trace = parse_json(trace, "trace")?;
        if !trace.is_object() && !trace.is_null() {
            return Err(PyValueError::new_err("trace must be an object or null"));
        }
        let sources_val = parse_json(sources, "sources")?;
        let sources = match &sources_val {
            Value::Null => None,
            Value::Array(items) => Some(items.as_slice()),
            _ => return Err(PyValueError::new_err("sources must be a list or null")),
        };
        let prefs_val = parse_json(preferences, "preferences")?;
        let preferences = match &prefs_val {
            Value::Null => None,
            Value::Object(_) => Some(&prefs_val),
            _ => {
                return Err(PyValueError::new_err(
                    "preferences must be an object or null",
                ));
            }
        };
        let split = apply_auto_split(&blocks, &trace, sources, preferences, || fresh_id(py))
            .map_err(PyValueError::new_err)?;
        Ok(split.to_json().to_string())
    })
}

/// Where the first homework a plan gave a time is, by day and then minute.
#[pyfunction]
fn session_plan_first_placed(trace: &str, targets: Vec<String>) -> PyResult<Option<(i64, i64)>> {
    guard(|| {
        let trace = parse_json(trace, "trace")?;
        if !trace.is_object() {
            return Err(PyValueError::new_err("trace must be an object"));
        }
        first_placed(&trace, &targets).map_err(PyValueError::new_err)
    })
}

/// Homework with minutes the plan could not give a time, named with its minutes.
#[pyfunction]
#[pyo3(signature = (left=None))]
fn session_plan_left_sentence(left: Option<Vec<(String, i64)>>) -> PyResult<String> {
    guard(|| Ok(left_sentence(&left.unwrap_or_default())))
}

/// How much homework a plan placed, plus waiting count and unplaced-minute remainder names.
#[pyfunction]
#[pyo3(signature = (placed, waiting, left=None))]
fn session_plan_sentence(
    placed: i64,
    waiting: i64,
    left: Option<Vec<(String, i64)>>,
) -> PyResult<String> {
    guard(|| Ok(plan_sentence(placed, waiting, &left.unwrap_or_default())))
}

/// Where Place now put one block, or that it found no room this week.
#[pyfunction]
fn session_place_now_sentence(block: &str, week_start: &str) -> PyResult<String> {
    guard(|| {
        let block = parse_json(block, "block")?;
        if !block.is_object() {
            return Err(PyValueError::new_err("block must be an object"));
        }
        place_now_sentence(&block, week_start).map_err(PyValueError::new_err)
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("PLAN_WEEK_OVER", WEEK_OVER)?;
    crate::export!(
        module,
        session_prepare_plan,
        session_apply_plan_answer,
        session_apply_auto_split,
        session_plan_first_placed,
        session_plan_left_sentence,
        session_plan_sentence,
        session_place_now_sentence,
    );
    Ok(())
}
