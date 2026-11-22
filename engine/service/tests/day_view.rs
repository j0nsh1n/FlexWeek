//! One day, as docs/stage2-contract.md describes GET /api/day: what is due soon, the day's sessions and
//! fixed blocks, the next thing to do, and the workload. Expected minutes come from the 00:00-24:00 grid,
//! not a recorded run; "now" is the tests' fixed moment, Thursday 5 November 2026 at 19:00. The Rust twins
//! of backend/tests/test_day_endpoint.py (its signed-out check stays with the routes, in
//! test_session_cookie_and_request_checks.py).

use std::path::PathBuf;

use flexweek_engine::plan::{Moment, parse_moment};
use flexweek_service::blocks::check_block;
use flexweek_service::views::{self, DATE_RULE};
use flexweek_service::{Refusal, ServiceError, with_db};
use serde_json::{Map, Value, json};

const DAY: &str = "2026-09-15";
const WEEK: &str = "2026-09-14";

fn now() -> Moment {
    parse_moment("2026-11-05T19:00").unwrap()
}

struct Db {
    dir: PathBuf,
    path: PathBuf,
}

impl Drop for Db {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

fn fresh(name: &str) -> Db {
    let dir = std::env::temp_dir().join(format!("flexweek-day-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("day.db");
    flexweek_store::initialize(&path, "2026-11-02").unwrap();
    Db { dir, path }
}

fn account(db: &Db, name: &str) -> i64 {
    with_db(&db.path, |conn| {
        let user = flexweek_store::insert_user(conn, name, "hash")?;
        flexweek_store::insert_preferences(conn, user, flexweek_store::PREFS_VERSION)?;
        Ok(user)
    })
    .unwrap()
}

fn merged(base: Value, changes: Value) -> Value {
    let mut out: Map<String, Value> = base.as_object().unwrap().clone();
    out.extend(changes.as_object().unwrap().clone());
    Value::Object(out)
}

/// A homework body as a save writes it.
fn homework(id: &str, changes: Value) -> Value {
    merged(
        json!({
            "id": id, "title": "Essay", "course": null, "category": "Homework", "priority": 3,
            "energy": "medium", "spotify_url": null, "due": "2026-09-16T23:59", "estimate_min": 120,
            "focus_minutes": 0, "focus_sessions": 0, "completed": false, "completed_at": null,
        }),
        changes,
    )
}

fn school() -> Value {
    json!({
        "id": "school", "title": "School", "kind": "locked", "duration_min": 390,
        "days": [0, 1, 2, 3, 4], "priority": 1, "energy": "medium", "start": "08:00",
        "category": "School",
    })
}

fn session(id: &str, changes: Value) -> Value {
    merged(
        json!({
            "id": id, "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [1],
            "priority": 3, "energy": "medium", "assignment_id": "hw-essay", "category": "Homework",
        }),
        changes,
    )
}

fn save_homework(db: &Db, user: i64, body: Value) {
    let id = body["id"].as_str().unwrap().to_string();
    with_db(&db.path, |conn| {
        flexweek_store::save_assignment(conn, user, &id, &body.to_string(), 0, 1000)?;
        Ok(())
    })
    .unwrap();
}

/// Saved as the week save writes blocks: each one written out in full.
fn save_week_from(db: &Db, user: i64, week: &str, blocks: &[Value]) {
    let written: Vec<Value> = blocks.iter().map(|b| check_block(b).unwrap()).collect();
    with_db(&db.path, |conn| {
        flexweek_store::save_week(conn, user, week, &Value::Array(written).to_string(), 0)?;
        Ok(())
    })
    .unwrap();
}

fn save_week(db: &Db, user: i64, blocks: &[Value]) {
    save_week_from(db, user, WEEK, blocks);
}

fn day_at(db: &Db, user: i64, date: &str, now: Moment) -> Value {
    views::day(&db.path, user, date, now).unwrap()
}

fn day(db: &Db, user: i64, date: &str) -> Value {
    day_at(db, user, date, now())
}

fn ids(list: &Value) -> Vec<&str> {
    list.as_array()
        .unwrap()
        .iter()
        .map(|item| item["id"].as_str().unwrap())
        .collect()
}

#[test]
fn an_empty_day_asks_to_add_and_has_the_whole_day_free() {
    let db = fresh("empty");
    let ana = account(&db, "ana");
    assert_eq!(
        day(&db, ana, DAY),
        json!({
            "date": DAY, "week_start": WEEK, "due_soon": [], "sessions": [], "locked": [],
            "next_action": { "kind": "add" },
            "workload": { "scheduled_min": 0, "focus_min": 0, "available_min": 1440, "by_category": [] },
        })
    );
}

#[test]
fn school_and_a_finished_session_leave_the_rest_of_the_day_free() {
    let db = fresh("school");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework(
            "hw-essay",
            json!({ "completed": true, "completed_at": "2026-09-15T17:00" }),
        ),
    );
    let done = session(
        "w1",
        json!({ "start": "16:00", "completed": true, "completed_day": 1 }),
    );
    save_week(&db, ana, &[school(), done]);
    let body = day(&db, ana, DAY);
    assert_eq!(body["next_action"], json!({ "kind": "add" }));
    assert_eq!(
        body["workload"],
        json!({
            "scheduled_min": 390 + 60, "focus_min": 60, "available_min": 1440 - 390 - 60,
            "by_category": [
                { "category": "School", "scheduled_min": 390, "focus_min": 0 },
                { "category": "Homework", "scheduled_min": 60, "focus_min": 60 },
            ],
        })
    );
    assert_eq!(ids(&body["locked"]), ["school"]);
    assert_eq!(ids(&body["sessions"]), ["w1"]);
    assert_eq!(body["sessions"][0]["start"], "16:00");
    assert_eq!(body["sessions"][0]["completed"], true);
}

#[test]
fn due_tomorrow_asks_to_plan_and_due_in_three_days_does_not() {
    let db = fresh("due");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    save_homework(
        &db,
        ana,
        homework(
            "later",
            json!({ "title": "Later", "due": "2026-09-18T12:00" }),
        ),
    );
    let body = day(&db, ana, DAY);
    assert_eq!(ids(&body["due_soon"]), ["hw-essay"]);
    let first = &body["due_soon"][0];
    assert_eq!(
        (
            &first["due"],
            &first["planned_min"],
            &first["unplanned_min"]
        ),
        (&json!("2026-09-16T23:59"), &json!(0), &json!(120))
    );
    assert_eq!(
        body["next_action"],
        json!({ "kind": "plan", "assignment_id": "hw-essay" })
    );
}

#[test]
fn a_placed_unfinished_session_is_the_next_thing_to_start() {
    let db = fresh("start");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    save_week(&db, ana, &[session("w1", json!({ "start": "16:00" }))]);
    let body = day(&db, ana, DAY);
    assert_eq!(
        body["next_action"],
        json!({ "kind": "start", "block_id": "w1" })
    );
    assert_eq!(body["sessions"][0]["start"], "16:00");
    assert_eq!(
        (
            &body["workload"]["scheduled_min"],
            &body["workload"]["focus_min"],
            &body["workload"]["available_min"]
        ),
        (&json!(60), &json!(0), &json!(1440 - 60))
    );
}

#[test]
fn overdue_open_homework_is_due_soon() {
    let db = fresh("overdue");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework("hw-essay", json!({ "due": "2026-09-14T12:00" })),
    );
    let body = day(&db, ana, DAY);
    assert_eq!(ids(&body["due_soon"]), ["hw-essay"]);
    assert_eq!(
        body["next_action"],
        json!({ "kind": "plan", "assignment_id": "hw-essay" })
    );
}

#[test]
fn a_malformed_or_out_of_range_date_is_refused() {
    let db = fresh("dates");
    let ana = account(&db, "ana");
    for date in ["2026-09-15T00:00", "1999-12-31", ""] {
        match views::day(&db.path, ana, date, now()) {
            Err(ServiceError::Refused(Refusal::Invalid(words))) => assert_eq!(words, DATE_RULE),
            other => panic!("{date:?} was not refused: {other:?}"),
        }
    }
}

#[test]
fn the_first_calendar_dates_use_the_single_lower_edge_week() {
    let db = fresh("edge");
    let ana = account(&db, "ana");
    let body = day(&db, ana, "2000-01-01");
    assert_eq!(
        (&body["date"], &body["week_start"], &body["sessions"]),
        (&json!("2000-01-01"), &json!("1999-12-27"), &json!([]))
    );
}

#[test]
fn a_day_does_not_show_another_accounts_week() {
    let db = fresh("other");
    let (ana, ben) = (account(&db, "ana"), account(&db, "ben"));
    save_homework(&db, ana, homework("hw-essay", json!({})));
    save_week(&db, ana, &[school()]);
    let body = day(&db, ben, DAY);
    assert_eq!(body["locked"], json!([]));
    assert_eq!(body["sessions"], json!([]));
    assert_eq!(body["due_soon"], json!([]));
    assert_eq!(body["workload"]["scheduled_min"], 0);
    assert_eq!(body["next_action"], json!({ "kind": "add" }));
}

#[test]
fn a_finished_session_counts_only_on_the_day_it_was_finished() {
    let db = fresh("finished-day");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework(
            "hw-essay",
            json!({ "completed": true, "completed_at": "2026-09-15T17:00" }),
        ),
    );
    let done = session(
        "w1",
        json!({ "days": [0, 1, 2], "start": "16:00", "completed": true, "completed_day": 1 }),
    );
    save_week(&db, ana, &[done]);
    let tuesday = day(&db, ana, "2026-09-15");
    assert_eq!(ids(&tuesday["sessions"]), ["w1"]);
    assert_eq!(
        (
            &tuesday["workload"]["scheduled_min"],
            &tuesday["workload"]["focus_min"]
        ),
        (&json!(60), &json!(60))
    );
    for other in ["2026-09-14", "2026-09-16"] {
        let body = day(&db, ana, other);
        assert_eq!(body["sessions"], json!([]), "{other}");
        assert_eq!(body["workload"]["scheduled_min"], 0, "{other}");
        assert_eq!(body["workload"]["focus_min"], 0, "{other}");
    }
}

#[test]
fn a_finished_session_with_no_named_day_counts_nowhere() {
    let db = fresh("no-day");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework(
            "hw-essay",
            json!({ "completed": true, "completed_at": "2026-09-15T17:00" }),
        ),
    );
    save_week(
        &db,
        ana,
        &[session(
            "w1",
            json!({ "days": [0, 1, 2], "completed": true }),
        )],
    );
    for date in ["2026-09-14", "2026-09-15", "2026-09-16"] {
        let body = day(&db, ana, date);
        assert_eq!(body["sessions"], json!([]), "{date}");
        assert_eq!(body["workload"]["focus_min"], 0, "{date}");
    }
}

#[test]
fn an_unfinished_session_is_offered_on_every_day_it_could_go() {
    let db = fresh("candidates");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    save_week(&db, ana, &[session("w1", json!({ "days": [0, 1, 2] }))]);
    for date in ["2026-09-14", "2026-09-15", "2026-09-16"] {
        let body = day(&db, ana, date);
        assert_eq!(ids(&body["sessions"]), ["w1"], "{date}");
        assert_eq!(body["workload"]["scheduled_min"], 0, "{date}");
        assert_eq!(body["workload"]["focus_min"], 0, "{date}");
    }
}

#[test]
fn only_homework_with_a_time_counts_as_planned() {
    let db = fresh("timed");
    let ana = account(&db, "ana");
    save_homework(&db, ana, homework("hw-essay", json!({})));
    let placed = session("w1", json!({ "start": "16:00" }));
    let waiting = session("w2", json!({ "days": [0, 1, 2] }));
    save_week(&db, ana, &[school(), placed, waiting]);
    let tuesday = day(&db, ana, DAY);
    let mut on_tuesday = ids(&tuesday["sessions"]);
    on_tuesday.sort_unstable();
    assert_eq!(on_tuesday, ["w1", "w2"]);
    assert_eq!(tuesday["workload"]["scheduled_min"], 390 + 60);
    let by_category: i64 = tuesday["workload"]["by_category"]
        .as_array()
        .unwrap()
        .iter()
        .map(|group| group["scheduled_min"].as_i64().unwrap())
        .sum();
    assert_eq!(by_category, 390 + 60);
    let monday = day(&db, ana, "2026-09-14");
    assert_eq!(ids(&monday["sessions"]), ["w2"]);
    assert_eq!(monday["workload"]["scheduled_min"], 390);
}

#[test]
fn a_due_with_no_time_sorts_after_a_morning_due_the_same_day() {
    let db = fresh("untimed");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework("allday", json!({ "title": "All day", "due": "2026-09-15" })),
    );
    save_homework(
        &db,
        ana,
        homework(
            "morning",
            json!({ "title": "Morning", "due": "2026-09-15T09:00" }),
        ),
    );
    assert_eq!(ids(&day(&db, ana, DAY)["due_soon"]), ["morning", "allday"]);
}

#[test]
fn work_finished_without_a_time_still_counts_as_planned_that_day() {
    let db = fresh("untimed-done");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework(
            "hw-essay",
            json!({ "completed": true, "completed_at": "2026-09-15T17:00" }),
        ),
    );
    save_week(&db, ana, &[session("w1", json!({ "completed": true }))]);
    let workload = &day(&db, ana, DAY)["workload"];
    assert_eq!(
        (&workload["scheduled_min"], &workload["focus_min"]),
        (&json!(60), &json!(60))
    );
}

/// Essay due Monday 9 November, 60 minutes, one session the week before on Friday 6 at 15:00. On
/// Thursday 5 at 19:00 that session is still ahead, so nothing more is needed; two days later it has
/// passed unfinished, so the hour is needed again.
#[test]
fn due_soon_counts_a_session_still_ahead_in_an_earlier_week_and_not_one_that_passed() {
    let db = fresh("ahead");
    let ana = account(&db, "ana");
    save_homework(
        &db,
        ana,
        homework(
            "hw-essay",
            json!({ "due": "2026-11-09T18:00", "estimate_min": 60 }),
        ),
    );
    save_week_from(
        &db,
        ana,
        "2026-11-02",
        &[session("s1", json!({ "days": [4], "start": "15:00" }))],
    );
    let thursday = day(&db, ana, "2026-11-09");
    assert_eq!(thursday["due_soon"][0]["unplanned_min"], 0);
    let saturday = day_at(
        &db,
        ana,
        "2026-11-09",
        parse_moment("2026-11-07T19:00").unwrap(),
    );
    assert_eq!(saturday["due_soon"][0]["unplanned_min"], 60);
}
