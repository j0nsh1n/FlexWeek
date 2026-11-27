//! Python bindings for Month cells and the Material Month view-model
//! (`flexweek_app::views::month`).
//!
//! Every exported function and method body runs inside `guard(` and refuses wrong-shaped
//! inputs with `ValueError` or `TypeError`.

use std::sync::{Mutex, MutexGuard};

use flexweek_app::views::month::{self, MonthCell, MonthChip, MonthView, OpenOccurrence, OpenWeek};
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyModule, PyString};
use serde_json::{Map, Value};

use crate::{guard, raise};

fn parse_object_or_null(text: &str, what: &str) -> PyResult<Value> {
    let parsed: Value = serde_json::from_str(text)
        .map_err(|error| PyValueError::new_err(format!("{what}: {error}")))?;
    match parsed {
        Value::Object(_) | Value::Null => Ok(parsed),
        _ => Err(PyValueError::new_err(format!(
            "{what} must be a JSON object or null"
        ))),
    }
}

fn py_opt_string(value: &Bound<'_, PyAny>, what: &str) -> PyResult<Option<String>> {
    if value.is_none() {
        return Ok(None);
    }
    if value.is_instance_of::<PyString>() {
        return Ok(Some(value.extract::<String>()?));
    }
    Err(PyTypeError::new_err(format!(
        "{what} must be a string or None"
    )))
}

fn read_prefs(prefs: &Bound<'_, PyAny>) -> PyResult<Value> {
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
    Ok(Value::Object(map))
}

fn read_open_occurrence(item: &Bound<'_, PyAny>) -> PyResult<OpenOccurrence> {
    Ok(OpenOccurrence {
        block_id: item.getattr("block_id")?.extract()?,
        title: item.getattr("title")?.extract()?,
        category: item.getattr("category")?.extract()?,
        day: item.getattr("day")?.extract()?,
        start: item.getattr("start")?.extract()?,
        end: item.getattr("end")?.extract()?,
        done: item.getattr("done")?.is_truthy()?,
        history: item.getattr("history")?.extract()?,
    })
}

fn read_week_occurrences(week: &Bound<'_, PyAny>) -> PyResult<Vec<OpenOccurrence>> {
    let raw = week
        .getattr("occurrences")
        .map_err(|_| PyTypeError::new_err("week must expose 'occurrences'"))?;
    let mut items = Vec::new();
    for entry in raw.try_iter()? {
        items.push(read_open_occurrence(&entry?)?);
    }
    Ok(items)
}

fn read_open_weeks(weeks: &Bound<'_, PyAny>) -> PyResult<Vec<OpenWeek>> {
    let items = weeks
        .call_method0("items")
        .map_err(|_| PyTypeError::new_err("weeks must be a mapping"))?;
    let mut out = Vec::new();
    for pair in items.try_iter()? {
        let pair = pair?;
        let parts: Vec<Bound<'_, PyAny>> = pair.try_iter()?.collect::<PyResult<_>>()?;
        if parts.len() != 2 {
            return Err(PyValueError::new_err(
                "weeks.items() must yield (week_start, week) pairs",
            ));
        }
        let week_start: String = parts[0].extract()?;
        let occurrences = read_week_occurrences(&parts[1])?;
        out.push(OpenWeek {
            week_start,
            occurrences,
        });
    }
    Ok(out)
}

fn read_session_weeks(
    unsaved: &Bound<'_, PyAny>,
    week_start: Option<&str>,
    built_week: &Bound<'_, PyAny>,
) -> PyResult<Vec<OpenWeek>> {
    let mut out = read_open_weeks(unsaved)?;
    if let Some(start) = week_start.filter(|text| !text.is_empty())
        && !built_week.is_none()
    {
        let occurrences = read_week_occurrences(built_week)?;
        out.push(OpenWeek {
            week_start: start.to_string(),
            occurrences,
        });
    }
    Ok(out)
}

fn read_chip(chip: &Bound<'_, PyAny>) -> PyResult<MonthChip> {
    let key = match chip.getattr("key") {
        Ok(val) => val.extract::<String>()?,
        Err(_) => String::new(),
    };
    let block_id = match chip.getattr("block_id") {
        Ok(val) => py_opt_string(&val, "block_id")?,
        Err(_) => None,
    };
    let start_val = chip.getattr("start")?;
    let start = if start_val.is_none() {
        None
    } else {
        Some(start_val.extract::<i64>()?)
    };
    let due_time = match chip.getattr("due_time") {
        Ok(val) => py_opt_string(&val, "due_time")?,
        Err(_) => None,
    };
    let late = match chip.getattr("late") {
        Ok(val) => val.is_truthy()?,
        Err(_) => false,
    };
    Ok(MonthChip {
        key,
        title: chip.getattr("title")?.extract()?,
        category: chip.getattr("category")?.extract()?,
        block_id,
        start,
        minutes: chip.getattr("minutes")?.extract()?,
        due: chip.getattr("due")?.is_truthy()?,
        due_time,
        done: chip.getattr("done")?.is_truthy()?,
        late,
        history: chip.getattr("history")?.extract()?,
    })
}

fn read_cell(cell: &Bound<'_, PyAny>) -> PyResult<MonthCell> {
    let mut chips = Vec::new();
    for item in cell.getattr("chips")?.try_iter()? {
        chips.push(read_chip(&item?)?);
    }
    Ok(MonthCell {
        iso: cell.getattr("iso")?.extract()?,
        in_month: cell.getattr("in_month")?.is_truthy()?,
        today: cell.getattr("today")?.is_truthy()?,
        chips,
        planned_min: cell.getattr("planned_min")?.extract()?,
        completed_min: cell.getattr("completed_min")?.extract()?,
    })
}

#[pyfunction]
fn views_month_chip_carried(
    block_id: Option<&str>,
    start: Option<i64>,
    due: bool,
) -> PyResult<bool> {
    guard(|| Ok(month::chip_carried(block_id, start, due)))
}

#[pyfunction]
fn views_month_chip_flag(
    history: &str,
    due: bool,
    late: bool,
    due_time: Option<&str>,
) -> PyResult<String> {
    guard(|| month::chip_flag(history, due, late, due_time).map_err(raise))
}

#[pyfunction]
fn views_month_chip_words(
    title: &str,
    start: Option<i64>,
    due: bool,
    late: bool,
    due_time: Option<&str>,
    history: &str,
) -> PyResult<String> {
    guard(|| month::chip_words(title, start, due, late, due_time, history).map_err(raise))
}

#[pyfunction]
fn views_month_day_number(iso: &str) -> PyResult<i64> {
    guard(|| month::day_number(iso).map_err(raise))
}

#[pyfunction]
fn views_month_cells(
    snapshot_json: &str,
    weeks: &Bound<'_, PyAny>,
    today_iso: &str,
    month_label: Option<&str>,
    first_weekday: u32,
) -> PyResult<String> {
    guard(|| {
        let snapshot = parse_object_or_null(snapshot_json, "snapshot")?;
        let open_weeks = read_open_weeks(weeks)?;
        let cells = month::month_cells(
            &snapshot,
            &open_weeks,
            today_iso,
            month_label,
            first_weekday,
        )
        .map_err(raise)?;
        let payload: Vec<Value> = cells.iter().map(MonthCell::to_json).collect();
        Ok(Value::Array(payload).to_string())
    })
}

#[pyfunction]
fn views_month_weekday_names(first_weekday: u32) -> PyResult<Vec<String>> {
    guard(|| month::weekday_names(first_weekday).map_err(raise))
}

#[pyfunction]
fn views_month_pane_line(chip: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let parsed = read_chip(chip)?;
        month::pane_line(&parsed).map_err(raise)
    })
}

#[pyfunction]
fn views_month_share(minutes: i64) -> PyResult<f64> {
    guard(|| Ok(month::study_share(minutes)))
}

#[pyfunction]
fn views_month_chip_kind(due: bool, late: bool) -> PyResult<String> {
    guard(|| Ok(month::chip_kind(due, late).to_string()))
}

#[pyfunction]
fn views_month_heading(iso: &str) -> PyResult<String> {
    guard(|| month::heading(iso).map_err(raise))
}

#[pyfunction]
fn views_month_access_name(iso: &str, today: bool, in_month: bool) -> PyResult<String> {
    guard(|| month::access_name(iso, today, in_month).map_err(raise))
}

#[pyfunction]
fn views_month_cell_row(cell: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let parsed = read_cell(cell)?;
        let row = month::cell_row(&parsed).map_err(raise)?;
        Ok(Value::Object(row).to_string())
    })
}

type PrepareReadTuple = (
    Option<bool>,
    Option<bool>,
    Option<String>,
    String,
    Option<bool>,
    Vec<String>,
);

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn views_month_prepare_read(
    signed_in: bool,
    prefs: &Bound<'_, PyAny>,
    month_label: Option<&str>,
    selected_month: Option<&str>,
    snapshot_json: &str,
    month_data_json: &str,
    week_start: Option<&str>,
    first_weekday: u32,
) -> PyResult<PrepareReadTuple> {
    guard(|| {
        let parsed_prefs = read_prefs(prefs)?;
        let snapshot = parse_object_or_null(snapshot_json, "snapshot")?;
        let month_data = parse_object_or_null(month_data_json, "month_data")?;
        let plan = month::prepare_read(
            signed_in,
            &parsed_prefs,
            month_label,
            selected_month,
            &snapshot,
            &month_data,
            week_start,
            first_weekday,
        )
        .map_err(raise)?;
        Ok((
            plan.clock_24h,
            plan.ready.then_some(true),
            plan.chosen_month,
            plan.chosen_snapshot.to_string(),
            plan.include_built_week.then_some(true),
            plan.weekday_names,
        ))
    })
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn views_month_build_rows(
    snapshot_json: &str,
    unsaved_weeks: &Bound<'_, PyAny>,
    week_start: Option<&str>,
    built_week: &Bound<'_, PyAny>,
    today_iso: &str,
    month_label: Option<&str>,
    first_weekday: u32,
) -> PyResult<String> {
    guard(|| {
        let snapshot = parse_object_or_null(snapshot_json, "snapshot")?;
        let open_weeks = read_session_weeks(unsaved_weeks, week_start, built_week)?;
        let rows = month::build_rows(
            &snapshot,
            &open_weeks,
            today_iso,
            month_label,
            first_weekday,
        )
        .map_err(raise)?;
        Ok(Value::Array(rows).to_string())
    })
}

/// Stateful view-model backing `desktop/native/material/bridge_month.py::MonthBridge`.
#[pyclass(name = "MonthView", module = "flexweek_engine")]
pub struct MonthViewHandle {
    state: Mutex<MonthView>,
}

impl MonthViewHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, MonthView>> {
        self.state
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the month view failed earlier"))
    }
}

#[pymethods]
impl MonthViewHandle {
    #[new]
    fn new() -> PyResult<Self> {
        guard(|| {
            Ok(Self {
                state: Mutex::new(MonthView::new()),
            })
        })
    }

    fn snapshot_json(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.snapshot().to_string()))
    }

    #[allow(clippy::too_many_arguments)]
    fn prepare_reload(
        &self,
        signed_in: bool,
        prefs: &Bound<'_, PyAny>,
        selected_month: Option<&str>,
        month_data_json: &str,
        week_start: Option<&str>,
        first_weekday: u32,
    ) -> PyResult<(Option<bool>, Option<bool>, Option<bool>)> {
        guard(|| {
            let parsed_prefs = read_prefs(prefs)?;
            let month_data = parse_object_or_null(month_data_json, "month_data")?;
            let plan = self
                .locked()?
                .prepare_reload(
                    signed_in,
                    &parsed_prefs,
                    selected_month,
                    &month_data,
                    week_start,
                    first_weekday,
                )
                .map_err(raise)?;
            Ok((
                plan.clock_24h,
                plan.ready.then_some(true),
                plan.include_built_week.then_some(true),
            ))
        })
    }

    fn finish_reload(
        &self,
        unsaved_weeks: &Bound<'_, PyAny>,
        week_start: Option<&str>,
        built_week: &Bound<'_, PyAny>,
        today_iso: &str,
    ) -> PyResult<()> {
        guard(|| {
            let open_weeks = read_session_weeks(unsaved_weeks, week_start, built_week)?;
            self.locked()?
                .finish_reload(&open_weeks, today_iso)
                .map_err(raise)
        })
    }

    fn select_date(&self, iso: &str) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.select_date(iso).then_some(true)))
    }

    fn close_date(&self) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.close_date().then_some(true)))
    }

    fn open_day_target(&self) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.open_day_target()))
    }

    fn picker_anchor(&self, selected_month: Option<&str>, today_iso: &str) -> PyResult<String> {
        guard(|| Ok(month::picker_anchor(selected_month, today_iso)))
    }

    fn go_to_date_month(&self, iso: &str, signed_in: bool) -> PyResult<Option<String>> {
        guard(|| Ok(month::go_to_date_month(iso, signed_in)))
    }

    fn today_month(&self, signed_in: bool, today_iso: &str) -> PyResult<Option<String>> {
        guard(|| Ok(month::today_month(signed_in, today_iso)))
    }

    fn activate_plan(
        &self,
        signed_in: bool,
        planner_view: &str,
    ) -> PyResult<(Option<bool>, Option<bool>)> {
        guard(|| {
            let plan = month::activate_plan(signed_in, planner_view);
            Ok((plan.open_month.then_some(true), plan.reload.then_some(true)))
        })
    }

    fn shift_plan(
        &self,
        signed_in: bool,
        planner_view: &str,
        amount: i64,
    ) -> PyResult<Option<(Option<bool>, i64)>> {
        guard(|| {
            Ok(month::shift_plan(signed_in, planner_view, amount)
                .map(|plan| (plan.open_month.then_some(true), plan.amount)))
        })
    }

    fn set_show_study_time(&self, on: bool) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.set_show_study_time(on).then_some(true)))
    }
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("VIEWS_MONTH_LOAD_CAP", month::LOAD_CAP)?;
    module.add("VIEWS_MONTH_LOAD_WORDS", month::LOAD_WORDS)?;
    module.add(
        "VIEWS_MONTH_HOMEWORK_CATEGORIES",
        month::HOMEWORK_CATEGORIES.to_vec(),
    )?;
    module.add("VIEWS_MONTH_WEEKDAYS", month::WEEKDAYS.to_vec())?;
    module.add_class::<MonthViewHandle>()?;
    crate::export!(
        module,
        views_month_chip_carried,
        views_month_chip_flag,
        views_month_chip_words,
        views_month_day_number,
        views_month_cells,
        views_month_weekday_names,
        views_month_pane_line,
        views_month_share,
        views_month_chip_kind,
        views_month_heading,
        views_month_access_name,
        views_month_cell_row,
        views_month_prepare_read,
        views_month_build_rows,
    );
    Ok(())
}
