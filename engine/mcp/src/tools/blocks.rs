//! `move_block` calls `hand_move` and returns its words. `delete_block` calls
//! `desk::blocks::delete_block`. Both read the week with School and Setup's activities merged in,
//! as the app shows it; `every_week` also takes one of those out of the standing week.

use flexweek_engine::desk::blocks;
use flexweek_engine::desk::grid::is_setup_block;
use flexweek_engine::desk::hand_move::{HandDrop, HandMove, WeekClock, hand_move};
use flexweek_engine::repeats::{apply_to_week, edit_intent};
use flexweek_engine::shown::{family_id, repeat_changes_from_shown_week};
use flexweek_engine::time::hhmm_to_minutes;
use flexweek_store::{
    ApplyInput, AssignmentInput, Connection, WeekInput, list_assignment_rows, standing_blocks,
};
use rmcp::handler::server::wrapper::Parameters;
use rmcp::schemars::JsonSchema;
use rmcp::{tool, tool_router};
use serde::Deserialize;
use serde_json::{Map, Value, json};

use super::fixed::{find, seen_week};
use super::homework;
use super::week::{self, RevisionArg, WeekTarget};
use super::write::{self, REACHES_PHONE};
use crate::session;

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct MoveArgs {
    operation_id: String,
    week_start: String,
    expected_revision: RevisionArg,
    block_id: String,
    #[serde(default)]
    day: Option<i64>,
    start: String,
    end: String,
}

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct DeleteArgs {
    operation_id: String,
    week_start: String,
    expected_revision: RevisionArg,
    block_id: String,
    scope: String,
    #[serde(default)]
    day: Option<i64>,
    /// School or a Setup activity only: take it out of this week and every week after. Without
    /// it, it stays in this week missed on its days, as the app does.
    #[serde(default)]
    every_week: Option<bool>,
}

fn assignment_map(conn: &Connection, user_id: i64) -> Result<Map<String, Value>, String> {
    let rows = list_assignment_rows(conn, user_id).map_err(session::storage_sentence)?;
    let mut map = Map::new();
    for (id, body, revision) in rows {
        let mut value: Value =
            serde_json::from_str(&body).map_err(|_| session::STORAGE_UNAVAILABLE.to_string())?;
        if let Some(object) = value.as_object_mut() {
            object.insert("id".into(), json!(id.clone()));
            object.insert("revision".into(), json!(revision));
        }
        map.insert(id, value);
    }
    Ok(map)
}

fn sole_day(block: &Value) -> Option<i64> {
    let days = block.get("days")?.as_array()?;
    if days.len() == 1 {
        days.first().and_then(Value::as_i64)
    } else {
        None
    }
}

/// A block with no start has no day yet (`from_day` -1). One day is that day.
/// A repeating block is edited on the day the assistant named.
fn from_day_of(block: &Value, to_day: i64) -> i64 {
    let start = block.get("start").and_then(Value::as_str).unwrap_or("");
    if start.is_empty() {
        return -1;
    }
    let Some(days) = block.get("days").and_then(Value::as_array) else {
        return to_day;
    };
    if days.len() == 1 {
        return days.first().and_then(Value::as_i64).unwrap_or(to_day);
    }
    if days.iter().any(|day| day.as_i64() == Some(to_day)) {
        return to_day;
    }
    to_day
}

fn saved_week(applied: &Value) -> Result<Value, String> {
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
    let revision = week.get("revision").cloned().unwrap_or(Value::Null);
    Ok(json!({
        "ok": true,
        "result": {
            "week_start": week_start,
            "week_starts_on": week::weekday_name(week_start)?,
            "revision": revision,
        },
        "revision": revision,
        "reaches_phone": REACHES_PHONE,
    }))
}

fn week_input(week_start: String, blocks: Vec<Value>, revision: i64) -> ApplyInput {
    ApplyInput {
        weeks: vec![WeekInput {
            week_start,
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

fn perform_move(app: &crate::App, args: &MoveArgs) -> Result<Value, String> {
    let opened = homework::open(app)?;
    let operation_id = write::operation_key(&args.operation_id)?;
    let digest = write::argument_digest(
        "move_block",
        &args.operation_id,
        &json!({
            "block_id": args.block_id,
            "day": args.day,
            "end": args.end,
            "expected_revision": args.expected_revision,
            "start": args.start,
            "week_start": args.week_start,
        }),
    );
    if let Some(saved) = homework::remembered(&opened.conn, opened.user_id, &operation_id, &digest)?
    {
        return saved_week(&saved);
    }
    let target = week::resolve_week(&args.week_start, app.first_weekday())?;
    let (blocks, monday_rev, shown_parts) = match target {
        WeekTarget::StoredMonday => {
            let (blocks, _) = seen_week(&opened.conn, opened.user_id, &args.week_start)?;
            let expected = week::expect_monday_revision(Some(&args.expected_revision), 0)?;
            (blocks, Some(expected), None)
        }
        WeekTarget::Shown { first, second, .. } => {
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
                )),
            )
        }
    };
    let found = find(&blocks, &args.block_id);
    let to_day = args
        .day
        .or_else(|| found.as_ref().and_then(sole_day))
        .unwrap_or(-1);
    let from_day = found
        .as_ref()
        .map(|block| from_day_of(block, to_day))
        .unwrap_or(to_day);
    let start_min = hhmm_to_minutes(&args.start).map_err(|err| err.message)?;
    let end_min = hhmm_to_minutes(&args.end).map_err(|err| err.message)?;
    let assignments = Value::Object(assignment_map(&opened.conn, opened.user_id)?);
    let mut count = 0_i64;
    let mut fresh = || {
        count += 1;
        format!(
            "{}-{count}",
            flexweek_store::digest(&format!("block:{}", args.operation_id))
        )
    };
    let drop = HandDrop {
        block_id: &args.block_id,
        from_day,
        to_day,
        start_min,
        end_min,
    };
    let now = app.now()?;
    let clock = WeekClock {
        week_start: &args.week_start,
        now_iso: &now.today,
        now_min: now.minute,
        step_min: 15,
    };
    let blocks = match hand_move(
        &Value::Array(blocks),
        &drop,
        &clock,
        &assignments,
        &mut fresh,
    )
    .map_err(|err| err.message)?
    {
        HandMove::Refused(words) => return Err(words),
        HandMove::Moved { blocks, .. } => blocks,
    };
    let Some((first, first_blocks, first_rev, second, second_blocks, second_rev)) = shown_parts
    else {
        let applied = homework::run_apply(
            &opened.conn,
            opened.user_id,
            "move_block",
            &operation_id,
            &digest,
            week_input(args.week_start.clone(), blocks, monday_rev.unwrap_or(0)),
            &homework::clock_of(app)?,
        )?;
        return saved_week(&applied);
    };
    let expected =
        week::expect_shown_revision(Some(&args.expected_revision), [first_rev, second_rev])?;
    if let Err(conflict) = week::check_shown_revision(&opened.conn, first_rev, second_rev, expected)
    {
        return Ok(conflict);
    }
    let weeks = week::split_shown_inputs(
        &args.week_start,
        &blocks,
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
        "move_block",
        &operation_id,
        &digest,
        input,
        &homework::clock_of(app)?,
    )?;
    if applied.get("error").is_some() {
        return Ok(applied);
    }
    let new_r1 = week::week_revision(&opened.conn, opened.user_id, &first)?;
    let new_r2 = week::week_revision(&opened.conn, opened.user_id, &second)?;
    let answer = json!({
        "ok": true,
        "result": {
            "week_start": args.week_start,
            "week_starts_on": week::weekday_name(&args.week_start)?,
            "revision": [new_r1, new_r2],
        },
        "revision": [new_r1, new_r2],
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

#[allow(clippy::too_many_lines)]
fn perform_delete(app: &crate::App, args: &DeleteArgs) -> Result<Value, String> {
    let opened = homework::open(app)?;
    let operation_id = write::operation_key(&args.operation_id)?;
    let digest = write::argument_digest(
        "delete_block",
        &args.operation_id,
        &json!({
            "block_id": args.block_id,
            "day": args.day,
            "every_week": args.every_week.unwrap_or(false),
            "expected_revision": args.expected_revision,
            "scope": args.scope,
            "week_start": args.week_start,
        }),
    );
    if let Some(saved) = homework::remembered(&opened.conn, opened.user_id, &operation_id, &digest)?
    {
        return saved_week(&saved);
    }
    let target = week::resolve_week(&args.week_start, app.first_weekday())?;
    let (blocks, monday_rev, shown_parts) = match target {
        WeekTarget::StoredMonday => {
            let (blocks, revision) = seen_week(&opened.conn, opened.user_id, &args.week_start)?;
            let expected = week::expect_monday_revision(Some(&args.expected_revision), revision)?;
            (blocks, Some((revision, expected)), None)
        }
        WeekTarget::Shown { first, second, .. } => {
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
                )),
            )
        }
    };
    let every_week = args.every_week.unwrap_or(false);
    let target_block = find(&blocks, &args.block_id);
    let setup = match target_block.as_ref() {
        Some(block) => is_setup_block(block).map_err(|err| err.message)?,
        None => false,
    };
    if every_week && !setup {
        return Err(
            "Only School and Setup's activities stand in every week, so every_week does not apply."
                .into(),
        );
    }
    // The app asks "this week or every week" only when the whole block goes
    // (`window.py` `_delete_block`); one day of it is this week only.
    let days = target_block
        .as_ref()
        .and_then(|block| block.get("days"))
        .and_then(Value::as_array)
        .map_or(0, Vec::len);
    if every_week && args.scope == "occurrence" && days > 1 {
        return Err(
            "every_week takes the whole block out; one day of it is this week only.".into(),
        );
    }
    let assignments = assignment_map(&opened.conn, opened.user_id)?;
    let now = app.now()?;
    let deletion = blocks::delete_block(
        &blocks,
        &assignments,
        &args.week_start,
        &args.block_id,
        &args.scope,
        args.day,
        &now.today,
        now.minute,
        every_week,
    )?;
    let Some((first, first_blocks, first_rev, second, second_blocks, second_rev)) = shown_parts
    else {
        let (revision, expected) = monday_rev.unwrap_or((0, 0));
        if deletion.label.is_none() {
            let answer = json!({
                "weeks": [{
                    "week_start": args.week_start,
                    "revision": revision,
                }],
                "assignments": [],
            });
            flexweek_store::remember_operation(
                &opened.conn,
                opened.user_id,
                &operation_id,
                &digest,
                &flexweek_engine::snapshot::canonical(&answer),
                // `changes.rs` keeps 100 operations. That constant is private.
                100,
            )
            .map_err(session::storage_sentence)?;
            opened.conn.execute_batch("COMMIT").map_err(|error| {
                session::storage_sentence(flexweek_store::StoreError::from(error))
            })?;
            return Ok(json!({
                "ok": true,
                "result": {
                    "week_start": args.week_start,
                    "week_starts_on": week::weekday_name(&args.week_start)?,
                    "revision": revision,
                },
                "revision": revision,
                "reaches_phone": REACHES_PHONE,
            }));
        }
        let mut input = week_input(args.week_start.clone(), deletion.blocks, expected);
        if every_week {
            input.repeats = Some(vec![json!({
                "id": family_id(&args.block_id),
                "scope": "from",
                "from_date": args.week_start,
                "stop": true,
            })]);
        }
        let applied = homework::run_apply(
            &opened.conn,
            opened.user_id,
            "delete_block",
            &operation_id,
            &digest,
            input,
            &homework::clock_of(app)?,
        )?;
        return saved_week(&applied);
    };
    let expected =
        week::expect_shown_revision(Some(&args.expected_revision), [first_rev, second_rev])?;
    if let Err(conflict) = week::check_shown_revision(&opened.conn, first_rev, second_rev, expected)
    {
        return Ok(conflict);
    }
    if deletion.label.is_none() {
        let answer = json!({
            "ok": true,
            "result": {
                "week_start": args.week_start,
                "week_starts_on": week::weekday_name(&args.week_start)?,
                "revision": [first_rev, second_rev],
            },
            "revision": [first_rev, second_rev],
            "reaches_phone": REACHES_PHONE,
        });
        let remembered = json!({"shown_reply": answer});
        flexweek_store::remember_operation(
            &opened.conn,
            opened.user_id,
            &operation_id,
            &digest,
            &flexweek_engine::snapshot::canonical(&remembered),
            100,
        )
        .map_err(session::storage_sentence)?;
        opened
            .conn
            .execute_batch("COMMIT")
            .map_err(|error| session::storage_sentence(flexweek_store::StoreError::from(error)))?;
        return Ok(answer);
    }
    let (second_baseline, repeats_input) = if every_week {
        let repeats = standing_blocks(&opened.conn, opened.user_id, &second)
            .map_err(session::storage_sentence)?;
        let family = family_id(&args.block_id);
        let repeat = find(&repeats, family);
        let stop_shown = json!({
            "id": family,
            "scope": "from",
            "from_date": args.week_start,
            "stop": true,
        });
        let stop_second = repeat_changes_from_shown_week(&[stop_shown], &args.week_start)
            .map_err(|err| err.message)?;
        let second_after_repeat =
            if let Some(intent) = edit_intent(family, &second, repeat.as_ref(), None) {
                apply_to_week(&second_blocks, &repeats, &[intent])?.0
            } else {
                second_blocks.clone()
            };
        (second_after_repeat, Some(stop_second))
    } else {
        (second_blocks.clone(), None)
    };
    let weeks = week::split_shown_inputs(
        &args.week_start,
        &deletion.blocks,
        &first,
        &first_blocks,
        first_rev,
        &second,
        &second_baseline,
        second_rev,
    )?;
    let input = ApplyInput {
        weeks,
        assignments: Vec::<AssignmentInput>::new(),
        operation_id: None,
        snapshot_label: None,
        repeats: repeats_input,
        argument_digest: None,
    };
    let applied = homework::run_apply(
        &opened.conn,
        opened.user_id,
        "delete_block",
        &operation_id,
        &digest,
        input,
        &homework::clock_of(app)?,
    )?;
    if applied.get("error").is_some() {
        return Ok(applied);
    }
    let new_r1 = week::week_revision(&opened.conn, opened.user_id, &first)?;
    let new_r2 = week::week_revision(&opened.conn, opened.user_id, &second)?;
    let answer = json!({
        "ok": true,
        "result": {
            "week_start": args.week_start,
            "week_starts_on": week::weekday_name(&args.week_start)?,
            "revision": [new_r1, new_r2],
        },
        "revision": [new_r1, new_r2],
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

#[tool_router(router = block_tools, vis = "pub(crate)")]
impl crate::App {
    #[tool(
        description = "Move a block to a day and time",
        annotations(read_only_hint = false, destructive_hint = false)
    )]
    async fn move_block(&self, Parameters(args): Parameters<MoveArgs>) -> Result<String, String> {
        write::finish("move_block", perform_move(self, &args))
    }

    #[tool(
        description = "Delete a block, or one day of it",
        annotations(destructive_hint = true, read_only_hint = false)
    )]
    async fn delete_block(
        &self,
        Parameters(args): Parameters<DeleteArgs>,
    ) -> Result<String, String> {
        write::finish("delete_block", perform_delete(self, &args))
    }
}
