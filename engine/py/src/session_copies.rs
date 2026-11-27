//! The session's clipboard, copy rows and relocation decisions
//! (`flexweek_app::session::copies`) for the Python window, with JSON text across. The window keeps
//! the state: it reads the clock, fetches weeks, draws ids, looks assignments up, and writes what
//! is decided here.

use flexweek_app::session::copies::{
    ClipboardBlock, CommitGroupsBatchInput, ConfirmPreviewInput, CopyDay, DateProblemInput,
    MoveToDateBatchInput, MoveToDateInput, PasteReady, PasteSelection, PreviewGroups, Relocation,
    RelocationInput, block_on_week, build_move_to_date_batch, clipboard_block, commit_groups_batch,
    commit_groups_order, confirm_preview_plan, copy_block_skipped, copy_day_items, copy_day_plan,
    copy_empty_words, copy_selected_plan, date_problem, duplicate_selected_prepare,
    fixed_copy_rows, move_to_date_needed, paste_destination, paste_proposals_build,
    paste_proposals_prepare, paste_ready, prepare_move_to_date, preview_groups,
    previous_week_for_copy, relocate, resolve_date_span,
};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::{Map, Value};

use crate::desk::fresh_id;
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

/// The assignments table: always an object of assignment objects, never a list or primitive.
fn assignments_table(value: Value) -> PyResult<Value> {
    let Value::Object(ref entries) = value else {
        return Err(PyTypeError::new_err("the assignments are an object"));
    };
    if entries
        .values()
        .any(|item| !item.is_object() && !item.is_null())
    {
        return Err(PyTypeError::new_err("every assignment is an object"));
    }
    Ok(value)
}

/// A JSON object, or None for JSON null: anything else never came from the window.
fn object_or_null(value: Value, what: &str) -> PyResult<Option<Value>> {
    if value.is_null() {
        return Ok(None);
    }
    if !value.is_object() {
        return Err(PyTypeError::new_err(format!("{what} is an object")));
    }
    Ok(Some(value))
}

/// The rows the empty-week copy sheet offers from last week's `source` (JSON object or null):
/// `{"rows": [...], "words": ...}` with one side null. `new_ids` holds one id per source block.
#[pyfunction]
#[pyo3(signature = (source, shown_start, new_ids))]
fn fixed_copy_rows_json(source: &str, shown_start: &str, new_ids: Vec<String>) -> PyResult<String> {
    guard(|| {
        let source = object_or_null(read(source)?, "the source week")?;
        let mut ids = new_ids.into_iter();
        let rows = fixed_copy_rows(source.as_ref(), shown_start, &mut ids).map_err(raise)?;
        Ok(rows.to_json().to_string())
    })
}

/// What the empty-week copy sheet says when `source` (JSON object or null) offers no rows,
/// as JSON text.
#[pyfunction]
fn copy_empty_words_json(source: &str) -> PyResult<String> {
    guard(|| {
        let source = object_or_null(read(source)?, "the source week")?;
        let words = copy_empty_words(source.as_ref()).map_err(raise)?;
        Ok(Value::String(words.to_string()).to_string())
    })
}

fn selection<'a>(
    selected_block_id: Option<&'a str>,
    selected_occurrence_day: Option<i64>,
    planner_view: &'a str,
    first_weekday: u32,
    selected_day: &'a str,
    today_iso: &'a str,
) -> PasteSelection<'a> {
    PasteSelection {
        selected_block_id,
        selected_occurrence_day,
        planner_view,
        first_weekday,
        selected_day,
        today_iso,
    }
}

/// Why the block cannot go on `to_iso`, or None. Weeks and days are resolved by the window;
/// `block` and `assignments` are JSON (null when missing); `start`, `duration_min` and
/// `assignment_id` are the dialog's own values for a block that is not on a week.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (block_id, from_iso, to_iso, from_week, to_week, from_day, to_day, block, start, duration_min, assignment_id, assignments, now_iso, now_minute, time_step))]
fn date_problem_json(
    block_id: &str,
    from_iso: &str,
    to_iso: &str,
    from_week: &str,
    to_week: &str,
    from_day: i64,
    to_day: i64,
    block: &str,
    start: Option<&str>,
    duration_min: Option<i64>,
    assignment_id: Option<&str>,
    assignments: &str,
    now_iso: &str,
    now_minute: i64,
    time_step: i64,
) -> PyResult<Option<String>> {
    guard(|| {
        let block = object_or_null(read(block)?, "the block")?;
        let assignments = assignments_table(read(assignments)?)?;
        let input = DateProblemInput {
            block_id,
            from_iso,
            to_iso,
            from_week,
            to_week,
            from_day,
            to_day,
            block: block.as_ref(),
            start,
            duration_min,
            assignment_id,
            assignments: &assignments,
            now_iso,
            now_minute,
            time_step,
        };
        date_problem(&input).map_err(raise)
    })
}

/// One block moved to another date, as JSON: `{"say", "source_after", "dest_after", "title"}`.
/// `source` and `dest` are `{"blocks", "revision"}` (dest null on the same week); `dest_words`
/// names the destination week; `new_id` is the id one split-off day takes.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (block_id, from_day, to_day, from_week, to_week, source, dest, assignments, dest_words, new_id))]
fn relocate_json(
    block_id: &str,
    from_day: i64,
    to_day: i64,
    from_week: &str,
    to_week: &str,
    source: &str,
    dest: &str,
    assignments: &str,
    dest_words: &str,
    new_id: &str,
) -> PyResult<String> {
    guard(|| {
        let source = read(source)?;
        if !source.is_object() {
            return Err(PyTypeError::new_err("the source week is an object"));
        }
        let dest = object_or_null(read(dest)?, "the destination week")?;
        let assignments = assignments_table(read(assignments)?)?;
        let input = RelocationInput {
            block_id,
            from_day,
            to_day,
            from_week,
            to_week,
            source: &source,
            dest: dest.as_ref(),
            assignments: &assignments,
            dest_words,
        };
        let mut ids = std::iter::once(new_id.to_string());
        let moved: Relocation = relocate(&input, &mut ids).map_err(raise)?;
        Ok(moved.to_json().to_string())
    })
}

/// One block copied, as JSON: `{"clipboard", "words"}`. `block_id` is None when nothing is
/// selected. `new_id` groups the copied item.
#[pyfunction]
#[pyo3(signature = (blocks, block_id, day, scope, new_id))]
fn clipboard_block_json(
    blocks: &str,
    block_id: Option<&str>,
    day: Option<i64>,
    scope: &str,
    new_id: &str,
) -> PyResult<String> {
    guard(|| {
        let blocks = objects(read(blocks)?, "blocks")?;
        let copied: ClipboardBlock =
            clipboard_block(&Value::Array(blocks), block_id, day, scope, new_id).map_err(raise)?;
        Ok(copied.to_json().to_string())
    })
}

/// Where a paste lands, as JSON `{"day", "start"}`, or None: the selected occurrence with its
/// placed start, the planner's day, or the column holding today.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (blocks, trace, selected_block_id, selected_occurrence_day, planner_view, first_weekday, selected_day, today_iso, week_start))]
fn paste_destination_json(
    blocks: &str,
    trace: &str,
    selected_block_id: Option<&str>,
    selected_occurrence_day: Option<i64>,
    planner_view: &str,
    first_weekday: u32,
    selected_day: &str,
    today_iso: &str,
    week_start: &str,
) -> PyResult<Option<String>> {
    guard(|| {
        let blocks = Value::Array(objects(read(blocks)?, "blocks")?);
        let trace = object_or_null(read(trace)?, "the trace")?.unwrap_or(Value::Null);
        let found = paste_destination(
            &blocks,
            &trace,
            &selection(
                selected_block_id,
                selected_occurrence_day,
                planner_view,
                first_weekday,
                selected_day,
                today_iso,
            ),
            week_start,
        )
        .map_err(raise)?;
        Ok(found.map(|destination| destination.to_json().to_string()))
    })
}

/// One day copied, as JSON: `{"clipboard", "words"}`. `day` is the resolved day to take;
/// None cannot index the week, as before. `new_ids` holds one id per block on the week.
#[pyfunction]
#[pyo3(signature = (blocks, trace, day, week_start, new_ids))]
fn clipboard_day_json(
    blocks: &str,
    trace: &str,
    day: Option<i64>,
    week_start: &str,
    new_ids: Vec<String>,
) -> PyResult<String> {
    guard(|| {
        let blocks = Value::Array(objects(read(blocks)?, "blocks")?);
        let trace = object_or_null(read(trace)?, "the trace")?.unwrap_or(Value::Null);
        let mut ids = new_ids.into_iter();
        let copied: CopyDay =
            copy_day_items(&blocks, &trace, day, week_start, &mut ids).map_err(raise)?;
        Ok(copied.to_json().to_string())
    })
}

/// A paste about to preview, as JSON: `{"day", "start", "words"}` with words set when there is
/// nowhere to paste. `target_day` set skips the destination choice. `clipboard` is null when
/// nothing is copied.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (clipboard, target_day, target_start, blocks, trace, selected_block_id, selected_occurrence_day, planner_view, first_weekday, selected_day, today_iso, week_start))]
fn paste_ready_json(
    clipboard: &str,
    target_day: Option<i64>,
    target_start: Option<&str>,
    blocks: &str,
    trace: &str,
    selected_block_id: Option<&str>,
    selected_occurrence_day: Option<i64>,
    planner_view: &str,
    first_weekday: u32,
    selected_day: &str,
    today_iso: &str,
    week_start: &str,
) -> PyResult<String> {
    guard(|| {
        let clipboard = object_or_null(read(clipboard)?, "the clipboard")?;
        let blocks = Value::Array(objects(read(blocks)?, "blocks")?);
        let trace = object_or_null(read(trace)?, "the trace")?.unwrap_or(Value::Null);
        let ready: PasteReady = paste_ready(
            clipboard.as_ref(),
            target_day,
            target_start,
            &blocks,
            &trace,
            &selection(
                selected_block_id,
                selected_occurrence_day,
                planner_view,
                first_weekday,
                selected_day,
                today_iso,
            ),
            week_start,
        )
        .map_err(raise)?;
        Ok(ready.to_json().to_string())
    })
}

/// The preview's checked `rows` (JSON list) after the merge, as JSON: `{"say", "by_week"}` with
/// one side set. `operation_id` groups the added blocks.
#[pyfunction]
fn preview_groups_json(rows: &str, operation_id: &str) -> PyResult<String> {
    guard(|| {
        let rows = read(rows)?;
        let preview: PreviewGroups = preview_groups(&rows, operation_id).map_err(raise)?;
        Ok(preview.to_json().to_string())
    })
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

fn req_bool(map: &Map<String, Value>, key: &str) -> PyResult<bool> {
    req(map, key)?
        .as_bool()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be a boolean")))
}

fn req_str<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a str> {
    req(map, key)?
        .as_str()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be a string")))
}

fn opt_str<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<Option<&'a str>> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => value
            .as_str()
            .map(Some)
            .ok_or_else(|| PyValueError::new_err(format!("{key} must be a string or null"))),
    }
}

fn opt_i64(map: &Map<String, Value>, key: &str) -> PyResult<Option<i64>> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => value
            .as_i64()
            .map(Some)
            .ok_or_else(|| PyValueError::new_err(format!("{key} must be an integer or null"))),
    }
}

fn req_u32(map: &Map<String, Value>, key: &str) -> PyResult<u32> {
    req(map, key)?
        .as_u64()
        .and_then(|value| u32::try_from(value).ok())
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be a non-negative integer")))
}

fn req_array<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a Vec<Value>> {
    req(map, key)?
        .as_array()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be a list")))
}

fn req_object_map<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<&'a Map<String, Value>> {
    req(map, key)?
        .as_object()
        .ok_or_else(|| PyValueError::new_err(format!("{key} must be an object")))
}

fn opt_object_value<'a>(map: &'a Map<String, Value>, key: &str) -> PyResult<Option<&'a Value>> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(value) if value.is_object() => Ok(Some(value)),
        Some(_) => Err(PyValueError::new_err(format!(
            "{key} must be an object or null"
        ))),
    }
}

/// Which week `copy_last_week_fixed_rows` reads, as JSON: `{"kind": "absent" | "say" | "ready", ...}`.
#[pyfunction]
fn session_previous_week_for_copy(
    signed_in: bool,
    week_start: &str,
    first_weekday: u32,
) -> PyResult<String> {
    guard(|| {
        Ok(previous_week_for_copy(signed_in, week_start, first_weekday)
            .to_json()
            .to_string())
    })
}

/// Find `block_id` inside one local week state JSON (`{"blocks": [...]}` or null).
#[pyfunction]
fn session_block_on_week(state: &str, block_id: &str) -> PyResult<Option<String>> {
    guard(|| {
        let state = object_or_null(read(state)?, "the week state")?;
        let found = block_on_week(state.as_ref(), block_id).map_err(raise)?;
        Ok(found.map(|block| block.to_string()))
    })
}

/// Resolve `(from_iso, to_iso)` against `first_weekday` into weeks and day indices, or None.
#[pyfunction]
fn session_resolve_date_span(
    from_iso: &str,
    to_iso: &str,
    first_weekday: u32,
) -> PyResult<Option<String>> {
    guard(|| {
        Ok(resolve_date_span(from_iso, to_iso, first_weekday)
            .map(|span| span.to_json().to_string()))
    })
}

/// Guard and key setup for `move_to_date`.
#[pyfunction]
fn session_prepare_move_to_date(payload: &str) -> PyResult<String> {
    guard(|| {
        let root = read(payload)?;
        let map = as_object(&root, "move to date")?;
        let input = MoveToDateInput {
            account_id: opt_i64(map, "account_id")?,
            conflict: req_bool(map, "conflict")?,
            busy: req_bool(map, "busy")?,
            pending_save: req_bool(map, "pending_save")?,
            block_id: req_str(map, "block_id")?,
            from_iso: req_str(map, "from_iso")?,
            to_iso: req_str(map, "to_iso")?,
            first_weekday: req_u32(map, "first_weekday")?,
        };
        Ok(prepare_move_to_date(&input).to_json().to_string())
    })
}

/// Weeks `move_to_date` still needs to fetch, as JSON list.
#[pyfunction]
fn session_move_to_date_needed(
    from_week: &str,
    to_week: &str,
    has_source: bool,
    has_dest: bool,
) -> PyResult<String> {
    guard(|| {
        let needed = move_to_date_needed(from_week, to_week, has_source, has_dest);
        Ok(Value::Array(needed.into_iter().map(Value::String).collect()).to_string())
    })
}

/// Build the `submit_batch` payload for `_commit_move_to_date`, or return refusal words.
#[pyfunction]
fn session_build_move_to_date_batch(py: Python<'_>, payload: &str) -> PyResult<String> {
    guard(|| {
        let root = read(payload)?;
        let map = as_object(&root, "move to date batch")?;
        let assignments = req(map, "assignments")?;
        if !assignments.is_object() {
            return Err(PyTypeError::new_err("the assignments are an object"));
        }
        let input = MoveToDateBatchInput {
            block_id: req_str(map, "block_id")?,
            from_iso: req_str(map, "from_iso")?,
            to_iso: req_str(map, "to_iso")?,
            from_week: req_str(map, "from_week")?,
            to_week: req_str(map, "to_week")?,
            source_local: opt_object_value(map, "source_local")?,
            dest_local: opt_object_value(map, "dest_local")?,
            fetched: req_object_map(map, "fetched")?,
            assignments,
            today_iso: req_str(map, "today_iso")?,
            operation_id: req_str(map, "operation_id")?,
            attempt_key: req_str(map, "attempt_key")?,
        };
        let new_id = fresh_id(py);
        let decision = build_move_to_date_batch(&input, &new_id).map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

/// Copy the selected block into the clipboard, or refuse when nothing is selected.
#[pyfunction]
#[pyo3(signature = (signed_in, blocks, selected_block_id, selected_occurrence_day, scope, new_id))]
fn session_copy_selected(
    signed_in: bool,
    blocks: &str,
    selected_block_id: Option<&str>,
    selected_occurrence_day: Option<i64>,
    scope: &str,
    new_id: &str,
) -> PyResult<String> {
    guard(|| {
        let blocks = Value::Array(objects(read(blocks)?, "blocks")?);
        let decision = copy_selected_plan(
            signed_in,
            &blocks,
            selected_block_id,
            selected_occurrence_day,
            scope,
            new_id,
        )
        .map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

/// Copy one day's items into the clipboard, resolving destination when `day` is null.
#[pyfunction]
fn session_copy_day(py: Python<'_>, payload: &str) -> PyResult<String> {
    guard(|| {
        let root = read(payload)?;
        let map = as_object(&root, "copy day")?;
        let block_list = req_array(map, "blocks")?;
        if block_list.iter().any(|item| !item.is_object()) {
            return Err(PyTypeError::new_err("every one of the blocks is an object"));
        }
        let blocks = Value::Array(block_list.clone());
        let trace = opt_object_value(map, "trace")?
            .cloned()
            .unwrap_or(Value::Null);
        let sel = selection(
            opt_str(map, "selected_block_id")?,
            opt_i64(map, "selected_occurrence_day")?,
            req_str(map, "planner_view")?,
            req_u32(map, "first_weekday")?,
            req_str(map, "selected_day")?,
            req_str(map, "today_iso")?,
        );
        let mut ids = block_list.iter().map(|_| fresh_id(py));
        let decision = copy_day_plan(
            req_bool(map, "signed_in")?,
            &blocks,
            &trace,
            opt_i64(map, "day")?,
            &sel,
            req_str(map, "week_start")?,
            &mut ids,
        )
        .map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

/// Check sign-in, clipboard and paste destination for `paste_proposals`.
#[pyfunction]
fn session_paste_proposals_prepare(payload: &str) -> PyResult<String> {
    guard(|| {
        let root = read(payload)?;
        let map = as_object(&root, "paste proposals prepare")?;
        let block_list = req_array(map, "blocks")?;
        if block_list.iter().any(|item| !item.is_object()) {
            return Err(PyTypeError::new_err("every one of the blocks is an object"));
        }
        let blocks = Value::Array(block_list.clone());
        let trace = opt_object_value(map, "trace")?
            .cloned()
            .unwrap_or(Value::Null);
        let clipboard = opt_object_value(map, "clipboard")?;
        let sel = selection(
            opt_str(map, "selected_block_id")?,
            opt_i64(map, "selected_occurrence_day")?,
            req_str(map, "planner_view")?,
            req_u32(map, "first_weekday")?,
            req_str(map, "selected_day")?,
            req_str(map, "today_iso")?,
        );
        let decision = paste_proposals_prepare(
            req_bool(map, "signed_in")?,
            clipboard,
            opt_i64(map, "target_day")?,
            opt_str(map, "target_start")?,
            &blocks,
            &trace,
            &sel,
            req_str(map, "week_start")?,
            req_bool(map, "has_assignments")?,
        )
        .map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

/// Build paste/duplicate proposal rows from `clipboard` and homework uncovered minutes.
#[pyfunction]
#[pyo3(signature = (clipboard, week_start, target_day, target_start, assignments, minutes))]
fn session_paste_proposals_build(
    clipboard: &str,
    week_start: &str,
    target_day: i64,
    target_start: Option<&str>,
    assignments: &str,
    minutes: &str,
) -> PyResult<String> {
    guard(|| {
        let clipboard = read(clipboard)?;
        if !clipboard.is_object() {
            return Err(PyTypeError::new_err("the clipboard is an object"));
        }
        let assignments = assignments_table(read(assignments)?)?;
        let minutes = read(minutes)?;
        if !minutes.is_object() {
            return Err(PyTypeError::new_err("the homework minutes are an object"));
        }
        let rows = paste_proposals_build(
            &clipboard,
            week_start,
            target_day,
            target_start,
            &assignments,
            &minutes,
        )
        .map_err(raise)?;
        Ok(Value::Array(rows).to_string())
    })
}

/// Prepare a duplicate preview without touching the session's clipboard or announcing a copy.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (signed_in, blocks, selected_block_id, selected_occurrence_day, scope, new_id, has_assignments))]
fn session_duplicate_selected_prepare(
    signed_in: bool,
    blocks: &str,
    selected_block_id: Option<&str>,
    selected_occurrence_day: Option<i64>,
    scope: &str,
    new_id: &str,
    has_assignments: bool,
) -> PyResult<String> {
    guard(|| {
        let blocks = Value::Array(objects(read(blocks)?, "blocks")?);
        let decision = duplicate_selected_prepare(
            signed_in,
            &blocks,
            selected_block_id,
            selected_occurrence_day,
            scope,
            new_id,
            has_assignments,
        )
        .map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

/// Decide single-week vs multi-week save for `confirm_preview`.
#[pyfunction]
fn session_confirm_preview_plan(payload: &str) -> PyResult<String> {
    guard(|| {
        let root = read(payload)?;
        let map = as_object(&root, "confirm preview")?;
        let rows = req(map, "rows")?;
        let blocks = req(map, "blocks")?;
        if !blocks.is_array() {
            return Err(PyTypeError::new_err("blocks are a list"));
        }
        let input = ConfirmPreviewInput {
            signed_in: req_bool(map, "signed_in")?,
            conflict: req_bool(map, "conflict")?,
            rows,
            week_start: req_str(map, "week_start")?,
            blocks,
            today_iso: req_str(map, "today_iso")?,
            operation_id: opt_str(map, "operation_id")?,
            attempt_key: opt_str(map, "attempt_key")?,
            attempts: req_object_map(map, "attempts")?,
            fresh_operation_id: req_str(map, "fresh_operation_id")?,
        };
        let decision = confirm_preview_plan(&input).map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

/// Remote weeks to GET in `_commit_groups` order (reversed non-open weeks).
#[pyfunction]
fn session_commit_groups_order(by_week: &str, week_start: &str) -> PyResult<String> {
    guard(|| {
        let root = read(by_week)?;
        let map = as_object(&root, "by_week")?;
        let order = commit_groups_order(map, week_start);
        Ok(Value::Array(order.into_iter().map(Value::String).collect()).to_string())
    })
}

/// Build the `submit_batch` payload for `_commit_groups`, checking block capacity per week.
#[pyfunction]
fn session_commit_groups_batch(payload: &str) -> PyResult<String> {
    guard(|| {
        let root = read(payload)?;
        let map = as_object(&root, "commit groups batch")?;
        let current_blocks = req_array(map, "current_blocks")?;
        let input = CommitGroupsBatchInput {
            by_week: req_object_map(map, "by_week")?,
            week_start: req_str(map, "week_start")?,
            current_blocks,
            current_revision: req(map, "current_revision")?,
            fetched: req_object_map(map, "fetched")?,
            today_iso: req_str(map, "today_iso")?,
            label: req_str(map, "label")?,
            snapshot_label: opt_str(map, "snapshot_label")?,
            operation_id: req_str(map, "operation_id")?,
            said: opt_str(map, "said")?,
        };
        let decision = commit_groups_batch(&input).map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

#[pyfunction]
fn session_copy_block_skipped(signed_in: bool) -> PyResult<bool> {
    guard(|| Ok(copy_block_skipped(signed_in)))
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        fixed_copy_rows_json,
        copy_empty_words_json,
        date_problem_json,
        relocate_json,
        clipboard_block_json,
        paste_destination_json,
        clipboard_day_json,
        paste_ready_json,
        preview_groups_json,
        session_previous_week_for_copy,
        session_block_on_week,
        session_resolve_date_span,
        session_prepare_move_to_date,
        session_move_to_date_needed,
        session_build_move_to_date_batch,
        session_copy_selected,
        session_copy_day,
        session_paste_proposals_prepare,
        session_paste_proposals_build,
        session_duplicate_selected_prepare,
        session_confirm_preview_plan,
        session_commit_groups_order,
        session_commit_groups_batch,
        session_copy_block_skipped,
    );
    Ok(())
}
