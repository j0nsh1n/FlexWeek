use chrono::{Datelike, Timelike};
use serde_json::{Value, json};

use crate::account::{availability, clock, load_open_week, work_windows};
use crate::core::{
    FfiError, FlexWeek, Preview, db_lock, engine_failure, failure, hex_preview, require_user,
};

const BUDGET_MS: f64 = flexweek_engine::solver::SOLVE_BUDGET_MS;
const LATE_STEP_MIN: i64 = 5;
const LATE_MAX_MIN: i64 = 60;

pub(crate) fn running_late(
    week: &FlexWeek,
    day: i64,
    minutes: i64,
    elapsed_ms: f64,
) -> Result<String, FfiError> {
    let user_id = require_user(week)?;
    if !(LATE_STEP_MIN..=LATE_MAX_MIN).contains(&minutes) || minutes % LATE_STEP_MIN != 0 {
        return Err(failure("Choose 5 to 60 minutes, in steps of 5."));
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
            placed_ids: Vec::new(),
        },
    );
    let moves = phone_moves(&trace_value, &settled, &assignments);
    let moved = moves.len();
    Ok(json!({
        "week_start": week_start,
        "placed": settled.iter().filter(|block| {
            block.get("start").and_then(Value::as_str).is_some()
        }).cloned().collect::<Vec<_>>(),
        "not_placed": waiting,
        "moves": moves,
        "explanations": trace_value.get("explanations").cloned().unwrap_or(json!([])),
        "applied_preview": preview_id,
        "moved": moved,
    })
    .to_string())
}

/// The moves the phone lists: work with a time at both ends (a "move" with no time at one end is the
/// solver recording that something stayed unplaced), each with its block's title and why in words.
/// Running late files its moves under the missed-day code with an explanation of its own, so the code's
/// sentence alone would tell a student who ran late that they had missed a day; the desktop reads the
/// explanation first for the same reason.
fn phone_moves(trace: &Value, blocks: &[Value], assignments: &Value) -> Vec<Value> {
    let explanations = trace
        .get("explanations")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let title_of = |id: &str| -> String {
        let block = blocks
            .iter()
            .find(|block| block.get("id").and_then(Value::as_str) == Some(id));
        block
            .and_then(|block| block.get("title").and_then(Value::as_str))
            .filter(|title| !title.is_empty())
            .map(str::to_string)
            .or_else(|| {
                let assignment = block?.get("assignment_id")?.as_str()?;
                assignments
                    .get(assignment)?
                    .get("title")?
                    .as_str()
                    .map(str::to_string)
            })
            .unwrap_or_else(|| "Homework".to_string())
    };
    trace
        .get("moves")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter(|item| item.get("from_start").and_then(Value::as_str).is_some())
        .filter(|item| item.get("to_start").and_then(Value::as_str).is_some())
        .map(|item| {
            let id = item.get("block_id").and_then(Value::as_str).unwrap_or("");
            let reason = item.get("reason").and_then(Value::as_str).unwrap_or("");
            let why = explanations
                .iter()
                .find(|told| {
                    told.get("block_id").and_then(Value::as_str) == Some(id)
                        && told.get("reason").and_then(Value::as_str) == Some(reason)
                })
                .and_then(|told| told.get("message").and_then(Value::as_str))
                .filter(|message| !message.is_empty())
                .map(str::to_string)
                .or_else(|| flexweek_engine::plan::sentence(reason).ok())
                .unwrap_or_default();
            let mut shown = item.clone();
            shown["title"] = json!(title_of(id));
            shown["why"] = json!(why);
            shown
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::tests_support::{open_at, save_week};
    use serde_json::json;

    /// Monday 16:05 (the 15-minute cutoff is 16:00): School is fixed until 14:30, Soccer is fixed at
    /// 17:30, and the Essay session sits at 16:00. Thirty minutes late puts the late block at
    /// 16:00-16:30, so the Essay has to move.
    fn late_monday(name: &str) -> Value {
        let (week, _) = open_at(name, "2026-10-05T16:05:00");
        let db = week.db.lock().unwrap();
        flexweek_store::insert_assignment(
            &db,
            week.user_id.unwrap(),
            "essay",
            r#"{"id":"essay","title":"History essay","due":"2026-10-08T21:00","estimate_min":60,"focus_minutes":0,"completed":false}"#,
        )
        .unwrap();
        drop(db);
        save_week(
            &week,
            "2026-10-05",
            &json!([
                {"id":"school","title":"School","kind":"locked","days":[0],"start":"08:00","duration_min":390,"category":"class"},
                {"id":"soccer","title":"Soccer","kind":"locked","days":[0],"start":"17:30","duration_min":60,"category":"extra"},
                {"id":"essay-session","title":"History essay","kind":"flexible","days":[0],"start":"16:00","duration_min":60,"assignment_id":"essay","category":"assignments"}
            ]),
        );
        serde_json::from_str(&week.running_late(0, 30, 0.0).unwrap()).unwrap()
    }

    fn moves(result: &Value) -> Vec<Value> {
        result["moves"].as_array().cloned().unwrap_or_default()
    }

    #[test]
    fn running_late_moves_name_the_block() {
        let result = late_monday("late-names");
        let moved = moves(&result);
        let essay = moved
            .iter()
            .find(|item| item["block_id"] == "essay-session");
        assert!(essay.is_some(), "the Essay session moves: {moved:?}");
        assert_eq!(
            essay.unwrap().get("title").and_then(Value::as_str),
            Some("History essay"),
            "a move names its block by the stored title"
        );
    }

    #[test]
    fn running_late_moves_carry_a_plain_why() {
        let result = late_monday("late-why");
        for item in moves(&result) {
            let why = item.get("why").and_then(Value::as_str).unwrap_or("");
            assert!(!why.is_empty(), "every move says why: {item}");
            assert!(
                !why.split_whitespace()
                    .any(|word| word.contains('_') && word.chars().any(char::is_uppercase)),
                "why is words, not a code: {why}"
            );
            assert!(
                !why.contains("missed a day"),
                "running late is not a missed day: {why}"
            );
        }
    }

    #[test]
    fn running_late_moves_only_work_that_has_a_time_at_both_ends_and_never_a_fixed_block() {
        let result = late_monday("late-ends");
        for item in moves(&result) {
            assert!(
                item["from_start"].is_string() && item["to_start"].is_string(),
                "{item}"
            );
            assert!(
                !["school", "soccer"].contains(&item["block_id"].as_str().unwrap_or("")),
                "{item}"
            );
            let start =
                flexweek_engine::time::hhmm_to_minutes(item["to_start"].as_str().unwrap()).unwrap();
            assert!(
                item["to_day"] != 0 || start >= 16 * 60 + 30,
                "moved work starts after the late block ends: {item}"
            );
        }
        assert_eq!(
            result["moved"],
            json!(moves(&result).len()),
            "the count is the list shown"
        );
    }

    /// The phone's Kotlin tests parse real output, not the fake core's: this file is it. Run with
    /// FLEXWEEK_WRITE_PHONE_FIXTURES=1 to write it after a deliberate change; otherwise the output must
    /// equal the file, and the Android test copy must equal it byte for byte.
    #[test]
    fn phone_fixture_running_late_matches_the_output_and_the_android_copy() {
        let mut result = late_monday("late-fixture");
        // Random per run; the phone only passes it back.
        result["applied_preview"] = json!("preview-id");
        for block in result["placed"].as_array_mut().unwrap() {
            if block["id"]
                .as_str()
                .is_some_and(|id| id.starts_with("b-late-"))
            {
                block["id"] = json!("b-late-id");
            }
        }
        let text = format!("{}\n", serde_json::to_string_pretty(&result).unwrap());
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let fixture = root.join("tests/fixtures/phone/running-late-30.json");
        let copy = root.join("../../android/app/src/test/resources/phone/running-late-30.json");
        if std::env::var("FLEXWEEK_WRITE_PHONE_FIXTURES").as_deref() == Ok("1") {
            for path in [&fixture, &copy] {
                std::fs::create_dir_all(path.parent().unwrap()).unwrap();
                std::fs::write(path, &text).unwrap();
            }
        }
        let saved = std::fs::read_to_string(&fixture).expect("the phone fixture exists");
        assert_eq!(
            saved, text,
            "the output changed: rewrite the phone fixture and check the Kotlin tests"
        );
        let android = std::fs::read_to_string(&copy).expect("the Android copy exists");
        assert_eq!(
            android, saved,
            "the Android copy differs from the engine fixture"
        );
    }

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

    /// The slider offers every step of 5 from 5 minutes through 60; anything else is refused by
    /// the guard before the week is read.
    #[test]
    fn running_late_slider_takes_5_to_60_in_steps_of_5() {
        let (week, _) = open_at("late-slider", "2026-10-05T17:00:00");
        let db = week.db.lock().unwrap();
        flexweek_store::insert_assignment(
            &db,
            week.user_id.unwrap(),
            "essay",
            r#"{"id":"essay","title":"Essay","due":"2026-10-08T21:00","estimate_min":60,"focus_minutes":0,"completed":false}"#,
        )
        .unwrap();
        drop(db);
        save_week(
            &week,
            "2026-10-05",
            &json!([
                {"id":"school","title":"School","kind":"locked","days":[0],"start":"08:00","duration_min":390,"category":"class"},
                {"id":"essay-session","title":"Essay","kind":"flexible","days":[0],"start":"16:00","duration_min":60,"assignment_id":"essay","category":"assignments"}
            ]),
        );
        assert!(
            week.running_late(0, 5, 0.0).is_ok(),
            "5 minutes is a slider step"
        );
        assert!(
            week.running_late(0, 35, 0.0).is_ok(),
            "35 minutes is a slider step"
        );
        assert!(
            week.running_late(0, 60, 0.0).is_ok(),
            "60 minutes is a slider step"
        );
        assert!(
            week.running_late(0, 0, 0.0).is_err(),
            "0 minutes is below the slider's first step"
        );
        assert!(
            week.running_late(0, 7, 0.0).is_err(),
            "7 minutes is not a step of 5"
        );
        assert!(
            week.running_late(0, 65, 0.0).is_err(),
            "65 minutes is past the slider's last step"
        );
        assert!(
            week.running_late(0, -5, 0.0).is_err(),
            "-5 minutes is not a step of 5"
        );
    }
}
