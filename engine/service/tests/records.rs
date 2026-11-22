//! Restore points on request, deleting routines and homework, and remembered operations: a retried
//! request gets its first answer and changes nothing more; an operation id reused with other data is
//! refused; a delete names a missing record or a changed one.

use std::path::PathBuf;

use flexweek_service::records::{
    self, HOMEWORK_CONFLICT, HOMEWORK_UNKNOWN, OPERATION_CONFLICT, ROUTINE_CONFLICT,
    ROUTINE_UNKNOWN,
};
use flexweek_service::{Refusal, ServiceError, views, with_db};
use serde_json::json;

struct Db {
    dir: PathBuf,
    path: PathBuf,
    user: i64,
}

impl Drop for Db {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

fn fresh(name: &str) -> Db {
    let dir = std::env::temp_dir().join(format!("flexweek-records-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("records.db");
    flexweek_store::initialize(&path, "2026-11-16").unwrap();
    let user = with_db(&path, |conn| {
        Ok(flexweek_store::insert_user(conn, "ana", "hash")?)
    })
    .unwrap();
    Db { dir, path, user }
}

fn refusal<T: std::fmt::Debug>(result: Result<T, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

fn points(db: &Db) -> usize {
    views::restore_points(&db.path, db.user).unwrap()["restore_points"]
        .as_array()
        .unwrap()
        .len()
}

#[test]
fn a_retried_restore_point_gives_its_first_answer_and_makes_no_second_point() {
    let db = fresh("point");
    let given = json!({ "label": "Before the trip", "operation_id": "op-1" });
    let first =
        records::create_restore_point(&db.path, db.user, &given, "aaaa", "2026-11-05T19:00")
            .unwrap();
    let again =
        records::create_restore_point(&db.path, db.user, &given, "bbbb", "2026-11-05T19:05")
            .unwrap();
    assert_eq!(first, again);
    assert_eq!(points(&db), 1);
    let other = json!({ "label": "Something else", "operation_id": "op-1" });
    let reused =
        records::create_restore_point(&db.path, db.user, &other, "cccc", "2026-11-05T19:06");
    assert_eq!(
        refusal(reused),
        Refusal::Conflict(OPERATION_CONFLICT.to_string())
    );
    assert_eq!(points(&db), 1);
}

#[test]
fn a_restore_point_needs_a_label_and_an_operation_id_and_nothing_else() {
    let db = fresh("point-input");
    for given in [
        json!({ "label": "   ", "operation_id": "op" }),
        json!({ "label": "", "operation_id": "op" }),
        json!({ "label": "x".repeat(81), "operation_id": "op" }),
        json!({ "label": "Trip" }),
        json!({ "label": "Trip", "operation_id": "op", "extra": 1 }),
        json!(["Trip"]),
    ] {
        let refused =
            records::create_restore_point(&db.path, db.user, &given, "t", "2026-11-05T19:00");
        assert!(matches!(refusal(refused), Refusal::Invalid(_)), "{given}");
    }
    assert_eq!(points(&db), 0);
}

fn routine(db: &Db) {
    with_db(&db.path, |conn| {
        let write = flexweek_store::RoutineWrite {
            id: "r1",
            name: "Morning",
            body: "[]",
            revision: 0,
            stamp: "2026-11-05T19:00",
            max_count: 50,
        };
        flexweek_store::save_routine(conn, db.user, write)?;
        Ok(())
    })
    .unwrap();
}

#[test]
fn deleting_a_routine_matches_its_revision_and_a_retry_gives_the_first_answer() {
    let db = fresh("routine");
    routine(&db);
    // A revision past 64 bits reaches the service as None: it never matches.
    let beyond = records::delete_routine(&db.path, db.user, "r1", None, None);
    assert_eq!(
        refusal(beyond),
        Refusal::Conflict(ROUTINE_CONFLICT.to_string())
    );
    let stale = records::delete_routine(&db.path, db.user, "r1", Some(7), None);
    assert_eq!(
        refusal(stale),
        Refusal::Conflict(ROUTINE_CONFLICT.to_string())
    );
    let gone = records::delete_routine(&db.path, db.user, "r1", Some(1), Some("op-del")).unwrap();
    assert_eq!(gone, json!({ "id": "r1" }));
    let retried =
        records::delete_routine(&db.path, db.user, "r1", Some(1), Some("op-del")).unwrap();
    assert_eq!(
        retried, gone,
        "a retried delete must give its first answer, not 'not found'"
    );
    let unknown = records::delete_routine(&db.path, db.user, "r1", Some(1), None);
    assert_eq!(
        refusal(unknown),
        Refusal::NotFound(ROUTINE_UNKNOWN.to_string())
    );
}

#[test]
fn deleting_homework_names_a_missing_or_changed_one() {
    let db = fresh("homework");
    let missing = records::delete_homework(&db.path, db.user, "hw", Some(0));
    assert_eq!(
        refusal(missing),
        Refusal::NotFound(HOMEWORK_UNKNOWN.to_string())
    );
    with_db(&db.path, |conn| {
        flexweek_store::insert_assignment(conn, db.user, "hw", r#"{"id":"hw"}"#)?;
        Ok(())
    })
    .unwrap();
    let stale = records::delete_homework(&db.path, db.user, "hw", Some(9));
    assert_eq!(
        refusal(stale),
        Refusal::Conflict(HOMEWORK_CONFLICT.to_string())
    );
    let beyond = records::delete_homework(&db.path, db.user, "hw", None);
    assert_eq!(
        refusal(beyond),
        Refusal::Conflict(HOMEWORK_CONFLICT.to_string())
    );
}
