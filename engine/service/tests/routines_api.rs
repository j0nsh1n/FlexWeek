//! Routines (Settings > Routines: a saved week of School and activities to start from): saving one, an
//! old revision refused, blocks that overlap refused, deleting with its revision and a retry, the 50 limit,
//! and each account's own. The Rust twins of backend/tests/test_routines_api.py (its "a missing revision
//! is 422" reads the address and "needs a session" is the sign-in check; both go with the server in P2).

use flexweek_service::records::{
    ROUTINE_CONFLICT, ROUTINE_ID_MISMATCH, ROUTINE_LIMIT, ROUTINE_UNKNOWN, delete_routine,
    save_routine,
};
use flexweek_service::{Refusal, ServiceError, views};
use flexweek_testkit::TestDb;
use serde_json::{Map, Value, json};

const CREATED: &str = "2026-11-05T19:00";
const LATER: &str = "2026-11-06T08:15";

fn merge(into: &mut Value, changes: Value) {
    let fields: &mut Map<String, Value> = into.as_object_mut().unwrap();
    for (key, value) in changes.as_object().unwrap() {
        fields.insert(key.clone(), value.clone());
    }
}

fn school(changes: Value) -> Value {
    let mut block = json!({
        "template_id": "school", "title": "School", "days": [0, 1, 2, 3, 4], "start": "08:00", "duration_min": 390,
        "category": "School", "course": null, "priority": 1, "energy": "medium", "spotify_url": null,
    });
    merge(&mut block, changes);
    block
}

fn practice(changes: Value) -> Value {
    let mut block = json!({
        "template_id": "practice", "title": "Practice", "days": [1, 3], "start": "16:00", "duration_min": 90,
        "category": "Sport", "course": null, "priority": 2, "energy": "high", "spotify_url": null,
    });
    merge(&mut block, changes);
    block
}

fn routine(id: &str, changes: Value) -> Value {
    let mut body = json!({ "id": id, "name": "School week", "blocks": [school(json!({})), practice(json!({}))], "revision": 0 });
    merge(&mut body, changes);
    body
}

fn put(db: &TestDb, user: i64, body: &Value, now: &str) -> Result<Value, ServiceError> {
    save_routine(&db.path, user, body["id"].as_str().unwrap(), body, now)
}

fn listed(db: &TestDb, user: i64) -> Vec<Value> {
    views::routines(&db.path, user).unwrap()["routines"]
        .as_array()
        .unwrap()
        .clone()
}

/// (created_at, updated_at, the rest).
fn stamps(body: &Value) -> (Value, Value, Value) {
    let mut rest = body.clone();
    let fields = rest.as_object_mut().unwrap();
    let created = fields.shift_remove("created_at").unwrap();
    let updated = fields.shift_remove("updated_at").unwrap();
    (created, updated, rest)
}

fn refused<T: std::fmt::Debug>(result: Result<T, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

#[test]
fn a_new_account_has_no_routines() {
    let db = TestDb::new("routines-empty");
    let ana = db.account("ana");
    assert_eq!(
        views::routines(&db.path, ana).unwrap(),
        json!({ "routines": [] })
    );
}

#[test]
fn a_new_routine_is_revision_1_and_saving_it_again_unchanged_keeps_it_and_its_times() {
    let db = TestDb::new("routines-create");
    let ana = db.account("ana");
    let created = put(&db, ana, &routine("r-1", json!({})), CREATED).unwrap();
    let one = routine("r-1", json!({ "revision": 1 }));
    assert_eq!(
        stamps(&created),
        (json!(CREATED), json!(CREATED), one.clone())
    );
    let again = put(&db, ana, &routine("r-1", json!({})), LATER).unwrap();
    assert_eq!(
        stamps(&again),
        (json!(CREATED), json!(CREATED), one.clone())
    );
    assert_eq!(
        stamps(&listed(&db, ana)[0]),
        (json!(CREATED), json!(CREATED), one)
    );
}

#[test]
fn a_routine_block_at_any_minute_saves() {
    let db = TestDb::new("routines-minute");
    let ana = db.account("ana");
    let body = routine(
        "r-1",
        json!({ "blocks": [school(json!({ "start": "07:05", "duration_min": 400 }))] }),
    );
    let saved = put(&db, ana, &body, CREATED).unwrap();
    let blocks: Vec<(Value, Value)> = saved["blocks"]
        .as_array()
        .unwrap()
        .iter()
        .map(|block| (block["start"].clone(), block["duration_min"].clone()))
        .collect();
    assert_eq!(blocks, [(json!("07:05"), json!(400))]);
}

#[test]
fn a_change_saved_from_an_old_revision_is_refused_and_keeps_the_routine() {
    let db = TestDb::new("routines-stale");
    let ana = db.account("ana");
    put(&db, ana, &routine("r-1", json!({})), CREATED).unwrap();
    assert_eq!(
        refused(put(
            &db,
            ana,
            &routine("r-1", json!({ "name": "Next week" })),
            LATER
        )),
        Refusal::Conflict(ROUTINE_CONFLICT.to_string())
    );
    assert_eq!(listed(&db, ana)[0]["name"], "School week");
}

#[test]
fn a_change_moves_the_revision_and_the_last_changed_time_and_keeps_when_it_was_made() {
    let db = TestDb::new("routines-update");
    let ana = db.account("ana");
    put(&db, ana, &routine("r-1", json!({})), CREATED).unwrap();
    let updated = put(
        &db,
        ana,
        &routine("r-1", json!({ "name": "Busy week", "revision": 1 })),
        LATER,
    )
    .unwrap();
    assert_eq!(
        stamps(&updated),
        (
            json!(CREATED),
            json!(LATER),
            routine("r-1", json!({ "name": "Busy week", "revision": 2 }))
        )
    );
}

#[test]
fn the_id_in_the_address_must_be_the_routines_own() {
    let db = TestDb::new("routines-id");
    let ana = db.account("ana");
    assert_eq!(
        refused(save_routine(
            &db.path,
            ana,
            "r-1",
            &routine("r-2", json!({})),
            CREATED
        )),
        Refusal::Invalid(ROUTINE_ID_MISMATCH.to_string())
    );
}

#[test]
fn blocks_that_overlap_are_refused_and_nothing_is_saved() {
    let db = TestDb::new("routines-overlap");
    let ana = db.account("ana");
    let clash = practice(json!({ "start": "14:00", "duration_min": 120 }));
    let body = routine("r-1", json!({ "blocks": [school(json!({})), clash] }));
    assert!(matches!(
        refused(put(&db, ana, &body, CREATED)),
        Refusal::Invalid(_)
    ));
    assert!(listed(&db, ana).is_empty());
}

#[test]
fn blocks_that_touch_end_to_start_are_allowed() {
    let db = TestDb::new("routines-adjacent");
    let ana = db.account("ana");
    let next_to_school =
        practice(json!({ "start": "14:30", "duration_min": 90, "days": [0, 1, 2, 3, 4] }));
    let saved = put(
        &db,
        ana,
        &routine(
            "r-1",
            json!({ "blocks": [school(json!({})), next_to_school] }),
        ),
        CREATED,
    )
    .unwrap();
    assert_eq!(saved["blocks"][1]["start"], "14:30");
}

#[test]
fn deleting_a_routine_matches_its_revision_and_a_retry_with_its_operation_gets_the_first_answer() {
    let db = TestDb::new("routines-delete");
    let ana = db.account("ana");
    put(&db, ana, &routine("r-1", json!({})), CREATED).unwrap();
    let deleted = delete_routine(&db.path, ana, "r-1", Some(1), Some("op-del-1")).unwrap();
    assert_eq!(deleted, json!({ "id": "r-1" }));
    assert!(listed(&db, ana).is_empty());
    assert_eq!(
        delete_routine(&db.path, ana, "r-1", Some(1), Some("op-del-1")).unwrap(),
        json!({ "id": "r-1" })
    );
    assert_eq!(
        refused(delete_routine(&db.path, ana, "r-1", Some(1), None)),
        Refusal::NotFound(ROUTINE_UNKNOWN.to_string())
    );
}

#[test]
fn an_account_holds_at_most_50_routines() {
    let db = TestDb::new("routines-limit");
    let ana = db.account("ana");
    for index in 0..50 {
        let body = routine(
            &format!("r-{index}"),
            json!({ "name": format!("Week {index}"), "blocks": [school(json!({ "template_id": format!("school-{index}") }))] }),
        );
        put(&db, ana, &body, CREATED).unwrap();
    }
    assert_eq!(
        refused(put(
            &db,
            ana,
            &routine("r-50", json!({ "name": "Overflow" })),
            CREATED
        )),
        Refusal::Invalid(ROUTINE_LIMIT.to_string())
    );
    assert_eq!(listed(&db, ana).len(), 50);
}

#[test]
fn each_account_has_its_own_routines_under_the_same_ids() {
    let db = TestDb::new("routines-owned");
    let ana = db.account("ana");
    let ben = db.account("ben");
    put(&db, ana, &routine("r-1", json!({})), CREATED).unwrap();
    assert!(listed(&db, ben).is_empty());
    assert_eq!(
        refused(delete_routine(&db.path, ben, "r-1", Some(1), None)),
        Refusal::NotFound(ROUTINE_UNKNOWN.to_string())
    );
    let stolen = put(
        &db,
        ben,
        &routine("r-1", json!({ "name": "Stolen" })),
        CREATED,
    )
    .unwrap();
    assert_eq!(stolen["name"], "Stolen");
    assert_eq!(listed(&db, ana)[0]["name"], "School week");
    assert_eq!(listed(&db, ben)[0]["name"], "Stolen");
}
