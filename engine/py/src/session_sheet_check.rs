//! Sheet validation (`block_sheet_problem`, `homework_sheet_problem`) and model helpers
//! (`ESTIMATE_MAX_MIN`, `valid_spotify_url`, `parse_due`, `due_is_timed`) for the desktop,
//! replacing `pydantic` and `backend.models` in the sheets and bridges.

use ::flexweek_engine::model;
use flexweek_app::session::sheet_check;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDate, PyModule};
use serde_json::Value;

use crate::{guard, raise};

fn parse_object(text: &str, what: &str) -> PyResult<Value> {
    let value: Value = serde_json::from_str(text)
        .map_err(|err| PyValueError::new_err(format!("{what}: {err}")))?;
    if !value.is_object() {
        return Err(PyValueError::new_err(format!(
            "{what} must be a JSON object"
        )));
    }
    Ok(value)
}

fn date_from_iso(py: Python<'_>, iso: &str) -> PyResult<Py<PyDate>> {
    let mut parts = iso.split('-');
    let year: i32 = parts.next().unwrap_or("0").parse().unwrap_or(0);
    let month: u8 = parts.next().unwrap_or("0").parse().unwrap_or(0);
    let day: u8 = parts.next().unwrap_or("0").parse().unwrap_or(0);
    Ok(PyDate::new(py, year, month, day)?.unbind())
}

/// Accept only open.spotify.com share links the desktop shell can safely open externally.
/// Returns `None` for `None` or `""`; raises `ValueError` for invalid links.
#[pyfunction]
fn valid_spotify_url(value: Option<&str>) -> PyResult<Option<String>> {
    guard(|| model::valid_spotify_url(value).map_err(raise))
}

/// The due day and minute work must end by. Date-only and 23:59 are the end of that day (1440).
#[pyfunction]
fn parse_due(py: Python<'_>, value: &str) -> PyResult<(Py<PyDate>, i64)> {
    guard(|| {
        let (day, minute) = model::parse_due(value).map_err(raise)?;
        Ok((date_from_iso(py, &day.to_string())?, minute))
    })
}

/// True when the due stamp names a clock other than the old end-of-day 23:59.
#[pyfunction]
fn due_is_timed(value: &str) -> PyResult<bool> {
    guard(|| Ok(model::due_is_timed(value)))
}

/// Validate one block JSON object as a single-block `WeekRequest`, returning `(field, message)` or
/// `None` when valid.
#[pyfunction]
fn block_sheet_problem(text: &str) -> PyResult<Option<(String, String)>> {
    guard(|| {
        let value = parse_object(text, "block")?;
        Ok(sheet_check::block_sheet_problem(&value))
    })
}

/// Filter to homework fields and validate as `Assignment`, returning `(field, message)` or `None`
/// when valid.
#[pyfunction]
fn homework_sheet_problem(text: &str) -> PyResult<Option<(String, String)>> {
    guard(|| {
        let value = parse_object(text, "homework")?;
        Ok(sheet_check::homework_sheet_problem(&value))
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("ESTIMATE_MAX_MIN", model::ESTIMATE_MAX_MIN)?;
    crate::export!(
        module,
        valid_spotify_url,
        parse_due,
        due_is_timed,
        block_sheet_problem,
        homework_sheet_problem,
    );
    Ok(())
}
