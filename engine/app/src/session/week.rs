//! Week decisions for the desktop session. The host owns the drafts and runs the reads.

use std::collections::HashSet;

use flexweek_engine::shown::shown_parts;
use flexweek_engine::time::week_start_on;
use flexweek_engine::{EngineError, EngineResult};
use flexweek_store::Revision;
use serde_json::{Map, Value};

pub type Row = Map<String, Value>;

const THIS_WEEK: &str = "This week.";

#[derive(Clone, Copy, Debug, Default)]
pub struct DraftFlags {
    pub dirty: bool,
    pub dirty_assignments: bool,
    pub pending_save: bool,
}

impl DraftFlags {
    pub fn held(self) -> bool {
        self.dirty || self.dirty_assignments || self.pending_save
    }
}

pub fn first_held<T>(parked: &[(T, DraftFlags)]) -> Option<&T> {
    parked
        .iter()
        .find(|(_, draft)| draft.held())
        .map(|(key, _)| key)
}

#[derive(Debug, PartialEq, Eq)]
pub enum LoadRoute {
    KeepOpen,
    Restore {
        start: String,
        park_open: bool,
        words: &'static str,
    },
    Fetch {
        start: String,
        discard_parked: bool,
    },
}

pub fn select_week(
    requested: &str,
    open: &str,
    first_weekday: u32,
    discard: bool,
    current: DraftFlags,
    parked: &[(String, DraftFlags)],
) -> EngineResult<LoadRoute> {
    let start = if requested == open || parked.iter().any(|(key, _)| key == requested) {
        requested.to_owned()
    } else {
        week_start_on(requested, first_weekday)?
    };
    if !discard {
        let held = parked
            .iter()
            .any(|(key, draft)| key == &start && draft.held());
        if start == open && (current.held() || held) {
            return Ok(LoadRoute::KeepOpen);
        }
        if held {
            return Ok(LoadRoute::Restore {
                start,
                park_open: current.held(),
                words: THIS_WEEK,
            });
        }
    }
    Ok(LoadRoute::Fetch {
        start,
        discard_parked: discard,
    })
}

pub fn load_words(said: Option<&str>) -> &str {
    said.unwrap_or(THIS_WEEK)
}

pub fn reload_words() -> &'static str {
    "Reloaded this week."
}

#[derive(Debug, PartialEq, Eq)]
pub enum RemoteChange {
    Ignore,
    Wait,
    Conflict,
    Reload(String),
}

pub fn remote_change(signed_in: bool, busy: bool, draft: DraftFlags, who: &str) -> RemoteChange {
    if !signed_in {
        RemoteChange::Ignore
    } else if busy {
        RemoteChange::Wait
    } else if draft.held() {
        RemoteChange::Conflict
    } else {
        RemoteChange::Reload(format!("Updated from {who}."))
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum History {
    Keep,
    Clear,
    MarkStale,
}

#[derive(Debug, PartialEq, Eq)]
pub struct ReadWeek {
    pub start: String,
    pub revision: Revision,
    pub blocks: Vec<Row>,
    pub stored: Vec<Row>,
    pub repeats: Vec<Row>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FailedRead {
    Week,
    Assignments,
}

pub enum LoadReply<'a> {
    Failed {
        read: FailedRead,
        selected_day: &'a str,
        first_weekday: u32,
    },
    Read {
        week: ReadWeek,
        assignments: Vec<Row>,
        revision: Revision,
        current: DraftFlags,
    },
}

#[derive(Debug, PartialEq, Eq)]
pub enum LoadFinish {
    Failed {
        clear_waiting_plan: bool,
        refresh_selected_day: bool,
    },
    Install {
        week: ReadWeek,
        assignments: Row,
        park_open: bool,
        history: History,
    },
}

fn assignment_id(row: &Row) -> EngineResult<&str> {
    row.get("id")
        .and_then(Value::as_str)
        .ok_or_else(|| EngineError::value("assignment id must be text"))
}

/// Moving the open draft and changing history are effects of receiving both replies.
pub fn finish_load(open: &str, reply: LoadReply<'_>) -> EngineResult<LoadFinish> {
    match reply {
        LoadReply::Failed {
            read,
            selected_day,
            first_weekday,
        } => Ok(LoadFinish::Failed {
            clear_waiting_plan: read == FailedRead::Assignments,
            refresh_selected_day: week_start_on(selected_day, first_weekday)? != open,
        }),
        LoadReply::Read {
            week,
            assignments,
            revision,
            current,
        } => {
            let moved = week.start != open;
            let history = if moved {
                History::Clear
            } else if week.revision != revision {
                History::MarkStale
            } else {
                History::Keep
            };
            let assignments = assignments
                .into_iter()
                .map(|row| Ok((assignment_id(&row)?.to_owned(), Value::Object(row))))
                .collect::<EngineResult<Row>>()?;
            Ok(LoadFinish::Install {
                week,
                assignments,
                park_open: moved && current.held(),
                history,
            })
        }
    }
}

pub fn wrote_open_weeks(open: &str, current: DraftFlags, written: &HashSet<String>) -> bool {
    !current.held()
        && !written.contains(open)
        && matches!(shown_parts(open), Ok(Some((first, second, _))) if written.contains(&first) || written.contains(&second))
}

#[derive(Debug, PartialEq, Eq)]
pub enum LocalWeek {
    Open,
    Parked,
    Missing,
}

pub fn local_week(requested: &str, open: &str, parked_dirty: bool) -> LocalWeek {
    if requested == open {
        LocalWeek::Open
    } else if parked_dirty {
        LocalWeek::Parked
    } else {
        LocalWeek::Missing
    }
}

pub fn dirty_parked<T>(parked: &[(T, DraftFlags)]) -> impl Iterator<Item = &T> {
    parked
        .iter()
        .filter(|(_, draft)| draft.dirty)
        .map(|(key, _)| key)
}

pub fn block_index(ids: &[String], id: &str) -> Option<usize> {
    ids.iter().position(|candidate| candidate == id)
}

#[derive(Debug, Default, PartialEq, Eq)]
pub struct AssignmentRefresh {
    pub saved_counts: Row,
    pub dirty_counts: Row,
    pub clean_rows: Row,
}

fn counts(row: &Row) -> Value {
    Value::Object(
        ["unplanned_min", "planned_min", "done_min"]
            .into_iter()
            .map(|field| {
                (
                    field.to_owned(),
                    row.get(field).cloned().unwrap_or(Value::Null),
                )
            })
            .collect(),
    )
}

/// Keep a dirty edit and the last saved homework intact, apart from the server's new counts.
pub fn refresh_assignments(
    incoming: Vec<Row>,
    local: &HashSet<String>,
    saved: &HashSet<String>,
    dirty: &HashSet<String>,
) -> EngineResult<AssignmentRefresh> {
    let mut refresh = AssignmentRefresh::default();
    for row in incoming {
        let id = assignment_id(&row)?.to_owned();
        if saved.contains(&id) {
            refresh.saved_counts.insert(id.clone(), counts(&row));
        }
        if dirty.contains(&id) {
            if local.contains(&id) {
                refresh.dirty_counts.insert(id, counts(&row));
            }
        } else {
            refresh.clean_rows.insert(id, Value::Object(row));
        }
    }
    Ok(refresh)
}
