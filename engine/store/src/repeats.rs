//! Changes to repeating blocks as the student meant them (`flexweek_engine::repeats`), on today's
//! storage: a standing row per repeat and the Monday it holds from, and a copy in each saved week.
//! Both save handlers (`changes::apply` and the backend's `post_changes`) come here, so a change is
//! applied one way whoever sends it.

use flexweek_engine::repeats::{
    Intent, Kept, kept_notice, own_changes, patched, restated_copy, restated_version,
};
use flexweek_engine::snapshot::canonical;
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::{Value, json};

use crate::{StoreError, StoreResult, defer_write};

/// What a batch of changes did: the saved weeks it rewrote, the later weeks that kept a change of
/// their own, and the sentence that says so (None when none did).
#[derive(Debug, Default)]
pub struct RepeatsOutcome {
    pub changed_weeks: Vec<String>,
    pub kept: Vec<Kept>,
    pub notice: Option<String>,
}

impl RepeatsOutcome {
    pub fn to_value(&self) -> Value {
        json!({
            "changed_weeks": self.changed_weeks,
            "kept": self.kept.iter().map(Kept::to_value).collect::<Vec<_>>(),
            "notice": self.notice,
        })
    }
}

#[derive(Debug)]
pub enum RepeatsFailure {
    Refused(String),
    Store(StoreError),
}

impl From<StoreError> for RepeatsFailure {
    fn from(error: StoreError) -> Self {
        Self::Store(error)
    }
}

impl From<rusqlite::Error> for RepeatsFailure {
    fn from(error: rusqlite::Error) -> Self {
        Self::Store(StoreError::Sqlite(error))
    }
}

impl From<flexweek_engine::EngineError> for RepeatsFailure {
    fn from(error: flexweek_engine::EngineError) -> Self {
        Self::Store(StoreError::Engine(error))
    }
}

fn parse(text: &str) -> StoreResult<Value> {
    serde_json::from_str(text).map_err(|error| StoreError::Json {
        text: text.to_string(),
        error,
    })
}

/// One repeat's rows, oldest first: the Monday each holds from and its body (None for a stop).
type Versions = Vec<(String, Option<Value>)>;

fn versions(conn: &Connection, user_id: i64, id: &str) -> StoreResult<(Versions, Option<i64>)> {
    let mut stmt = conn.prepare(
        "SELECT from_week, position, body FROM standing_blocks WHERE user_id = ?1 AND id = ?2
        ORDER BY from_week",
    )?;
    let rows = stmt
        .query_map(params![user_id, id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, i64>(1)?,
                row.get::<_, Option<String>>(2)?,
            ))
        })?
        .collect::<Result<Vec<_>, _>>()?;
    let position = rows.first().map(|(_, position, _)| *position);
    let mut out = Vec::with_capacity(rows.len());
    for (from_week, _, body) in rows {
        out.push((from_week, body.as_deref().map(parse).transpose()?));
    }
    Ok((out, position))
}

/// The version standing in `week`.
fn at<'a>(versions: &'a Versions, week: &str) -> Option<&'a Value> {
    versions
        .iter()
        .rev()
        .find(|(from, _)| from.as_str() <= week)
        .and_then(|(_, body)| body.as_ref())
}

/// The version standing in the week before `week`.
fn before<'a>(versions: &'a Versions, week: &str) -> Option<&'a Value> {
    versions
        .iter()
        .rev()
        .find(|(from, _)| from.as_str() < week)
        .and_then(|(_, body)| body.as_ref())
}

/// The versions after `intent`. A stop ends the repeat for good from its week; any other change
/// reaches a later version only where that version had not changed the same thing itself, and a
/// later stop stays.
fn rewritten(versions: &Versions, week: &str, new: Option<Value>, stop: bool) -> Versions {
    let mut out: Versions = versions
        .iter()
        .filter(|(from, _)| from.as_str() < week)
        .cloned()
        .collect();
    out.push((week.to_string(), new));
    if stop {
        return out;
    }
    for (from, body) in versions.iter().filter(|(from, _)| from.as_str() > week) {
        let restated = restated_version(before(versions, from), before(&out, from), body.as_ref());
        out.push((from.clone(), restated));
    }
    out
}

fn clock_24h(conn: &Connection, user_id: i64) -> StoreResult<bool> {
    let comfort: Option<String> = conn
        .query_row(
            "SELECT comfort_json FROM preferences WHERE user_id = ?1",
            params![user_id],
            |row| row.get(0),
        )
        .optional()?;
    let Some(text) = comfort.filter(|text| !text.is_empty()) else {
        return Ok(false);
    };
    Ok(serde_json::from_str::<Value>(&text)
        .ok()
        .and_then(|comfort| comfort.get("clock_24h").and_then(Value::as_bool))
        .unwrap_or(false))
}

/// Where a new repeat goes in Setup's order: after those standing in its week.
fn next_position(conn: &Connection, user_id: i64, week: &str) -> StoreResult<i64> {
    Ok(crate::standing_blocks(conn, user_id, week)?.len() as i64)
}

fn write_versions(
    conn: &Connection,
    user_id: i64,
    id: &str,
    position: i64,
    old: &Versions,
    new: &Versions,
    week: &str,
) -> StoreResult<()> {
    for (from, _) in old.iter().filter(|(from, _)| from.as_str() >= week) {
        if !new.iter().any(|(kept, _)| kept == from) {
            defer_write(
                conn,
                "DELETE FROM standing_blocks WHERE user_id = ?1 AND id = ?2 AND from_week = ?3",
                params![user_id, id, from],
            )?;
        }
    }
    for (from, body) in new.iter().filter(|(from, _)| from.as_str() >= week) {
        if old.iter().any(|(was, held)| was == from && held == body) {
            continue;
        }
        let encoded = body.as_ref().map(canonical);
        defer_write(
            conn,
            "INSERT INTO standing_blocks(user_id, id, from_week, position, body)
            VALUES (?1, ?2, ?3, ?4, ?5)
            ON CONFLICT(user_id, id, from_week)
            DO UPDATE SET position = excluded.position, body = excluded.body",
            params![user_id, id, from, position, encoded],
        )?;
    }
    Ok(())
}

/// Apply `intents` in order: the repeat's rows from each change's week, then every saved week from
/// that week on, where a week's copy follows the change except on what that week changed itself.
/// The open week is usually in the same batch already changed by the client with the same rule
/// (`repeats::apply_to_week`), so this pass leaves it as it is.
pub fn apply_repeat_intents(
    conn: &Connection,
    user_id: i64,
    intents: &[Intent],
) -> Result<RepeatsOutcome, RepeatsFailure> {
    let h24 = clock_24h(conn, user_id)?;
    let mut outcome = RepeatsOutcome::default();
    let mut titles: Vec<String> = Vec::new();
    let mut first_week: Option<String> = None;
    for intent in intents {
        let week = intent.from_week()?;
        let (old, position) = versions(conn, user_id, &intent.id)?;
        let base = at(&old, &week).cloned();
        let new_here = patched(base.as_ref(), intent).map_err(RepeatsFailure::Refused)?;
        if new_here == base {
            continue;
        }
        let title = new_here
            .as_ref()
            .or(base.as_ref())
            .and_then(|body| body.get("title"))
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();
        if !titles.contains(&title) {
            titles.push(title);
        }
        first_week.get_or_insert_with(|| week.clone());
        let new = rewritten(&old, &week, new_here, intent.stop);
        let position = match position {
            Some(position) => position,
            None => next_position(conn, user_id, &week)?,
        };
        write_versions(conn, user_id, &intent.id, position, &old, &new, &week)?;
        let mut stmt = conn.prepare(
            "SELECT week_start, blocks FROM weeks WHERE user_id = ?1 AND week_start >= ?2
            ORDER BY week_start",
        )?;
        let saved = stmt
            .query_map(params![user_id, week], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
            })?
            .collect::<Result<Vec<_>, _>>()?;
        for (week_start, text) in saved {
            let (was, now) = (at(&old, &week_start), at(&new, &week_start));
            if was == now {
                continue;
            }
            let Value::Array(stored) = parse(&text)? else {
                continue;
            };
            let Some(held) = stored
                .iter()
                .position(|block| block.get("id").and_then(Value::as_str) == Some(&intent.id))
            else {
                continue;
            };
            let mut updated = stored.clone();
            match restated_copy(was, now, &stored[held]) {
                Some(copy) => updated[held] = copy,
                None => {
                    updated.remove(held);
                }
            }
            if week_start > week
                && let (Some(now), Some(copy)) = (now, updated.get(held))
                && copy.get("id") == now.get("id")
            {
                let changes = own_changes(copy, now, &updated, h24);
                if !changes.is_empty() {
                    outcome.kept.push(Kept {
                        week_start: week_start.clone(),
                        id: intent.id.clone(),
                        changes,
                    });
                }
            }
            if updated != stored {
                defer_write(
                    conn,
                    "UPDATE weeks SET blocks = ?1, revision = revision + 1
                    WHERE user_id = ?2 AND week_start = ?3",
                    params![canonical(&Value::Array(updated)), user_id, week_start],
                )?;
                if !outcome.changed_weeks.contains(&week_start) {
                    outcome.changed_weeks.push(week_start);
                }
            }
        }
    }
    outcome.changed_weeks.sort();
    if let Some(week) = first_week {
        outcome.notice = kept_notice(&titles, &week, &outcome.kept)?;
    }
    Ok(outcome)
}
