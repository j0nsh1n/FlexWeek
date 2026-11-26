//! The desktop session's view (`flexweek_app::session::views`, P4 slice 10A). The window still sends
//! the requests and emits its signals. JSON text crosses for a decision's world, its effect and a
//! fetch's reply; the fields tests assign come back as Python values.

use std::sync::{Mutex, MutexGuard};

use flexweek_app::session::views::{ViewReply, ViewState, ViewWorld, today_column};
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};
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

fn require<'a>(fields: &'a Map<String, Value>, name: &str, what: &str) -> PyResult<&'a Value> {
    fields
        .get(name)
        .ok_or_else(|| PyValueError::new_err(format!("{what}.{name} is missing")))
}

fn bool_field(fields: &Map<String, Value>, name: &str, what: &str) -> PyResult<bool> {
    match require(fields, name, what)? {
        Value::Bool(flag) => Ok(*flag),
        _ => Err(PyTypeError::new_err(format!("{what}.{name} is a bool"))),
    }
}

fn text_field(fields: &Map<String, Value>, name: &str, what: &str) -> PyResult<String> {
    match require(fields, name, what)? {
        Value::String(text) => Ok(text.clone()),
        _ => Err(PyTypeError::new_err(format!("{what}.{name} is a string"))),
    }
}

fn opt_text_field(fields: &Map<String, Value>, name: &str, what: &str) -> PyResult<Option<String>> {
    match require(fields, name, what)? {
        Value::Null => Ok(None),
        Value::String(text) => Ok(Some(text.clone())),
        _ => Err(PyTypeError::new_err(format!(
            "{what}.{name} is a string or null"
        ))),
    }
}

fn i64_field(fields: &Map<String, Value>, name: &str, what: &str) -> PyResult<i64> {
    match require(fields, name, what)? {
        Value::Number(number) => number
            .as_i64()
            .ok_or_else(|| PyTypeError::new_err(format!("{what}.{name} is an integer"))),
        _ => Err(PyTypeError::new_err(format!("{what}.{name} is an integer"))),
    }
}

struct OwnedWorld {
    signed_in: bool,
    account_id: Option<String>,
    week_start: String,
    today: String,
    busy: bool,
    held: bool,
    parked: bool,
}

impl OwnedWorld {
    fn parse(text: &str) -> PyResult<Self> {
        let fields = parse_object(text, "world")?;
        Ok(Self {
            signed_in: bool_field(&fields, "signed_in", "world")?,
            account_id: opt_text_field(&fields, "account_id", "world")?,
            week_start: text_field(&fields, "week_start", "world")?,
            today: text_field(&fields, "today", "world")?,
            busy: bool_field(&fields, "busy", "world")?,
            held: bool_field(&fields, "held", "world")?,
            parked: bool_field(&fields, "parked", "world")?,
        })
    }

    fn borrow(&self) -> ViewWorld<'_> {
        ViewWorld {
            signed_in: self.signed_in,
            account_id: self.account_id.as_deref(),
            week_start: &self.week_start,
            today: &self.today,
            busy: self.busy,
            held: self.held,
            parked: self.parked,
        }
    }
}

struct OwnedReply {
    kind: String,
    token: i64,
    asked: String,
    generation: i64,
    owner: String,
    account_id: Option<String>,
    data: Option<Value>,
    error: Option<String>,
}

impl OwnedReply {
    fn parse(text: &str) -> PyResult<Self> {
        let fields = parse_object(text, "reply")?;
        let data = match require(&fields, "data", "reply")? {
            Value::Null => None,
            value => Some(value.clone()),
        };
        Ok(Self {
            kind: text_field(&fields, "kind", "reply")?,
            token: i64_field(&fields, "token", "reply")?,
            asked: text_field(&fields, "asked", "reply")?,
            generation: i64_field(&fields, "gen", "reply")?,
            owner: text_field(&fields, "owner", "reply")?,
            account_id: opt_text_field(&fields, "account_id", "reply")?,
            data,
            error: opt_text_field(&fields, "error", "reply")?,
        })
    }

    fn borrow(&self) -> ViewReply<'_> {
        ViewReply {
            kind: &self.kind,
            token: self.token,
            asked: &self.asked,
            generation: self.generation,
            owner: &self.owner,
            account_id: self.account_id.as_deref(),
            data: self.data.as_ref(),
            error: self.error.as_deref(),
        }
    }
}

fn effect_text(
    result: Result<flexweek_app::session::views::ViewEffect, String>,
) -> PyResult<String> {
    result
        .map(|effect| effect.to_json().to_string())
        .map_err(PyValueError::new_err)
}

fn loads<'py>(py: Python<'py>, value: &Value) -> PyResult<Bound<'py, PyAny>> {
    py.import("json")?
        .getattr("loads")?
        .call1((value.to_string(),))
}

fn dumped(py: Python<'_>, value: &Bound<'_, PyAny>, what: &str) -> PyResult<Value> {
    let text: String = py
        .import("json")?
        .getattr("dumps")?
        .call1((value,))?
        .extract()?;
    serde_json::from_str(&text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn python_text(value: &Bound<'_, PyAny>) -> PyResult<String> {
    value.str()?.extract()
}

/// What the desktop is showing, and the month answers it has kept.
#[pyclass(name = "ViewState", module = "flexweek_engine")]
pub struct ViewStateHandle {
    state: Mutex<ViewState>,
}

impl ViewStateHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, ViewState>> {
        self.state
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the view state failed earlier"))
    }
}

#[pymethods]
impl ViewStateHandle {
    #[new]
    fn new(today: String) -> PyResult<Self> {
        guard(|| {
            Ok(Self {
                state: Mutex::new(ViewState::new(today)),
            })
        })
    }

    fn planner_view(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.planner_view.clone()))
    }

    fn set_planner_view(&self, value: String) -> PyResult<()> {
        guard(|| {
            self.locked()?.planner_view = value;
            Ok(())
        })
    }

    fn selected_day(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.selected_day.clone()))
    }

    fn set_selected_day(&self, value: String) -> PyResult<()> {
        guard(|| {
            self.locked()?.selected_day = value;
            Ok(())
        })
    }

    fn day_data<'py>(&self, py: Python<'py>) -> PyResult<Py<PyAny>> {
        guard(|| match &self.locked()?.day_data {
            Some(value) => Ok(loads(py, value)?.unbind()),
            None => Ok(py.None()),
        })
    }

    fn set_day_data(&self, py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<()> {
        guard(|| {
            self.locked()?.day_data = if value.is_none() {
                None
            } else {
                Some(dumped(py, value, "day data")?)
            };
            Ok(())
        })
    }

    fn selected_month(&self) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.selected_month.clone()))
    }

    fn set_selected_month(&self, value: Option<String>) -> PyResult<()> {
        guard(|| {
            self.locked()?.selected_month = value;
            Ok(())
        })
    }

    fn month_data<'py>(&self, py: Python<'py>) -> PyResult<Py<PyAny>> {
        guard(|| match &self.locked()?.month_data {
            Some(value) => Ok(loads(py, value)?.unbind()),
            None => Ok(py.None()),
        })
    }

    fn set_month_data(&self, py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<()> {
        guard(|| {
            self.locked()?.month_data = if value.is_none() {
                None
            } else {
                Some(dumped(py, value, "month data")?)
            };
            Ok(())
        })
    }

    fn first_weekday(&self) -> PyResult<i64> {
        guard(|| Ok(self.locked()?.first_weekday))
    }

    fn set_first_weekday(&self, value: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.first_weekday = value;
            Ok(())
        })
    }

    fn refollow_week(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.refollow_week))
    }

    fn set_refollow_week(&self, value: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.refollow_week = value;
            Ok(())
        })
    }

    fn armed_category(&self) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.armed_category.clone()))
    }

    fn set_armed_category(&self, value: Option<String>) -> PyResult<()> {
        guard(|| {
            self.locked()?.armed_category = value;
            Ok(())
        })
    }

    fn selected_block_id(&self) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.selected_block_id.clone()))
    }

    fn set_selected_block_id(&self, value: Option<String>) -> PyResult<()> {
        guard(|| {
            self.locked()?.selected_block_id = value;
            Ok(())
        })
    }

    fn selected_occurrence_day(&self) -> PyResult<Option<i64>> {
        guard(|| Ok(self.locked()?.selected_occurrence_day))
    }

    fn set_selected_occurrence_day(&self, value: Option<i64>) -> PyResult<()> {
        guard(|| {
            self.locked()?.selected_occurrence_day = value;
            Ok(())
        })
    }

    fn day_ticket(&self) -> PyResult<i64> {
        guard(|| Ok(self.locked()?.day_ticket))
    }

    fn set_day_ticket(&self, value: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.day_ticket = value;
            Ok(())
        })
    }

    fn month_ticket(&self) -> PyResult<i64> {
        guard(|| Ok(self.locked()?.month_ticket))
    }

    fn set_month_ticket(&self, value: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.month_ticket = value;
            Ok(())
        })
    }

    fn month_gen(&self) -> PyResult<i64> {
        guard(|| Ok(self.locked()?.month_gen))
    }

    fn set_month_gen(&self, value: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.month_gen = value;
            Ok(())
        })
    }

    fn month_data_gen(&self) -> PyResult<i64> {
        guard(|| Ok(self.locked()?.month_data_gen))
    }

    fn set_month_data_gen(&self, value: i64) -> PyResult<()> {
        guard(|| {
            self.locked()?.month_data_gen = value;
            Ok(())
        })
    }

    fn cache_mapping<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        guard(|| {
            let state = self.locked()?;
            let mapping = PyDict::new(py);
            for ((owner, month), value) in state.cached_months() {
                let key = PyTuple::new(py, [owner.as_str(), month.as_str()])?;
                mapping.set_item(key, loads(py, value)?)?;
            }
            Ok(mapping)
        })
    }

    fn replace_cache(&self, py: Python<'_>, mapping: &Bound<'_, PyAny>) -> PyResult<()> {
        guard(|| {
            let mut entries = std::collections::BTreeMap::new();
            for result in mapping.call_method0("items")?.try_iter()? {
                let pair = result?;
                let key = pair.get_item(0)?;
                let owner = python_text(&key.get_item(0)?)?;
                let month = python_text(&key.get_item(1)?)?;
                entries.insert(
                    (owner, month),
                    dumped(py, &pair.get_item(1)?, "month cache")?,
                );
            }
            self.locked()?.replace_cache(entries);
            Ok(())
        })
    }

    fn clear_cache(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.clear_cache();
            Ok(())
        })
    }

    fn insert_cache(
        &self,
        py: Python<'_>,
        owner: &str,
        month: &str,
        value: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        guard(|| {
            let parsed = dumped(py, value, "month cache")?;
            self.locked()?
                .insert_cache(owner.to_string(), month.to_string(), parsed);
            Ok(())
        })
    }

    fn remove_cache(&self, owner: &str, month: &str) -> PyResult<()> {
        guard(|| {
            self.locked()?.remove_cache(owner, month);
            Ok(())
        })
    }

    fn prefetch_members<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        guard(|| {
            let state = self.locked()?;
            let members = PyList::empty(py);
            for (owner, month) in state.prefetch_keys() {
                members.append(PyTuple::new(py, [owner.as_str(), month.as_str()])?)?;
            }
            Ok(members)
        })
    }

    fn clear_prefetch(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.clear_prefetch();
            Ok(())
        })
    }

    fn add_prefetch(&self, owner: &str, month: &str) -> PyResult<()> {
        guard(|| {
            self.locked()?
                .add_prefetch(owner.to_string(), month.to_string());
            Ok(())
        })
    }

    fn discard_prefetch(&self, owner: &str, month: &str) -> PyResult<()> {
        guard(|| {
            self.locked()?.discard_prefetch(owner, month);
            Ok(())
        })
    }

    fn invalidate_months(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.invalidate_months();
            Ok(())
        })
    }

    fn column_of(&self, iso_day: &str, week_start: &str) -> PyResult<Option<i64>> {
        guard(|| Ok(today_column(iso_day, week_start)))
    }

    fn ensure_selected_day(&self, week_start: &str) -> PyResult<()> {
        guard(|| {
            self.locked()?
                .ensure_selected_day(week_start)
                .map_err(PyValueError::new_err)
        })
    }

    fn set_view(&self, view: &str, world: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedWorld::parse(world)?;
            effect_text(self.locked()?.set_view(view, &owned.borrow()))
        })
    }

    fn open_day(&self, iso_day: &str, world: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedWorld::parse(world)?;
            effect_text(self.locked()?.open_day(iso_day, &owned.borrow()))
        })
    }

    fn open_month(&self, month: Option<&str>, world: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedWorld::parse(world)?;
            effect_text(self.locked()?.open_month(month, &owned.borrow()))
        })
    }

    fn shift_month(&self, amount: i64, world: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedWorld::parse(world)?;
            effect_text(self.locked()?.shift_month(amount, &owned.borrow()))
        })
    }

    fn follow_first_weekday(&self, new_weekday: i64, world: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedWorld::parse(world)?;
            effect_text(
                self.locked()?
                    .follow_first_weekday(new_weekday, &owned.borrow()),
            )
        })
    }

    fn follow_week(&self, world: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedWorld::parse(world)?;
            effect_text(self.locked()?.follow_week(&owned.borrow()))
        })
    }

    fn refresh(&self, world: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedWorld::parse(world)?;
            effect_text(self.locked()?.refresh(&owned.borrow()))
        })
    }

    fn fetch_day(&self, world: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedWorld::parse(world)?;
            Ok(self
                .locked()?
                .fetch_day(&owned.borrow())
                .to_json()
                .to_string())
        })
    }

    fn fetch_month(&self, world: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedWorld::parse(world)?;
            Ok(self
                .locked()?
                .fetch_month(&owned.borrow())
                .to_json()
                .to_string())
        })
    }

    fn prefetch(&self, world: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedWorld::parse(world)?;
            effect_text(self.locked()?.prefetch(&owned.borrow()))
        })
    }

    fn month_path(&self, month: &str) -> PyResult<String> {
        guard(|| Ok(self.locked()?.month_path(month)))
    }

    fn view_reply(&self, reply: &str) -> PyResult<String> {
        guard(|| {
            let owned = OwnedReply::parse(reply)?;
            Ok(self
                .locked()?
                .view_reply(owned.borrow())
                .to_json()
                .to_string())
        })
    }
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<ViewStateHandle>()?;
    Ok(())
}
