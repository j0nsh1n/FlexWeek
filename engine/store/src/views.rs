//! Read assembly the HTTP routes still do in Python (`month_weeks`, the day, the homework list).
//!
//! `rewrite_stored_blocks` is called with an identity normalizer. The pydantic pass that fills
//! TimeBlock defaults is a later slice and lives in the engine, which this lane does not change.
//! Titles and the other assignment fields are still copied onto the block.

use std::collections::{BTreeMap, BTreeSet};

use flexweek_engine::model::due_sort_key;
use flexweek_engine::plan::{build_day, build_month, planned_minutes_by_id};
use flexweek_engine::time::{
    is_calendar_date, is_month_label, is_week_start, monday_of, month_grid, parse_month,
};
use rusqlite::Connection;
use serde_json::{Map, Value, json};

use crate::{
    Relay, StoreError, StoreResult, assignment_bodies, assignment_view, list_account_weeks,
    list_assignment_rows, list_restore_points, list_routines, load_assignment_rows, read_week,
    rewrite_stored_blocks, week_blocks, week_with_standing,
};

const WEEK_START_RULE: &str =
    "week_start must be a Monday from 2000-01-03 through 2099-12-28, or 1999-12-27";
const DATE_RULE: &str = "date must be YYYY-MM-DD between 2000-01-01 and 2099-12-31";
const MONTH_RULE: &str = "month must be YYYY-MM between 2000-01 and 2099-12";

pub fn day_view(conn: &Connection, user_id: i64, date: &str) -> StoreResult<Value> {
    if !is_calendar_date(date) {
        return Err(StoreError::Date(DATE_RULE.into()));
    }
    let week_start = monday_of(date)?;
    let stored = week_blocks(conn, user_id, &week_start)?;
    let merged = week_with_standing(
        conn,
        user_id,
        &week_start,
        stored.as_deref().unwrap_or("[]"),
    )?;
    let blocks = parse_json(&merged)?;
    let ids = assignment_ids(&blocks);
    let owned = owned_assignments(conn, user_id, &ids)?;
    let rewritten = rewritten(&blocks, &owned)?;
    let assignments = parsed_assignment_bodies(conn, user_id)?;
    let weeks = raw_weeks(conn, user_id)?;
    Ok(build_day(
        date,
        &week_start,
        &rewritten,
        &assignments,
        &weeks,
    )?)
}

pub fn month_view(conn: &Connection, user_id: i64, month: &str) -> StoreResult<Value> {
    if !is_month_label(month) {
        return Err(StoreError::Date(MONTH_RULE.into()));
    }
    let (first, last) = parse_month(month)?;
    let (grid_start, grid_end) = month_grid(&first, &last)?;
    let mut saved: BTreeMap<String, String> =
        list_account_weeks(conn, user_id)?.into_iter().collect();
    let mut monday = grid_start;
    while monday.as_str() <= grid_end.as_str() {
        saved
            .entry(monday.clone())
            .or_insert_with(|| "[]".to_string());
        monday = add_days(&monday, 7).ok_or_else(|| StoreError::Date(WEEK_START_RULE.into()))?;
    }
    let mut weeks = Vec::with_capacity(saved.len());
    for (start, text) in saved {
        let merged = week_with_standing(conn, user_id, &start, &text)?;
        let blocks: Vec<Value> =
            serde_json::from_str(&merged).map_err(|error| StoreError::Json {
                text: merged,
                error,
            })?;
        weeks.push((start, blocks));
    }
    let assignments = parsed_assignment_bodies(conn, user_id)?;
    Ok(build_month(month, &assignments, &weeks)?)
}

pub fn homework_list(
    conn: &Connection,
    user_id: i64,
    week_start: &str,
    include_completed: bool,
) -> StoreResult<Value> {
    if !is_week_start(week_start) {
        return Err(StoreError::Date(WEEK_START_RULE.into()));
    }
    let rows = list_assignment_rows(conn, user_id)?;
    let weeks = raw_weeks(conn, user_id)?;
    let planned = planned_minutes_by_id(&weeks, week_start);
    let mut session_weeks: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for (saved_week, blocks) in &weeks {
        for block in blocks {
            let Some(id) = block.get("assignment_id").and_then(Value::as_str) else {
                continue;
            };
            session_weeks
                .entry(id.to_string())
                .or_default()
                .insert(saved_week.clone());
        }
    }
    let mut keyed = Vec::new();
    for (row_id, row_body, row_revision) in rows {
        let body = parse_json(&row_body)?;
        let completed = body
            .get("completed")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        if completed && !include_completed {
            continue;
        }
        let planned_min = planned.get(&row_id).copied().unwrap_or(0);
        let mut item = assignment_view(&body, row_revision, planned_min)?;
        let listed: Vec<&str> = session_weeks
            .get(&row_id)
            .map(|weeks| weeks.iter().map(String::as_str).collect())
            .unwrap_or_default();
        if let Some(fields) = item.as_object_mut() {
            fields.insert("session_weeks".into(), json!(listed));
        }
        let due = item.get("due").and_then(Value::as_str);
        let id = item.get("id").and_then(Value::as_str).unwrap_or("");
        let key = due_sort_key(due, id)?;
        keyed.push((key, item));
    }
    keyed.sort_by(|left, right| left.0.cmp(&right.0));
    let items: Vec<Value> = keyed.into_iter().map(|(_, item)| item).collect();
    Ok(json!({ "assignments": items }))
}

pub fn week_view(conn: &Connection, user_id: i64, week_start: &str) -> StoreResult<Value> {
    if !is_week_start(week_start) {
        return Err(StoreError::Date(WEEK_START_RULE.into()));
    }
    let row = read_week(conn, user_id, week_start)?;
    let stored = row.as_ref().map(|(blocks, _)| blocks.as_str());
    let merged = week_with_standing(conn, user_id, week_start, stored.unwrap_or("[]"))?;
    let blocks = parse_json(&merged)?;
    let ids = assignment_ids(&blocks);
    let owned = owned_assignments(conn, user_id, &ids)?;
    let rewritten = rewritten(&blocks, &owned)?;
    let revision = row.map(|(_, revision)| revision).unwrap_or(0);
    Ok(json!({
        "week_start": week_start,
        "revision": revision,
        "blocks": rewritten,
    }))
}

pub fn routine_list(conn: &Connection, user_id: i64) -> StoreResult<Value> {
    let text = list_routines(conn, user_id)?;
    let rows: Vec<Value> =
        serde_json::from_str(&text).map_err(|error| StoreError::Json { text, error })?;
    let mut routines = Vec::with_capacity(rows.len());
    for row in rows {
        let body = row.get("body").and_then(Value::as_str).unwrap_or("[]");
        let blocks = parse_json(body)?;
        routines.push(json!({
            "id": row.get("id").cloned().unwrap_or(Value::Null),
            "name": row.get("name").cloned().unwrap_or(Value::Null),
            "blocks": blocks,
            "revision": row.get("revision").cloned().unwrap_or(Value::Null),
            "created_at": row.get("created_at").cloned().unwrap_or(Value::Null),
            "updated_at": row.get("updated_at").cloned().unwrap_or(Value::Null),
        }));
    }
    Ok(json!({ "routines": routines }))
}

pub fn restore_point_list(conn: &Connection, user_id: i64) -> StoreResult<Value> {
    let text = list_restore_points(conn, user_id)?;
    let rows: Vec<Value> =
        serde_json::from_str(&text).map_err(|error| StoreError::Json { text, error })?;
    let mut restore_points = Vec::with_capacity(rows.len());
    for row in rows {
        restore_points.push(json!({
            "id": row.get("id").cloned().unwrap_or(Value::Null),
            "label": row.get("label").cloned().unwrap_or(Value::Null),
            "created_at": row.get("created_at").cloned().unwrap_or(Value::Null),
            "weeks": row.get("weeks_count").cloned().unwrap_or(Value::Null),
            "assignments": row.get("assignments_count").cloned().unwrap_or(Value::Null),
        }));
    }
    Ok(json!({ "restore_points": restore_points }))
}

fn rewritten(blocks: &Value, owned: &Value) -> StoreResult<Vec<Value>> {
    rewrite_stored_blocks(blocks, owned, |block| Ok(block.clone())).map_err(|error| match error {
        Relay::Store(error) | Relay::Caller(error) => error,
    })
}

fn assignment_ids(blocks: &Value) -> Vec<String> {
    blocks
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|block| block.get("assignment_id").and_then(Value::as_str))
        .map(str::to_string)
        .collect()
}

fn owned_assignments(conn: &Connection, user_id: i64, ids: &[String]) -> StoreResult<Value> {
    let mut fields = Map::new();
    for (id, body, _) in load_assignment_rows(conn, user_id, ids)? {
        fields.insert(id, parse_json(&body)?);
    }
    Ok(Value::Object(fields))
}

fn parsed_assignment_bodies(conn: &Connection, user_id: i64) -> StoreResult<Vec<(Value, i64)>> {
    let mut rows = Vec::new();
    for (body, revision) in assignment_bodies(conn, user_id)? {
        rows.push((parse_json(&body)?, revision));
    }
    Ok(rows)
}

fn raw_weeks(conn: &Connection, user_id: i64) -> StoreResult<Vec<(String, Vec<Value>)>> {
    let mut weeks = Vec::new();
    for (start, text) in list_account_weeks(conn, user_id)? {
        let blocks: Vec<Value> =
            serde_json::from_str(&text).map_err(|error| StoreError::Json { text, error })?;
        weeks.push((start, blocks));
    }
    Ok(weeks)
}

fn parse_json(text: &str) -> StoreResult<Value> {
    serde_json::from_str(text).map_err(|error| StoreError::Json {
        text: text.to_string(),
        error,
    })
}

/// Seven days later, as `YYYY-MM-DD`. The store crate does not depend on chrono.
fn add_days(iso: &str, days: i32) -> Option<String> {
    let mut parts = iso.split('-');
    let year: i32 = parts.next()?.parse().ok()?;
    let month: u32 = parts.next()?.parse().ok()?;
    let day: u32 = parts.next()?.parse().ok()?;
    if parts.next().is_some() {
        return None;
    }
    let z = days_from_civil(year, month, day).checked_add(days)?;
    let (year, month, day) = civil_from_days(z);
    Some(format!("{year:04}-{month:02}-{day:02}"))
}

fn days_from_civil(mut year: i32, month: u32, day: u32) -> i32 {
    year -= i32::from(month <= 2);
    let era = if year >= 0 { year } else { year - 399 } / 400;
    let year_of_era = (year - era * 400) as u32;
    let month_prime = if month > 2 { month - 3 } else { month + 9 };
    let day_of_year = (153 * month_prime + 2) / 5 + day - 1;
    let day_of_era = year_of_era * 365 + year_of_era / 4 - year_of_era / 100 + day_of_year;
    era * 146097 + day_of_era as i32 - 719468
}

fn civil_from_days(z: i32) -> (i32, u32, u32) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let day_of_era = (z - era * 146097) as u32;
    let year_of_era =
        (day_of_era - day_of_era / 1460 + day_of_era / 36524 - day_of_era / 146096) / 365;
    let year = year_of_era as i32 + era * 400;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let month_prime = (5 * day_of_year + 2) / 153;
    let day = day_of_year - (153 * month_prime + 2) / 5 + 1;
    let month = if month_prime < 10 {
        month_prime + 3
    } else {
        month_prime - 9
    };
    (year + i32::from(month <= 2), month, day)
}
