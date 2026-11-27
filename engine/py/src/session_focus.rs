//! The focus timer's decisions (`flexweek_app::session::focus`, 2.0.0 plan P4 group 6) for the Python
//! window: `desktop/native/focus.py` sends one JSON text of arguments and reads one JSON text back.

use ::flexweek_engine::EngineResult;
use flexweek_app::session::focus;
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::Value;

use crate::guard;

/// Parses the arguments (one JSON object) and answers with `decide`'s JSON text. Each caller wraps it in
/// `guard`, so a panic in the decision stays a Python error.
fn run(args: &str, decide: fn(&Value) -> EngineResult<Value>) -> PyResult<String> {
    let args: Value =
        serde_json::from_str(args).map_err(|error| PyValueError::new_err(error.to_string()))?;
    if !args.is_object() {
        return Err(PyTypeError::new_err(
            "the focus arguments are one JSON object",
        ));
    }
    decide(&args)
        .map(|answer| answer.to_string())
        .map_err(crate::raise)
}

#[pyfunction]
fn session_focus_start_target(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::start_target))
}

#[pyfunction]
fn session_focus_start_decision(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::start_decision))
}

#[pyfunction]
fn session_focus_elapsed_min(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::elapsed_min))
}

#[pyfunction]
fn session_focus_tick_step(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::tick_step))
}

#[pyfunction]
fn session_focus_advance_begin(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::advance_begin))
}

#[pyfunction]
fn session_focus_advance_plan(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::advance_plan))
}

#[pyfunction]
fn session_focus_enter_phase(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::enter_phase))
}

#[pyfunction]
fn session_focus_credit_plan(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::credit_plan))
}

#[pyfunction]
fn session_focus_auto_complete_plan(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::auto_complete_plan))
}

#[pyfunction]
fn session_focus_mutes_alerts(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::mutes_alerts))
}

#[pyfunction]
fn session_focus_hold_alerts(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::hold_alerts))
}

#[pyfunction]
fn session_focus_drop_missing(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::drop_missing))
}

#[pyfunction]
fn session_focus_rebase(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::rebase))
}

#[pyfunction]
fn session_focus_scheduled_blocks(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::scheduled_blocks))
}

#[pyfunction]
fn session_focus_restore_decision(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::restore_decision))
}

#[pyfunction]
fn session_focus_focus_spotify_decision(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::focus_spotify_decision))
}

#[pyfunction]
fn session_focus_focus_spotify_open_failed(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::focus_spotify_open_failed))
}

#[pyfunction]
fn session_focus_start_allowed(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::start_allowed))
}

#[pyfunction]
fn session_focus_toggle_pause_decision(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::toggle_pause_decision))
}

#[pyfunction]
fn session_focus_end_early_decision(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::end_early_decision))
}

#[pyfunction]
fn session_focus_credit_enqueue_decision(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::credit_enqueue_decision))
}

#[pyfunction]
fn session_focus_apply_credit_blocks(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::apply_credit_blocks))
}

#[pyfunction]
fn session_focus_apply_auto_complete_blocks(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::apply_auto_complete_blocks))
}

#[pyfunction]
fn session_focus_split_held(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::split_held))
}

#[pyfunction]
fn session_focus_release_held(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::release_held))
}

#[pyfunction]
fn session_focus_finish_focused_plan(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::finish_focused_plan))
}

#[pyfunction]
fn session_focus_finish_after_load(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::finish_after_load))
}

#[pyfunction]
fn session_focus_finish_intent_on_request(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::finish_intent_on_request))
}

#[pyfunction]
fn session_focus_restart_finished_plan(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::restart_finished_plan))
}

#[pyfunction]
fn session_focus_add_focus_time_plan(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::add_focus_time_plan))
}

#[pyfunction]
fn session_focus_take_break_plan(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::take_break_plan))
}

#[pyfunction]
fn session_focus_load_kept(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::load_kept))
}

#[pyfunction]
fn session_focus_merge_kept(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::merge_kept))
}

#[pyfunction]
fn session_focus_remove_kept(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::remove_kept))
}

#[pyfunction]
fn session_focus_kept_text(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::kept_text))
}

#[pyfunction]
fn session_focus_overdue_for_start(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::overdue_for_start))
}

#[pyfunction]
fn session_focus_start_names_homework(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::start_names_homework))
}

/// Any JSON value. A non-id is None; a number the JSON parser cannot hold is ValueError,
/// which the window turns back into None.
#[pyfunction]
fn session_focus_canonical_account_id(text: &str) -> PyResult<Option<i64>> {
    guard(|| {
        let value: Value =
            serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))?;
        Ok(focus::canonical_account_id(&value))
    })
}

#[pyfunction]
fn session_focus_finish_load_result(args: &str) -> PyResult<String> {
    guard(|| run(args, focus::finish_load_result))
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        session_focus_start_target,
        session_focus_start_decision,
        session_focus_elapsed_min,
        session_focus_tick_step,
        session_focus_advance_begin,
        session_focus_advance_plan,
        session_focus_enter_phase,
        session_focus_credit_plan,
        session_focus_auto_complete_plan,
        session_focus_mutes_alerts,
        session_focus_hold_alerts,
        session_focus_drop_missing,
        session_focus_rebase,
        session_focus_scheduled_blocks,
        session_focus_restore_decision,
        session_focus_focus_spotify_decision,
        session_focus_focus_spotify_open_failed,
        session_focus_start_allowed,
        session_focus_toggle_pause_decision,
        session_focus_end_early_decision,
        session_focus_credit_enqueue_decision,
        session_focus_apply_credit_blocks,
        session_focus_apply_auto_complete_blocks,
        session_focus_split_held,
        session_focus_release_held,
        session_focus_finish_focused_plan,
        session_focus_finish_after_load,
        session_focus_finish_intent_on_request,
        session_focus_restart_finished_plan,
        session_focus_add_focus_time_plan,
        session_focus_take_break_plan,
        session_focus_load_kept,
        session_focus_merge_kept,
        session_focus_remove_kept,
        session_focus_kept_text,
        session_focus_overdue_for_start,
        session_focus_start_names_homework,
        session_focus_canonical_account_id,
        session_focus_finish_load_result,
    );
    Ok(())
}
