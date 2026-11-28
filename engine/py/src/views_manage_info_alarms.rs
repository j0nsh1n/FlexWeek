//! Python bindings for Material alarms, Help/About/Update, and Manage account/Restore
//! (`flexweek_app::views::manage_info_alarms`).
//!
//! Every exported function and method body runs inside `guard(` and refuses wrong-shaped
//! inputs with `ValueError` or `TypeError`.

use std::sync::{Mutex, MutexGuard};

use flexweek_app::views::manage_info_alarms::{
    self, AlarmDraft, BAD_LINK, DATA_ACTIONS, DAY_EXPORT_FILENAME, FULL, MAX_ALARMS, NO_DAY,
    NO_LOCATION, NOT_SAVED, RESTORE_FIRST, RingState, SELECT_DAY_FIRST, WeekImportDecision,
};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyModule, PyTuple};
use serde_json::Value;

use crate::{guard, raise};

fn parse_json(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn parse_array(text: &str, what: &str) -> PyResult<Vec<Value>> {
    match parse_json(text, what)? {
        Value::Array(items) => Ok(items),
        _ => Err(PyValueError::new_err(format!("{what} must be a JSON list"))),
    }
}

fn parse_object(text: &str, what: &str) -> PyResult<Value> {
    match parse_json(text, what)? {
        value @ Value::Object(_) => Ok(value),
        _ => Err(PyValueError::new_err(format!(
            "{what} must be a JSON object"
        ))),
    }
}

fn parse_object_or_null(text: &str, what: &str) -> PyResult<Value> {
    match parse_json(text, what)? {
        value @ (Value::Object(_) | Value::Null) => Ok(value),
        _ => Err(PyValueError::new_err(format!(
            "{what} must be a JSON object or null"
        ))),
    }
}

fn dump(value: &Value) -> PyResult<String> {
    serde_json::to_string(value).map_err(|error| PyValueError::new_err(format!("json: {error}")))
}

#[pyclass(name = "AlarmDraftCore", module = "flexweek_engine")]
pub struct AlarmDraftHandle {
    state: Mutex<AlarmDraft>,
}

impl AlarmDraftHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, AlarmDraft>> {
        self.state
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the alarm draft failed earlier"))
    }
}

#[pymethods]
impl AlarmDraftHandle {
    #[new]
    #[pyo3(signature = (alarm_json, default_sound, fresh_id, clock_24h = false))]
    fn new(
        alarm_json: &str,
        default_sound: &str,
        fresh_id: &str,
        clock_24h: bool,
    ) -> PyResult<Self> {
        guard(|| {
            let alarm = parse_object_or_null(alarm_json, "alarm")?;
            let draft = AlarmDraft::new(
                (!alarm.is_null()).then_some(&alarm),
                default_sound,
                fresh_id,
                clock_24h,
            )
            .map_err(raise)?;
            Ok(Self {
                state: Mutex::new(draft),
            })
        })
    }

    #[getter]
    fn existing(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.existing))
    }

    #[getter]
    fn clock_24h(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.clock_24h))
    }

    #[getter]
    fn id(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.id.clone()))
    }

    #[getter]
    fn name(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.name.clone()))
    }

    #[getter]
    fn hour(&self) -> PyResult<i64> {
        guard(|| Ok(self.locked()?.hour))
    }

    #[getter]
    fn minute(&self) -> PyResult<i64> {
        guard(|| Ok(self.locked()?.minute))
    }

    #[getter]
    fn days(&self) -> PyResult<Vec<i64>> {
        guard(|| Ok(self.locked()?.days.clone()))
    }

    #[getter]
    fn enabled(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.enabled))
    }

    #[getter]
    fn sound(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.sound.clone()))
    }

    #[getter]
    fn link(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.link.clone()))
    }

    #[getter]
    fn days_problem(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.days_problem.clone()))
    }

    #[getter]
    fn link_problem(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.link_problem.clone()))
    }

    #[getter]
    fn error(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.error.clone()))
    }

    #[setter]
    fn set_error(&self, value: String) -> PyResult<()> {
        guard(|| {
            self.locked()?.error = value;
            Ok(())
        })
    }

    fn dirty(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.dirty()))
    }

    fn set_text(&self, name: &str, value: &str) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_text(name, value);
            Ok(())
        })
    }

    fn set_number(&self, name: &str, value: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_number(name, value);
            Ok(())
        })
    }

    fn set_enabled(&self, on: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_enabled(on);
            Ok(())
        })
    }

    fn toggle_day(&self, day: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.toggle_day(day);
            Ok(())
        })
    }

    fn candidate_json(&self) -> PyResult<Option<String>> {
        guard(|| match self.locked()?.candidate() {
            Some(value) => Ok(Some(dump(&value)?)),
            None => Ok(None),
        })
    }

    fn form_json(&self) -> PyResult<String> {
        guard(|| dump(&self.locked()?.form()))
    }
}

#[pyclass(name = "RingView", module = "flexweek_engine")]
pub struct RingViewHandle {
    state: Mutex<RingState>,
}

impl RingViewHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, RingState>> {
        self.state
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the ring view failed earlier"))
    }
}

#[pymethods]
impl RingViewHandle {
    #[new]
    fn new() -> PyResult<Self> {
        guard(|| {
            Ok(Self {
                state: Mutex::new(RingState::new()),
            })
        })
    }

    #[getter]
    fn open(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.open))
    }

    fn form_json(&self) -> PyResult<String> {
        guard(|| dump(&self.locked()?.form))
    }

    fn show_alarm(&self, alarm_json: &str, url: &str) -> PyResult<String> {
        guard(|| {
            let alarm = parse_object(alarm_json, "alarm")?;
            let form = self.locked()?.show_alarm(&alarm, url).map_err(raise)?;
            dump(&form)
        })
    }

    fn show_playing(&self, words: &str) -> PyResult<Option<String>> {
        guard(|| match self.locked()?.show_playing(words) {
            Some(form) => Ok(Some(dump(&form)?)),
            None => Ok(None),
        })
    }

    fn finish(&self) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.finish().then_some(true)))
    }

    fn spotify_url(&self) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.spotify_url().map(str::to_string)))
    }
}

#[pyfunction]
fn views_alarm_rows(alarms_json: &str) -> PyResult<String> {
    guard(|| {
        let alarms = parse_array(alarms_json, "alarms")?;
        let rows = manage_info_alarms::alarm_rows(&alarms).map_err(raise)?;
        dump(&Value::Array(rows))
    })
}

#[pyfunction]
#[pyo3(signature = (alarm_json, url = ""))]
fn views_ring_form(alarm_json: &str, url: &str) -> PyResult<String> {
    guard(|| {
        let alarm = parse_object(alarm_json, "alarm")?;
        dump(&manage_info_alarms::ring_form(&alarm, url).map_err(raise)?)
    })
}

#[pyfunction]
fn views_with_alarm(alarms_json: &str, made_json: &str) -> PyResult<String> {
    guard(|| {
        let alarms = parse_array(alarms_json, "alarms")?;
        let made = parse_object(made_json, "made")?;
        let out = manage_info_alarms::with_alarm(&alarms, &made).map_err(raise)?;
        dump(&Value::Array(out))
    })
}

#[pyfunction]
fn views_help_form(numbers: bool, letters: bool) -> PyResult<String> {
    guard(|| dump(&manage_info_alarms::help_form(numbers, letters)))
}

#[pyfunction]
fn views_about_form(storage_json: &str, logo_url: &str, version: &str) -> PyResult<String> {
    guard(|| {
        let storage = parse_object_or_null(storage_json, "storage")?;
        dump(&manage_info_alarms::about_form(&storage, logo_url, version).map_err(raise)?)
    })
}

#[pyfunction]
fn views_update_form(update_json: &str, current: &str, state_json: &str) -> PyResult<String> {
    guard(|| {
        let update = parse_object(update_json, "update")?;
        let state = parse_object(state_json, "state")?;
        dump(&manage_info_alarms::update_form(&update, current, &state).map_err(raise)?)
    })
}

#[pyfunction]
fn views_manage_where(storage_json: &str) -> PyResult<String> {
    guard(|| {
        let storage = parse_object_or_null(storage_json, "storage")?;
        Ok(manage_info_alarms::where_saved(&storage)
            .map_err(raise)?
            .to_string())
    })
}

#[pyfunction]
fn views_account_form(storage_json: &str, remaining_json: &str) -> PyResult<String> {
    guard(|| {
        let storage = parse_object_or_null(storage_json, "storage")?;
        let remaining = parse_json(remaining_json, "remaining")?;
        dump(&manage_info_alarms::account_form(&storage, &remaining).map_err(raise)?)
    })
}

#[pyfunction]
fn views_restore_form(
    points_json: &str,
    preview_json: &str,
    storage_json: &str,
    selected: &str,
    label: &str,
    note: &str,
) -> PyResult<String> {
    guard(|| {
        let points = parse_array(points_json, "points")?;
        let preview = parse_object_or_null(preview_json, "preview")?;
        let storage = parse_object_or_null(storage_json, "storage")?;
        dump(
            &manage_info_alarms::restore_form(&points, &preview, &storage, selected, label, note)
                .map_err(raise)?,
        )
    })
}

#[pyfunction]
fn views_delete_question(name: &str, storage_json: &str) -> PyResult<String> {
    guard(|| {
        let storage = parse_object_or_null(storage_json, "storage")?;
        dump(&manage_info_alarms::delete_question(name, &storage).map_err(raise)?)
    })
}

#[pyfunction]
fn views_import_question(preview_json: &str) -> PyResult<String> {
    guard(|| {
        let preview = parse_object(preview_json, "preview")?;
        dump(&manage_info_alarms::import_question(&preview).map_err(raise)?)
    })
}

#[pyfunction]
fn views_replace_week_question(week: &str) -> PyResult<String> {
    guard(|| dump(&manage_info_alarms::replace_week_question(week)))
}

#[pyfunction]
fn views_account_delete_question(account_json: &str, storage_json: &str) -> PyResult<String> {
    guard(|| {
        let account = parse_object_or_null(account_json, "account")?;
        let storage = parse_object_or_null(storage_json, "storage")?;
        dump(&manage_info_alarms::account_delete_question(&account, &storage).map_err(raise)?)
    })
}

#[pyfunction]
fn views_week_export_filename(week_start: &str) -> PyResult<String> {
    guard(|| Ok(manage_info_alarms::week_export_filename(week_start)))
}

#[pyfunction]
fn views_parse_backup_json(raw: &str) -> PyResult<(Option<String>, Option<String>)> {
    guard(|| match manage_info_alarms::parse_backup_json(raw) {
        Ok(snapshot) => Ok((Some(dump(&snapshot)?), None)),
        Err(error) => Ok((None, Some(error.to_string()))),
    })
}

#[pyfunction]
fn views_decide_week_import(
    parsed_json: &str,
    has_blocks: bool,
    week_start: &str,
    today_iso: &str,
) -> PyResult<(Option<String>, Option<String>)> {
    guard(|| {
        let parsed = parse_object(parsed_json, "parsed")?;
        match manage_info_alarms::decide_week_import(&parsed, has_blocks, week_start, today_iso)
            .map_err(raise)?
        {
            WeekImportDecision::Error(message) => Ok((Some(message), None)),
            WeekImportDecision::AskReplace(question) => Ok((None, Some(dump(&question)?))),
            WeekImportDecision::Import => Ok((None, None)),
        }
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = module.py();
    module.add("VIEW_ALARM_MAX", MAX_ALARMS)?;
    module.add("VIEW_ALARM_NO_DAY", NO_DAY)?;
    module.add("VIEW_ALARM_BAD_LINK", BAD_LINK)?;
    module.add("VIEW_ALARM_FULL", FULL)?;
    module.add("VIEW_ALARM_NOT_SAVED", NOT_SAVED)?;
    module.add(
        "VIEW_ALARM_SOUNDS_JSON",
        dump(&Value::Array(manage_info_alarms::alarm_sounds()))?,
    )?;
    module.add(
        "VIEW_ALARM_HOURS_JSON",
        dump(&Value::Array(manage_info_alarms::hours_24()))?,
    )?;
    module.add(
        "VIEW_ALARM_HOURS_12_JSON",
        dump(&Value::Array(manage_info_alarms::hours_12()))?,
    )?;
    module.add(
        "VIEW_ALARM_MINUTES_JSON",
        dump(&Value::Array(manage_info_alarms::minutes_list()))?,
    )?;
    module.add(
        "VIEW_SIGN_OUT_JSON",
        dump(&manage_info_alarms::sign_out_question())?,
    )?;
    module.add("VIEW_MANAGE_NO_LOCATION", NO_LOCATION)?;
    module.add("VIEW_MANAGE_RESTORE_FIRST", RESTORE_FIRST)?;
    module.add(
        "VIEW_MANAGE_RESTORE_QUESTION_JSON",
        dump(&manage_info_alarms::restore_question())?,
    )?;
    module.add("VIEW_MANAGE_DAY_EXPORT_FILENAME", DAY_EXPORT_FILENAME)?;
    module.add("VIEW_MANAGE_SELECT_DAY_FIRST", SELECT_DAY_FIRST)?;
    let mut actions = Vec::with_capacity(DATA_ACTIONS.len());
    for (name, action, label) in DATA_ACTIONS {
        actions.push(PyTuple::new(py, [name, action, label])?.into_any());
    }
    module.add("VIEW_MANAGE_DATA_ACTIONS", PyTuple::new(py, actions)?)?;
    module.add_class::<AlarmDraftHandle>()?;
    module.add_class::<RingViewHandle>()?;
    crate::export!(
        module,
        views_alarm_rows,
        views_ring_form,
        views_with_alarm,
        views_help_form,
        views_about_form,
        views_update_form,
        views_manage_where,
        views_account_form,
        views_restore_form,
        views_delete_question,
        views_import_question,
        views_replace_week_question,
        views_account_delete_question,
        views_week_export_filename,
        views_parse_backup_json,
        views_decide_week_import,
    );
    Ok(())
}
