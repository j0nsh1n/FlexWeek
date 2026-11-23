//! The one save for an action that touches several things at once, for the app (`POST /api/changes`,
//! through `flexweek_service::changes`) and the assistant alike: homework saved and deleted, weeks written
//! (a Monday is one stored week; a week on screen from another day covers two), School and Setup's
//! activities changed from a week on, and a restore point made first when the save asks for one. All of it
//! commits together or not at all, and a save sent again with its operation id gets the first answer back.

use std::collections::BTreeMap;

use flexweek_engine::repeats::parse_intents;
use flexweek_engine::shown::{
    compose_shown_week_due, repeat_changes_from_shown_week, shown_parts, split_shown_week,
};
use flexweek_engine::snapshot::canonical;
use flexweek_engine::time::{is_calendar_date, is_week_start};
use flexweek_engine::validate::{time_block, week_request};
pub use rusqlite::Connection;
use serde_json::{Map, Value, json};

use crate::shown_weeks::{homework_of, seen_week, shown_week};
use crate::writes::{
    MAX_ASSIGNMENTS, WEEK_CONFLICT, conflict, refuse, remove_homework, write_homework, write_week,
};
use crate::{
    Recall, RepeatsFailure, StoreError, apply_repeat_intents, begin_immediate,
    create_restore_point, payload_digest, read_week, recall_operation, remember_operation,
    standing_blocks, week_with_standing,
};

const MAX_OPERATIONS: i64 = 100;
const MAX_RESTORE_POINTS: i64 = 20;
const OPERATION_CONFLICT: &str = "This operation was already used with different data.";
const ID_MISMATCH: &str = "assignment id in the path and body must match";
const SHOWN_WEEK_RULE: &str = "a Monday week has one revision";

#[derive(Debug)]
pub struct ApplyClock {
    pub now: String,
    pub restore_token: String,
}

#[derive(Debug)]
pub struct WeekInput {
    pub week_start: String,
    pub blocks: Vec<Value>,
    pub revision: Revision,
}

/// A Monday week is one stored week with one revision; a week on screen that starts on another day covers
/// two stored weeks and names both revisions.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Revision {
    Stored(i64),
    Shown(i64, i64),
}

impl From<i64> for Revision {
    fn from(revision: i64) -> Self {
        Self::Stored(revision)
    }
}

impl Revision {
    /// As the save's request writes it: one number, or the two for a week on screen.
    fn to_value(self) -> Value {
        match self {
            Self::Stored(revision) => json!(revision),
            Self::Shown(first, second) => json!([first, second]),
        }
    }
}

#[derive(Debug)]
pub struct AssignmentInput {
    pub id: String,
    pub assignment: Option<Value>,
    pub revision: i64,
}

#[derive(Debug)]
pub struct ApplyInput {
    pub weeks: Vec<WeekInput>,
    pub assignments: Vec<AssignmentInput>,
    pub operation_id: Option<String>,
    pub snapshot_label: Option<String>,
    /// Changes to School and Setup's activities as the student meant them
    /// (`flexweek_engine::repeats::Intent`), applied after the weeks are saved.
    pub repeats: Option<Vec<Value>>,
    /// When set, the operation row is keyed by this digest instead of the batch.
    /// A tool passes a digest of the assistant's arguments so a retry still matches
    /// after the write has changed the stored week.
    pub argument_digest: Option<String>,
}

/// What kind of refusal a save got, as the app tells them apart (bad input, not found, changed elsewhere).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RefusalKind {
    Invalid,
    NotFound,
    Conflict,
}

#[derive(Debug)]
pub enum ApplyFailure {
    Store(StoreError),
    Refused {
        kind: RefusalKind,
        message: String,
        current_revision: Option<i64>,
    },
}

impl From<StoreError> for ApplyFailure {
    fn from(error: StoreError) -> Self {
        Self::Store(error)
    }
}

impl From<RepeatsFailure> for ApplyFailure {
    fn from(failure: RepeatsFailure) -> Self {
        match failure {
            RepeatsFailure::Refused(message) => refuse(&message),
            RepeatsFailure::Store(error) => Self::Store(error),
        }
    }
}

impl From<flexweek_engine::EngineError> for ApplyFailure {
    fn from(error: flexweek_engine::EngineError) -> Self {
        Self::Store(StoreError::Engine(error))
    }
}

pub fn apply(
    conn: &Connection,
    user_id: i64,
    input: &ApplyInput,
    clock: &ApplyClock,
) -> Result<Value, ApplyFailure> {
    begin_immediate(conn)?;
    match apply_tx(conn, user_id, input, clock) {
        Ok(value) => match conn.execute("COMMIT", []) {
            Ok(_) => Ok(value),
            Err(error) => {
                let _ = conn.execute("ROLLBACK", []);
                Err(StoreError::Sqlite(error).into())
            }
        },
        Err(error) => {
            let _ = conn.execute("ROLLBACK", []);
            Err(error)
        }
    }
}

/// `apply` for a caller that already holds the write lock (`begin_immediate`), so what it read to
/// build `input` cannot change before the batch is saved. A refused batch writes nothing, and the
/// caller still ends its own transaction.
pub fn apply_within(
    conn: &Connection,
    user_id: i64,
    input: &ApplyInput,
    clock: &ApplyClock,
) -> Result<Value, ApplyFailure> {
    conn.execute("SAVEPOINT apply_within", [])
        .map_err(StoreError::from)?;
    match apply_tx(conn, user_id, input, clock) {
        Ok(value) => {
            conn.execute("RELEASE apply_within", [])
                .map_err(StoreError::from)?;
            Ok(value)
        }
        Err(error) => {
            let _ = conn.execute("ROLLBACK TO apply_within", []);
            let _ = conn.execute("RELEASE apply_within", []);
            Err(error)
        }
    }
}

fn apply_tx(
    conn: &Connection,
    user_id: i64,
    input: &ApplyInput,
    clock: &ApplyClock,
) -> Result<Value, ApplyFailure> {
    let digest = input
        .argument_digest
        .clone()
        .unwrap_or_else(|| batch_digest(input));
    if let Some(operation_id) = &input.operation_id {
        match recall_operation(conn, user_id, operation_id, &digest)? {
            Recall::Hit(response) => return parse_json(&response),
            Recall::Conflict => return Err(conflict(OPERATION_CONFLICT, None)),
            Recall::Missing => {}
        }
    }
    let point = match &input.snapshot_label {
        Some(label) => Some(create_restore_point(
            conn,
            user_id,
            &clock.restore_token,
            label,
            &clock.now,
            &[],
            MAX_RESTORE_POINTS,
        )?),
        None => None,
    };
    // A week on screen is checked against its stored weeks as they were before this save began, so homework
    // deleted in the same save does not count as someone else's change.
    let mut before = BTreeMap::new();
    for week in &input.weeks {
        if let Some((first, second)) = shown_parts_of(&week.week_start)? {
            for stored_start in [first, second] {
                if let std::collections::btree_map::Entry::Vacant(slot) = before.entry(stored_start)
                {
                    let revision = stored_revision(conn, user_id, slot.key())?;
                    slot.insert(revision);
                }
            }
        }
    }
    let assignments = apply_assignments(conn, user_id, &input.assignments)?;
    let mut changes = input.repeats.clone();
    for week in &input.weeks {
        if let Some(trimmed) = &changes
            && shown_parts_of(&week.week_start)?.is_some()
        {
            // From this week on, on screen: the stored week the shown one starts in keeps the change on its
            // shown days only, saved below; the repeat changes from the next Monday.
            changes = Some(repeat_changes_from_shown_week(trimmed, &week.week_start)?);
        }
    }
    // Stored (Monday) weeks first: an Undo that puts back a stored week a week on screen also shows sends
    // both, and the week on screen then finds them as it means them.
    let mut ordered = Vec::with_capacity(input.weeks.len());
    for week in &input.weeks {
        ordered.push((week, shown_parts_of(&week.week_start)?));
    }
    ordered.sort_by_key(|(_, shown)| shown.is_some());
    let mut repeats: Option<Value> = None;
    let mut answers = Vec::with_capacity(ordered.len());
    for (week, shown) in ordered {
        if let Some((first, second)) = shown {
            if let Some(changes) = &changes
                && repeats.is_none()
            {
                // A repeat changed from the next Monday stands there before the week on screen is split:
                // that week's days then match it and keep no copy of their own.
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
            return Err(refuse(SHOWN_WEEK_RULE));
        };
        let (blocks, revision) = write_week(
            conn,
            user_id,
            &week.week_start,
            checked_input(&week.blocks)?,
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
        // Saved weeks from the change's week on take it here; the open week is in `weeks`, already changed
        // by the client, so Undo takes back its part only.
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
    if let Some(operation_id) = &input.operation_id {
        remember_operation(
            conn,
            user_id,
            operation_id,
            &digest,
            &canonical(&result),
            MAX_OPERATIONS,
        )?;
    }
    Ok(result)
}

/// The blocks a caller sends, checked before anything is written: each reads as a block and the week as a
/// week, refused with the rule's own words. The app has checked them already, so for it this never refuses.
fn checked_input(blocks: &[Value]) -> Result<Vec<Value>, ApplyFailure> {
    let mut checked = Vec::with_capacity(blocks.len());
    for block in blocks {
        checked.push(
            time_block(block)
                .map(|block| block.to_value())
                .map_err(|why| refuse(&why))?,
        );
    }
    week_request(&json!({ "blocks": checked })).map_err(|why| refuse(&why))?;
    Ok(checked)
}

/// Homework saves first, then deletes, each answered as the app answers it.
fn apply_assignments(
    conn: &Connection,
    user_id: i64,
    changes: &[AssignmentInput],
) -> Result<Vec<Value>, ApplyFailure> {
    let mut results = Vec::with_capacity(changes.len());
    let mut deletes = Vec::new();
    for change in changes {
        let Some(body) = &change.assignment else {
            deletes.push(change);
            continue;
        };
        if body.get("id").and_then(Value::as_str) != Some(change.id.as_str()) {
            return Err(refuse(ID_MISMATCH));
        }
        let revision = write_homework(
            conn,
            user_id,
            &change.id,
            body,
            change.revision,
            MAX_ASSIGNMENTS,
        )?;
        results.push(json!({ "id": change.id, "revision": revision, "assignment": body }));
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

/// The stored weeks a week on screen covers when it does not start on a Monday.
fn shown_parts_of(week_start: &str) -> Result<Option<(String, String)>, ApplyFailure> {
    if is_week_start(week_start) || !is_calendar_date(week_start) {
        return Ok(None);
    }
    Ok(shown_parts(week_start)?.map(|(first, second, _)| (first, second)))
}

fn stored_revision(conn: &Connection, user_id: i64, week_start: &str) -> Result<i64, ApplyFailure> {
    Ok(read_week(conn, user_id, week_start)?.map_or(0, |(_, revision)| revision))
}

/// Changes the repeats as `changes` say, in every saved week from each change's week on.
fn apply_repeats(
    conn: &Connection,
    user_id: i64,
    changes: &[Value],
) -> Result<Value, ApplyFailure> {
    let intents = parse_intents(&Value::Array(changes.to_vec())).map_err(|why| refuse(&why))?;
    let outcome = apply_repeat_intents(conn, user_id, &intents)?;
    // The app read this part back from canonical text, so its keys come out sorted.
    parse_json(&canonical(&outcome.to_value()))
}

/// Splits a saved week on screen back into the stored weeks it covers and writes the ones it changed, each
/// at the revision it had before this save began.
fn save_shown_week(
    conn: &Connection,
    user_id: i64,
    week: &WeekInput,
    (first, second): (&str, &str),
    before: &BTreeMap<String, i64>,
) -> Result<(), ApplyFailure> {
    let (first_blocks, first_revision) = seen_week(conn, user_id, first)?;
    let (second_blocks, second_revision) = seen_week(conn, user_id, second)?;
    let both: Vec<Value> = first_blocks.iter().chain(&second_blocks).cloned().collect();
    let homework = homework_of(conn, user_id, &both)?;
    let now = compose_shown_week_due(&week.week_start, &first_blocks, &second_blocks, &homework)?;
    if canonical(&Value::Array(week.blocks.clone())) == canonical(&Value::Array(now)) {
        return Ok(());
    }
    if week.revision != Revision::Shown(before[first], before[second]) {
        return Err(conflict(WEEK_CONFLICT, None));
    }
    let (first_new, second_new) = split_shown_week(
        &week.week_start,
        &week.blocks,
        &first_blocks,
        &second_blocks,
    )?;
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

/// Every block written out again; the split came from blocks already checked, so one that no longer reads
/// came from stored data.
fn written(blocks: Vec<Value>) -> Result<Vec<Value>, ApplyFailure> {
    blocks
        .iter()
        .map(|block| {
            time_block(block)
                .map(|checked| checked.to_value())
                .map_err(|why| {
                    StoreError::Broken(format!("a saved block no longer reads: {why}")).into()
                })
        })
        .collect()
}

/// One week of the answer: the week as `GET /api/week` gives it.
struct WeekAnswer {
    week_start: String,
    shown: Option<(String, String)>,
    blocks: Vec<Value>,
    revision: i64,
}

fn week_answer(
    conn: &Connection,
    user_id: i64,
    answer: WeekAnswer,
    repeats_changed: bool,
) -> Result<Value, ApplyFailure> {
    if let Some((first, second)) = &answer.shown {
        return Ok(shown_week(
            conn,
            user_id,
            &answer.week_start,
            (first, second),
            || {},
        )?);
    }
    let mut stored = Value::Array(answer.blocks).to_string();
    let mut revision = answer.revision;
    if repeats_changed {
        // All weeks rewrites the open week's row too: the answer gives it as now stored.
        if let Some((text, now)) = read_week(conn, user_id, &answer.week_start)? {
            stored = text;
            revision = now;
        }
    }
    let blocks = parse_json(&week_with_standing(
        conn,
        user_id,
        &answer.week_start,
        &stored,
    )?)?;
    let mut fields = Map::new();
    fields.insert("week_start".into(), Value::from(answer.week_start.as_str()));
    fields.insert("blocks".into(), blocks);
    fields.insert("revision".into(), Value::from(revision));
    let standing = standing_blocks(conn, user_id, &answer.week_start)?;
    if !standing.is_empty() {
        fields.insert("repeats".into(), Value::Array(standing));
    }
    Ok(Value::Object(fields))
}

/// The key a save's operation id is remembered under when the caller gives none of its own: the save as the
/// app's request wrote it, so a save sent again across an update still finds its first answer.
pub fn batch_digest(input: &ApplyInput) -> String {
    payload_digest(&batch_value(input))
}

fn batch_value(input: &ApplyInput) -> Value {
    json!({
        "weeks": input.weeks.iter().map(|week| json!({
            "blocks": week.blocks,
            "week_start": week.week_start,
            "revision": week.revision.to_value(),
        })).collect::<Vec<_>>(),
        "assignments": input.assignments.iter().map(|change| json!({
            "id": change.id,
            "assignment": change.assignment,
            "revision": change.revision,
        })).collect::<Vec<_>>(),
        "operation_id": input.operation_id,
        "snapshot_label": input.snapshot_label,
        "repeats": input.repeats,
    })
}

fn parse_json(text: &str) -> Result<Value, ApplyFailure> {
    serde_json::from_str(text).map_err(|error| {
        ApplyFailure::Store(StoreError::Json {
            text: text.to_string(),
            error,
        })
    })
}
