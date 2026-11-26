//! The session's homework edit decisions (`flexweek_app::session::homework_edits`) for the Python window,
//! with JSON text across. The window keeps the state and settles the week after it applies the answer.

use flexweek_app::session::homework_edits::{
    HomeworkEditInput, completed_homework, edit_homework, unpin_homework,
};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::{Map, Value};

use crate::guard;

fn read(text: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))
}

fn objects(value: Value, what: &str) -> PyResult<Vec<Value>> {
    let Value::Array(items) = value else {
        return Err(PyTypeError::new_err(format!("{what} are a list")));
    };
    if items.iter().any(|item| !item.is_object()) {
        return Err(PyTypeError::new_err(format!(
            "every one of the {what} is an object"
        )));
    }
    Ok(items)
}

fn days(value: Value) -> PyResult<Option<Vec<i64>>> {
    match value {
        Value::Null => Ok(None),
        Value::Array(items) => items
            .iter()
            .map(|item| {
                item.as_i64()
                    .ok_or_else(|| PyTypeError::new_err("every day is a whole number"))
            })
            .collect::<PyResult<Vec<_>>>()
            .map(Some),
        _ => Err(PyTypeError::new_err("the days are a list or null")),
    }
}

/// The edit of a homework (JSON object) saved from the dialog, as JSON:
/// `{"assignment", "blocks", "changed", "pinned", "label"}`. `basis` is the block list the server's
/// counts were read with, or null; `days` is a list of day numbers or null.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (blocks, assignments, basis, assignment, week_start, days_json, spread, new_session_id))]
fn homework_edit_json(
    blocks: &str,
    assignments: &str,
    basis: &str,
    assignment: &str,
    week_start: &str,
    days_json: &str,
    spread: bool,
    new_session_id: &str,
) -> PyResult<String> {
    guard(|| {
        let blocks = objects(read(blocks)?, "blocks")?;
        let Value::Object(known) = read(assignments)? else {
            return Err(PyTypeError::new_err("the assignments are an object"));
        };
        if known.values().any(|item| !item.is_object()) {
            return Err(PyTypeError::new_err("every assignment is an object"));
        }
        let basis = match read(basis)? {
            Value::Null => None,
            other => Some(objects(other, "basis blocks")?),
        };
        let assignment = read(assignment)?;
        if !assignment.is_object() {
            return Err(PyTypeError::new_err("the homework is an object"));
        }
        let days = days(read(days_json)?)?;
        let known: Map<String, Value> = known;
        let input = HomeworkEditInput {
            blocks: &blocks,
            assignments: &known,
            basis: basis.as_deref(),
            assignment: &assignment,
            week_start,
            days: days.as_deref(),
            spread,
            new_session_id,
        };
        let edit = edit_homework(&input).map_err(PyValueError::new_err)?;
        Ok(edit.to_json().to_string())
    })
}

/// The blocks (JSON list) with the homework's pins taken off, as JSON, or None when none was pinned.
#[pyfunction]
fn homework_unpin_json(blocks: &str, assignment_id: &str) -> PyResult<Option<String>> {
    guard(|| {
        let blocks = objects(read(blocks)?, "blocks")?;
        Ok(unpin_homework(&blocks, assignment_id).map(|after| Value::Array(after).to_string()))
    })
}

/// The homework (JSON object) as it is saved when finished or reopened, as JSON.
#[pyfunction]
fn homework_completed_json(known: &str, completed: bool, stamp: &str) -> PyResult<String> {
    guard(|| {
        let known = read(known)?;
        if !known.is_object() {
            return Err(PyTypeError::new_err("the homework is an object"));
        }
        completed_homework(&known, completed, stamp)
            .map(|body| body.to_string())
            .map_err(PyValueError::new_err)
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        homework_edit_json,
        homework_unpin_json,
        homework_completed_json
    );
    Ok(())
}
