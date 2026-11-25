//! The session's block and repeat edit decisions (`flexweek_app::session::block_edits`) for the
//! Python window, with JSON text across. The window keeps the state and settles the week after it
//! applies what is decided.

use flexweek_app::session::block_edits::{
    BlockDeleteInput, BlockEditInput, HandMoveInput, RepeatEditInput, apply_block_edit,
    apply_hand_move, delete_block, repeat_edit, setup_standing,
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

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        block_edit_json,
        block_hand_json,
        block_delete_json,
        repeat_edit_json,
        setup_standing_json
    );
    Ok(())
}
