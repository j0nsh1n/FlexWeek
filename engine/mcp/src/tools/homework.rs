//! Homework and block writes. Sessions stay in step through `desk::homework`,
//! and the batch is `changes::apply`. `set_block_done` follows `agenda.rs`.

use flexweek_engine::desk::blocks::SETUP_BLOCK;
use flexweek_engine::desk::grid::is_setup_block;
use flexweek_engine::desk::homework::edit_homework;
use flexweek_store::{
    ApplyClock, ApplyInput, AssignmentInput, Connection, Recall, WeekInput, apply,
    list_account_weeks, list_assignment_rows, read_week, recall_operation,
};
use rmcp::handler::server::wrapper::Parameters;
use rmcp::schemars::JsonSchema;
use rmcp::{tool, tool_router};
use serde::Deserialize;
use serde_json::{Map, Value, json};

use super::write::{self, OPERATION_CONFLICT, REACHES_PHONE};
use crate::session;

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct AddArgs {
    operation_id: String,
    title: String,
    due: String,
    estimate_min: i64,
    #[serde(default)]
    priority: Option<i64>,
    #[serde(default)]
    energy: Option<String>,
    #[serde(default)]
    course: Option<String>,
    #[serde(default)]
    category: Option<String>,
    #[serde(default)]
    notes: Option<String>,
    #[serde(default)]
    spread: Option<bool>,
}

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct EditArgs {
    operation_id: String,
    id: String,
    expected_revision: i64,
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    due: Option<String>,
    #[serde(default)]
    estimate_min: Option<i64>,
    #[serde(default)]
    priority: Option<i64>,
    #[serde(default)]
    energy: Option<String>,
    #[serde(default)]
    course: Option<String>,
    #[serde(default)]
    category: Option<String>,
    #[serde(default)]
    notes: Option<String>,
    #[serde(default)]
    spread: Option<bool>,
}

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct DeleteArgs {
    operation_id: String,
    id: String,
    expected_revision: i64,
}

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct HomeworkDoneArgs {
    operation_id: String,
    id: String,
    done: bool,
}

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct BlockDoneArgs {
    operation_id: String,
    week_start: String,
    block_id: String,
    day: i64,
    done: bool,
}

struct Opened {
    user_id: i64,
    conn: Connection,
}

fn open(app: &crate::App) -> Result<Opened, String> {
    let account = session::for_call(
        app.started_as.as_ref(),
        &app.session_file,
        &app.database,
        app.now_unix,
    )?;
    let conn = flexweek_store::open_connection(&app.database).map_err(session::storage_sentence)?;
    Ok(Opened {
        user_id: account.user_id,
        conn,
    })
}

fn minute_of(unix: i64) -> i64 {
    unix.rem_euclid(86_400) / 60
}

fn stamp_of(today: &str, minute: i64) -> String {
    format!("{today}T{:02}:{:02}", minute / 60, minute % 60)
}

fn clock_of(app: &crate::App) -> ApplyClock {
    ApplyClock {
        now: stamp_of(&app.today, minute_of(app.now_unix)),
        restore_token: String::new(),
    }
}

fn derived_id(operation_id: &str, kind: &str) -> String {
    flexweek_store::digest(&format!("{kind}:{operation_id}"))
}

fn remembered(
    conn: &Connection,
    user_id: i64,
    operation_id: &str,
    digest: &str,
) -> Result<Option<Value>, String> {
    match recall_operation(conn, user_id, operation_id, digest)
        .map_err(session::storage_sentence)?
    {
        Recall::Hit(text) => {
            let value = serde_json::from_str(&text)
                .map_err(|_| session::STORAGE_UNAVAILABLE.to_string())?;
            Ok(Some(write::stable(value)?))
        }
        Recall::Conflict => Err(OPERATION_CONFLICT.into()),
        Recall::Missing => Ok(None),
    }
}

fn run_apply(
    conn: &Connection,
    user_id: i64,
    operation_id: &str,
    digest: &str,
    mut input: ApplyInput,
    clock: &ApplyClock,
) -> Result<Value, String> {
    input.operation_id = Some(operation_id.to_string());
    input.argument_digest = Some(digest.to_string());
    write::from_apply(apply(conn, user_id, &input, clock))
}

fn parse_blocks(text: &str) -> Result<Vec<Value>, String> {
    match serde_json::from_str::<Value>(text) {
        Ok(Value::Array(items)) => Ok(items),
        _ => Err("stored week is not a list".into()),
    }
}

fn load_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
) -> Result<(Vec<Value>, i64), String> {
    match read_week(conn, user_id, week_start).map_err(session::storage_sentence)? {
        None => Ok((Vec::new(), 0)),
        Some((text, revision)) => Ok((parse_blocks(&text)?, revision)),
    }
}

fn load_assignments(conn: &Connection, user_id: i64) -> Result<Map<String, Value>, String> {
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

fn weeks_touching(
    conn: &Connection,
    user_id: i64,
    assignment_id: &str,
    today: &str,
) -> Result<Vec<(String, Vec<Value>, i64)>, String> {
    let current = flexweek_engine::time::monday_of(today).map_err(|err| err.message)?;
    let mut starts = vec![current.clone()];
    let stored = list_account_weeks(conn, user_id).map_err(session::storage_sentence)?;
    for (start, raw) in stored {
        if start == current {
            continue;
        }
        let blocks = parse_blocks(&raw)?;
        let linked = blocks
            .iter()
            .any(|block| block.get("assignment_id").and_then(Value::as_str) == Some(assignment_id));
        if linked {
            starts.push(start);
        }
    }
    let mut weeks = Vec::new();
    for start in starts {
        let (blocks, revision) = load_week(conn, user_id, &start)?;
        weeks.push((start, blocks, revision));
    }
    Ok(weeks)
}

fn put_str(map: &mut Map<String, Value>, key: &str, value: &Option<String>) {
    if let Some(text) = value {
        map.insert(key.to_string(), json!(text));
    }
}

fn add_payload(args: &AddArgs, assignment_id: &str) -> Value {
    let mut map = Map::new();
    map.insert("id".into(), json!(assignment_id));
    map.insert("title".into(), json!(args.title));
    map.insert("due".into(), json!(args.due));
    map.insert("estimate_min".into(), json!(args.estimate_min));
    if let Some(priority) = args.priority {
        map.insert("priority".into(), json!(priority));
    }
    put_str(&mut map, "energy", &args.energy);
    put_str(&mut map, "course", &args.course);
    put_str(&mut map, "category", &args.category);
    put_str(&mut map, "notes", &args.notes);
    Value::Object(map)
}

fn edit_payload(existing: &Value, args: &EditArgs) -> Result<Value, String> {
    let mut map = existing
        .as_object()
        .cloned()
        .ok_or_else(|| session::STORAGE_UNAVAILABLE.to_string())?;
    map.insert("id".into(), json!(args.id));
    put_str(&mut map, "title", &args.title);
    put_str(&mut map, "due", &args.due);
    if let Some(estimate) = args.estimate_min {
        map.insert("estimate_min".into(), json!(estimate));
    }
    if let Some(priority) = args.priority {
        map.insert("priority".into(), json!(priority));
    }
    put_str(&mut map, "energy", &args.energy);
    put_str(&mut map, "course", &args.course);
    put_str(&mut map, "category", &args.category);
    put_str(&mut map, "notes", &args.notes);
    Ok(Value::Object(map))
}

fn done_payload(existing: &Value, done: bool, stamp: &str) -> Result<Value, String> {
    let mut map = existing
        .as_object()
        .cloned()
        .ok_or_else(|| session::STORAGE_UNAVAILABLE.to_string())?;
    let completed_at = if done {
        match map.get("completed_at").and_then(Value::as_str) {
            Some(kept) if !kept.is_empty() => json!(kept),
            _ => json!(stamp),
        }
    } else {
        Value::Null
    };
    map.insert("completed".into(), json!(done));
    map.insert("completed_at".into(), completed_at);
    Ok(Value::Object(map))
}

struct Edited {
    weeks: Vec<(String, Vec<Value>, i64)>,
    assignment: Value,
}

fn edit_weeks(
    weeks: Vec<(String, Vec<Value>, i64)>,
    assignments: &Map<String, Value>,
    payload: &Value,
    spread: bool,
    session_id: &str,
    today: &str,
    minute: i64,
) -> Result<Edited, String> {
    let mut edited = Vec::new();
    let mut assignment = None;
    for (start, blocks, revision) in weeks {
        let changed = edit_homework(
            &blocks,
            assignments,
            &start,
            payload,
            None,
            spread,
            session_id,
            today,
            minute,
        )?;
        assignment = Some(changed.assignment);
        edited.push((start, changed.blocks, revision));
    }
    let assignment = assignment.ok_or_else(|| "homework was not found".to_string())?;
    Ok(Edited {
        weeks: edited,
        assignment,
    })
}

fn homework_input(edited: Edited, revision: i64) -> Result<ApplyInput, String> {
    let id = edited
        .assignment
        .get("id")
        .and_then(Value::as_str)
        .ok_or_else(|| session::STORAGE_UNAVAILABLE.to_string())?
        .to_string();
    Ok(ApplyInput {
        weeks: edited
            .weeks
            .into_iter()
            .map(|(week_start, blocks, revision)| WeekInput {
                week_start,
                blocks,
                revision,
            })
            .collect(),
        assignments: vec![AssignmentInput {
            id,
            assignment: Some(edited.assignment),
            revision,
        }],
        operation_id: None,
        snapshot_label: None,
        standing: None,
        argument_digest: None,
    })
}

fn saved_homework(applied: &Value) -> Result<Value, String> {
    if applied.get("error").is_some() {
        return Ok(applied.clone());
    }
    let entry = applied
        .get("assignments")
        .and_then(Value::as_array)
        .and_then(|items| items.first())
        .ok_or_else(|| session::STORAGE_UNAVAILABLE.to_string())?;
    let id = entry
        .get("id")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let revision = entry.get("revision").cloned().unwrap_or(Value::Null);
    let mut assignment = entry.get("assignment").cloned().unwrap_or(Value::Null);
    if let Some(object) = assignment.as_object_mut() {
        object.insert("revision".into(), revision.clone());
    }
    let mut session_ids = Vec::new();
    if let Some(weeks) = applied.get("weeks").and_then(Value::as_array) {
        for week in weeks {
            let Some(blocks) = week.get("blocks").and_then(Value::as_array) else {
                continue;
            };
            for block in blocks {
                if block.get("assignment_id").and_then(Value::as_str) != Some(id.as_str()) {
                    continue;
                }
                if let Some(block_id) = block.get("id").and_then(Value::as_str) {
                    session_ids.push(json!(block_id));
                }
            }
        }
    }
    Ok(json!({
        "ok": true,
        "result": {
            "assignment": assignment,
            "session_ids": session_ids,
        },
        "revision": revision,
        "reaches_phone": REACHES_PHONE,
    }))
}

fn saved_delete(applied: &Value) -> Result<Value, String> {
    if applied.get("error").is_some() {
        return Ok(applied.clone());
    }
    let entry = applied
        .get("assignments")
        .and_then(Value::as_array)
        .and_then(|items| items.first())
        .ok_or_else(|| session::STORAGE_UNAVAILABLE.to_string())?;
    Ok(json!({
        "ok": true,
        "result": {
            "removed_sessions": entry.get("removed_sessions").cloned().unwrap_or(Value::Null),
            "changed_weeks": entry.get("changed_weeks").cloned().unwrap_or(Value::Null),
        },
        "reaches_phone": REACHES_PHONE,
    }))
}

fn saved_block(applied: &Value) -> Result<Value, String> {
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

fn column_revision(existing: &Value) -> i64 {
    existing
        .get("revision")
        .and_then(Value::as_i64)
        .unwrap_or(0)
}

fn mark_block(blocks: &mut [Value], block_id: &str, day: i64, done: bool) -> Result<(), String> {
    let Some(block) = blocks
        .iter_mut()
        .find(|block| block.get("id").and_then(Value::as_str) == Some(block_id))
    else {
        return Err("block was not found".into());
    };
    if is_setup_block(block).map_err(|err| err.message)? {
        return Err(SETUP_BLOCK.into());
    }
    let object = block
        .as_object_mut()
        .ok_or_else(|| "stored block is not an object".to_string())?;
    let flexible = object.get("kind").and_then(Value::as_str) == Some("flexible");
    let has_start = object
        .get("start")
        .and_then(Value::as_str)
        .is_some_and(|start| !start.is_empty());
    let day_ok = object
        .get("days")
        .and_then(Value::as_array)
        .is_some_and(|days| days.iter().any(|value| value.as_i64() == Some(day)));
    if done && flexible && has_start && !day_ok {
        return Err("day is not one of the block's days".into());
    }
    object.insert("completed".into(), json!(done));
    if done && flexible && has_start && day_ok {
        object.insert("completed_day".into(), json!(day));
    } else {
        object.shift_remove("completed_day");
    }
    Ok(())
}

fn add_arguments(args: &AddArgs) -> Value {
    json!({
        "category": args.category,
        "course": args.course,
        "due": args.due,
        "energy": args.energy,
        "estimate_min": args.estimate_min,
        "notes": args.notes,
        "priority": args.priority,
        "spread": args.spread.unwrap_or(false),
        "title": args.title,
    })
}

fn edit_arguments(args: &EditArgs) -> Value {
    json!({
        "category": args.category,
        "course": args.course,
        "due": args.due,
        "energy": args.energy,
        "estimate_min": args.estimate_min,
        "expected_revision": args.expected_revision,
        "id": args.id,
        "notes": args.notes,
        "priority": args.priority,
        "spread": args.spread.unwrap_or(false),
        "title": args.title,
    })
}

#[tool_router(router = homework_tools, vis = "pub(crate)")]
impl crate::App {
    #[tool(
        description = "Add homework and one open session on this week",
        annotations(read_only_hint = false, destructive_hint = false)
    )]
    async fn add_homework(&self, Parameters(args): Parameters<AddArgs>) -> Result<String, String> {
        let result = (|| {
            let opened = open(self)?;
            let operation_id = write::operation_key(&args.operation_id)?;
            let digest =
                write::argument_digest("add_homework", &args.operation_id, &add_arguments(&args));
            if let Some(saved) = remembered(&opened.conn, opened.user_id, &operation_id, &digest)? {
                return saved_homework(&saved);
            }
            let assignment_id = derived_id(&args.operation_id, "hw");
            let session_id = derived_id(&args.operation_id, "session");
            let payload = add_payload(&args, &assignment_id);
            let assignments = load_assignments(&opened.conn, opened.user_id)?;
            let weeks = weeks_touching(&opened.conn, opened.user_id, &assignment_id, &self.today)?;
            let edited = edit_weeks(
                weeks,
                &assignments,
                &payload,
                args.spread.unwrap_or(false),
                &session_id,
                &self.today,
                minute_of(self.now_unix),
            )?;
            let input = homework_input(edited, 0)?;
            let applied = run_apply(
                &opened.conn,
                opened.user_id,
                &operation_id,
                &digest,
                input,
                &clock_of(self),
            )?;
            saved_homework(&applied)
        })();
        write::finish("add_homework", result)
    }

    #[tool(
        description = "Change homework and keep its sessions in step",
        annotations(read_only_hint = false, destructive_hint = false)
    )]
    async fn edit_homework(
        &self,
        Parameters(args): Parameters<EditArgs>,
    ) -> Result<String, String> {
        let result = (|| {
            let opened = open(self)?;
            let operation_id = write::operation_key(&args.operation_id)?;
            let digest =
                write::argument_digest("edit_homework", &args.operation_id, &edit_arguments(&args));
            if let Some(saved) = remembered(&opened.conn, opened.user_id, &operation_id, &digest)? {
                return saved_homework(&saved);
            }
            let assignments = load_assignments(&opened.conn, opened.user_id)?;
            let Some(existing) = assignments.get(&args.id) else {
                return Err("homework was not found".into());
            };
            let payload = edit_payload(existing, &args)?;
            let session_id = derived_id(&args.operation_id, "session");
            let weeks = weeks_touching(&opened.conn, opened.user_id, &args.id, &self.today)?;
            let edited = edit_weeks(
                weeks,
                &assignments,
                &payload,
                args.spread.unwrap_or(false),
                &session_id,
                &self.today,
                minute_of(self.now_unix),
            )?;
            let input = homework_input(edited, args.expected_revision)?;
            let applied = run_apply(
                &opened.conn,
                opened.user_id,
                &operation_id,
                &digest,
                input,
                &clock_of(self),
            )?;
            saved_homework(&applied)
        })();
        write::finish("edit_homework", result)
    }

    #[tool(
        description = "Delete homework and its sessions",
        annotations(destructive_hint = true, read_only_hint = false)
    )]
    async fn delete_homework(
        &self,
        Parameters(args): Parameters<DeleteArgs>,
    ) -> Result<String, String> {
        let result = (|| {
            let opened = open(self)?;
            let operation_id = write::operation_key(&args.operation_id)?;
            let digest = write::argument_digest(
                "delete_homework",
                &args.operation_id,
                &json!({
                    "expected_revision": args.expected_revision,
                    "id": args.id,
                }),
            );
            if let Some(saved) = remembered(&opened.conn, opened.user_id, &operation_id, &digest)? {
                return saved_delete(&saved);
            }
            let input = ApplyInput {
                weeks: Vec::new(),
                assignments: vec![AssignmentInput {
                    id: args.id,
                    assignment: None,
                    revision: args.expected_revision,
                }],
                operation_id: None,
                snapshot_label: None,
                standing: None,
                argument_digest: None,
            };
            let applied = run_apply(
                &opened.conn,
                opened.user_id,
                &operation_id,
                &digest,
                input,
                &clock_of(self),
            )?;
            saved_delete(&applied)
        })();
        write::finish("delete_homework", result)
    }

    #[tool(
        description = "Mark homework done or not done, and its sessions with it",
        annotations(read_only_hint = false, destructive_hint = false)
    )]
    async fn set_homework_done(
        &self,
        Parameters(args): Parameters<HomeworkDoneArgs>,
    ) -> Result<String, String> {
        let result = (|| {
            let opened = open(self)?;
            let operation_id = write::operation_key(&args.operation_id)?;
            let digest = write::argument_digest(
                "set_homework_done",
                &args.operation_id,
                &json!({"done": args.done, "id": args.id}),
            );
            if let Some(saved) = remembered(&opened.conn, opened.user_id, &operation_id, &digest)? {
                return saved_homework(&saved);
            }
            let assignments = load_assignments(&opened.conn, opened.user_id)?;
            let Some(existing) = assignments.get(&args.id) else {
                return Err("homework was not found".into());
            };
            let revision = column_revision(existing);
            let payload = done_payload(
                existing,
                args.done,
                &stamp_of(&self.today, minute_of(self.now_unix)),
            )?;
            let session_id = derived_id(&args.operation_id, "session");
            let weeks = weeks_touching(&opened.conn, opened.user_id, &args.id, &self.today)?;
            let edited = edit_weeks(
                weeks,
                &assignments,
                &payload,
                false,
                &session_id,
                &self.today,
                minute_of(self.now_unix),
            )?;
            let input = homework_input(edited, revision)?;
            let applied = run_apply(
                &opened.conn,
                opened.user_id,
                &operation_id,
                &digest,
                input,
                &clock_of(self),
            )?;
            saved_homework(&applied)
        })();
        write::finish("set_homework_done", result)
    }

    #[tool(
        description = "Mark one block done or not done",
        annotations(read_only_hint = false, destructive_hint = false)
    )]
    async fn set_block_done(
        &self,
        Parameters(args): Parameters<BlockDoneArgs>,
    ) -> Result<String, String> {
        let result = (|| {
            let opened = open(self)?;
            let operation_id = write::operation_key(&args.operation_id)?;
            let digest = write::argument_digest(
                "set_block_done",
                &args.operation_id,
                &json!({
                    "block_id": args.block_id,
                    "day": args.day,
                    "done": args.done,
                    "week_start": args.week_start,
                }),
            );
            if let Some(saved) = remembered(&opened.conn, opened.user_id, &operation_id, &digest)? {
                return saved_block(&saved);
            }
            let Some((text, revision)) = read_week(&opened.conn, opened.user_id, &args.week_start)
                .map_err(session::storage_sentence)?
            else {
                return Err("week was not found".into());
            };
            let mut blocks = parse_blocks(&text)?;
            mark_block(&mut blocks, &args.block_id, args.day, args.done)?;
            let input = ApplyInput {
                weeks: vec![WeekInput {
                    week_start: args.week_start,
                    blocks,
                    revision,
                }],
                assignments: Vec::new(),
                operation_id: None,
                snapshot_label: None,
                standing: None,
                argument_digest: None,
            };
            let applied = run_apply(
                &opened.conn,
                opened.user_id,
                &operation_id,
                &digest,
                input,
                &clock_of(self),
            )?;
            saved_block(&applied)
        })();
        write::finish("set_block_done", result)
    }
}
