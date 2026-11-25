//! Changes request decisions for the Python window.

use flexweek_app::session::changes::{self, SaveDraft, SaveFailureKind};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyModule, PySet};
use serde_json::{Map, Value};

use crate::{guard, raise};

fn read(text: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))
}

fn object<'a>(value: &'a Value, name: &str) -> PyResult<&'a Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| PyValueError::new_err(format!("{name} must be an object")))
}

fn rows<'a>(value: &'a Value, name: &str) -> PyResult<&'a [Value]> {
    value
        .as_array()
        .filter(|rows| rows.iter().all(Value::is_object))
        .map(Vec::as_slice)
        .ok_or_else(|| PyValueError::new_err(format!("{name} must be a list of objects")))
}

fn optional_rows<'a>(value: &'a Value, name: &str) -> PyResult<&'a [Value]> {
    if value.is_null() {
        Ok(&[])
    } else {
        rows(value, name)
    }
}

fn fresh_id(uuid4: &Bound<'_, PyAny>) -> PyResult<String> {
    Ok(uuid4.call0()?.str()?.to_str()?.to_owned())
}

#[pyfunction]
fn save_assignment_write(id: &str, item: &str, revision: i64) -> PyResult<String> {
    guard(|| {
        let item = read(item)?;
        let item = (!item.is_null()).then_some(&item);
        Ok(changes::assignment_write(id, item, revision)
            .map_err(raise)?
            .to_string())
    })
}

#[pyfunction]
fn save_week_write(week_start: &str, blocks: &str, revision: &str) -> PyResult<String> {
    guard(|| {
        let (blocks, revision) = (read(blocks)?, read(revision)?);
        Ok(
            changes::week_write(week_start, rows(&blocks, "blocks")?, &revision)
                .map_err(raise)?
                .to_string(),
        )
    })
}

#[pyfunction]
#[pyo3(signature = (week_start, draft, dirty_assignments, traveling, operation_id, snapshot_label, uuid4))]
fn freeze_save(
    week_start: &str,
    draft: &str,
    dirty_assignments: Vec<String>,
    traveling: Option<&str>,
    operation_id: Option<&str>,
    snapshot_label: Option<&str>,
    uuid4: &Bound<'_, PyAny>,
) -> PyResult<String> {
    guard(|| {
        let draft = read(draft)?;
        object(&draft, "draft")?;
        let step = &draft["travel_step"];
        if !step.is_null() {
            object(step, "travel step")?;
        }
        let input = SaveDraft {
            week_start,
            blocks: rows(&draft["blocks"], "blocks")?,
            revision: &draft["revision"],
            committed_blocks: rows(&draft["committed_blocks"], "committed blocks")?,
            assignments: object(&draft["assignments"], "assignments")?,
            committed_assignments: object(
                &draft["committed_assignments"],
                "committed assignments",
            )?,
            dirty_assignments: &dirty_assignments,
            travel_weeks: optional_rows(&step["weeks"], "travel weeks")?,
            undo: traveling == Some("undo"),
            stored_parts: rows(&draft["stored_parts"], "stored parts")?,
            saved_repeats: rows(&draft["saved_repeats"], "saved repeats")?,
            repeats: rows(&draft["repeats"], "repeats")?,
            queued_repeats: optional_rows(&draft["queued_repeats"], "queued repeats")?,
        };
        let id = operation_id.unwrap_or_default();
        let mut request = changes::freeze_save(&input, id, snapshot_label).map_err(raise)?;
        if id.is_empty() {
            request["operation_id"] = Value::from(fresh_id(uuid4)?);
        }
        Ok(request.to_string())
    })
}

#[pyfunction]
fn renew_save_retry(
    previous: &str,
    rebuilt: &str,
    uuid4: &Bound<'_, PyAny>,
) -> PyResult<Option<String>> {
    guard(|| {
        let (previous, mut rebuilt) = (read(previous)?, read(rebuilt)?);
        object(&previous, "previous request")?;
        object(&rebuilt, "rebuilt request")?;
        if !changes::retry_needs_new_id(&previous, &rebuilt) {
            return Ok(None);
        }
        rebuilt["operation_id"] = Value::from(fresh_id(uuid4)?);
        Ok(Some(rebuilt.to_string()))
    })
}

#[pyfunction]
fn prepare_save_post<'py>(
    py: Python<'py>,
    request: &str,
    week_start: &str,
    shifted_week: bool,
) -> PyResult<(String, Option<String>, Bound<'py, PySet>)> {
    guard(|| {
        let request = read(request)?;
        let weeks = optional_rows(&request["weeks"], "weeks")?;
        let dates = weeks
            .iter()
            .map(|week| {
                week["week_start"]
                    .as_str()
                    .ok_or_else(|| PyValueError::new_err("week_start must be text"))
            })
            .collect::<PyResult<Vec<_>>>()?;
        // Keep the destination chosen by this process's set iteration when several weeks qualify.
        let written = PySet::new(py, dates)?;
        let dates = (&written)
            .into_iter()
            .map(|date| date.extract::<String>())
            .collect::<PyResult<Vec<_>>>()?;
        let Value::Object(request) = request else {
            return Err(PyValueError::new_err("request must be an object"));
        };
        let (payload, destination) =
            changes::prepare_post(request, &dates, week_start, shifted_week).map_err(raise)?;
        Ok((payload.to_string(), destination, written))
    })
}

#[pyfunction]
fn save_failure(status: i64, message: &str) -> PyResult<(bool, String)> {
    guard(|| {
        let failure = changes::classify_failure(status, message);
        Ok((failure.kind == SaveFailureKind::Refused, failure.words))
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        save_assignment_write,
        save_week_write,
        freeze_save,
        renew_save_retry,
        prepare_save_post,
        save_failure
    );
    Ok(())
}
