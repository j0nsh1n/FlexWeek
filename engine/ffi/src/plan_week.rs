use std::collections::{BTreeMap, HashSet};

use chrono::Timelike;
use serde_json::{Map, Value, json};

use crate::account::{
    availability, clock, empty_plan, load_open_week, remember, rollback, store_operation,
    stored_weeks, views_for_week, work_windows, write_week,
};
use crate::core::{
    FfiError, FlexWeek, Preview, db_lock, engine_failure, failure, hex_preview, require_user,
};

const WEEK_OVER: &str = "This week is over, so nothing was planned. Plan this week or a later one.";
const BUDGET_MS: f64 = flexweek_engine::solver::SOLVE_BUDGET_MS;

fn assignment_object(views: Map<String, Value>) -> Value {
    Value::Object(views)
}

fn as_map(value: &Value) -> Result<&Map<String, Value>, FfiError> {
    value
        .as_object()
        .ok_or_else(|| failure("assignments are not an object"))
}

pub(crate) fn deadline_json(map: &BTreeMap<String, Option<(i64, i64)>>) -> Value {
    let mut out = Map::new();
    for (id, point) in map {
        out.insert(
            id.clone(),
            match point {
                Some((day, minute)) => json!([day, minute]),
                None => Value::Null,
            },
        );
    }
    Value::Object(out)
}

pub(crate) fn slack_json(map: &BTreeMap<String, (i64, i64)>) -> Value {
    let mut out = Map::new();
    for (id, (day, minute)) in map {
        out.insert(id.clone(), json!([day, minute]));
    }
    Value::Object(out)
}

pub(crate) fn run_plan(
    week: &FlexWeek,
    week_start: &str,
    elapsed_ms: f64,
) -> Result<(Value, Vec<Value>, Vec<Value>, Value), FfiError> {
    let user_id = require_user(week)?;
    let local = crate::core::parse_local(&week.host.local_now())?;
    let today = local.format("%Y-%m-%d").to_string();
    let start = flexweek_engine::desk::planning::plan_start_at(
        week_start,
        &today,
        i64::from(local.time().hour()),
        i64::from(local.time().minute()),
        i64::from(local.time().second()),
        i64::from(local.time().nanosecond() / 1000),
    )
    .map_err(engine_failure)?;
    if start.is_some_and(|(day, _)| day > 6) {
        return Ok((
            empty_plan(week_start, WEEK_OVER),
            Vec::new(),
            Vec::new(),
            json!([]),
        ));
    }
    let db = db_lock(week)?;
    let (keyed, tree, rows) = crate::account::assignment_map(&db, user_id)?;
    let weeks = stored_weeks(&db, user_id)?;
    let views = views_for_week(&keyed, &rows, &weeks, week_start)?;
    let assignments = assignment_object(views);
    let (blocks, _revision) = load_open_week(&db, user_id, week_start, &assignments)?;
    let earlier: Vec<Value> = weeks
        .iter()
        .filter(|(start, _, _)| start.as_str() < week_start)
        .map(|(start, blocks, week_revision)| {
            json!({
                "week_start": start,
                "blocks": blocks,
                "revision": week_revision,
            })
        })
        .collect();
    let moved = flexweek_engine::desk::planning::move_earlier_homework(
        &blocks,
        &earlier,
        as_map(&assignments)?,
        week_start,
    )
    .map_err(engine_failure)?;
    let planning_blocks = moved
        .get("blocks")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or(blocks);
    let moved_blocks = moved
        .get("moved")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let earlier_updates = moved
        .get("weeks")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let earlier_blocks: Vec<Value> = earlier
        .iter()
        .flat_map(|week| week.get("blocks").and_then(Value::as_array).cloned())
        .flatten()
        .filter(|block| {
            block.get("start").and_then(Value::as_str).is_some()
                && !block
                    .get("completed")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
        })
        .collect();
    let open_blocks = flexweek_engine::desk::planning::open_rest_sessions(
        &planning_blocks,
        as_map(&assignments)?,
        week_start,
        &earlier_blocks,
    )
    .map_err(engine_failure)?;
    let not_before = start.map(|(day, minute)| json!([day, minute]));
    let (payload, targets) = flexweek_engine::desk::planning::solve_request(
        &Value::Array(open_blocks.clone()),
        &assignments,
        week_start,
        false,
        None,
        not_before.as_ref(),
        false,
    )
    .map_err(engine_failure)?;
    let first_day = start.map(|(day, _)| day).unwrap_or(0);
    let first_minute = start.map(|(_, minute)| minute).unwrap_or(0);
    let committed: Vec<Value> = open_blocks
        .iter()
        .filter(|block| block.get("start").and_then(Value::as_str).is_some())
        .cloned()
        .chain(moved_blocks.iter().cloned())
        .collect();
    let avail = availability(&db, user_id)?;
    let work = avail.work.as_array().cloned().unwrap_or_default();
    let target_ids: Vec<String> = targets
        .iter()
        .filter_map(Value::as_str)
        .map(str::to_string)
        .collect();
    let (week_blocks, shares) = flexweek_engine::desk::planning::fair_share(
        &open_blocks,
        as_map(&assignments)?,
        &Value::Array(committed),
        week_start,
        first_day,
        first_minute,
        &work,
        &target_ids,
    )
    .map_err(engine_failure)?;
    let (payload, targets) = if shares.is_empty() {
        (payload, targets)
    } else {
        let kept: HashSet<String> = week_blocks
            .iter()
            .filter_map(|block| block.get("id").and_then(Value::as_str).map(str::to_string))
            .collect();
        let only: Vec<Value> = target_ids
            .iter()
            .filter(|id| kept.contains(*id))
            .map(|id| Value::String(id.clone()))
            .collect();
        flexweek_engine::desk::planning::solve_request(
            &Value::Array(week_blocks.clone()),
            &assignments,
            week_start,
            false,
            Some(&Value::Array(only)),
            not_before.as_ref(),
            false,
        )
        .map_err(engine_failure)?
    };
    if targets.is_empty() {
        return Ok((
            empty_plan(week_start, ""),
            Vec::new(),
            earlier_updates,
            Value::Array(week_blocks),
        ));
    }
    let prepared = flexweek_engine::plan::prepare_solve(&payload, week_start, &tree)
        .map_err(engine_failure)?;
    let (solve_blocks, deadlines, slack) = prepared;
    let typed: Result<Vec<_>, _> = solve_blocks
        .iter()
        .map(flexweek_engine::solver::block_from_value)
        .collect();
    let typed = typed.map_err(engine_failure)?;
    let windows = work_windows(&avail.work)?;
    let overrides = flexweek_engine::solver::overrides_from(
        Some(&deadline_json(&deadlines)),
        Some(&slack_json(&slack)),
    );
    let elapsed = clock(week, elapsed_ms);
    let trace = flexweek_engine::solver::solve(
        &typed,
        Some(&avail.occupancy),
        Some(&windows),
        Some(&overrides),
        start,
        BUDGET_MS,
        &elapsed,
    )
    .map_err(engine_failure)?;
    let trace_value = flexweek_engine::solver::trace_to_value(&trace);
    let planned = flexweek_engine::desk::planning::apply_plan(
        &Value::Array(week_blocks),
        &trace_value,
        Some(&Value::Array(targets.clone())),
        Some(&assignments),
        Some(week_start),
    )
    .map_err(engine_failure)?;
    let (settled, _) = flexweek_engine::desk::planning::settle_placements(
        &Value::Array(planned),
        &assignments,
        week_start,
        &Value::Array(vec![]),
        false,
    )
    .map_err(engine_failure)?;
    drop(db);
    let target_set: HashSet<&str> = targets.iter().filter_map(Value::as_str).collect();
    let placed: Vec<Value> = settled
        .as_array()
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|block| {
            let id = block.get("id").and_then(Value::as_str).unwrap_or("");
            target_set.contains(id) && block.get("start").and_then(Value::as_str).is_some()
        })
        .collect();
    let mut not_placed: Vec<Value> = settled
        .as_array()
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|block| {
            let id = block.get("id").and_then(Value::as_str).unwrap_or("");
            target_set.contains(id) && block.get("start").and_then(Value::as_str).is_none()
        })
        .collect();
    for block in &mut not_placed {
        let id = block.get("id").and_then(Value::as_str).unwrap_or("");
        if let Some(explanation) = trace_value["explanations"]
            .as_array()
            .into_iter()
            .flatten()
            .find(|item| item["block_id"].as_str() == Some(id))
            && let Some(reason) = explanation.get("reason").and_then(Value::as_str)
        {
            block["reason"] = json!(reason);
            block["why"] = json!(flexweek_engine::plan::sentence(reason).map_err(engine_failure)?);
        }
    }
    let result = json!({
        "week_start": week_start,
        "placed": placed,
        "not_placed": not_placed,
        "moves": trace_value.get("moves").cloned().unwrap_or(json!([])),
        "explanations": trace_value.get("explanations").cloned().unwrap_or(json!([])),
        "shares": shares,
        "complete": trace_value.get("complete").cloned().unwrap_or(json!(false)),
    });
    Ok((result, earlier_updates, vec![], settled))
}

pub(crate) fn plan_week(
    week: &FlexWeek,
    week_start: &str,
    elapsed_ms: f64,
) -> Result<String, FfiError> {
    require_user(week)?;
    flexweek_engine::time::monday_of(week_start).map_err(engine_failure)?;
    if week_start != flexweek_engine::time::monday_of(week_start).map_err(engine_failure)? {
        return Err(failure("week_start must be a Monday"));
    }
    let (mut result, earlier, _, settled) = run_plan(week, week_start, elapsed_ms)?;
    if result.get("applied_preview").and_then(Value::as_str) == Some("")
        && result
            .get("placed")
            .and_then(Value::as_array)
            .is_some_and(Vec::is_empty)
    {
        return Ok(result.to_string());
    }
    let preview_id = hex_preview(&*week.host);
    result["applied_preview"] = json!(preview_id);
    let user_id = require_user(week)?;
    let db = db_lock(week)?;
    let revision = flexweek_store::read_week(&db, user_id, week_start)
        .map_err(failure)?
        .map(|(_, revision)| revision)
        .unwrap_or(0);
    drop(db);
    week.previews.lock().map_err(failure)?.insert(
        preview_id,
        Preview {
            week_start: week_start.to_string(),
            blocks: settled,
            earlier,
            revision,
            placed_ids: result["placed"]
                .as_array()
                .into_iter()
                .flatten()
                .filter_map(|block| block.get("id").and_then(Value::as_str).map(str::to_string))
                .collect(),
        },
    );
    Ok(result.to_string())
}

pub(crate) fn accept_plan(week: &FlexWeek, preview_id: &str) -> Result<String, FfiError> {
    let user_id = require_user(week)?;
    if preview_id.is_empty() {
        return Err(failure("preview was not found"));
    }
    let preview = week
        .previews
        .lock()
        .map_err(failure)?
        .remove(preview_id)
        .ok_or_else(|| failure("preview was not found"))?;
    let payload = json!(["accept_plan", preview_id, preview.week_start]).to_string();
    let db = db_lock(week)?;
    let placed_ids = preview.placed_ids.clone();
    if remember(&db, user_id, preview_id, &payload)? {
        return Ok(
            json!({"accepted": true, "week_start": preview.week_start, "placed_ids": placed_ids})
                .to_string(),
        );
    }
    write_week(
        &db,
        user_id,
        &preview.week_start,
        &preview.blocks,
        preview.revision,
    )?;
    for update in &preview.earlier {
        let Some(week_start) = update.get("week_start").and_then(Value::as_str) else {
            continue;
        };
        let revision = update.get("revision").and_then(Value::as_i64).unwrap_or(0);
        let after = update.get("after").cloned().unwrap_or(json!([]));
        write_week(&db, user_id, week_start, &after, revision)?;
    }
    if let Err(error) = store_operation(&db, user_id, preview_id, &payload) {
        rollback(&db);
        return Err(error);
    }
    db.execute_batch("COMMIT").map_err(failure)?;
    drop(db);
    week.host.data_changed("week".into());
    Ok(
        json!({"accepted": true, "week_start": preview.week_start, "placed_ids": placed_ids})
            .to_string(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::tests_support::{open_at, save_week};
    use serde_json::json;
    use std::fs;

    fn load_case(name: &str) -> Value {
        let path = format!("{}/tests/fixtures/{name}.json", env!("CARGO_MANIFEST_DIR"));
        serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap()
    }

    fn seed(week: &FlexWeek, case: &Value) {
        let db = week.db.lock().unwrap();
        let user = week.user_id.unwrap();
        for (id, body) in case["assignments"].as_object().unwrap() {
            flexweek_store::insert_assignment(&db, user, id, &body.to_string()).unwrap();
        }
        drop(db);
        save_week(week, case["week_start"].as_str().unwrap(), &case["blocks"]);
    }

    fn placed_rows(result: &Value) -> Vec<Value> {
        result["placed"]
            .as_array()
            .unwrap()
            .iter()
            .map(|block| {
                json!({
                    "id": block["id"],
                    "assignment_id": block.get("assignment_id"),
                    "start": block.get("start"),
                    "days": block.get("days"),
                    "duration_min": block.get("duration_min"),
                })
            })
            .collect()
    }

    fn assert_golden(name: &str) {
        let case = load_case(name);
        let (week, _) = open_at(name, case["now"].as_str().unwrap());
        seed(&week, &case);
        let result: Value = serde_json::from_str(
            &week
                .plan_week(case["week_start"].as_str().unwrap().into(), 0.0)
                .unwrap(),
        )
        .unwrap();
        assert_eq!(
            Value::Array(placed_rows(&result)),
            case["expected"]["placed"]
        );
        assert_eq!(
            result["not_placed"].as_array().unwrap().len(),
            case["expected"]["not_placed"].as_array().unwrap().len()
        );
    }

    #[test]
    fn plan_week_matches_open_thursday_golden() {
        assert_golden("open-thursday");
    }

    #[test]
    fn plan_week_matches_tight_tuesday_golden() {
        assert_golden("tight-tuesday");
    }

    #[test]
    fn plan_week_matches_later_fair_share_golden() {
        assert_golden("later-fair-share");
    }

    #[test]
    fn accept_plan_writes_the_previewed_starts() {
        let case = load_case("open-thursday");
        let (week, _) = open_at("accept-plan", case["now"].as_str().unwrap());
        seed(&week, &case);
        let result: Value =
            serde_json::from_str(&week.plan_week("2026-10-05".into(), 0.0).unwrap()).unwrap();
        let preview = result["applied_preview"].as_str().unwrap().to_string();
        let accepted: Value = serde_json::from_str(&week.accept_plan(preview).unwrap()).unwrap();
        assert_eq!(accepted["placed_ids"], json!(["essay-session"]));
        let db = week.db.lock().unwrap();
        let raw = flexweek_store::week_blocks(&db, week.user_id.unwrap(), "2026-10-05")
            .unwrap()
            .unwrap();
        let blocks: Value = serde_json::from_str(&raw).unwrap();
        let essay = blocks
            .as_array()
            .unwrap()
            .iter()
            .find(|block| block["id"] == "essay-session")
            .unwrap();
        assert_eq!(essay["start"], "16:00");
        assert_eq!(essay["days"], json!([0]));
    }

    #[test]
    fn plan_placed_rows_name_one_day_and_a_start() {
        let case = load_case("open-thursday");
        let (week, _) = open_at("plan-shape", case["now"].as_str().unwrap());
        seed(&week, &case);
        let result: Value = serde_json::from_str(
            &week
                .plan_week(case["week_start"].as_str().unwrap().into(), 0.0)
                .unwrap(),
        )
        .unwrap();
        let row = &result["placed"][0];
        assert_eq!(row["days"], json!([0]));
        assert_eq!(row["start"], "16:00");
    }

    #[test]
    fn plan_not_placed_rows_carry_why() {
        let case = load_case("tight-tuesday");
        let (week, _) = open_at("plan-why", case["now"].as_str().unwrap());
        seed(&week, &case);
        let result: Value = serde_json::from_str(
            &week
                .plan_week(case["week_start"].as_str().unwrap().into(), 0.0)
                .unwrap(),
        )
        .unwrap();
        for row in result["not_placed"].as_array().unwrap() {
            let reason = row["reason"].as_str().expect("reason code is present");
            assert_eq!(row["why"], flexweek_engine::plan::sentence(reason).unwrap());
        }
    }

    #[test]
    fn phone_fixture_plan_matches_open_thursday_and_android_copy() {
        let case = load_case("open-thursday");
        let (week, _) = open_at("plan-fixture", case["now"].as_str().unwrap());
        seed(&week, &case);
        let mut result: Value = serde_json::from_str(
            &week
                .plan_week(case["week_start"].as_str().unwrap().into(), 0.0)
                .unwrap(),
        )
        .unwrap();
        result["applied_preview"] = json!("preview-id");
        let text = format!("{}\n", serde_json::to_string_pretty(&result).unwrap());
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let fixture = root.join("tests/fixtures/phone/plan-open-thursday.json");
        let copy = root.join("../../android/app/src/test/resources/phone/plan-open-thursday.json");
        if std::env::var("FLEXWEEK_WRITE_PHONE_FIXTURES").as_deref() == Ok("1") {
            for path in [&fixture, &copy] {
                std::fs::create_dir_all(path.parent().unwrap()).unwrap();
                std::fs::write(path, &text).unwrap();
            }
        }
        assert_eq!(std::fs::read_to_string(&fixture).unwrap(), text);
        assert_eq!(std::fs::read_to_string(&copy).unwrap(), text);
        assert_eq!(result["placed"][0]["start"], "16:00");
        assert_eq!(result["placed"][0]["days"], json!([0]));
    }

    #[test]
    fn phone_fixture_not_placed_plan_matches_android_copy() {
        let (week, _) = open_at("plan-not-placed-fixture", "2026-10-05T08:00:00");
        let db = week.db.lock().unwrap();
        flexweek_store::insert_assignment(
            &db,
            week.user_id.unwrap(),
            "essay",
            r#"{"id":"essay","title":"History essay","due":"2026-10-08T21:00","estimate_min":60,"focus_minutes":0,"completed":false}"#,
        ).unwrap();
        drop(db);
        save_week(
            &week,
            "2026-10-05",
            &json!([
                {"id":"school","title":"School","kind":"locked","days":[0],"start":"00:00","duration_min":1440,"category":"class"},
                {"id":"essay-session","title":"History essay","kind":"flexible","days":[0],"duration_min":60,"assignment_id":"essay","priority":3,"energy":"medium","category":"assignments"}
            ]),
        );
        let mut result: Value =
            serde_json::from_str(&week.plan_week("2026-10-05".into(), 0.0).unwrap()).unwrap();
        result["applied_preview"] = json!("preview-id");
        let text = format!("{}\n", serde_json::to_string_pretty(&result).unwrap());
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let fixture = root.join("tests/fixtures/phone/plan-not-placed.json");
        let copy = root.join("../../android/app/src/test/resources/phone/plan-not-placed.json");
        if std::env::var("FLEXWEEK_WRITE_PHONE_FIXTURES").as_deref() == Ok("1") {
            for path in [&fixture, &copy] {
                std::fs::create_dir_all(path.parent().unwrap()).unwrap();
                std::fs::write(path, &text).unwrap();
            }
        }
        assert_eq!(std::fs::read_to_string(&fixture).unwrap(), text);
        assert_eq!(std::fs::read_to_string(&copy).unwrap(), text);
        let row = &result["not_placed"][0];
        assert!(row["reason"].is_string());
        assert!(row["why"].is_string());
    }
}
