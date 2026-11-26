//! The session's restore point, export and import decisions (`flexweek_app::session::transfer`) for the
//! Python window, with JSON text across. The window keeps the requests and applies what is decided.

use flexweek_app::session::transfer::{
    ImportContext, create_restore_key, import_key, import_week_decision, restore_apply_guard,
    restore_key, restore_points_after_create, transfer_blocked,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::Value;

use crate::{guard, raise};

fn read(text: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))
}

/// The restore point list (JSON list) after `point` (JSON) was made, as JSON.
#[pyfunction]
fn restore_points_after_create_json(current: &str, point: &str) -> PyResult<String> {
    guard(|| {
        let Value::Array(current) = read(current)? else {
            return Err(PyValueError::new_err("the restore points are a list"));
        };
        let after = restore_points_after_create(&current, &read(point)?);
        Ok(Value::Array(after).to_string())
    })
}

/// The words that refuse a restore, or None; `preview` is the shown preview as JSON, or None.
#[pyfunction]
#[pyo3(signature = (signed_in, preview, point_id))]
fn restore_guard_words(
    signed_in: bool,
    preview: Option<&str>,
    point_id: &str,
) -> PyResult<Option<&'static str>> {
    guard(|| {
        let preview = preview.map(read).transpose()?;
        Ok(restore_apply_guard(signed_in, preview.as_ref(), point_id))
    })
}

/// The words that stop an export or import while changes are unsaved, or None.
#[pyfunction]
fn transfer_blocked_words(
    dirty: bool,
    dirty_assignment_count: usize,
    verb: &str,
) -> PyResult<Option<String>> {
    guard(|| Ok(transfer_blocked(dirty, dirty_assignment_count, verb)))
}

#[pyfunction]
fn create_restore_operation_key(account_id: i64, label: &str) -> PyResult<String> {
    guard(|| Ok(create_restore_key(account_id, label)))
}

#[pyfunction]
fn restore_operation_key(account_id: i64, point_id: &str) -> PyResult<String> {
    guard(|| Ok(restore_key(account_id, point_id)))
}

/// `state_token` is the preview's token as JSON text.
#[pyfunction]
fn import_operation_key(account_id: i64, state_token: &str) -> PyResult<String> {
    guard(|| Ok(import_key(account_id, &read(state_token)?)))
}

/// What to do with a parsed week or day file (JSON): `{"say": words}` or `{"blocks": [...], "create": [...]}`.
/// `replace` is None when the caller did not choose.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (parsed, week_start, week_words, target_words, blocks, assignments, replace))]
fn import_week_decision_json(
    parsed: &str,
    week_start: &str,
    week_words: &str,
    target_words: &str,
    blocks: &str,
    assignments: &str,
    replace: Option<bool>,
) -> PyResult<String> {
    guard(|| {
        let (parsed, blocks, assignments) = (read(parsed)?, read(blocks)?, read(assignments)?);
        if !parsed.is_object() {
            return Err(PyValueError::new_err("the parsed file is a JSON object"));
        }
        let context = ImportContext {
            week_start,
            week_words,
            target_words,
            blocks: &blocks,
            assignments: &assignments,
            replace,
        };
        let decision = import_week_decision(&parsed, &context).map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        restore_points_after_create_json,
        restore_guard_words,
        transfer_blocked_words,
        create_restore_operation_key,
        restore_operation_key,
        import_operation_key,
        import_week_decision_json
    );
    Ok(())
}
