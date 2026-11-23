//! Study hours (Settings > Study hours, the work windows Plan places homework in): the day runs midnight to
//! midnight, a week saves blocks at its edges, and stored hours bind Plan. Placement inside the hours is
//! tested in engine/engine/tests/work_windows_plan.rs. The Rust twins of backend/tests/test_work_windows.py.

use flexweek_engine::time::{
    DAY_END_MIN, DAY_START_MIN, SLOTS_PER_DAY, hhmm_to_slot, minutes_to_hhmm,
};
use flexweek_service::plans::{Stopwatch, plan};
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::week_saves::save_week;
use flexweek_service::{Refusal, ServiceError, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const WEEK: &str = "2026-09-14";

fn solve(db: &TestDb, user: i64, blocks: Value) -> Value {
    let start_clock = || -> Stopwatch { Box::new(|| 0.0) };
    plan(&db.path, user, &json!({ "blocks": blocks }), &start_clock).unwrap()
}

fn with_hours(db: &TestDb, user: i64, windows: Value) -> Result<Value, ServiceError> {
    let mut prefs = read_preferences(&db.path, user).unwrap();
    prefs["work_windows"] = windows;
    write_preferences(&db.path, user, &prefs)
}

#[test]
fn the_day_runs_midnight_to_midnight() {
    assert_eq!((DAY_START_MIN, DAY_END_MIN, SLOTS_PER_DAY), (0, 1440, 96));
    assert_eq!(hhmm_to_slot("00:00").unwrap(), 0);
    assert_eq!(minutes_to_hhmm(1440), "24:00");
}

#[test]
fn a_week_saves_a_block_at_midnight_and_one_that_ends_at_24_00() {
    let db = TestDb::new("windows-edges");
    let ana = db.account("ana");
    let block = |id: &str, title: &str, start: &str| {
        json!({ "id": id, "title": title, "kind": "locked", "duration_min": 60, "days": [0], "start": start,
                "priority": 1, "energy": "low" })
    };
    let blocks = json!([
        block("night", "Night reading", "00:00"),
        block("late", "Late lab", "23:00")
    ]);
    save_week(
        &db.path,
        ana,
        &json!({ "week_start": WEEK, "blocks": blocks, "revision": 0 }),
    )
    .unwrap();
    let loaded = weeks::read_week(&db.path, ana, WEEK).unwrap()["blocks"].clone();
    let found: Vec<(Value, Value, Value)> = loaded
        .as_array()
        .unwrap()
        .iter()
        .map(|b| {
            (
                b["id"].clone(),
                b["start"].clone(),
                b["duration_min"].clone(),
            )
        })
        .collect();
    assert_eq!(
        found,
        [
            (json!("night"), json!("00:00"), json!(60)),
            (json!("late"), json!("23:00"), json!(60))
        ]
    );
}

#[test]
fn study_hours_may_end_at_midnight_but_not_where_they_start() {
    let db = TestDb::new("windows-midnight");
    let ana = db.account("ana");
    let saved = with_hours(
        &db,
        ana,
        json!([{ "days": [0], "start": "23:00", "end": "24:00" }]),
    )
    .unwrap();
    assert_eq!(saved["work_windows"][0]["end"], "24:00");
    assert!(matches!(
        with_hours(
            &db,
            ana,
            json!([{ "days": [0], "start": "23:00", "end": "23:00" }])
        ),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
}

#[test]
fn plan_without_stored_hours_still_plans_and_says_it_used_the_whole_day() {
    let db = TestDb::new("windows-none");
    let ana = db.account("ana");
    let essay = json!({ "id": "hw", "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [0],
                        "priority": 3, "energy": "high" });
    let trace = solve(&db, ana, json!([essay]));
    assert_eq!(trace["placed"][0]["start"], "06:00");
    assert_eq!(trace["work_windows_defaulted"], true);
    assert_eq!(
        trace["work_windows"][0],
        json!({ "days": [0, 1, 2, 3, 4, 5, 6], "start": "00:00", "end": "24:00" })
    );
}

#[test]
fn stored_study_hours_are_kept_and_bind_plan() {
    let db = TestDb::new("windows-stored");
    let ana = db.account("ana");
    let windows = json!([{ "days": [0], "start": "16:00", "end": "18:00" }]);
    assert_eq!(
        with_hours(&db, ana, windows.clone()).unwrap()["work_windows"],
        windows
    );
    let essay = json!({ "id": "hw", "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [0, 1],
                        "priority": 3, "energy": "medium" });
    let trace = solve(&db, ana, json!([essay]));
    assert_eq!(
        (&trace["placed"][0]["start"], &trace["placed"][0]["days"]),
        (&json!("16:00"), &json!([0]))
    );
    assert_eq!(trace["work_windows_defaulted"], false);
}
