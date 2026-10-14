use std::collections::BTreeMap;
use std::convert::Infallible;

use rusqlite::Connection;
use serde_json::{Map, Value, json};

use crate::core::{FfiError, engine_failure, failure};

pub(crate) fn decode_blocks(raw: &str) -> Result<Value, FfiError> {
    serde_json::from_str(raw).map_err(failure)
}

pub(crate) fn rewritten(blocks: &Value, assignments: &Value) -> Result<Vec<Value>, FfiError> {
    flexweek_store::rewrite_stored_blocks(blocks, assignments, |block| {
        Ok::<Value, Infallible>(block.clone())
    })
    .map_err(|relay| match relay {
        flexweek_store::Relay::Store(error) => failure(error),
        flexweek_store::Relay::Caller(error) => match error {},
    })
}

type AssignmentTables = (
    Map<String, Value>,
    BTreeMap<String, Value>,
    Vec<(String, String, i64)>,
);

pub(crate) fn assignment_map(db: &Connection, user_id: i64) -> Result<AssignmentTables, FfiError> {
    let rows = flexweek_store::list_assignment_rows(db, user_id).map_err(failure)?;
    let mut keyed = Map::new();
    let mut tree = BTreeMap::new();
    for (id, body, _) in &rows {
        let value: Value = serde_json::from_str(body).map_err(failure)?;
        keyed.insert(id.clone(), value.clone());
        tree.insert(id.clone(), value);
    }
    Ok((keyed, tree, rows))
}

pub(crate) fn stored_weeks(
    db: &Connection,
    user_id: i64,
) -> Result<Vec<(String, Vec<Value>, i64)>, FfiError> {
    let mut weeks = Vec::new();
    for (start, stored) in flexweek_store::list_account_weeks(db, user_id).map_err(failure)? {
        let revision = flexweek_store::read_week(db, user_id, &start)
            .map_err(failure)?
            .map(|(_, revision)| revision)
            .unwrap_or(0);
        let blocks: Vec<Value> = serde_json::from_str(&stored).map_err(failure)?;
        weeks.push((start, blocks, revision));
    }
    Ok(weeks)
}

pub(crate) fn load_open_week(
    db: &Connection,
    user_id: i64,
    week_start: &str,
    assignments: &Value,
) -> Result<(Vec<Value>, i64), FfiError> {
    let raw = flexweek_store::week_blocks(db, user_id, week_start)
        .map_err(failure)?
        .unwrap_or_else(|| "[]".into());
    let merged =
        flexweek_store::week_with_standing(db, user_id, week_start, &raw).map_err(failure)?;
    let stored = decode_blocks(&merged)?;
    let blocks = rewritten(&stored, assignments)?;
    let revision = flexweek_store::read_week(db, user_id, week_start)
        .map_err(failure)?
        .map(|(_, revision)| revision)
        .unwrap_or(0);
    Ok((blocks, revision))
}

pub(crate) fn views_for_week(
    assignments: &Map<String, Value>,
    rows: &[(String, String, i64)],
    weeks: &[(String, Vec<Value>, i64)],
    week_start: &str,
) -> Result<Map<String, Value>, FfiError> {
    let listed: Vec<(String, Vec<Value>)> = weeks
        .iter()
        .map(|(start, blocks, _)| (start.clone(), blocks.clone()))
        .collect();
    let planned = flexweek_engine::plan::planned_minutes_by_id(&listed, week_start);
    let mut views = Map::new();
    for (id, _, revision) in rows {
        let Some(body) = assignments.get(id) else {
            continue;
        };
        let planned_min = planned.get(id).copied().unwrap_or(0);
        let mut view = flexweek_store::assignment_view(body, *revision, planned_min)
            .map_err(engine_failure)?;
        if let Some(given) = body.get("unplanned_min") {
            view["unplanned_min"] = given.clone();
        }
        views.insert(id.clone(), view);
    }
    Ok(views)
}

pub(crate) fn availability(
    db: &Connection,
    user_id: i64,
) -> Result<flexweek_store::SolveAvailability, FfiError> {
    let stored = flexweek_store::availability_json(db, user_id).map_err(failure)?;
    flexweek_store::solve_availability(stored.as_deref(), |_kind, items| {
        Ok::<Value, FfiError>(items.clone())
    })
    .map_err(|relay| match relay {
        flexweek_store::Relay::Store(error) => failure(error),
        flexweek_store::Relay::Caller(error) => error,
    })
}

pub(crate) fn work_windows(
    value: &Value,
) -> Result<Vec<flexweek_engine::solver::WorkWindow>, FfiError> {
    Ok(value
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .map(flexweek_engine::solver::work_window_from_value)
        .collect())
}

pub(crate) fn hex_id(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

pub(crate) fn remember(
    db: &Connection,
    user_id: i64,
    op_id: &str,
    payload: &str,
) -> Result<bool, FfiError> {
    if op_id.is_empty() {
        return Ok(false);
    }
    match flexweek_store::recall_operation(db, user_id, op_id, &flexweek_store::digest(payload))
        .map_err(failure)?
    {
        flexweek_store::Recall::Hit(_) => Ok(true),
        flexweek_store::Recall::Conflict => {
            Err(failure("operation id was already used for another change"))
        }
        flexweek_store::Recall::Missing => Ok(false),
    }
}

pub(crate) fn store_operation(
    db: &Connection,
    user_id: i64,
    op_id: &str,
    payload: &str,
) -> Result<(), FfiError> {
    if !op_id.is_empty() {
        flexweek_store::remember_operation(
            db,
            user_id,
            op_id,
            &flexweek_store::digest(payload),
            "{}",
            1000,
        )
        .map_err(failure)?;
    }
    Ok(())
}

pub(crate) fn rollback(db: &Connection) {
    let _ = db.execute_batch("ROLLBACK");
}

pub(crate) fn write_week(
    db: &Connection,
    user_id: i64,
    week_start: &str,
    blocks: &Value,
    revision: i64,
) -> Result<(), FfiError> {
    match flexweek_store::save_week(db, user_id, week_start, &blocks.to_string(), revision)
        .map_err(failure)?
    {
        flexweek_store::WeekSave::Ready(_) => Ok(()),
        flexweek_store::WeekSave::Conflict => {
            rollback(db);
            Err(failure("week changed on another device"))
        }
    }
}

pub(crate) fn clock(week: &crate::core::FlexWeek, elapsed_ms: f64) -> impl Fn() -> f64 + '_ {
    let origin = week.host.now_unix_ms();
    move || elapsed_ms + (week.host.now_unix_ms() - origin) as f64
}

pub(crate) fn empty_plan(week_start: &str, message: &str) -> Value {
    json!({
        "week_start": week_start,
        "placed": [],
        "not_placed": [],
        "moves": [],
        "explanations": [],
        "applied_preview": "",
        "message": message,
    })
}
