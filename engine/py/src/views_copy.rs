//! Sheet rules, settings copy and the sign-in checks for the Python window. JSON text crosses for
//! dicts and day lists. Each exported function only calls `guard`.

use flexweek_app::views::copy::{
    self, ABOUT_HERE, ABOUT_LINE, ACCOUNT_CODES_NOTE, ACCOUNT_DATA_NOTE, ACCOUNT_PASSWORD_NOTE,
    ACCOUNT_SAVED, ALARM_NOTE, ALARM_TONE_LABELS, BLOCK_SONG_NOTE, CREATE_HEADING, CREATE_NOTE,
    DELETE_ACCOUNT_QUESTION, DND_NOTE, DOT_WORDS, DRAG_STEP_CHOICES, DRAG_STEP_QUESTION,
    FOCUS_AUDIO_NOTE, HELP_LETTER_KEYS, HELP_NUMBER_KEYS, HELP_OTHER_KEYS, HELP_PLANNING,
    HELP_PLANNING_MATERIAL, HELP_SCREENS, NO_PROTECTED, NO_SCHOOL_DAYS, NO_SOUND, NO_STUDY_HOURS,
    PAIR_CLOSED, PAIR_ONCE, PLANNING_STYLES, PROTECTED_WORDS, READ_FAILED, READ_WEEK_FAILED,
    RECOVERY_COPY, RECOVERY_FILE, RECOVERY_KEEP, RECOVERY_SAID_MS, RECOVERY_SAVE, RECOVERY_WAIT,
    RELAY_SENTENCE, REPLACE_WEEK_QUESTION, RESET_HEADING, RESET_NOTE, RESTORE_FIRST,
    SCHOOL_HOURS_NOTE, SIGN_IN_HEADING, SPLIT_ROUNDED, SPORT_FALLBACK, SPOTIFY_LINK_HINT,
    SPOTIFY_TONE_NOTE, SPOTIFY_TONE_REST, STUDY_HOURS_LINE, TRAY_NOTE, UNREACHABLE_WORDS,
    WRITE_FAILED,
};
use flexweek_app::views::sheet_rules::{
    self, BLOCK_PROBLEMS, BLOCK_REFUSED, CUTOFFS, DUE_PASSED, ESTIMATE_ERROR, ESTIMATE_LONG,
    ESTIMATE_SHORT, HOMEWORK_PROBLEMS, HOMEWORK_REFUSED, LATE_WAIT, REPEAT_NOTE, SLOT_HINT,
    SPREAD_NOTHING,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};
use serde_json::Value;

use crate::{guard, raise};

fn parse_json(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn parse_days(text: &str) -> PyResult<Vec<i64>> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("days: {error}")))
}

fn parse_moves(text: &str) -> PyResult<Vec<(String, String)>> {
    let value = parse_json(text, "moves")?;
    let Some(items) = value.as_array() else {
        return Err(PyValueError::new_err("moves must be a list"));
    };
    let mut moves = Vec::with_capacity(items.len());
    for item in items {
        let Some(pair) = item.as_array() else {
            return Err(PyValueError::new_err("a move must be a pair"));
        };
        if pair.len() != 2 {
            return Err(PyValueError::new_err("a move must be a pair"));
        }
        let old = pair[0]
            .as_str()
            .ok_or_else(|| PyValueError::new_err("a move name must be text"))?;
        let new = pair[1]
            .as_str()
            .ok_or_else(|| PyValueError::new_err("a move name must be text"))?;
        moves.push((old.to_string(), new.to_string()));
    }
    Ok(moves)
}

fn dump(value: &Value) -> PyResult<String> {
    serde_json::to_string(value).map_err(|error| PyValueError::new_err(format!("json: {error}")))
}

fn turn_pair(py: Python<'_>, kept: Vec<i64>, moved: Vec<(i64, i64)>) -> PyResult<Py<PyAny>> {
    let kept_list = PyList::new(py, kept)?;
    let mut pairs = Vec::with_capacity(moved.len());
    for (old, new) in moved {
        pairs.push(PyTuple::new(py, [old, new])?.into_any());
    }
    let moved_list = PyList::new(py, pairs)?;
    Ok(
        PyTuple::new(py, [kept_list.into_any(), moved_list.into_any()])?
            .into_any()
            .unbind(),
    )
}

fn text_rows<'py>(py: Python<'py>, rows: &[(&str, &str)]) -> PyResult<Bound<'py, PyTuple>> {
    let mut items = Vec::with_capacity(rows.len());
    for &(left, right) in rows {
        items.push(PyTuple::new(py, [left, right])?.into_any());
    }
    PyTuple::new(py, items)
}

fn text_dict<'py>(py: Python<'py>, rows: &[(&str, &str)]) -> PyResult<Bound<'py, PyDict>> {
    let mapping = PyDict::new(py);
    for &(key, words) in rows {
        mapping.set_item(key, words)?;
    }
    Ok(mapping)
}

#[pyfunction]
fn view_guess_locked_category(start: &str) -> PyResult<String> {
    guard(|| sheet_rules::guess_locked_category(start).map_err(raise))
}

#[pyfunction]
fn view_short_day_name(week_start: &str, day: i64) -> PyResult<String> {
    guard(|| sheet_rules::short_day_name(week_start, day).map_err(raise))
}

#[pyfunction]
fn view_full_day_name(week_start: &str, day: i64) -> PyResult<String> {
    guard(|| sheet_rules::full_day_name(week_start, day).map_err(raise))
}

#[pyfunction]
fn view_same_weekday(day: i64, from_week: &str, to_week: &str) -> PyResult<i64> {
    guard(|| sheet_rules::same_weekday(day, from_week, to_week).map_err(raise))
}

#[pyfunction]
fn view_turn_days_keeping_weekdays(
    py: Python<'_>,
    days_json: &str,
    from_week: &str,
    to_week: &str,
) -> PyResult<Py<PyAny>> {
    guard(|| {
        let days = parse_days(days_json)?;
        let (kept, moved) =
            sheet_rules::turn_days_keeping_weekdays(&days, from_week, to_week).map_err(raise)?;
        turn_pair(py, kept, moved)
    })
}

#[pyfunction]
fn view_first_day_changed(from_week: &str, to_week: &str) -> PyResult<bool> {
    guard(|| sheet_rules::first_day_changed(from_week, to_week).map_err(raise))
}

#[pyfunction]
fn view_moved_day_names(
    old_day: i64,
    from_week: &str,
    new_day: i64,
    to_week: &str,
) -> PyResult<(String, String)> {
    guard(|| sheet_rules::moved_day_names(old_day, from_week, new_day, to_week).map_err(raise))
}

#[pyfunction]
fn view_moved_across_months(
    old_day: i64,
    from_week: &str,
    new_day: i64,
    to_week: &str,
) -> PyResult<bool> {
    guard(|| sheet_rules::moved_across_months(old_day, from_week, new_day, to_week).map_err(raise))
}

#[pyfunction]
fn view_moved_days_note(moves_json: &str) -> PyResult<String> {
    guard(|| {
        let moves = parse_moves(moves_json)?;
        Ok(sheet_rules::moved_days_note(&moves))
    })
}

#[pyfunction]
fn view_day_range_words(days_json: &str, week_start: &str) -> PyResult<String> {
    guard(|| {
        let days = parse_days(days_json)?;
        sheet_rules::day_range_words(&days, week_start).map_err(raise)
    })
}

#[pyfunction]
fn view_day_range_and_words(days_json: &str, week_start: &str) -> PyResult<String> {
    guard(|| {
        let days = parse_days(days_json)?;
        sheet_rules::day_range_and_words(&days, week_start).map_err(raise)
    })
}

#[pyfunction]
fn view_preset_locked(text: &str) -> PyResult<String> {
    guard(|| {
        let input = parse_json(text, "preset")?;
        dump(&sheet_rules::preset_locked(&input).map_err(raise)?)
    })
}

#[pyfunction]
fn view_spread_words(sessions_json: &str, due: &str, today: &str) -> PyResult<String> {
    guard(|| {
        let sessions = parse_json(sessions_json, "sessions")?;
        sheet_rules::spread_words(&sessions, due, today).map_err(raise)
    })
}

#[pyfunction]
fn view_today_from_words(minute: i64) -> PyResult<String> {
    guard(|| Ok(sheet_rules::today_from_words(minute)))
}

#[pyfunction]
fn view_unbroken_time(text: &str) -> PyResult<String> {
    guard(|| Ok(sheet_rules::unbroken_time(text)))
}

#[pyfunction]
fn view_late_summary(moved: i64) -> PyResult<String> {
    guard(|| Ok(sheet_rules::late_summary(moved)))
}

#[pyfunction]
fn view_late_move(
    move_json: &str,
    block_json: &str,
    title: &str,
    week_start: &str,
) -> PyResult<String> {
    guard(|| {
        let move_value = parse_json(move_json, "move")?;
        let block = parse_json(block_json, "block")?;
        sheet_rules::late_move(&move_value, &block, title, week_start).map_err(raise)
    })
}

#[pyfunction]
fn view_ring_days(days_json: &str) -> PyResult<String> {
    guard(|| {
        let days = parse_days(days_json)?;
        copy::ring_days(&days).map_err(raise)
    })
}

#[pyfunction]
#[pyo3(signature = (numbers, letters, *, material = false))]
fn view_help_keys(
    numbers: bool,
    letters: bool,
    material: bool,
) -> PyResult<Vec<(&'static str, &'static str)>> {
    guard(|| Ok(copy::help_keys(numbers, letters, material)))
}

#[pyfunction]
fn view_keys_words(marked: &str) -> PyResult<String> {
    guard(|| Ok(copy::keys_words(marked)))
}

#[pyfunction]
#[pyo3(signature = (notes, limit = 6))]
fn view_first_lines(notes: &str, limit: i64) -> PyResult<String> {
    guard(|| Ok(copy::first_lines(notes, limit)))
}

#[pyfunction]
fn view_key_parts(marked: &str) -> PyResult<Vec<(String, bool)>> {
    guard(|| Ok(copy::key_parts(marked)))
}

#[pyfunction]
fn view_recovery_status(remaining_json: &str) -> PyResult<String> {
    guard(|| {
        let remaining = parse_json(remaining_json, "remaining")?;
        Ok(copy::recovery_status(&remaining))
    })
}

#[pyfunction]
fn view_restore_parts(point_json: &str) -> PyResult<(String, String)> {
    guard(|| {
        let point = parse_json(point_json, "point")?;
        copy::restore_parts(&point).map_err(raise)
    })
}

#[pyfunction]
fn view_restore_row(point_json: &str) -> PyResult<String> {
    guard(|| {
        let point = parse_json(point_json, "point")?;
        copy::restore_row(&point).map_err(raise)
    })
}

#[pyfunction]
fn view_restore_summary(preview_json: &str) -> PyResult<String> {
    guard(|| {
        let preview = parse_json(preview_json, "preview")?;
        copy::restore_summary(&preview).map_err(raise)
    })
}

#[pyfunction]
fn view_transfer_summary(preview_json: &str) -> PyResult<String> {
    guard(|| {
        let preview = parse_json(preview_json, "preview")?;
        copy::transfer_summary(&preview).map_err(raise)
    })
}

#[pyfunction]
fn view_seen_words(last_seen_ms: Option<String>, now_ms: i64, weekday: &str) -> PyResult<String> {
    guard(|| copy::seen_words(last_seen_ms.as_deref(), now_ms, weekday).map_err(raise))
}

#[pyfunction]
fn view_clock_warning_words(count: i64) -> PyResult<String> {
    guard(|| Ok(copy::clock_warning_words(count)))
}

#[pyfunction]
fn view_sync_state(status_json: &str, linked: bool) -> PyResult<String> {
    guard(|| {
        let status = parse_json(status_json, "status")?;
        copy::sync_state(&status, linked).map_err(raise)
    })
}

#[pyfunction]
fn view_countdown_words(seconds: i64) -> PyResult<String> {
    guard(|| Ok(copy::countdown_words(seconds)))
}

#[pyfunction]
fn view_tries_words(tries: i64) -> PyResult<String> {
    guard(|| Ok(copy::tries_words(tries)))
}

#[pyfunction]
fn view_pair_problem(state: &str) -> PyResult<String> {
    guard(|| Ok(copy::pair_problem(state)))
}

#[pyfunction]
fn view_username_ok(name: &str) -> PyResult<bool> {
    guard(|| Ok(copy::username_ok(name)))
}

#[pyfunction]
fn view_sign_in_problem(name: &str, password: &str) -> PyResult<String> {
    guard(|| copy::sign_in_problem(name, password).map_err(raise))
}

#[pyfunction]
fn view_sign_up_problem(name: &str, password: &str) -> PyResult<String> {
    guard(|| copy::sign_up_problem(name, password).map_err(raise))
}

#[pyfunction]
fn view_short_password_needed(n: i64) -> PyResult<String> {
    guard(|| Ok(copy::short_password_needed(n)))
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = module.py();
    module.add("VIEW_SPREAD_NOTHING", SPREAD_NOTHING)?;
    module.add("VIEW_SLOT_HINT", SLOT_HINT)?;
    module.add("VIEW_DUE_PASSED", DUE_PASSED)?;
    module.add("VIEW_ESTIMATE_ERROR", ESTIMATE_ERROR)?;
    module.add("VIEW_ESTIMATE_SHORT", ESTIMATE_SHORT)?;
    module.add("VIEW_ESTIMATE_LONG", ESTIMATE_LONG)?;
    module.add("VIEW_HOMEWORK_REFUSED", HOMEWORK_REFUSED)?;
    module.add("VIEW_REPEAT_NOTE", REPEAT_NOTE)?;
    module.add("VIEW_LATE_WAIT", LATE_WAIT)?;
    module.add("VIEW_BLOCK_REFUSED", BLOCK_REFUSED)?;
    module.add("VIEW_HOMEWORK_PROBLEMS", text_dict(py, HOMEWORK_PROBLEMS)?)?;
    module.add("VIEW_BLOCK_PROBLEMS", text_dict(py, BLOCK_PROBLEMS)?)?;
    module.add("VIEW_CUTOFFS", PyTuple::new(py, CUTOFFS)?)?;
    module.add("VIEW_RECOVERY_KEEP", RECOVERY_KEEP)?;
    module.add("VIEW_RECOVERY_WAIT", RECOVERY_WAIT)?;
    module.add("VIEW_SIGN_IN_HEADING", SIGN_IN_HEADING)?;
    module.add("VIEW_CREATE_HEADING", CREATE_HEADING)?;
    module.add("VIEW_CREATE_NOTE", CREATE_NOTE)?;
    module.add("VIEW_RESET_HEADING", RESET_HEADING)?;
    module.add("VIEW_RESET_NOTE", RESET_NOTE)?;
    module.add("VIEW_RECOVERY_COPY", RECOVERY_COPY)?;
    module.add("VIEW_RECOVERY_SAVE", RECOVERY_SAVE)?;
    module.add("VIEW_RECOVERY_FILE", RECOVERY_FILE)?;
    module.add("VIEW_RECOVERY_SAID_MS", RECOVERY_SAID_MS)?;
    module.add("VIEW_READ_FAILED", READ_FAILED)?;
    module.add("VIEW_READ_WEEK_FAILED", READ_WEEK_FAILED)?;
    module.add("VIEW_WRITE_FAILED", WRITE_FAILED)?;
    module.add("VIEW_ACCOUNT_SAVED", ACCOUNT_SAVED)?;
    module.add("VIEW_REPLACE_WEEK_QUESTION", REPLACE_WEEK_QUESTION)?;
    module.add("VIEW_DELETE_ACCOUNT_QUESTION", DELETE_ACCOUNT_QUESTION)?;
    module.add("VIEW_SPORT_FALLBACK", SPORT_FALLBACK)?;
    module.add("VIEW_ALARM_NOTE", ALARM_NOTE)?;
    module.add("VIEW_DRAG_STEP_QUESTION", DRAG_STEP_QUESTION)?;
    module.add("VIEW_ALARM_TONE_LABELS", text_dict(py, ALARM_TONE_LABELS)?)?;
    module.add("VIEW_PROTECTED_WORDS", text_dict(py, PROTECTED_WORDS)?)?;
    module.add("VIEW_DOT_WORDS", text_dict(py, DOT_WORDS)?)?;
    let mut steps = Vec::with_capacity(DRAG_STEP_CHOICES.len());
    for (minutes, label) in DRAG_STEP_CHOICES {
        let row = PyTuple::new(
            py,
            [
                minutes.into_pyobject(py)?.into_any(),
                label.into_pyobject(py)?.into_any(),
            ],
        )?;
        steps.push(row.into_any());
    }
    module.add("VIEW_DRAG_STEP_CHOICES", PyTuple::new(py, steps)?)?;
    let mut styles = Vec::with_capacity(PLANNING_STYLES.len());
    for (value, label, note) in PLANNING_STYLES {
        styles.push(PyTuple::new(py, [value, label, note])?.into_any());
    }
    module.add("VIEW_PLANNING_STYLES", PyTuple::new(py, styles)?)?;
    module.add("VIEW_SPOTIFY_LINK_HINT", SPOTIFY_LINK_HINT)?;
    module.add("VIEW_SPOTIFY_TONE_REST", SPOTIFY_TONE_REST)?;
    module.add("VIEW_SPOTIFY_TONE_NOTE", SPOTIFY_TONE_NOTE)?;
    module.add("VIEW_STUDY_HOURS_LINE", STUDY_HOURS_LINE)?;
    module.add("VIEW_SCHOOL_HOURS_NOTE", SCHOOL_HOURS_NOTE)?;
    module.add("VIEW_NO_SCHOOL_DAYS", NO_SCHOOL_DAYS)?;
    module.add("VIEW_NO_STUDY_HOURS", NO_STUDY_HOURS)?;
    module.add("VIEW_NO_PROTECTED", NO_PROTECTED)?;
    module.add("VIEW_DND_NOTE", DND_NOTE)?;
    module.add("VIEW_TRAY_NOTE", TRAY_NOTE)?;
    module.add("VIEW_BLOCK_SONG_NOTE", BLOCK_SONG_NOTE)?;
    module.add("VIEW_FOCUS_AUDIO_NOTE", FOCUS_AUDIO_NOTE)?;
    module.add("VIEW_NO_SOUND", NO_SOUND)?;
    module.add("VIEW_SPLIT_ROUNDED", SPLIT_ROUNDED)?;
    module.add("VIEW_ABOUT_LINE", ABOUT_LINE)?;
    module.add("VIEW_ABOUT_HERE", ABOUT_HERE)?;
    module.add("VIEW_HELP_SCREENS", text_rows(py, &HELP_SCREENS)?)?;
    module.add("VIEW_HELP_PLANNING", HELP_PLANNING)?;
    module.add("VIEW_HELP_PLANNING_MATERIAL", HELP_PLANNING_MATERIAL)?;
    module.add("VIEW_HELP_NUMBER_KEYS", text_rows(py, HELP_NUMBER_KEYS)?)?;
    module.add("VIEW_HELP_LETTER_KEYS", text_rows(py, HELP_LETTER_KEYS)?)?;
    module.add("VIEW_HELP_OTHER_KEYS", text_rows(py, HELP_OTHER_KEYS)?)?;
    let mut help_keys = Vec::new();
    help_keys.extend_from_slice(HELP_NUMBER_KEYS);
    help_keys.extend_from_slice(HELP_LETTER_KEYS);
    help_keys.extend_from_slice(HELP_OTHER_KEYS);
    module.add("VIEW_HELP_KEYS", text_rows(py, &help_keys)?)?;
    module.add("VIEW_ACCOUNT_PASSWORD_NOTE", ACCOUNT_PASSWORD_NOTE)?;
    module.add("VIEW_ACCOUNT_CODES_NOTE", ACCOUNT_CODES_NOTE)?;
    module.add("VIEW_ACCOUNT_DATA_NOTE", ACCOUNT_DATA_NOTE)?;
    module.add("VIEW_RESTORE_FIRST", RESTORE_FIRST)?;
    module.add("VIEW_RELAY_SENTENCE", RELAY_SENTENCE)?;
    module.add("VIEW_UNREACHABLE_WORDS", UNREACHABLE_WORDS)?;
    module.add("VIEW_PAIR_ONCE", PAIR_ONCE)?;
    module.add("VIEW_PAIR_CLOSED", PAIR_CLOSED)?;
    crate::export!(
        module,
        view_guess_locked_category,
        view_short_day_name,
        view_full_day_name,
        view_same_weekday,
        view_turn_days_keeping_weekdays,
        view_first_day_changed,
        view_moved_day_names,
        view_moved_across_months,
        view_moved_days_note,
        view_day_range_words,
        view_day_range_and_words,
        view_preset_locked,
        view_spread_words,
        view_today_from_words,
        view_unbroken_time,
        view_late_summary,
        view_late_move,
        view_ring_days,
        view_help_keys,
        view_keys_words,
        view_first_lines,
        view_key_parts,
        view_recovery_status,
        view_restore_parts,
        view_restore_row,
        view_restore_summary,
        view_transfer_summary,
        view_seen_words,
        view_clock_warning_words,
        view_sync_state,
        view_countdown_words,
        view_tries_words,
        view_pair_problem,
        view_username_ok,
        view_sign_in_problem,
        view_sign_up_problem,
        view_short_password_needed,
    );
    Ok(())
}
