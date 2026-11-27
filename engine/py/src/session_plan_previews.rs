//! Running late, missed-commitment recovery, Allow splitting and Spread preview decisions
//! (`flexweek_app::session::plan_previews`, 2.0.0 plan P4 group 5B) for the Python window.
//! JSON text crosses, as with `session_transfer`.

use flexweek_app::session::plan_previews::{
    AllowSplittingInput, LateAcceptInput, LateAnswerInput, LateInput, RecoverAnswerInput,
    RecoverInput, SpreadAnswerInput, SpreadSelectionInput, accept_late, confirm_spread_skipped,
    late_answer, late_blocks, late_payload_from_base, late_summary, prepare_allow_splitting,
    prepare_late, recover_answer, recover_payload_from_base, recover_request, spread_answer,
    spread_key, spread_ready_sentence, spread_selection,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::Value;

use crate::guard;

fn parse(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn parse_object(text: &str, what: &str) -> PyResult<Value> {
    let value = parse(text, what)?;
    if !value.is_object() {
        return Err(PyValueError::new_err(format!(
            "{what} must be a JSON object"
        )));
    }
    Ok(value)
}

fn parse_optional_object(text: Option<&str>, what: &str) -> PyResult<Option<Value>> {
    match text {
        None => Ok(None),
        Some(raw) => match parse(raw, what)? {
            Value::Null => Ok(None),
            value if value.is_object() => Ok(Some(value)),
            _ => Err(PyValueError::new_err(format!(
                "{what} must be a JSON object"
            ))),
        },
    }
}

fn parse_blocks(text: &str, what: &str) -> PyResult<Vec<Value>> {
    let Value::Array(items) = parse(text, what)? else {
        return Err(PyValueError::new_err(format!("{what} must be a JSON list")));
    };
    if items.iter().any(|item| !item.is_object()) {
        return Err(PyValueError::new_err(format!(
            "each item in {what} must be a JSON object"
        )));
    }
    Ok(items)
}

fn value_err(message: String) -> PyErr {
    PyValueError::new_err(message)
}

#[pyfunction]
fn session_spread_ready_sentence(
    title: &str,
    minutes: i64,
    due: &str,
    today: &str,
) -> PyResult<String> {
    guard(|| spread_ready_sentence(title, minutes, due, today).map_err(value_err))
}

#[pyfunction]
fn session_late_summary(moved: i64) -> PyResult<String> {
    guard(|| {
        let count = usize::try_from(moved)
            .map_err(|_| PyValueError::new_err("moved must be zero or positive"))?;
        Ok(late_summary(count))
    })
}

#[pyfunction]
fn session_late_blocks(blocks: &str) -> PyResult<String> {
    guard(|| {
        let blocks = parse_blocks(blocks, "blocks")?;
        Ok(Value::Array(late_blocks(&blocks)).to_string())
    })
}

#[pyfunction]
fn session_spread_operation_key(
    account_id: i64,
    assignment_id: &str,
    from_date: &str,
    session_min: i64,
) -> PyResult<String> {
    guard(|| {
        Ok(spread_key(
            account_id,
            assignment_id,
            from_date,
            session_min,
        ))
    })
}

#[pyfunction]
#[pyo3(signature = (assignment, done_min, week_start, today_iso, selected_day=None))]
fn session_prepare_allow_splitting(
    assignment: Option<&str>,
    done_min: i64,
    week_start: &str,
    today_iso: &str,
    selected_day: Option<&str>,
) -> PyResult<String> {
    guard(|| {
        let assignment = parse_optional_object(assignment, "assignment")?;
        let plan = prepare_allow_splitting(AllowSplittingInput {
            assignment: assignment.as_ref(),
            done_min,
            week_start,
            today_iso,
            selected_day,
        })
        .map_err(value_err)?;
        Ok(match plan {
            Some(found) => found.to_json().to_string(),
            None => Value::Null.to_string(),
        })
    })
}

#[pyfunction]
#[pyo3(signature = (week_start, blocks, trace, block_id, day))]
fn session_recover_request(
    week_start: &str,
    blocks: &str,
    trace: Option<&str>,
    block_id: &str,
    day: i64,
) -> PyResult<String> {
    guard(|| {
        let blocks = parse_blocks(blocks, "blocks")?;
        let trace = parse_optional_object(trace, "trace")?;
        let prep = recover_request(RecoverInput {
            week_start,
            blocks: &blocks,
            trace: trace.as_ref(),
            block_id,
            day,
        })
        .map_err(value_err)?;
        Ok(prep.to_json().to_string())
    })
}

#[pyfunction]
fn session_recover_payload_from_base(
    week_start: &str,
    blocks: &str,
    block_id: &str,
    day: i64,
    base_trace: &str,
) -> PyResult<String> {
    guard(|| {
        let blocks = parse_blocks(blocks, "blocks")?;
        let base_trace = parse_object(base_trace, "base_trace")?;
        let payload = recover_payload_from_base(week_start, &blocks, block_id, day, &base_trace)
            .map_err(value_err)?;
        Ok(payload.to_string())
    })
}

#[pyfunction]
fn session_recover_answer(
    week_start: &str,
    blocks: &str,
    assignments: &str,
    block_id: &str,
    day: i64,
    trace: &str,
) -> PyResult<String> {
    guard(|| {
        let blocks = parse_blocks(blocks, "blocks")?;
        let assignments = parse_object(assignments, "assignments")?;
        let trace = parse_object(trace, "trace")?;
        let applied = recover_answer(RecoverAnswerInput {
            week_start,
            blocks: &blocks,
            assignments: &assignments,
            block_id,
            day,
            trace: &trace,
        })
        .map_err(value_err)?;
        Ok(match applied {
            Some(found) => found.to_json().to_string(),
            None => Value::Null.to_string(),
        })
    })
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (week_start, today_iso, now_hour, now_minute, minutes, dirty, conflict, blocks, trace=None))]
fn session_prepare_late(
    week_start: &str,
    today_iso: &str,
    now_hour: i64,
    now_minute: i64,
    minutes: i64,
    dirty: bool,
    conflict: bool,
    blocks: &str,
    trace: Option<&str>,
) -> PyResult<String> {
    guard(|| {
        let blocks = parse_blocks(blocks, "blocks")?;
        let trace = parse_optional_object(trace, "trace")?;
        let prep = prepare_late(LateInput {
            week_start,
            today_iso,
            now_hour,
            now_minute,
            minutes,
            dirty,
            conflict,
            blocks: &blocks,
            trace: trace.as_ref(),
        })
        .map_err(value_err)?;
        Ok(prep.to_json().to_string())
    })
}

#[pyfunction]
fn session_late_payload_from_base(
    week_start: &str,
    blocks: &str,
    day: i64,
    from_start: &str,
    minutes: i64,
    base_trace: &str,
) -> PyResult<String> {
    guard(|| {
        let blocks = parse_blocks(blocks, "blocks")?;
        let base_trace = parse_object(base_trace, "base_trace")?;
        let payload =
            late_payload_from_base(week_start, &blocks, day, from_start, minutes, &base_trace)
                .map_err(value_err)?;
        Ok(payload.to_string())
    })
}

#[pyfunction]
fn session_late_answer(
    week_start: &str,
    day: i64,
    from_start: &str,
    minutes: i64,
    operation_id: &str,
    trace: &str,
) -> PyResult<String> {
    guard(|| {
        let trace = parse_object(trace, "trace")?;
        let answered = late_answer(LateAnswerInput {
            week_start,
            day,
            from_start,
            minutes,
            operation_id,
            trace: &trace,
        })
        .map_err(value_err)?;
        Ok(answered.to_json().to_string())
    })
}

#[pyfunction]
#[pyo3(signature = (preview, week_start, blocks, assignments))]
fn session_accept_late(
    preview: Option<&str>,
    week_start: &str,
    blocks: &str,
    assignments: &str,
) -> PyResult<String> {
    guard(|| {
        let preview = parse_optional_object(preview, "preview")?;
        let blocks = parse_blocks(blocks, "blocks")?;
        let assignments = parse_object(assignments, "assignments")?;
        let decision = accept_late(LateAcceptInput {
            preview: preview.as_ref(),
            week_start,
            blocks: &blocks,
            assignments: &assignments,
        })
        .map_err(value_err)?;
        Ok(decision.to_json().to_string())
    })
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn session_spread_answer(
    assignment_id: &str,
    assignment: &str,
    data: &str,
    from_date: &str,
    session_min: i64,
    today_iso: &str,
    id_prefix: &str,
) -> PyResult<String> {
    guard(|| {
        let assignment = parse_object(assignment, "assignment")?;
        let data = parse_object(data, "data")?;
        let answered = spread_answer(SpreadAnswerInput {
            assignment_id,
            assignment: &assignment,
            data: &data,
            from_date,
            session_min,
            today_iso,
            id_prefix,
        })
        .map_err(value_err)?;
        Ok(answered.to_json().to_string())
    })
}

#[pyfunction]
#[pyo3(signature = (preview, assignments, week_start, first_weekday, operation_id, allow_split_pending=None))]
fn session_spread_selection(
    preview: &str,
    assignments: &str,
    week_start: &str,
    first_weekday: i64,
    operation_id: &str,
    allow_split_pending: Option<&str>,
) -> PyResult<String> {
    guard(|| {
        if !(0..=6).contains(&first_weekday) {
            return Err(PyValueError::new_err("first_weekday must be 0 to 6"));
        }
        let preview = parse_object(preview, "preview")?;
        let assignments = parse_object(assignments, "assignments")?;
        let selection = spread_selection(SpreadSelectionInput {
            preview: &preview,
            assignments: &assignments,
            week_start,
            first_weekday: first_weekday as u32,
            operation_id,
            allow_split_pending,
        })
        .map_err(value_err)?;
        Ok(selection.to_json().to_string())
    })
}

#[pyfunction]
fn session_confirm_spread_skipped(has_preview: bool, signed_in: bool) -> PyResult<bool> {
    guard(|| Ok(confirm_spread_skipped(has_preview, signed_in)))
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        session_spread_ready_sentence,
        session_late_summary,
        session_late_blocks,
        session_spread_operation_key,
        session_prepare_allow_splitting,
        session_recover_request,
        session_recover_payload_from_base,
        session_recover_answer,
        session_prepare_late,
        session_late_payload_from_base,
        session_late_answer,
        session_accept_late,
        session_spread_answer,
        session_spread_selection,
        session_confirm_spread_skipped,
    );
    Ok(())
}
