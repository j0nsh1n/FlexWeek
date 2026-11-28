//! Sheet lifecycle, save and delete flows, alarms and the notice bar for the Python bridge. JSON
//! text crosses. Each exported function only calls `guard`.

use flexweek_app::views::sheets_core;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde_json::Value;

use crate::{guard, raise};

fn parse_json(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn dump(value: &Value) -> PyResult<String> {
    serde_json::to_string(value).map_err(|error| PyValueError::new_err(format!("json: {error}")))
}

#[pyfunction]
fn sheets_words() -> PyResult<String> {
    guard(|| dump(&sheets_core::words()))
}

#[pyfunction]
fn sheets_plan(op: &str, facts: &str) -> PyResult<String> {
    guard(|| {
        let facts = parse_json(facts, "facts")?;
        dump(&sheets_core::plan(op, &facts).map_err(raise)?)
    })
}

#[pyfunction]
fn sheets_doubled_words(name: &str, weeks: Vec<String>, today: &str) -> PyResult<String> {
    guard(|| sheets_core::doubled_words(name, &weeks, today).map_err(raise))
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(module, sheets_words, sheets_plan, sheets_doubled_words);
    Ok(())
}
