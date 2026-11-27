//! The kept reminder cards, the alarm queue and the block-alert decisions
//! (`flexweek_app::session::reminders`) for the Python window. `KeptReminders`, `KeptAlerts` and
//! `controller.py` hold the Qt objects, pass what they read in as JSON text, and say what the answers say.

use std::cell::RefCell;

use flexweek_app::session::reminders::{
    AlarmClock, AlarmQueue, AlarmSeen, AlertStrip, Cards, FetchApply, Membership, OpenWeek,
    block_notices, block_songs, cached_reminders_due, check_alerts_begin, due_alarm_plan,
    open_reminder_source, parked_or_cached_source, prepare_block_alerts, reminder_fetch_apply,
    reminder_fetch_begin, reminder_fetch_failed, reminder_fetch_gate, resolve_spotify_url,
    todays_reminder_blocks,
};
use flexweek_engine::desk::remind;
use flexweek_engine::{EngineError, ErrorKind};
use pyo3::exceptions::{PyAttributeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PySet, PySetMethods};
use serde_json::{Value, json};

use crate::desk::members_of;
use crate::{guard, raise};

fn parse(text: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("not JSON: {error}")))
}

fn object(text: &str, what: &str) -> PyResult<Value> {
    let value = parse(text)?;
    if value.is_object() {
        Ok(value)
    } else {
        Err(PyValueError::new_err(format!("{what} is a JSON object")))
    }
}

/// Today's blocks by reminder key: an object, or `null` when they are not known.
fn rows_of(text: &str) -> PyResult<Value> {
    let rows = parse(text)?;
    if rows.is_null() || rows.is_object() {
        Ok(rows)
    } else {
        Err(PyValueError::new_err(
            "today's rows are a JSON object or null",
        ))
    }
}

/// `null` is "not known" for today's blocks, as the window passes it.
fn known(rows: &Value) -> Option<&Value> {
    if rows.is_null() { None } else { Some(rows) }
}

#[pyclass(name = "ReminderCards", module = "flexweek_engine")]
pub struct PyCards {
    cards: Cards,
}

#[pymethods]
impl PyCards {
    #[new]
    fn new() -> Self {
        Self {
            cards: Cards::default(),
        }
    }

    fn has_cards(&self) -> bool {
        !self.cards.is_empty()
    }

    /// `notice` and `rows` (reminder key to block title, or null) as JSON text; answers
    /// `{"kept", "changed", "said"}`.
    fn add(&mut self, notice: &str, rows: &str, now_min: i64) -> PyResult<String> {
        guard(|| {
            let (notice, rows) = (object(notice, "a notice")?, rows_of(rows)?);
            let added = self
                .cards
                .add(&notice, known(&rows), now_min)
                .map_err(raise)?;
            Ok(json!({
                "kept": added.kept,
                "changed": added.changed,
                "said": added.said,
            })
            .to_string())
        })
    }

    fn cards(&self) -> PyResult<String> {
        guard(|| Ok(Value::Array(self.cards.visible()).to_string()))
    }

    fn snooze(&mut self, key: &str, now_min: i64) -> PyResult<bool> {
        guard(|| self.cards.snooze(key, now_min).map_err(raise))
    }

    fn close(&mut self, key: &str) -> PyResult<bool> {
        guard(|| Ok(self.cards.close(key)))
    }

    fn clear(&mut self) -> PyResult<bool> {
        guard(|| Ok(self.cards.clear()))
    }

    /// `rows` as in `add`; answers `{"changed", "said", "released"}`.
    fn sync(&mut self, rows: &str, now_min: i64) -> PyResult<String> {
        guard(|| {
            let rows = rows_of(rows)?;
            let told = self.cards.sync(known(&rows), now_min).map_err(raise)?;
            Ok(json!({
                "changed": told.changed,
                "said": told.said,
                "released": told.released,
            })
            .to_string())
        })
    }
}

#[pyclass(name = "AlarmQueue", module = "flexweek_engine")]
pub struct PyAlarmQueue {
    queue: AlarmQueue,
}

#[pymethods]
impl PyAlarmQueue {
    #[new]
    fn new() -> Self {
        Self {
            queue: AlarmQueue::default(),
        }
    }

    /// Whether the alarm (JSON text) rings now.
    fn enqueue(&mut self, alarm: &str) -> PyResult<bool> {
        guard(|| Ok(self.queue.enqueue(object(alarm, "an alarm")?)))
    }

    /// Answers `{"snoozed": {"id", "until_ms"} or null, "next": the alarm that rings next or null}`.
    fn finish(&mut self, snooze: bool, now_ms: i64) -> PyResult<String> {
        guard(|| {
            let finished = self.queue.finish(snooze, now_ms);
            let snoozed = finished
                .snoozed
                .map(|(id, until_ms)| json!({ "id": id, "until_ms": until_ms }));
            Ok(json!({ "snoozed": snoozed, "next": finished.next }).to_string())
        })
    }

    /// The ringing alarm as JSON text, or `null`.
    fn active(&self) -> PyResult<String> {
        guard(|| Ok(json!(self.queue.active()).to_string()))
    }

    fn waiting(&self) -> PyResult<String> {
        guard(|| Ok(json!(self.queue.waiting()).to_string()))
    }

    /// The kept block songs, by alarm id.
    fn songs(&self) -> PyResult<String> {
        guard(|| Ok(Value::Object(self.queue.songs()).to_string()))
    }

    fn clear(&mut self) -> PyResult<()> {
        guard(|| {
            self.queue.clear();
            Ok(())
        })
    }
}

#[pyclass(name = "AlertStrip", module = "flexweek_engine")]
pub struct PyStrip {
    strip: AlertStrip,
}

#[pymethods]
impl PyStrip {
    #[new]
    fn new() -> Self {
        Self {
            strip: AlertStrip::default(),
        }
    }

    /// `notices` is a JSON array. A notice that is not an object fails as Python's `.get` did.
    fn add(&mut self, notices: &str) -> PyResult<()> {
        guard(|| {
            let notices = array(notices, "notices")?;
            self.strip.add(&notices).map_err(raise)?;
            Ok(())
        })
    }

    fn clear(&mut self) -> PyResult<()> {
        guard(|| {
            self.strip.clear();
            Ok(())
        })
    }

    fn pending(&self) -> PyResult<usize> {
        guard(|| Ok(self.strip.pending()))
    }

    fn text(&self) -> PyResult<String> {
        guard(|| Ok(self.strip.text().to_string()))
    }

    /// Whether this drop left the strip empty, so the window can say the student is done.
    fn drop(&mut self) -> PyResult<bool> {
        guard(|| Ok(self.strip.drop().map_err(raise)?.handled))
    }
}

fn array(text: &str, what: &str) -> PyResult<Vec<Value>> {
    match parse(text)? {
        Value::Array(items) => Ok(items),
        _ => Err(PyValueError::new_err(format!("{what} are a JSON array"))),
    }
}

fn source_json(found: Option<(&Value, &Value)>) -> String {
    match found {
        None => "null".to_string(),
        Some((blocks, trace)) => json!({ "blocks": blocks, "trace": trace }).to_string(),
    }
}

/// The open week when it is today, else null. The window looks up a parked week only for null.
#[pyfunction]
fn session_open_reminder_source(
    week_start: &str,
    blocks: &str,
    trace: &str,
    today_monday: &str,
) -> PyResult<String> {
    guard(|| {
        let (week_start, blocks, trace) = (parse(week_start)?, parse(blocks)?, parse(trace)?);
        Ok(source_json(open_reminder_source(
            OpenWeek {
                week_start: week_start.as_str(),
                blocks: &blocks,
                trace: &trace,
            },
            today_monday,
        )))
    })
}

/// The parked week, else the cached week when it is today, else null.
#[pyfunction]
fn session_parked_or_cached_source(
    parked: &str,
    cached_week: &str,
    cached_blocks: &str,
    cached_trace: &str,
    today_monday: &str,
) -> PyResult<String> {
    guard(|| {
        let (parked, cached_week, cached_blocks, cached_trace) = (
            parse(parked)?,
            parse(cached_week)?,
            parse(cached_blocks)?,
            parse(cached_trace)?,
        );
        let found = parked_or_cached_source(
            &parked,
            cached_week.as_str(),
            &cached_blocks,
            &cached_trace,
            today_monday,
        )
        .map_err(raise)?;
        Ok(source_json(found))
    })
}

/// Today's blocks by reminder key.
#[pyfunction]
fn session_todays_reminder_blocks(blocks: &str, trace: &str, today_iso: &str) -> PyResult<String> {
    guard(|| {
        let (blocks, trace) = (parse(blocks)?, parse(trace)?);
        let rows = todays_reminder_blocks(&blocks, &trace, today_iso).map_err(raise)?;
        Ok(Value::Object(rows).to_string())
    })
}

/// `{"today_monday": string or null}`. Null means block reminders are off, so nothing is fetched.
#[pyfunction]
fn session_check_alerts_begin(prefs: &str, today_iso: &str) -> PyResult<String> {
    guard(|| {
        let prefs = parse(prefs)?;
        let monday = check_alerts_begin(&prefs, today_iso).map_err(raise)?;
        Ok(json!({ "today_monday": monday }).to_string())
    })
}

/// Whether a fetch reply should still announce today's blocks.
#[pyfunction]
fn session_cached_reminders_due(
    prefs: &str,
    today_iso: &str,
    today_monday: &str,
) -> PyResult<bool> {
    guard(|| {
        let prefs = parse(prefs)?;
        cached_reminders_due(&prefs, today_iso, today_monday).map_err(raise)
    })
}

/// Notices and the songs for blocks that are starting. Fired reminder keys are added to `fired`
/// before songs are read, and played song ids are added to `played`, as the sets were updated then.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn session_due_block_alerts(
    blocks: &str,
    trace: &str,
    today_iso: &str,
    now_min: i64,
    prefs: &str,
    fired: &Bound<'_, PyAny>,
    played: &Bound<'_, PyAny>,
) -> PyResult<String> {
    let (fired_text, fired_is_set) = members_of(fired)?;
    let (played_text, played_is_set) = members_of(played)?;
    let fired_type = fired.get_type().name()?.to_string();
    let played_type = played.get_type().name()?.to_string();
    let fired_set = fired.cast::<PySet>().ok();
    let played_set = played.cast::<PySet>().ok();
    let (blocks, trace, prefs) = (parse(blocks)?, parse(trace)?, parse(prefs)?);
    let (fired_members, played_members) = (parse(&fired_text)?, parse(&played_text)?);
    let prepared = guard(|| prepare_block_alerts(&blocks, &trace, &prefs).map_err(raise))?;
    let (notices, fired_keys) = guard(|| {
        block_notices(
            &prepared,
            today_iso,
            now_min,
            Membership {
                values: &fired_members,
                is_set: fired_is_set,
            },
        )
        .map_err(raise)
    })?;
    if !fired_keys.is_empty() {
        let Some(set) = fired_set else {
            return Err(PyAttributeError::new_err(format!(
                "'{fired_type}' object has no attribute 'add'"
            )));
        };
        for key in &fired_keys {
            set.add(key)?;
        }
    }
    let (songs, played_ids) = guard(|| {
        block_songs(
            &prepared,
            today_iso,
            now_min,
            Membership {
                values: &played_members,
                is_set: played_is_set,
            },
        )
        .map_err(raise)
    })?;
    let Some(set) = played_set else {
        return Err(PyAttributeError::new_err(format!(
            "'{played_type}' object has no attribute 'update'"
        )));
    };
    for id in &played_ids {
        set.add(id)?;
    }
    Ok(json!({ "notices": notices, "songs": songs }).to_string())
}

/// Whether to GET today's week, and the ticket that reply must carry.
#[pyfunction]
fn session_reminder_fetch_begin(
    fetching: &str,
    ticket: i64,
    today_monday: &str,
) -> PyResult<String> {
    guard(|| {
        let fetching = parse(fetching)?;
        let begun = reminder_fetch_begin(fetching.as_str(), ticket, today_monday).map_err(raise)?;
        Ok(json!({
            "send": begun.send,
            "fetching": begun.fetching,
            "ticket": begun.ticket,
        })
        .to_string())
    })
}

/// `ignore` leaves the in-flight fetch alone. `need_parked` is when the open week is not today.
#[pyfunction]
fn session_reminder_fetch_gate(
    token: i64,
    ticket: i64,
    account: &str,
    week_start: &str,
    today_monday: &str,
) -> PyResult<String> {
    guard(|| {
        let (account, week_start) = (parse(account)?, parse(week_start)?);
        let gate = reminder_fetch_gate(token, ticket, &account, &week_start, today_monday);
        Ok(json!({
            "kind": if gate.ignore { "ignore" } else { "continue" },
            "need_parked": gate.need_parked,
        })
        .to_string())
    })
}

/// Reuse a week already here, or keep the server's week and blocks.
#[pyfunction]
fn session_reminder_fetch_apply(
    need_parked: bool,
    parked: &str,
    data: &str,
    today_monday: &str,
) -> PyResult<String> {
    guard(|| {
        let (parked, data) = (parse(parked)?, parse(data)?);
        let reply =
            reminder_fetch_apply(need_parked, &parked, &data, today_monday).map_err(raise)?;
        Ok(match reply {
            FetchApply::Reuse => json!({ "kind": "reuse" }).to_string(),
            FetchApply::Cache { week, blocks } => {
                json!({ "kind": "cache", "week": week, "blocks": blocks }).to_string()
            }
        })
    })
}

/// Whether this failure is still the latest fetch, so the window clears the in-flight flag.
#[pyfunction]
fn session_reminder_fetch_failed(token: i64, ticket: i64) -> PyResult<bool> {
    guard(|| Ok(reminder_fetch_failed(token, ticket)))
}

/// Alarms due since the last look. `fired` gains the keys marked even when a later step fails.
/// `moment_of_day` is the caller's `datetime.fromisoformat`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn session_due_alarm_plan(
    prefs: &str,
    snoozed_songs: &str,
    today_iso: &str,
    weekday: i64,
    now_ms: i64,
    last_check_ms: Option<i64>,
    fired: &Bound<'_, PyAny>,
    snoozed: &str,
    moment_of_day: &Bound<'_, PyAny>,
) -> PyResult<String> {
    let fired_set = fired.cast::<PySet>().ok();
    let is_set = fired_set.is_some();
    let held_type = fired.get_type().name()?.to_string();
    let (members, _) = members_of(fired)?;
    let (prefs, songs, fired_members, snoozed) = (
        parse(prefs)?,
        parse(snoozed_songs)?,
        parse(&members)?,
        parse(snoozed)?,
    );
    let mut added = Vec::new();
    let failure: RefCell<Option<PyErr>> = RefCell::new(None);
    let mut convert = |hour: i64, minute: i64| -> flexweek_engine::EngineResult<i64> {
        let read = || -> PyResult<i64> {
            let kwargs = PyDict::new(moment_of_day.py());
            kwargs.set_item("hour", hour)?;
            kwargs.set_item("minute", minute)?;
            kwargs.set_item("second", 0)?;
            kwargs.set_item("microsecond", 0)?;
            let day = moment_of_day.call1((today_iso,))?;
            let due_at = day.call_method("replace", (), Some(&kwargs))?;
            let seconds = due_at.call_method0("timestamp")?.extract::<f64>()?;
            Ok(remind::millis_of(seconds))
        };
        read().map_err(|error| {
            *failure.borrow_mut() = Some(error);
            EngineError::value("local time")
        })
    };
    let outcome = guard(|| {
        Ok(due_alarm_plan(
            &prefs,
            &songs,
            AlarmClock {
                today_iso,
                weekday,
                now_ms,
                last_check_ms,
            },
            &mut AlarmSeen {
                fired: &fired_members,
                is_set,
                added: &mut added,
            },
            &snoozed,
            &mut convert,
        ))
    })?;
    if let Some(set) = fired_set {
        for key in &added {
            set.add(key)?;
        }
    }
    if let Some(error) = failure.into_inner() {
        return Err(error);
    }
    let plan = outcome.map_err(|mut error| {
        if !is_set
            && error.kind == ErrorKind::Attribute
            && error.message.ends_with("attribute 'add'")
        {
            error.message = format!("'{held_type}' object has no attribute 'add'");
        }
        raise(error)
    })?;
    Ok(json!({
        "queued": plan.queued,
        "snoozed_alarms": plan.snoozed,
        "last_alarm_check": plan.last_alarm_check,
    })
    .to_string())
}

/// A link handed in, or the Settings link when `value` is null. An invalid link is `""`.
#[pyfunction]
fn session_resolve_spotify_url(prefs: &str, value: &str) -> PyResult<String> {
    guard(|| {
        let (prefs, value) = (parse(prefs)?, parse(value)?);
        resolve_spotify_url(&prefs, &value).map_err(raise)
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyCards>()?;
    module.add_class::<PyAlarmQueue>()?;
    module.add_class::<PyStrip>()?;
    crate::export!(
        module,
        session_open_reminder_source,
        session_parked_or_cached_source,
        session_todays_reminder_blocks,
        session_check_alerts_begin,
        session_cached_reminders_due,
        session_due_block_alerts,
        session_reminder_fetch_begin,
        session_reminder_fetch_gate,
        session_reminder_fetch_apply,
        session_reminder_fetch_failed,
        session_due_alarm_plan,
        session_resolve_spotify_url,
    );
    Ok(())
}
