//! Setup's write queue and the preference request bodies for the Python window (`flexweek_app::session::
//! preferences`, 2.0.0 plan P4 group 8). JSON text crosses, as with `NativeCore`.

use std::sync::{Mutex, MutexGuard};

use flexweek_app::session::preferences::{
    SetupQueue, availability_body, follow_first_weekday, preferences_body,
};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use serde_json::{Map, Value};

use crate::guard;

fn parse(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn parse_object(text: &str, what: &str) -> PyResult<Map<String, Value>> {
    match parse(text, what)? {
        Value::Object(fields) => Ok(fields),
        _ => Err(PyValueError::new_err(format!("{what} is an object"))),
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

/// What setup kept and has not yet written. `next` answers the step to send as JSON text.
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

    fn next(&self, signed_in: bool, busy: bool, has_preferences: bool) -> PyResult<String> {
        guard(|| {
            let step = self.locked()?.next(signed_in, busy, has_preferences);
            Ok(step.to_json().to_string())
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

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        session_preferences_body,
        session_availability_body,
        session_follow_first_weekday
    );
    module.add_class::<SetupQueueHandle>()?;
    Ok(())
}
