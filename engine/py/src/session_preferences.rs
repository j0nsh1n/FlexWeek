//! Setup's write queue, queued preference saves and preference request decisions for the Python
//! window (`flexweek_app::session::preferences`, 2.0.0 plan P4 group 8). JSON text crosses, as with
//! `NativeCore`. Wrong-shaped JSON is refused with ValueError/TypeError.

use std::sync::{Mutex, MutexGuard};

use flexweek_app::session::preferences::{
    HOURS_REFUSED, MAX_WORK_WINDOWS, PreferencesQueue, SetupQueue, SetupStep, WORK_WINDOW_PRESETS,
    WORK_WINDOW_PRESETS_NOTE, availability_body, flush_setup_action, follow_first_weekday,
    keep_setup_merged_prefs, parse_recovery_status, parse_reminder_limits, parse_timer_presets,
    preferences_body, prepare_save_availability, prepare_save_preferences,
    prepare_timer_split_preview,
};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyList, PyTuple};
use serde_json::{Map, Value};

use crate::{guard, raise};

fn parse(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn parse_object(text: &str, what: &str) -> PyResult<Map<String, Value>> {
    match parse(text, what)? {
        Value::Object(fields) => Ok(fields),
        _ => Err(PyValueError::new_err(format!("{what} is an object"))),
    }
}

fn parse_opt_object(text: Option<&str>, what: &str) -> PyResult<Option<Value>> {
    text.map(|raw| parse_object(raw, what).map(Value::Object))
        .transpose()
}

fn parse_array(text: &str, what: &str) -> PyResult<Value> {
    match parse(text, what)? {
        value @ Value::Array(_) => Ok(value),
        _ => Err(PyValueError::new_err(format!("{what} must be a list"))),
    }
}

fn parse_setup_step(text: &str) -> PyResult<SetupStep> {
    let fields = parse_object(text, "setup step")?;
    let kind = fields
        .get("step")
        .and_then(Value::as_str)
        .ok_or_else(|| PyValueError::new_err("setup step must have a string 'step' field"))?;
    match kind {
        "nothing" => Ok(SetupStep::Nothing),
        "preferences" => {
            let updates = fields
                .get("updates")
                .and_then(Value::as_object)
                .ok_or_else(|| {
                    PyValueError::new_err("preferences step must have an object 'updates' field")
                })?;
            Ok(SetupStep::Preferences(updates.clone()))
        }
        "windows" => {
            let windows = fields
                .get("windows")
                .ok_or_else(|| PyValueError::new_err("windows step must have a 'windows' field"))?;
            Ok(SetupStep::Windows(windows.clone()))
        }
        "week" => Ok(SetupStep::Week),
        other => Err(PyValueError::new_err(format!(
            "unknown setup step {other:?}"
        ))),
    }
}

/// The preferences with the updates on top, as the save sends them.
#[pyfunction]
fn session_preferences_body(current: &str, updates: &str) -> PyResult<String> {
    guard(|| {
        let current = Value::Object(parse_object(current, "current preferences")?);
        let updates = Value::Object(parse_object(updates, "updates")?);
        Ok(preferences_body(&current, &updates).to_string())
    })
}

/// The preferences with the protected time, the day cutoff and, when given, Study hours on top.
#[pyfunction]
#[pyo3(signature = (prefs, protected, day_cutoff, work_windows=None))]
fn session_availability_body(
    prefs: &str,
    protected: &str,
    day_cutoff: &str,
    work_windows: Option<&str>,
) -> PyResult<String> {
    guard(|| {
        let prefs = Value::Object(parse_object(prefs, "preferences")?);
        let protected = parse(protected, "protected time")?;
        let day_cutoff = parse(day_cutoff, "day cutoff")?;
        let windows = work_windows
            .map(|text| parse(text, "work windows"))
            .transpose()?;
        Ok(availability_body(&prefs, &protected, &day_cutoff, windows.as_ref()).to_string())
    })
}

/// `{changed, refollow, rebase_focus}` as JSON text.
#[pyfunction]
fn session_follow_first_weekday(old: i64, new: i64, signed_in: bool) -> PyResult<String> {
    guard(|| {
        Ok(follow_first_weekday(old, new, signed_in)
            .to_json()
            .to_string())
    })
}

/// Optimistically overlay queued setup preferences on top of `current_prefs` when present.
#[pyfunction]
#[pyo3(signature = (current_prefs, setup_prefs))]
fn session_keep_setup_merged_prefs(
    current_prefs: Option<&str>,
    setup_prefs: &str,
) -> PyResult<Option<String>> {
    guard(|| {
        let current = parse_opt_object(current_prefs, "current preferences")?;
        let setup = parse_object(setup_prefs, "setup preferences")?;
        Ok(keep_setup_merged_prefs(current.as_ref(), &setup).map(|value| value.to_string()))
    })
}

/// Resolve a setup step against `current_prefs` (`protected` and `day_cutoff` defaults).
#[pyfunction]
#[pyo3(signature = (step, current_prefs=None))]
fn session_flush_setup_action(step: &str, current_prefs: Option<&str>) -> PyResult<String> {
    guard(|| {
        let step = parse_setup_step(step)?;
        let current = parse_opt_object(current_prefs, "current preferences")?;
        Ok(flush_setup_action(&step, current.as_ref())
            .to_json()
            .to_string())
    })
}

/// Validate protected time and Study hours windows and build the availability PUT request.
#[pyfunction]
#[pyo3(signature = (signed_in, prefs, protected, day_cutoff, work_windows=None))]
fn session_prepare_save_availability(
    signed_in: bool,
    prefs: Option<&str>,
    protected: &str,
    day_cutoff: &str,
    work_windows: Option<&str>,
) -> PyResult<String> {
    guard(|| {
        let prefs = parse_opt_object(prefs, "preferences")?;
        let protected = parse_array(protected, "protected time")?;
        let day_cutoff = parse(day_cutoff, "day cutoff")?;
        let windows = work_windows
            .map(|text| parse_array(text, "work windows"))
            .transpose()?;
        Ok(prepare_save_availability(
            signed_in,
            prefs.as_ref(),
            &protected,
            &day_cutoff,
            windows.as_ref(),
        )
        .to_json()
        .to_string())
    })
}

/// Guard, request body and status words for one `PUT /api/preferences`.
#[pyfunction]
#[pyo3(signature = (signed_in, prefs, updates))]
fn session_prepare_save_preferences(
    signed_in: bool,
    prefs: Option<&str>,
    updates: &str,
) -> PyResult<String> {
    guard(|| {
        let prefs = parse_opt_object(prefs, "preferences")?;
        let updates = Value::Object(parse_object(updates, "updates")?);
        Ok(
            prepare_save_preferences(signed_in, prefs.as_ref(), &updates)
                .to_json()
                .to_string(),
        )
    })
}

/// Build the 5-field `POST /api/timer-split-preview` request from `duration_min` and preferences.
#[pyfunction]
#[pyo3(signature = (signed_in, prefs, duration_min))]
fn session_prepare_timer_split_preview(
    signed_in: bool,
    prefs: Option<&str>,
    duration_min: i64,
) -> PyResult<String> {
    guard(|| {
        let prefs = parse_opt_object(prefs, "preferences")?;
        Ok(
            prepare_timer_split_preview(signed_in, prefs.as_ref(), duration_min)
                .to_json()
                .to_string(),
        )
    })
}

/// Extract the preset list from `/api/timer-presets` as a JSON array.
#[pyfunction]
fn session_parse_timer_presets(data: &str) -> PyResult<String> {
    guard(|| {
        let data = parse(data, "timer presets")?;
        let presets = parse_timer_presets(&data).map_err(raise)?;
        Ok(Value::Array(presets).to_string())
    })
}

/// Copy the `/api/reminder-limits` reply as a JSON object.
#[pyfunction]
fn session_parse_reminder_limits(data: &str) -> PyResult<String> {
    guard(|| {
        let data = parse(data, "reminder limits")?;
        let limits = parse_reminder_limits(&data).map_err(raise)?;
        Ok(Value::Object(limits).to_string())
    })
}

/// Extract the remaining recovery-code count from `/api/auth/recovery-status`.
#[pyfunction]
fn session_parse_recovery_status(data: &str) -> PyResult<i64> {
    guard(|| {
        let data = parse(data, "recovery status")?;
        parse_recovery_status(&data).map_err(raise)
    })
}

/// What setup kept and has not yet written. `next` and `next_action` answer the step to send as JSON text.
#[pyclass(name = "SetupQueue", module = "flexweek_engine")]
pub struct SetupQueueHandle {
    queue: Mutex<SetupQueue>,
}

impl SetupQueueHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, SetupQueue>> {
        self.queue
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the setup queue failed earlier"))
    }
}

#[pymethods]
impl SetupQueueHandle {
    #[new]
    fn new() -> Self {
        Self {
            queue: Mutex::new(SetupQueue::default()),
        }
    }

    #[pyo3(signature = (updates, work_windows=None, save_week=false))]
    fn keep(&self, updates: &str, work_windows: Option<&str>, save_week: bool) -> PyResult<()> {
        guard(|| {
            let updates = parse_object(updates, "updates")?;
            let windows = work_windows
                .map(|text| parse(text, "work windows"))
                .transpose()?;
            self.locked()?.keep(&updates, windows, save_week);
            Ok(())
        })
    }

    #[pyo3(signature = (updates, work_windows=None, save_week=false, current_prefs=None))]
    fn keep_and_merge(
        &self,
        updates: &str,
        work_windows: Option<&str>,
        save_week: bool,
        current_prefs: Option<&str>,
    ) -> PyResult<Option<String>> {
        guard(|| {
            let updates = parse_object(updates, "updates")?;
            let windows = work_windows
                .map(|text| parse(text, "work windows"))
                .transpose()?;
            let current = parse_opt_object(current_prefs, "current preferences")?;
            Ok(self
                .locked()?
                .keep_and_merge(&updates, windows, save_week, current.as_ref())
                .map(|value| value.to_string()))
        })
    }

    fn next(&self, signed_in: bool, busy: bool, has_preferences: bool) -> PyResult<String> {
        guard(|| {
            let step = self.locked()?.next(signed_in, busy, has_preferences);
            Ok(step.to_json().to_string())
        })
    }

    #[pyo3(signature = (signed_in, busy, current_prefs=None))]
    fn next_action(
        &self,
        signed_in: bool,
        busy: bool,
        current_prefs: Option<&str>,
    ) -> PyResult<String> {
        guard(|| {
            let current = parse_opt_object(current_prefs, "current preferences")?;
            let action = self
                .locked()?
                .next_action(signed_in, busy, current.as_ref());
            Ok(action.to_json().to_string())
        })
    }

    fn has_pending(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.has_pending()))
    }

    #[pyo3(signature = (current_id, incoming_id))]
    fn drop_if_other_account(&self, current_id: Option<&str>, incoming_id: &str) -> PyResult<bool> {
        guard(|| {
            let current = current_id
                .map(|raw| parse(raw, "current account id"))
                .transpose()?;
            let incoming = parse(incoming_id, "incoming account id")?;
            Ok(self
                .locked()?
                .drop_if_other_account(current.as_ref(), &incoming))
        })
    }

    fn prefs(&self) -> PyResult<String> {
        guard(|| Ok(Value::Object(self.locked()?.prefs().clone()).to_string()))
    }

    fn windows(&self) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.windows().map(Value::to_string)))
    }

    fn week(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.week()))
    }

    fn set_prefs(&self, prefs: &str) -> PyResult<()> {
        guard(|| {
            let prefs = parse_object(prefs, "preferences")?;
            self.locked()?.set_prefs(prefs);
            Ok(())
        })
    }

    #[pyo3(signature = (work_windows=None))]
    fn set_windows(&self, work_windows: Option<&str>) -> PyResult<()> {
        guard(|| {
            let windows = work_windows
                .map(|text| parse(text, "work windows"))
                .transpose()?;
            self.locked()?.set_windows(windows);
            Ok(())
        })
    }

    fn set_week(&self, week: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_week(week);
            Ok(())
        })
    }

    fn clear(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.clear();
            Ok(())
        })
    }
}

/// Queued Settings preference saves and preference-fetch staleness ticket.
#[pyclass(name = "PreferencesQueue", module = "flexweek_engine")]
pub struct PreferencesQueueHandle {
    queue: Mutex<PreferencesQueue>,
}

impl PreferencesQueueHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, PreferencesQueue>> {
        self.queue
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the preferences queue failed earlier"))
    }
}

#[pymethods]
impl PreferencesQueueHandle {
    #[new]
    fn new() -> Self {
        Self {
            queue: Mutex::new(PreferencesQueue::default()),
        }
    }

    fn enqueue(&self, signed_in: bool, has_preferences: bool, updates: &str) -> PyResult<bool> {
        guard(|| {
            let updates = parse_object(updates, "updates")?;
            Ok(self.locked()?.enqueue(signed_in, has_preferences, &updates))
        })
    }

    #[pyo3(signature = (signed_in, busy, current_ticket, current_prefs=None))]
    fn next(
        &self,
        signed_in: bool,
        busy: bool,
        current_ticket: u64,
        current_prefs: Option<&str>,
    ) -> PyResult<String> {
        guard(|| {
            let current = parse_opt_object(current_prefs, "current preferences")?;
            let action = self
                .locked()?
                .next(signed_in, busy, current_ticket, current.as_ref());
            Ok(action.to_json().to_string())
        })
    }

    fn mark_in_flight(&self, ticket: u64) -> PyResult<()> {
        guard(|| {
            self.locked()?.mark_in_flight(ticket);
            Ok(())
        })
    }

    fn finish(&self, ticket: u64) -> PyResult<()> {
        guard(|| {
            self.locked()?.finish(ticket);
            Ok(())
        })
    }

    fn has_pending(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.has_pending()))
    }

    fn pending_count(&self) -> PyResult<usize> {
        guard(|| Ok(self.locked()?.pending_count()))
    }

    #[pyo3(signature = (current_id, incoming_id))]
    fn drop_if_other_account(&self, current_id: Option<&str>, incoming_id: &str) -> PyResult<bool> {
        guard(|| {
            let current = current_id
                .map(|raw| parse(raw, "current account id"))
                .transpose()?;
            let incoming = parse(incoming_id, "incoming account id")?;
            Ok(self
                .locked()?
                .drop_if_other_account(current.as_ref(), &incoming))
        })
    }

    fn clear(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.clear();
            Ok(())
        })
    }

    fn begin_fetch(&self, signed_in: bool) -> PyResult<Option<u64>> {
        guard(|| Ok(self.locked()?.begin_fetch(signed_in)))
    }

    fn accept_fetch(&self, token: u64, signed_in: bool) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.accept_fetch(token, signed_in)))
    }

    fn fetch_ticket(&self) -> PyResult<u64> {
        guard(|| Ok(self.locked()?.fetch_ticket()))
    }

    fn set_fetch_ticket(&self, ticket: u64) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_fetch_ticket(ticket);
            Ok(())
        })
    }
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = module.py();
    module.add("MAX_WORK_WINDOWS", MAX_WORK_WINDOWS)?;
    module.add("WORK_WINDOW_PRESETS_NOTE", WORK_WINDOW_PRESETS_NOTE)?;
    module.add("HOURS_REFUSED", HOURS_REFUSED)?;
    let mut rows = Vec::with_capacity(WORK_WINDOW_PRESETS.len());
    for &(label, days, start, end) in WORK_WINDOW_PRESETS {
        let day_list = PyList::new(py, days)?;
        let row = PyTuple::new(
            py,
            [
                label.into_pyobject(py)?.into_any(),
                day_list.into_any(),
                start.into_pyobject(py)?.into_any(),
                end.into_pyobject(py)?.into_any(),
            ],
        )?;
        rows.push(row.into_any());
    }
    module.add("WORK_WINDOW_PRESETS", PyTuple::new(py, rows)?)?;
    crate::export!(
        module,
        session_preferences_body,
        session_availability_body,
        session_follow_first_weekday,
        session_keep_setup_merged_prefs,
        session_flush_setup_action,
        session_prepare_save_availability,
        session_prepare_save_preferences,
        session_prepare_timer_split_preview,
        session_parse_timer_presets,
        session_parse_reminder_limits,
        session_parse_recovery_status,
    );
    module.add_class::<SetupQueueHandle>()?;
    module.add_class::<PreferencesQueueHandle>()?;
    Ok(())
}
