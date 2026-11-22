//! The app's multi-week save (`changes::apply_changes`, `POST /api/changes`): what lands where, what is
//! refused, and that a refusal leaves the account as it was.

use flexweek_service::changes::apply_changes;
use flexweek_service::homework_saves::ASSIGNMENT_CONFLICT;
use flexweek_service::records::OPERATION_CONFLICT;
use flexweek_service::week_saves::WEEK_CONFLICT;
use flexweek_service::{Refusal, ServiceError, weeks};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const NOW: &str = "2026-11-18T09:30";

fn block(id: &str, day: i64) -> Value {
    json!({
        "id": id, "title": id, "kind": "locked", "duration_min": 60, "days": [day], "start": "16:00",
        "category": "Club",
    })
}

fn homework(id: &str, title: &str) -> Value {
    json!({ "id": id, "title": title, "due": "2026-11-20T21:00", "estimate_min": 60 })
}

fn save(db: &TestDb, user: i64, given: Value) -> Result<Value, ServiceError> {
    apply_changes(&db.path, user, &given, "0123456789abcdef", NOW)
}

fn refused(result: Result<Value, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

fn ids(week: &Value) -> Vec<String> {
    week["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|block| block["id"].as_str().unwrap().to_string())
        .collect()
}

fn read(db: &TestDb, user: i64, week_start: &str) -> Value {
    weeks::read_week(&db.path, user, week_start).unwrap()
}

/// Two stored weeks, Monday 16 and Monday 23 November, seen from Thursday 19th.
fn two_weeks(db: &TestDb, user: i64) {
    save(
        db,
        user,
        json!({ "weeks": [
            { "week_start": "2026-11-16", "blocks": [block("mon", 0), block("thu", 3)], "revision": 0 },
            { "week_start": "2026-11-23", "blocks": [block("mon2", 0)], "revision": 0 },
        ] }),
    )
    .unwrap();
}

#[test]
fn a_week_on_screen_from_thursday_saves_into_both_stored_weeks_and_a_stale_one_is_refused() {
    let db = TestDb::new("shown");
    let user = db.account("alice");
    two_weeks(&db, user);
    let seen = read(&db, user, "2026-11-19");
    assert_eq!(seen["revision"], json!([1, 1]));
    // Saturday on screen is in the first stored week; next Tuesday is in the second.
    let mut blocks = seen["blocks"].as_array().unwrap().clone();
    blocks.push(block("sat", 2));
    blocks.push(block("tue2", 5));
    let given =
        json!({ "weeks": [{ "week_start": "2026-11-19", "blocks": blocks, "revision": [1, 1] }] });
    let answer = save(&db, user, given.clone()).unwrap();
    assert_eq!(answer["weeks"][0]["revision"], json!([2, 2]));
    assert_eq!(ids(&read(&db, user, "2026-11-16")), ["mon", "thu", "sat"]);
    assert_eq!(ids(&read(&db, user, "2026-11-23")), ["mon2", "tue2"]);
    assert_eq!(
        refused(save(&db, user, given)),
        Refusal::Conflict(WEEK_CONFLICT.to_string())
    );
    assert_eq!(read(&db, user, "2026-11-19")["revision"], json!([2, 2]));
}

/// Undo of a change made on the week from Thursday sends the stored Monday week it touched and the week on
/// screen together; the Monday week is written first, so the week on screen finds it as it means it.
#[test]
fn an_undo_of_a_monday_week_and_the_week_on_screen_together_lands_both() {
    let db = TestDb::new("undo");
    let user = db.account("alice");
    two_weeks(&db, user);
    let seen = read(&db, user, "2026-11-19");
    let first = seen["stored"][0].clone();
    let mut blocks = seen["blocks"].as_array().unwrap().clone();
    blocks.retain(|block| block["id"] != "mon2");
    let answer = save(
        &db,
        user,
        json!({ "weeks": [
            { "week_start": "2026-11-19", "blocks": blocks, "revision": seen["revision"] },
            { "week_start": "2026-11-16", "blocks": [block("mon", 0)], "revision": first["revision"] },
        ] }),
    )
    .unwrap();
    let starts: Vec<&str> = answer["weeks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|week| week["week_start"].as_str().unwrap())
        .collect();
    assert_eq!(starts, ["2026-11-16", "2026-11-19"]);
    assert_eq!(ids(&read(&db, user, "2026-11-16")), ["mon", "thu"]);
    assert!(ids(&read(&db, user, "2026-11-23")).is_empty());
}

#[test]
fn a_save_refused_part_way_keeps_none_of_its_earlier_parts() {
    let db = TestDb::new("all-or-nothing");
    let user = db.account("alice");
    two_weeks(&db, user);
    let refusal = refused(save(
        &db,
        user,
        json!({
            "assignments": [{ "id": "hw1", "assignment": homework("hw1", "Essay"), "revision": 0 }],
            "weeks": [{ "week_start": "2026-11-16", "blocks": [], "revision": 0 }],
            "snapshot_label": "Before",
        }),
    ));
    assert_eq!(refusal, Refusal::Conflict(WEEK_CONFLICT.to_string()));
    for table in ["assignments", "restore_points"] {
        assert_eq!(rows(&db, table), 0, "the refused save kept its {table}");
    }
    assert_eq!(ids(&read(&db, user, "2026-11-16")), ["mon", "thu"]);
    save(
        &db,
        user,
        json!({ "assignments": [{ "id": "hw1", "assignment": homework("hw1", "Essay"), "revision": 0 }] }),
    )
    .unwrap();
    assert_eq!(
        refused(save(
            &db,
            user,
            json!({ "assignments": [{ "id": "hw1", "assignment": homework("hw1", "Other"), "revision": 0 }] }),
        )),
        Refusal::Conflict(ASSIGNMENT_CONFLICT.to_string())
    );
}

fn rows(db: &TestDb, table: &str) -> i64 {
    rusqlite::Connection::open(&db.path)
        .unwrap()
        .query_row(&format!("SELECT count(*) FROM {table}"), [], |row| {
            row.get(0)
        })
        .unwrap()
}

#[test]
fn a_save_sent_again_gets_its_first_answer_and_other_data_under_its_name_is_refused() {
    let db = TestDb::new("again");
    let user = db.account("alice");
    let given = json!({
        "weeks": [{ "week_start": "2026-11-16", "blocks": [block("gym", 0)], "revision": 0 }],
        "operation_id": "op-1",
        "snapshot_label": "Before gym",
    });
    let first = save(&db, user, given.clone()).unwrap();
    assert_eq!(first["restore_point"]["label"], "Before gym");
    let again = save(&db, user, given.clone()).unwrap();
    assert_eq!(again, first);
    assert_eq!(
        read(&db, user, "2026-11-16")["revision"],
        1,
        "the second send wrote again"
    );
    let mut other = given;
    other["snapshot_label"] = json!("Other");
    assert_eq!(
        refused(save(&db, user, other)),
        Refusal::Conflict(OPERATION_CONFLICT.to_string())
    );
}
