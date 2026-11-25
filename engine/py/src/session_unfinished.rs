//! Unfinished homework lists, planner counts and "Plan into this week" preparation
//! (`flexweek_app::session::unfinished`, P4 group 5, slice 5C) for the Python window.

use flexweek_app::session::unfinished::{
    ClockNow, HomeworkCountsInput, UnfinishedInput, UnfinishedPlanInput, UnfinishedPreviewInput,
    homework_counts, left_unfinished_items, plan_unfinished, unfinished_items, unfinished_preview,
};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::{Map, Value};

use crate::guard;

fn parse_root(text: &str) -> PyResult<Map<String, Value>> {
    let value: Value =
        serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))?;
    match value {
        Value::Object(map) => Ok(map),
        _ => Err(PyTypeError::new_err("arguments must be one JSON object")),
    }
}

fn req_str<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a str> {
    match map.get(key) {
        Some(Value::String(text)) => Ok(text.as_str()),
        Some(_) => Err(PyTypeError::new_err(format!("{key} must be a string"))),
        None => Err(PyValueError::new_err(format!("missing {key}"))),
    }
}

fn req_i64(map: &Map<String, Value>, key: &str) -> PyResult<i64> {
    match map.get(key) {
        Some(value) => value
            .as_i64()
            .ok_or_else(|| PyTypeError::new_err(format!("{key} must be an integer"))),
        None => Err(PyValueError::new_err(format!("missing {key}"))),
    }
}

fn opt_i64(map: &Map<String, Value>, key: &str, default: i64) -> PyResult<i64> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(default),
        Some(value) => value
            .as_i64()
            .ok_or_else(|| PyTypeError::new_err(format!("{key} must be an integer"))),
    }
}

fn opt_bool(map: &Map<String, Value>, key: &str, default: bool) -> PyResult<bool> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(default),
        Some(Value::Bool(flag)) => Ok(*flag),
        Some(_) => Err(PyTypeError::new_err(format!("{key} must be a boolean"))),
    }
}

fn req_weekday(map: &Map<String, Value>, key: &str) -> PyResult<u32> {
    let raw = req_i64(map, key)?;
    if !(0..=6).contains(&raw) {
        return Err(PyValueError::new_err(format!("{key} must be 0..=6")));
    }
    Ok(raw as u32)
}

fn req_array<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a [Value]> {
    match map.get(key) {
        Some(Value::Array(items)) => Ok(items.as_slice()),
        Some(_) => Err(PyTypeError::new_err(format!("{key} must be a list"))),
        None => Err(PyValueError::new_err(format!("missing {key}"))),
    }
}

fn req_object_list<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a [Value]> {
    let items = req_array(map, key)?;
    if items.iter().any(|item| !item.is_object()) {
        return Err(PyTypeError::new_err(format!(
            "each entry in {key} must be a JSON object"
        )));
    }
    Ok(items)
}

fn req_string_list(map: &Map<String, Value>, key: &str) -> PyResult<Vec<String>> {
    let items = req_array(map, key)?;
    let mut out = Vec::with_capacity(items.len());
    for item in items {
        let Some(text) = item.as_str() else {
            return Err(PyTypeError::new_err(format!(
                "each entry in {key} must be a string"
            )));
        };
        out.push(text.to_string());
    }
    Ok(out)
}

fn req_assignments<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a Map<String, Value>> {
    match map.get(key) {
        Some(Value::Object(table)) => {
            if table.values().any(|value| !value.is_object()) {
                return Err(PyTypeError::new_err(format!(
                    "each value in {key} must be a JSON object"
                )));
            }
            Ok(table)
        }
        Some(_) => Err(PyTypeError::new_err(format!("{key} must be a JSON object"))),
        None => Err(PyValueError::new_err(format!("missing {key}"))),
    }
}

fn req_clock<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<ClockNow<'a>> {
    let Some(value) = map.get(key) else {
        return Err(PyValueError::new_err(format!("missing {key}")));
    };
    let Value::Object(clock) = value else {
        return Err(PyTypeError::new_err(format!("{key} must be a JSON object")));
    };
    Ok(ClockNow {
        today: req_str(clock, "today")?,
        hour: req_i64(clock, "hour")?,
        minute: req_i64(clock, "minute")?,
        second: opt_i64(clock, "second", 0)?,
        microsecond: opt_i64(clock, "microsecond", 0)?,
    })
}

/// Unified homework counts for the open week, as JSON text.
#[pyfunction]
fn session_homework_counts(args: &str) -> PyResult<String> {
    guard(|| {
        let map = parse_root(args)?;
        let input = HomeworkCountsInput {
            week_start: req_str(&map, "week_start")?,
            first_weekday: req_weekday(&map, "first_weekday")?,
            blocks: req_object_list(&map, "blocks")?,
            assignments: req_assignments(&map, "assignments")?,
            assignments_basis: req_object_list(&map, "assignments_basis")?,
            now: req_clock(&map, "now")?,
        };
        let counts = homework_counts(input).map_err(PyValueError::new_err)?;
        Ok(counts.to_json().to_string())
    })
}

/// Unfinished homework items for the shown week (or only `left_from_last_week` when requested).
#[pyfunction]
fn session_unfinished_items(args: &str) -> PyResult<String> {
    guard(|| {
        let map = parse_root(args)?;
        let saved_weeks = req_string_list(&map, "saved_weeks")?;
        let only_left = opt_bool(&map, "only_left_from_last_week", false)?;
        let input = UnfinishedInput {
            week_start: req_str(&map, "week_start")?,
            first_weekday: req_weekday(&map, "first_weekday")?,
            blocks: req_object_list(&map, "blocks")?,
            assignments: req_assignments(&map, "assignments")?,
            assignments_basis: req_object_list(&map, "assignments_basis")?,
            saved_weeks: &saved_weeks,
            stored_parts: req_object_list(&map, "stored_parts")?,
            now: req_clock(&map, "now")?,
        };
        let items = if only_left {
            left_unfinished_items(input)
        } else {
            unfinished_items(input)
        }
        .map_err(PyValueError::new_err)?;
        Ok(Value::Array(items).to_string())
    })
}

/// Single-homework preview row for `plan_unfinished`, or `{"say": ...}`.
#[pyfunction]
fn session_unfinished_preview(args: &str) -> PyResult<String> {
    guard(|| {
        let map = parse_root(args)?;
        let block_id = req_str(&map, "block_id")?;
        let input = UnfinishedPreviewInput {
            week_start: req_str(&map, "week_start")?,
            blocks: req_object_list(&map, "blocks")?,
            assignments: req_assignments(&map, "assignments")?,
            assignments_basis: req_object_list(&map, "assignments_basis")?,
            assignment_id: req_str(&map, "assignment_id")?,
            now: req_clock(&map, "now")?,
            plannable_today: req_str(&map, "plannable_today")?,
        };
        let preview = unfinished_preview(input, block_id).map_err(PyValueError::new_err)?;
        Ok(preview.to_json().to_string())
    })
}

/// Provisional blocks and ordinary/overdue solve targets for `plan_left`, or `{"say": ...}`.
#[pyfunction]
fn session_plan_unfinished(args: &str) -> PyResult<String> {
    guard(|| {
        let map = parse_root(args)?;
        let assignment_ids = req_string_list(&map, "assignment_ids")?;
        let new_ids = req_string_list(&map, "new_ids")?;
        let input = UnfinishedPlanInput {
            week_start: req_str(&map, "week_start")?,
            blocks: req_object_list(&map, "blocks")?,
            assignments: req_assignments(&map, "assignments")?,
            assignments_basis: req_object_list(&map, "assignments_basis")?,
            assignment_ids: &assignment_ids,
            now: req_clock(&map, "now")?,
        };
        let mut id_iter = new_ids.into_iter();
        let plan = plan_unfinished(input, &mut id_iter).map_err(PyValueError::new_err)?;
        Ok(plan.to_json().to_string())
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        session_homework_counts,
        session_unfinished_items,
        session_unfinished_preview,
        session_plan_unfinished
    );
    Ok(())
}
