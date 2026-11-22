//! The app's one save for an action that touches several things at once, as `backend/app.py`'s
//! `POST /api/changes` does it: homework saved and deleted, weeks written (a Monday is one stored week; a
//! week on screen from another day covers two), School and Setup's activities changed from a week on, and
//! a restore point made first when the save asks for one. All of it commits together or not at all, and a
//! save sent again with its operation id gets the first answer back.

use std::collections::BTreeMap;
use std::path::Path;

use flexweek_engine::shown::{
    compose_shown_week_due, repeat_changes_from_shown_week, shown_parts, split_shown_week,
};
use flexweek_engine::snapshot::canonical;
use flexweek_engine::time::{is_calendar_date, is_week_start};
use flexweek_engine::validate::{assignment_content, week_request, whole_number};
use flexweek_store::{self as store, Connection, RepeatsFailure, StoreError};
use serde_json::{Map, Value, json};

use crate::accounts::INVALID_INPUT;
use crate::blocks::{BlockRefused, Checked, refuse};
use crate::homework_saves::{ID_MISMATCH, write_homework};
use crate::records::{recall, remember, remove_homework};
use crate::week_saves::{WEEK_CONFLICT, write_week, written};
use crate::weeks::{homework_of, seen_week, shown_week};
use crate::{Refusal, ServiceError, ServiceResult, with_db};

const MAX_ASSIGNMENTS: i64 = 1000;
const MAX_RESTORE_POINTS: i64 = 20;
const REVISION_MAX: i128 = (1 << 53) - 1;
/// One save can stop every repeat and add as many new ones (`backend/app.py`'s `MAX_REPEAT_CHANGES`).
const MAX_REPEAT_CHANGES: usize = 2 * flexweek_engine::repeats::MAX_REPEATS;

/// A week the save writes, as `ChangedWeek` reads it.
#[derive(Debug, Clone)]
pub struct ChangedWeek {
    pub week_start: String,
    pub blocks: Vec<Value>,
    /// One revision for a Monday; a week on screen from another day names the two stored weeks it covers.
    pub revision: Revision,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Revision {
    Stored(i64),
    Shown(i64, i64),
}

/// A homework the save writes (`assignment` set) or deletes, as `AssignmentChange` reads it.
#[derive(Debug, Clone)]
pub struct HomeworkChange {
    pub id: String,
    pub assignment: Option<Value>,
    pub revision: i64,
}

/// The save as `ChangesRequest` reads it.
#[derive(Debug, Clone)]
pub struct ChangesRequest {
    pub weeks: Vec<ChangedWeek>,
    pub assignments: Vec<HomeworkChange>,
    pub operation_id: Option<String>,
    pub snapshot_label: Option<String>,
    pub repeats: Option<Vec<Value>>,
}

impl ChangesRequest {
    /// The request as `ChangesRequest.model_dump()` writes it; its digest keys the remembered answer.
    pub fn to_value(&self) -> Value {
        let weeks: Vec<Value> = self
            .weeks
            .iter()
            .map(|week| {
                let revision = match week.revision {
                    Revision::Stored(revision) => json!(revision),
                    Revision::Shown(first, second) => json!([first, second]),
                };
                json!({ "blocks": week.blocks, "week_start": week.week_start, "revision": revision })
            })
            .collect();
        let assignments: Vec<Value> = self
            .assignments
            .iter()
            .map(|change| {
                json!({ "id": change.id, "assignment": change.assignment, "revision": change.revision })
            })
            .collect();
        json!({
            "weeks": weeks,
            "assignments": assignments,
            "operation_id": self.operation_id,
            "snapshot_label": self.snapshot_label,
            "repeats": self.repeats,
        })
    }
}

fn object<'a>(value: &'a Value, what: &str) -> Checked<&'a Map<String, Value>> {
    match value {
        Value::Object(fields) => Ok(fields),
        _ => refuse(format!("{what} must be an object")),
    }
}

fn only(fields: &Map<String, Value>, allowed: &[&str], what: &str) -> Checked<()> {
    match fields.keys().find(|key| !allowed.contains(&key.as_str())) {
        Some(extra) => refuse(format!("{what} does not take {extra}")),
        None => Ok(()),
    }
}

fn revision(value: &Value) -> Checked<i64> {
    match whole_number(value) {
        Some(revision) if (0..=REVISION_MAX).contains(&revision) => Ok(revision as i64),
        _ => refuse("revision must be a whole number from 0"),
    }
}

/// `str | None` of 1 to 80 characters; missing is None.
fn short_text(fields: &Map<String, Value>, name: &str) -> Checked<Option<String>> {
    match fields.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) if (1..=80).contains(&text.chars().count()) => {
            Ok(Some(text.clone()))
        }
        _ => refuse(format!("{name} must be 1 to 80 characters")),
    }
}

/// A list field that defaults to empty.
fn items<'a>(fields: &'a Map<String, Value>, name: &str) -> Checked<&'a [Value]> {
    match fields.get(name) {
        None => Ok(&[]),
        Some(Value::Array(items)) => Ok(items),
        _ => refuse(format!("{name} must be a list")),
    }
}

const SHOWN_WEEK_RULE: &str =
    "a week from another day names the revisions of the two stored weeks it covers";

fn changed_week(value: &Value) -> Checked<ChangedWeek> {
    let fields = object(value, "a changed week")?;
    only(
        fields,
        &["blocks", "week_start", "revision"],
        "a changed week",
    )?;
    let Some(blocks) = fields.get("blocks") else {
        return refuse("blocks is required");
    };
    let checked = week_request(&json!({ "blocks": blocks })).map_err(BlockRefused)?;
    let week_start = match fields.get("week_start") {
        Some(Value::String(text)) => text.clone(),
        _ => return refuse("week_start is required"),
    };
    // `Revision | list[Revision]`: a list is read item by item; anything else as one revision.
    let given = match fields.get("revision") {
        Some(Value::Array(items)) => Err(items),
        Some(other) => Ok(revision(other)?),
        None => return refuse("revision is required"),
    };
    let revision = match given {
        Ok(one) if is_week_start(&week_start) => Revision::Stored(one),
        Err(items) if !is_week_start(&week_start) && is_calendar_date(&week_start) => {
            let read = items.iter().map(revision).collect::<Checked<Vec<i64>>>()?;
            match read[..] {
                [first, second] => Revision::Shown(first, second),
                _ => return refuse(SHOWN_WEEK_RULE),
            }
        }
        _ => return refuse(SHOWN_WEEK_RULE),
    };
    Ok(ChangedWeek {
        week_start,
        blocks: checked
            .blocks
            .iter()
            .map(|block| block.to_value())
            .collect(),
        revision,
    })
}

fn homework_change(value: &Value) -> Checked<HomeworkChange> {
    let fields = object(value, "a homework change")?;
    only(
        fields,
        &["id", "assignment", "revision"],
        "a homework change",
    )?;
    let id = match fields.get("id") {
        Some(Value::String(id)) if (1..=80).contains(&id.chars().count()) => id.clone(),
        _ => return refuse("id must be 1 to 80 characters"),
    };
    let assignment = match fields.get("assignment") {
        None => return refuse("assignment is required"),
        Some(Value::Null) => None,
        Some(body) => Some(assignment_content(body).map_err(BlockRefused)?.to_value()),
    };
    let Some(given) = fields.get("revision") else {
        return refuse("revision is required");
    };
    Ok(HomeworkChange {
        id,
        assignment,
        revision: revision(given)?,
    })
}

/// The save as `ChangesRequest` reads it, or why the app would refuse it.
pub fn check_changes(given: &Value) -> Checked<ChangesRequest> {
    let fields = object(given, "a save")?;
    only(
        fields,
        &[
            "weeks",
            "assignments",
            "operation_id",
            "snapshot_label",
            "repeats",
        ],
        "a save",
    )?;
    let weeks = items(fields, "weeks")?
        .iter()
        .map(changed_week)
        .collect::<Checked<Vec<_>>>()?;
    let assignments = items(fields, "assignments")?
        .iter()
        .map(homework_change)
        .collect::<Checked<Vec<_>>>()?;
    let operation_id = short_text(fields, "operation_id")?;
    let snapshot_label = short_text(fields, "snapshot_label")?;
    let repeats = match fields.get("repeats") {
        None | Some(Value::Null) => None,
        Some(Value::Array(items))
            if items.len() <= MAX_REPEAT_CHANGES && items.iter().all(Value::is_object) =>
        {
            Some(items.clone())
        }
        _ => return refuse("repeats must be a list of changes"),
    };
    Ok(ChangesRequest {
        weeks,
        assignments,
        operation_id,
        snapshot_label,
        repeats,
    })
}

fn engine(error: flexweek_engine::EngineError) -> ServiceError {
    StoreError::Engine(error).into()
}

fn parsed(text: &str) -> ServiceResult<Value> {
    serde_json::from_str(text).map_err(|error| {
        StoreError::Json {
            text: text.to_string(),
            error,
        }
        .into()
    })
}

/// The stored weeks a week on screen covers when it does not start on a Monday.
fn shown_parts_of(week_start: &str) -> ServiceResult<Option<(String, String)>> {
    if is_week_start(week_start) || !is_calendar_date(week_start) {
        return Ok(None);
    }
    Ok(shown_parts(week_start)
        .map_err(engine)?
        .map(|(first, second, _)| (first, second)))
}

fn stored_revision(conn: &Connection, user_id: i64, week_start: &str) -> ServiceResult<i64> {
    Ok(store::read_week(conn, user_id, week_start)?
        .map(|(_, revision)| revision)
        .unwrap_or(0))
}

/// Changes the repeats as `changes` say, in every saved week from each change's week on.
fn apply_repeats(conn: &Connection, user_id: i64, changes: &[Value]) -> ServiceResult<Value> {
    let intents = flexweek_engine::repeats::parse_intents(&Value::Array(changes.to_vec()))
        .map_err(Refusal::Invalid)?;
    match store::apply_repeat_intents(conn, user_id, &intents) {
        // The app read this part back from canonical text, so its keys come out sorted.
        Ok(outcome) => parsed(&canonical(&outcome.to_value())),
        Err(RepeatsFailure::Refused(words)) => Err(Refusal::Invalid(words).into()),
        Err(RepeatsFailure::Store(error)) => Err(error.into()),
    }
}

/// Splits a saved week on screen back into the stored weeks it covers and writes the ones it changed. Its
/// revisions are checked against the stored weeks as they were before this save began, so homework deleted
/// in the same save does not count as someone else's change.
fn save_shown_week(
    conn: &Connection,
    user_id: i64,
    week: &ChangedWeek,
    (first, second): (&str, &str),
    before: &BTreeMap<String, i64>,
) -> ServiceResult<()> {
    let (first_blocks, first_revision) = seen_week(conn, user_id, first)?;
    let (second_blocks, second_revision) = seen_week(conn, user_id, second)?;
    let both: Vec<Value> = first_blocks.iter().chain(&second_blocks).cloned().collect();
    let homework = homework_of(conn, user_id, &both)?;
    let now = compose_shown_week_due(&week.week_start, &first_blocks, &second_blocks, &homework)
        .map_err(engine)?;
    if canonical(&Value::Array(week.blocks.clone())) == canonical(&Value::Array(now)) {
        return Ok(());
    }
    if week.revision != Revision::Shown(before[first], before[second]) {
        return Err(Refusal::Conflict(WEEK_CONFLICT.to_string()).into());
    }
    let (first_new, second_new) = split_shown_week(
        &week.week_start,
        &week.blocks,
        &first_blocks,
        &second_blocks,
    )
    .map_err(engine)?;
    for (stored_start, new, seen, revision) in [
        (first, first_new, first_blocks, first_revision),
        (second, second_new, second_blocks, second_revision),
    ] {
        if new == seen {
            continue;
        }
        write_week(conn, user_id, stored_start, written(new)?, revision)?;
    }
    Ok(())
}

/// One week of the answer: the week as `GET /api/week` gives it.
struct WeekAnswer {
    week_start: String,
    shown: Option<(String, String)>,
    blocks: Vec<Value>,
    revision: i64,
}

/// Saves `given` as `POST /api/changes` does and answers it. `token` names a restore point made first, at
/// `now`, when the save asks for one.
pub fn apply_changes(
    path: &Path,
    user_id: i64,
    given: &Value,
    token: &str,
    now: &str,
) -> ServiceResult<Value> {
    let request = check_changes(given)
        .map_err(|_| ServiceError::from(Refusal::Invalid(INVALID_INPUT.to_string())))?;
    let digest = store::payload_digest(&request.to_value());
    with_db(path, |conn| {
        store::begin_immediate(conn)?;
        if let Some(operation_id) = &request.operation_id
            && let Some(first) = recall(conn, user_id, operation_id, &digest)?
        {
            return Ok(first);
        }
        let point = match &request.snapshot_label {
            Some(label) => Some(store::create_restore_point(
                conn,
                user_id,
                token,
                label,
                now,
                &[],
                MAX_RESTORE_POINTS,
            )?),
            None => None,
        };
        let mut before = BTreeMap::new();
        for week in &request.weeks {
            if let Some((first, second)) = shown_parts_of(&week.week_start)? {
                for stored_start in [first, second] {
                    if let std::collections::btree_map::Entry::Vacant(slot) =
                        before.entry(stored_start)
                    {
                        let revision = stored_revision(conn, user_id, slot.key())?;
                        slot.insert(revision);
                    }
                }
            }
        }
        let assignments = save_homework_changes(conn, user_id, &request.assignments)?;
        let mut repeats: Option<Value> = None;
        let mut changes = request.repeats.clone();
        for week in &request.weeks {
            if let Some(trimmed) = &changes
                && shown_parts_of(&week.week_start)?.is_some()
            {
                // From this week on, on screen: the stored week the shown one starts in keeps the change on
                // its shown days only, saved below; the repeat changes from the next Monday.
                changes = Some(
                    repeat_changes_from_shown_week(trimmed, &week.week_start).map_err(engine)?,
                );
            }
        }
        // Stored (Monday) weeks first: an Undo that puts back a stored week a week on screen also shows
        // sends both, and the week on screen then finds them as it means them.
        let mut ordered: Vec<(&ChangedWeek, Option<(String, String)>)> = Vec::new();
        for week in &request.weeks {
            ordered.push((week, shown_parts_of(&week.week_start)?));
        }
        ordered.sort_by_key(|(_, shown)| shown.is_some());
        let mut answers = Vec::with_capacity(ordered.len());
        for (week, shown) in ordered {
            if let Some((first, second)) = shown {
                if let Some(changes) = &changes
                    && repeats.is_none()
                {
                    // A repeat changed from the next Monday stands there before the week on screen is
                    // split: that week's days then match it and keep no copy of their own.
                    repeats = Some(apply_repeats(conn, user_id, changes)?);
                }
                save_shown_week(conn, user_id, week, (&first, &second), &before)?;
                answers.push(WeekAnswer {
                    week_start: week.week_start.clone(),
                    shown: Some((first, second)),
                    blocks: Vec::new(),
                    revision: 0,
                });
                continue;
            }
            let Revision::Stored(revision) = week.revision else {
                return Err(ServiceError::Broken(
                    "a Monday week with two revisions".into(),
                ));
            };
            let (blocks, revision) = write_week(
                conn,
                user_id,
                &week.week_start,
                week.blocks.clone(),
                revision,
            )?;
            answers.push(WeekAnswer {
                week_start: week.week_start.clone(),
                shown: None,
                blocks,
                revision,
            });
        }
        if let Some(changes) = &changes
            && repeats.is_none()
        {
            // Saved weeks from the change's week on take it here; the open week is in `weeks`, already
            // changed by the client, so Undo takes back its part only.
            repeats = Some(apply_repeats(conn, user_id, changes)?);
        }
        let mut weeks = Vec::with_capacity(answers.len());
        for answer in answers {
            weeks.push(week_answer(conn, user_id, answer, repeats.is_some())?);
        }
        let mut result = Map::new();
        result.insert("weeks".into(), Value::Array(weeks));
        result.insert("assignments".into(), Value::Array(assignments));
        if let Some(repeats) = repeats {
            result.insert("repeats".into(), repeats);
        }
        if let Some(point) = point {
            // The point made before this save, so its notice's Undo can put it back.
            result.insert("restore_point".into(), point);
        }
        let result = Value::Object(result);
        if let Some(operation_id) = &request.operation_id {
            remember(conn, user_id, operation_id, &digest, &result)?;
        }
        Ok(result)
    })
}

/// Homework saves first, then deletes, each answered as the app answers it.
fn save_homework_changes(
    conn: &Connection,
    user_id: i64,
    changes: &[HomeworkChange],
) -> ServiceResult<Vec<Value>> {
    let mut results = Vec::with_capacity(changes.len());
    let mut deletes = Vec::new();
    for change in changes {
        let Some(content) = &change.assignment else {
            deletes.push(change);
            continue;
        };
        if content["id"] != change.id.as_str() {
            return Err(Refusal::Invalid(ID_MISMATCH.to_string()).into());
        }
        let revision = write_homework(
            conn,
            user_id,
            &change.id,
            content,
            change.revision,
            MAX_ASSIGNMENTS,
        )?;
        results.push(json!({ "id": change.id, "revision": revision, "assignment": content }));
    }
    for change in deletes {
        let deleted = remove_homework(conn, user_id, &change.id, Some(change.revision))?;
        results.push(json!({
            "id": change.id,
            "revision": change.revision,
            "assignment": Value::Null,
            "changed_weeks": deleted["changed_weeks"],
            "removed_sessions": deleted["removed_sessions"],
        }));
    }
    Ok(results)
}

fn week_answer(
    conn: &Connection,
    user_id: i64,
    answer: WeekAnswer,
    repeats_changed: bool,
) -> ServiceResult<Value> {
    if let Some((first, second)) = &answer.shown {
        return shown_week(conn, user_id, &answer.week_start, (first, second), || {});
    }
    let mut stored = Value::Array(answer.blocks).to_string();
    let mut revision = answer.revision;
    if repeats_changed {
        // All weeks rewrites the open week's row too: the answer gives it as now stored.
        if let Some((text, now)) = store::read_week(conn, user_id, &answer.week_start)? {
            stored = text;
            revision = now;
        }
    }
    let blocks = parsed(&store::week_with_standing(
        conn,
        user_id,
        &answer.week_start,
        &stored,
    )?)?;
    let mut fields = Map::new();
    fields.insert("week_start".into(), Value::from(answer.week_start.as_str()));
    fields.insert("blocks".into(), blocks);
    fields.insert("revision".into(), Value::from(revision));
    let standing = store::standing_blocks(conn, user_id, &answer.week_start)?;
    if !standing.is_empty() {
        fields.insert("repeats".into(), Value::Array(standing));
    }
    Ok(Value::Object(fields))
}
