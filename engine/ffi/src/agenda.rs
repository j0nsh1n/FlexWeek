use std::convert::Infallible;

use chrono::Datelike;
use flexweek_engine::desk::blocks::mark_block_done;
use flexweek_engine::desk::homework::mark_homework_done;
use flexweek_engine::desk::weekmodel::build_week;
use flexweek_engine::desk::weekview::Week;
use flexweek_engine::{plan, time};
use serde_json::{Map, Value, json};

use crate::core::{
    FfiError, FlexWeek, db_lock, engine_failure, failure, local_stamp, parse_date, require_user,
};

fn assignment_values(rows: &[(String, i64)]) -> Result<(Vec<(Value, i64)>, Value), FfiError> {
    let mut parsed = Vec::with_capacity(rows.len());
    let mut keyed = Map::new();
    for (body, revision) in rows {
        let value: Value = serde_json::from_str(body).map_err(failure)?;
        if let Some(id) = value.get("id").and_then(Value::as_str) {
            keyed.insert(id.to_string(), value.clone());
        }
        parsed.push((value, *revision));
    }
    Ok((parsed, Value::Object(keyed)))
}

fn decode_blocks(raw: &str) -> Result<Value, FfiError> {
    serde_json::from_str(raw).map_err(failure)
}

fn rewritten(blocks: &Value, assignments: &Value) -> Result<Vec<Value>, FfiError> {
    flexweek_store::rewrite_stored_blocks(blocks, assignments, |block| {
        Ok::<Value, Infallible>(block.clone())
    })
    .map_err(|relay| match relay {
        flexweek_store::Relay::Store(error) => failure(error),
        flexweek_store::Relay::Caller(error) => match error {},
    })
}

fn stored_weeks(
    db: &rusqlite::Connection,
    user_id: i64,
) -> Result<Vec<(String, Vec<Value>)>, FfiError> {
    let mut weeks = Vec::new();
    for (start, stored) in flexweek_store::list_account_weeks(db, user_id).map_err(failure)? {
        let blocks: Vec<Value> = serde_json::from_str(&stored).map_err(failure)?;
        weeks.push((start, blocks));
    }
    Ok(weeks)
}

fn date_offset(monday: &str, day: i64) -> Result<String, FfiError> {
    let (year, month, date) =
        flexweek_engine::desk::weekview::date_of(monday, day).map_err(engine_failure)?;
    Ok(format!("{year:04}-{month:02}-{date:02}"))
}

fn whole(value: &Value) -> Option<i64> {
    value.as_i64().or_else(|| {
        value
            .as_f64()
            .and_then(|number| (number.fract() == 0.0).then_some(number as i64))
    })
}

fn hhmm(minutes: i64) -> String {
    time::minutes_to_hhmm(minutes)
}

fn occurrence_row(item: &Value, now_minute: i64) -> Option<Value> {
    let start = whole(item.get("start")?)?;
    let end = whole(item.get("end")?)?;
    Some(json!({
        "id": item.get("block_id").cloned().unwrap_or(Value::Null),
        "title": item.get("title").cloned().unwrap_or(json!("")),
        "category": item.get("category").cloned().unwrap_or(json!("")),
        "start": hhmm(start),
        "end": hhmm(end),
        "start_min": start,
        "end_min": end,
        "duration_min": end - start,
        "homework": item.get("work").and_then(Value::as_bool).unwrap_or(false),
        "done": item.get("done").and_then(Value::as_bool).unwrap_or(false),
        "missed": item.get("missed").and_then(Value::as_bool).unwrap_or(false),
        "past": end <= now_minute,
        "day": whole(item.get("day")?).unwrap_or(0),
        "assignment_id": item.get("assignment_id").cloned().unwrap_or(Value::Null),
    }))
}

fn due_homework(assignments: &[(Value, i64)], monday: &str) -> Result<Vec<Value>, FfiError> {
    let end = date_offset(monday, 6)?;
    let mut rows = Vec::new();
    for (body, _) in assignments {
        if body.get("completed").and_then(Value::as_bool) == Some(true) {
            continue;
        }
        let Some(due) = body.get("due").and_then(Value::as_str) else {
            continue;
        };
        let Some(date) = due.get(..10) else {
            continue;
        };
        if date < monday || date > end.as_str() {
            continue;
        }
        let weekday = parse_date(date)?.weekday().num_days_from_monday() as usize;
        rows.push(json!({
            "id": body.get("id").cloned().unwrap_or(Value::Null),
            "title": body.get("title").cloned().unwrap_or(json!("")),
            "due": due,
            "weekday": flexweek_engine::desk::calendar::DAYS[weekday],
        }));
    }
    rows.sort_by(|left, right| {
        left["due"]
            .as_str()
            .cmp(&right["due"].as_str())
            .then_with(|| left["title"].as_str().cmp(&right["title"].as_str()))
    });
    Ok(rows)
}

fn empty_today(week: &FlexWeek, date: &str, monday: &str, day: i64) -> Result<String, FfiError> {
    let mut days = Vec::new();
    for offset in 0..7 {
        days.push(json!({
            "day": offset,
            "date": date_offset(monday, offset)?,
            "scheduled_count": 0,
            "due_count": 0,
        }));
    }
    Ok(json!({
        "date": date,
        "week_start": monday,
        "day": day,
        "days": days,
        "rows": [],
        "now": Value::Null,
        "nothing_left": false,
        "no_time_yet": [],
        "due_homework": [],
        "due_soon": [],
        "workload": {
            "scheduled_min": 0,
            "focus_min": 0,
            "available_min": 0,
            "by_category": [],
        },
        "empty": true,
        "sync_status": week.sync.status(),
    })
    .to_string())
}

pub(crate) fn today(week: &FlexWeek, date: &str, now_minute: i64) -> Result<String, FfiError> {
    let parsed_date = parse_date(date)?;
    let monday = time::monday_of(date).map_err(engine_failure)?;
    let day = i64::from(parsed_date.weekday().num_days_from_monday());
    let Some(user_id) = week.account_id() else {
        return empty_today(week, date, &monday, day);
    };
    let db = db_lock(week)?;
    let raw = flexweek_store::week_blocks(&db, user_id, &monday)
        .map_err(failure)?
        .unwrap_or_else(|| "[]".into());
    let merged =
        flexweek_store::week_with_standing(&db, user_id, &monday, &raw).map_err(failure)?;
    let all_assignments = flexweek_store::assignment_bodies(&db, user_id).map_err(failure)?;
    let (assignment_rows, assignment_map) = assignment_values(&all_assignments)?;
    let stored_blocks = decode_blocks(&merged)?;
    let blocks = rewritten(&stored_blocks, &assignment_map)?;
    let weeks = stored_weeks(&db, user_id)?;
    let day_data = plan::build_day(date, &monday, &blocks, &assignment_rows, &weeks)
        .map_err(engine_failure)?;
    let model = build_week(
        &json!(monday),
        &Value::Array(blocks),
        &assignment_map,
        &json!({}),
    )
    .map_err(engine_failure)?;
    let view = Week::read(&model.to_string()).map_err(engine_failure)?;
    let (current, queue) = view.day_queue(day, now_minute);
    let occurrences = model
        .get("occurrences")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let rows: Vec<Value> = occurrences
        .iter()
        .filter(|item| whole(item.get("day").unwrap_or(&Value::Null)) == Some(day))
        .filter_map(|item| occurrence_row(item, now_minute))
        .collect();
    let now = queue.first().and_then(|at| {
        let item = occurrences.get(*at)?;
        let start = whole(item.get("start")?)?;
        let end = whole(item.get("end")?)?;
        let then = queue.get(1).and_then(|next| occurrences.get(*next));
        let then_start = then.and_then(|item| whole(item.get("start")?));
        Some(json!({
            "kind": if current == Some(*at) { "now" } else { "up_next" },
            "block_id": item.get("block_id").cloned().unwrap_or(Value::Null),
            "title": item.get("title").cloned().unwrap_or(json!("")),
            "homework": item.get("work").and_then(Value::as_bool).unwrap_or(false),
            "minutes_left": if current == Some(*at) { end - now_minute } else { start - now_minute },
            "start": hhmm(start),
            "end": hhmm(end),
            "then_title": then.map(|item| item.get("title").cloned().unwrap_or(json!(""))),
            "then_start": then_start.map(hhmm),
        }))
    });
    let no_time_yet: Vec<Value> = model
        .get("waiting")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .map(|item| {
                    json!({
                        "id": item.get("block_id").cloned().unwrap_or(Value::Null),
                        "title": item.get("title").cloned().unwrap_or(json!("")),
                        "category": item.get("category").cloned().unwrap_or(json!("")),
                        "minutes": whole(item.get("minutes").unwrap_or(&Value::Null)).unwrap_or(0),
                        "due": item.get("due").cloned().unwrap_or(Value::Null),
                        "assignment_id": item.get("assignment_id").cloned().unwrap_or(Value::Null),
                        "reason": item.get("reason").cloned().unwrap_or(json!("")),
                    })
                })
                .collect()
        })
        .unwrap_or_default();
    let due = due_homework(&assignment_rows, &monday)?;
    let mut chips = Vec::new();
    for offset in 0..7 {
        let chip_date = date_offset(&monday, offset)?;
        let scheduled_count = occurrences
            .iter()
            .filter(|item| whole(item.get("day").unwrap_or(&Value::Null)) == Some(offset))
            .count();
        let due_count = due
            .iter()
            .filter(|item| {
                item["due"].as_str().and_then(|text| text.get(..10)) == Some(chip_date.as_str())
            })
            .count();
        chips.push(json!({
            "day": offset,
            "date": chip_date,
            "scheduled_count": scheduled_count,
            "due_count": due_count,
        }));
    }
    let nothing_left = now.is_none() && !rows.is_empty();
    let empty = rows.is_empty();
    Ok(json!({
        "date": date,
        "week_start": monday,
        "day": day,
        "days": chips,
        "rows": rows,
        "now": now,
        "nothing_left": nothing_left,
        "no_time_yet": no_time_yet,
        "due_homework": due,
        "due_soon": day_data.get("due_soon").cloned().unwrap_or(json!([])),
        "workload": day_data.get("workload").cloned().unwrap_or(json!({})),
        "empty": empty,
        "sync_status": week.sync.status(),
    })
    .to_string())
}

pub(crate) fn operation_seen(
    db: &rusqlite::Connection,
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

pub(crate) fn remember_operation(
    db: &rusqlite::Connection,
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

fn rollback(db: &rusqlite::Connection) {
    let _ = db.execute_batch("ROLLBACK");
}

pub(crate) fn set_block_done(
    week: &FlexWeek,
    week_start: &str,
    block_id: &str,
    day: i64,
    done: bool,
    op_id: &str,
) -> Result<(), FfiError> {
    let user_id = require_user(week)?;
    let payload = json!(["block", week_start, block_id, day, done]).to_string();
    let db = db_lock(week)?;
    if operation_seen(&db, user_id, op_id, &payload)? {
        return Ok(());
    }
    let Some((raw, revision)) =
        flexweek_store::read_week(&db, user_id, week_start).map_err(failure)?
    else {
        return Err(failure("week was not found"));
    };
    let mut blocks: Value = serde_json::from_str(&raw).map_err(failure)?;
    let items = blocks
        .as_array_mut()
        .ok_or_else(|| failure("stored week is not a list"))?;
    mark_block_done(items, block_id, day, done).map_err(failure)?;
    match flexweek_store::save_week(&db, user_id, week_start, &blocks.to_string(), revision)
        .map_err(failure)?
    {
        flexweek_store::WeekSave::Ready(_) => {}
        flexweek_store::WeekSave::Conflict => {
            rollback(&db);
            return Err(failure("week changed on another device"));
        }
    }
    if let Err(error) = remember_operation(&db, user_id, op_id, &payload) {
        rollback(&db);
        return Err(error);
    }
    db.execute_batch("COMMIT").map_err(failure)?;
    drop(db);
    week.host.data_changed("week".into());
    Ok(())
}

pub(crate) fn set_homework_done(
    week: &FlexWeek,
    id: &str,
    done: bool,
    op_id: &str,
) -> Result<(), FfiError> {
    let user_id = require_user(week)?;
    let payload = json!(["homework", id, done]).to_string();
    let db = db_lock(week)?;
    if operation_seen(&db, user_id, op_id, &payload)? {
        return Ok(());
    }
    let rows = flexweek_store::list_assignment_rows(&db, user_id).map_err(failure)?;
    let mut stored = None;
    let mut revision = 0;
    let mut assignment_map = Map::new();
    for (assignment_id, body, row_revision) in &rows {
        let parsed: Value = serde_json::from_str(body).map_err(failure)?;
        if assignment_id == id {
            stored = Some(parsed.clone());
            revision = *row_revision;
        }
        assignment_map.insert(assignment_id.clone(), parsed);
    }
    let assignment = stored.ok_or_else(|| failure("homework was not found"))?;
    let needs_stamp = done
        && assignment.is_object()
        && assignment
            .get("completed_at")
            .and_then(Value::as_str)
            .filter(|text| !text.is_empty())
            .is_none();
    let stamp = if needs_stamp {
        local_stamp(&*week.host)?
    } else {
        String::new()
    };
    let mut weeks = Vec::new();
    for (week_start, raw) in flexweek_store::list_account_weeks(&db, user_id).map_err(failure)? {
        let parsed: Value = serde_json::from_str(&raw).map_err(failure)?;
        let Value::Array(blocks) = parsed else {
            return Err(failure("stored week is not a list"));
        };
        weeks.push((week_start, blocks));
    }
    let marked = mark_homework_done(id, &assignment, &assignment_map, &weeks, done, &stamp)
        .map_err(failure)?;
    match flexweek_store::save_assignment(
        &db,
        user_id,
        id,
        &marked.assignment.to_string(),
        revision,
        i64::MAX,
    )
    .map_err(failure)?
    {
        flexweek_store::AssignmentSave::Ready(_) => {}
        flexweek_store::AssignmentSave::Conflict => {
            rollback(&db);
            return Err(failure("homework changed on another device"));
        }
        flexweek_store::AssignmentSave::OverLimit => {
            rollback(&db);
            return Err(failure("assignment limit reached"));
        }
    }
    for marked_week in marked.weeks {
        let (_, week_revision) = flexweek_store::read_week(&db, user_id, &marked_week.week_start)
            .map_err(failure)?
            .ok_or_else(|| {
                rollback(&db);
                failure("week was not found")
            })?;
        match flexweek_store::save_week(
            &db,
            user_id,
            &marked_week.week_start,
            &Value::Array(marked_week.blocks).to_string(),
            week_revision,
        )
        .map_err(failure)?
        {
            flexweek_store::WeekSave::Ready(_) => {}
            flexweek_store::WeekSave::Conflict => {
                rollback(&db);
                return Err(failure("week changed on another device"));
            }
        }
    }
    if let Err(error) = remember_operation(&db, user_id, op_id, &payload) {
        rollback(&db);
        return Err(error);
    }
    db.execute_batch("COMMIT").map_err(failure)?;
    drop(db);
    week.host.data_changed("homework".into());
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::tests_support::{open_test, save_week};
    use serde_json::json;

    fn agenda_week(week: &FlexWeek) {
        let db = week.db.lock().unwrap();
        for (id, body) in [
            (
                "bio",
                r#"{"id":"bio","title":"Bio reading","due":"2026-10-07T20:00","estimate_min":60,"focus_minutes":0,"completed":false,"category":"homework"}"#,
            ),
            (
                "lab",
                r#"{"id":"lab","title":"Lab report","due":"2026-10-08T18:00","estimate_min":60,"focus_minutes":0,"completed":false,"category":"homework"}"#,
            ),
            (
                "essay",
                r#"{"id":"essay","title":"History essay","due":"2026-10-09T21:00","estimate_min":60,"focus_minutes":0,"completed":false,"category":"homework"}"#,
            ),
            (
                "poster",
                r#"{"id":"poster","title":"Science poster","due":"2026-10-09T16:00","estimate_min":60,"focus_minutes":0,"completed":false,"category":"homework"}"#,
            ),
            (
                "math",
                r#"{"id":"math","title":"Math worksheet","due":"2026-10-11T12:00","estimate_min":60,"focus_minutes":0,"completed":false,"category":"homework"}"#,
            ),
        ] {
            flexweek_store::insert_assignment(&db, week.user_id.unwrap(), id, body).unwrap();
        }
        drop(db);
        save_week(
            week,
            "2026-10-05",
            &json!([
                {"id":"school","title":"School","kind":"locked","days":[0,1,2,3,4],"start":"08:00","duration_min":390,"category":"school"},
                {"id":"soccer","title":"Soccer","kind":"locked","days":[1,3],"start":"16:00","duration_min":90,"category":"sports"},
                {"id":"bio-session","assignment_id":"bio","title":"STALE BIO","kind":"flexible","days":[2],"start":"17:00","duration_min":60,"completed":true,"completed_day":2,"category":"study"},
                {"id":"lab-session","assignment_id":"lab","title":"STALE LAB","kind":"flexible","days":[3],"start":"10:00","duration_min":60,"category":"study"},
                {"id":"essay-session","assignment_id":"essay","title":"STALE ESSAY","kind":"flexible","days":[3],"start":"19:00","duration_min":60,"category":"study"},
                {"id":"poster-session","assignment_id":"poster","title":"STALE POSTER","kind":"flexible","days":[4],"duration_min":60,"category":"study"},
                {"id":"math-session","assignment_id":"math","title":"STALE MATH","kind":"flexible","days":[6],"duration_min":60,"category":"study"}
            ]),
        );
    }

    #[test]
    fn today_follows_the_agenda_queue_for_the_demo_thursday() {
        let (week, _path) = open_test("golden-day");
        agenda_week(&week);
        let out: Value =
            serde_json::from_str(&week.today("2026-10-08".into(), 15 * 60 + 40).unwrap()).unwrap();
        assert_eq!(out["week_start"], "2026-10-05");
        assert_eq!(out["day"], 3);
        assert_eq!(out["empty"], false);
        assert_eq!(out["nothing_left"], false);
        assert_eq!(out["sync_status"], "not paired");
        assert_eq!(
            out["rows"]
                .as_array()
                .unwrap()
                .iter()
                .map(|row| row["title"].as_str().unwrap())
                .collect::<Vec<_>>(),
            vec!["School", "Lab report", "Soccer", "History essay"]
        );
        assert_eq!(out["rows"][0]["start"], "08:00");
        assert_eq!(out["rows"][0]["end"], "14:30");
        assert_eq!(out["rows"][0]["past"], true);
        assert_eq!(out["rows"][0]["homework"], false);
        assert_eq!(out["rows"][1]["id"], "lab-session");
        assert_eq!(out["rows"][1]["start"], "10:00");
        assert_eq!(out["rows"][1]["end"], "11:00");
        assert_eq!(out["rows"][1]["past"], true);
        assert_eq!(out["rows"][1]["homework"], true);
        assert_eq!(out["rows"][1]["category"], "homework");
        assert_eq!(out["rows"][2]["start"], "16:00");
        assert_eq!(out["rows"][2]["end"], "17:30");
        assert_eq!(out["rows"][2]["past"], false);
        assert_eq!(out["rows"][3]["start"], "19:00");
        assert_eq!(out["rows"][3]["end"], "20:00");
        assert_eq!(out["rows"][3]["homework"], true);
        assert_eq!(out["now"]["kind"], "up_next");
        assert_eq!(out["now"]["title"], "Soccer");
        assert_eq!(out["now"]["block_id"], "soccer");
        assert_eq!(out["now"]["homework"], false);
        assert_eq!(out["now"]["minutes_left"], 20);
        assert_eq!(out["now"]["start"], "16:00");
        assert_eq!(out["now"]["end"], "17:30");
        assert_eq!(out["now"]["then_title"], "History essay");
        assert_eq!(out["now"]["then_start"], "19:00");
        assert_eq!(out["days"][3]["date"], "2026-10-08");
        assert_eq!(out["days"][3]["scheduled_count"], 4);
        assert_eq!(out["days"][3]["due_count"], 1);
        assert_eq!(out["days"][4]["date"], "2026-10-09");
        assert_eq!(out["days"][4]["scheduled_count"], 1);
        assert_eq!(out["days"][4]["due_count"], 2);
        assert_eq!(out["days"][5]["scheduled_count"], 0);
        assert_eq!(out["days"][5]["due_count"], 0);
        assert_eq!(
            out["no_time_yet"]
                .as_array()
                .unwrap()
                .iter()
                .map(|item| item["title"].as_str().unwrap())
                .collect::<Vec<_>>(),
            vec!["Science poster", "Math worksheet"]
        );
        assert_eq!(out["no_time_yet"][0]["id"], "poster-session");
        assert_eq!(out["no_time_yet"][0]["minutes"], 60);
        assert_eq!(out["no_time_yet"][0]["due"], "2026-10-09T16:00");
        assert_eq!(out["no_time_yet"][0]["reason"], "Not planned yet.");
        assert_eq!(out["no_time_yet"][0]["category"], "homework");
        assert_eq!(
            out["due_homework"]
                .as_array()
                .unwrap()
                .iter()
                .map(|item| item["title"].as_str().unwrap())
                .collect::<Vec<_>>(),
            vec![
                "Bio reading",
                "Lab report",
                "Science poster",
                "History essay",
                "Math worksheet"
            ]
        );
        assert_eq!(out["due_homework"][2]["weekday"], "Fri");
        assert_eq!(out["due_homework"][4]["weekday"], "Sun");
        assert_eq!(
            out["due_soon"]
                .as_array()
                .unwrap()
                .iter()
                .map(|item| item["id"].as_str().unwrap())
                .collect::<Vec<_>>(),
            vec!["bio", "lab", "poster", "essay"]
        );
        assert_eq!(out["due_soon"][0]["unplanned_min"], 60);
        assert_eq!(out["workload"]["scheduled_min"], 600);
        assert_eq!(out["workload"]["focus_min"], 0);

        let early: Value =
            serde_json::from_str(&week.today("2026-10-08".into(), 10 * 60 + 30).unwrap()).unwrap();
        assert_eq!(early["now"]["kind"], "now");
        assert_eq!(early["now"]["title"], "Lab report");
        assert_eq!(early["now"]["homework"], true);
        assert_eq!(early["now"]["minutes_left"], 30);
        assert_eq!(early["now"]["then_title"], "Soccer");
        assert_eq!(early["now"]["then_start"], "16:00");
        assert_eq!(early["rows"][1]["past"], false);

        let late: Value =
            serde_json::from_str(&week.today("2026-10-08".into(), 21 * 60).unwrap()).unwrap();
        assert!(late["now"].is_null());
        assert_eq!(late["nothing_left"], true);
        assert_eq!(late["rows"][3]["past"], true);

        let saturday: Value =
            serde_json::from_str(&week.today("2026-10-10".into(), 15 * 60 + 40).unwrap()).unwrap();
        assert_eq!(saturday["empty"], true);
        assert_eq!(saturday["rows"].as_array().unwrap().len(), 0);
        assert!(saturday["now"].is_null());
    }

    #[test]
    fn set_block_done_sets_both_completion_fields_and_is_retry_safe() {
        let (week, _path) = open_test("block-done");
        save_week(
            &week,
            "2026-10-12",
            &json!([
                {"id":"session","title":"Reading","kind":"flexible","days":[0],"start":"10:00","duration_min":30},
                {"id":"school","title":"School","kind":"locked","days":[0],"start":"08:00","duration_min":60}
            ]),
        );
        week.set_block_done(
            "2026-10-12".into(),
            "session".into(),
            0,
            true,
            "op-1".into(),
        )
        .unwrap();
        week.set_block_done(
            "2026-10-12".into(),
            "session".into(),
            0,
            true,
            "op-1".into(),
        )
        .unwrap();
        let conflict = week.set_block_done(
            "2026-10-12".into(),
            "session".into(),
            0,
            false,
            "op-1".into(),
        );
        assert_eq!(
            conflict.unwrap_err().to_string(),
            "operation id was already used for another change"
        );
        week.set_block_done(
            "2026-10-12".into(),
            "school".into(),
            0,
            true,
            "op-school".into(),
        )
        .unwrap();
        let db = week.db.lock().unwrap();
        let blocks = flexweek_store::week_blocks(&db, week.user_id.unwrap(), "2026-10-12")
            .unwrap()
            .unwrap();
        let blocks: Value = serde_json::from_str(&blocks).unwrap();
        assert_eq!(blocks[0]["completed"], true);
        assert_eq!(blocks[0]["completed_day"], 0);
        assert_eq!(blocks[0]["start"], "10:00");
        assert_eq!(blocks[1]["completed"], true);
        assert!(blocks[1].get("completed_day").is_none());
    }

    #[test]
    fn set_homework_done_updates_the_assignment_and_session_together() {
        let (week, _path) = open_test("homework-done");
        let db = week.db.lock().unwrap();
        flexweek_store::insert_assignment(
            &db,
            week.user_id.unwrap(),
            "essay",
            r#"{"id":"essay","title":"Essay","due":"2026-10-14T21:00","estimate_min":60,"focus_minutes":0,"completed":false,"completed_at":"2026-10-01T08:00"}"#,
        )
        .unwrap();
        drop(db);
        save_week(
            &week,
            "2026-10-12",
            &json!([{"id":"essay-session","assignment_id":"essay","title":"Essay","kind":"flexible","days":[0],"start":"19:00","duration_min":60}]),
        );
        week.set_homework_done("essay".into(), true, "op-2".into())
            .unwrap();
        week.set_homework_done("essay".into(), true, "op-2".into())
            .unwrap();
        let db = week.db.lock().unwrap();
        let assignment: String = db
            .query_row("SELECT body FROM assignments WHERE id='essay'", [], |row| {
                row.get(0)
            })
            .unwrap();
        let assignment: Value = serde_json::from_str(&assignment).unwrap();
        let blocks: Value = serde_json::from_str(
            &flexweek_store::week_blocks(&db, week.user_id.unwrap(), "2026-10-12")
                .unwrap()
                .unwrap(),
        )
        .unwrap();
        drop(db);
        assert_eq!(assignment["completed"], true);
        assert_eq!(assignment["completed_at"], "2026-10-01T08:00");
        assert_eq!(blocks[0]["completed"], true);
        assert_eq!(blocks[0]["completed_day"], 0);
        assert_eq!(blocks[0]["start"], "19:00");
        week.set_homework_done("essay".into(), false, "op-3".into())
            .unwrap();
        let db = week.db.lock().unwrap();
        let assignment: String = db
            .query_row("SELECT body FROM assignments WHERE id='essay'", [], |row| {
                row.get(0)
            })
            .unwrap();
        let assignment: Value = serde_json::from_str(&assignment).unwrap();
        let blocks: Value = serde_json::from_str(
            &flexweek_store::week_blocks(&db, week.user_id.unwrap(), "2026-10-12")
                .unwrap()
                .unwrap(),
        )
        .unwrap();
        assert_eq!(assignment["completed"], false);
        assert!(assignment["completed_at"].is_null());
        assert_eq!(blocks[0]["completed"], false);
        assert!(blocks[0].get("completed_day").is_none());
        assert_eq!(blocks[0]["start"], "19:00");
    }

    /// The widget's Monday (picture 9 A): at 14:10 Algebra set 4 (2:30 to 4 PM, fixed) is next, then
    /// Spanish quiz prep (4 to 4:45 PM, homework) and Soccer practice (5 to 7 PM, fixed).
    fn monday_up_next(name: &str) -> Value {
        let (week, _path) = open_test(name);
        let db = week.db.lock().unwrap();
        flexweek_store::insert_assignment(
            &db,
            week.user_id.unwrap(),
            "spanish",
            r#"{"id":"spanish","title":"Spanish quiz prep","due":"2026-10-14T21:00","estimate_min":45,"focus_minutes":0,"completed":false,"category":"homework"}"#,
        )
        .unwrap();
        drop(db);
        save_week(
            &week,
            "2026-10-12",
            &json!([
                {"id":"algebra","title":"Algebra set 4","kind":"locked","days":[0],"start":"14:30","duration_min":90,"category":"school"},
                {"id":"spanish-session","assignment_id":"spanish","title":"Spanish quiz prep","kind":"flexible","days":[0],"start":"16:00","duration_min":45,"category":"study"},
                {"id":"soccer","title":"Soccer practice","kind":"locked","days":[0],"start":"17:00","duration_min":120,"category":"sports"}
            ]),
        );
        serde_json::from_str(&week.today("2026-10-12".into(), 14 * 60 + 10).unwrap()).unwrap()
    }

    /// The phone's Kotlin tests for the home-screen widget parse real output: this file is it. Run with
    /// FLEXWEEK_WRITE_PHONE_FIXTURES=1 to write it after a deliberate change; otherwise the output must
    /// equal the file, and the Android test copy must equal it byte for byte.
    #[test]
    fn phone_fixture_today_up_next_matches_the_output_and_the_android_copy() {
        let result = monday_up_next("up-next-fixture");
        // The values below are typed from picture 9 A, not copied from the output.
        assert_eq!(result["now"]["kind"], "up_next");
        assert_eq!(result["now"]["title"], "Algebra set 4");
        assert_eq!(result["now"]["minutes_left"], 20);
        assert_eq!(result["now"]["start"], "14:30");
        assert_eq!(result["now"]["end"], "16:00");
        let rows = result["rows"].as_array().unwrap();
        assert_eq!(rows.len(), 3, "the day has three rows: {rows:?}");
        let expected = [
            ("Algebra set 4", "14:30", "16:00", 90, false),
            ("Spanish quiz prep", "16:00", "16:45", 45, true),
            ("Soccer practice", "17:00", "19:00", 120, false),
        ];
        for (row, (title, start, end, minutes, homework)) in rows.iter().zip(expected) {
            assert_eq!(row["title"], title);
            assert_eq!(row["start"], start);
            assert_eq!(row["end"], end);
            assert_eq!(row["duration_min"], minutes);
            assert_eq!(row["homework"], homework);
            assert_eq!(row["done"], false);
            assert_eq!(row["past"], false);
        }
        let text = format!("{}\n", serde_json::to_string_pretty(&result).unwrap());
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let fixture = root.join("tests/fixtures/phone/today-up-next.json");
        let copy = root.join("../../android/app/src/test/resources/phone/today-up-next.json");
        if std::env::var("FLEXWEEK_WRITE_PHONE_FIXTURES").as_deref() == Ok("1") {
            for path in [&fixture, &copy] {
                std::fs::create_dir_all(path.parent().unwrap()).unwrap();
                std::fs::write(path, &text).unwrap();
            }
        }
        assert!(
            fixture.exists(),
            "the phone fixture today-up-next.json does not exist: write it with FLEXWEEK_WRITE_PHONE_FIXTURES=1"
        );
        let saved = std::fs::read_to_string(&fixture).unwrap();
        assert_eq!(
            saved, text,
            "the output changed: rewrite the phone fixture and check the Kotlin tests"
        );
        assert!(
            copy.exists(),
            "the Android copy of today-up-next.json does not exist"
        );
        let android = std::fs::read_to_string(&copy).unwrap();
        assert_eq!(
            android, saved,
            "the Android copy differs from the engine fixture"
        );
    }
}
