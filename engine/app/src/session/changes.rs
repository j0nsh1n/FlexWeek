//! Build a changes request from the draft and decide how to send it. The window owns the draft,
//! holds the built request for retries, and applies the answer.

use std::collections::BTreeMap;

use flexweek_engine::desk::history::{self, revision_after_deletes, same_value};
use flexweek_engine::plan;
use flexweek_engine::repeats::{Intent, intents_between};
use flexweek_engine::shown::stored_weeks;
use flexweek_engine::stored::truthy;
use flexweek_engine::validate::{ASSIGNMENT_FIELDS, whole_number};
use flexweek_engine::{EngineError, EngineResult};
use flexweek_service::{blocks, homework_saves};
use serde_json::{Map, Value, json};

pub fn assignment_write(id: &str, item: Option<&Value>, revision: i64) -> EngineResult<Value> {
    let assignment = item
        .map(|item| {
            let fields = object(item, "homework")?;
            let content = fields
                .iter()
                .filter(|(key, _)| {
                    key.as_str() == "revision" || ASSIGNMENT_FIELDS.contains(&key.as_str())
                })
                .map(|(key, value)| (key.clone(), value.clone()))
                .collect();
            homework_saves::check_homework(&Value::Object(content))
                .map(|(body, _)| body)
                .map_err(|error| EngineError::value(error.0))
        })
        .transpose()?;
    Ok(json!({"id": id, "assignment": assignment, "revision": revision}))
}

pub fn week_write(week_start: &str, rows: &[Value], revision: &Value) -> EngineResult<Value> {
    check_revision(revision)?;
    let blocks = rows
        .iter()
        .map(|row| blocks::check_block(row).map_err(|error| EngineError::value(error.0)))
        .collect::<EngineResult<Vec<_>>>()?;
    Ok(json!({"week_start": week_start, "blocks": blocks, "revision": revision}))
}

pub struct SaveDraft<'a> {
    pub week_start: &'a str,
    pub blocks: &'a [Value],
    pub revision: &'a Value,
    pub committed_blocks: &'a [Value],
    pub assignments: &'a Map<String, Value>,
    pub committed_assignments: &'a Map<String, Value>,
    pub dirty_assignments: &'a [String],
    pub travel_weeks: &'a [Value],
    pub undo: bool,
    pub stored_parts: &'a [Value],
    pub saved_repeats: &'a [Value],
    pub repeats: &'a [Value],
    pub queued_repeats: &'a [Value],
}

fn object<'a>(value: &'a Value, name: &str) -> EngineResult<&'a Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| EngineError::value(format!("{name} must be an object")))
}

fn date_of(value: &Value) -> EngineResult<&str> {
    value["week_start"]
        .as_str()
        .ok_or_else(|| EngineError::value("week_start must be text"))
}

fn rows<'a>(value: &'a Value, key: &str) -> EngineResult<&'a [Value]> {
    value[key]
        .as_array()
        .map(Vec::as_slice)
        .ok_or_else(|| EngineError::value(format!("{key} must be a list")))
}

fn check_revision(revision: &Value) -> EngineResult<()> {
    if revision.is_i64()
        || matches!(revision.as_array().map(Vec::as_slice), Some([first, second]) if first.is_i64() && second.is_i64())
    {
        Ok(())
    } else {
        Err(EngineError::value(
            "revision must be an integer or two stored-week revisions",
        ))
    }
}

fn assignment_revision(source: Option<&Value>) -> EngineResult<i64> {
    match source.and_then(|item| item.get("revision")) {
        None | Some(Value::Null) => Ok(0),
        Some(Value::String(text)) if text.is_empty() => Ok(0),
        Some(value) => whole_number(value)
            .and_then(|number| i64::try_from(number).ok())
            .ok_or_else(|| EngineError::value("assignment revision must be a whole number")),
    }
}

/// The request kept until acknowledgment, including any local navigation metadata.
pub fn freeze_save(
    draft: &SaveDraft<'_>,
    operation_id: &str,
    snapshot_label: Option<&str>,
) -> EngineResult<Value> {
    let mut dirty: Vec<&String> = draft.dirty_assignments.iter().collect();
    dirty.sort_unstable();
    let mut assignments = Vec::with_capacity(dirty.len());
    let mut deleted = Vec::new();
    for id in dirty {
        let item = draft.assignments.get(id);
        let source = item.or_else(|| draft.committed_assignments.get(id));
        let revision = assignment_revision(source)?;
        assignments.push(assignment_write(id, item, revision)?);
        if item.is_none() {
            deleted.push(id.clone());
        }
    }

    let mut extra = Vec::new();
    for week in draft.travel_weeks {
        let date = date_of(week)?;
        if date != draft.week_start {
            extra.push((date, week));
        }
    }
    let traveling = !extra.is_empty();
    check_revision(draft.revision)?;
    let revision = if traveling {
        draft.revision.clone()
    } else {
        revision_after_deletes(draft.committed_blocks, draft.revision, &deleted)?
    };
    let mut weeks = vec![week_write(draft.week_start, draft.blocks, &revision)?];
    if traveling {
        let mut live = BTreeMap::new();
        for part in draft.stored_parts {
            live.insert(date_of(part)?, part);
        }
        let side = if draft.undo { "before" } else { "after" };
        for (date, week) in extra {
            let revision = if let Some(part) = live.get(date) {
                check_revision(&part["revision"])?;
                revision_after_deletes(rows(part, "blocks")?, &part["revision"], &deleted)?
            } else {
                week["revision"].clone()
            };
            weeks.push(week_write(date, rows(week, side)?, &revision)?);
        }
    }

    let mut request =
        json!({"weeks": weeks, "assignments": assignments, "operation_id": operation_id});
    if traveling {
        request["stay"] = json!(true);
    } else {
        let repeats = if draft.queued_repeats.is_empty() {
            intents_between(draft.saved_repeats, draft.repeats, draft.week_start)
                .iter()
                .map(Intent::to_value)
                .collect()
        } else {
            draft.queued_repeats.to_vec()
        };
        if !repeats.is_empty() {
            request["repeats"] = Value::Array(repeats);
        }
    }
    if let Some(label) = snapshot_label.filter(|label| !label.is_empty()) {
        request["snapshot_label"] = json!(label);
    }
    Ok(request)
}

/// Python's dict equality ignores key order. A retry with the same request keeps the original ID,
/// even if the store already received it and only its reply was lost.
pub fn retry_needs_new_id(previous: &Value, rebuilt: &Value) -> bool {
    !same_value(previous, rebuilt)
}

/// The wire body and the week to open afterward. `written` is in the host's set iteration order.
pub fn prepare_post(
    mut request: Map<String, Value>,
    written: &[String],
    week_start: &str,
    shifted_week: bool,
) -> EngineResult<(Value, Option<String>)> {
    let stay = match request.shift_remove("stay") {
        None | Some(Value::Null) => false,
        Some(Value::Bool(stay)) => stay,
        _ => return Err(EngineError::value("stay must be a boolean")),
    };
    let shown_parts = if shifted_week {
        stored_weeks(week_start)?
    } else {
        Vec::new()
    };
    let keeps_week = stay
        || written
            .iter()
            .any(|week| week == week_start || shown_parts.contains(week));
    let destination = if keeps_week {
        None
    } else {
        written.first().cloned()
    };
    Ok((Value::Object(request), destination))
}

#[derive(Debug, PartialEq, Eq)]
pub enum SaveFailureKind {
    Unreachable,
    Conflict,
    Refused,
}

#[derive(Debug, PartialEq, Eq)]
pub struct SaveFailure {
    pub kind: SaveFailureKind,
    pub words: String,
}

pub fn classify_failure(status: i64, message: &str) -> SaveFailure {
    let kind = match status {
        0 => SaveFailureKind::Unreachable,
        409 => SaveFailureKind::Conflict,
        _ => SaveFailureKind::Refused,
    };
    let words = if kind == SaveFailureKind::Unreachable {
        "Not saved: FlexWeek can't be reached. Your changes are still here. Choose Retry save."
            .into()
    } else {
        format!("Not saved. {message}")
    };
    SaveFailure { kind, words }
}

/// The Undo step a save records, before it has an ID: what changed from the saved week to the draft.
pub fn save_step(draft: &SaveDraft<'_>, label: &str) -> EngineResult<Option<Value>> {
    history::capture_step(
        label,
        draft.week_start,
        &Value::Array(draft.committed_blocks.to_vec()),
        &Value::Array(draft.blocks.to_vec()),
        &Value::Object(draft.committed_assignments.clone()),
        &Value::Object(draft.assignments.clone()),
        draft.dirty_assignments,
    )
}

/// An Undo or Redo whose save is under way.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Travel {
    Undo,
    Redo,
}

/// What the window holds when a save's answer comes in.
pub struct SaveAnswer<'a> {
    pub data: &'a Value,
    pub week_start: &'a str,
    pub shifted_week: bool,
    /// Local `YYYY-MM-DDTHH:MM`, read only when an off-screen week's counts move.
    pub now: &'a str,
    pub sent_repeats: bool,
    pub assignments: &'a Map<String, Value>,
    pub committed_assignments: &'a Map<String, Value>,
    pub stored_parts: &'a [Value],
    pub traveling: Option<Travel>,
    pub travel_step: Option<&'a Value>,
    pub pending_step: Option<&'a Value>,
    pub plan_step_id: Option<&'a str>,
    pub join: bool,
    /// The status line the save was started with, if any.
    pub held_words: Option<&'a str>,
    /// The repeat intents this save carried, and those waiting to be sent.
    pub sent_intents: Option<&'a [Value]>,
    pub waiting_intents: Option<&'a [Value]>,
}

/// The open week as the server stored it.
#[derive(Debug, PartialEq)]
pub struct SavedWeek {
    pub blocks: Vec<Value>,
    pub revision: Value,
    pub stored: Vec<Value>,
    /// Only when the save carried repeat changes.
    pub repeats: Option<Vec<Value>>,
}

/// Where an acknowledged step goes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StepPlace {
    Undo,
    JoinUndo,
    Redo,
}

/// The edits a save's answer makes, in the order the window applies them: session weeks, then the
/// moved counts, then the open week, then each homework row (null removes it), then the step.
#[derive(Debug, PartialEq)]
pub struct Acknowledgment {
    pub session_weeks: Map<String, Value>,
    pub live_counts: Map<String, Value>,
    pub saved_counts: Map<String, Value>,
    pub open_week: Option<SavedWeek>,
    pub homework: Vec<(String, Option<Value>)>,
    pub step: Option<(StepPlace, Value)>,
    pub clear_redo: bool,
    /// The save landed a Plan's step: the window says it with an Undo of its own.
    pub planned: bool,
    pub words: String,
    pub waiting_intents: Option<Vec<Value>>,
}

/// `x or []` for a list field.
fn optional_list<'a>(value: &'a Value, key: &str) -> EngineResult<&'a [Value]> {
    match value.get(key) {
        None => Ok(&[]),
        Some(found) if !truthy(Some(found)) => Ok(&[]),
        Some(Value::Array(items)) => Ok(items),
        Some(_) => Err(EngineError::value(format!("{key} must be a list"))),
    }
}

fn text_of<'a>(value: &'a Value, key: &str) -> EngineResult<&'a str> {
    value
        .get(key)
        .ok_or_else(|| EngineError::key(key))?
        .as_str()
        .ok_or_else(|| EngineError::value(format!("{key} must be text")))
}

/// `int(value)` for a held count.
fn int_of(value: &Value) -> EngineResult<i64> {
    match value {
        Value::Bool(flag) => Ok(i64::from(*flag)),
        Value::Number(number) => number
            .as_i64()
            .or_else(|| number.as_f64().map(|float| float.trunc() as i64))
            .ok_or_else(|| EngineError::value("a count is too large")),
        Value::String(text) => text
            .trim()
            .parse()
            .map_err(|_| EngineError::value(format!("invalid literal for int(): {text:?}"))),
        _ => Err(EngineError::value("a count must be a number")),
    }
}

static NO_BLOCKS: Value = Value::Array(Vec::new());

/// The stored weeks' blocks the count rules read; a side that is not a list is left out.
fn counted_weeks(weeks: Vec<(String, &Value)>) -> Vec<(String, Vec<Value>)> {
    weeks
        .into_iter()
        .filter_map(|(start, blocks)| Some((start, blocks.as_array()?.clone())))
        .collect()
}

/// A held copy of the homework and the count edits made to it.
type HeldCopy<'a> = (&'a mut Map<String, Value>, &'a mut Map<String, Value>);

/// A save that moved sessions into or out of a week other than the open one changes what the held
/// `planned_min` and `done_min` count, which were read with the open week as saved. Those weeks'
/// change goes on the held numbers of both copies, so every count is right before the next read.
fn shift_held_counts(
    answer: &SaveAnswer<'_>,
    replied: &[Value],
    held: [HeldCopy<'_>; 2],
) -> EngineResult<()> {
    let step = if answer.traveling.is_some() {
        answer.travel_step
    } else {
        answer.pending_step
    };
    let Some(step) = step else {
        return Ok(());
    };
    let (old_side, new_side) = if answer.traveling == Some(Travel::Undo) {
        ("after", "before")
    } else {
        ("before", "after")
    };
    // Homework that Undo or Redo brings back from a delete has the numbers the step kept, read with
    // its sessions back in every week; shifting them again would count those twice.
    let mut restored = Vec::new();
    if answer.traveling.is_some() {
        for entry in optional_list(step, "assignments")? {
            if entry.get("basis").is_some()
                && !entry
                    .get(new_side)
                    .ok_or_else(|| EngineError::key(new_side))?
                    .is_null()
            {
                restored.push(text_of(entry, "id")?);
            }
        }
    }
    let mut open_weeks = vec![answer.week_start.to_string()];
    if answer.shifted_week {
        open_weeks.extend(stored_weeks(answer.week_start)?);
    }
    let (mut old_weeks, mut new_weeks) = (Vec::new(), Vec::new());
    for entry in optional_list(step, "weeks")? {
        let start = text_of(entry, "week_start")?;
        let stored = replied
            .iter()
            .rev()
            .find(|week| week.get("week_start").and_then(Value::as_str) == Some(start));
        let Some(stored) = stored.filter(|_| !open_weeks.iter().any(|open| open == start)) else {
            continue;
        };
        let old = entry
            .get(old_side)
            .ok_or_else(|| EngineError::key(old_side))?;
        old_weeks.push((start.to_string(), old));
        let new = match stored.get("blocks") {
            Some(blocks) if truthy(Some(blocks)) => blocks,
            _ => &NO_BLOCKS,
        };
        new_weeks.push((start.to_string(), new));
    }
    if old_weeks.is_empty() {
        return Ok(());
    }
    let (old_weeks, new_weeks) = (counted_weeks(old_weeks), counted_weeks(new_weeks));
    let now = plan::parse_moment(answer.now)?;
    let planned = |weeks: &[(String, Vec<Value>)]| {
        if answer.shifted_week {
            plan::planned_minutes_from_day(weeks, answer.week_start, Some(now))
        } else {
            Ok(plan::planned_minutes_by_id(
                weeks,
                answer.week_start,
                Some(now),
            ))
        }
    };
    let moved = [
        ("planned_min", planned(&old_weeks)?, planned(&new_weeks)?),
        (
            "done_min",
            plan::done_minutes_by_id(&old_weeks),
            plan::done_minutes_by_id(&new_weeks),
        ),
    ];
    let [(live, live_counts), (saved, saved_counts)] = held;
    for (key, gone, came) in moved {
        let mut homework: Vec<&String> = gone.keys().chain(came.keys()).collect();
        homework.sort_unstable();
        homework.dedup();
        for id in homework {
            if restored.contains(&id.as_str()) {
                continue;
            }
            let change = came.get(id).copied().unwrap_or(0) - gone.get(id).copied().unwrap_or(0);
            for (copies, counts) in [
                (&mut *live, &mut *live_counts),
                (&mut *saved, &mut *saved_counts),
            ] {
                let Some(item) = copies.get_mut(id.as_str()) else {
                    continue;
                };
                let item = item
                    .as_object_mut()
                    .ok_or_else(|| EngineError::value("homework must be an object"))?;
                let Some(count) = item.get(key).filter(|count| !count.is_null()) else {
                    continue;
                };
                let shifted = int_of(count)?
                    .checked_add(change)
                    .ok_or_else(|| EngineError::value("a count is too large"))?;
                item.insert(key.into(), json!(shifted));
                let edits = counts
                    .entry(id.clone())
                    .or_insert_with(|| Value::Object(Map::new()));
                edits[key] = json!(shifted);
            }
        }
    }
    Ok(())
}

/// The edits a save's answer makes to the window's copies, its Undo history and its status line. A
/// Plan's step is reported as planned only once the save holding it lands.
pub fn acknowledge_save(answer: &SaveAnswer<'_>) -> EngineResult<Acknowledgment> {
    for step in [answer.pending_step, answer.travel_step]
        .into_iter()
        .flatten()
    {
        for field in ["weeks", "assignments"] {
            if !matches!(step.get(field), None | Some(Value::Null | Value::Array(_))) {
                return Err(EngineError::value(format!("step {field} must be a list")));
            }
        }
    }

    let replied = optional_list(answer.data, "weeks")?;
    let mut changed = Vec::new();
    let mut held_in: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    for week in replied {
        let start = text_of(week, "week_start")?;
        changed.push(start);
        for block in optional_list(week, "blocks")? {
            if let Some(id) = block
                .get("assignment_id")
                .and_then(Value::as_str)
                .filter(|id| !id.is_empty())
            {
                held_in.entry(id).or_default().push(start);
            }
        }
    }

    let mut live = answer.assignments.clone();
    let mut session_weeks = Map::new();
    for (id, item) in &mut live {
        let item = item
            .as_object_mut()
            .ok_or_else(|| EngineError::value("homework must be an object"))?;
        let mut weeks = std::collections::BTreeSet::new();
        for week in optional_list(&Value::Object(item.clone()), "session_weeks")? {
            let week = week
                .as_str()
                .ok_or_else(|| EngineError::value("session weeks must be text"))?;
            if !changed.contains(&week) {
                weeks.insert(week.to_string());
            }
        }
        weeks.extend(
            held_in
                .get(id.as_str())
                .into_iter()
                .flatten()
                .map(|week| (*week).to_string()),
        );
        let weeks = json!(weeks);
        item.insert("session_weeks".into(), weeks.clone());
        session_weeks.insert(id.clone(), weeks);
    }

    let mut saved = answer.committed_assignments.clone();
    let (mut live_counts, mut saved_counts) = (Map::new(), Map::new());
    shift_held_counts(
        answer,
        replied,
        [
            (&mut live, &mut live_counts),
            (&mut saved, &mut saved_counts),
        ],
    )?;

    let open_week = replied
        .iter()
        .find(|week| week.get("week_start").and_then(Value::as_str) == Some(answer.week_start))
        .map(|current| -> EngineResult<SavedWeek> {
            let blocks = current
                .get("blocks")
                .ok_or_else(|| EngineError::key("blocks"))?
                .as_array()
                .ok_or_else(|| EngineError::value("blocks must be a list"))?;
            Ok(SavedWeek {
                blocks: blocks.clone(),
                revision: current
                    .get("revision")
                    .cloned()
                    .ok_or_else(|| EngineError::key("revision"))?,
                stored: optional_list(current, "stored")?.to_vec(),
                repeats: answer
                    .sent_repeats
                    .then(|| optional_list(current, "repeats").map(<[Value]>::to_vec))
                    .transpose()?,
            })
        })
        .transpose()?;

    let mut homework = Vec::new();
    for result in optional_list(answer.data, "assignments")? {
        let id = text_of(result, "id")?.to_string();
        let row = result.get("assignment").filter(|row| truthy(Some(row)));
        let Some(row) = row else {
            live.shift_remove(&id);
            homework.push((id, None));
            continue;
        };
        let mut stored = row
            .as_object()
            .cloned()
            .ok_or_else(|| EngineError::value("a saved homework must be an object"))?;
        let revision = result
            .get("revision")
            .cloned()
            .ok_or_else(|| EngineError::key("revision"))?;
        stored.insert("revision".into(), revision);
        // The save's echo has no server numbers; the held ones still match the saved-week copy.
        let held = live.get(&id).cloned().unwrap_or_else(|| json!({}));
        stored.insert(
            "session_weeks".into(),
            json!(optional_list(&held, "session_weeks")?),
        );
        for key in ["unplanned_min", "planned_min", "done_min"] {
            if let Some(count) = held.get(key) {
                stored.insert(key.into(), count.clone());
            }
        }
        let stored = Value::Object(stored);
        live.insert(id.clone(), stored.clone());
        homework.push((id, Some(stored)));
    }

    let mut planned = false;
    let mut clear_redo = false;
    let (step, words) = match (answer.traveling, answer.travel_step) {
        (Some(travel), Some(step)) => {
            let label = text_of(step, "label")?;
            let mut kept = step
                .as_object()
                .cloned()
                .ok_or_else(|| EngineError::value("step must be an object"))?;
            kept.insert(
                "weeks".into(),
                Value::Array(history::keep_step_revisions(step, answer.data)),
            );
            let (place, done) = match travel {
                Travel::Undo => (StepPlace::Redo, "Undid"),
                Travel::Redo => (StepPlace::Undo, "Redid"),
            };
            (
                Some((place, Value::Object(kept))),
                format!("{done} {label}."),
            )
        }
        _ => {
            // Steps built by hand, such as a move to another date, carry no ID and never match.
            planned = answer.pending_step.is_some_and(|step| {
                answer
                    .plan_step_id
                    .is_some_and(|id| step.get("id").and_then(Value::as_str) == Some(id))
            });
            let step = match answer.pending_step {
                Some(step) => {
                    clear_redo = true;
                    let stored_after = open_week
                        .as_ref()
                        .map_or(answer.stored_parts, |week| week.stored.as_slice());
                    let place = if answer.join {
                        StepPlace::JoinUndo
                    } else {
                        StepPlace::Undo
                    };
                    let acknowledged = history::acknowledged_step(
                        step,
                        answer.data,
                        answer.stored_parts,
                        stored_after,
                        &live,
                    )?;
                    Some((place, acknowledged))
                }
                None => None,
            };
            let words = if planned {
                answer.held_words.filter(|words| !words.is_empty())
            } else {
                answer.held_words
            };
            (step, words.unwrap_or("Saved.").to_string())
        }
    };

    Ok(Acknowledgment {
        session_weeks,
        live_counts,
        saved_counts,
        open_week,
        homework,
        step,
        clear_redo,
        planned,
        words,
        waiting_intents: acknowledge_repeats(answer.sent_intents, answer.waiting_intents)?,
    })
}

/// The repeat intents still waiting once the server took the ones a save carried: a choice made
/// since (another intent, or a later one for the same repeat) is still sent with the next save.
pub fn acknowledge_repeats(
    sent: Option<&[Value]>,
    waiting: Option<&[Value]>,
) -> EngineResult<Option<Vec<Value>>> {
    let sent = sent.unwrap_or_default();
    if sent.is_empty() {
        return Ok(waiting.map(<[Value]>::to_vec));
    }
    let id_of = |item: &Value| {
        item.get("id")
            .cloned()
            .ok_or_else(|| EngineError::key("id"))
    };
    let mut carried = Vec::with_capacity(sent.len());
    for item in sent {
        carried.push((id_of(item)?, item));
    }
    let mut left = Vec::new();
    for item in waiting.unwrap_or_default() {
        let id = id_of(item)?;
        let took = carried
            .iter()
            .rev()
            .find(|(sent_id, _)| *sent_id == id)
            .is_some_and(|(_, sent)| same_value(sent, item));
        if !took {
            left.push(item.clone());
        }
    }
    Ok((!left.is_empty()).then_some(left))
}

/// What a refused Undo says once the week is read again as it is saved.
pub const TRAVEL_REFUSED: &str = "Undo did not go through. Your week was reloaded as it's saved.";

/// How the window recovers from a failed save.
#[derive(Debug, PartialEq, Eq)]
pub struct Refusal {
    pub failure: SaveFailure,
    /// The week changed elsewhere: saving waits for Reload, and held move and preview attempts end.
    pub conflict: bool,
    /// A failed Undo or Redo puts the saved week back and drops its batch.
    pub roll_back: bool,
    /// The Undo or Redo step goes back on the stack it came from.
    pub step_back: Option<Travel>,
    /// An Undo or Redo the server refused reads the week again, saying this.
    pub reload_words: Option<&'static str>,
}

pub fn refuse_save(
    status: i64,
    message: &str,
    traveling: Option<Travel>,
    holds_step: bool,
) -> Refusal {
    let failure = classify_failure(status, message);
    let conflict = failure.kind == SaveFailureKind::Conflict;
    let step_back = traveling.filter(|_| holds_step);
    Refusal {
        failure,
        conflict,
        roll_back: step_back.is_some() && !conflict,
        step_back,
        reload_words: (traveling.is_some() && conflict).then_some(TRAVEL_REFUSED),
    }
}
