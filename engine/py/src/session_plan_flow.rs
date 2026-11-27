//! Plan continuation for the desktop window (`flexweek_app::session::plan_flow`). JSON text crosses
//! for each decision. The sets and the lost-time notes tests mutate in place stay Python objects.

use std::sync::{Mutex, MutexGuard};

use flexweek_app::session::plan_flow::{
    self, PendingStep, PlanFlow, PostPending, SolveCommitInput, SpreadNext, SpreadPhase,
};
use flexweek_app::session::unfinished::ClockNow;
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PySet};
use serde_json::{Map, Value};

use crate::{guard, raise};

fn parse(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn object(text: &str, what: &str) -> PyResult<Map<String, Value>> {
    match parse(text, what)? {
        Value::Object(fields) => Ok(fields),
        _ => Err(PyValueError::new_err(format!("{what} must be an object"))),
    }
}

fn require<'a>(fields: &'a Map<String, Value>, name: &str) -> PyResult<&'a Value> {
    fields
        .get(name)
        .ok_or_else(|| PyValueError::new_err(format!("missing field {name}")))
}

fn require_bool(fields: &Map<String, Value>, name: &str) -> PyResult<bool> {
    require(fields, name)?
        .as_bool()
        .ok_or_else(|| PyValueError::new_err(format!("{name} must be a bool")))
}

fn require_i64(fields: &Map<String, Value>, name: &str) -> PyResult<i64> {
    require(fields, name)?
        .as_i64()
        .ok_or_else(|| PyValueError::new_err(format!("{name} must be an integer")))
}

fn require_str<'a>(fields: &'a Map<String, Value>, name: &str) -> PyResult<&'a str> {
    require(fields, name)?
        .as_str()
        .ok_or_else(|| PyValueError::new_err(format!("{name} must be text")))
}

fn string_list(value: &Value, name: &str) -> PyResult<Vec<String>> {
    let items = value
        .as_array()
        .ok_or_else(|| PyValueError::new_err(format!("{name} must be a list")))?;
    items
        .iter()
        .map(|item| {
            item.as_str()
                .map(str::to_string)
                .ok_or_else(|| PyValueError::new_err(format!("{name} must be text")))
        })
        .collect()
}

fn loads<'py>(py: Python<'py>, value: &Value) -> PyResult<Bound<'py, PyAny>> {
    py.import("json")?
        .getattr("loads")?
        .call1((value.to_string(),))
}

fn string_ids(set: &Bound<'_, PySet>) -> PyResult<Vec<String>> {
    let mut ids = Vec::new();
    for value in set {
        ids.push(value.extract()?);
    }
    Ok(ids)
}

fn fill_set(set: &Bound<'_, PySet>, ids: &[String]) -> PyResult<()> {
    set.call_method0("clear")?;
    for id in ids {
        set.call_method1("add", (id,))?;
    }
    Ok(())
}

fn read_notes(py: Python<'_>, notes: &Py<PyDict>) -> PyResult<Map<String, Value>> {
    let mut map = Map::new();
    for (key, value) in notes.bind(py).iter() {
        let key: String = key.extract()?;
        let text: String = py
            .import("json")?
            .getattr("dumps")?
            .call1((value,))?
            .extract()?;
        let parsed = serde_json::from_str(&text)
            .map_err(|error| PyValueError::new_err(format!("needs_time: {error}")))?;
        map.insert(key, parsed);
    }
    Ok(map)
}

fn fill_notes(py: Python<'_>, notes: &Py<PyDict>, map: &Map<String, Value>) -> PyResult<()> {
    let bound = notes.bind(py);
    bound.call_method0("clear")?;
    for (key, value) in map {
        bound.set_item(key, loads(py, value)?)?;
    }
    Ok(())
}

fn optional_ids(value: &Bound<'_, PyAny>) -> PyResult<Option<Vec<String>>> {
    if value.is_none() {
        return Ok(None);
    }
    let mut ids = Vec::new();
    for item in value.try_iter()? {
        ids.push(item?.extract()?);
    }
    Ok(Some(ids))
}

fn clock_of(value: &Value) -> PyResult<ClockNowOwned> {
    let fields = value
        .as_object()
        .ok_or_else(|| PyValueError::new_err("now must be an object"))?;
    Ok(ClockNowOwned {
        today: require_str(fields, "today")?.to_string(),
        hour: require_i64(fields, "hour")?,
        minute: require_i64(fields, "minute")?,
        second: require_i64(fields, "second")?,
        microsecond: require_i64(fields, "microsecond")?,
    })
}

struct ClockNowOwned {
    today: String,
    hour: i64,
    minute: i64,
    second: i64,
    microsecond: i64,
}

impl ClockNowOwned {
    fn borrow(&self) -> ClockNow<'_> {
        ClockNow {
            today: &self.today,
            hour: self.hour,
            minute: self.minute,
            second: self.second,
            microsecond: self.microsecond,
        }
    }
}

fn steps_json(steps: &[PendingStep]) -> String {
    Value::Array(steps.iter().map(PendingStep::to_json).collect()).to_string()
}

struct Store {
    plan_after_save: Py<PySet>,
    plan_after_load: Py<PySet>,
    split_whole: Py<PySet>,
    split_planned: Py<PySet>,
    seen_unfinished: Py<PySet>,
    needs_time: Py<PyDict>,
    replan_after_save: bool,
    replan_after_load: bool,
    fresh_plan: bool,
    allow_split_pending: Option<String>,
    spread_after_save: Option<SpreadNext>,
}

impl Store {
    fn read(&self, py: Python<'_>) -> PyResult<PlanFlow> {
        Ok(PlanFlow {
            plan_after_save: string_ids(self.plan_after_save.bind(py))?,
            plan_after_load: string_ids(self.plan_after_load.bind(py))?,
            split_whole: string_ids(self.split_whole.bind(py))?,
            split_planned: string_ids(self.split_planned.bind(py))?,
            replan_after_save: self.replan_after_save,
            replan_after_load: self.replan_after_load,
            spread_after_save: self.spread_after_save.clone(),
            allow_split_pending: self.allow_split_pending.clone(),
            fresh_plan: self.fresh_plan,
            seen_unfinished: string_ids(self.seen_unfinished.bind(py))?,
            needs_time: read_notes(py, &self.needs_time)?,
        })
    }

    fn write(&mut self, py: Python<'_>, flow: &PlanFlow) -> PyResult<()> {
        fill_set(self.plan_after_save.bind(py), &flow.plan_after_save)?;
        fill_set(self.plan_after_load.bind(py), &flow.plan_after_load)?;
        fill_set(self.split_whole.bind(py), &flow.split_whole)?;
        fill_set(self.split_planned.bind(py), &flow.split_planned)?;
        fill_set(self.seen_unfinished.bind(py), &flow.seen_unfinished)?;
        fill_notes(py, &self.needs_time, &flow.needs_time)?;
        self.replan_after_save = flow.replan_after_save;
        self.replan_after_load = flow.replan_after_load;
        self.fresh_plan = flow.fresh_plan;
        self.allow_split_pending = flow.allow_split_pending.clone();
        self.spread_after_save = flow.spread_after_save.clone();
        Ok(())
    }
}

/// The plan flags `NativeSession` used to keep itself. Getters hand back the same set or dict the
/// window assigned, so an in-place edit is still there on the next read.
#[pyclass(name = "PlanFlow", module = "flexweek_engine")]
struct PlanFlowHandle {
    store: Mutex<Store>,
}

impl PlanFlowHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, Store>> {
        self.store
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the plan flow failed earlier"))
    }

    fn update<T>(
        &self,
        py: Python<'_>,
        body: impl FnOnce(&mut PlanFlow) -> Result<T, flexweek_engine::EngineError>,
    ) -> PyResult<T> {
        let mut store = self.locked()?;
        let mut flow = store.read(py)?;
        let result = body(&mut flow).map_err(raise)?;
        store.write(py, &flow)?;
        Ok(result)
    }
}

#[pymethods]
impl PlanFlowHandle {
    #[new]
    fn new(py: Python<'_>) -> PyResult<Self> {
        guard(|| {
            Ok(Self {
                store: Mutex::new(Store {
                    plan_after_save: PySet::new(py, Vec::<String>::new())?.unbind(),
                    plan_after_load: PySet::new(py, Vec::<String>::new())?.unbind(),
                    split_whole: PySet::new(py, Vec::<String>::new())?.unbind(),
                    split_planned: PySet::new(py, Vec::<String>::new())?.unbind(),
                    seen_unfinished: PySet::new(py, Vec::<String>::new())?.unbind(),
                    needs_time: PyDict::new(py).unbind(),
                    replan_after_save: false,
                    replan_after_load: false,
                    fresh_plan: false,
                    allow_split_pending: None,
                    spread_after_save: None,
                }),
            })
        })
    }

    fn plan_after_save<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PySet>> {
        guard(|| Ok(self.locked()?.plan_after_save.bind(py).clone()))
    }

    fn set_plan_after_save(&self, value: Bound<'_, PySet>) -> PyResult<()> {
        guard(|| {
            self.locked()?.plan_after_save = value.unbind();
            Ok(())
        })
    }

    fn plan_after_load<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PySet>> {
        guard(|| Ok(self.locked()?.plan_after_load.bind(py).clone()))
    }

    fn set_plan_after_load(&self, value: Bound<'_, PySet>) -> PyResult<()> {
        guard(|| {
            self.locked()?.plan_after_load = value.unbind();
            Ok(())
        })
    }

    fn split_whole<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PySet>> {
        guard(|| Ok(self.locked()?.split_whole.bind(py).clone()))
    }

    fn set_split_whole(&self, value: Bound<'_, PySet>) -> PyResult<()> {
        guard(|| {
            self.locked()?.split_whole = value.unbind();
            Ok(())
        })
    }

    fn split_planned<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PySet>> {
        guard(|| Ok(self.locked()?.split_planned.bind(py).clone()))
    }

    fn set_split_planned(&self, value: Bound<'_, PySet>) -> PyResult<()> {
        guard(|| {
            self.locked()?.split_planned = value.unbind();
            Ok(())
        })
    }

    fn seen_unfinished<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PySet>> {
        guard(|| Ok(self.locked()?.seen_unfinished.bind(py).clone()))
    }

    fn set_seen_unfinished(&self, value: Bound<'_, PySet>) -> PyResult<()> {
        guard(|| {
            self.locked()?.seen_unfinished = value.unbind();
            Ok(())
        })
    }

    fn needs_time<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        guard(|| Ok(self.locked()?.needs_time.bind(py).clone()))
    }

    fn set_needs_time(&self, value: Bound<'_, PyDict>) -> PyResult<()> {
        guard(|| {
            self.locked()?.needs_time = value.unbind();
            Ok(())
        })
    }

    fn replan_after_save(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.replan_after_save))
    }

    fn set_replan_after_save(&self, value: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.replan_after_save = value;
            Ok(())
        })
    }

    fn replan_after_load(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.replan_after_load))
    }

    fn set_replan_after_load(&self, value: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.replan_after_load = value;
            Ok(())
        })
    }

    fn fresh_plan(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.fresh_plan))
    }

    fn set_fresh_plan(&self, value: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.fresh_plan = value;
            Ok(())
        })
    }

    fn allow_split_pending(&self) -> PyResult<Option<String>> {
        guard(|| Ok(self.locked()?.allow_split_pending.clone()))
    }

    fn set_allow_split_pending(&self, value: Option<String>) -> PyResult<()> {
        guard(|| {
            self.locked()?.allow_split_pending = value;
            Ok(())
        })
    }

    fn spread_after_save(&self) -> PyResult<Option<(String, i64, String)>> {
        guard(|| {
            Ok(self
                .locked()?
                .spread_after_save
                .clone()
                .map(|spread| (spread.assignment_id, spread.session_min, spread.from_date)))
        })
    }

    fn set_spread_after_save(&self, value: Option<(String, i64, String)>) -> PyResult<()> {
        guard(|| {
            self.locked()?.spread_after_save =
                value.map(|(assignment_id, session_min, from_date)| SpreadNext {
                    assignment_id,
                    session_min,
                    from_date,
                });
            Ok(())
        })
    }

    fn post_pending_ok(&self, py: Python<'_>, payload: &str) -> PyResult<String> {
        guard(|| {
            let fields = object(payload, "saved answer")?;
            let input = PostPending {
                planned: require(&fields, "planned")?.clone(),
                open_week: require(&fields, "open_week")?.clone(),
                destination: require(&fields, "destination")?.clone(),
                repeat_notice: require(&fields, "repeat_notice")?.clone(),
                point_id: require(&fields, "point_id")?.clone(),
                doubled: require(&fields, "doubled")?.clone(),
                refollow: require_bool(&fields, "refollow")?,
                wrote_open: require_bool(&fields, "wrote_open")?,
                first_weekday: require_i64(&fields, "first_weekday")?,
            };
            let steps = self.update(py, |flow| flow.post_pending_ok(&input))?;
            Ok(steps_json(&steps))
        })
    }

    fn post_pending_err(&self, py: Python<'_>) -> PyResult<()> {
        guard(|| {
            self.update(py, |flow| {
                flow.post_pending_err();
                Ok(())
            })
        })
    }

    fn plan_after_save_ids(
        &self,
        py: Python<'_>,
        blocks: &str,
        assignment_id: &str,
    ) -> PyResult<()> {
        guard(|| {
            let blocks = parse(blocks, "blocks")?;
            let blocks = blocks
                .as_array()
                .ok_or_else(|| PyValueError::new_err("blocks must be a list"))?;
            self.update(py, |flow| flow.plan_after_save(blocks, assignment_id))?;
            Ok(())
        })
    }

    fn plan_waiting_for_load(&self, py: Python<'_>) -> PyResult<String> {
        guard(|| {
            let steps = self.update(py, |flow| Ok(flow.plan_waiting_for_load()))?;
            Ok(steps_json(&steps))
        })
    }

    fn solve_apply_commit(
        &self,
        py: Python<'_>,
        payload: &str,
        only: &Bound<'_, PyAny>,
    ) -> PyResult<String> {
        guard(|| {
            let fields = object(payload, "plan answer")?;
            let dirty_assignments =
                string_list(require(&fields, "dirty_assignments")?, "dirty_assignments")?;
            let targets = string_list(require(&fields, "targets")?, "targets")?;
            let input = SolveCommitInput {
                needs_time: require(&fields, "needs_time")?.clone(),
                split_note: require(&fields, "split_note")?.clone(),
                changed: require_bool(&fields, "changed")?,
                placed_note: require_str(&fields, "placed_note")?.to_string(),
                placed_where: require(&fields, "placed_where")?.clone(),
                dirty: require_bool(&fields, "dirty")?,
                dirty_assignments: &dirty_assignments,
                prior_updates: require(&fields, "prior_updates")?.clone(),
                targets: &targets,
                join: require_bool(&fields, "join")?,
                only_is_some: !only.is_none(),
                step_id: require_str(&fields, "step_id")?.to_string(),
            };
            let commit = self.update(py, |flow| flow.solve_apply_commit(&input))?;
            Ok(commit.to_json().to_string())
        })
    }

    fn solve_err_rollback(
        &self,
        py: Python<'_>,
        payload: &str,
        new_left: &Bound<'_, PyAny>,
    ) -> PyResult<String> {
        guard(|| {
            let fields = object(payload, "rollback")?;
            let blocks = parse_blocks(require(&fields, "blocks")?)?;
            let left = optional_ids(new_left)?;
            let dirty = require(&fields, "dirty_before")?.clone();
            let rollback = self.update(py, |flow| {
                flow.solve_err_rollback(&blocks, left.as_deref(), &dirty)
            })?;
            Ok(rollback.to_json().to_string())
        })
    }

    fn consume_plan_review<'py>(&self, py: Python<'py>, trace: &str) -> PyResult<Py<PyAny>> {
        guard(|| {
            let parsed = parse(trace, "trace")?;
            let trace = if parsed.is_null() { None } else { Some(parsed) };
            let review = self.update(py, |flow| Ok(flow.consume_plan_review(trace.as_ref())))?;
            match review {
                Some(value) => Ok(loads(py, &value)?.unbind()),
                None => Ok(py.None()),
            }
        })
    }

    fn consume_unfinished(
        &self,
        py: Python<'_>,
        week_start: &str,
        items: &str,
    ) -> PyResult<String> {
        guard(|| {
            let items = parse(items, "items")?;
            let items = items
                .as_array()
                .ok_or_else(|| PyValueError::new_err("items must be a list"))?;
            let shown = self.update(py, |flow| Ok(flow.consume_unfinished(week_start, items)))?;
            Ok(Value::Array(shown).to_string())
        })
    }

    fn preview_spread_stop(&self, py: Python<'_>, item: &str) -> PyResult<bool> {
        guard(|| {
            let parsed = parse(item, "assignment")?;
            let item = if parsed.is_null() { None } else { Some(parsed) };
            self.update(py, |flow| flow.preview_spread_stop(item.as_ref()))
        })
    }

    #[pyo3(signature = (made, plan_ids, ok=None))]
    fn confirm_spread_transition(
        &self,
        py: Python<'_>,
        made: &str,
        plan_ids: &str,
        ok: Option<bool>,
    ) -> PyResult<()> {
        guard(|| {
            let made = string_list(&parse(made, "made")?, "made")?;
            let plan_ids = string_list(&parse(plan_ids, "plan_ids")?, "plan_ids")?;
            let phase = match ok {
                None => SpreadPhase::Stage,
                Some(ok) => SpreadPhase::Finish { ok },
            };
            self.update(py, |flow| {
                flow.confirm_spread_transition(&made, &plan_ids, phase);
                Ok(())
            })
        })
    }
}

fn parse_blocks(value: &Value) -> PyResult<Vec<Value>> {
    value
        .as_array()
        .cloned()
        .ok_or_else(|| PyValueError::new_err("blocks must be a list"))
}

fn account_id(value: &Value) -> PyResult<Option<Value>> {
    if value.is_null() {
        return Ok(None);
    }
    let fields = value
        .as_object()
        .ok_or_else(|| PyTypeError::new_err("account id must be read from the account"))?;
    fields
        .get("id")
        .cloned()
        .map(Some)
        .ok_or_else(|| PyValueError::new_err("missing field id"))
}

#[pyfunction]
fn session_stored_week_rows(
    stored_parts: &str,
    revision: &str,
    week_start: &str,
) -> PyResult<Vec<(String, i64)>> {
    guard(|| {
        plan_flow::stored_week_rows(
            &parse(stored_parts, "stored parts")?,
            &parse(revision, "revision")?,
            week_start,
        )
        .map_err(raise)
    })
}

#[pyfunction]
fn session_fail_words(planning: bool, status: i64, message: &str) -> PyResult<String> {
    guard(|| Ok(plan_flow::fail_words(planning, status, message)))
}

#[pyfunction]
fn session_touch_settle(payload: &str) -> PyResult<String> {
    guard(|| {
        let fields = object(payload, "touch")?;
        let blocks = parse_blocks(require(&fields, "blocks")?)?;
        let assignments = require(&fields, "assignments")?
            .as_object()
            .ok_or_else(|| PyValueError::new_err("assignments must be an object"))?;
        let homework = parse_blocks(require(&fields, "homework")?)?;
        let week_start = require_str(&fields, "week_start")?;
        let keep = string_list(require(&fields, "keep")?, "keep")?;
        let selected = require(&fields, "selected_block_id")?;
        let selected =
            if selected.is_null() {
                None
            } else {
                Some(selected.as_str().ok_or_else(|| {
                    PyValueError::new_err("selected_block_id must be text or null")
                })?)
            };
        let now = clock_of(require(&fields, "now")?)?;
        let needs = require(&fields, "needs_time")?
            .as_object()
            .ok_or_else(|| PyValueError::new_err("needs_time must be an object"))?;
        let settled = plan_flow::touch_settle(
            &blocks,
            assignments,
            &homework,
            week_start,
            &keep,
            selected,
            &now.borrow(),
            needs,
        )
        .map_err(raise)?;
        Ok(settled.to_json().to_string())
    })
}

#[pyfunction]
fn session_plan_notes<'py>(py: Python<'py>, trace: &str, needs_time: &str) -> PyResult<Py<PyAny>> {
    guard(|| {
        let trace = parse(trace, "trace")?;
        let trace = if trace.is_null() { None } else { Some(trace) };
        let needs = parse(needs_time, "needs_time")?;
        let needs = needs
            .as_object()
            .ok_or_else(|| PyValueError::new_err("needs_time must be an object"))?;
        match plan_flow::plan_notes(trace.as_ref(), needs) {
            Some(value) => Ok(loads(py, &value)?.unbind()),
            None => Ok(py.None()),
        }
    })
}

#[pyfunction]
fn session_delete_homework_guard(payload: &str) -> PyResult<String> {
    guard(|| {
        let fields = object(payload, "delete")?;
        let account = account_id(require(&fields, "account")?)?;
        let assignment_id = require_str(&fields, "assignment_id")?;
        let item = require(&fields, "item")?;
        let item = if item.is_null() { None } else { Some(item) };
        let decision = plan_flow::delete_homework_guard(
            account.as_ref(),
            assignment_id,
            item,
            require_bool(&fields, "conflict")?,
            require_bool(&fields, "busy")?,
            require_bool(&fields, "dirty")?,
            require(&fields, "pending_save")?,
        )
        .map_err(raise)?;
        Ok(decision.to_json().to_string())
    })
}

#[pyfunction]
fn session_did_these_ids(assignments: &str, assignment_ids: &str) -> PyResult<Vec<String>> {
    guard(|| {
        let assignments = parse(assignments, "assignments")?;
        let assignments = assignments
            .as_object()
            .ok_or_else(|| PyValueError::new_err("assignments must be an object"))?;
        let ids = string_list(&parse(assignment_ids, "assignment_ids")?, "assignment_ids")?;
        Ok(plan_flow::did_these_ids(assignments, &ids))
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PlanFlowHandle>()?;
    crate::export!(
        module,
        session_stored_week_rows,
        session_fail_words,
        session_touch_settle,
        session_plan_notes,
        session_delete_homework_guard,
        session_did_these_ids,
    );
    Ok(())
}
