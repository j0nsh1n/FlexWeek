//! The session's restore point, export and import decisions (`flexweek_app::session::transfer`) for the
//! Python window, with JSON text across. The window keeps the requests and applies what is decided.

use flexweek_app::session::transfer::{
    ImportContext, create_restore_key, finish_apply_import_err, finish_apply_import_ok,
    finish_apply_restore_err, finish_apply_restore_ok, finish_create_restore,
    finish_preview_import, import_key, import_target_week as target_week, import_week_decision,
    prepare_apply_import, prepare_apply_restore, prepare_create_restore, prepare_export_account,
    prepare_preview_import, prepare_preview_restore, restore_apply_guard, restore_key,
    restore_points_after_create, restore_points_from_reply, transfer_blocked,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::Value;

use crate::{guard, raise};

fn read(text: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))
}

fn read_named(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn read_list(text: &str, what: &str) -> PyResult<Vec<Value>> {
    match read_named(text, what)? {
        Value::Array(items) => Ok(items),
        _ => Err(PyValueError::new_err(format!("{what} must be a list"))),
    }
}

fn read_optional(text: Option<&str>, what: &str) -> PyResult<Option<Value>> {
    text.map(|value| read_named(value, what)).transpose()
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

/// The week an import file is for: its own week string, or the week open now.
#[pyfunction]
fn import_target_week(parsed: &str, open_week: &str) -> PyResult<String> {
    guard(|| {
        let parsed = read(parsed)?;
        if !parsed.is_object() {
            return Err(PyValueError::new_err("the parsed file is a JSON object"));
        }
        Ok(target_week(&parsed, open_week).to_string())
    })
}

/// The listed restore points (JSON list) from a fetch reply.
#[pyfunction]
fn session_restore_points_from_reply(data: &str) -> PyResult<String> {
    guard(|| {
        let data = read_named(data, "restore points reply")?;
        let points = restore_points_from_reply(&data).map_err(raise)?;
        Ok(Value::Array(points).to_string())
    })
}

/// Whether a restore point can be made, and the POST when it can. The body has no attempt id yet.
#[pyfunction]
#[pyo3(signature = (signed_in, account_id, label))]
fn session_prepare_create_restore(
    signed_in: bool,
    account_id: Option<i64>,
    label: &str,
) -> PyResult<String> {
    guard(|| {
        Ok(prepare_create_restore(signed_in, account_id, label)
            .map_err(raise)?
            .to_json()
            .to_string())
    })
}

/// The list and the sentence after a restore point was made. `requested_label` is what was typed.
#[pyfunction]
fn session_finish_create_restore(
    current: &str,
    reply: &str,
    requested_label: &str,
) -> PyResult<String> {
    guard(|| {
        let current = read_list(current, "restore points")?;
        let reply = read_named(reply, "restore point reply")?;
        Ok(finish_create_restore(&current, &reply, requested_label)
            .map_err(raise)?
            .to_json()
            .to_string())
    })
}

/// The GET for one point's preview, or nothing when signed out.
#[pyfunction]
fn session_prepare_preview_restore(signed_in: bool, point_id: &str) -> PyResult<String> {
    guard(|| {
        Ok(prepare_preview_restore(signed_in, point_id)
            .to_json()
            .to_string())
    })
}

/// Whether this point may be put back, and the POST when it may. `preview` is JSON, or None.
#[pyfunction]
#[pyo3(signature = (signed_in, account_id, preview, point_id))]
fn session_prepare_apply_restore(
    signed_in: bool,
    account_id: Option<i64>,
    preview: Option<&str>,
    point_id: &str,
) -> PyResult<String> {
    guard(|| {
        let preview = read_optional(preview, "restore preview")?;
        Ok(
            prepare_apply_restore(signed_in, account_id, preview.as_ref(), point_id)
                .map_err(raise)?
                .to_json()
                .to_string(),
        )
    })
}

/// What a successful restore does to the window.
#[pyfunction]
fn session_finish_apply_restore_ok() -> PyResult<String> {
    guard(|| Ok(finish_apply_restore_ok().to_string()))
}

/// Whether a failed restore drops the preview. Only status 409 does.
#[pyfunction]
fn session_finish_apply_restore_err(status: i64) -> PyResult<String> {
    guard(|| Ok(finish_apply_restore_err(status).to_string()))
}

/// The export POST, or the sentence that waits for unsaved work.
#[pyfunction]
fn session_prepare_export_account(
    signed_in: bool,
    dirty: bool,
    dirty_assignment_count: usize,
    password: &str,
) -> PyResult<String> {
    guard(|| {
        Ok(
            prepare_export_account(signed_in, dirty, dirty_assignment_count, password)
                .to_json()
                .to_string(),
        )
    })
}

/// The import-preview POST, or the sentence that waits for unsaved work. `snapshot` is JSON.
#[pyfunction]
fn session_prepare_preview_import(
    signed_in: bool,
    dirty: bool,
    dirty_assignment_count: usize,
    snapshot: &str,
) -> PyResult<String> {
    guard(|| {
        let snapshot = read_named(snapshot, "import snapshot")?;
        Ok(
            prepare_preview_import(signed_in, dirty, dirty_assignment_count, &snapshot)
                .to_json()
                .to_string(),
        )
    })
}

/// The preview the window keeps. `snapshot` and `data` are JSON.
#[pyfunction]
fn session_finish_preview_import(snapshot: &str, data: &str) -> PyResult<String> {
    guard(|| {
        let snapshot = read_named(snapshot, "import snapshot")?;
        let data = read_named(data, "import preview")?;
        Ok(finish_preview_import(&snapshot, &data)
            .map_err(raise)?
            .to_string())
    })
}

/// Whether the shown import may be applied. `preview` is JSON, or None. The body has no attempt id yet.
#[pyfunction]
#[pyo3(signature = (account_id, preview, dirty, dirty_assignment_count))]
fn session_prepare_apply_import(
    account_id: Option<i64>,
    preview: Option<&str>,
    dirty: bool,
    dirty_assignment_count: usize,
) -> PyResult<String> {
    guard(|| {
        let preview = read_optional(preview, "import preview")?;
        Ok(
            prepare_apply_import(account_id, preview.as_ref(), dirty, dirty_assignment_count)
                .map_err(raise)?
                .to_json()
                .to_string(),
        )
    })
}

/// What a successful import does to the window.
#[pyfunction]
fn session_finish_apply_import_ok() -> PyResult<String> {
    guard(|| Ok(finish_apply_import_ok().to_string()))
}

/// Whether a failed import drops the preview. Only status 409 does.
#[pyfunction]
fn session_finish_apply_import_err(status: i64) -> PyResult<String> {
    guard(|| Ok(finish_apply_import_err(status).to_string()))
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
        import_target_week,
        import_week_decision_json,
        session_restore_points_from_reply,
        session_prepare_create_restore,
        session_finish_create_restore,
        session_prepare_preview_restore,
        session_prepare_apply_restore,
        session_finish_apply_restore_ok,
        session_finish_apply_restore_err,
        session_prepare_export_account,
        session_prepare_preview_import,
        session_finish_preview_import,
        session_prepare_apply_import,
        session_finish_apply_import_ok,
        session_finish_apply_import_err
    );
    Ok(())
}
