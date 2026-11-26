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

const WEEK_OVER: &str = "That week is over. Open this week or a later one, then plan again.";
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

pub(crate) fn plan_rules(
    db: &rusqlite::Connection,
    user_id: i64,
) -> Result<flexweek_engine::solver::PlanRules, FfiError> {
    let raw = flexweek_store::preference_row(db, user_id)
        .map_err(failure)?
        .unwrap_or_else(|| "{}".to_string());
    let prefs: Value = serde_json::from_str(&raw).map_err(failure)?;
    Ok(flexweek_engine::solver::plan_rules_from_value(&prefs))
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
    let now_point = flexweek_engine::desk::planning::clock_point(
        week_start,
        &today,
        i64::from(local.time().hour()),
        i64::from(local.time().minute()),
    )
    .map_err(engine_failure)?
    .map(|(day, minute)| json!([day, minute]));
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
    let now = (
        local.date_naive(),
        i64::from(local.time().hour()) * 60 + i64::from(local.time().minute()),
    );
    let views = views_for_week(&keyed, &rows, &weeks, week_start, Some(now))?;
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
        .unwrap_or_else(|| blocks.clone());
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
    // The homework's numbers were read with the week as saved (`blocks`), waiting sessions included.
    let open_blocks = flexweek_engine::desk::planning::open_rest_sessions_at(
        &planning_blocks,
        as_map(&assignments)?,
        week_start,
        &earlier_blocks,
        &blocks,
        now_point.as_ref(),
    )
    .map_err(engine_failure)?;
    let not_before = start.map(|(day, minute)| json!([day, minute]));
    let (payload, targets) = flexweek_engine::desk::planning::solve_request_at(
        &Value::Array(open_blocks.clone()),
        &assignments,
        week_start,
        false,
        None,
        not_before.as_ref(),
        false,
        now_point.as_ref(),
        &blocks,
    )
    .map_err(engine_failure)?;
    let first_day = start.map(|(day, _)| day).unwrap_or(0);
    let first_minute = start.map(|(_, minute)| minute).unwrap_or(0);
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
        &Value::Array(blocks.clone()),
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
        flexweek_engine::desk::planning::solve_request_at(
            &Value::Array(week_blocks.clone()),
            &assignments,
            week_start,
            false,
            Some(&Value::Array(only)),
            not_before.as_ref(),
            false,
            now_point.as_ref(),
            &blocks,
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
    let rules = plan_rules(&db, user_id)?;
    let trace = flexweek_engine::solver::solve_with_rules(
        &typed,
        Some(&avail.occupancy),
        Some(&windows),
        Some(&overrides),
        start,
        BUDGET_MS,
        &elapsed,
        rules,
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
    let settled_blocks = settled.as_array().cloned().unwrap_or_default();
    let placed: Vec<Value> = settled_blocks
        .iter()
        .filter(|block| {
            let id = block.get("id").and_then(Value::as_str).unwrap_or("");
            reports_planned(id, &target_set) && block.get("start").and_then(Value::as_str).is_some()
        })
        .cloned()
        .map(|block| with_parent_title(block, &settled_blocks))
        .collect();
    let mut not_placed: Vec<Value> = settled_blocks
        .iter()
        .filter(|block| {
            let id = block.get("id").and_then(Value::as_str).unwrap_or("");
            reports_planned(id, &target_set) && block.get("start").and_then(Value::as_str).is_none()
        })
        .cloned()
        .map(|block| with_parent_title(block, &settled_blocks))
        .collect();
    for block in &mut not_placed {
        let id = block.get("id").and_then(Value::as_str).unwrap_or("");
        if let Some(explanation) = trace_value["explanations"]
            .as_array()
            .into_iter()
            .flatten()
            .find(|item| item["block_id"].as_str() == Some(id))
            && let Some(reason) = explanation.get("reason").and_then(Value::as_str)
            // A code with no words (a new one, or a placed block's note) must not fail the whole plan.
            && let Ok(why) = flexweek_engine::plan::sentence(reason)
        {
            block["reason"] = json!(reason);
            block["why"] = json!(why);
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

fn split_parent_id(id: &str) -> Option<&str> {
    let parent = id.strip_suffix("~2")?;
    if parent.is_empty() {
        None
    } else {
        Some(parent)
    }
}

fn reports_planned(id: &str, targets: &HashSet<&str>) -> bool {
    targets.contains(id) || split_parent_id(id).is_some_and(|parent| targets.contains(parent))
}

fn with_parent_title(mut block: Value, settled: &[Value]) -> Value {
    let Some(id) = block.get("id").and_then(Value::as_str) else {
        return block;
    };
    let Some(parent_id) = split_parent_id(id) else {
        return block;
    };
    let Some(title) = settled
        .iter()
        .find(|item| item.get("id").and_then(Value::as_str) == Some(parent_id))
        .and_then(|parent| parent.get("title"))
        .cloned()
    else {
        return block;
    };
    if let Some(object) = block.as_object_mut() {
        object.insert("title".into(), title);
    }
    block
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
        return Err(failure("That plan preview is gone. Plan again."));
    }
    let preview = week
        .previews
        .lock()
        .map_err(failure)?
        .remove(preview_id)
        .ok_or_else(|| failure("That plan preview is gone. Plan again."))?;
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
    week.local_change("week");
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
    fn a_saved_waiting_session_gets_its_share_without_a_stored_unplanned_number() {
        // The later-fair-share case as a save really stores it: no `unplanned_min` in the homework, which the
        // store counts from the saved weeks (planned 180: the waiting session here). This week's part is
        // 180 less 0 held in later weeks; the session being planned holds none of it yet. On Saturday 10:00,
        // Sat and Sun are 2 of the 12 plannable days to Wed 21, so it gets 180 x 2 / 12 = 30, as the golden.
        let mut case = load_case("later-fair-share");
        case["assignments"]["poster"]
            .as_object_mut()
            .unwrap()
            .shift_remove("unplanned_min");
        let (week, _) = open_at("later-fair-share-real", case["now"].as_str().unwrap());
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
        assert_eq!(result["shares"], case["expected"]["shares"]);
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

    /// A 60 minute essay due Friday 21:00 with one session on Monday 09:00 of the week of 5 October, for a
    /// plan on Wednesday 7 October 12:00 (`pinned`: a session the student shaped by hand).
    fn plan_with_a_session_from_monday(name: &str, pinned: bool) -> Value {
        let (week, _) = open_at(name, "2026-10-07T12:00:00");
        {
            let db = week.db.lock().unwrap();
            flexweek_store::insert_assignment(
                &db,
                week.user_id.unwrap(),
                "essay",
                r#"{"id":"essay","title":"History essay","due":"2026-10-09T21:00","estimate_min":60,"focus_minutes":0,"completed":false,"priority":3,"energy":"medium","spread":"one"}"#,
            )
            .unwrap();
        }
        let mut session = json!({"id":"essay-session","title":"History essay","kind":"flexible","days":[0],"start":"09:00","duration_min":60,"assignment_id":"essay","priority":3,"energy":"medium","category":"assignments"});
        if pinned {
            session["pinned"] = json!(true);
        }
        save_week(&week, "2026-10-05", &json!([session]));
        serde_json::from_str(&week.plan_week("2026-10-05".into(), 0.0).unwrap()).unwrap()
    }

    #[test]
    fn plan_moves_a_session_that_passed_unfinished_to_a_time_still_ahead() {
        let result = plan_with_a_session_from_monday("plan-moves-passed", false);
        let rows = placed_rows(&result);
        assert_eq!(rows.len(), 1, "got {result}");
        let day = rows[0]["days"][0].as_i64().unwrap();
        let start =
            flexweek_engine::time::hhmm_to_minutes(rows[0]["start"].as_str().unwrap()).unwrap();
        assert!((day, start) >= (2, 12 * 60), "not before now, got {rows:?}");
        assert!(day <= 4, "before it is due, got {rows:?}");
    }

    #[test]
    fn plan_keeps_a_pinned_session_that_passed() {
        let result = plan_with_a_session_from_monday("plan-keeps-pinned-passed", true);
        // The pinned session is not moved, so it is not among the placed rows; its 60 minutes are still
        // needed, so the plan places a new session for them at a time still ahead.
        let rows = placed_rows(&result);
        assert_eq!(rows.len(), 1, "got {result}");
        assert_ne!(rows[0]["id"], "essay-session", "got {result}");
        let day = rows[0]["days"][0].as_i64().unwrap();
        let start =
            flexweek_engine::time::hhmm_to_minutes(rows[0]["start"].as_str().unwrap()).unwrap();
        assert!((day, start) >= (2, 12 * 60), "not before now, got {rows:?}");
    }

    /// Monday is all fixed (School 00:00 for 24 h) and the History essay may only go on Monday, so Plan
    /// cannot place it.
    fn full_monday(name: &str) -> Value {
        let (week, _) = open_at(name, "2026-10-05T08:00:00");
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
        serde_json::from_str(&week.plan_week("2026-10-05".into(), 0.0).unwrap()).unwrap()
    }

    #[test]
    fn plan_not_placed_rows_carry_why() {
        let result = full_monday("plan-why");
        let rows = result["not_placed"].as_array().unwrap();
        assert!(
            !rows.is_empty(),
            "a full Monday leaves the essay with no time"
        );
        for row in rows {
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
        let mut result = full_monday("plan-not-placed-fixture");
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

    fn plan_split(name: &str, window_end: &str) -> (std::sync::Arc<FlexWeek>, Value) {
        let (week, _) = open_at(name, "2026-10-05T08:00:00");
        let db = week.db.lock().unwrap();
        let availability =
            format!(r#"{{"work_windows":[{{"days":[0],"start":"16:00","end":"{window_end}"}}]}}"#);
        db.execute(
            "UPDATE preferences SET split_long_tasks=1, availability_json=?1 WHERE user_id=?2",
            (availability, week.user_id.unwrap()),
        )
        .unwrap();
        drop(db);
        save_week(
            &week,
            "2026-10-05",
            &json!([{
                "id": "essay",
                "title": "English essay",
                "kind": "flexible",
                "days": [0],
                "duration_min": 120,
                "priority": 3,
                "energy": "medium"
            }]),
        );
        let result: Value =
            serde_json::from_str(&week.plan_week("2026-10-05".into(), 0.0).unwrap()).unwrap();
        (week, result)
    }

    fn titles(rows: &[Value]) -> Vec<&str> {
        rows.iter()
            .map(|row| row["title"].as_str().unwrap_or(""))
            .collect()
    }

    #[test]
    fn a_split_with_one_free_hour_reports_the_waiting_half() {
        // Monday 16:00–17:00 holds one hour of a 120-minute essay. The review shows the
        // placed hour and the hour still waiting, both under the essay's title. Accept
        // keeps that waiting hour.
        let (week, result) = plan_split("split-one-hour", "17:00");
        let placed = result["placed"].as_array().unwrap();
        let waiting = result["not_placed"].as_array().unwrap();
        assert_eq!(
            (
                placed
                    .iter()
                    .map(|row| row["id"].as_str().unwrap())
                    .collect::<Vec<_>>(),
                waiting
                    .iter()
                    .map(|row| row["id"].as_str().unwrap())
                    .collect::<Vec<_>>(),
            ),
            (vec!["essay"], vec!["essay~2"]),
            "placed {placed:?} waiting {waiting:?}"
        );
        assert_eq!(placed[0]["duration_min"], 60);
        assert_eq!(placed[0]["start"], "16:00");
        assert!(waiting[0].get("start").is_none());
        assert_eq!(waiting[0]["duration_min"], 60);
        assert_eq!(titles(placed), vec!["English essay"]);
        assert_eq!(titles(waiting), vec!["English essay"]);
        let preview = result["applied_preview"].as_str().unwrap().to_string();
        week.accept_plan(preview).unwrap();
        let db = week.db.lock().unwrap();
        let raw = flexweek_store::week_blocks(&db, week.user_id.unwrap(), "2026-10-05")
            .unwrap()
            .unwrap();
        let blocks: Value = serde_json::from_str(&raw).unwrap();
        let half = blocks
            .as_array()
            .unwrap()
            .iter()
            .find(|block| block["id"] == "essay~2")
            .unwrap();
        assert_eq!(half["title"], "English essay");
        assert_eq!(half["duration_min"], 60);
        assert!(half.get("start").is_none());
    }

    #[test]
    fn a_split_that_fits_reports_both_halves() {
        // Monday 16:00–18:15 holds both hours and the default 15-minute gap between them.
        // The preview and the accepted ids name each half, under the essay's title.
        let (week, result) = plan_split("split-both-hours", "18:15");
        let placed = result["placed"].as_array().unwrap();
        let mut ids: Vec<&str> = placed
            .iter()
            .map(|row| row["id"].as_str().unwrap())
            .collect();
        ids.sort_unstable();
        assert_eq!(ids, vec!["essay", "essay~2"], "placed {placed:?}");
        assert!(result["not_placed"].as_array().unwrap().is_empty());
        assert_eq!(titles(placed), vec!["English essay", "English essay"]);
        for row in placed {
            assert_eq!(row["duration_min"], 60);
        }
        let preview = result["applied_preview"].as_str().unwrap().to_string();
        let accepted: Value = serde_json::from_str(&week.accept_plan(preview).unwrap()).unwrap();
        let mut accepted_ids = accepted["placed_ids"].as_array().unwrap().clone();
        accepted_ids.sort_by_key(|id| id.as_str().unwrap().to_string());
        assert_eq!(accepted_ids, vec![json!("essay"), json!("essay~2")]);
    }
}
