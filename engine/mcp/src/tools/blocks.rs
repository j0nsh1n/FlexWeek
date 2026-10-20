//! `move_block` calls `hand_move` and returns its words. `delete_block` calls
//! `desk::blocks::delete_block`. School and activities are refused before either edit.

use flexweek_engine::desk::blocks::{self, SETUP_BLOCK};
use flexweek_engine::desk::grid::is_setup_block;
use flexweek_engine::desk::hand_move::{HandDrop, HandMove, WeekClock, hand_move};
use flexweek_engine::time::hhmm_to_minutes;
use flexweek_store::{
    ApplyInput, AssignmentInput, Connection, WeekInput, list_assignment_rows, read_week,
};
use rmcp::handler::server::wrapper::Parameters;
use rmcp::schemars::JsonSchema;
use rmcp::{tool, tool_router};
use serde::Deserialize;
use serde_json::{Map, Value, json};

use super::homework;
use super::write::{self, REACHES_PHONE};
use crate::session;

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct MoveArgs {
    operation_id: String,
    week_start: String,
    expected_revision: i64,
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
    expected_revision: i64,
    block_id: String,
    scope: String,
    #[serde(default)]
    day: Option<i64>,
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
    let week = applied
        .get("weeks")
        .and_then(Value::as_array)
        .and_then(|items| items.first())
        .ok_or_else(|| session::STORAGE_UNAVAILABLE.to_string())?;
    let revision = week.get("revision").cloned().unwrap_or(Value::Null);
    Ok(json!({
        "ok": true,
        "result": {
            "week_start": week.get("week_start").cloned().unwrap_or(Value::Null),
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
        standing: None,
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
    let Some((text, _)) = read_week(&opened.conn, opened.user_id, &args.week_start)
        .map_err(session::storage_sentence)?
    else {
        return Err("week was not found".into());
    };
    let blocks = homework::parse_blocks(&text)?;
    let found = blocks
        .iter()
        .find(|block| block.get("id").and_then(Value::as_str) == Some(args.block_id.as_str()))
        .cloned();
    if let Some(block) = &found
        && is_setup_block(block).map_err(|err| err.message)?
    {
        return Err(SETUP_BLOCK.into());
    }
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
    let clock = WeekClock {
        week_start: &args.week_start,
        now_iso: &app.today,
        now_min: homework::minute_of(app.now_unix),
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
    let applied = homework::run_apply(
        &opened.conn,
        opened.user_id,
        &operation_id,
        &digest,
        week_input(args.week_start.clone(), blocks, args.expected_revision),
        &homework::clock_of(app),
    )?;
    saved_week(&applied)
}

fn perform_delete(app: &crate::App, args: &DeleteArgs) -> Result<Value, String> {
    let opened = homework::open(app)?;
    let operation_id = write::operation_key(&args.operation_id)?;
    let digest = write::argument_digest(
        "delete_block",
        &args.operation_id,
        &json!({
            "block_id": args.block_id,
            "day": args.day,
            "expected_revision": args.expected_revision,
            "scope": args.scope,
            "week_start": args.week_start,
        }),
    );
    if let Some(saved) = homework::remembered(&opened.conn, opened.user_id, &operation_id, &digest)?
    {
        return saved_week(&saved);
    }
    let Some((text, revision)) = read_week(&opened.conn, opened.user_id, &args.week_start)
        .map_err(session::storage_sentence)?
    else {
        return Err("week was not found".into());
    };
    let blocks = homework::parse_blocks(&text)?;
    let assignments = assignment_map(&opened.conn, opened.user_id)?;
    let deletion = blocks::delete_block(
        &blocks,
        &assignments,
        &args.week_start,
        &args.block_id,
        &args.scope,
        args.day,
        &app.today,
        homework::minute_of(app.now_unix),
    )?;
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
        opened
            .conn
            .execute_batch("COMMIT")
            .map_err(|error| session::storage_sentence(flexweek_store::StoreError::from(error)))?;
        return Ok(json!({
            "ok": true,
            "result": {"week_start": args.week_start, "revision": revision},
            "revision": revision,
            "reaches_phone": REACHES_PHONE,
        }));
    }
    let applied = homework::run_apply(
        &opened.conn,
        opened.user_id,
        &operation_id,
        &digest,
        week_input(
            args.week_start.clone(),
            deletion.blocks,
            args.expected_revision,
        ),
        &homework::clock_of(app),
    )?;
    saved_week(&applied)
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
