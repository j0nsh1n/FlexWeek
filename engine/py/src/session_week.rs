//! Bind the desktop's week decisions without taking ownership of its drafts.

use std::collections::HashSet;

use flexweek_app::session::week::{
    self, DraftFlags, FailedRead, History, LoadFinish, LoadReply, LoadRoute, LocalWeek, ReadWeek,
    RemoteChange, Row,
};
use flexweek_store::Revision;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde::{Deserialize, de::DeserializeOwned};
use serde_json::{Value, json};

use crate::{guard, raise};

type Flags = (bool, bool, bool);
type Parked = Vec<(String, Flags)>;

fn flags((dirty, dirty_assignments, pending_save): Flags) -> DraftFlags {
    DraftFlags {
        dirty,
        dirty_assignments,
        pending_save,
    }
}

fn drafts(parked: Parked) -> Vec<(String, DraftFlags)> {
    parked
        .into_iter()
        .map(|(start, draft)| (start, flags(draft)))
        .collect()
}

fn read<T: DeserializeOwned>(text: &str) -> PyResult<T> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))
}

fn checked_revision(revision: Value) -> PyResult<Revision> {
    match revision {
        Value::Number(number) => number.as_i64().map(Revision::Stored),
        Value::Array(parts) => match parts.as_slice() {
            [first, second] => first
                .as_i64()
                .zip(second.as_i64())
                .map(|(first, second)| Revision::Shown(first, second)),
            _ => None,
        },
        _ => None,
    }
    .ok_or_else(|| {
        PyValueError::new_err("revision must be an integer or two stored-week revisions")
    })
}

#[derive(Deserialize)]
struct WeekReply {
    week_start: String,
    revision: Value,
    blocks: Vec<Row>,
    stored: Option<Vec<Row>>,
    repeats: Option<Vec<Row>>,
}

#[pyfunction]
fn week_held(current: Flags) -> PyResult<bool> {
    guard(|| Ok(flags(current).held()))
}

#[pyfunction]
fn first_held_week(parked: Parked) -> PyResult<Option<String>> {
    guard(|| Ok(week::first_held(&drafts(parked)).cloned()))
}

#[pyfunction]
fn dirty_parked_weeks(parked: Parked) -> PyResult<Vec<String>> {
    guard(|| Ok(week::dirty_parked(&drafts(parked)).cloned().collect()))
}

#[pyfunction]
fn week_select(
    requested: &str,
    open: &str,
    first_weekday: u32,
    discard: bool,
    current: Flags,
    parked: Parked,
) -> PyResult<String> {
    guard(|| {
        let route = week::select_week(
            requested,
            open,
            first_weekday,
            discard,
            flags(current),
            &drafts(parked),
        )
        .map_err(raise)?;
        Ok(match route {
            LoadRoute::KeepOpen => json!({"action": "keep"}),
            LoadRoute::Restore {
                start,
                park_open,
                words,
            } => {
                json!({"action": "restore", "start": start, "park_open": park_open, "words": words})
            }
            LoadRoute::Fetch {
                start,
                discard_parked,
            } => {
                json!({"action": "fetch", "start": start, "discard_parked": discard_parked})
            }
        }
        .to_string())
    })
}

#[pyfunction]
fn week_reload_words() -> PyResult<&'static str> {
    guard(|| Ok(week::reload_words()))
}

#[pyfunction]
fn week_remote_change(
    signed_in: bool,
    busy: bool,
    current: Flags,
    who: &str,
) -> PyResult<(bool, bool, Option<String>)> {
    guard(|| {
        Ok(
            match week::remote_change(signed_in, busy, flags(current), who) {
                RemoteChange::Ignore => (true, false, None),
                RemoteChange::Wait => (false, false, None),
                RemoteChange::Conflict => (true, true, None),
                RemoteChange::Reload(words) => (true, false, Some(words)),
            },
        )
    })
}

#[pyfunction]
fn week_load_failed(
    open: &str,
    assignments: bool,
    selected_day: &str,
    first_weekday: u32,
) -> PyResult<(bool, bool)> {
    guard(|| {
        let read = if assignments {
            FailedRead::Assignments
        } else {
            FailedRead::Week
        };
        let LoadFinish::Failed {
            clear_waiting_plan,
            refresh_selected_day,
        } = week::finish_load(
            open,
            LoadReply::Failed {
                read,
                selected_day,
                first_weekday,
            },
        )
        .map_err(raise)?
        else {
            unreachable!("only a successful read can install a week");
        };
        Ok((clear_waiting_plan, refresh_selected_day))
    })
}

#[pyfunction]
#[pyo3(signature = (open, current, revision, week_reply, assignments_reply, said))]
fn week_install(
    open: &str,
    current: Flags,
    revision: &str,
    week_reply: &str,
    assignments_reply: &str,
    said: Option<&str>,
) -> PyResult<String> {
    guard(|| {
        let reply: WeekReply = serde_json::from_value(Value::Object(read(week_reply)?))
            .map_err(|error| PyValueError::new_err(error.to_string()))?;
        let reply = LoadReply::Read {
            week: ReadWeek {
                start: reply.week_start,
                revision: checked_revision(reply.revision)?,
                blocks: reply.blocks,
                stored: reply.stored.unwrap_or_default(),
                repeats: reply.repeats.unwrap_or_default(),
            },
            assignments: read(assignments_reply)?,
            revision: checked_revision(read(revision)?)?,
            current: flags(current),
        };
        let LoadFinish::Install {
            week,
            assignments,
            park_open,
            history,
        } = week::finish_load(open, reply).map_err(raise)?
        else {
            unreachable!("both successful reads are present");
        };
        let history = match history {
            History::Keep => "keep",
            History::Clear => "clear",
            History::MarkStale => "stale",
        };
        let revision = match week.revision {
            Revision::Stored(revision) => json!(revision),
            Revision::Shown(first, second) => json!([first, second]),
        };
        Ok(json!({
            "start": week.start,
            "revision": revision,
            "blocks": week.blocks,
            "stored": week.stored,
            "repeats": week.repeats,
            "assignments": assignments,
            "park_open": park_open,
            "history": history,
            "words": week::load_words(said),
        })
        .to_string())
    })
}

#[pyfunction]
fn week_wrote_open(open: &str, current: Flags, written: HashSet<String>) -> PyResult<bool> {
    guard(|| Ok(week::wrote_open_weeks(open, flags(current), &written)))
}

#[pyfunction]
fn week_local_source(requested: &str, open: &str, parked_dirty: bool) -> PyResult<&'static str> {
    guard(|| {
        Ok(match week::local_week(requested, open, parked_dirty) {
            LocalWeek::Open => "open",
            LocalWeek::Parked => "parked",
            LocalWeek::Missing => "missing",
        })
    })
}

#[pyfunction]
fn week_block_index(ids: Vec<String>, id: &str) -> PyResult<Option<usize>> {
    guard(|| Ok(week::block_index(&ids, id)))
}

#[pyfunction]
fn week_load_skipped(signed_in: bool, busy: bool) -> PyResult<bool> {
    guard(|| Ok(week::load_week_skipped(signed_in, busy)))
}

#[pyfunction]
fn week_refresh_assignments(
    incoming: &str,
    local: HashSet<String>,
    saved: HashSet<String>,
    dirty: HashSet<String>,
) -> PyResult<String> {
    guard(|| {
        let incoming: Option<Vec<Row>> = read(incoming)?;
        let edits = week::refresh_assignments(incoming.unwrap_or_default(), &local, &saved, &dirty)
            .map_err(raise)?;
        Ok(json!({
            "saved_counts": edits.saved_counts,
            "dirty_counts": edits.dirty_counts,
            "clean_rows": edits.clean_rows,
        })
        .to_string())
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        week_held,
        first_held_week,
        dirty_parked_weeks,
        week_select,
        week_reload_words,
        week_remote_change,
        week_load_failed,
        week_install,
        week_wrote_open,
        week_local_source,
        week_block_index,
        week_load_skipped,
        week_refresh_assignments,
    );
    Ok(())
}
