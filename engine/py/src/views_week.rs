//! Python bindings for the Material Week view-model (`flexweek_app::views::week`).
//!
//! Every exported function and method body runs inside `guard(` and refuses wrong-shaped
//! inputs with `ValueError` or `TypeError`.

use std::collections::HashSet;
use std::sync::{Mutex, MutexGuard};

use flexweek_app::views::week::{
    self, OccurrenceInput, ReloadInput, UncoveredInput, WaitingInput, WeekView,
};
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyInt, PyModule, PyString};
use serde_json::{Map, Value};

use crate::{guard, raise};

fn parse_json(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn parse_array(text: &str, what: &str) -> PyResult<Vec<Value>> {
    let parsed = parse_json(text, what)?;
    match parsed {
        Value::Array(items) => Ok(items),
        _ => Err(PyValueError::new_err(format!("{what} must be a JSON list"))),
    }
}

fn parse_object_or_null(text: &str, what: &str) -> PyResult<Value> {
    let parsed = parse_json(text, what)?;
    match parsed {
        Value::Object(_) | Value::Null => Ok(parsed),
        _ => Err(PyValueError::new_err(format!(
            "{what} must be a JSON object or null"
        ))),
    }
}

fn py_opt_string(value: &Bound<'_, PyAny>) -> PyResult<Option<String>> {
    if value.is_none() {
        return Ok(None);
    }
    if value.is_instance_of::<PyString>() {
        return Ok(Some(value.extract::<String>()?));
    }
    if !value.is_truthy()? {
        return Ok(None);
    }
    Ok(Some(value.str()?.extract::<String>()?))
}

fn read_occurrence(item: &Bound<'_, PyAny>) -> PyResult<OccurrenceInput> {
    let assignment = item.getattr("assignment_id")?;
    let assignment_id = if assignment.is_none() {
        String::new()
    } else if assignment.is_instance_of::<PyString>() {
        assignment.extract::<String>()?
    } else if !assignment.is_truthy()? {
        String::new()
    } else {
        return Err(PyTypeError::new_err(
            "assignment_id must be a string or None",
        ));
    };
    Ok(OccurrenceInput {
        block_id: item.getattr("block_id")?.extract()?,
        title: item.getattr("title")?.extract()?,
        category: item.getattr("category")?.extract()?,
        day: item.getattr("day")?.extract()?,
        start: item.getattr("start")?.extract()?,
        end: item.getattr("end")?.extract()?,
        work: item.getattr("work")?.is_truthy()?,
        done: item.getattr("done")?.is_truthy()?,
        assignment_id,
    })
}

fn read_waiting(item: &Bound<'_, PyAny>) -> PyResult<WaitingInput> {
    let assignment = item.getattr("assignment_id")?;
    let assignment_id = if assignment.is_none() {
        String::new()
    } else if assignment.is_instance_of::<PyString>() {
        assignment.extract::<String>()?
    } else if !assignment.is_truthy()? {
        String::new()
    } else {
        return Err(PyTypeError::new_err(
            "assignment_id must be a string or None",
        ));
    };
    Ok(WaitingInput {
        block_id: item.getattr("block_id")?.extract()?,
        title: item.getattr("title")?.extract()?,
        minutes: item.getattr("minutes")?.extract()?,
        assignment_id,
        due: py_opt_string(&item.getattr("due")?)?,
        reason: item.getattr("reason")?.extract()?,
    })
}

fn read_uncovered(items: &Bound<'_, PyAny>) -> PyResult<Vec<UncoveredInput>> {
    let mut out = Vec::new();
    for entry in items.try_iter()? {
        let entry = entry?;
        let parts: Vec<Bound<'_, PyAny>> = entry.try_iter()?.collect::<PyResult<_>>()?;
        if parts.len() != 3 {
            return Err(PyValueError::new_err(
                "each uncovered remainder must be a 3-tuple (title, minutes, assignment_id)",
            ));
        }
        let title: String = parts[0].extract()?;
        let minutes: i64 = parts[1].extract()?;
        let assignment_id = py_scalar_to_json(&parts[2])?;
        out.push(UncoveredInput {
            title,
            minutes,
            assignment_id,
        });
    }
    Ok(out)
}

fn py_scalar_to_json(value: &Bound<'_, PyAny>) -> PyResult<Value> {
    if value.is_none() {
        Ok(Value::Null)
    } else if value.is_instance_of::<PyBool>() {
        Ok(Value::Bool(value.extract()?))
    } else if value.is_instance_of::<PyInt>() {
        Ok(Value::from(value.extract::<i64>()?))
    } else if value.is_instance_of::<PyString>() {
        Ok(Value::String(value.extract()?))
    } else {
        Err(PyTypeError::new_err(
            "expected a string, integer, boolean, or None",
        ))
    }
}

fn read_reload_prefs(prefs: &Bound<'_, PyAny>) -> PyResult<Value> {
    if prefs.is_none() {
        return Ok(Value::Null);
    }
    let dict = prefs
        .cast::<PyDict>()
        .map_err(|_| PyTypeError::new_err("preferences must be a dict or None"))?;
    let mut map = Map::new();
    if let Some(value) = dict.get_item("clock_24h")? {
        map.insert("clock_24h".to_string(), Value::Bool(value.is_truthy()?));
    }
    for key in ["show_weekends", "dim_completed"] {
        if let Some(value) = dict.get_item(key)?
            && value.is_instance_of::<PyBool>()
        {
            map.insert(key.to_string(), Value::Bool(value.extract()?));
        }
    }
    if let Some(value) = dict.get_item("drag_step_min")?
        && !value.is_instance_of::<PyBool>()
        && value.is_instance_of::<PyInt>()
        && let Ok(step) = value.extract::<i64>()
    {
        map.insert("drag_step_min".to_string(), Value::from(step));
    }
    Ok(Value::Object(map))
}

#[pyfunction]
fn views_week_bool_pref(prefs: &Bound<'_, PyAny>, key: &str, default: bool) -> PyResult<bool> {
    guard(|| {
        if prefs.is_none() {
            return Ok(default);
        }
        let dict = prefs
            .cast::<PyDict>()
            .map_err(|_| PyTypeError::new_err("prefs must be a dict or None"))?;
        let mut map = Map::new();
        if let Some(value) = dict.get_item(key)?
            && value.is_instance_of::<PyBool>()
        {
            map.insert(key.to_string(), Value::Bool(value.extract()?));
        }
        Ok(week::bool_pref(&Value::Object(map), key, default))
    })
}

#[pyfunction]
#[pyo3(signature = (item, mode, dim, gone, fresh, missed = false))]
fn views_week_occurrence_row(
    item: &Bound<'_, PyAny>,
    mode: &str,
    dim: bool,
    gone: bool,
    fresh: bool,
    missed: bool,
) -> PyResult<String> {
    guard(|| {
        let input = read_occurrence(item)?;
        let row = week::occurrence_row(&input, mode, dim, gone, fresh, missed).map_err(raise)?;
        Ok(Value::Object(row).to_string())
    })
}

#[pyfunction]
fn views_week_overlapped(rows_json: &str) -> PyResult<String> {
    guard(|| {
        let rows = parse_array(rows_json, "rows")?;
        let placed = week::overlapped(rows).map_err(raise)?;
        Ok(Value::Array(placed).to_string())
    })
}

#[pyfunction]
fn views_week_tag_for(
    due: &Bound<'_, PyAny>,
    minutes: i64,
    today_iso: &str,
    hour: i64,
    minute: i64,
) -> PyResult<(String, String)> {
    guard(|| {
        let due_text = py_opt_string(due)?;
        let (tag, kind) =
            week::tag_for(due_text.as_deref(), minutes, today_iso, hour * 60 + minute)
                .map_err(raise)?;
        Ok((tag.to_string(), kind.to_string()))
    })
}

#[pyfunction]
fn views_week_left_line(unfinished_json: &str) -> PyResult<String> {
    guard(|| {
        let items = parse_array(unfinished_json, "unfinished")?;
        Ok(week::left_line(&items))
    })
}

#[pyfunction]
fn views_week_plan_label(prefs: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let value = match prefs.cast::<PyDict>() {
            Ok(dict) => match dict.get_item("planning_style")? {
                Some(item) if item.is_instance_of::<PyString>() => {
                    let mut map = Map::new();
                    map.insert(
                        "planning_style".to_string(),
                        Value::String(item.extract::<String>()?),
                    );
                    Value::Object(map)
                }
                _ => Value::Null,
            },
            Err(_) if prefs.is_none() => Value::Null,
            Err(_) => return Err(PyTypeError::new_err("preferences must be a dict or None")),
        };
        Ok(week::plan_label(&value).to_string())
    })
}

#[pyfunction]
fn views_week_optional_day(day: i64) -> PyResult<Option<i64>> {
    guard(|| Ok(week::optional_day(day)))
}

#[pyfunction]
fn views_week_has_copied(clipboard: &Bound<'_, PyAny>, busy: bool) -> PyResult<bool> {
    guard(|| Ok(week::has_copied(!clipboard.is_none(), busy)))
}

#[pyfunction]
fn views_week_parse_date(iso: &str) -> PyResult<Option<String>> {
    guard(|| Ok(week::parse_iso_date(iso)))
}

#[pyfunction]
fn views_week_hand_move_problem(answer_json: &str) -> PyResult<Option<String>> {
    guard(|| {
        let parsed = parse_json(answer_json, "hand move answer")?;
        week::hand_move_problem(&parsed).map_err(raise)
    })
}

#[pyfunction]
fn views_week_when_idle(busy: bool) -> PyResult<Option<bool>> {
    guard(|| Ok((!busy).then_some(true)))
}

/// Stateful view-model backing `desktop/native/material/bridge_week.py::WeekBridge`.
#[pyclass(name = "WeekView", module = "flexweek_engine")]
pub struct WeekViewHandle {
    state: Mutex<WeekView>,
}

impl WeekViewHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, WeekView>> {
        self.state
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the week view failed earlier"))
    }
}

#[pymethods]
impl WeekViewHandle {
    #[new]
    fn new() -> PyResult<Self> {
        guard(|| {
            Ok(Self {
                state: Mutex::new(WeekView::new()),
            })
        })
    }

    fn clock_24h(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.clock_24h))
    }

    fn snapshot_json(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.snapshot().to_string()))
    }

    fn prepare_reload(
        &self,
        prefs: &Bound<'_, PyAny>,
        week_start: Option<&str>,
        signed_in: bool,
    ) -> PyResult<Option<bool>> {
        guard(|| {
            let parsed_prefs = read_reload_prefs(prefs)?;
            let ready = self
                .locked()?
                .prepare_reload(&parsed_prefs, week_start, signed_in)
                .map_err(raise)?;
            Ok(ready.then_some(true))
        })
    }

    // Reload collects the session's week, missed ids, drawer counts, and clocks in one call.
    #[allow(clippy::too_many_arguments)]
    fn finish_reload(
        &self,
        mode: &str,
        week: &Bound<'_, PyAny>,
        missed: &Bound<'_, PyAny>,
        needed_json: &str,
        plan_can_place: bool,
        uncovered: &Bound<'_, PyAny>,
        unfinished_json: &str,
        today_iso: &str,
        hour: i64,
        minute: i64,
        steady_ms: i64,
        fresh_s: f64,
    ) -> PyResult<()> {
        guard(|| {
            let mut occurrences = Vec::new();
            for item in week.getattr("occurrences")?.try_iter()? {
                occurrences.push(read_occurrence(&item?)?);
            }
            let mut waiting = Vec::new();
            if let Ok(items) = week.getattr("waiting") {
                for item in items.try_iter()? {
                    waiting.push(read_waiting(&item?)?);
                }
            }
            let mut missed_set = HashSet::new();
            for item in missed.try_iter()? {
                missed_set.insert(item?.extract::<String>()?);
            }
            let needed = parse_array(needed_json, "needed")?;
            let uncovered_items = read_uncovered(uncovered)?;
            let unfinished = parse_array(unfinished_json, "unfinished")?;
            self.locked()?
                .finish_reload(ReloadInput {
                    mode,
                    occurrences: &occurrences,
                    waiting: &waiting,
                    missed: &missed_set,
                    needed: &needed,
                    plan_can_place,
                    uncovered: &uncovered_items,
                    unfinished: &unfinished,
                    today_iso,
                    clock_minute: hour * 60 + minute,
                    steady_ms,
                    fresh_s,
                })
                .map_err(raise)
        })
    }

    fn begin_plan(&self, steady_ms: i64) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.begin_plan(steady_ms).then_some(true)))
    }

    fn on_status(
        &self,
        message: &str,
        steady_ms: i64,
        plan_window_s: f64,
    ) -> PyResult<Option<bool>> {
        guard(|| {
            Ok(self
                .locked()?
                .on_status(message, steady_ms, plan_window_s)
                .then_some(true))
        })
    }

    fn on_planned(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.on_planned();
            Ok(())
        })
    }

    fn on_save_finished(&self, ok: bool) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.on_save_finished(ok)))
    }

    fn place_homework_plan(
        &self,
        blocks_json: &str,
        block_id: &str,
        day: i64,
        start: i64,
        busy: bool,
    ) -> PyResult<Option<(i64, i64, Option<bool>)>> {
        guard(|| {
            let blocks = parse_array(blocks_json, "blocks")?;
            let plan = self
                .locked()?
                .place_homework_plan(&blocks, block_id, day, start, busy)
                .map_err(raise)?;
            Ok(plan.map(|found| (found.start, found.end, found.judge.then_some(true))))
        })
    }

    fn move_block_plan(
        &self,
        blocks_json: &str,
        block_id: &str,
        day: i64,
        start: i64,
        end: i64,
        busy: bool,
    ) -> PyResult<Option<(i64, i64, Option<bool>)>> {
        guard(|| {
            let blocks = parse_array(blocks_json, "blocks")?;
            let plan = self
                .locked()?
                .move_block_plan(&blocks, block_id, day, start, end, busy);
            Ok(plan.map(|found| (found.start, found.end, found.judge.then_some(true))))
        })
    }

    fn plan_one_target(
        &self,
        blocks_json: &str,
        identifier: &str,
        steady_ms: i64,
    ) -> PyResult<Option<String>> {
        guard(|| {
            let blocks = parse_array(blocks_json, "blocks")?;
            Ok(self
                .locked()?
                .plan_one_target(&blocks, identifier, steady_ms))
        })
    }

    fn toggle_done_plan(
        &self,
        assignments_json: &str,
        assignment_id: &str,
        busy: bool,
    ) -> PyResult<Option<(bool, String)>> {
        guard(|| {
            let assignments = parse_object_or_null(assignments_json, "assignments")?;
            Ok(self
                .locked()?
                .toggle_done_plan(&assignments, assignment_id, busy)
                .map(|plan| (plan.finished, plan.notice)))
        })
    }

    fn record_done_after_save(&self, words: String, busy: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.record_done_after_save(words, busy);
            Ok(())
        })
    }

    fn toggle_weekends_start(&self, prefs_json: &str) -> PyResult<(u64, bool, String)> {
        guard(|| {
            let prefs = parse_object_or_null(prefs_json, "preferences")?;
            let plan = self.locked()?.toggle_weekends_start(&prefs);
            Ok((plan.ticket, plan.wanted, plan.preferences.to_string()))
        })
    }

    fn toggle_weekends_finish(
        &self,
        ticket: u64,
        ok: bool,
        latest_prefs_json: &str,
    ) -> PyResult<Option<(String, String)>> {
        guard(|| {
            let latest = parse_object_or_null(latest_prefs_json, "preferences")?;
            Ok(self
                .locked()?
                .toggle_weekends_finish(ticket, ok, &latest)
                .map(|rollback| {
                    (
                        rollback.preferences.to_string(),
                        rollback.message.to_string(),
                    )
                }))
        })
    }

    fn picker_anchor(&self, week_start: Option<&str>) -> PyResult<String> {
        guard(|| Ok(self.locked()?.nav.picker_anchor(week_start.unwrap_or(""))))
    }

    fn shift_target(&self, days: i64, week_start: Option<&str>) -> PyResult<Option<String>> {
        guard(|| {
            self.locked()?
                .nav
                .shift_target(days, week_start.unwrap_or(""))
                .map_err(raise)
        })
    }

    fn load_target(&self, target: String, busy: bool) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.nav.load_target(target, busy).then_some(true)))
    }

    fn begin_flush(&self, week_start: Option<&str>, busy: bool) -> PyResult<Option<String>> {
        guard(|| {
            Ok(self
                .locked()?
                .nav
                .begin_flush(week_start.unwrap_or(""), busy))
        })
    }

    fn finish_flush(&self, busy: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.nav.finish_flush(busy);
            Ok(())
        })
    }

    fn settle_navigation(&self, week_start: Option<&str>, busy: bool) -> PyResult<Option<bool>> {
        guard(|| {
            Ok(self
                .locked()?
                .nav
                .settle_navigation(week_start.unwrap_or(""), busy)
                .then_some(true))
        })
    }

    fn on_account_changed(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.nav.on_account_changed();
            Ok(())
        })
    }

    fn target_week(&self) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.nav.target_week.clone()))
    }

    fn set_target_week(&self, value: Option<String>) -> PyResult<()> {
        guard(|| {
            self.locked()?.nav.target_week = value;
            Ok(())
        })
    }

    fn loading_week(&self) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.nav.loading_week.clone()))
    }

    fn set_loading_week(&self, value: Option<String>) -> PyResult<()> {
        guard(|| {
            self.locked()?.nav.loading_week = value;
            Ok(())
        })
    }
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("VIEWS_WEEK_EVERYTHING_TIMED", week::EVERYTHING_TIMED)?;
    module.add("VIEWS_WEEK_DANGER_SLACK_MIN", week::DANGER_SLACK_MIN)?;
    module.add("VIEWS_WEEK_TIGHT_SLACK_MIN", week::TIGHT_SLACK_MIN)?;
    module.add("VIEWS_WEEK_DAY_MIN", week::DAY_MIN)?;
    module.add("VIEWS_WEEK_PLAN_WINDOW_S", week::PLAN_WINDOW_S)?;
    module.add("VIEWS_WEEK_FRESH_S", week::FRESH_S)?;
    module.add_class::<WeekViewHandle>()?;
    crate::export!(
        module,
        views_week_bool_pref,
        views_week_occurrence_row,
        views_week_overlapped,
        views_week_tag_for,
        views_week_left_line,
        views_week_plan_label,
        views_week_optional_day,
        views_week_has_copied,
        views_week_parse_date,
        views_week_hand_move_problem,
        views_week_when_idle,
    );
    Ok(())
}
