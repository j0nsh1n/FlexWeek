//! The store behind the screens: the answer to a delete whose revision is far out of range, the order of the
//! fields in a delete's reply, and writes that roll back together. The Rust twins of
//! backend/tests/test_store_writes_and_reads.py. Its revisions beyond 64 bits are read by the server's query
//! parser, which goes with the server in P2; here the largest and smallest 64-bit revisions stand in.

use flexweek_engine::validate::routine;
use flexweek_service::changes::apply_changes;
use flexweek_service::homework_saves::save_homework;
use flexweek_service::records::{
    HOMEWORK_CONFLICT, HOMEWORK_UNKNOWN, ROUTINE_CONFLICT, ROUTINE_UNKNOWN, delete_homework,
    delete_routine, save_routine,
};
use flexweek_service::week_saves::{WEEK_CONFLICT, save_week};
use flexweek_service::{Refusal, ServiceError, views, with_db};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

const WEEK_A: &str = "2026-09-07";
const WEEK_B: &str = "2026-09-14";
const NOW: &str = "2026-11-05T19:00";
const FAR: [i64; 2] = [i64::MAX, i64::MIN];

fn assignment() -> Value {
    json!({
        "id": "hw-essay", "title": "Essay", "course": null, "category": null, "priority": 2, "energy": "low",
        "spotify_url": null, "due": "2026-09-15T23:59", "estimate_min": 120, "focus_minutes": 0,
        "focus_sessions": 0, "completed": false, "completed_at": null, "revision": 0,
    })
}

fn routine_body() -> Value {
    let mut body = routine(&json!({
        "id": "r1", "name": "Morning", "revision": 0,
        "blocks": [{ "template_id": "t1", "title": "Block", "days": [0, 1], "start": "08:00", "duration_min": 60 }],
    }))
    .unwrap()
    .to_value();
    body["revision"] = json!(0);
    body
}

fn school() -> Value {
    json!({ "id": "school", "title": "School", "kind": "locked", "duration_min": 390, "days": [0, 1, 2, 3, 4],
            "priority": 1, "energy": "medium", "start": "08:00", "category": "School" })
}

fn stored_session_week(db: &TestDb, user: i64) {
    save_homework(&db.path, user, "hw-essay", &assignment()).unwrap();
    let session = json!({ "id": "w1", "title": "stale title", "kind": "flexible", "duration_min": 60, "days": [0],
                          "priority": 3, "energy": "medium", "assignment_id": "hw-essay" });
    save_week(
        &db.path,
        user,
        &json!({ "week_start": WEEK_B, "blocks": [session], "revision": 0 }),
    )
    .unwrap();
}

fn refused_with(result: Result<Value, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

#[test]
fn deleting_homework_with_a_far_out_revision_answers_not_found_then_conflict() {
    for revision in FAR {
        let db = TestDb::new("store-far-homework");
        let ana = db.account("ana");
        assert!(matches!(
            refused_with(delete_homework(&db.path, ana, "hw-essay", Some(revision))),
            Refusal::NotFound(ref words) if words == HOMEWORK_UNKNOWN
        ));
        save_homework(&db.path, ana, "hw-essay", &assignment()).unwrap();
        assert!(matches!(
            refused_with(delete_homework(&db.path, ana, "hw-essay", Some(revision))),
            Refusal::Conflict(ref words) if words == HOMEWORK_CONFLICT
        ));
        delete_homework(&db.path, ana, "hw-essay", Some(1)).unwrap();
    }
}

#[test]
fn deleting_a_routine_with_a_far_out_revision_answers_not_found_then_conflict() {
    for revision in FAR {
        let db = TestDb::new("store-far-routine");
        let ana = db.account("ana");
        assert!(matches!(
            refused_with(delete_routine(&db.path, ana, "r1", Some(revision), None)),
            Refusal::NotFound(ref words) if words == ROUTINE_UNKNOWN
        ));
        save_routine(&db.path, ana, "r1", &routine_body(), NOW).unwrap();
        assert!(matches!(
            refused_with(delete_routine(&db.path, ana, "r1", Some(revision), Some("op-1"))),
            Refusal::Conflict(ref words) if words == ROUTINE_CONFLICT
        ));
        delete_routine(&db.path, ana, "r1", Some(1), None).unwrap();
    }
}

#[test]
fn the_reply_to_deleting_homework_lists_each_changed_week_before_its_revision() {
    let db = TestDb::new("store-delete-reply");
    let ana = db.account("ana");
    stored_session_week(&db, ana);
    let deleted = delete_homework(&db.path, ana, "hw-essay", Some(1)).unwrap();
    assert!(
        deleted.to_string().contains(&format!(
            r#""changed_weeks":[{{"week_start":"{WEEK_B}","revision":2}}]"#
        )),
        "{deleted}"
    );
}

#[test]
fn the_reply_to_a_batch_of_changes_lists_each_changed_week_before_its_revision() {
    let db = TestDb::new("store-batch-reply");
    let ana = db.account("ana");
    stored_session_week(&db, ana);
    let given = json!({ "weeks": [], "assignments": [{ "id": "hw-essay", "assignment": null, "revision": 1 }] });
    let batch = apply_changes(&db.path, ana, &given, "0123456789abcdef", NOW).unwrap();
    assert!(
        batch.to_string().contains(&format!(
            r#""changed_weeks":[{{"week_start":"{WEEK_B}","revision":2}}]"#
        )),
        "{batch}"
    );
}

#[test]
fn a_write_is_undone_when_a_later_write_in_the_same_connection_fails() {
    let db = TestDb::new("store-later-fails");
    let ana = db.account("ana");
    with_db(&db.path, |conn| {
        flexweek_store::insert_assignment(conn, ana, "hw-essay", r#"{"id":"hw-essay"}"#)?;
        Ok(())
    })
    .unwrap();
    let failed: Result<(), ServiceError> = with_db(&db.path, |conn| {
        // Python's connection begins a transaction before a raw write; rusqlite's does not.
        conn.execute("BEGIN DEFERRED", [])
            .map_err(flexweek_store::StoreError::Sqlite)?;
        conn.execute(
            "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, '[]', 1)",
            rusqlite::params![ana, WEEK_A],
        )
        .map_err(flexweek_store::StoreError::Sqlite)?;
        flexweek_store::insert_assignment(conn, ana, "hw-essay", r#"{"id":"hw-essay"}"#)?;
        Ok(())
    });
    assert!(failed.is_err());
    let conn = db.sql();
    let weeks: i64 = conn
        .query_row("SELECT COUNT(*) FROM weeks", [], |row| row.get(0))
        .unwrap();
    assert_eq!(weeks, 0);
    assert_eq!(flexweek_store::count_assignments(&conn, ana).unwrap(), 1);
}

#[test]
fn a_batch_that_saves_homework_then_hits_a_stale_week_leaves_no_homework() {
    let db = TestDb::new("store-batch-stale");
    let ana = db.account("ana");
    save_week(
        &db.path,
        ana,
        &json!({ "week_start": WEEK_A, "blocks": [], "revision": 0 }),
    )
    .unwrap();
    let mut fresh = assignment();
    fresh.as_object_mut().unwrap().shift_remove("revision");
    let given = json!({
        "weeks": [{ "week_start": WEEK_A, "blocks": [school()], "revision": 7 }],
        "assignments": [{ "id": "hw-essay", "assignment": fresh, "revision": 0 }],
    });
    assert!(matches!(
        refused_with(apply_changes(&db.path, ana, &given, "0123456789abcdef", NOW)),
        Refusal::Conflict(ref words) if words == WEEK_CONFLICT
    ));
    let now = flexweek_engine::plan::parse_moment(NOW).unwrap();
    assert_eq!(
        views::homework(&db.path, ana, WEEK_A, false, now).unwrap(),
        json!({ "assignments": [] })
    );
}

#[test]
fn replacing_an_account_that_fails_after_its_deletes_leaves_the_account_as_it_was() {
    let db = TestDb::new("store-replace-fails");
    let ana = db.account("ana");
    with_db(&db.path, |conn| {
        conn.execute(
            r#"INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?1, ?2, '[{"id":"old"}]', 3)"#,
            rusqlite::params![ana, WEEK_A],
        )
        .map_err(flexweek_store::StoreError::Sqlite)?;
        flexweek_store::insert_assignment(conn, ana, "old", r#"{"id":"old"}"#)?;
        Ok(())
    })
    .unwrap();
    let twice = (WEEK_B.to_string(), "[]".to_string(), 1);
    let failed: Result<(), ServiceError> = with_db(&db.path, |conn| {
        flexweek_store::replace_account(conn, ana, &[twice.clone(), twice], &[])?;
        Ok(())
    });
    assert!(failed.is_err());
    let conn = db.sql();
    let mut stmt = conn
        .prepare("SELECT week_start, blocks, revision FROM weeks WHERE user_id = ?1")
        .unwrap();
    let weeks = stmt
        .query_map([ana], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)?,
            ))
        })
        .unwrap()
        .collect::<Result<Vec<_>, _>>()
        .unwrap();
    assert_eq!(
        weeks,
        [(WEEK_A.to_string(), r#"[{"id":"old"}]"#.to_string(), 3)]
    );
    assert_eq!(flexweek_store::count_assignments(&conn, ana).unwrap(), 1);
}
