//! The kept reminder cards and the alarm queue (`flexweek_app::session::reminders`) for the Python
//! window: `desktop/native/kept_alerts.py`'s `KeptReminders` and `controller.py`'s alarm queue hold a
//! `ReminderCards` and an `AlarmQueue`, pass what they read in as JSON text and say what the answers say.

use flexweek_app::session::reminders::{AlarmQueue, Cards};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde_json::{Value, json};

use crate::{guard, raise};

fn parse(text: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("not JSON: {error}")))
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
            let (notice, rows) = (parse(notice)?, parse(rows)?);
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
            let rows = parse(rows)?;
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
        guard(|| Ok(self.queue.enqueue(parse(alarm)?)))
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

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyCards>()?;
    module.add_class::<PyAlarmQueue>()?;
    Ok(())
}
