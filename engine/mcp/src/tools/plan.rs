//! `plan_homework` is "Plan my homework": the steps of `controller.py` `solve` as the phone runs
//! them in Rust (`ffi/src/plan_week.rs` `run_plan`). Homework that already has a time keeps it;
//! earlier weeks' unfinished sessions move into this week; the planner places the rest around the
//! fixed blocks, never before now. What it placed is written in one change, after one restore
//! point. `day` keeps the plan to that day. The desktop's focus-chunk split after a plan is not
//! part of it, as on the phone.

use std::collections::{BTreeMap, HashSet};

use flexweek_engine::desk::planning;
use flexweek_engine::solver;
use flexweek_store::{
    ApplyInput, AssignmentInput, Connection, WeekInput, list_account_weeks, list_assignment_rows,
    read_week,
};
use rmcp::handler::server::wrapper::Parameters;
use rmcp::schemars::JsonSchema;
use rmcp::{tool, tool_router};
use serde::Deserialize;
use serde_json::{Map, Value, json};

use super::fixed::seen_week;
use super::homework;
use super::write::{self, REACHES_PHONE};
use crate::session;

const WEEK_OVER: &str = "This week is over, so nothing was planned. Plan this week or a later one.";
const NOT_THAT_DAY: &str = "It cannot go on that day: its due date or its days leave that day out.";

#[derive(Deserialize, JsonSchema)]
#[schemars(crate = "rmcp::schemars")]
struct PlanArgs {
    operation_id: String,
    week_start: String,
    /// Plan only this day, 0 (Monday) to 6 (Sunday). Without it the whole week is planned.
    #[serde(default)]
    day: Option<i64>,
}

fn engine(error: flexweek_engine::EngineError) -> String {
    error.message
}

/// `(assignments by id, the same as a sorted map, the raw rows)`, as `ffi` `assignment_map`.
type Assignments = (
    Map<String, Value>,
    BTreeMap<String, Value>,
    Vec<(String, String, i64)>,
);

fn assignments(conn: &Connection, user_id: i64) -> Result<Assignments, String> {
    let rows = list_assignment_rows(conn, user_id).map_err(session::storage_sentence)?;
    let mut keyed = Map::new();
    let mut tree = BTreeMap::new();
    for (id, body, _) in &rows {
        let value: Value =
            serde_json::from_str(body).map_err(|_| session::STORAGE_UNAVAILABLE.to_string())?;
        keyed.insert(id.clone(), value.clone());
        tree.insert(id.clone(), value);
    }
    Ok((keyed, tree, rows))
}

fn stored_weeks(conn: &Connection, user_id: i64) -> Result<Vec<(String, Vec<Value>, i64)>, String> {
    let mut weeks = Vec::new();
    for (start, text) in list_account_weeks(conn, user_id).map_err(session::storage_sentence)? {
        let revision = read_week(conn, user_id, &start)
            .map_err(session::storage_sentence)?
            .map_or(0, |(_, revision)| revision);
        weeks.push((start, homework::parse_blocks(&text)?, revision));
    }
    Ok(weeks)
}

/// The homework as the planner reads it, with this week's planned minutes (`ffi` `views_for_week`).
fn views(
    keyed: &Map<String, Value>,
    rows: &[(String, String, i64)],
    weeks: &[(String, Vec<Value>, i64)],
    week_start: &str,
) -> Result<Map<String, Value>, String> {
    let listed: Vec<(String, Vec<Value>)> = weeks
        .iter()
        .map(|(start, blocks, _)| (start.clone(), blocks.clone()))
        .collect();
    let planned = flexweek_engine::plan::planned_minutes_by_id(&listed, week_start);
    let mut out = Map::new();
    for (id, _, revision) in rows {
        let Some(body) = keyed.get(id) else {
            continue;
        };
        let minutes = planned.get(id).copied().unwrap_or(0);
        let mut view = flexweek_store::assignment_view(body, *revision, minutes).map_err(engine)?;
        if let Some(given) = body.get("unplanned_min") {
            view["unplanned_min"] = given.clone();
        }
        out.insert(id.clone(), view);
    }
    Ok(out)
}

fn open_week(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
    assignments: &Value,
) -> Result<(Vec<Value>, i64), String> {
    let (blocks, revision) = seen_week(conn, user_id, week_start)?;
    let rewritten =
        flexweek_store::rewrite_stored_blocks(&Value::Array(blocks), assignments, |block| {
            Ok::<Value, std::convert::Infallible>(block.clone())
        })
        .map_err(|relay| match relay {
            flexweek_store::Relay::Store(error) => session::storage_sentence(error),
            flexweek_store::Relay::Caller(never) => match never {},
        })?;
    Ok((rewritten, revision))
}

fn availability(
    conn: &Connection,
    user_id: i64,
) -> Result<flexweek_store::SolveAvailability, String> {
    let stored =
        flexweek_store::availability_json(conn, user_id).map_err(session::storage_sentence)?;
    flexweek_store::solve_availability(stored.as_deref(), |_kind, items| {
        Ok::<Value, String>(items.clone())
    })
    .map_err(|relay| match relay {
        flexweek_store::Relay::Store(error) => session::storage_sentence(error),
        flexweek_store::Relay::Caller(error) => error,
    })
}

fn plan_rules(conn: &Connection, user_id: i64) -> Result<solver::PlanRules, String> {
    let raw = flexweek_store::preference_row(conn, user_id)
        .map_err(session::storage_sentence)?
        .unwrap_or_else(|| "{}".to_string());
    let prefs: Value =
        serde_json::from_str(&raw).map_err(|_| session::STORAGE_UNAVAILABLE.to_string())?;
    Ok(solver::plan_rules_from_value(&prefs))
}

fn points(map: &BTreeMap<String, Option<(i64, i64)>>) -> Value {
    Value::Object(
        map.iter()
            .map(|(id, point)| {
                (
                    id.clone(),
                    point.map_or(Value::Null, |(day, minute)| json!([day, minute])),
                )
            })
            .collect(),
    )
}

fn slack(map: &BTreeMap<String, (i64, i64)>) -> Value {
    Value::Object(
        map.iter()
            .map(|(id, (day, minute))| (id.clone(), json!([day, minute])))
            .collect(),
    )
}

fn ids(values: &[Value]) -> Vec<String> {
    values
        .iter()
        .filter_map(Value::as_str)
        .map(str::to_string)
        .collect()
}

/// A split's second half is `<id>~2`; it reports as the homework it came from.
fn parent_of(id: &str) -> Option<&str> {
    id.strip_suffix("~2").filter(|parent| !parent.is_empty())
}

fn reported(id: &str, targets: &HashSet<String>) -> bool {
    targets.contains(id) || parent_of(id).is_some_and(|parent| targets.contains(parent))
}

/// Keeps the plan to `day`: each session the planner may place keeps only that day, and one that
/// cannot be on it is left out of this plan.
fn on_day(
    payload: Vec<Value>,
    targets: Vec<Value>,
    day: i64,
) -> (Vec<Value>, Vec<Value>, Vec<String>) {
    let wanted: HashSet<String> = ids(&targets).into_iter().collect();
    let mut kept = Vec::new();
    let mut left = Vec::new();
    for mut block in payload {
        let id = block["id"].as_str().unwrap_or("").to_string();
        if !wanted.contains(&id) {
            kept.push(block);
            continue;
        }
        let allowed = block["days"]
            .as_array()
            .is_some_and(|days| days.iter().any(|value| value.as_i64() == Some(day)));
        if !allowed {
            left.push(id);
            continue;
        }
        block["days"] = json!([day]);
        kept.push(block);
    }
    let targets = targets
        .into_iter()
        .filter(|id| {
            id.as_str()
                .is_none_or(|id| !left.iter().any(|gone| gone == id))
        })
        .collect();
    (kept, targets, left)
}

struct Planned {
    message: String,
    /// The week after the plan, every block in it.
    week: Option<Vec<Value>>,
    revision: i64,
    /// `{week_start, revision, after}` of earlier weeks whose sessions moved here.
    earlier: Vec<Value>,
    placed: Vec<Value>,
    not_placed: Vec<Value>,
}

fn row(block: &Value) -> Value {
    let start = block["start"].as_str().unwrap_or("");
    let end = flexweek_engine::time::hhmm_to_minutes(start)
        .map(|minute| minute + block["duration_min"].as_i64().unwrap_or(0))
        .ok();
    json!({
        "id": block["id"],
        "title": block["title"],
        "assignment_id": block.get("assignment_id").cloned().unwrap_or(Value::Null),
        "day": block["days"].as_array().and_then(|days| days.first()).cloned().unwrap_or(Value::Null),
        "start": block.get("start").cloned().unwrap_or(Value::Null),
        "end": end.map(|minute| json!(flexweek_engine::time::minutes_to_hhmm(minute))),
        "duration_min": block["duration_min"],
    })
}

fn with_parent_title(mut block: Value, settled: &[Value]) -> Value {
    let parent = block["id"].as_str().and_then(parent_of).map(str::to_string);
    if let Some(parent) = parent
        && let Some(title) = settled
            .iter()
            .find(|item| item["id"].as_str() == Some(parent.as_str()))
            .map(|item| item["title"].clone())
    {
        block["title"] = title;
    }
    block
}

#[allow(clippy::too_many_lines)]
fn run_plan(
    app: &crate::App,
    conn: &Connection,
    user_id: i64,
    args: &PlanArgs,
) -> Result<Planned, String> {
    let week_start = args.week_start.as_str();
    let hour = app.minute / 60;
    let start = planning::plan_start_at(week_start, &app.today, hour, app.minute % 60, 0, 0)
        .map_err(engine)?;
    let empty = |message: &str| Planned {
        message: message.to_string(),
        week: None,
        revision: 0,
        earlier: Vec::new(),
        placed: Vec::new(),
        not_placed: Vec::new(),
    };
    if start.is_some_and(|(day, _)| day > 6) {
        return Ok(empty(WEEK_OVER));
    }
    if let Some(day) = args.day
        && !(0..=6).contains(&day)
    {
        return Err("day must be 0 (Monday) to 6 (Sunday)".into());
    }
    let (keyed, tree, rows) = assignments(conn, user_id)?;
    let weeks = stored_weeks(conn, user_id)?;
    let assignments = Value::Object(views(&keyed, &rows, &weeks, week_start)?);
    let by_id = assignments.as_object().cloned().unwrap_or_default();
    let (blocks, revision) = open_week(conn, user_id, week_start, &assignments)?;
    let earlier: Vec<Value> = weeks
        .iter()
        .filter(|(start, _, _)| start.as_str() < week_start)
        .map(|(start, blocks, revision)| json!({"week_start": start, "blocks": blocks, "revision": revision}))
        .collect();
    let moved =
        planning::move_earlier_homework(&blocks, &earlier, &by_id, week_start).map_err(engine)?;
    let planning_blocks = moved["blocks"].as_array().cloned().unwrap_or(blocks);
    let moved_blocks = moved["moved"].as_array().cloned().unwrap_or_default();
    let earlier_updates = moved["weeks"].as_array().cloned().unwrap_or_default();
    let earlier_blocks: Vec<Value> = earlier
        .iter()
        .flat_map(|week| week["blocks"].as_array().cloned().unwrap_or_default())
        .filter(|block| block["start"].is_string() && block["completed"] != json!(true))
        .collect();
    let open_blocks =
        planning::open_rest_sessions(&planning_blocks, &by_id, week_start, &earlier_blocks)
            .map_err(engine)?;
    let not_before = start.map(|(day, minute)| json!([day, minute]));
    let (payload, targets) = planning::solve_request(
        &Value::Array(open_blocks.clone()),
        &assignments,
        week_start,
        false,
        None,
        not_before.as_ref(),
        false,
    )
    .map_err(engine)?;
    let (first_day, first_minute) = start.unwrap_or((0, 0));
    let committed: Vec<Value> = open_blocks
        .iter()
        .filter(|block| block["start"].is_string())
        .cloned()
        .chain(moved_blocks.iter().cloned())
        .collect();
    let found = availability(conn, user_id)?;
    let work = found.work.as_array().cloned().unwrap_or_default();
    let target_ids = ids(&targets);
    let (week_blocks, shares) = planning::fair_share(
        &open_blocks,
        &by_id,
        &Value::Array(committed),
        week_start,
        first_day,
        first_minute,
        &work,
        &target_ids,
    )
    .map_err(engine)?;
    let (payload, targets) = if shares.is_empty() {
        (payload, targets)
    } else {
        let kept: HashSet<&str> = week_blocks
            .iter()
            .filter_map(|block| block["id"].as_str())
            .collect();
        let only: Vec<Value> = target_ids
            .iter()
            .filter(|id| kept.contains(id.as_str()))
            .map(|id| json!(id))
            .collect();
        planning::solve_request(
            &Value::Array(week_blocks.clone()),
            &assignments,
            week_start,
            false,
            Some(&Value::Array(only)),
            not_before.as_ref(),
            false,
        )
        .map_err(engine)?
    };
    let (payload, targets, left) = match args.day {
        Some(day) => on_day(payload, targets, day),
        None => (payload, targets, Vec::new()),
    };
    let left_rows: Vec<Value> = left
        .iter()
        .filter_map(|id| {
            week_blocks
                .iter()
                .find(|block| block["id"].as_str() == Some(id.as_str()))
        })
        .map(|block| {
            let mut shown = row(block);
            shown["reason"] = json!("not_that_day");
            shown["why"] = json!(NOT_THAT_DAY);
            shown
        })
        .collect();
    if targets.is_empty() {
        return Ok(Planned {
            not_placed: left_rows,
            ..empty("")
        });
    }
    let (solve_blocks, deadlines, slack_points) =
        flexweek_engine::plan::prepare_solve(&payload, week_start, &tree).map_err(engine)?;
    let typed = solve_blocks
        .iter()
        .map(solver::block_from_value)
        .collect::<Result<Vec<_>, _>>()
        .map_err(engine)?;
    let windows: Vec<_> = work.iter().map(solver::work_window_from_value).collect();
    let overrides = solver::overrides_from(Some(&points(&deadlines)), Some(&slack(&slack_points)));
    let began = std::time::Instant::now();
    let elapsed = move || began.elapsed().as_secs_f64() * 1000.0;
    let trace = solver::solve_with_rules(
        &typed,
        Some(&found.occupancy),
        Some(&windows),
        Some(&overrides),
        start,
        solver::SOLVE_BUDGET_MS,
        &elapsed,
        plan_rules(conn, user_id)?,
    )
    .map_err(engine)?;
    let trace = solver::trace_to_value(&trace);
    let applied = planning::apply_plan(
        &Value::Array(week_blocks),
        &trace,
        Some(&Value::Array(targets.clone())),
        Some(&assignments),
        Some(week_start),
    )
    .map_err(engine)?;
    let (settled, _) = planning::settle_placements(
        &Value::Array(applied),
        &assignments,
        week_start,
        &json!([]),
        false,
    )
    .map_err(engine)?;
    let settled = settled.as_array().cloned().unwrap_or_default();
    let target_set: HashSet<String> = ids(&targets).into_iter().collect();
    let mut placed = Vec::new();
    let mut not_placed = Vec::new();
    for block in &settled {
        let id = block["id"].as_str().unwrap_or("");
        if !reported(id, &target_set) {
            continue;
        }
        let shown = row(&with_parent_title(block.clone(), &settled));
        if block["start"].is_string() {
            placed.push(shown);
            continue;
        }
        let mut shown = shown;
        let why = trace["explanations"]
            .as_array()
            .into_iter()
            .flatten()
            .find(|item| item["block_id"].as_str() == Some(id))
            .and_then(|item| item["reason"].as_str())
            .and_then(|reason| {
                flexweek_engine::plan::sentence(reason)
                    .ok()
                    .map(|why| (reason.to_string(), why))
            });
        if let Some((reason, why)) = why {
            shown["reason"] = json!(reason);
            shown["why"] = json!(why);
        }
        not_placed.push(shown);
    }
    not_placed.extend(left_rows);
    Ok(Planned {
        message: String::new(),
        week: Some(settled),
        revision,
        earlier: earlier_updates,
        placed,
        not_placed,
    })
}

fn reply(
    planned: &Planned,
    week_start: &str,
    revision: Value,
    operation_id: Option<&str>,
) -> Value {
    json!({
        "ok": true,
        "result": {
            "week_start": week_start,
            "revision": revision,
            "placed": planned.placed,
            "not_placed": planned.not_placed,
            "message": planned.message,
        },
        "revision": revision,
        "restore_point": operation_id.map(write::point_id),
        "reaches_phone": REACHES_PHONE,
    })
}

fn perform(app: &crate::App, args: &PlanArgs) -> Result<Value, String> {
    let opened = homework::open(app)?;
    let operation_id = write::operation_key(&args.operation_id)?;
    let digest = write::argument_digest(
        "plan_homework",
        &args.operation_id,
        &json!({"day": args.day, "week_start": args.week_start}),
    );
    if let Some(remembered) =
        homework::remembered(&opened.conn, opened.user_id, &operation_id, &digest)?
    {
        if remembered.get("plan").is_some() {
            return Ok(remembered["plan"].clone());
        }
        let revision = remembered["weeks"][0]["revision"].clone();
        return Ok(
            json!({"ok": true, "result": {"week_start": args.week_start, "revision": revision},
            "revision": revision, "restore_point": write::point_id(&operation_id),
            "reaches_phone": REACHES_PHONE}),
        );
    }
    let planned = run_plan(app, &opened.conn, opened.user_id, args)?;
    let Some(week) = planned.week.clone().filter(|_| !planned.placed.is_empty()) else {
        // Nothing placed is nothing written, and no restore point.
        return Ok(reply(
            &planned,
            &args.week_start,
            json!(planned.revision),
            None,
        ));
    };
    let mut weeks = vec![WeekInput {
        week_start: args.week_start.clone(),
        blocks: week,
        revision: planned.revision,
    }];
    for update in &planned.earlier {
        let Some(start) = update["week_start"].as_str() else {
            continue;
        };
        weeks.push(WeekInput {
            week_start: start.to_string(),
            blocks: update["after"].as_array().cloned().unwrap_or_default(),
            revision: update["revision"].as_i64().unwrap_or(0),
        });
    }
    let input = ApplyInput {
        weeks,
        assignments: Vec::<AssignmentInput>::new(),
        operation_id: None,
        snapshot_label: None,
        standing: None,
        argument_digest: None,
    };
    let applied = homework::run_apply(
        &opened.conn,
        opened.user_id,
        "plan_homework",
        &operation_id,
        &digest,
        input,
        &homework::clock_of(app),
    )?;
    if applied.get("error").is_some() {
        return Ok(applied);
    }
    let revision = applied["weeks"][0]["revision"].clone();
    let answer = reply(&planned, &args.week_start, revision, Some(&operation_id));
    remember_plan(
        &opened.conn,
        opened.user_id,
        &operation_id,
        &applied,
        &answer,
    )?;
    Ok(answer)
}

/// The save remembered the batch under this operation; the plan's own answer is added to it, so a
/// retry gets what the first call said.
fn remember_plan(
    conn: &Connection,
    user_id: i64,
    operation_id: &str,
    applied: &Value,
    answer: &Value,
) -> Result<(), String> {
    let mut saved = applied.clone();
    saved["plan"] = answer.clone();
    conn.execute(
        "UPDATE operations SET response = ?1 WHERE user_id = ?2 AND operation_id = ?3",
        (
            flexweek_engine::snapshot::canonical(&saved),
            user_id,
            operation_id,
        ),
    )
    .map_err(|error| session::storage_sentence(flexweek_store::StoreError::from(error)))?;
    Ok(())
}

#[tool_router(router = plan_tools, vis = "pub(crate)")]
impl crate::App {
    #[tool(
        description = "Plan my homework: FlexWeek's own planner gives homework with no time a \
            time this week (or on one day), around school and other fixed time, never before now. \
            Returns what it placed and what it could not place with the reason, and saves it as one \
            change",
        annotations(read_only_hint = false, destructive_hint = false)
    )]
    async fn plan_homework(
        &self,
        Parameters(args): Parameters<PlanArgs>,
    ) -> Result<String, String> {
        write::finish("plan_homework", perform(self, &args))
    }
}
