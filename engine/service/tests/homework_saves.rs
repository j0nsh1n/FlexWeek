//! Saving a homework from the Homework list (spec.md): a save from an old revision is refused, the id in
//! the address must be the homework's own, saving the same homework again keeps its revision, and the limit
//! on how many homework an account holds counts only that account's.

use flexweek_service::homework_saves::{
    ASSIGNMENT_CONFLICT, ID_MISMATCH, save_homework, save_homework_up_to,
};
use flexweek_service::week_saves::ASSIGNMENT_LIMIT;
use flexweek_service::{Refusal, ServiceError};
use flexweek_testkit::TestDb;
use serde_json::{Value, json};

fn homework(id: &str, revision: i64) -> Value {
    json!({
        "id": id, "title": "Essay", "due": "2026-11-20T21:00", "estimate_min": 60, "revision": revision,
    })
}

fn refusal(result: Result<Value, ServiceError>) -> Refusal {
    match result {
        Err(ServiceError::Refused(refusal)) => refusal,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

#[test]
fn a_save_from_an_old_revision_is_refused_and_the_same_save_keeps_its_revision() {
    let db = TestDb::new("homework-revision");
    let ana = db.account("ana");
    let first = save_homework(&db.path, ana, "hw1", &homework("hw1", 0)).unwrap();
    assert_eq!(first["revision"], 1);
    let again = save_homework(&db.path, ana, "hw1", &homework("hw1", 1)).unwrap();
    assert_eq!(
        again["revision"], 1,
        "an identical save made a new revision"
    );
    let mut changed = homework("hw1", 0);
    changed["title"] = json!("Other");
    assert_eq!(
        refusal(save_homework(&db.path, ana, "hw1", &changed)),
        Refusal::Conflict(ASSIGNMENT_CONFLICT.to_string())
    );
}

#[test]
fn the_id_in_the_address_must_be_the_homeworks_own() {
    let db = TestDb::new("homework-id");
    let ana = db.account("ana");
    assert_eq!(
        refusal(save_homework(&db.path, ana, "hw9", &homework("hw1", 0))),
        Refusal::Invalid(ID_MISMATCH.to_string())
    );
}

#[test]
fn another_accounts_homework_does_not_count_toward_the_limit() {
    let db = TestDb::new("homework-limit");
    let (ana, ben) = (db.account("ana"), db.account("ben"));
    for id in ["b1", "b2"] {
        save_homework_up_to(&db.path, ben, id, &homework(id, 0), 2).unwrap();
    }
    assert_eq!(
        refusal(save_homework_up_to(
            &db.path,
            ben,
            "b3",
            &homework("b3", 0),
            2
        )),
        Refusal::Invalid(ASSIGNMENT_LIMIT.to_string())
    );
    save_homework_up_to(&db.path, ana, "a1", &homework("a1", 0), 2).unwrap();
}
