//! Python bindings for the Add and Edit homework sheet (`flexweek_app::views::sheet_homework`).
//!
//! Every exported function and method body runs inside `guard(` and refuses wrong-shaped input with
//! `ValueError` or `TypeError`. The session facts the sheet judges against cross as one JSON text per
//! call (`env`); the done-minutes figure is read through the session's own method, only when asked.

use std::cell::RefCell;
use std::sync::{Mutex, MutexGuard};

use flexweek_app::views::sheet_homework::{
    self as sheet, DAYS_AHEAD, ENERGIES, Env, HomeworkDraft, OpenOptions, PROMPTS, SPREAD_CHOICES,
    STEPS, TITLE_PROBLEM, TYPES, WHEN_CHOICES,
};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyModule, PyString};
use serde_json::{Map, Value};

use crate::{guard, raise};

fn parse_json(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn object_of(value: Value, what: &str) -> PyResult<Map<String, Value>> {
    match value {
        Value::Object(map) => Ok(map),
        _ => Err(PyValueError::new_err(format!(
            "{what} must be a JSON object"
        ))),
    }
}

fn opt_text(map: &Map<String, Value>, key: &str) -> PyResult<Option<String>> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) => Ok(Some(text.clone())),
        Some(_) => Err(PyTypeError::new_err(format!("{key} must be text or null"))),
    }
}

fn opt_int(map: &Map<String, Value>, key: &str) -> PyResult<Option<i64>> {
    match map.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => match value.as_i64() {
            Some(found) if value.is_i64() => Ok(Some(found)),
            _ => Err(PyTypeError::new_err(format!(
                "{key} must be an integer or null"
            ))),
        },
    }
}

/// What the open session knows, as `read_env` finds it.
struct EnvData {
    week_start: Option<String>,
    blocks: Vec<Value>,
    preferences: Value,
    selected_day: String,
}

fn read_env(text: &str) -> PyResult<EnvData> {
    let map = object_of(parse_json(text, "env")?, "env")?;
    let blocks = match map.get("blocks") {
        None | Some(Value::Null) => Vec::new(),
        Some(Value::Array(items)) => items.clone(),
        Some(_) => return Err(PyValueError::new_err("blocks must be a JSON list")),
    };
    Ok(EnvData {
        week_start: opt_text(&map, "week_start")?,
        blocks,
        preferences: map.get("preferences").cloned().unwrap_or(Value::Null),
        selected_day: opt_text(&map, "selected_day")?.unwrap_or_default(),
    })
}

fn read_options(text: &str) -> PyResult<OpenOptions> {
    let map = object_of(parse_json(text, "options")?, "options")?;
    Ok(OpenOptions {
        category: opt_text(&map, "category")?,
        due: opt_text(&map, "due")?,
        when: opt_text(&map, "when")?,
        when_day: opt_int(&map, "when_day")?,
        when_time: opt_text(&map, "when_time")?,
        day: opt_int(&map, "day")?,
        start_min: opt_int(&map, "start_min")?,
        end_min: opt_int(&map, "end_min")?,
        estimate_min: opt_int(&map, "estimate_min")?,
    })
}

/// The session's `done_minutes_for`, called with a homework id. A Python error it raises is kept in
/// `failed` and raised again once the sheet's own call returns.
fn ask_done(
    done_for: &Option<Py<PyAny>>,
    failed: &RefCell<Option<PyErr>>,
) -> Option<impl Fn(&Value) -> EngineResult<i64>> {
    let found = done_for.as_ref()?;
    Some(move |id: &Value| -> EngineResult<i64> {
        Python::attach(|py| {
            let given: Py<PyAny> = match id {
                Value::String(text) => PyString::new(py, text).into_any().unbind(),
                _ => py.None(),
            };
            found
                .call1(py, (given,))
                .and_then(|answer| answer.extract::<i64>(py))
                .map_err(|error| {
                    let message = error.to_string();
                    *failed.borrow_mut() = Some(error);
                    EngineError {
                        kind: ErrorKind::Value,
                        message,
                    }
                })
        })
    })
}

#[pyclass(name = "HomeworkDraftCore", module = "flexweek_engine")]
pub struct HomeworkDraftHandle {
    state: Mutex<HomeworkDraft>,
    done_for: Option<Py<PyAny>>,
}

impl HomeworkDraftHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, HomeworkDraft>> {
        self.state
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the homework sheet failed earlier"))
    }

    /// Runs `work` with the session facts in `env_text`, then raises what `done_minutes_for` raised.
    fn with_env<T>(
        &self,
        env_text: &str,
        work: impl FnOnce(&mut HomeworkDraft, &Env) -> EngineResult<T>,
    ) -> PyResult<T> {
        let data = read_env(env_text)?;
        let failed = RefCell::new(None);
        let done = ask_done(&self.done_for, &failed);
        let env = Env {
            week_start: data.week_start.as_deref(),
            blocks: &data.blocks,
            preferences: &data.preferences,
            selected_day: &data.selected_day,
            done_minutes_for: done
                .as_ref()
                .map(|found| found as &dyn Fn(&Value) -> EngineResult<i64>),
        };
        let outcome = work(&mut *self.locked()?, &env);
        if let Some(error) = failed.take() {
            return Err(error);
        }
        outcome.map_err(raise)
    }
}

#[pymethods]
impl HomeworkDraftHandle {
    #[new]
    #[pyo3(signature = (env, stamp, fresh_id, assignment, options, done_for=None))]
    fn new(
        env: &str,
        stamp: &str,
        fresh_id: &str,
        assignment: &str,
        options: &str,
        done_for: Option<Py<PyAny>>,
    ) -> PyResult<Self> {
        guard(|| {
            let data = read_env(env)?;
            let existing = parse_json(assignment, "assignment")?;
            let failed = RefCell::new(None);
            let opened = {
                let done = ask_done(&done_for, &failed);
                let facts = Env {
                    week_start: data.week_start.as_deref(),
                    blocks: &data.blocks,
                    preferences: &data.preferences,
                    selected_day: &data.selected_day,
                    done_minutes_for: done
                        .as_ref()
                        .map(|found| found as &dyn Fn(&Value) -> EngineResult<i64>),
                };
                HomeworkDraft::open(
                    &facts,
                    stamp,
                    fresh_id,
                    (!existing.is_null()).then_some(&existing),
                    &read_options(options)?,
                )
            };
            if let Some(error) = failed.take() {
                return Err(error);
            }
            Ok(Self {
                state: Mutex::new(opened.map_err(raise)?),
                done_for,
            })
        })
    }

    fn read_clock(&self, stamp: &str) -> PyResult<()> {
        guard(|| self.locked()?.read_clock(stamp).map_err(raise))
    }

    fn follow_week(&self, env: &str, fresh_day: i64) -> PyResult<()> {
        guard(|| self.with_env(env, |draft, facts| draft.follow_week(facts, fresh_day)))
    }

    fn dirty(&self) -> PyResult<bool> {
        guard(|| self.locked()?.dirty().map_err(raise))
    }

    fn estimate(&self) -> PyResult<i64> {
        guard(|| Ok(self.locked()?.estimate()))
    }

    fn set(&self, env: &str, name: &str, value: &str) -> PyResult<()> {
        guard(|| {
            let given = parse_json(value, "value")?;
            self.with_env(env, |draft, facts| draft.set(facts, name, &given))
        })
    }

    fn use_picked(&self, env: &str, day: i64, start: &str) -> PyResult<()> {
        guard(|| self.with_env(env, |draft, facts| draft.use_picked(facts, day, start)))
    }

    fn add_link(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.add_link();
            Ok(())
        })
    }

    fn remove_link(&self, index: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.remove_link(index);
            Ok(())
        })
    }

    fn add_check(&self, fresh_id: &str) -> PyResult<()> {
        guard(|| {
            self.locked()?.add_check(fresh_id);
            Ok(())
        })
    }

    fn toggle_check(&self, index: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.toggle_check(index);
            Ok(())
        })
    }

    fn remove_check(&self, index: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.remove_check(index);
            Ok(())
        })
    }

    fn back(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.back();
            Ok(())
        })
    }

    fn goto(&self, index: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.goto(index);
            Ok(())
        })
    }

    fn advance(&self, env: &str) -> PyResult<bool> {
        guard(|| self.with_env(env, |draft, facts| draft.advance(facts)))
    }

    fn candidate(&self, env: &str) -> PyResult<Option<String>> {
        guard(|| {
            let made = self.with_env(env, |draft, facts| draft.candidate(facts))?;
            Ok(made.map(|found| found.to_string()))
        })
    }

    fn form(&self, env: &str) -> PyResult<String> {
        guard(|| {
            let shown = self.with_env(env, |draft, facts| draft.form(facts))?;
            Ok(shown.to_string())
        })
    }

    fn spread_shown(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.spread_shown()))
    }

    fn spread_requested(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.spread_requested()))
    }

    fn spread_plan(&self, env: &str) -> PyResult<String> {
        guard(|| {
            let plan = self.with_env(env, |draft, facts| draft.spread_plan(facts))?;
            Ok(plan.to_string())
        })
    }

    fn spread_figures(&self, env: &str) -> PyResult<(i64, String, String)> {
        guard(|| {
            let (session_min, from_date, sessions) =
                self.with_env(env, |draft, facts| draft.spread_figures(facts))?;
            Ok((session_min, from_date, Value::Array(sessions).to_string()))
        })
    }

    fn field(&self, name: &str) -> PyResult<String> {
        guard(|| Ok(self.locked()?.field(name).map_err(raise)?.to_string()))
    }
}

#[pyfunction]
fn views_homework_quarter_hours(step: i64) -> PyResult<String> {
    guard(|| Ok(sheet::quarter_hours(step).map_err(raise)?.to_string()))
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("VIEWS_HOMEWORK_STEPS", STEPS.to_vec())?;
    module.add("VIEWS_HOMEWORK_PROMPTS", PROMPTS.to_vec())?;
    module.add("VIEWS_HOMEWORK_TITLE_PROBLEM", TITLE_PROBLEM)?;
    module.add("VIEWS_HOMEWORK_TYPES", TYPES.to_vec())?;
    module.add("VIEWS_HOMEWORK_ENERGIES", ENERGIES.to_vec())?;
    module.add("VIEWS_HOMEWORK_WHEN_CHOICES", WHEN_CHOICES.to_vec())?;
    module.add("VIEWS_HOMEWORK_SPREAD_CHOICES", SPREAD_CHOICES.to_vec())?;
    module.add("VIEWS_HOMEWORK_DAYS_AHEAD", DAYS_AHEAD)?;
    module.add_class::<HomeworkDraftHandle>()?;
    crate::export!(module, views_homework_quarter_hours);
    Ok(())
}
