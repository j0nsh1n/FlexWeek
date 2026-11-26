//! Save, delete and apply routine decisions (`flexweek_app::session::routines`) for the Python
//! window, with JSON text across. Wrong-shaped JSON is refused before the decision runs. The window
//! still draws operation ids, sends the requests and applies what is decided.

use flexweek_app::session::routines::{
    apply_routine_rows_decision, delete_routine_path, prepare_apply_routine,
    prepare_delete_routine, prepare_save_routine, routines_from_reply, save_routine_reply,
    save_routine_request,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::{Map, Value};

use crate::desk::fresh_id;
use crate::{guard, raise};

fn read(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn as_object<'a>(value: &'a Value, what: &str) -> PyResult<&'a Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| PyValueError::new_err(format!("{what} must be a JSON object")))
}

fn req<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a Value> {
    map.get(key)
        .ok_or_else(|| PyValueError::new_err(format!("missing field {key:?}")))
}

fn req_str<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a str> {
    req(map, key)?
        .as_str()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be a string")))
}

fn req_i64_or_null(map: &Map<String, Value>, key: &str) -> PyResult<Option<i64>> {
    match req(map, key)? {
        Value::Null => Ok(None),
        value => value
            .as_i64()
            .map(Some)
            .ok_or_else(|| PyValueError::new_err(format!("{key} must be an integer or null"))),
    }
}

fn req_array<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a Vec<Value>> {
    req(map, key)?
        .as_array()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be a list")))
}

fn req_array_or_null<'a>(
    map: &'a Map<String, Value>,
    key: &str,
) -> PyResult<Option<&'a Vec<Value>>> {
    match req(map, key)? {
        Value::Null => Ok(None),
        Value::Array(items) => Ok(Some(items)),
        _ => Err(PyValueError::new_err(format!(
            "{key} must be a list or null"
        ))),
    }
}

fn req_object_value<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a Value> {
    let value = req(map, key)?;
    if !value.is_object() {
        return Err(PyValueError::new_err(format!("{key} must be an object")));
    }
    Ok(value)
}

/// Whether a routine can be saved. One fresh id is drawn per block on the week; a filtered-out
/// block leaves its id unused, and the ids that remain stay in week order.
#[pyfunction]
fn session_prepare_save_routine(py: Python<'_>, payload: &str) -> PyResult<String> {
    guard(|| {
        let root = read(payload, "save routine")?;
        let map = as_object(&root, "save routine")?;
        let blocks = req_array(map, "blocks")?;
        let block_ids = req_array_or_null(map, "block_ids")?.map(Vec::as_slice);
        let template_uuids: Vec<String> = blocks.iter().map(|_| fresh_id(py)).collect();
        let decision = prepare_save_routine(
            req_i64_or_null(map, "account_id")?,
            req_str(map, "week_start")?,
            blocks,
            req_str(map, "name")?,
            block_ids,
            &template_uuids,
        )
        .map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

/// The PUT once `operation_id` exists. `templates` is the decision's template list as JSON.
#[pyfunction]
fn session_save_routine_request(
    operation_id: &str,
    title: &str,
    templates: &str,
) -> PyResult<String> {
    guard(|| {
        let templates = read(templates, "routine templates")?;
        let templates = templates
            .as_array()
            .ok_or_else(|| PyValueError::new_err("routine templates must be a list"))?;
        Ok(save_routine_request(operation_id, title, templates)
            .to_json()
            .to_string())
    })
}

/// What a successful save stores, and the words that say it landed. `data` is the reply JSON.
#[pyfunction]
fn session_save_routine_reply(data: &str) -> PyResult<String> {
    guard(|| {
        let data = read(data, "save reply")?;
        if !data.is_object() {
            return Err(PyValueError::new_err("save reply must be a JSON object"));
        }
        Ok(save_routine_reply(&data)
            .map_err(raise)?
            .to_json()
            .to_string())
    })
}

/// The delete key and "Deleted <name>.", or that there is nothing to delete.
#[pyfunction]
fn session_prepare_delete_routine(payload: &str) -> PyResult<String> {
    guard(|| {
        let root = read(payload, "delete routine")?;
        let map = as_object(&root, "delete routine")?;
        let decision = prepare_delete_routine(
            req_i64_or_null(map, "account_id")?,
            req_object_value(map, "routines")?,
            req_str(map, "routine_id")?,
        )
        .map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

/// The DELETE path. `revision` is JSON, read with `int` only once the operation id exists.
#[pyfunction]
fn session_delete_routine_path(
    routine_id: &str,
    revision: &str,
    operation_id: &str,
) -> PyResult<String> {
    guard(|| {
        let revision = read(revision, "revision")?;
        delete_routine_path(routine_id, &revision, operation_id).map_err(raise)
    })
}

/// The rows a routine would add, or the weekday sentence.
#[pyfunction]
fn session_apply_routine_rows(payload: &str) -> PyResult<String> {
    guard(|| {
        let root = read(payload, "routine rows")?;
        let map = as_object(&root, "routine rows")?;
        let decision = apply_routine_rows_decision(
            req_object_value(map, "routines")?,
            req_str(map, "routine_id")?,
            req_str(map, "week_start")?,
            req_array(map, "days")?,
        )
        .map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

/// Whether applying can go ahead. `rows` null means the caller did not pass any, so the rows
/// decision runs first.
#[pyfunction]
fn session_prepare_apply_routine(payload: &str) -> PyResult<String> {
    guard(|| {
        let root = read(payload, "apply routine")?;
        let map = as_object(&root, "apply routine")?;
        let rows = req_array_or_null(map, "rows")?.map(Vec::as_slice);
        let decision = prepare_apply_routine(
            req_i64_or_null(map, "account_id")?,
            req_object_value(map, "routines")?,
            req_str(map, "routine_id")?,
            req_str(map, "week_start")?,
            req_array(map, "days")?,
            rows,
        )
        .map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

/// The server's routine list as a JSON object keyed by id.
#[pyfunction]
fn session_routines_from_reply(data: &str) -> PyResult<String> {
    guard(|| {
        let data = read(data, "routines reply")?;
        if !data.is_object() {
            return Err(PyValueError::new_err(
                "routines reply must be a JSON object",
            ));
        }
        let routines = routines_from_reply(&data).map_err(raise)?;
        Ok(Value::Object(routines).to_string())
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        session_prepare_save_routine,
        session_save_routine_request,
        session_save_routine_reply,
        session_prepare_delete_routine,
        session_delete_routine_path,
        session_apply_routine_rows,
        session_prepare_apply_routine,
        session_routines_from_reply,
    );
    Ok(())
}
