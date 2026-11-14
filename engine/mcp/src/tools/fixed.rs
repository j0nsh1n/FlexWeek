//! Fixed time the assistant adds or changes, through the desktop's own edit
//! (`grid::apply_block_edit`, as `controller.py` `add_block`) and the block editor's checks
//! (`widgets.py` `BlockDialog.accept`): the end after the start, no new day or moved start in the
//! past, and fixed time only (homework has its own tools). Landing beside another block is
//! allowed, as in the app, and the reply names it. School and Setup's activities change this week
//! unless `every_week` stands the change from this week on, as the app's School hours do.

use flexweek_engine::desk::calendar::{FLEX_CATEGORIES, LOCKED_CATEGORIES};
use flexweek_engine::desk::grid::{apply_block_edit, is_setup_block, past_problem, span_clash};
use flexweek_engine::desk::weekmodel::clock_text;
use flexweek_engine::repeats::{apply_to_week, edit_intent};
use flexweek_engine::shown::{
    apply_repeats_to_shown_week, family_id, repeat_changes_from_shown_week,
};
use flexweek_engine::time::{clock_to_minutes, hhmm_to_minutes, minutes_to_hhmm};
use flexweek_store::{
    ApplyInput, AssignmentInput, Connection, WeekInput, read_week, standing_blocks,
    week_with_standing,
};
use rmcp::handler::server::wrapper::Parameters;
use rmcp::schemars::JsonSchema;
use rmcp::{tool, tool_router};
use serde::Deserialize;
use serde_json::{Value, json};

use super::homework;
use super::week::{self, RevisionArg, WeekTarget};
use super::write::{self, REACHES_PHONE};
use crate::session;

const FLEXIBLE: &str = "Use the homework editor for flexible work.";
const NOT_IN_WEEK: &str = "That block is not in this week, so nothing changed.";
const NOT_STANDING: &str =
    "Only School and Setup's activities stand in every week, so every_week does not apply.";
const DAYS_RULE: &str =
    "days must name at least one day, 0 (the week's first day) to 6 (its last), once each";
const DEFAULT_CATEGORY: &str = "extra";

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct AddArgs {
    operation_id: String,
    week_start: String,
    title: String,
    /// Days of the week it is on, 0 (the week's first day) to 6 (its last). Several days repeat it this week.
    days: Vec<i64>,
    start: String,
    /// HH:MM; 24:00 is the end of the day.
    end: String,
    /// One of class, exercise, extra, meals, sleep, free. Default extra.
    #[serde(default)]
    category: Option<String>,
    /// When given, a week changed since then is a conflict. `[first_revision, second_revision]` for a non-Monday week.
    #[serde(default)]
    expected_revision: Option<RevisionArg>,
}

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct EditArgs {
    operation_id: String,
    week_start: String,
    expected_revision: RevisionArg,
    block_id: String,
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    start: Option<String>,
    #[serde(default)]
    end: Option<String>,
    #[serde(default)]
    days: Option<Vec<i64>>,
    #[serde(default)]
    category: Option<String>,
    /// "series" (default) or "occurrence" with `day`: that day alone becomes a block of its own.
    #[serde(default)]
    scope: Option<String>,
    #[serde(default)]
    day: Option<i64>,
    /// School or a Setup activity only: the change stands in this week and every week after.
    #[serde(default)]
    every_week: Option<bool>,
}

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct SkipArgs {
    operation_id: String,
    week_start: String,
    expected_revision: RevisionArg,
    block_id: String,
    day: i64,
    /// false takes the skip back. Default true.
    #[serde(default)]
    skipped: Option<bool>,
}

/// A week as the student sees it, with the standing School and activities merged in, as
/// `GET /api/week` serves it, and its saved revision (0 for a week nobody saved).
pub(crate) fn seen_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> Result<(Vec<Value>, i64), String> {
    let monday = flexweek_engine::time::monday_of(week_start).map_err(|err| err.message)?;
    if monday != week_start {
        return Err("week_start must be a Monday".into());
    }
    let row = read_week(conn, user_id, week_start).map_err(session::storage_sentence)?;
    let stored = row.as_ref().map_or("[]", |(text, _)| text.as_str());
    let merged =
        week_with_standing(conn, user_id, week_start, stored).map_err(session::storage_sentence)?;
    let blocks = homework::parse_blocks(&merged)?;
    Ok((blocks, row.map_or(0, |(_, revision)| revision)))
}

pub(crate) fn find(blocks: &[Value], id: &str) -> Option<Value> {
    blocks
        .iter()
        .find(|block| block.get("id").and_then(Value::as_str) == Some(id))
        .cloned()
}

fn category_of(given: Option<&str>) -> Result<String, String> {
    let category = given.unwrap_or(DEFAULT_CATEGORY);
    if FLEX_CATEGORIES.contains(&category) {
        return Err(FLEXIBLE.into());
    }
    if !LOCKED_CATEGORIES.contains(&category) {
        return Err(format!(
            "category must be one of {}",
            LOCKED_CATEGORIES.join(", ")
        ));
    }
    Ok(category.to_string())
}

fn days_of(days: &[i64]) -> Result<Vec<i64>, String> {
    let mut sorted = days.to_vec();
    sorted.sort_unstable();
    sorted.dedup();
    if days.is_empty()
        || sorted.len() != days.len()
        || sorted.iter().any(|day| !(0..=6).contains(day))
    {
        return Err(DAYS_RULE.into());
    }
    Ok(sorted)
}

fn span_of(start: &str, end: &str) -> Result<(i64, i64), String> {
    let start_min = hhmm_to_minutes(start).map_err(|err| err.message)?;
    let end_min = clock_to_minutes(end).map_err(|err| err.message)?;
    if end_min <= start_min {
        return Err(format!(
            "End needs to be later than Start ({}).",
            clock_text(start_min)
        ));
    }
    Ok((start_min, end_min))
}

fn past_of(app: &crate::App, week_start: &str, day: i64, start_min: i64) -> Result<(), String> {
    let now = app.now()?;
    match past_problem(
        "locked", week_start, day, start_min, &now.today, now.minute, 15,
    )
    .map_err(|err| err.message)?
    {
        Some(words) => Err(words),
        None => Ok(()),
    }
}

fn beside(blocks: &[Value], block: &Value) -> Result<Option<String>, String> {
    let Some(start) = block.get("start").and_then(Value::as_str) else {
        return Ok(None);
    };
    let start_min = hhmm_to_minutes(start).map_err(|err| err.message)?;
    let end_min = start_min + block["duration_min"].as_i64().unwrap_or(0);
    for day in block["days"].as_array().into_iter().flatten() {
        if let Some(title) = span_clash(
            &Value::Array(blocks.to_vec()),
            &block["id"],
            day,
            start_min,
            end_min,
        )
        .map_err(|err| err.message)?
        {
            return Ok(Some(title));
        }
    }
    Ok(None)
}

fn fresh_ids(operation_id: &str) -> impl FnMut() -> String {
    let seed = flexweek_store::digest(&format!("block:{operation_id}"));
    let mut count = 0_i64;
    move || {
        count += 1;
        format!("{seed}-{count}")
    }
}

fn week_input(week_start: &str, blocks: Vec<Value>, revision: i64) -> ApplyInput {
    ApplyInput {
        weeks: vec![WeekInput {
            week_start: week_start.to_string(),
            blocks,
            revision,
        }],
        assignments: Vec::<AssignmentInput>::new(),
        operation_id: None,
        snapshot_label: None,
        repeats: None,
        argument_digest: None,
    }
}

/// The answer to a fixed-time write, from what `apply` saved. A retry gets the same answer from
/// the remembered save.
fn saved(applied: &Value, block_id: &str, operation_id: &str) -> Result<Value, String> {
    if applied.get("error").is_some() {
        return Ok(applied.clone());
    }
    if let Some(reply) = applied.get("shown_reply") {
        return Ok(reply.clone());
    }
    let week = applied
        .get("weeks")
        .and_then(Value::as_array)
        .and_then(|items| items.first())
        .ok_or_else(|| session::STORAGE_UNAVAILABLE.to_string())?;
    let week_start = week
        .get("week_start")
        .and_then(Value::as_str)
        .ok_or_else(|| session::STORAGE_UNAVAILABLE.to_string())?;
    let blocks = week["blocks"].as_array().cloned().unwrap_or_default();
    let next_to = match find(&blocks, block_id) {
        Some(block) => beside(&blocks, &block)?,
        None => None,
    };
    let revision = week.get("revision").cloned().unwrap_or(Value::Null);
    Ok(json!({
        "ok": true,
        "result": {
            "week_start": week_start,
            "week_starts_on": week::weekday_name(week_start)?,
            "revision": revision,
            "block_id": block_id,
            "beside": next_to,
        },
        "revision": revision,
        "restore_point": write::point_id(operation_id),
        "reaches_phone": REACHES_PHONE,
    }))
}

fn build_shown_saved_reply(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
    first: &str,
    second: &str,
    block_id: &str,
    operation_id: &str,
) -> Result<Value, String> {
    let (first_after, new_r1) = seen_week(conn, user_id, first)?;
    let (second_after, new_r2) = seen_week(conn, user_id, second)?;
    let shown_after =
        week::compose_shown_blocks(conn, user_id, week_start, &first_after, &second_after)?;
    let next_to = match find(&shown_after, block_id) {
        Some(block) => beside(&shown_after, &block)?,
        None => None,
    };
    Ok(json!({
        "ok": true,
        "result": {
            "week_start": week_start,
            "week_starts_on": week::weekday_name(week_start)?,
            "revision": [new_r1, new_r2],
            "block_id": block_id,
            "beside": next_to,
        },
        "revision": [new_r1, new_r2],
        "restore_point": write::point_id(operation_id),
        "reaches_phone": REACHES_PHONE,
    }))
}

fn perform_add(app: &crate::App, args: &AddArgs) -> Result<Value, String> {
    let opened = homework::open(app)?;
    let operation_id = write::operation_key(&args.operation_id)?;
    let digest = write::argument_digest(
        "add_block",
        &args.operation_id,
        &json!({
            "category": args.category,
            "days": args.days,
            "end": args.end,
            "expected_revision": args.expected_revision,
            "start": args.start,
            "title": args.title,
            "week_start": args.week_start,
        }),
    );
    let block_id = flexweek_store::digest(&format!("fixed:{}", args.operation_id));
    if let Some(remembered) =
        homework::remembered(&opened.conn, opened.user_id, &operation_id, &digest)?
    {
        return saved(&remembered, &block_id, &operation_id);
    }
    let category = category_of(args.category.as_deref())?;
    let days = days_of(&args.days)?;
    let (start_min, end_min) = span_of(&args.start, &args.end)?;
    let target = week::resolve_week(&args.week_start, app.first_weekday())?;
    for day in &days {
        past_of(app, &args.week_start, *day, start_min)?;
    }
    let block = json!({
        "id": block_id,
        "title": args.title.trim(),
        "kind": "locked",
        "category": category,
        "days": days,
        "start": minutes_to_hhmm(start_min),
        "duration_min": end_min - start_min,
        "priority": 3,
        "energy": "medium",
    });
    match target {
        WeekTarget::StoredMonday => {
            let (blocks, revision) = seen_week(&opened.conn, opened.user_id, &args.week_start)?;
            let expected = week::expect_monday_revision(args.expected_revision.as_ref(), revision)?;
            let mut fresh = fresh_ids(&args.operation_id);
            let edited = apply_block_edit(
                &Value::Array(blocks),
                &block,
                &json!("series"),
                &Value::Null,
                &mut fresh,
            )
            .map_err(|err| err.message)?;
            let applied = homework::run_apply(
                &opened.conn,
                opened.user_id,
                "add_block",
                &operation_id,
                &digest,
                week_input(&args.week_start, edited, expected),
                &homework::clock_of(app)?,
            )?;
            saved(&applied, &block_id, &operation_id)
        }
        WeekTarget::Shown { first, second, .. } => {
            let (first_blocks, first_rev) = seen_week(&opened.conn, opened.user_id, &first)?;
            let (second_blocks, second_rev) = seen_week(&opened.conn, opened.user_id, &second)?;
            let expected = week::expect_shown_revision(
                args.expected_revision.as_ref(),
                [first_rev, second_rev],
            )?;
            if let Err(conflict) =
                week::check_shown_revision(&opened.conn, first_rev, second_rev, expected)
            {
                return Ok(conflict);
            }
            let shown_blocks = week::compose_shown_blocks(
                &opened.conn,
                opened.user_id,
                &args.week_start,
                &first_blocks,
                &second_blocks,
            )?;
            let mut fresh = fresh_ids(&args.operation_id);
            let edited = apply_block_edit(
                &Value::Array(shown_blocks),
                &block,
                &json!("series"),
                &Value::Null,
                &mut fresh,
            )
            .map_err(|err| err.message)?;
            let weeks = week::split_shown_inputs(
                &args.week_start,
                &edited,
                &first,
                &first_blocks,
                first_rev,
                &second,
                &second_blocks,
                second_rev,
            )?;
            let input = ApplyInput {
                weeks,
                assignments: Vec::<AssignmentInput>::new(),
                operation_id: None,
                snapshot_label: None,
                repeats: None,
                argument_digest: None,
            };
            let applied = homework::run_apply(
                &opened.conn,
                opened.user_id,
                "add_block",
                &operation_id,
                &digest,
                input,
                &homework::clock_of(app)?,
            )?;
            if applied.get("error").is_some() {
                return Ok(applied);
            }
            let answer = build_shown_saved_reply(
                &opened.conn,
                opened.user_id,
                &args.week_start,
                &first,
                &second,
                &block_id,
                &operation_id,
            )?;
            week::remember_shown_reply(
                &opened.conn,
                opened.user_id,
                &operation_id,
                &applied,
                &answer,
            )?;
            Ok(answer)
        }
    }
}

/// `BlockDialog._moved_into_the_past` for a block that exists: only a day it is newly on, or a
/// start moved on one day, may not be in the past. A series keeps a start it already had, so
/// School can still be edited after Monday.
fn edit_past(
    app: &crate::App,
    week_start: &str,
    original: &Value,
    chosen: &[i64],
    start: &str,
) -> Result<(), String> {
    let had: Vec<i64> = original["days"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_i64)
        .collect();
    let original_start = original["start"].as_str().unwrap_or("");
    let start_min = hhmm_to_minutes(start).map_err(|err| err.message)?;
    for day in chosen {
        let added = !had.contains(day);
        let moved = chosen.len() == 1 && had.contains(day) && start != original_start;
        if added || moved {
            past_of(app, week_start, *day, start_min)?;
        }
    }
    Ok(())
}

#[allow(clippy::too_many_lines)]
fn perform_edit(app: &crate::App, args: &EditArgs) -> Result<Value, String> {
    let opened = homework::open(app)?;
    let operation_id = write::operation_key(&args.operation_id)?;
    let digest = write::argument_digest(
        "edit_block",
        &args.operation_id,
        &json!({
            "block_id": args.block_id,
            "category": args.category,
            "day": args.day,
            "days": args.days,
            "end": args.end,
            "every_week": args.every_week.unwrap_or(false),
            "expected_revision": args.expected_revision,
            "scope": args.scope,
            "start": args.start,
            "title": args.title,
            "week_start": args.week_start,
        }),
    );
    let occurrence = args.scope.as_deref() == Some("occurrence");
    if let Some(remembered) =
        homework::remembered(&opened.conn, opened.user_id, &operation_id, &digest)?
    {
        let shown = edited_id(&remembered, args, occurrence);
        return saved(&remembered, &shown, &operation_id);
    }
    if let Some(scope) = &args.scope
        && scope != "series"
        && scope != "occurrence"
    {
        return Err("scope must be series or occurrence".into());
    }
    let target = week::resolve_week(&args.week_start, app.first_weekday())?;
    let (shown_blocks, monday_rev, shown_parts) = match target {
        WeekTarget::StoredMonday => {
            let (blocks, _) = seen_week(&opened.conn, opened.user_id, &args.week_start)?;
            let expected = week::expect_monday_revision(Some(&args.expected_revision), 0)?;
            (blocks, Some(expected), None)
        }
        WeekTarget::Shown {
            first,
            second,
            offset,
        } => {
            let (first_blocks, first_rev) = seen_week(&opened.conn, opened.user_id, &first)?;
            let (second_blocks, second_rev) = seen_week(&opened.conn, opened.user_id, &second)?;
            let shown_blocks = week::compose_shown_blocks(
                &opened.conn,
                opened.user_id,
                &args.week_start,
                &first_blocks,
                &second_blocks,
            )?;
            (
                shown_blocks,
                None,
                Some((
                    first,
                    first_blocks,
                    first_rev,
                    second,
                    second_blocks,
                    second_rev,
                    offset,
                )),
            )
        }
    };
    let Some(original) = find(&shown_blocks, &args.block_id) else {
        return Err(NOT_IN_WEEK.into());
    };
    if original["kind"] != json!("locked") {
        return Err(FLEXIBLE.into());
    }
    let setup = is_setup_block(&original).map_err(|err| err.message)?;
    let every_week = args.every_week.unwrap_or(false);
    if every_week && (!setup || occurrence) {
        return Err(NOT_STANDING.into());
    }
    if occurrence && args.day.is_none() {
        return Err("an occurrence edit needs the day".into());
    }
    let held_start = original["start"].as_str().unwrap_or("").to_string();
    let held_length = original["duration_min"].as_i64().unwrap_or(0);
    let start = args.start.clone().unwrap_or_else(|| held_start.clone());
    // A new start alone keeps the length, as dragging does.
    let end = match &args.end {
        Some(end) => end.clone(),
        None => {
            let begin = hhmm_to_minutes(&start).map_err(|err| err.message)?;
            minutes_to_hhmm(begin + held_length)
        }
    };
    let (start_min, end_min) = span_of(&start, &end)?;
    let days = match &args.days {
        Some(days) if !occurrence => days_of(days)?,
        _ => original["days"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_i64)
            .collect(),
    };
    let chosen = match (occurrence, args.day) {
        (true, Some(day)) => vec![day],
        _ => days.clone(),
    };
    edit_past(
        app,
        &args.week_start,
        &original,
        &chosen,
        &args.start.clone().unwrap_or(held_start),
    )?;
    let mut candidate = original.clone();
    if let Some(fields) = candidate.as_object_mut() {
        if let Some(title) = &args.title {
            fields.insert("title".into(), json!(title.trim()));
        }
        if args.category.is_some() {
            fields.insert(
                "category".into(),
                json!(category_of(args.category.as_deref())?),
            );
        }
        fields.insert("days".into(), json!(days));
        fields.insert("start".into(), json!(minutes_to_hhmm(start_min)));
        fields.insert("duration_min".into(), json!(end_min - start_min));
        let missed: Vec<Value> = fields
            .get("missed_days")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter(|day| day.as_i64().is_some_and(|day| days.contains(&day)))
            .cloned()
            .collect();
        fields.insert("missed_days".into(), Value::Array(missed));
    }
    let Some((first, first_blocks, first_rev, second, second_blocks, second_rev, offset)) =
        shown_parts
    else {
        let expected = monday_rev.unwrap_or(0);
        let input = if every_week {
            every_week_input(
                &opened.conn,
                opened.user_id,
                args,
                &shown_blocks,
                start_min,
                end_min,
                expected,
            )?
        } else {
            let mut fresh = fresh_ids(&args.operation_id);
            let edited = apply_block_edit(
                &Value::Array(shown_blocks),
                &candidate,
                &json!(if occurrence { "occurrence" } else { "series" }),
                &args.day.map_or(Value::Null, Value::from),
                &mut fresh,
            )
            .map_err(|err| err.message)?;
            week_input(&args.week_start, edited, expected)
        };
        let applied = homework::run_apply(
            &opened.conn,
            opened.user_id,
            "edit_block",
            &operation_id,
            &digest,
            input,
            &homework::clock_of(app)?,
        )?;
        let shown = edited_id(&applied, args, occurrence);
        return saved(&applied, &shown, &operation_id);
    };
    let expected =
        week::expect_shown_revision(Some(&args.expected_revision), [first_rev, second_rev])?;
    if let Err(conflict) = week::check_shown_revision(&opened.conn, first_rev, second_rev, expected)
    {
        return Ok(conflict);
    }
    let input = if every_week {
        every_week_shown_input(
            &opened.conn,
            opened.user_id,
            args,
            &shown_blocks,
            &first,
            &first_blocks,
            first_rev,
            &second,
            &second_blocks,
            second_rev,
            offset,
            start_min,
            end_min,
        )?
    } else {
        let mut fresh = fresh_ids(&args.operation_id);
        let edited = apply_block_edit(
            &Value::Array(shown_blocks),
            &candidate,
            &json!(if occurrence { "occurrence" } else { "series" }),
            &args.day.map_or(Value::Null, Value::from),
            &mut fresh,
        )
        .map_err(|err| err.message)?;
        let weeks = week::split_shown_inputs(
            &args.week_start,
            &edited,
            &first,
            &first_blocks,
            first_rev,
            &second,
            &second_blocks,
            second_rev,
        )?;
        ApplyInput {
            weeks,
            assignments: Vec::<AssignmentInput>::new(),
            operation_id: None,
            snapshot_label: None,
            repeats: None,
            argument_digest: None,
        }
    };
    let applied = homework::run_apply(
        &opened.conn,
        opened.user_id,
        "edit_block",
        &operation_id,
        &digest,
        input,
        &homework::clock_of(app)?,
    )?;
    if applied.get("error").is_some() {
        return Ok(applied);
    }
    let (first_after, new_r1) = seen_week(&opened.conn, opened.user_id, &first)?;
    let (second_after, new_r2) = seen_week(&opened.conn, opened.user_id, &second)?;
    let shown_after = week::compose_shown_blocks(
        &opened.conn,
        opened.user_id,
        &args.week_start,
        &first_after,
        &second_after,
    )?;
    let shown_id = if occurrence {
        let fresh = flexweek_store::digest(&format!("block:{}", args.operation_id));
        shown_after
            .iter()
            .filter_map(|block| block["id"].as_str())
            .find(|id| id.starts_with(&fresh))
            .map_or_else(|| args.block_id.clone(), str::to_string)
    } else {
        args.block_id.clone()
    };
    let next_to = match find(&shown_after, &shown_id) {
        Some(block) => beside(&shown_after, &block)?,
        None => None,
    };
    let answer = json!({
        "ok": true,
        "result": {
            "week_start": args.week_start,
            "week_starts_on": week::weekday_name(&args.week_start)?,
            "revision": [new_r1, new_r2],
            "block_id": shown_id,
            "beside": next_to,
        },
        "revision": [new_r1, new_r2],
        "restore_point": write::point_id(&operation_id),
        "reaches_phone": REACHES_PHONE,
    });
    week::remember_shown_reply(
        &opened.conn,
        opened.user_id,
        &operation_id,
        &applied,
        &answer,
    )?;
    Ok(answer)
}

/// An `every_week` edit: only the arguments the assistant named change, from this week on, measured
/// against the repeat rather than this week's copy, so what this week changed itself (a skipped day,
/// a one-week name) neither spreads to later weeks nor is lost here.
fn every_week_input(
    conn: &Connection,
    user_id: i64,
    args: &EditArgs,
    blocks: &[Value],
    start_min: i64,
    end_min: i64,
    expected_revision: i64,
) -> Result<ApplyInput, String> {
    let repeats =
        standing_blocks(conn, user_id, &args.week_start).map_err(session::storage_sentence)?;
    // A piece of School split off at a week's seam changes School.
    let family = family_id(&args.block_id);
    let Some(repeat) = find(&repeats, family) else {
        return Err(NOT_STANDING.into());
    };
    let mut wanted = repeat.clone();
    if let Some(fields) = wanted.as_object_mut() {
        if let Some(title) = &args.title {
            fields.insert("title".into(), json!(title.trim()));
        }
        if args.category.is_some() {
            fields.insert(
                "category".into(),
                json!(category_of(args.category.as_deref())?),
            );
        }
        if args.start.is_some() || args.end.is_some() {
            fields.insert("start".into(), json!(minutes_to_hhmm(start_min)));
            fields.insert("duration_min".into(), json!(end_min - start_min));
        }
        if let Some(days) = &args.days {
            fields.insert("days".into(), json!(days_of(days)?));
        }
    }
    let mut input = week_input(&args.week_start, blocks.to_vec(), expected_revision);
    let Some(intent) = edit_intent(family, &args.week_start, Some(&repeat), Some(&wanted)) else {
        return Ok(input);
    };
    let (week, _) = apply_to_week(blocks, &repeats, std::slice::from_ref(&intent))?;
    input.weeks[0].blocks = week;
    input.repeats = Some(vec![intent.to_value()]);
    Ok(input)
}

#[allow(clippy::too_many_arguments)]
fn every_week_shown_input(
    conn: &Connection,
    user_id: i64,
    args: &EditArgs,
    shown_blocks: &[Value],
    first: &str,
    first_blocks: &[Value],
    first_rev: i64,
    second: &str,
    second_blocks: &[Value],
    second_rev: i64,
    offset: i64,
    start_min: i64,
    end_min: i64,
) -> Result<ApplyInput, String> {
    let repeats = standing_blocks(conn, user_id, second).map_err(session::storage_sentence)?;
    let family = family_id(&args.block_id);
    let Some(repeat) = find(&repeats, family) else {
        return Err(NOT_STANDING.into());
    };
    let mut wanted = repeat.clone();
    if let Some(fields) = wanted.as_object_mut() {
        if let Some(title) = &args.title {
            fields.insert("title".into(), json!(title.trim()));
        }
        if args.category.is_some() {
            fields.insert(
                "category".into(),
                json!(category_of(args.category.as_deref())?),
            );
        }
        if args.start.is_some() || args.end.is_some() {
            fields.insert("start".into(), json!(minutes_to_hhmm(start_min)));
            fields.insert("duration_min".into(), json!(end_min - start_min));
        }
        if let Some(days) = &args.days {
            let mut weekdays: Vec<i64> = days_of(days)?
                .into_iter()
                .map(|day| (day + offset).rem_euclid(7))
                .collect();
            weekdays.sort_unstable();
            weekdays.dedup();
            fields.insert("days".into(), json!(weekdays));
        }
    }
    let Some(intent_shown) = edit_intent(family, &args.week_start, Some(&repeat), Some(&wanted))
    else {
        return Ok(ApplyInput {
            weeks: Vec::new(),
            assignments: Vec::new(),
            operation_id: None,
            snapshot_label: None,
            repeats: None,
            argument_digest: None,
        });
    };
    let intent_second_val =
        repeat_changes_from_shown_week(&[intent_shown.to_value()], &args.week_start)
            .map_err(|err| err.message)?
            .into_iter()
            .next()
            .ok_or_else(|| session::STORAGE_UNAVAILABLE.to_string())?;
    let intent_second = edit_intent(family, second, Some(&repeat), Some(&wanted))
        .ok_or_else(|| session::STORAGE_UNAVAILABLE.to_string())?;
    let (second_after_repeat, _) = apply_to_week(
        second_blocks,
        &repeats,
        std::slice::from_ref(&intent_second),
    )?;
    let (shown_after, _) = apply_repeats_to_shown_week(
        &args.week_start,
        shown_blocks,
        &repeats,
        std::slice::from_ref(&intent_shown),
    )?;
    let weeks = week::split_shown_inputs(
        &args.week_start,
        &shown_after,
        first,
        first_blocks,
        first_rev,
        second,
        &second_after_repeat,
        second_rev,
    )?;
    Ok(ApplyInput {
        weeks,
        assignments: Vec::<AssignmentInput>::new(),
        operation_id: None,
        snapshot_label: None,
        repeats: Some(vec![intent_second_val]),
        argument_digest: None,
    })
}

/// The block the edit left on the asked day: a day split off a series has an id of its own.
fn edited_id(applied: &Value, args: &EditArgs, occurrence: bool) -> String {
    if !occurrence {
        return args.block_id.clone();
    }
    let blocks = applied["weeks"][0]["blocks"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let fresh = flexweek_store::digest(&format!("block:{}", args.operation_id));
    blocks
        .iter()
        .filter_map(|block| block["id"].as_str())
        .find(|id| id.starts_with(&fresh))
        .map_or_else(|| args.block_id.clone(), str::to_string)
}

fn perform_skip(app: &crate::App, args: &SkipArgs) -> Result<Value, String> {
    let opened = homework::open(app)?;
    let operation_id = write::operation_key(&args.operation_id)?;
    let skipped = args.skipped.unwrap_or(true);
    let digest = write::argument_digest(
        "skip_block_day",
        &args.operation_id,
        &json!({
            "block_id": args.block_id,
            "day": args.day,
            "expected_revision": args.expected_revision,
            "skipped": skipped,
            "week_start": args.week_start,
        }),
    );
    if let Some(remembered) =
        homework::remembered(&opened.conn, opened.user_id, &operation_id, &digest)?
    {
        return saved(&remembered, &args.block_id, &operation_id);
    }
    let apply_skip = |blocks: &mut [Value]| -> Result<(), String> {
        let Some(block) = blocks
            .iter_mut()
            .find(|block| block.get("id").and_then(Value::as_str) == Some(args.block_id.as_str()))
        else {
            return Err(NOT_IN_WEEK.into());
        };
        let mut missed: Vec<i64> = block["missed_days"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_i64)
            .filter(|day| *day != args.day)
            .collect();
        if skipped {
            missed.push(args.day);
        }
        missed.sort_unstable();
        if let Some(fields) = block.as_object_mut() {
            fields.insert("missed_days".into(), json!(missed));
        }
        Ok(())
    };
    match week::resolve_week(&args.week_start, app.first_weekday())? {
        WeekTarget::StoredMonday => {
            let (mut blocks, _) = seen_week(&opened.conn, opened.user_id, &args.week_start)?;
            apply_skip(&mut blocks)?;
            let expected = week::expect_monday_revision(Some(&args.expected_revision), 0)?;
            // The store's check refuses a skip of homework or of a day the block is not on.
            let applied = homework::run_apply(
                &opened.conn,
                opened.user_id,
                "skip_block_day",
                &operation_id,
                &digest,
                week_input(&args.week_start, blocks, expected),
                &homework::clock_of(app)?,
            )?;
            saved(&applied, &args.block_id, &operation_id)
        }
        WeekTarget::Shown { first, second, .. } => {
            let (first_blocks, first_rev) = seen_week(&opened.conn, opened.user_id, &first)?;
            let (second_blocks, second_rev) = seen_week(&opened.conn, opened.user_id, &second)?;
            let mut shown_blocks = week::compose_shown_blocks(
                &opened.conn,
                opened.user_id,
                &args.week_start,
                &first_blocks,
                &second_blocks,
            )?;
            apply_skip(&mut shown_blocks)?;
            flexweek_engine::validate::week_request(&json!({"blocks": shown_blocks}))?;
            let expected = week::expect_shown_revision(
                Some(&args.expected_revision),
                [first_rev, second_rev],
            )?;
            if let Err(conflict) =
                week::check_shown_revision(&opened.conn, first_rev, second_rev, expected)
            {
                return Ok(conflict);
            }
            let weeks = week::split_shown_inputs(
                &args.week_start,
                &shown_blocks,
                &first,
                &first_blocks,
                first_rev,
                &second,
                &second_blocks,
                second_rev,
            )?;
            let input = ApplyInput {
                weeks,
                assignments: Vec::<AssignmentInput>::new(),
                operation_id: None,
                snapshot_label: None,
                repeats: None,
                argument_digest: None,
            };
            let applied = homework::run_apply(
                &opened.conn,
                opened.user_id,
                "skip_block_day",
                &operation_id,
                &digest,
                input,
                &homework::clock_of(app)?,
            )?;
            if applied.get("error").is_some() {
                return Ok(applied);
            }
            let answer = build_shown_saved_reply(
                &opened.conn,
                opened.user_id,
                &args.week_start,
                &first,
                &second,
                &args.block_id,
                &operation_id,
            )?;
            week::remember_shown_reply(
                &opened.conn,
                opened.user_id,
                &operation_id,
                &applied,
                &answer,
            )?;
            Ok(answer)
        }
    }
}

#[tool_router(router = fixed_tools, vis = "pub(crate)")]
impl crate::App {
    #[tool(
        description = "Add fixed time that is not homework (a break, a meal, rest, an event) on \
            one or more days of a week. It may sit beside other blocks, as in the app; the reply \
            names one it sits beside",
        annotations(read_only_hint = false, destructive_hint = false)
    )]
    async fn add_block(&self, Parameters(args): Parameters<AddArgs>) -> Result<String, String> {
        write::finish("add_block", perform_add(self, &args))
    }

    #[tool(
        description = "Change fixed time: title, start, end, days or category, for the series or \
            one day of it. School and Setup's activities change this week only unless every_week",
        annotations(read_only_hint = false, destructive_hint = false)
    )]
    async fn edit_block(&self, Parameters(args): Parameters<EditArgs>) -> Result<String, String> {
        write::finish("edit_block", perform_edit(self, &args))
    }

    #[tool(
        description = "Skip fixed time on one day of a week (a day off): it stays on the \
            calendar as missed and its time is free to plan. skipped false takes it back",
        annotations(read_only_hint = false, destructive_hint = false)
    )]
    async fn skip_block_day(
        &self,
        Parameters(args): Parameters<SkipArgs>,
    ) -> Result<String, String> {
        write::finish("skip_block_day", perform_skip(self, &args))
    }
}
