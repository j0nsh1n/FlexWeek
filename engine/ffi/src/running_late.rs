use chrono::{Datelike, Timelike};
use serde_json::{Value, json};

use crate::account::{availability, clock, load_open_week, work_windows};
use crate::core::{
    FfiError, FlexWeek, Preview, db_lock, engine_failure, failure, hex_preview, require_user,
};

const BUDGET_MS: f64 = flexweek_engine::solver::SOLVE_BUDGET_MS;

pub(crate) fn running_late(
    week: &FlexWeek,
    day: i64,
    minutes: i64,
    elapsed_ms: f64,
) -> Result<String, FfiError> {
    let user_id = require_user(week)?;
    if ![15, 30, 60].contains(&minutes) {
        return Err(failure("Choose 15, 30 or 60 minutes."));
    }
    if !(0..=6).contains(&day) {
        return Err(failure("day must be 0..6"));
    }
    let local = crate::core::parse_local(&week.host.local_now())?;
    let today = local.format("%Y-%m-%d").to_string();
    let week_start = flexweek_engine::time::monday_of(&today).map_err(engine_failure)?;
    let weekday = i64::from(local.weekday().num_days_from_monday());
    if weekday != day {
        return Err(failure("Open this week before using Running late."));
    }
    let clock_min = i64::from(local.time().hour()) * 60 + i64::from(local.time().minute());
    let from_start = flexweek_engine::desk::planning::late_from_start(clock_min);
    let from_min = flexweek_engine::time::hhmm_to_minutes(&from_start).map_err(engine_failure)?;
    let db = db_lock(week)?;
    let (keyed, tree, _) = crate::account::assignment_map(&db, user_id)?;
    let assignments = Value::Object(keyed);
    let (blocks, revision) = load_open_week(&db, user_id, &week_start, &assignments)?;
    if let Some(refusal) = flexweek_engine::desk::reuse::running_late_refusal(
        &week_start,
        &today,
        false,
        false,
        blocks.len() as i64,
    ) {
        return Err(failure(refusal));
    }
    let waiting: Vec<Value> = blocks
        .iter()
        .filter(|block| {
            block.get("kind").and_then(Value::as_str) == Some("flexible")
                && block.get("start").and_then(Value::as_str).is_none()
                && !block
                    .get("completed")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
        })
        .cloned()
        .collect();
    let timed: Vec<Value> = blocks
        .iter()
        .filter(|block| {
            block.get("kind").and_then(Value::as_str) != Some("flexible")
                || block.get("start").and_then(Value::as_str).is_some()
                || block
                    .get("completed")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
        })
        .cloned()
        .collect();
    let prepared =
        flexweek_engine::plan::prepare_solve(&timed, &week_start, &tree).map_err(engine_failure)?;
    let (solve_blocks, deadlines, slack) = prepared;
    let typed: Result<Vec<_>, _> = solve_blocks
        .iter()
        .map(flexweek_engine::solver::block_from_value)
        .collect();
    let typed = typed.map_err(engine_failure)?;
    let overrides = flexweek_engine::solver::overrides_from(
        Some(&crate::plan_week::deadline_json(&deadlines)),
        Some(&crate::plan_week::slack_json(&slack)),
    );
    let previous: Result<Vec<_>, _> = timed
        .iter()
        .filter(|block| block.get("start").and_then(Value::as_str).is_some())
        .map(flexweek_engine::solver::block_from_value)
        .collect();
    let previous = previous.map_err(engine_failure)?;
    let avail = availability(&db, user_id)?;
    let windows = work_windows(&avail.work)?;
    let elapsed = clock(week, elapsed_ms);
    let trace = flexweek_engine::solver::reschedule_running_late(
        &typed,
        day,
        minutes,
        &from_start,
        &previous,
        Some(&avail.occupancy),
        Some(&windows),
        Some(&overrides),
        Some((day, from_min)),
        BUDGET_MS,
        &elapsed,
    )
    .map_err(engine_failure)?;
    let trace_value = flexweek_engine::solver::trace_to_value(&trace);
    let late_id = format!(
        "b-late-{}",
        crate::account::hex_id(&week.host.random_bytes(8))
    );
    let late_block = flexweek_engine::desk::planning::running_late_block(
        &json!(day),
        &from_start,
        minutes,
        &json!(late_id),
    )
    .map_err(engine_failure)?;
    let with_late = {
        let mut blocks = timed.clone();
        blocks.push(late_block);
        blocks
    };
    let planned = flexweek_engine::desk::planning::apply_plan(
        &Value::Array(with_late),
        &trace_value,
        None,
        Some(&assignments),
        Some(week_start.as_str()),
    )
    .map_err(engine_failure)?;
    let mut settled = planned;
    settled.extend(waiting.clone());
    drop(db);
    let preview_id = hex_preview(&*week.host);
    week.previews.lock().map_err(failure)?.insert(
        preview_id.clone(),
        Preview {
            week_start: week_start.clone(),
            blocks: Value::Array(settled.clone()),
            earlier: Vec::new(),
            revision,
        },
    );
    let moved = trace_value
        .get("moves")
        .and_then(Value::as_array)
        .map(Vec::len)
        .unwrap_or(0);
    Ok(json!({
        "week_start": week_start,
        "placed": settled.iter().filter(|block| {
            block.get("start").and_then(Value::as_str).is_some()
        }).cloned().collect::<Vec<_>>(),
        "not_placed": waiting,
        "moves": trace_value.get("moves").cloned().unwrap_or(json!([])),
        "explanations": trace_value.get("explanations").cloned().unwrap_or(json!([])),
        "applied_preview": preview_id,
        "moved": moved,
    })
    .to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::tests_support::{open_at, save_week};
    use serde_json::json;

    #[test]
    fn running_late_moves_timed_blocks_and_leaves_waiting_homework() {
        let (week, _) = open_at("late", "2026-10-05T17:00:00");
        let db = week.db.lock().unwrap();
        flexweek_store::insert_assignment(
            &db,
            week.user_id.unwrap(),
            "essay",
            r#"{"id":"essay","title":"Essay","due":"2026-10-08T21:00","estimate_min":60,"focus_minutes":0,"completed":false}"#,
        )
        .unwrap();
        flexweek_store::insert_assignment(
            &db,
            week.user_id.unwrap(),
            "lab",
            r#"{"id":"lab","title":"Lab","due":"2026-10-08T21:00","estimate_min":60,"focus_minutes":0,"completed":false}"#,
        )
        .unwrap();
        drop(db);
        save_week(
            &week,
            "2026-10-05",
            &json!([
                {"id":"school","title":"School","kind":"locked","days":[0],"start":"08:00","duration_min":390,"category":"class"},
                {"id":"essay-session","title":"Essay","kind":"flexible","days":[0],"start":"16:00","duration_min":60,"assignment_id":"essay","category":"assignments"},
                {"id":"lab-session","title":"Lab","kind":"flexible","days":[0,1,2],"duration_min":60,"assignment_id":"lab","category":"assignments"}
            ]),
        );
        let result: Value = serde_json::from_str(&week.running_late(0, 30, 0.0).unwrap()).unwrap();
        let waiting: Vec<_> = result["not_placed"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|block| block.get("id").and_then(Value::as_str))
            .collect();
        assert_eq!(waiting, vec!["lab-session"]);
        assert!(
            result["placed"]
                .as_array()
                .unwrap()
                .iter()
                .any(|block| block["id"] == "essay-session" && block.get("start").is_some())
        );
        let preview = result["applied_preview"].as_str().unwrap();
        assert!(!preview.is_empty());
    }
}
