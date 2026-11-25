//! The focus timer's decisions (`flexweek_app::session::focus`, 2.0.0 plan P4 group 6) for the Python
//! window: `desktop/native/focus.py` sends one JSON text of arguments and reads one JSON text back.

use ::flexweek_engine::EngineResult;
use flexweek_app::session::focus;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::Value;

use crate::guard;

fn run(args: &str, decide: fn(&Value) -> EngineResult<Value>) -> PyResult<String> {
    guard(|| {
        let args: Value = serde_json::from_str(args)
            .map_err(|error| PyValueError::new_err(error.to_string()))?;
        decide(&args)
            .map(|answer| answer.to_string())
            .map_err(crate::raise)
    })
}

#[pyfunction]
fn session_focus_start_target(args: &str) -> PyResult<String> {
    run(args, focus::start_target)
}

#[pyfunction]
fn session_focus_start_decision(args: &str) -> PyResult<String> {
    run(args, focus::start_decision)
}

#[pyfunction]
fn session_focus_elapsed_min(args: &str) -> PyResult<String> {
    run(args, focus::elapsed_min)
}

#[pyfunction]
fn session_focus_tick_step(args: &str) -> PyResult<String> {
    run(args, focus::tick_step)
}

#[pyfunction]
fn session_focus_advance_begin(args: &str) -> PyResult<String> {
    run(args, focus::advance_begin)
}

#[pyfunction]
fn session_focus_advance_plan(args: &str) -> PyResult<String> {
    run(args, focus::advance_plan)
}

#[pyfunction]
fn session_focus_enter_phase(args: &str) -> PyResult<String> {
    run(args, focus::enter_phase)
}

#[pyfunction]
fn session_focus_credit_plan(args: &str) -> PyResult<String> {
    run(args, focus::credit_plan)
}

#[pyfunction]
fn session_focus_auto_complete_plan(args: &str) -> PyResult<String> {
    run(args, focus::auto_complete_plan)
}

#[pyfunction]
fn session_focus_mutes_alerts(args: &str) -> PyResult<String> {
    run(args, focus::mutes_alerts)
}

#[pyfunction]
fn session_focus_hold_alerts(args: &str) -> PyResult<String> {
    run(args, focus::hold_alerts)
}

#[pyfunction]
fn session_focus_drop_missing(args: &str) -> PyResult<String> {
    run(args, focus::drop_missing)
}

#[pyfunction]
fn session_focus_rebase(args: &str) -> PyResult<String> {
    run(args, focus::rebase)
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
        session_focus_rebase
    );
    Ok(())
}
