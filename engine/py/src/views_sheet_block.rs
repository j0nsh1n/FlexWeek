//! Block sheet and paste preview for the Python window. JSON text crosses for the sheet state.
//! Each exported function only calls `guard`.

use flexweek_app::views::sheet_block::{BlockDraft, SheetClock};
use flexweek_app::views::sheet_preview::{self, PreviewDraft};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde_json::Value;

use crate::{guard, raise};

fn parse_json(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn dump(value: &Value) -> PyResult<String> {
    serde_json::to_string(value).map_err(|error| PyValueError::new_err(format!("json: {error}")))
}

fn clock_of(text: &str) -> PyResult<SheetClock> {
    let value = parse_json(text, "clock")?;
    SheetClock::from_value(&value).map_err(raise)
}

fn draft_of(text: &str) -> PyResult<BlockDraft> {
    let value = parse_json(text, "state")?;
    BlockDraft::from_value(&value).map_err(raise)
}

fn state_of(draft: &BlockDraft) -> PyResult<String> {
    dump(&draft.to_value())
}

fn preview_of(text: &str) -> PyResult<PreviewDraft> {
    let value = parse_json(text, "state")?;
    PreviewDraft::from_value(&value).map_err(raise)
}

fn preview_state(draft: &PreviewDraft) -> PyResult<String> {
    dump(&draft.to_value())
}

fn days_of(text: &str) -> PyResult<Vec<Value>> {
    match parse_json(text, "days")? {
        Value::Array(items) => Ok(items),
        _ => Err(PyValueError::new_err("days must be a list")),
    }
}

#[pyfunction]
fn block_draft_open(spec: &str, clock: &str) -> PyResult<String> {
    guard(|| {
        let spec = parse_json(spec, "spec")?;
        let clock = clock_of(clock)?;
        state_of(&BlockDraft::open(&spec, &clock).map_err(raise)?)
    })
}

#[pyfunction]
fn block_draft_set(state: &str, name: &str, value: &str) -> PyResult<String> {
    guard(|| {
        let mut draft = draft_of(state)?;
        let value = parse_json(value, "value")?;
        draft.set(name, &value).map_err(raise)?;
        state_of(&draft)
    })
}

#[pyfunction]
fn block_draft_toggle_day(state: &str, day: &str) -> PyResult<String> {
    guard(|| {
        let mut draft = draft_of(state)?;
        let day = parse_json(day, "day")?;
        draft.toggle_day(&day).map_err(raise)?;
        state_of(&draft)
    })
}

#[pyfunction]
fn block_draft_use_picked(state: &str, day: i64, start: &str, length: i64) -> PyResult<String> {
    guard(|| {
        let mut draft = draft_of(state)?;
        draft.use_picked(day, start, length).map_err(raise)?;
        state_of(&draft)
    })
}

#[pyfunction]
fn block_draft_follow_week(state: &str, fresh_days: &str, clock: &str) -> PyResult<String> {
    guard(|| {
        let mut draft = draft_of(state)?;
        let fresh_days = days_of(fresh_days)?;
        let clock = clock_of(clock)?;
        draft.follow_week(&fresh_days, &clock).map_err(raise)?;
        state_of(&draft)
    })
}

#[pyfunction]
fn block_draft_back(state: &str) -> PyResult<String> {
    guard(|| {
        let mut draft = draft_of(state)?;
        draft.back();
        state_of(&draft)
    })
}

#[pyfunction]
fn block_draft_goto(state: &str, index: i64) -> PyResult<String> {
    guard(|| {
        let mut draft = draft_of(state)?;
        draft.goto(index);
        state_of(&draft)
    })
}

#[pyfunction]
fn block_draft_advance(state: &str, clock: &str) -> PyResult<(String, bool)> {
    guard(|| {
        let mut draft = draft_of(state)?;
        let clock = clock_of(clock)?;
        let done = draft.advance(&clock).map_err(raise)?;
        Ok((state_of(&draft)?, done))
    })
}

#[pyfunction]
fn block_draft_candidate(state: &str, clock: &str) -> PyResult<(String, String)> {
    guard(|| {
        let mut draft = draft_of(state)?;
        let clock = clock_of(clock)?;
        let made = draft.candidate(&clock).map_err(raise)?;
        let made = match made {
            Some(value) => dump(&value)?,
            None => "null".to_string(),
        };
        Ok((state_of(&draft)?, made))
    })
}

#[pyfunction]
fn block_draft_clash(state: &str, blocks: &str) -> PyResult<String> {
    guard(|| {
        let draft = draft_of(state)?;
        let blocks = parse_json(blocks, "blocks")?;
        draft.clash(&blocks).map_err(raise)
    })
}

#[pyfunction]
fn block_draft_form(state: &str, clock: &str) -> PyResult<String> {
    guard(|| {
        let draft = draft_of(state)?;
        let clock = clock_of(clock)?;
        dump(&draft.form(&clock).map_err(raise)?)
    })
}

#[pyfunction]
fn block_draft_save_plan(state: &str, made: &str, clock: &str, fresh_id: &str) -> PyResult<String> {
    guard(|| {
        let draft = draft_of(state)?;
        let made = parse_json(made, "made")?;
        let clock = clock_of(clock)?;
        dump(&draft.save_plan(&made, &clock, fresh_id).map_err(raise)?)
    })
}

#[pyfunction]
fn block_draft_stopped_one_off(state: &str, made: &str) -> PyResult<String> {
    guard(|| {
        let draft = draft_of(state)?;
        let made = parse_json(made, "made")?;
        match draft.stopped_one_off(&made).map_err(raise)? {
            Some(value) => dump(&value),
            None => Ok("null".to_string()),
        }
    })
}

#[pyfunction]
fn block_draft_recover_missed(state: &str) -> PyResult<bool> {
    guard(|| {
        let draft = draft_of(state)?;
        draft.recover_missed().map_err(raise)
    })
}

#[pyfunction]
fn block_draft_delete_question(state: &str, clock: &str) -> PyResult<String> {
    guard(|| {
        let draft = draft_of(state)?;
        let clock = clock_of(clock)?;
        dump(&draft.delete_question(&clock).map_err(raise)?)
    })
}

#[pyfunction]
fn block_draft_save_question(state: &str) -> PyResult<String> {
    guard(|| {
        let draft = draft_of(state)?;
        dump(&draft.save_question().map_err(raise)?)
    })
}

#[pyfunction]
fn block_draft_dirty(state: &str) -> PyResult<bool> {
    guard(|| {
        let draft = draft_of(state)?;
        Ok(draft.dirty())
    })
}

#[pyfunction]
fn preview_draft_open(spec: &str) -> PyResult<String> {
    guard(|| {
        let spec = parse_json(spec, "spec")?;
        preview_state(&PreviewDraft::open(&spec).map_err(raise)?)
    })
}

#[pyfunction]
fn preview_draft_can_save(state: &str) -> PyResult<bool> {
    guard(|| {
        let draft = preview_of(state)?;
        Ok(draft.can_save())
    })
}

#[pyfunction]
fn preview_draft_check(state: &str, index: i64, checked: bool) -> PyResult<String> {
    guard(|| {
        let mut draft = preview_of(state)?;
        draft.check(index, checked).map_err(raise)?;
        preview_state(&draft)
    })
}

#[pyfunction]
fn preview_draft_set_day(state: &str, index: i64, day: i64, existing: &str) -> PyResult<String> {
    guard(|| {
        let mut draft = preview_of(state)?;
        let existing = parse_json(existing, "existing")?;
        draft.set_day(index, day, &existing).map_err(raise)?;
        preview_state(&draft)
    })
}

#[pyfunction]
fn preview_draft_set_start(
    state: &str,
    index: i64,
    start: &str,
    existing: &str,
) -> PyResult<String> {
    guard(|| {
        let mut draft = preview_of(state)?;
        let existing = parse_json(existing, "existing")?;
        draft.set_start(index, start, &existing).map_err(raise)?;
        preview_state(&draft)
    })
}

#[pyfunction]
fn preview_draft_set_duration(
    state: &str,
    index: i64,
    minutes: &str,
    existing: &str,
) -> PyResult<String> {
    guard(|| {
        let mut draft = preview_of(state)?;
        let minutes = parse_json(minutes, "minutes")?;
        let existing = parse_json(existing, "existing")?;
        draft
            .set_duration(index, &minutes, &existing)
            .map_err(raise)?;
        preview_state(&draft)
    })
}

#[pyfunction]
fn preview_draft_form(state: &str, existing: &str) -> PyResult<(String, String)> {
    guard(|| {
        let mut draft = preview_of(state)?;
        let existing = parse_json(existing, "existing")?;
        let form = dump(&draft.form(&existing).map_err(raise)?)?;
        Ok((preview_state(&draft)?, form))
    })
}

#[pyfunction]
fn preview_beside_words(clash: &str) -> PyResult<String> {
    guard(|| Ok(sheet_preview::beside_words(clash)))
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        block_draft_open,
        block_draft_set,
        block_draft_toggle_day,
        block_draft_use_picked,
        block_draft_follow_week,
        block_draft_back,
        block_draft_goto,
        block_draft_advance,
        block_draft_candidate,
        block_draft_clash,
        block_draft_form,
        block_draft_save_plan,
        block_draft_stopped_one_off,
        block_draft_recover_missed,
        block_draft_delete_question,
        block_draft_save_question,
        block_draft_dirty,
        preview_draft_open,
        preview_draft_can_save,
        preview_draft_check,
        preview_draft_set_day,
        preview_draft_set_start,
        preview_draft_set_duration,
        preview_draft_form,
        preview_beside_words,
    );
    Ok(())
}
