//! Changes to repeating blocks as the student meant them (`flexweek_engine::repeats`), on today's
//! storage: a standing row per repeat and the Monday it holds from, and a copy in each saved week.
//! Both save handlers (`changes::apply` and the backend's `post_changes`) come here, so a change is
//! applied one way whoever sends it.

use flexweek_engine::repeats::{
    Edited, Intent, Kept, change_shown_start, edited_weeks_line, kept_notice, own_changes, patched,
    pieces_after_replace, restated_pieces, restated_version, stands_from,
};
use flexweek_engine::shown::{
    compose_shown_week, family_id, replaced_repeat_on_shown_week, shown_parts, split_shown_week,
};
use flexweek_engine::snapshot::canonical;
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::{Value, json};

use crate::{StoreError, StoreResult, defer_write, read_week, week_with_standing};

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

/// The versions after `intent`. A stop, or a change that replaces one-week edits, ends what stood
/// after `start`. A change that keeps those edits reaches a later version only where that version
/// had not changed the same thing itself, and a later stop stays.
fn rewritten(versions: &Versions, start: &str, new: Option<Value>, drop_later: bool) -> Versions {
    let mut out: Versions = versions
        .iter()
        .filter(|(from, _)| from.as_str() < start)
        .cloned()
        .collect();
    out.push((start.to_string(), new));
    if drop_later {
        return out;
    }
    for (from, body) in versions.iter().filter(|(from, _)| from.as_str() > start) {
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

fn family_of(block: &Value) -> Option<&str> {
    block.get("id").and_then(Value::as_str).map(family_id)
}

/// Apply `intents` in order: the repeat's rows from each change's week, then every saved week from
/// that week on, where a week's copy follows the change except on what that week changed itself.
/// The open week is usually in the same batch already changed by the client with the same rule
/// (`repeats::apply_to_week`), so this pass leaves it as it is.
fn seen_blocks(
    conn: &Connection,
    user_id: i64,
    monday: &str,
) -> Result<Vec<Value>, RepeatsFailure> {
    let raw = read_week(conn, user_id, monday)?
        .map(|(blocks, _)| blocks)
        .unwrap_or_else(|| "[]".to_string());
    let seen = week_with_standing(conn, user_id, monday, &raw)?;
    match parse(&seen)? {
        Value::Array(blocks) => Ok(blocks),
        _ => Ok(Vec::new()),
    }
}

fn write_week(
    conn: &Connection,
    user_id: i64,
    monday: &str,
    blocks: &[Value],
) -> Result<(), RepeatsFailure> {
    let encoded = canonical(&Value::Array(blocks.to_vec()));
    match read_week(conn, user_id, monday)? {
        Some((stored, _)) if stored == encoded => Ok(()),
        Some(_) => {
            defer_write(
                conn,
                "UPDATE weeks SET blocks = ?1, revision = revision + 1
                WHERE user_id = ?2 AND week_start = ?3",
                params![encoded, user_id, monday],
            )?;
            Ok(())
        }
        None => {
            defer_write(
                conn,
                "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, ?3, 1)",
                params![user_id, monday, encoded],
            )?;
            Ok(())
        }
    }
}

/// The shown week the change starts on may begin in the middle of a stored Monday. Split that week
/// the way a save of it would: days before it stay, and its own days take the new repeat.
fn write_seam(
    conn: &Connection,
    user_id: i64,
    intent: &Intent,
    new_body: Option<&Value>,
) -> Result<(), RepeatsFailure> {
    let start =
        change_shown_start(intent).map_err(|error| RepeatsFailure::Refused(error.message))?;
    let Some((first, second, _)) =
        shown_parts(&start).map_err(|error| RepeatsFailure::Refused(error.message))?
    else {
        return Ok(());
    };
    let first_blocks = seen_blocks(conn, user_id, &first)?;
    let second_blocks = seen_blocks(conn, user_id, &second)?;
    let shown = compose_shown_week(&start, &first_blocks, &second_blocks)
        .map_err(|error| RepeatsFailure::Refused(error.message))?;
    let replaced = replaced_repeat_on_shown_week(&start, &shown, &intent.id, new_body)
        .map_err(|error| RepeatsFailure::Refused(error.message))?;
    let (out_first, out_second) =
        split_shown_week(&start, &replaced, &first_blocks, &second_blocks)
            .map_err(|error| RepeatsFailure::Refused(error.message))?;
    write_week(conn, user_id, &first, &out_first)?;
    write_week(conn, user_id, &second, &out_second)?;
    Ok(())
}

pub fn apply_repeat_intents(
    conn: &Connection,
    user_id: i64,
    intents: &[Intent],
) -> Result<RepeatsOutcome, RepeatsFailure> {
    Ok(enact(conn, user_id, intents, true)?.0)
}

/// The later weeks a change would reach that have their own one-week edit, and the sentence that
/// asks about them. Nothing is written. An empty `line` means the client asks nothing.
pub fn preview_edited_weeks(
    conn: &Connection,
    user_id: i64,
    intents: &[Intent],
) -> Result<Value, RepeatsFailure> {
    let (outcome, titles) = enact(conn, user_id, intents, false)?;
    let mut weeks = Vec::new();
    let mut names = Vec::new();
    for kept in &outcome.kept {
        if !weeks.contains(&kept.week_start) {
            weeks.push(kept.week_start.clone());
        }
        if let Some(title) = titles
            .iter()
            .find(|(id, _)| id == &kept.id)
            .map(|(_, title)| title)
            && !names.contains(title)
        {
            names.push(title.clone());
        }
    }
    let line = edited_weeks_line(&weeks, &names)
        .map_err(|error| RepeatsFailure::Refused(error.message))?;
    Ok(json!({"weeks": weeks, "line": line}))
}

fn enact(
    conn: &Connection,
    user_id: i64,
    intents: &[Intent],
    write: bool,
) -> Result<(RepeatsOutcome, Vec<(String, String)>), RepeatsFailure> {
    let h24 = clock_24h(conn, user_id)?;
    let mut outcome = RepeatsOutcome::default();
    let mut titles: Vec<String> = Vec::new();
    let mut titled: Vec<(String, String)> = Vec::new();
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
            titles.push(title.clone());
        }
        if !titled.iter().any(|(id, _)| id == &intent.id) {
            titled.push((intent.id.clone(), title));
        }
        first_week.get_or_insert_with(|| week.clone());
        let start = stands_from(intent).map_err(|error| RepeatsFailure::Refused(error.message))?;
        // From today on, an open week later than today must still write from the day after today's
        // week. The earlier of the two is the bound for the standing row, the saved weeks, and
        // which version each of those weeks is compared with.
        let bound = if week.as_str() < start.as_str() {
            week.clone()
        } else {
            start.clone()
        };
        // Keeping one-week edits is the only answer that still merges a later version. The other
        // two write this change over them, from `start` on.
        let drop_later = intent.stop || intent.edited != Edited::Keep;
        let new = rewritten(&old, &start, new_here.clone(), drop_later);
        if write && intent.edited == Edited::FromToday {
            // The shown week after today may start mid stored week. The days before it stay, and
            // the days from that shown week on take the change, by the same split as any other
            // change from a week that does not start on Monday.
            write_seam(conn, user_id, intent, new_here.as_ref())?;
        }
        // A later change that stays where this one would have set the same thing is named too, at the
        // week it starts. A saved copy of that very week is named instead, against this change, below:
        // the copy is what the week shows, so naming both would say two things about one week.
        let mut later_versions: Vec<Kept> = Vec::new();
        if intent.edited == Edited::Keep
            && let Some(here) = &new_here
        {
            for (from, body) in new.iter().filter(|(from, _)| from.as_str() > week.as_str()) {
                let Some(body) = body else { continue };
                let changes = own_changes(body, here, std::slice::from_ref(body), h24);
                if !changes.is_empty() {
                    later_versions.push(Kept {
                        week_start: from.clone(),
                        id: intent.id.clone(),
                        changes,
                    });
                }
            }
        }
        if write {
            let position = match position {
                Some(position) => position,
                None => next_position(conn, user_id, &week)?,
            };
            write_versions(conn, user_id, &intent.id, position, &old, &new, &bound)?;
        }
        let mut stmt = conn.prepare(
            "SELECT week_start, blocks FROM weeks WHERE user_id = ?1 AND week_start >= ?2
            ORDER BY week_start",
        )?;
        let saved = stmt
            .query_map(params![user_id, bound], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
            })?
            .collect::<Result<Vec<_>, _>>()?;
        for (week_start, text) in saved {
            // Before the Monday the change stands from, a stored week is left alone. The one that
            // also holds the first days of the next shown week was split above.
            if intent.edited == Edited::FromToday && week_start.as_str() < start.as_str() {
                continue;
            }
            let (was, now) = (at(&old, &week_start), at(&new, &week_start));
            let version_starts_here = later_versions
                .iter()
                .any(|kept| kept.week_start == week_start);
            // A week this change does not reach is left as saved, but where a later version starts its
            // copy may still say something of its own that the version's line would misstate.
            // All weeks and From today on still replace a saved edit when the standing bodies match.
            let replaces = intent.edited != Edited::Keep;
            if was == now && !version_starts_here && !replaces {
                // The question is asked before any answer, so it names a week whose copy has its
                // own edit even when keeping edits leaves it alone: All weeks would replace it.
                if !write
                    && let Some(body) = was
                    && let Value::Array(stored) = parse(&text)?
                {
                    let mut changes = Vec::new();
                    for piece in stored.iter().filter(|block| {
                        block.get("id").and_then(Value::as_str).map(family_id)
                            == Some(intent.id.as_str())
                    }) {
                        for change in own_changes(piece, body, &stored, h24) {
                            if !changes.contains(&change) {
                                changes.push(change);
                            }
                        }
                    }
                    if !changes.is_empty() {
                        outcome.kept.push(Kept {
                            week_start: week_start.clone(),
                            id: intent.id.clone(),
                            changes,
                        });
                    }
                }
                continue;
            }
            let Value::Array(stored) = parse(&text)? else {
                continue;
            };
            // Every piece of the repeat in that week: School split at a seam is School on each side.
            let pieces: Vec<usize> = (0..stored.len())
                .filter(|at| {
                    stored[*at].get("id").and_then(Value::as_str).map(family_id)
                        == Some(intent.id.as_str())
                })
                .collect();
            if pieces.is_empty() {
                continue;
            }
            // A stop that keeps one-week edits names a saved week whose copy is not the standing
            // body, before that copy would be removed, and leaves the copy there.
            if intent.stop && intent.edited == Edited::Keep {
                let own = match was {
                    Some(body) => {
                        pieces.len() != 1
                            || pieces
                                .iter()
                                .any(|at| !own_changes(&stored[*at], body, &stored, h24).is_empty())
                    }
                    None => true,
                };
                if own {
                    let mut changes = Vec::new();
                    if let Some(body) = was {
                        for at in &pieces {
                            for change in own_changes(&stored[*at], body, &stored, h24) {
                                if !changes.contains(&change) {
                                    changes.push(change);
                                }
                            }
                        }
                    }
                    if changes.is_empty() {
                        changes.push("its own times".to_string());
                    }
                    outcome.kept.push(Kept {
                        week_start: week_start.clone(),
                        id: intent.id.clone(),
                        changes,
                    });
                    continue;
                }
            }
            let mut updated = stored.clone();
            if was != now || intent.edited != Edited::Keep {
                let copies: Vec<Value> = pieces.iter().map(|at| stored[*at].clone()).collect();
                let restated = if intent.edited == Edited::Keep {
                    restated_pieces(was, now, &copies, &intent.id)
                } else {
                    pieces_after_replace(&copies, now)
                };
                for (at, copy) in pieces.into_iter().zip(restated).rev() {
                    match copy {
                        Some(copy) => updated[at] = copy,
                        None => {
                            updated.remove(at);
                        }
                    }
                }
            }
            // School's own id, else a piece of it: a week can hold School only as a piece.
            let held = updated
                .iter()
                .position(|block| block.get("id").and_then(Value::as_str) == Some(&intent.id))
                .or_else(|| {
                    updated
                        .iter()
                        .position(|block| family_of(block) == Some(&intent.id))
                })
                .unwrap_or(updated.len());
            // Where a later version starts, the copy's own changes are measured against this change, as
            // the version's would have been, so the week is named once for everything it keeps.
            let measured_against = if version_starts_here {
                new_here.as_ref()
            } else {
                now
            };
            later_versions.retain(|kept| kept.week_start != week_start);
            if intent.edited == Edited::Keep
                && week_start > week
                && let (Some(now), Some(copy)) = (measured_against, updated.get(held))
                && family_of(copy) == now.get("id").and_then(Value::as_str)
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
            if write && updated != stored {
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
        outcome.kept.append(&mut later_versions);
    }
    outcome.changed_weeks.sort();
    outcome.kept.sort_by(|a, b| a.week_start.cmp(&b.week_start));
    if let Some(week) = first_week {
        outcome.notice = kept_notice(&titles, &week, &outcome.kept)?;
    }
    Ok((outcome, titled))
}
