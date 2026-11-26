//! Changes request decisions for the Python window.

use ::flexweek_engine::desk::history;
use flexweek_app::session::changes::{
    self, Acknowledgment, SaveAnswer, SaveDraft, SaveFailureKind, StepPlace, Travel,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyModule, PySet};
use serde_json::{Map, Value, json};

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

fn draft_input<'a>(
    week_start: &'a str,
    draft: &'a Value,
    dirty_assignments: &'a [String],
    traveling: Option<&str>,
) -> PyResult<SaveDraft<'a>> {
    let step = &draft["travel_step"];
    Ok(SaveDraft {
        week_start,
        blocks: rows(&draft["blocks"], "blocks")?,
        revision: &draft["revision"],
        committed_blocks: rows(&draft["committed_blocks"], "committed blocks")?,
        assignments: object(&draft["assignments"], "assignments")?,
        committed_assignments: object(&draft["committed_assignments"], "committed assignments")?,
        dirty_assignments,
        travel_weeks: optional_rows(&step["weeks"], "travel weeks")?,
        undo: traveling == Some("undo"),
        stored_parts: rows(&draft["stored_parts"], "stored parts")?,
        saved_repeats: rows(&draft["saved_repeats"], "saved repeats")?,
        repeats: rows(&draft["repeats"], "repeats")?,
        queued_repeats: optional_rows(&draft["queued_repeats"], "queued repeats")?,
    })
}

fn travel(traveling: Option<&str>) -> PyResult<Option<Travel>> {
    match traveling {
        None => Ok(None),
        Some("undo") => Ok(Some(Travel::Undo)),
        Some("redo") => Ok(Some(Travel::Redo)),
        Some(_) => Err(PyValueError::new_err(
            "traveling must be undo, redo or None",
        )),
    }
}

fn travel_name(travel: Travel) -> &'static str {
    match travel {
        Travel::Undo => "undo",
        Travel::Redo => "redo",
    }
}

fn text<'a>(value: &'a Value, name: &str) -> PyResult<&'a str> {
    value
        .as_str()
        .ok_or_else(|| PyValueError::new_err(format!("{name} must be text")))
}

fn optional_text<'a>(value: &'a Value, name: &str) -> PyResult<Option<&'a str>> {
    if value.is_null() {
        Ok(None)
    } else {
        text(value, name).map(Some)
    }
}

fn flag(value: &Value, name: &str) -> PyResult<bool> {
    value
        .as_bool()
        .ok_or_else(|| PyValueError::new_err(format!("{name} must be a boolean")))
}

fn optional_object<'a>(value: &'a Value, name: &str) -> PyResult<Option<&'a Value>> {
    if value.is_null() {
        Ok(None)
    } else {
        object(value, name).map(|_| Some(value))
    }
}

fn optional_list<'a>(value: &'a Value, name: &str) -> PyResult<Option<&'a [Value]>> {
    if value.is_null() {
        Ok(None)
    } else {
        rows(value, name).map(Some)
    }
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
        optional_object(&draft["travel_step"], "travel step")?;
        let input = draft_input(week_start, &draft, &dirty_assignments, traveling)?;
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

#[pyfunction]
fn save_history_step(
    week_start: &str,
    draft: &str,
    dirty_assignments: Vec<String>,
    label: &str,
    uuid4: &Bound<'_, PyAny>,
) -> PyResult<Option<String>> {
    guard(|| {
        let draft = read(draft)?;
        object(&draft, "draft")?;
        optional_object(&draft["travel_step"], "travel step")?;
        let input = draft_input(week_start, &draft, &dirty_assignments, None)?;
        let Some(mut step) = changes::save_step(&input, label).map_err(raise)? else {
            return Ok(None);
        };
        step["id"] = Value::from(fresh_id(uuid4)?);
        Ok(Some(step.to_string()))
    })
}

fn answer_json(answer: Acknowledgment) -> Value {
    let (place, step) = match answer.step {
        None => (Value::Null, Value::Null),
        Some((place, step)) => {
            let place = match place {
                StepPlace::Undo => "undo",
                StepPlace::JoinUndo => "join",
                StepPlace::Redo => "redo",
            };
            (json!(place), step)
        }
    };
    let open_week = answer.open_week.map(|week| {
        json!({
            "blocks": week.blocks,
            "revision": week.revision,
            "stored": week.stored,
            "repeats": week.repeats,
        })
    });
    let homework: Vec<Value> = answer
        .homework
        .into_iter()
        .map(|(id, row)| json!([id, row]))
        .collect();
    json!({
        "session_weeks": answer.session_weeks,
        "live_counts": answer.live_counts,
        "saved_counts": answer.saved_counts,
        "open_week": open_week,
        "homework": homework,
        "step": step,
        "place": place,
        "clear_redo": answer.clear_redo,
        "planned": answer.planned,
        "words": answer.words,
        "waiting_intents": answer.waiting_intents,
    })
}

#[pyfunction]
fn save_answer(data: &str, state: &str) -> PyResult<String> {
    guard(|| {
        let (data, state) = (read(data)?, read(state)?);
        object(&data, "answer")?;
        object(&state, "state")?;
        optional_list(&data["weeks"], "weeks")?;
        optional_list(&data["assignments"], "saved homework")?;
        let answer = SaveAnswer {
            data: &data,
            week_start: text(&state["week_start"], "week_start")?,
            shifted_week: flag(&state["shifted_week"], "shifted_week")?,
            now: text(&state["now"], "now")?,
            sent_repeats: flag(&state["sent_repeats"], "sent_repeats")?,
            assignments: object(&state["assignments"], "assignments")?,
            committed_assignments: object(
                &state["committed_assignments"],
                "committed assignments",
            )?,
            stored_parts: rows(&state["stored_parts"], "stored parts")?,
            traveling: travel(optional_text(&state["traveling"], "traveling")?)?,
            travel_step: optional_object(&state["travel_step"], "travel step")?,
            pending_step: optional_object(&state["pending_step"], "pending step")?,
            plan_step_id: optional_text(&state["plan_step_id"], "plan step id")?,
            join: flag(&state["join"], "join")?,
            held_words: optional_text(&state["held"], "held words")?,
            sent_intents: optional_list(&state["sent_intents"], "sent intents")?,
            waiting_intents: optional_list(&state["waiting_intents"], "waiting intents")?,
        };
        let answer = changes::acknowledge_save(&answer).map_err(raise)?;
        Ok(answer_json(answer).to_string())
    })
}

#[pyfunction]
fn save_refusal(
    status: i64,
    message: &str,
    traveling: Option<&str>,
    holds_step: bool,
) -> PyResult<String> {
    guard(|| {
        let refusal = changes::refuse_save(status, message, travel(traveling)?, holds_step);
        Ok(json!({
            "refused": refusal.failure.kind == SaveFailureKind::Refused,
            "words": refusal.failure.words,
            "conflict": refusal.conflict,
            "roll_back": refusal.roll_back,
            "step_back": refusal.step_back.map(travel_name),
            "reload_words": refusal.reload_words,
        })
        .to_string())
    })
}

#[pyfunction]
fn save_travel_side(
    step: &str,
    side: &str,
    open_week: &str,
    blocks: &str,
    assignments: &str,
    basis: &str,
) -> PyResult<String> {
    guard(|| {
        let redo = match side {
            "before" => false,
            "after" => true,
            _ => return Err(PyValueError::new_err("side must be before or after")),
        };
        let (step, blocks, assignments, basis) =
            (read(step)?, read(blocks)?, read(assignments)?, read(basis)?);
        object(&step, "step")?;
        optional_list(&step["weeks"], "step weeks")?;
        optional_list(&step["assignments"], "step homework")?;
        let applied = history::travel_side(
            &step,
            redo,
            open_week,
            rows(&blocks, "blocks")?,
            object(&assignments, "assignments")?,
            rows(&basis, "basis")?,
        )
        .map_err(raise)?;
        let homework: Vec<Value> = applied
            .assignments
            .into_iter()
            .map(|(id, row)| json!([id, row]))
            .collect();
        Ok(json!({
            "blocks": applied.blocks,
            "assignments": homework,
            "basis": applied.basis,
            "dirty": applied.dirty,
        })
        .to_string())
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
        save_failure,
        save_history_step,
        save_answer,
        save_refusal,
        save_travel_side,
    );
    Ok(())
}
