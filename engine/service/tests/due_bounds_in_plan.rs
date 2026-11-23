//! How a homework's due date bounds where Plan places its sessions. Bounds and slack minutes are worked from
//! the calendar: the week of 2026-09-07 runs Monday 7 to Sunday 13 September. The Rust twins of
//! backend/tests/test_homework_due_bounds_in_solve.py.

use flexweek_service::homework_saves::save_homework;
use flexweek_service::plans::{Stopwatch, plan};
use flexweek_service::preferences::{read_preferences, write_preferences};
use flexweek_service::{Refusal, ServiceError, views};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const WEEK_ONE: &str = "2026-09-07";
const WEEK_TWO: &str = "2026-09-14";

fn assignment(changes: Value) -> Value {
    let mut body = json!({
        "id": "hw-essay", "title": "Essay", "course": null, "category": null, "priority": 3, "energy": "high",
        "spotify_url": null, "due": "2026-09-15T23:59", "estimate_min": 120, "focus_minutes": 0,
        "focus_sessions": 0, "completed": false, "completed_at": null, "revision": 0,
    });
    for (key, value) in changes.as_object().unwrap() {
        body[key] = value.clone();
    }
    body
}

fn session(id: &str, changes: Value) -> Value {
    let mut block = json!({ "id": id, "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [0],
                            "priority": 3, "energy": "high", "assignment_id": "hw-essay" });
    for (key, value) in changes.as_object().unwrap() {
        block[key] = value.clone();
    }
    block
}

fn homework(db: &TestDb, user: i64, changes: Value) {
    save_homework(&db.path, user, "hw-essay", &assignment(changes)).unwrap();
}

fn solve(
    db: &TestDb,
    user: i64,
    blocks: Value,
    week_start: Option<&str>,
) -> Result<Value, ServiceError> {
    let mut given = json!({ "blocks": blocks });
    if let Some(week_start) = week_start {
        given["week_start"] = json!(week_start);
    }
    let start_clock = || -> Stopwatch { Box::new(|| 0.0) };
    plan(&db.path, user, &given, &start_clock)
}

fn ids(blocks: &Value) -> Vec<&str> {
    blocks
        .as_array()
        .unwrap()
        .iter()
        .map(|block| block["id"].as_str().unwrap())
        .collect()
}

fn slack(trace: &Value) -> Value {
    trace["explanations"]
        .as_array()
        .unwrap()
        .iter()
        .find(|item| !item["slack_min"].is_null())
        .unwrap()
        .clone()
}

fn reasons(trace: &Value) -> Vec<&str> {
    let mut found: Vec<&str> = trace["moves"]
        .as_array()
        .unwrap()
        .iter()
        .map(|m| m["reason"].as_str().unwrap())
        .collect();
    found.sort_unstable();
    found.dedup();
    found
}

#[test]
fn a_week_is_needed_when_a_block_is_a_homework_session() {
    let db = TestDb::new("due-needs-week");
    let ana = db.account("ana");
    homework(&db, ana, json!({}));
    assert!(matches!(
        solve(
            &db,
            ana,
            json!([session("sun", json!({ "days": [6] }))]),
            None
        ),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
}

#[test]
fn another_accounts_homework_is_refused() {
    let db = TestDb::new("due-other");
    let ana = db.account("ana");
    let ben = db.account("ben");
    homework(&db, ana, json!({}));
    assert!(matches!(
        solve(
            &db,
            ben,
            json!([session("sun", json!({ "days": [6] }))]),
            Some(WEEK_ONE)
        ),
        Err(ServiceError::Refused(Refusal::Invalid(_)))
    ));
}

/// Due Tuesday 15 September 23:59: from Sunday 13 06:00 that is 2 days and 18 hours less one minute after the
/// session ends at 07:00, 3,900 minutes of slack; from Monday 14 06:00, 2,460.
#[test]
fn due_next_tuesday_places_sunday_this_week_and_monday_next_week() {
    let db = TestDb::new("due-tuesday");
    let ana = db.account("ana");
    homework(&db, ana, json!({ "due": "2026-09-15T23:59" }));
    let sun = solve(
        &db,
        ana,
        json!([session("sun", json!({ "days": [6] }))]),
        Some(WEEK_ONE),
    )
    .unwrap();
    let mon = solve(
        &db,
        ana,
        json!([session("mon", json!({ "days": [0] }))]),
        Some(WEEK_TWO),
    )
    .unwrap();
    assert_eq!(ids(&sun["placed"]), ["sun"]);
    assert_eq!(
        (&sun["placed"][0]["days"], &sun["placed"][0]["start"]),
        (&json!([6]), &json!("06:00"))
    );
    assert_eq!(sun["unplaced"], json!([]));
    let found = slack(&sun);
    assert_eq!(
        (&found["slack_min"], &found["slack_status"]),
        (&json!(3900), &json!("ok"))
    );
    assert_eq!(ids(&mon["placed"]), ["mon"]);
    assert_eq!(
        (&mon["placed"][0]["days"], &mon["placed"][0]["start"]),
        (&json!([0]), &json!("06:00"))
    );
    assert_eq!(slack(&mon)["slack_min"], 2460);
}

#[test]
fn due_sunday_at_2359_allows_a_session_that_ends_at_the_end_of_the_day() {
    let db = TestDb::new("due-sunday-2359");
    let ana = db.account("ana");
    let mut prefs = read_preferences(&db.path, ana).unwrap();
    prefs["work_windows"] =
        json!([{ "days": [0, 1, 2, 3, 4, 5, 6], "start": "06:00", "end": "23:00" }]);
    write_preferences(&db.path, ana, &prefs).unwrap();
    homework(&db, ana, json!({ "due": "2026-09-13T23:59" }));
    let trace = solve(
        &db,
        ana,
        json!([session(
            "sun",
            json!({ "days": [6], "earliest": "Sunday 22:00" })
        )]),
        Some(WEEK_ONE),
    )
    .unwrap();
    assert_eq!(ids(&trace["placed"]), ["sun"]);
    assert_eq!(trace["placed"][0]["start"], "22:00");
    assert_eq!(trace["complete"], true);
    assert_eq!(slack(&trace)["slack_min"], 60);
}

#[test]
fn due_monday_0000_next_week_puts_no_bound_inside_this_week() {
    let db = TestDb::new("due-monday-midnight");
    let ana = db.account("ana");
    homework(&db, ana, json!({ "due": "2026-09-14T00:00" }));
    let trace = solve(
        &db,
        ana,
        json!([session("sun", json!({ "days": [6] }))]),
        Some(WEEK_ONE),
    )
    .unwrap();
    assert_eq!(ids(&trace["placed"]), ["sun"]);
    assert_eq!(trace["placed"][0]["days"], json!([6]));
    assert_eq!(slack(&trace)["slack_min"], 1020);
}

#[test]
fn a_due_before_the_week_is_a_missed_deadline() {
    let db = TestDb::new("due-before");
    let ana = db.account("ana");
    homework(&db, ana, json!({ "due": "2026-09-06T23:59" }));
    let trace = solve(
        &db,
        ana,
        json!([session("mon", json!({ "days": [0] }))]),
        Some(WEEK_ONE),
    )
    .unwrap();
    assert_eq!(ids(&trace["unplaced"]), ["mon"]);
    assert_eq!(trace["placed"], json!([]));
    assert_eq!(reasons(&trace), ["DEADLINE_PASSED"]);
    assert!(
        trace["failed_constraints"]
            .as_array()
            .unwrap()
            .contains(&json!("DEADLINE_PASSED"))
    );
}

#[test]
fn finished_homework_keeps_its_done_sessions_and_drops_open_ones() {
    let db = TestDb::new("due-finished");
    let ana = db.account("ana");
    homework(
        &db,
        ana,
        json!({ "completed": true, "completed_at": "2026-09-13T07:00", "due": "2026-09-15T23:59" }),
    );
    let spent = session(
        "sun",
        json!({ "days": [6], "start": "06:00", "completed": true, "completed_day": 6 }),
    );
    let later = session("mon", json!({ "days": [0] }));
    let kept = solve(&db, ana, json!([spent, later]), Some(WEEK_ONE)).unwrap();
    let skipped = solve(&db, ana, json!([later]), Some(WEEK_TWO)).unwrap();
    assert_eq!(ids(&kept["placed"]), ["sun"]);
    assert_eq!(
        (&kept["placed"][0]["start"], &kept["placed"][0]["days"]),
        (&json!("06:00"), &json!([6]))
    );
    assert_eq!(kept["unplaced"], json!([]));
    assert_eq!(
        (
            &skipped["placed"],
            &skipped["unplaced"],
            &skipped["complete"]
        ),
        (&json!([]), &json!([]), &json!(true))
    );
}

#[test]
fn a_due_with_no_time_is_kept_and_bounds_plan_at_the_end_of_that_day() {
    let db = TestDb::new("due-date-only");
    let ana = db.account("ana");
    homework(&db, ana, json!({ "due": "2026-09-13" }));
    let now = flexweek_engine::plan::parse_moment("2026-09-07T08:00").unwrap();
    assert_eq!(
        views::homework(&db.path, ana, WEEK_ONE, false, now).unwrap()["assignments"][0]["due"],
        "2026-09-13"
    );
    let trace = solve(
        &db,
        ana,
        json!([session(
            "sun",
            json!({ "days": [6], "earliest": "Sunday 22:00" })
        )]),
        Some(WEEK_ONE),
    )
    .unwrap();
    assert_eq!(ids(&trace["placed"]), ["sun"]);
    assert_eq!(trace["placed"][0]["start"], "22:00");
    assert_eq!(trace["complete"], true);
    assert_eq!(slack(&trace)["slack_min"], 60);
}

#[test]
fn a_due_time_bounds_plan_at_that_minute() {
    let db = TestDb::new("due-minute");
    let ana = db.account("ana");
    homework(&db, ana, json!({ "due": "2026-09-07T09:00" }));
    let late = solve(
        &db,
        ana,
        json!([session(
            "mon",
            json!({ "days": [0], "earliest": "Monday 09:00" })
        )]),
        Some(WEEK_ONE),
    )
    .unwrap();
    assert_eq!(ids(&late["unplaced"]), ["mon"]);
    assert_eq!(reasons(&late), ["DEADLINE_PASSED"]);
    let on_time = solve(
        &db,
        ana,
        json!([session(
            "mon",
            json!({ "days": [0], "earliest": "Monday 08:00" })
        )]),
        Some(WEEK_ONE),
    )
    .unwrap();
    assert_eq!(ids(&on_time["placed"]), ["mon"]);
    assert_eq!(on_time["placed"][0]["start"], "08:00");
    assert_eq!(on_time["complete"], true);
}
