//! Python bindings for the Material Day and My day view-model (`flexweek_app::views::day`).
//!
//! Every exported function and method body runs inside `guard(` and refuses wrong-shaped
//! inputs with `ValueError` or `TypeError`.

use std::cell::RefCell;
use std::collections::HashSet;
use std::sync::{Mutex, MutexGuard};

use flexweek_app::views::day::{
    self, BeginInput, BoardInput, DIM_KEYS, DayItem, DayView, FinishInput, FocusHooks, NUDGE_KEYS,
    TimerWords, WeekLookups,
};
use flexweek_app::views::week::OccurrenceInput;
use flexweek_engine::{EngineError, EngineResult};
use pyo3::exceptions::{PyRuntimeError, PyTypeError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyModule, PyString};
use serde_json::{Map, Value, json};

use crate::{guard, raise};

const MINUTE_STAMP: &str = "%Y-%m-%dT%H:%M";

fn parse_state(text: &str) -> PyResult<Value> {
    serde_json::from_str(text)
        .map_err(|error| PyTypeError::new_err(format!("focus state: {error}")))
}

// A text value, or None for anything that is not text.
fn text_of(value: &Bound<'_, PyAny>) -> PyResult<Option<String>> {
    if value.is_instance_of::<PyString>() {
        return Ok(Some(value.extract::<String>()?));
    }
    Ok(None)
}

// `str(value or "")`: nothing and empty things read as an empty string.
fn text_or_empty(value: &Bound<'_, PyAny>) -> PyResult<String> {
    if value.is_none() || !value.is_truthy()? {
        return Ok(String::new());
    }
    value.str()?.extract()
}

fn text_or_none(value: &Bound<'_, PyAny>, what: &str) -> PyResult<Option<String>> {
    if value.is_none() {
        return Ok(None);
    }
    text_of(value)?
        .map(Some)
        .ok_or_else(|| PyTypeError::new_err(format!("{what} must be a string or None")))
}

fn read_item(item: &Bound<'_, PyAny>) -> PyResult<DayItem> {
    let slack = if item.hasattr("slack")? {
        text_or_none(&item.getattr("slack")?, "slack")?
    } else {
        None
    };
    Ok(DayItem {
        base: OccurrenceInput {
            block_id: item.getattr("block_id")?.str()?.extract()?,
            title: item.getattr("title")?.str()?.extract()?,
            category: text_or_empty(&item.getattr("category")?)?,
            day: item.getattr("day")?.extract()?,
            start: item.getattr("start")?.extract()?,
            end: item.getattr("end")?.extract()?,
            work: item.getattr("work")?.is_truthy()?,
            done: item.getattr("done")?.is_truthy()?,
            assignment_id: text_or_empty(&item.getattr("assignment_id")?)?,
        },
        missed: item.getattr("missed")?.is_truthy()?,
        pinned: item.getattr("pinned")?.is_truthy()?,
        due: text_or_none(&item.getattr("due")?, "due")?,
        slack,
    })
}

fn read_items(items: &Bound<'_, PyAny>) -> PyResult<Vec<DayItem>> {
    let mut found = Vec::new();
    for item in items.try_iter()? {
        found.push(read_item(&item?)?);
    }
    Ok(found)
}

fn read_missed(missed: &Bound<'_, PyAny>) -> PyResult<HashSet<String>> {
    let mut found = HashSet::new();
    for id in missed.try_iter()? {
        found.insert(id?.extract::<String>()?);
    }
    Ok(found)
}

// The preferences Day reads: the clock's truth, and the switches only when they are real booleans.
fn read_prefs(prefs: &Bound<'_, PyAny>) -> PyResult<Value> {
    if prefs.is_none() {
        return Ok(Value::Object(Map::new()));
    }
    let dict = prefs
        .cast::<PyDict>()
        .map_err(|_| PyTypeError::new_err("preferences must be a dict or None"))?;
    let mut map = Map::new();
    if let Some(value) = dict.get_item("clock_24h")? {
        map.insert("clock_24h".to_string(), Value::Bool(value.is_truthy()?));
    }
    for key in DIM_KEYS.iter().chain(NUDGE_KEYS.iter()) {
        if let Some(value) = dict.get_item(key)?
            && value.is_instance_of::<PyBool>()
        {
            map.insert((*key).to_string(), Value::Bool(value.extract()?));
        }
    }
    Ok(Value::Object(map))
}

fn minute_stamp(moment: &Bound<'_, PyAny>) -> PyResult<String> {
    moment.call_method1("strftime", (MINUTE_STAMP,))?.extract()
}

fn homework_done(state: &Value, assignments: Option<&Bound<'_, PyAny>>) -> PyResult<Option<bool>> {
    let Some(assignments) = assignments.filter(|found| !found.is_none()) else {
        return Ok(None);
    };
    let Some(id) = state.get("assignmentId").and_then(Value::as_str) else {
        return Ok(None);
    };
    let dict = assignments
        .cast::<PyDict>()
        .map_err(|_| PyTypeError::new_err("assignments must be a dict or None"))?;
    let Some(item) = dict.get_item(id)?.filter(|found| !found.is_none()) else {
        return Ok(None);
    };
    let item = item
        .cast::<PyDict>()
        .map_err(|_| PyTypeError::new_err("an assignment must be a dict"))?;
    Ok(Some(match item.get_item("completed")? {
        Some(done) => done.is_truthy()?,
        None => false,
    }))
}

fn timer_of(
    focus_json: &str,
    now_ms: i64,
    assignments: Option<&Bound<'_, PyAny>>,
) -> PyResult<TimerWords> {
    let state = parse_state(focus_json)?;
    let done = homework_done(&state, assignments)?;
    day::timer_words(&state, now_ms, done).map_err(raise)
}

// The week model's answers, asked only when the rule needs them. A Python error is kept and raised
// as it was, instead of the placeholder the Rust trait can carry.
struct PyWeek<'a, 'py> {
    week: &'a Bound<'py, PyAny>,
    failed: RefCell<Option<PyErr>>,
}

impl PyWeek<'_, '_> {
    fn keep<T>(&self, found: PyResult<T>) -> EngineResult<T> {
        found.map_err(|error| {
            *self.failed.borrow_mut() = Some(error);
            EngineError::value("the week model failed")
        })
    }
}

impl WeekLookups for PyWeek<'_, '_> {
    fn has_unplaced_api(&self) -> bool {
        self.week.hasattr("due_today_unplaced").unwrap_or(false)
    }

    fn unplaced_count(&self, day: i64) -> EngineResult<usize> {
        let waiting = self.keep(self.week.call_method1("due_today_unplaced", (day,)))?;
        self.keep(waiting.len())
    }

    fn leftover_kind(&self, day: i64) -> EngineResult<String> {
        let kind = self.keep(self.week.call_method1("leftover_kind", (day,)))?;
        self.keep(kind.extract())
    }

    fn leftover_title_line(&self, day: i64) -> EngineResult<(String, String)> {
        let parts = self.keep(self.week.call_method1("leftover_parts", (day,)))?;
        let (_kicker, title, line): (String, String, String) = self.keep(parts.extract())?;
        Ok((title, line))
    }
}

#[pyfunction]
fn views_day_read_flag(
    prefs: &Bound<'_, PyAny>,
    keys: Vec<String>,
    default: bool,
) -> PyResult<bool> {
    guard(|| {
        if prefs.is_none() {
            return Ok(default);
        }
        let Ok(dict) = prefs.cast::<PyDict>() else {
            return Ok(default);
        };
        let mut map = Map::new();
        for key in &keys {
            if let Some(value) = dict.get_item(key)?
                && value.is_instance_of::<PyBool>()
            {
                map.insert(key.clone(), Value::Bool(value.extract()?));
            }
        }
        let names: Vec<&str> = keys.iter().map(String::as_str).collect();
        Ok(day::read_flag(&Value::Object(map), &names, default))
    })
}

// Up next, Done, the Now card and the ring for one day, as JSON with the board's field names.
#[pyfunction]
#[pyo3(signature = (items, minute, when, nudges, dim, mode, on, now, missed, unplaced, unplaced_words))]
#[allow(clippy::too_many_arguments)]
fn views_day_board_for(
    items: &Bound<'_, PyAny>,
    minute: i64,
    when: &str,
    nudges: bool,
    dim: bool,
    mode: &str,
    on: &Bound<'_, PyAny>,
    now: Option<&Bound<'_, PyAny>>,
    missed: &Bound<'_, PyAny>,
    unplaced: i64,
    unplaced_words: Option<(String, String)>,
) -> PyResult<String> {
    guard(|| {
        let found = read_items(items)?;
        let missed_ids = read_missed(missed)?;
        let on_iso: String = on.call_method0("isoformat")?.extract()?;
        let stamp = now.map(minute_stamp).transpose()?;
        let board = day::board_for(&BoardInput {
            items: &found,
            minute,
            when,
            nudges,
            dim,
            mode,
            on: &on_iso,
            now: stamp.as_deref(),
            missed: &missed_ids,
            unplaced,
            unplaced_words: unplaced_words
                .as_ref()
                .map(|(title, line)| (title.as_str(), line.as_str())),
        })
        .map_err(raise)?;
        Ok(board.to_json().to_string())
    })
}

// What the Finish button on a Day row does: (words to say first, words to say once it is done).
#[pyfunction]
fn views_day_finish_plan(
    assignment_id: &str,
    busy: bool,
    saving: bool,
    assignments: &Bound<'_, PyAny>,
) -> PyResult<(Option<String>, Option<String>)> {
    guard(|| {
        let title = if assignments.is_none() {
            None
        } else {
            let dict = assignments
                .cast::<PyDict>()
                .map_err(|_| PyTypeError::new_err("assignments must be a dict or None"))?;
            match dict.get_item(assignment_id)?.filter(|item| !item.is_none()) {
                Some(item) => {
                    let item = item
                        .cast::<PyDict>()
                        .map_err(|_| PyTypeError::new_err("an assignment must be a dict"))?;
                    match item.get_item("title")? {
                        Some(title) => Some(text_or_empty(&title)?),
                        None => None,
                    }
                }
                None => None,
            }
        };
        let plan = day::finish_plan(assignment_id, busy, saving, title.as_deref());
        Ok((plan.say_now, plan.finished))
    })
}

// Whether the session's answer to Mark finished ("finished", "queued" or False) may have changed the card.
#[pyfunction]
fn views_day_finish_refreshes(outcome: &Bound<'_, PyAny>) -> PyResult<Option<bool>> {
    guard(|| {
        let text = text_of(outcome)?;
        Ok(day::finish_refreshes(text.as_deref()).then_some(true))
    })
}

#[pyfunction]
fn views_day_when_true(value: &Bound<'_, PyAny>) -> PyResult<Option<bool>> {
    guard(|| Ok(value.is_truthy()?.then_some(true)))
}

// Whether the session's focus state is a timer that has run out.
#[pyfunction]
fn views_day_focus_ended(focus: &Bound<'_, PyAny>) -> PyResult<Option<bool>> {
    guard(|| {
        let Ok(dict) = focus.cast::<PyDict>() else {
            return Ok(None);
        };
        let mut map = Map::new();
        if let Some(phase) = dict.get_item("phase")?
            && let Some(text) = text_of(&phase)?
        {
            map.insert("phase".to_string(), Value::String(text));
        }
        Ok(day::focus_ended(&Value::Object(map)).then_some(true))
    })
}

/// Stateful view-model backing `desktop/native/material/bridge_day.py::DayBridge`.
#[pyclass(name = "DayView", module = "flexweek_engine")]
pub struct DayViewHandle {
    state: Mutex<DayView>,
}

impl DayViewHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, DayView>> {
        self.state
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the day view failed earlier"))
    }
}

#[pymethods]
impl DayViewHandle {
    #[new]
    fn new(today_only: bool) -> PyResult<Self> {
        guard(|| {
            Ok(Self {
                state: Mutex::new(DayView::new(today_only)),
            })
        })
    }

    fn mode(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.mode().to_string()))
    }

    fn snapshot_json(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.snapshot().to_string()))
    }

    // Returns (clock is 24-hour, go on or None, week to load or None, day of the shown week or None,
    // read the week or None).
    #[pyo3(signature = (mode, prefs, today_iso, hour, minute, selected_day, signed_in, week_start, needed_week, busy, message, fetch, screen, can_load))]
    #[allow(clippy::too_many_arguments, clippy::type_complexity)]
    fn begin_reload(
        &self,
        mode: &str,
        prefs: &Bound<'_, PyAny>,
        today_iso: &str,
        hour: i64,
        minute: i64,
        selected_day: &Bound<'_, PyAny>,
        signed_in: bool,
        week_start: Option<&str>,
        needed_week: &str,
        busy: bool,
        message: Option<&str>,
        fetch: bool,
        screen: &str,
        can_load: bool,
    ) -> PyResult<(
        bool,
        Option<bool>,
        Option<String>,
        Option<i64>,
        Option<bool>,
    )> {
        guard(|| {
            let parsed = read_prefs(prefs)?;
            let selected = text_of(selected_day)?;
            let outcome = self
                .locked()?
                .begin_reload(&BeginInput {
                    mode,
                    prefs: &parsed,
                    today_iso,
                    clock_minute: hour * 60 + minute,
                    selected_day: selected.as_deref(),
                    signed_in,
                    week_start,
                    needed_week,
                    busy,
                    message,
                    fetch,
                    screen,
                    can_load,
                })
                .map_err(raise)?;
            Ok((
                outcome.clock_24h,
                outcome.proceed.then_some(true),
                outcome.load,
                outcome.day,
                outcome.read_week.then_some(true),
            ))
        })
    }

    // Returns {"board": ..., "block_rows": [...]} as JSON.
    #[allow(clippy::too_many_arguments)]
    fn finish_reload(
        &self,
        week: Option<&Bound<'_, PyAny>>,
        items: &Bound<'_, PyAny>,
        missed: &Bound<'_, PyAny>,
        prefs: &Bound<'_, PyAny>,
        focus_json: &str,
        assignments: Option<&Bound<'_, PyAny>>,
        now_ms: i64,
        moment: &Bound<'_, PyAny>,
    ) -> PyResult<String> {
        guard(|| {
            let found = read_items(items)?;
            let missed_ids = read_missed(missed)?;
            let parsed = read_prefs(prefs)?;
            let timer = timer_of(focus_json, now_ms, assignments)?;
            let stamp = minute_stamp(moment)?;
            let lookups = week.map(|model| PyWeek {
                week: model,
                failed: RefCell::new(None),
            });
            let published = self.locked()?.finish_reload(&FinishInput {
                items: &found,
                missed: &missed_ids,
                prefs: &parsed,
                timer,
                week: lookups.as_ref().map(|each| each as &dyn WeekLookups),
                now: &stamp,
            });
            if let Some(error) = lookups.and_then(|each| each.failed.take()) {
                return Err(error);
            }
            let published = published.map_err(raise)?;
            Ok(json!({
                "board": published.board.to_json(),
                "block_rows": published.block_rows,
            })
            .to_string())
        })
    }

    fn refresh_timer(
        &self,
        focus_json: &str,
        now_ms: i64,
        assignments: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Option<bool>> {
        guard(|| {
            let timer = timer_of(focus_json, now_ms, assignments)?;
            Ok(self.locked()?.refresh_timer(timer).then_some(true))
        })
    }

    fn mark_load_started(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.mark_load_started();
            Ok(())
        })
    }

    fn reset_load(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.reset_load();
            Ok(())
        })
    }

    fn today_requested(&self, has_session: bool) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.today_requested(has_session).then_some(true)))
    }

    fn set_want_today(&self, wanted: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_want_today(wanted);
            Ok(())
        })
    }

    fn after_week(&self, has_session: bool, busy: bool) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.after_week(has_session, busy).then_some(true)))
    }

    fn reopen_today(
        &self,
        screen: &str,
        selected_day: &Bound<'_, PyAny>,
        week_start: &Bound<'_, PyAny>,
        holding: &str,
        today_iso: &str,
    ) -> PyResult<Option<bool>> {
        guard(|| {
            let selected = text_of(selected_day)?;
            let started = text_of(week_start)?;
            Ok(self
                .locked()?
                .reopen_today(
                    screen,
                    selected.as_deref(),
                    started.as_deref(),
                    holding,
                    today_iso,
                )
                .then_some(true))
        })
    }

    fn on_busy(&self, busy: bool, screen: &str) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.on_busy(busy, screen).then_some(true)))
    }

    fn pick_target(&self, day: i64) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.pick_target(day)))
    }

    fn shift_target(&self, days: i64) -> PyResult<Option<String>> {
        guard(|| self.locked()?.shift_target(days).map_err(raise))
    }

    fn left_line(&self, board_line: &str) -> PyResult<String> {
        guard(|| Ok(self.locked()?.left_line(board_line)))
    }

    fn show_now(&self, board_show_now: bool) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.show_now(board_show_now)))
    }

    // Returns (call to make, block id, day): `open_focus`, `hook`, `widgets` or `session`.
    fn start_focus_plan(
        &self,
        opener: bool,
        hook: bool,
        starter: bool,
        block_id: &str,
        day: i64,
    ) -> PyResult<(String, Option<String>, Option<i64>)> {
        guard(|| {
            let plan = self.locked()?.start_focus_plan(
                &FocusHooks {
                    opener,
                    hook,
                    starter,
                },
                block_id,
                day,
            );
            Ok((plan.action.to_string(), plan.block_id, plan.day))
        })
    }
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("VIEWS_DAY_NUDGE_KEYS", NUDGE_KEYS.to_vec())?;
    module.add("VIEWS_DAY_DIM_KEYS", DIM_KEYS.to_vec())?;
    module.add_class::<DayViewHandle>()?;
    crate::export!(
        module,
        views_day_read_flag,
        views_day_board_for,
        views_day_finish_plan,
        views_day_finish_refreshes,
        views_day_when_true,
        views_day_focus_ended,
    );
    Ok(())
}
