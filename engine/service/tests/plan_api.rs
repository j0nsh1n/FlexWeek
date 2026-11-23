//! What the Plan button answers: lengths it takes or refuses, the shape of a replan after a missed block, the
//! missed-day rules, and running late (a preview that writes nothing, its refusals, the moved block and its
//! sentence). Where a session lands is the engine's (engine/engine/tests/test_solver.rs). The Rust twins of
//! backend/tests/test_solve_endpoint.py and test_running_late_api.py.

use flexweek_service::plans::{Stopwatch, plan};
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::week_saves::save_week;
use flexweek_service::{Refusal, ServiceError, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const LATE_MESSAGE: &str = "Moved after you ran late so the rest of the day still fits.";

fn homework(changes: Value) -> Value {
    let mut block = json!({ "id": "hw", "title": "Homework", "kind": "flexible", "duration_min": 60, "days": [0],
                            "priority": 3, "energy": "medium" });
    for (key, value) in changes.as_object().unwrap() {
        block[key] = value.clone();
    }
    block
}

fn fixed(id: &str, title: &str, start: &str, minutes: i64, missed: Option<Value>) -> Value {
    let mut block = json!({ "id": id, "title": title, "kind": "locked", "duration_min": minutes, "days": [0],
                            "priority": 1, "energy": "medium", "start": start });
    if let Some(missed) = missed {
        block["missed_days"] = missed;
    }
    block
}

fn solve(db: &TestDb, user: i64, given: Value) -> Result<Value, ServiceError> {
    let start_clock = || -> Stopwatch { Box::new(|| 0.0) };
    plan(&db.path, user, &given, &start_clock)
}

fn invalid(result: Result<Value, ServiceError>) -> bool {
    matches!(result, Err(ServiceError::Refused(Refusal::Invalid(_))))
}

fn work_hours(db: &TestDb, user: i64, buffer: Option<i64>) {
    let mut prefs = read_preferences(&db.path, user).unwrap();
    prefs["work_windows"] =
        json!([{ "days": [0, 1, 2, 3, 4, 5, 6], "start": "06:00", "end": "23:00" }]);
    if let Some(buffer) = buffer {
        prefs["buffer_min"] = json!(buffer);
    }
    write_preferences(&db.path, user, &prefs).unwrap();
}

fn moved(trace: &Value) -> Value {
    trace["moves"]
        .as_array()
        .unwrap()
        .iter()
        .find(|m| m["reason"] == "RESHUFFLE_AFTER_MISS")
        .unwrap()
        .clone()
}

#[test]
fn a_block_of_no_length_is_refused() {
    let db = TestDb::new("plan-zero");
    let ana = db.account("ana");
    assert!(invalid(solve(
        &db,
        ana,
        json!({ "blocks": [homework(json!({ "duration_min": 0 }))] })
    )));
}

#[test]
fn a_block_on_the_grid_is_planned_and_the_answer_says_what_was_placed_and_how_long_it_took() {
    let db = TestDb::new("plan-ok");
    let ana = db.account("ana");
    let trace = solve(&db, ana, json!({ "blocks": [homework(json!({}))] })).unwrap();
    for key in ["placed", "unplaced", "solve_ms"] {
        assert!(trace.get(key).is_some(), "{key} missing from {trace}");
    }
}

#[test]
fn a_replan_after_a_missed_block_moves_the_homework_and_says_from_where_to_where() {
    let db = TestDb::new("plan-recover");
    let ana = db.account("ana");
    let school = fixed("school", "School", "06:00", 1020, None);
    let hw = homework(json!({ "days": [0, 1], "energy": "high" }));
    let solved = solve(&db, ana, json!({ "blocks": [school, hw] })).unwrap();
    let recover = json!({ "missed_block_id": "school", "missed_day": 0, "previous_placed": solved["placed"] });
    let trace = solve(
        &db,
        ana,
        json!({ "blocks": [school, hw], "recover": recover }),
    )
    .unwrap();
    assert_eq!(
        moved(&trace),
        json!({ "block_id": "hw", "reason": "RESHUFFLE_AFTER_MISS", "from_day": 1, "from_start": "06:00",
                "to_day": 0, "to_start": "06:00" })
    );
}

#[test]
fn a_replan_for_something_that_is_not_a_fixed_block_on_that_day_is_refused() {
    let db = TestDb::new("plan-recover-bad");
    let ana = db.account("ana");
    let recover = json!({ "missed_block_id": "hw", "missed_day": 0, "previous_placed": [] });
    assert!(invalid(solve(
        &db,
        ana,
        json!({ "blocks": [homework(json!({}))], "recover": recover })
    )));
}

#[test]
fn a_saved_week_keeps_a_missed_day_of_a_fixed_block() {
    let db = TestDb::new("plan-missed-saved");
    let ana = db.account("ana");
    let mut school = fixed("school", "School", "08:00", 60, Some(json!([0])));
    school["days"] = json!([0, 1]);
    save_week(
        &db.path,
        ana,
        &json!({ "week_start": "2026-09-07", "blocks": [school], "revision": 0 }),
    )
    .unwrap();
    assert_eq!(
        weeks::read_week(&db.path, ana, "2026-09-07").unwrap()["blocks"][0]["missed_days"],
        json!([0])
    );
}

#[test]
fn homework_cannot_be_marked_missed() {
    let db = TestDb::new("plan-flex-missed");
    let ana = db.account("ana");
    assert!(invalid(solve(
        &db,
        ana,
        json!({ "blocks": [homework(json!({ "missed_days": [0] }))] })
    )));
}

#[test]
fn a_replan_for_a_day_already_marked_missed_is_refused() {
    let db = TestDb::new("plan-missed-twice");
    let ana = db.account("ana");
    let school = fixed("school", "School", "08:00", 60, Some(json!([0])));
    let recover = json!({ "missed_block_id": "school", "missed_day": 0, "previous_placed": [] });
    assert!(invalid(solve(
        &db,
        ana,
        json!({ "blocks": [school], "recover": recover })
    )));
}

#[test]
fn running_late_is_a_preview_that_writes_nothing() {
    let db = TestDb::new("late-preview");
    let ana = db.account("ana");
    // The homework fills the one free hour before a fixed event, so this account chose no gap.
    work_hours(&db, ana, Some(0));
    let wind = fixed("wind", "Wind-down", "07:00", 960, None);
    let hw = homework(json!({ "energy": "high" }));
    let before = solve(&db, ana, json!({ "blocks": [wind, hw] })).unwrap();
    let placed: Vec<&str> = before["placed"]
        .as_array()
        .unwrap()
        .iter()
        .map(|b| b["id"].as_str().unwrap())
        .collect();
    assert!(
        placed.contains(&"wind") && placed.contains(&"hw"),
        "{placed:?}"
    );
    let late = json!({ "day": 0, "minutes": 60, "from_start": "06:00", "previous_placed": before["placed"] });
    let trace = solve(
        &db,
        ana,
        json!({ "blocks": [wind, hw], "running_late": late }),
    )
    .unwrap();
    let unplaced: Vec<&str> = trace["unplaced"]
        .as_array()
        .unwrap()
        .iter()
        .map(|b| b["id"].as_str().unwrap())
        .collect();
    assert_eq!(unplaced, ["hw"]);
    let wind_placed = trace["placed"]
        .as_array()
        .unwrap()
        .iter()
        .find(|b| b["id"] == "wind")
        .unwrap();
    assert_eq!(wind_placed["start"], "07:00");
    assert_eq!(
        weeks::read_week(&db.path, ana, "2026-09-14").unwrap(),
        json!({ "week_start": "2026-09-14", "blocks": [], "revision": 0 })
    );
}

#[test]
fn running_late_together_with_a_replan_or_by_45_minutes_is_refused() {
    let db = TestDb::new("late-refused");
    let ana = db.account("ana");
    let school = fixed("school", "School", "08:00", 60, None);
    let both = json!({
        "blocks": [school, homework(json!({}))],
        "recover": { "missed_block_id": "school", "missed_day": 0, "previous_placed": [] },
        "running_late": { "day": 0, "minutes": 30, "from_start": "14:30", "previous_placed": [] },
    });
    assert!(invalid(solve(&db, ana, both)));
    let odd = json!({ "blocks": [homework(json!({}))],
                      "running_late": { "day": 0, "minutes": 45, "from_start": "14:30", "previous_placed": [] } });
    assert!(invalid(solve(&db, ana, odd)));
}

#[test]
fn a_block_moved_for_running_late_says_so_in_its_own_sentence() {
    let db = TestDb::new("late-sentence");
    let ana = db.account("ana");
    work_hours(&db, ana, None);
    let school = fixed("school", "School", "08:00", 390, None);
    let hw = homework(json!({ "days": [0, 1], "energy": "high" }));
    let before = solve(&db, ana, json!({ "blocks": [school, hw] })).unwrap();
    let late = json!({ "day": 0, "minutes": 30, "from_start": "06:00", "previous_placed": before["placed"] });
    let trace = solve(
        &db,
        ana,
        json!({ "blocks": [school, hw], "running_late": late }),
    )
    .unwrap();
    let movement = moved(&trace);
    assert_eq!(
        (
            &movement["block_id"],
            &movement["from_start"],
            &movement["to_start"]
        ),
        (&json!("hw"), &json!("06:00"), &json!("06:30"))
    );
    let message = trace["explanations"]
        .as_array()
        .unwrap()
        .iter()
        .find(|item| item["block_id"] == "hw" && item["reason"] == "RESHUFFLE_AFTER_MISS")
        .unwrap()["message"]
        .clone();
    assert_eq!(message, LATE_MESSAGE);
}
