//! The session's clipboard, copy rows and relocation decisions
//! (`flexweek_app::session::copies`) for the Python window, with JSON text across. The window keeps
//! the state: it reads the clock, fetches weeks, draws ids, looks assignments up, and writes what
//! is decided here.

use flexweek_app::session::copies::{
    ClipboardBlock, CopyDay, DateProblemInput, PasteReady, PasteSelection, PreviewGroups,
    Relocation, RelocationInput, clipboard_block, copy_day_items, copy_empty_words, date_problem,
    fixed_copy_rows, paste_destination, paste_ready, preview_groups, relocate,
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
        let block = read(block)?;
        let block = (!block.is_null()).then_some(block);
        let assignments = read(assignments)?;
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
        let dest = read(dest)?;
        let dest = (!dest.is_null()).then_some(dest);
        if let Some(dest) = dest.as_ref()
            && !dest.is_object()
        {
            return Err(PyTypeError::new_err("the destination week is an object"));
        }
        let assignments = read(assignments)?;
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
        let blocks = read(blocks)?;
        let trace = read(trace)?;
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
        let blocks = read(blocks)?;
        let trace = read(trace)?;
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
        let clipboard = read(clipboard)?;
        let clipboard = (!clipboard.is_null()).then_some(clipboard);
        let blocks = read(blocks)?;
        let trace = read(trace)?;
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
        preview_groups_json
    );
    Ok(())
}
