//! Python bindings for the Material Focus view-model (`flexweek_app::views::focus`).
//!
//! The bridge sends the timer state, preferences, homework and the offer as JSON text and reads the
//! decision back. Every exported function body runs inside `guard(` and refuses a wrong-shaped
//! input with `ValueError` or `TypeError`.

use flexweek_app::views::focus;
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyInt, PyModule, PyString};
use serde_json::{Value, json};

use crate::{guard, raise};

fn parse_object_or_null(text: &str, what: &str) -> PyResult<Value> {
    let parsed: Value = serde_json::from_str(text)
        .map_err(|error| PyValueError::new_err(format!("{what}: {error}")))?;
    match parsed {
        Value::Object(_) | Value::Null => Ok(parsed),
        _ => Err(PyTypeError::new_err(format!(
            "{what} must be a JSON object or null"
        ))),
    }
}

#[pyfunction]
fn views_focus_words() -> PyResult<String> {
    guard(|| {
        let table = |pairs: &[(&str, &str)]| {
            Value::Object(
                pairs
                    .iter()
                    .map(|(key, text)| ((*key).to_string(), Value::String((*text).to_string())))
                    .collect(),
            )
        };
        Ok(json!({
            "phase_words": table(&focus::PHASE_WORDS),
            "ready_words": focus::READY_WORDS,
            "quick_title": focus::QUICK_TITLE,
            "skip_hints": table(&focus::SKIP_HINTS),
            "audio_words": table(&focus::AUDIO_WORDS),
        })
        .to_string())
    })
}

#[pyfunction]
fn views_focus_phase(state: &str) -> PyResult<String> {
    guard(|| focus::phase(&parse_object_or_null(state, "state")?).map_err(raise))
}

#[pyfunction]
fn views_focus_ready(state: &str) -> PyResult<bool> {
    guard(|| Ok(focus::ready(&parse_object_or_null(state, "state")?)))
}

#[pyfunction]
fn views_focus_ended(state: &str) -> PyResult<bool> {
    guard(|| focus::ended(&parse_object_or_null(state, "state")?).map_err(raise))
}

#[pyfunction]
fn views_focus_active(state: &str) -> PyResult<bool> {
    guard(|| focus::active(&parse_object_or_null(state, "state")?).map_err(raise))
}

#[pyfunction]
fn views_focus_running(state: &str) -> PyResult<bool> {
    guard(|| focus::running(&parse_object_or_null(state, "state")?).map_err(raise))
}

#[pyfunction]
fn views_focus_paused(state: &str) -> PyResult<bool> {
    guard(|| focus::paused(&parse_object_or_null(state, "state")?).map_err(raise))
}

#[pyfunction]
fn views_focus_phase_text(state: &str) -> PyResult<String> {
    guard(|| focus::phase_text(&parse_object_or_null(state, "state")?).map_err(raise))
}

#[pyfunction]
fn views_focus_title(state: &str, offer: &str) -> PyResult<String> {
    guard(|| {
        let state = parse_object_or_null(state, "state")?;
        let offer = parse_object_or_null(offer, "offer")?;
        focus::title(&state, &offer).map_err(raise)
    })
}

#[pyfunction]
fn views_focus_offered(state: &str, offer: &str) -> PyResult<bool> {
    guard(|| {
        let state = parse_object_or_null(state, "state")?;
        let offer = parse_object_or_null(offer, "offer")?;
        Ok(focus::offered(&state, &offer))
    })
}

#[pyfunction]
fn views_focus_time_text(state: &str, prefs: &str, now_ms: i64) -> PyResult<String> {
    guard(|| {
        let state = parse_object_or_null(state, "state")?;
        let prefs = parse_object_or_null(prefs, "preferences")?;
        focus::time_text(&state, &prefs, now_ms).map_err(raise)
    })
}

#[pyfunction]
fn views_focus_pause_text(state: &str) -> PyResult<String> {
    guard(|| {
        focus::pause_text(&parse_object_or_null(state, "state")?)
            .map(str::to_string)
            .map_err(raise)
    })
}

#[pyfunction]
fn views_focus_skip_hint(state: &str) -> PyResult<String> {
    guard(|| {
        focus::skip_hint(&parse_object_or_null(state, "state")?)
            .map(str::to_string)
            .map_err(raise)
    })
}

#[pyfunction]
fn views_focus_note(state: &str, prefs: &str, mutes_alerts: bool) -> PyResult<String> {
    guard(|| {
        let state = parse_object_or_null(state, "state")?;
        let prefs = parse_object_or_null(prefs, "preferences")?;
        focus::note(&state, &prefs, mutes_alerts).map_err(raise)
    })
}

#[pyfunction]
fn views_focus_can_finish_homework(state: &str, assignments: &str) -> PyResult<bool> {
    guard(|| {
        let state = parse_object_or_null(state, "state")?;
        let assignments = parse_object_or_null(assignments, "assignments")?;
        focus::can_finish_homework(&state, &assignments).map_err(raise)
    })
}

#[pyfunction]
fn views_focus_end_question(
    state: &str,
    assignments: &str,
    title: &str,
    elapsed_min: i64,
) -> PyResult<String> {
    guard(|| {
        let state = parse_object_or_null(state, "state")?;
        let assignments = parse_object_or_null(assignments, "assignments")?;
        focus::end_question(&state, &assignments, title, elapsed_min).map_err(raise)
    })
}

#[pyfunction]
fn views_focus_refresh_open(open: bool, account_missing: bool) -> PyResult<bool> {
    guard(|| Ok(focus::refresh_open(open, account_missing)))
}

#[pyfunction]
fn views_focus_leave_step(state: &str) -> PyResult<String> {
    guard(|| {
        focus::leave_step(&parse_object_or_null(state, "state")?)
            .map(str::to_string)
            .map_err(raise)
    })
}

#[pyfunction]
fn views_focus_back_step(state: &str) -> PyResult<String> {
    guard(|| {
        focus::back_step(&parse_object_or_null(state, "state")?)
            .map(str::to_string)
            .map_err(raise)
    })
}

/// The homework finish answers "finished", "queued" or False; anything else is a wrong shape.
#[pyfunction]
fn views_focus_finish_step(outcome: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let named = if outcome.is_instance_of::<PyString>() {
            Some(outcome.extract::<String>()?)
        } else if outcome.is_none() || outcome.is_instance_of::<PyBool>() {
            None
        } else {
            return Err(PyTypeError::new_err(
                "the finish outcome must be a string, a boolean or None",
            ));
        };
        Ok(focus::finish_step(named.as_deref()).to_string())
    })
}

/// What QML sends to Start focus: an empty block id and a day that is not a whole number are None.
#[pyfunction]
fn views_focus_start_args(
    block_id: &str,
    day: &Bound<'_, PyAny>,
) -> PyResult<(Option<String>, Option<i64>)> {
    guard(|| {
        let day = if day.is_instance_of::<PyInt>() {
            Some(day.extract::<i64>()?)
        } else {
            None
        };
        Ok((focus::block_for_start(block_id).map(str::to_string), day))
    })
}

#[pyfunction]
fn views_focus_after_start_step(started: bool) -> PyResult<String> {
    guard(|| Ok(focus::after_start_step(started).to_string()))
}

#[pyfunction]
fn views_focus_remembers_origin(object_name: &str) -> PyResult<bool> {
    guard(|| Ok(focus::remembers_origin(object_name)))
}

#[pyfunction]
fn views_focus_restores_origin(
    visible: bool,
    enabled: bool,
    can_take_focus: bool,
) -> PyResult<bool> {
    guard(|| Ok(focus::restores_origin(visible, enabled, can_take_focus)))
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        views_focus_words,
        views_focus_phase,
        views_focus_ready,
        views_focus_ended,
        views_focus_active,
        views_focus_running,
        views_focus_paused,
        views_focus_phase_text,
        views_focus_title,
        views_focus_offered,
        views_focus_time_text,
        views_focus_pause_text,
        views_focus_skip_hint,
        views_focus_note,
        views_focus_can_finish_homework,
        views_focus_end_question,
        views_focus_refresh_open,
        views_focus_leave_step,
        views_focus_back_step,
        views_focus_finish_step,
        views_focus_start_args,
        views_focus_after_start_step,
        views_focus_remembers_origin,
        views_focus_restores_origin,
    );
    Ok(())
}
