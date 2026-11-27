//! The session's block and repeat edit decisions (`flexweek_app::session::block_edits`) for the
//! Python window, with JSON text across. The window keeps the state and settles the week after it
//! applies what is decided.

use flexweek_app::session::block_edits::{
    BlockDeleteInput, BlockEditInput, HandMoveInput, RepeatEditInput, apply_block_edit,
    apply_hand_move, delete_block, delete_selected_plan, has_block, place_block_words, repeat_edit,
    resume_pending, setup_standing, unpin_label,
};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::Value;

use crate::{guard, raise};

fn read(text: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))
}

fn objects(value: Value, what: &str) -> PyResult<Vec<Value>> {
    let Value::Array(items) = value else {
        return Err(PyTypeError::new_err(format!("{what} are a list")));
    };
    if items.iter().any(|item| !item.is_object()) {
        return Err(PyTypeError::new_err(format!(
            "every one of the {what} is an object"
        )));
    }
    Ok(items)
}

/// An added or edited block (JSON object) on the week (JSON list), as JSON:
/// `{"blocks", "label", "block_id"}`. `scope` is `series` or `occurrence`; `day` is a day number or
/// None; `new_id` is the id one split-off day takes.
#[pyfunction]
#[pyo3(signature = (blocks, block, scope, day, new_id))]
fn block_edit_json(
    blocks: &str,
    block: &str,
    scope: &str,
    day: Option<i64>,
    new_id: &str,
) -> PyResult<String> {
    guard(|| {
        let blocks = objects(read(blocks)?, "blocks")?;
        let block = read(block)?;
        if !block.is_object() {
            return Err(PyTypeError::new_err("the block is an object"));
        }
        let input = BlockEditInput {
            blocks: &Value::Array(blocks),
            block: &block,
            scope,
            day,
            new_id,
        };
        let edit = apply_block_edit(&input).map_err(raise)?;
        Ok(edit.to_json().to_string())
    })
}

/// The hand-move rule's answer (JSON object) applied to the week (JSON list), as JSON:
/// `{"moved", "blocks", "block_id", "label", "problem"}`. `block_id` is the id the student dropped.
#[pyfunction]
fn block_hand_json(blocks: &str, answer: &str, block_id: &str) -> PyResult<String> {
    guard(|| {
        let blocks = objects(read(blocks)?, "blocks")?;
        let answer = read(answer)?;
        if !answer.is_object() {
            return Err(PyTypeError::new_err("the hand-move answer is an object"));
        }
        let input = HandMoveInput {
            blocks: &Value::Array(blocks),
            answer: &answer,
            block_id,
        };
        let moved = apply_hand_move(&input).map_err(raise)?;
        Ok(moved.to_json().to_string())
    })
}

/// A deleted block, as JSON: `{"blocks", "repeats", "clear_selection", "label"}`, or None when the
/// block is not in this week. `scope` is `series` or `occurrence`; `day` is a day number or None;
/// `selected_id` is the selected block's id or None; `label` names the Undo step or is None for the
/// usual words.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (blocks, repeats, block_id, scope, day, every_week, selected_id, label))]
fn block_delete_json(
    blocks: &str,
    repeats: &str,
    block_id: &str,
    scope: &str,
    day: Option<i64>,
    every_week: bool,
    selected_id: Option<&str>,
    label: Option<&str>,
) -> PyResult<Option<String>> {
    guard(|| {
        let blocks = objects(read(blocks)?, "blocks")?;
        let repeats = objects(read(repeats)?, "repeats")?;
        let input = BlockDeleteInput {
            blocks: &Value::Array(blocks),
            repeats: &Value::Array(repeats),
            block_id,
            scope,
            day,
            every_week,
            selected_id,
            label,
        };
        let gone = delete_block(&input).map_err(raise)?;
        Ok(gone.map(|decision| decision.to_json().to_string()))
    })
}

/// The repeats become `after` (JSON list) from this week on, as JSON:
/// `{"blocks", "repeats", "stamped", "preview", "leaves_week"}`, or None when nothing changed.
/// `saved_repeats` are what the server last said; `send` is the held repeat intents or null;
/// `edited` is `keep`, `replace`, or `from_today`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (blocks, repeats, after, saved_repeats, send, week_start, edited, today, first_weekday))]
fn repeat_edit_json(
    blocks: &str,
    repeats: &str,
    after: &str,
    saved_repeats: &str,
    send: &str,
    week_start: &str,
    edited: &str,
    today: &str,
    first_weekday: i64,
) -> PyResult<Option<String>> {
    guard(|| {
        let blocks = objects(read(blocks)?, "blocks")?;
        let repeats = objects(read(repeats)?, "repeats")?;
        let after = objects(read(after)?, "after")?;
        let saved_repeats = objects(read(saved_repeats)?, "saved repeats")?;
        let send = match read(send)? {
            Value::Null => None,
            Value::Array(items) => {
                if items.iter().any(|item| !item.is_object()) {
                    return Err(PyTypeError::new_err(
                        "every one of the held repeats is an object",
                    ));
                }
                Some(Value::Array(items))
            }
            _ => {
                return Err(PyTypeError::new_err("the held repeats are a list or null"));
            }
        };
        let input = RepeatEditInput {
            blocks: &Value::Array(blocks),
            repeats: &Value::Array(repeats),
            after: &Value::Array(after),
            saved_repeats: &Value::Array(saved_repeats),
            send: send.as_ref(),
            week_start,
            edited,
            today,
            first_weekday,
        };
        let edit = repeat_edit(&input).map_err(raise)?;
        Ok(edit.map(|decision| decision.to_json().to_string()))
    })
}

/// The repeats after Setup (JSON lists): School and the activities as `blocks` has them, and every
/// weekly fixed time standing in `repeats`, as JSON.
#[pyfunction]
fn setup_standing_json(repeats: &str, blocks: &str) -> PyResult<String> {
    guard(|| {
        let repeats = objects(read(repeats)?, "repeats")?;
        let blocks = objects(read(blocks)?, "blocks")?;
        let standing =
            setup_standing(&Value::Array(blocks), &Value::Array(repeats)).map_err(raise)?;
        Ok(Value::Array(standing).to_string())
    })
}

/// Whether `block_id` exists in `blocks` (JSON list).
#[pyfunction]
fn has_block_json(blocks: &str, block_id: &str) -> PyResult<bool> {
    guard(|| {
        let blocks = objects(read(blocks)?, "blocks")?;
        has_block(&Value::Array(blocks), block_id).map_err(raise)
    })
}

/// The words `place_block` emits after a hand move succeeds, or None when `block_id` is absent.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (blocks, block_id, from_day, day, start, end, week_start))]
fn place_block_words_json(
    blocks: &str,
    block_id: &str,
    from_day: i64,
    day: i64,
    start: i64,
    end: i64,
    week_start: &str,
) -> PyResult<Option<String>> {
    guard(|| {
        let blocks = objects(read(blocks)?, "blocks")?;
        place_block_words(
            &Value::Array(blocks),
            block_id,
            from_day,
            day,
            start,
            end,
            week_start,
        )
        .map_err(raise)
    })
}

/// What `_resume_pending` schedules once idle: `{"place": [...] | null, "flush_setup": bool}`.
#[pyfunction]
#[pyo3(signature = (busy, hand_waiting, has_setup_prefs, has_setup_work_windows, has_setup_week))]
fn resume_pending_json(
    busy: bool,
    hand_waiting: &str,
    has_setup_prefs: bool,
    has_setup_work_windows: bool,
    has_setup_week: bool,
) -> PyResult<String> {
    guard(|| {
        let waiting = match read(hand_waiting)? {
            Value::Null => None,
            Value::Array(items) if items.len() == 5 => Some(Value::Array(items)),
            _ => {
                return Err(PyTypeError::new_err(
                    "hand_waiting is a 5-item list or null",
                ));
            }
        };
        let decision = resume_pending(
            busy,
            waiting.as_ref(),
            has_setup_prefs,
            has_setup_work_windows,
            has_setup_week,
        );
        Ok(decision.to_json().to_string())
    })
}

/// What `delete_selected` deletes, as JSON `{"block_id", "scope", "day"}`, or None.
#[pyfunction]
#[pyo3(signature = (blocks, selected_block_id, selected_occurrence_day))]
fn delete_selected_plan_json(
    blocks: &str,
    selected_block_id: Option<&str>,
    selected_occurrence_day: Option<i64>,
) -> PyResult<Option<String>> {
    guard(|| {
        let blocks = objects(read(blocks)?, "blocks")?;
        let plan = delete_selected_plan(
            &Value::Array(blocks),
            selected_block_id,
            selected_occurrence_day,
        )
        .map_err(raise)?;
        Ok(plan.map(|decision| decision.to_json().to_string()))
    })
}

/// The Undo step label for `unpin_assignment`: `"unpinning <title>"` (or `"unpinning homework"`).
#[pyfunction]
fn unpin_label_json(assignments: &str, assignment_id: &str) -> PyResult<String> {
    guard(|| {
        let assignments = read(assignments)?;
        if !assignments.is_object() {
            return Err(PyTypeError::new_err("the assignments are an object"));
        }
        unpin_label(&assignments, assignment_id).map_err(raise)
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        block_edit_json,
        block_hand_json,
        block_delete_json,
        repeat_edit_json,
        setup_standing_json,
        has_block_json,
        place_block_words_json,
        resume_pending_json,
        delete_selected_plan_json,
        unpin_label_json,
    );
    Ok(())
}
