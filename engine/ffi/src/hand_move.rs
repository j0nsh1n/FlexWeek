use chrono::Timelike;
use serde_json::{Value, json};

use crate::account::{assignment_map, hex_id, load_open_week, rollback, write_week};
use crate::core::{
    FfiError, FlexWeek, HandLanding, db_lock, engine_failure, failure, parse_local, require_user,
};
use flexweek_engine::desk::hand_move::{HandDrop, HandMove, WeekClock};

const DAYS_IN_WEEK: i64 = 7;
const KEPT_OPERATIONS: i64 = 1000;
const SLEEP: &str = "sleep";

fn check_monday(week_start: &str) -> Result<(), FfiError> {
    if week_start != flexweek_engine::time::monday_of(week_start).map_err(engine_failure)? {
        return Err(failure("week_start must be a Monday"));
    }
    Ok(())
}

/// Let go of a block at a new day and time, by the one rule in the engine, and save the week with the
/// revision check. A retry with the same operation id gets the first answer and saves nothing more.
pub(crate) fn hand_move(
    week: &FlexWeek,
    week_start: &str,
    landing: &HandLanding,
    op_id: &str,
) -> Result<String, FfiError> {
    let user_id = require_user(week)?;
    check_monday(week_start)?;
    let landing = &HandDrop {
        block_id: &landing.block_id,
        from_day: landing.from_day,
        to_day: landing.to_day,
        start_min: landing.start_min,
        end_min: landing.end_min,
    };
    let payload = json!([
        "hand_move",
        week_start,
        landing.block_id,
        landing.from_day,
        landing.to_day,
        landing.start_min,
        landing.end_min
    ])
    .to_string();
    let db = db_lock(week)?;
    if !op_id.is_empty() {
        match flexweek_store::recall_operation(
            &db,
            user_id,
            op_id,
            &flexweek_store::digest(&payload),
        )
        .map_err(failure)?
        {
            flexweek_store::Recall::Hit(response) => return Ok(response),
            flexweek_store::Recall::Conflict => {
                return Err(failure("operation id was already used for another change"));
            }
            flexweek_store::Recall::Missing => {}
        }
    }
    let (keyed, _, _) = assignment_map(&db, user_id)?;
    let assignments = Value::Object(keyed);
    let (blocks, revision) = load_open_week(&db, user_id, week_start, &assignments)?;
    let local = parse_local(&week.host.local_now())?;
    let now_iso = local.format("%Y-%m-%d").to_string();
    let clock = WeekClock {
        week_start,
        now_iso: &now_iso,
        now_min: i64::from(local.time().hour()) * 60 + i64::from(local.time().minute()),
    };
    let made = format!("b-hand-{}", hex_id(&week.host.random_bytes(8)));
    let answer = flexweek_engine::desk::hand_move::hand_move(
        &Value::Array(blocks),
        landing,
        &clock,
        &assignments,
        &mut || made.clone(),
    )
    .map_err(engine_failure)?;
    let HandMove::Moved {
        blocks,
        block_id,
        beside,
    } = answer
    else {
        return Ok(answer.to_value().to_string());
    };
    let block = blocks
        .iter()
        .find(|item| item.get("id").and_then(Value::as_str) == Some(block_id.as_str()))
        .cloned();
    write_week(&db, user_id, week_start, &Value::Array(blocks), revision)?;
    let response =
        json!({"moved": true, "block_id": block_id, "block": block, "beside": beside}).to_string();
    if !op_id.is_empty()
        && let Err(error) = flexweek_store::remember_operation(
            &db,
            user_id,
            op_id,
            &flexweek_store::digest(&payload),
            &response,
            KEPT_OPERATIONS,
        )
    {
        rollback(&db);
        return Err(failure(error));
    }
    db.execute_batch("COMMIT").map_err(failure)?;
    drop(db);
    week.host.data_changed("week".into());
    Ok(response)
}

/// The week's timed blocks for each of its seven days, sleep left out. `movable` is homework that
/// the hand-move rule would pin: linked, flexible and not finished.
pub(crate) fn week_blocks(week: &FlexWeek, week_start: &str) -> Result<String, FfiError> {
    let user_id = require_user(week)?;
    check_monday(week_start)?;
    let start = chrono::NaiveDate::parse_from_str(week_start, "%Y-%m-%d").map_err(failure)?;
    let db = db_lock(week)?;
    let (keyed, _, _) = assignment_map(&db, user_id)?;
    let assignments = Value::Object(keyed);
    let (blocks, _) = load_open_week(&db, user_id, week_start, &assignments)?;
    drop(db);
    let model = flexweek_engine::desk::weekmodel::build_week(
        &json!(week_start),
        &Value::Array(blocks.clone()),
        &assignments,
        &json!({}),
    )
    .map_err(engine_failure)?;
    let occurrences = model["occurrences"].as_array().cloned().unwrap_or_default();
    let mut days = Vec::new();
    for day in 0..DAYS_IN_WEEK {
        let mut listed = Vec::new();
        for item in occurrences.iter().filter(|item| {
            item["day"].as_i64() == Some(day)
                && item["category"].as_str() != Some(SLEEP)
                && item["missed"].as_bool() != Some(true)
        }) {
            let source = blocks
                .iter()
                .find(|block| block.get("id") == item.get("block_id"));
            let linked = match source {
                Some(block) => {
                    flexweek_engine::desk::grid::linked_homework(block).map_err(engine_failure)?
                }
                None => false,
            };
            listed.push(json!({
                "id": item["block_id"],
                "title": item["title"],
                "category": item["category"],
                "start_min": item["start"],
                "end_min": item["end"],
                "homework": crate::week_rows::is_homework(item),
                "movable": linked && item["done"].as_bool() != Some(true),
            }));
        }
        days.push(json!({
            "day": day,
            "date": (start + chrono::Days::new(day as u64)).to_string(),
            "blocks": listed,
        }));
    }
    Ok(json!({"week_start": week_start, "days": days}).to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::tests_support::{open_at, save_week};
    use std::sync::Arc;

    const MONDAY: &str = "2026-10-19";
    const MON: i64 = 0;
    const TUE: i64 = 1;
    const ALGEBRA_START_MIN: i64 = 14 * 60 + 30;
    const ALGEBRA_END_MIN: i64 = 16 * 60;
    const ALGEBRA_MINUTES: i64 = 90;

    fn fixture_week(name: &str, local: &str) -> Arc<FlexWeek> {
        let (week, _) = open_at(name, local);
        {
            let db = week.db.lock().unwrap();
            flexweek_store::insert_assignment(
                &db,
                week.user_id.unwrap(),
                "algebra-4",
                r#"{"id":"algebra-4","title":"Algebra set 4","due":"2026-10-23T23:59","estimate_min":90,"focus_minutes":0,"completed":false}"#,
            )
            .unwrap();
            db.execute_batch("COMMIT").unwrap();
        }
        save_week(
            &week,
            MONDAY,
            &json!([
                {"id":"school","title":"School","kind":"locked","days":[0,1,2,3,4],"start":"08:00","duration_min":390,"category":"class"},
                {"id":"algebra","title":"Algebra set 4","kind":"flexible","days":[0],"start":"14:30","duration_min":90,"category":"assignments","assignment_id":"algebra-4","work":true},
                {"id":"soccer","title":"Soccer","kind":"locked","days":[1],"start":"17:00","duration_min":60,"category":"sport"},
                {"id":"sleep","title":"Sleep","kind":"locked","days":[0,1,2,3,4,5,6],"start":"23:00","duration_min":420,"category":"sleep"}
            ]),
        );
        week
    }

    fn morning(name: &str) -> Arc<FlexWeek> {
        fixture_week(name, "2026-10-19T08:00:00")
    }

    fn blocks_of(week: &FlexWeek) -> Value {
        serde_json::from_str(&week.week_blocks(MONDAY.to_string()).unwrap()).unwrap()
    }

    fn landing(
        block_id: &str,
        from_day: i64,
        to_day: i64,
        start_min: i64,
        end_min: i64,
    ) -> HandLanding {
        HandLanding {
            block_id: block_id.into(),
            from_day,
            to_day,
            start_min,
            end_min,
        }
    }

    fn move_algebra(week: &FlexWeek, to_day: i64, op: &str) -> Value {
        serde_json::from_str(
            &week
                .hand_move(
                    MONDAY.into(),
                    landing("algebra", MON, to_day, ALGEBRA_START_MIN, ALGEBRA_END_MIN),
                    op.into(),
                )
                .unwrap(),
        )
        .unwrap()
    }

    fn day_blocks(output: &Value, day: usize) -> Vec<Value> {
        output["days"][day]["blocks"]
            .as_array()
            .cloned()
            .unwrap_or_default()
    }

    fn stored(week: &FlexWeek) -> Vec<Value> {
        let db = week.db.lock().unwrap();
        let (raw, _) = flexweek_store::read_week(&db, week.user_id.unwrap(), MONDAY)
            .unwrap()
            .unwrap();
        serde_json::from_str(&raw).unwrap()
    }

    #[test]
    fn week_blocks_lists_algebra_on_monday_as_movable_homework() {
        let output = blocks_of(&morning("wb-algebra"));
        let monday = day_blocks(&output, 0);
        assert!(!monday.is_empty(), "Monday has timed blocks: {output}");
        let algebra = monday.iter().find(|block| block["id"] == "algebra");
        assert!(algebra.is_some(), "Algebra set 4 is on Monday: {monday:?}");
        let algebra = algebra.unwrap();
        assert_eq!(algebra["title"], json!("Algebra set 4"));
        assert_eq!(algebra["category"], json!("assignments"));
        assert_eq!(algebra["start_min"], json!(ALGEBRA_START_MIN));
        assert_eq!(algebra["end_min"], json!(ALGEBRA_END_MIN));
        assert_eq!(algebra["homework"], json!(true));
        assert_eq!(algebra["movable"], json!(true));
    }

    #[test]
    fn week_blocks_has_seven_days_in_order() {
        let output = blocks_of(&morning("wb-days"));
        let days = output["days"].as_array().cloned().unwrap_or_default();
        assert_eq!(days.len(), 7, "one entry for each day of the week");
        for (index, day) in days.iter().enumerate() {
            assert_eq!(day["day"], json!(index), "Monday through Sunday");
        }
        assert_eq!(days[1]["date"], json!("2026-10-20"));
    }

    #[test]
    fn week_blocks_does_not_let_a_fixed_block_move() {
        let output = blocks_of(&morning("wb-fixed"));
        let monday = day_blocks(&output, 0);
        let school = monday.iter().find(|block| block["id"] == "school");
        assert!(school.is_some(), "School is on Monday: {monday:?}");
        assert_eq!(school.unwrap()["homework"], json!(false));
        assert_eq!(school.unwrap()["movable"], json!(false));
    }

    #[test]
    fn week_blocks_leaves_sleep_out() {
        let output = blocks_of(&morning("wb-sleep"));
        let monday = day_blocks(&output, 0);
        assert!(!monday.is_empty(), "Monday has timed blocks: {output}");
        assert!(
            monday.iter().all(|block| block["id"] != "sleep"),
            "sleep is not listed: {monday:?}"
        );
    }

    #[test]
    fn week_blocks_does_not_let_finished_homework_move() {
        let week = morning("wb-done");
        week.set_block_done(MONDAY.into(), "algebra".into(), MON, true, "done-1".into())
            .unwrap();
        let monday = day_blocks(&blocks_of(&week), 0);
        let algebra = monday.iter().find(|block| block["id"] == "algebra");
        assert!(
            algebra.is_some(),
            "finished homework is still listed: {monday:?}"
        );
        assert_eq!(algebra.unwrap()["movable"], json!(false));
    }

    #[test]
    fn week_blocks_refuses_a_date_that_is_not_a_monday() {
        let week = morning("wb-tuesday");
        let refused = week.week_blocks("2026-10-20".into());
        assert!(refused.is_err(), "a Tuesday is refused");
        assert_eq!(
            refused.unwrap_err().to_string(),
            "week_start must be a Monday"
        );
    }

    #[test]
    fn hand_move_puts_homework_on_the_new_day_with_its_time_and_pins_it() {
        let week = morning("hm-tuesday");
        let answer = move_algebra(&week, TUE, "move-1");
        assert_eq!(answer["moved"], json!(true), "{answer}");
        assert_eq!(answer["block_id"], json!("algebra"));
        let saved = stored(&week);
        let algebra = saved.iter().find(|block| block["id"] == "algebra");
        assert!(algebra.is_some(), "the block was saved: {saved:?}");
        let algebra = algebra.unwrap();
        assert_eq!(algebra["days"], json!([TUE]));
        assert_eq!(algebra["start"], json!("14:30"));
        assert_eq!(algebra["duration_min"], json!(ALGEBRA_MINUTES));
        assert_eq!(algebra["pinned"], json!(true));
        let tuesday = day_blocks(&blocks_of(&week), 1);
        let shown = tuesday.iter().find(|block| block["id"] == "algebra");
        assert!(
            shown.is_some(),
            "the week now shows it on Tuesday: {tuesday:?}"
        );
        assert_eq!(shown.unwrap()["start_min"], json!(ALGEBRA_START_MIN));
    }

    #[test]
    fn hand_move_keeps_every_other_block_as_it_was() {
        let week = morning("hm-others");
        let before = stored(&week);
        let answer = move_algebra(&week, TUE, "move-others");
        assert_eq!(answer["moved"], json!(true), "{answer}");
        let after = stored(&week);
        assert_eq!(after.len(), before.len(), "no block appeared or vanished");
        assert!(!before.is_empty(), "the week was saved before the move");
        for id in ["school", "soccer", "sleep"] {
            let was = before.iter().find(|block| block["id"] == id);
            assert!(was.is_some(), "{id} was in the week: {before:?}");
            let now = after.iter().find(|block| block["id"] == id);
            assert_eq!(now, was, "{id} is untouched");
        }
    }

    #[test]
    fn hand_move_repeated_with_the_same_operation_id_changes_nothing_more() {
        let week = morning("hm-retry");
        let first = move_algebra(&week, TUE, "move-retry");
        assert_eq!(first["moved"], json!(true), "{first}");
        let revision = {
            let db = week.db.lock().unwrap();
            flexweek_store::read_week(&db, week.user_id.unwrap(), MONDAY)
                .unwrap()
                .unwrap()
                .1
        };
        let again = move_algebra(&week, TUE, "move-retry");
        assert_eq!(again, first, "the retry gets the first answer");
        let after = {
            let db = week.db.lock().unwrap();
            flexweek_store::read_week(&db, week.user_id.unwrap(), MONDAY)
                .unwrap()
                .unwrap()
                .1
        };
        assert_eq!(after, revision, "the retry saved nothing");
    }

    #[test]
    fn hand_move_refuses_an_operation_id_used_for_another_change() {
        let week = morning("hm-conflict");
        let first = move_algebra(&week, TUE, "move-reuse");
        assert_eq!(first["moved"], json!(true), "{first}");
        let other = week.hand_move(
            MONDAY.into(),
            landing("algebra", TUE, 2, ALGEBRA_START_MIN, ALGEBRA_END_MIN),
            "move-reuse".into(),
        );
        assert!(other.is_err(), "the reused id is refused");
        assert_eq!(
            other.unwrap_err().to_string(),
            "operation id was already used for another change"
        );
    }

    #[test]
    fn hand_move_gives_back_the_refusal_and_saves_nothing() {
        let week = morning("hm-refused");
        let before = stored(&week);
        let answer: Value = serde_json::from_str(
            &week
                .hand_move(
                    MONDAY.into(),
                    landing("algebra", MON, TUE, ALGEBRA_START_MIN, ALGEBRA_START_MIN),
                    "move-bad".into(),
                )
                .unwrap(),
        )
        .unwrap();
        assert_eq!(answer["moved"], json!(false), "{answer}");
        assert_eq!(
            answer["problem"],
            json!("The end has to come after the start, so it stayed where it was.")
        );
        assert_eq!(stored(&week), before, "a refusal saves nothing");
    }

    #[test]
    fn hand_move_refuses_a_start_that_has_already_passed() {
        let week = fixture_week("hm-past", "2026-10-19T15:00:00");
        let answer: Value = serde_json::from_str(
            &week
                .hand_move(
                    MONDAY.into(),
                    landing("algebra", MON, MON, 9 * 60, 9 * 60 + ALGEBRA_MINUTES),
                    "move-past".into(),
                )
                .unwrap(),
        )
        .unwrap();
        assert_eq!(answer["moved"], json!(false), "{answer}");
        assert_eq!(
            answer["problem"],
            json!("That time has passed. Choose 15:00 or later today, or another day.")
        );
    }

    #[test]
    fn hand_move_refuses_a_block_that_is_not_in_the_week() {
        let week = morning("hm-missing");
        let answer: Value = serde_json::from_str(
            &week
                .hand_move(
                    MONDAY.into(),
                    landing("nothing", MON, TUE, ALGEBRA_START_MIN, ALGEBRA_END_MIN),
                    "move-missing".into(),
                )
                .unwrap(),
        )
        .unwrap();
        assert_eq!(answer["moved"], json!(false), "{answer}");
        assert_eq!(
            answer["problem"],
            json!("That block is not in this week, so nothing moved.")
        );
    }

    #[test]
    fn hand_move_refuses_a_date_that_is_not_a_monday() {
        let week = morning("hm-tuesday-date");
        let refused = week.hand_move(
            "2026-10-20".into(),
            landing("algebra", MON, TUE, ALGEBRA_START_MIN, ALGEBRA_END_MIN),
            "move-date".into(),
        );
        assert!(refused.is_err(), "a Tuesday is refused");
        assert_eq!(
            refused.unwrap_err().to_string(),
            "week_start must be a Monday"
        );
    }

    /// The phone's Kotlin tests parse real output, not the fake core's: these files are it. Run with
    /// FLEXWEEK_WRITE_PHONE_FIXTURES=1 to write them after a deliberate change; otherwise the output
    /// must equal the file, and the Android test copy must equal it byte for byte.
    fn check_fixture(name: &str, result: &Value) {
        let text = format!("{}\n", serde_json::to_string_pretty(result).unwrap());
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let fixture = root.join(format!("tests/fixtures/phone/{name}"));
        let copy = root.join(format!("../../android/app/src/test/resources/phone/{name}"));
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
    fn phone_fixture_hand_move_matches_the_output_and_the_android_copy() {
        let answer = move_algebra(&morning("hm-fixture"), TUE, "move-fixture");
        check_fixture("hand-move.json", &answer);
        assert_eq!(answer["block"]["days"], json!([TUE]));
        assert_eq!(answer["block"]["start"], json!("14:30"));
        assert_eq!(answer["block"]["pinned"], json!(true));
    }

    #[test]
    fn phone_fixture_week_blocks_matches_the_output_and_the_android_copy() {
        let output = blocks_of(&morning("wb-fixture"));
        check_fixture("week-blocks.json", &output);
        let monday = day_blocks(&output, 0);
        let algebra = monday
            .iter()
            .find(|block| block["id"] == "algebra")
            .unwrap();
        assert_eq!(algebra["start_min"], json!(ALGEBRA_START_MIN));
        assert_eq!(algebra["movable"], json!(true));
    }
}
